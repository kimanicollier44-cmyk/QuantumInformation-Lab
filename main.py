#!/usr/bin/env python3
"""QuantumInformation-Lab - educational quantum information theory lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Education only - and the central lesson is stated up front:

  * Quantum information theory, at this scale, is bookkeeping on
    density matrices: entropies read off a spectrum, a Holevo chi
    computed from its definition, a Schumacher rate counted sequence
    by sequence, and entropy inequalities checked on states the lab
    actually constructed.
  * Every headline number is graded against a closed form or an
    exact identity - never against another run of the same code.
  * Dimensions stay small (at most 3 qubits). The lab proves
    identities and counting arguments. It builds NO compression
    codec, and it claims NO capacity theorem for any real channel.

One grading note, flagged honestly: the build brief for this lab
stated the Holevo chi of the {|0>, |+>} ensemble as
1 - h2((1 - 1/sqrt(2))/2) = 0.399124. Computed from the definition,
chi = S(average state) = h2((1 - 1/sqrt(2))/2) = 0.600876. The
brief's expression is not chi - it is exactly the accessible
information of the Helstrom-basis measurement on the same ensemble,
1 - h2(P_error). This lab asserts the TRUE chi and grades the
brief's expression where it actually belongs: as I_acc, with the
Holevo inequality I_acc <= chi holding as 0.399124 <= 0.600876.

Conventions, stated once and used everywhere:

  * All entropies are in bits (log base 2); 0 log 0 = 0.
  * S(rho) = -Tr rho log2 rho, from the eigenvalues of rho, which
    come from a from-scratch cyclic Jacobi Hermitian eigensolver
    that is refereed on known spectra before it is trusted.
  * Ensembles are lists of (probability, density matrix); chi is
    S(sum p_i rho_i) - sum p_i S(rho_i), computed from that
    definition every time.
  * The Schumacher source is the qubit source with eigenvalues
    (0.8, 0.2); its entropy is h2(0.2). Typical sets are frequency
    typical: sequences whose minority-symbol frequency lies within
    delta = 0.1 of 0.2, counted by explicit binomial sums.

Every real-world deployment use is a permanent HOLD gate - with
Gemini Argon 4 Extended Thinking as DECIDER (names-only,
tighten-only), Muse as advisor (never overrides HOLD), and Google
Flow plan-only seats.
"""
import cmath
import hashlib
import json
import math
import sys

# ---------------------------------------------------------------- constants
VERSION = "1.0.0"

SOURCE_P = 0.2          # minority eigenvalue of the Schumacher source
TYPICAL_DELTA = 0.1     # frequency window for the typical set
SCHUMACHER_NS = (4, 8, 12)

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "capacity_or_codec_claim": "HOLD - no channel capacity theorem and no compression codec is built, proved for a real system, or claimed here; only finite-n counting on a stated toy source",
    "compression_product_claim": "HOLD - no compression product, service, or fidelity guarantee for real data follows from a counting argument",
    "qkd_security_claim": "HOLD - no QKD or cryptographic security claim follows from a Holevo quantity computed on a toy ensemble",
    "real_device_entropy_claim": "HOLD - no entropy, purity, or state figure for any real device or prepared state is asserted",
    "entanglement_resource_claim": "HOLD - no claim that entanglement can be created, distributed, or consumed as a resource on any real hardware",
    "teleportation_service_claim": "HOLD - no teleportation service, fidelity guarantee, or network offering",
    "error_correction_product_claim": "HOLD - no error-correction product, code, or fault-tolerance claim is made or certified here",
    "hardware_specification_claim": "HOLD - no hardware specification (T1, T2, gate error, readout fidelity) for any real device is asserted",
    "vendor_performance_claim": "HOLD - no vendor system, processor, or link performance figure is stated, endorsed, or compared",
    "medical_or_sensing_claim": "HOLD - no medical, sensing, or metrology claim from entropy mathematics",
    "investment_claim": "HOLD - no investment claim; a lab model is not a prospectus",
    "certification_claim": "HOLD - no certification that any system meets any standard",
    "live_hardware_control": "HOLD - no control of real qubits, links, or laboratory hardware, ever",
    "model_as_measurement_claim": "HOLD - a computed number is a statement about the model at stated inputs, never a measurement",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ 1. Matrix kit
# Complex matrices as plain lists of lists, any size the lab needs
# (1 to 8). Everything - products, daggers, Kronecker products,
# partial traces - is written out so every number can be read.

def mat(rows):
    return [[complex(v) for v in row] for row in rows]


def eye(n):
    return [[complex(1 if i == j else 0) for j in range(n)] for i in range(n)]


def zeros(n, m=None):
    m = n if m is None else m
    return [[0j] * m for _ in range(n)]


def madd(A, B):
    return [[a + b for a, b in zip(ra, rb)] for ra, rb in zip(A, B)]


def mscale(A, s):
    return [[a * s for a in row] for row in A]


def mmul(A, B):
    n, m, k = len(A), len(B[0]), len(B)
    out = zeros(n, m)
    for i in range(n):
        for j in range(m):
            out[i][j] = sum(A[i][t] * B[t][j] for t in range(k))
    return out


def dagger(A):
    return [[A[j][i].conjugate() for j in range(len(A))]
            for i in range(len(A[0]))]


def mtrace(A):
    return sum(A[i][i] for i in range(len(A)))


def kron(A, B):
    """Kronecker product: out[(a,b),(c,d)] = A[a][c] * B[b][d]."""
    na, nb = len(A), len(B)
    out = zeros(na * nb)
    for a in range(na):
        for c in range(na):
            for b in range(nb):
                for d in range(nb):
                    out[a * nb + b][c * nb + d] = A[a][c] * B[b][d]
    return out


def frobenius(A):
    return math.sqrt(sum(abs(v) ** 2 for row in A for v in row))


def mat_max_dev(A, B):
    return max(abs(a - b) for ra, rb in zip(A, B) for a, b in zip(ra, rb))


PAULI_I = mat([[1, 0], [0, 1]])
PAULI_X = mat([[0, 1], [1, 0]])
PAULI_Y = mat([[0, -1j], [1j, 0]])
PAULI_Z = mat([[1, 0], [0, -1]])
PAULIS = (PAULI_X, PAULI_Y, PAULI_Z)


def hermitian_eigenvalues(A):
    """Eigenvalues of a Hermitian matrix by cyclic Jacobi rotations.

    Each rotation first phases the pivot element real, then applies
    the stable real Jacobi angle. Sweeps run until the off-diagonal
    Frobenius mass is below 1e-14 or 100 sweeps pass. Returns
    eigenvalues sorted ascending.
    """
    n = len(A)
    a = [[A[i][j] for j in range(n)] for i in range(n)]
    for _ in range(100):
        off = math.sqrt(sum(abs(a[p][q]) ** 2
                            for p in range(n) for q in range(p + 1, n)))
        if off < 1e-14:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                apq = a[p][q]
                b = abs(apq)
                if b < 1e-15:
                    continue
                app, aqq = a[p][p].real, a[q][q].real
                alpha = cmath.phase(apq)
                tau = (aqq - app) / (2.0 * b)
                if tau == 0.0:
                    t = -1.0
                else:
                    t = -math.copysign(
                        1.0 / (abs(tau) + math.sqrt(tau * tau + 1.0)), tau)
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                e_neg = cmath.exp(-1j * alpha)
                U = eye(n)
                U[p][p] = c
                U[q][q] = c * e_neg
                U[q][p] = s * e_neg
                U[p][q] = -s
                a = mmul(dagger(U), mmul(a, U))
    return sorted(a[i][i].real for i in range(n))


# ------------------------------------------------------------ splitmix64 RNG
_MASK64 = (1 << 64) - 1


class SplitMix64:
    """Deterministic splitmix64 stream - the lab's only randomness."""

    def __init__(self, seed):
        self.state = seed & _MASK64

    def next_u64(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
        return z ^ (z >> 31)

    def uniform(self):
        """Uniform double in [0, 1)."""
        return (self.next_u64() >> 11) / float(1 << 53)


def random_density_matrix(dim, seed):
    """A valid density matrix A A^dagger / Tr(A A^dagger) with A drawn
    from a seeded splitmix64 stream - deterministic, full rank."""
    rng = SplitMix64(seed)
    A = [[complex(2.0 * rng.uniform() - 1.0, 2.0 * rng.uniform() - 1.0)
          for _ in range(dim)] for _ in range(dim)]
    rho = mmul(A, dagger(A))
    tr = mtrace(rho).real
    return mscale(rho, 1.0 / tr)


def random_unitary(dim, seed):
    """A unitary by Gram-Schmidt on seeded random columns."""
    rng = SplitMix64(seed)
    cols = [[complex(2.0 * rng.uniform() - 1.0, 2.0 * rng.uniform() - 1.0)
             for _ in range(dim)] for _ in range(dim)]
    basis = []
    for j in range(dim):
        v = [cols[i][j] for i in range(dim)]
        for u in basis:
            proj = sum(x.conjugate() * y for x, y in zip(u, v))
            v = [y - proj * x for x, y in zip(u, v)]
        nrm = math.sqrt(sum(abs(x) ** 2 for x in v))
        basis.append([x / nrm for x in v])
    return [[basis[j][i] for j in range(dim)] for i in range(dim)]


# ================================================================ 2. States
def ket(vec):
    return [complex(v) for v in vec]


def projector(vec):
    v = ket(vec)
    nrm = math.sqrt(sum(abs(x) ** 2 for x in v))
    v = [x / nrm for x in v]
    return [[v[i] * v[j].conjugate() for j in range(len(v))]
            for i in range(len(v))]


def diag_state(probs):
    n = len(probs)
    out = zeros(n)
    for i, p in enumerate(probs):
        out[i][i] = p
    return out


KET_0 = ket([1, 0])
KET_1 = ket([0, 1])
KET_PLUS = ket([1 / math.sqrt(2), 1 / math.sqrt(2)])
KET_MINUS = ket([1 / math.sqrt(2), -1 / math.sqrt(2)])

RHO_0 = projector(KET_0)
RHO_1 = projector(KET_1)
RHO_PLUS = projector(KET_PLUS)
RHO_MINUS = projector(KET_MINUS)
RHO_MAXMIX_QUBIT = mscale(PAULI_I, 0.5)
RHO_MAXMIX_QUTRIT = mscale(eye(3), 1.0 / 3.0)
RHO_CLASSICAL_8020 = diag_state([0.8, 0.2])
RHO_CLASSICAL_3 = diag_state([0.5, 0.3, 0.2])

# Bell state |Phi+> = (|00> + |11>) / sqrt(2), and the GHZ state.
RHO_BELL = projector(ket([1 / math.sqrt(2), 0, 0, 1 / math.sqrt(2)]))
RHO_GHZ = projector(ket([1 / math.sqrt(2), 0, 0, 0, 0, 0, 0,
                         1 / math.sqrt(2)]))
# Classically correlated tripartite mixture (|000><000| + |111><111|)/2.
RHO_GHZ_MIX = mscale(madd(projector(ket([1, 0, 0, 0, 0, 0, 0, 0])),
                          projector(ket([0, 0, 0, 0, 0, 0, 0, 1]))), 0.5)
# Stated bipartite state for data processing: 0.7 Bell + 0.3 white noise.
RHO_DP = madd(mscale(RHO_BELL, 0.7), mscale(eye(4), 0.3 / 4.0))


def partial_trace(rho, dims, keep):
    """Trace out every subsystem except those in `keep` (index list).

    dims is the list of subsystem dimensions; rho acts on their
    tensor product in order. Index arithmetic only - no shortcuts.
    """
    n_sub = len(dims)
    total = 1
    for d in dims:
        total *= d
    keep = sorted(keep)
    out_dim = 1
    for i in keep:
        out_dim *= dims[i]
    strides = []
    acc = 1
    for d in reversed(dims):
        strides.append(acc)
        acc *= d
    strides = list(reversed(strides))

    def indices(flat):
        return [(flat // strides[i]) % dims[i] for i in range(n_sub)]

    out = zeros(out_dim)
    for r in range(total):
        ri = indices(r)
        for c in range(total):
            ci = indices(c)
            if all(ri[i] == ci[i] for i in range(n_sub) if i not in keep):
                orow = 0
                ocol = 0
                for i in keep:
                    orow = orow * dims[i] + ri[i]
                    ocol = ocol * dims[i] + ci[i]
                out[orow][ocol] += rho[r][c]
    return out


def reduced(rho, dims, keep):
    return partial_trace(rho, dims, keep)


# ================================================================ 3. Entropies
def binary_entropy(p):
    """h2(p) in bits, with h2(0) = h2(1) = 0."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p)


def shannon_entropy(probs):
    return sum(-p * math.log2(p) for p in probs if p > 0.0)


def von_neumann_entropy(rho):
    """S(rho) = -sum lam log2 lam over the Jacobi spectrum."""
    s = 0.0
    for lam in hermitian_eigenvalues(rho):
        if lam > 1e-15:
            s -= lam * math.log2(lam)
    return s


def purity(rho):
    """Tr rho^2 = sum of squared eigenvalues = Frobenius norm squared."""
    return sum(abs(v) ** 2 for row in rho for v in row)


def renyi_entropy(rho, alpha):
    """S_alpha = log2(sum lam^alpha) / (1 - alpha); alpha = inf gives
    the min-entropy -log2(lam_max)."""
    eigs = [max(lam, 0.0) for lam in hermitian_eigenvalues(rho)]
    if alpha == math.inf:
        val = -math.log2(max(eigs))
    else:
        total = sum(lam ** alpha for lam in eigs if lam > 0.0)
        val = math.log2(total) / (1.0 - alpha)
    return 0.0 if abs(val) < 1e-15 else val


def entropy_report():
    named = {
        "pure_|0>": RHO_0,
        "pure_|+>": RHO_PLUS,
        "maximally_mixed_qubit": RHO_MAXMIX_QUBIT,
        "maximally_mixed_qutrit": RHO_MAXMIX_QUTRIT,
        "classical_0.8_0.2": RHO_CLASSICAL_8020,
        "classical_0.5_0.3_0.2": RHO_CLASSICAL_3,
        "bell_joint_AB": RHO_BELL,
        "bell_reduced_A": reduced(RHO_BELL, [2, 2], [0]),
    }
    rows = {}
    for name, rho in named.items():
        rows[name] = {
            "dim": len(rho),
            "eigenvalues": [round(v, 6)
                            for v in hermitian_eigenvalues(rho)],
            "S_von_neumann": round(von_neumann_entropy(rho), 6),
            "purity": round(purity(rho), 6),
        }
    rows["shannon_0.8_0.2"] = round(shannon_entropy([0.8, 0.2]), 6)
    rows["shannon_0.5_0.3_0.2"] = round(shannon_entropy([0.5, 0.3, 0.2]), 6)
    rows["log2_3"] = round(math.log2(3.0), 6)
    return rows


def renyi_report():
    named = {
        "pure_|0>": RHO_0,
        "maximally_mixed_qubit": RHO_MAXMIX_QUBIT,
        "classical_0.8_0.2": RHO_CLASSICAL_8020,
        "bell_joint_AB": RHO_BELL,
        "seeded_random_qubit": random_density_matrix(2, 20261118),
    }
    rows = {}
    for name, rho in named.items():
        rows[name] = {
            "S1_von_neumann": round(von_neumann_entropy(rho), 6),
            "S2_collision": round(renyi_entropy(rho, 2.0), 6),
            "S_min": round(renyi_entropy(rho, math.inf), 6),
            "S2_le_S1": bool(renyi_entropy(rho, 2.0)
                             <= von_neumann_entropy(rho) + 1e-12),
        }
    rows["min_entropy_classical_8020_closed"] = round(-math.log2(0.8), 6)
    return rows


# ================================================================ 4. Ensembles + Holevo
def trine_states():
    """Three pure qubit states with Bloch vectors 120 degrees apart."""
    out = []
    for k in range(3):
        theta = 2.0 * math.pi * k / 3.0
        out.append(projector(ket([math.cos(theta), math.sin(theta)])))
    return out


ENSEMBLES = {
    "a_two_nonorthogonal": [(0.5, RHO_0), (0.5, RHO_PLUS)],
    "bb84_four_state": [(0.25, RHO_0), (0.25, RHO_1),
                        (0.25, RHO_PLUS), (0.25, RHO_MINUS)],
    "trine": [(1.0 / 3.0, rho) for rho in trine_states()],
}


def ensemble_average(ensemble):
    dim = len(ensemble[0][1])
    avg = zeros(dim)
    for p, rho in ensemble:
        avg = madd(avg, mscale(rho, p))
    return avg


def holevo_chi(ensemble):
    """chi = S(average) - sum p_i S(rho_i), from the definition."""
    avg = ensemble_average(ensemble)
    return (von_neumann_entropy(avg)
            - sum(p * von_neumann_entropy(rho) for p, rho in ensemble))


def chi_a_closed_form():
    """TRUE closed form for ensemble (a): the average state
    [[3/4, 1/4], [1/4, 1/4]] has spectrum (1 +/- 1/sqrt(2))/2, so
    chi = h2((1 - 1/sqrt(2))/2). (The build brief's 1 - h2(...) is
    the Helstrom accessible information, graded in section 5.)"""
    return binary_entropy((1.0 - 1.0 / math.sqrt(2.0)) / 2.0)


def holevo_report():
    rows = {}
    for name, ens in ENSEMBLES.items():
        avg = ensemble_average(ens)
        rows[name] = {
            "n_states": len(ens),
            "avg_eigenvalues": [round(v, 6)
                                for v in hermitian_eigenvalues(avg)],
            "S_average": round(von_neumann_entropy(avg), 6),
            "avg_individual_S": round(
                sum(p * von_neumann_entropy(r) for p, r in ens), 6),
            "chi": round(holevo_chi(ens), 6),
        }
    rows["a_chi_closed_form_h2"] = round(chi_a_closed_form(), 6)
    rows["a_brief_formula_1_minus_h2"] = round(1.0 - chi_a_closed_form(), 6)
    rows["a_brief_formula_is"] = (
        "the Helstrom-measurement accessible information, not chi")
    return rows


# ================================================================ 5. Accessible information
# ONE stated projective measurement per ensemble. For ensemble (a)
# the stated measurement is the Helstrom basis - used as a given
# measurement; the discrimination limit itself is NOT re-derived
# here (QuantumDiscrimination-Lab owns that). The check is the
# Holevo inequality I_acc <= chi with both numbers computed.

def helstrom_basis_a():
    """Stated measurement for ensemble (a): projectors onto the real
    unit vectors at angles -pi/8 and 3pi/8."""
    m0 = ket([math.cos(-math.pi / 8.0), math.sin(-math.pi / 8.0)])
    m1 = ket([math.cos(3.0 * math.pi / 8.0), math.sin(3.0 * math.pi / 8.0)])
    return [projector(m0), projector(m1)]


def z_basis():
    return [RHO_0, RHO_1]


def measurement_joint_probs(ensemble, projectors):
    """P(x, y) = p_x Tr[Pi_y rho_x] for a projective measurement."""
    joint = []
    for p, rho in ensemble:
        row = []
        for pi in projectors:
            row.append(p * mtrace(mmul(pi, rho)).real)
        joint.append(row)
    return joint


def mutual_info_from_joint(joint):
    nx = len(joint)
    ny = len(joint[0])
    px = [sum(joint[x][y] for y in range(ny)) for x in range(nx)]
    py = [sum(joint[x][y] for x in range(nx)) for y in range(ny)]
    mi = 0.0
    for x in range(nx):
        for y in range(ny):
            pxy = joint[x][y]
            if pxy > 1e-15:
                mi += pxy * math.log2(pxy / (px[x] * py[y]))
    return mi


def accessible_report():
    ens_a = ENSEMBLES["a_two_nonorthogonal"]
    joint_h = measurement_joint_probs(ens_a, helstrom_basis_a())
    i_hel = mutual_info_from_joint(joint_h)
    p_err = joint_h[0][1] + joint_h[1][0]  # P(y != x), priors included
    i_z_a = mutual_info_from_joint(
        measurement_joint_probs(ens_a, z_basis()))
    rows = {
        "ensemble_a_chi": round(holevo_chi(ens_a), 6),
        "ensemble_a_I_helstrom_basis": round(i_hel, 6),
        "ensemble_a_helstrom_error_prob": round(p_err, 6),
        "helstrom_error_closed_form": round(
            (1.0 - 1.0 / math.sqrt(2.0)) / 2.0, 6),
        "I_helstrom_closed_form_1_minus_h2": round(
            1.0 - binary_entropy((1.0 - 1.0 / math.sqrt(2.0)) / 2.0), 6),
        "ensemble_a_I_z_basis": round(i_z_a, 6),
        "holevo_inequality_holds": bool(i_hel <= holevo_chi(ens_a) + 1e-12),
    }
    for name in ("bb84_four_state", "trine"):
        ens = ENSEMBLES[name]
        i_z = mutual_info_from_joint(
            measurement_joint_probs(ens, z_basis()))
        rows[f"{name}_chi"] = round(holevo_chi(ens), 6)
        rows[f"{name}_I_z_basis"] = round(i_z, 6)
        rows[f"{name}_gap_chi_minus_Iz"] = round(holevo_chi(ens) - i_z, 6)
    return rows


# ================================================================ 6. Schumacher counting
# Source: qubit with eigenvalues (0.8, 0.2), S = h2(0.2). A length-n
# sequence with k minority symbols has probability 0.8^(n-k) 0.2^k
# and multiplicity C(n, k). The frequency-typical set keeps the k
# with |k/n - 0.2| <= 0.1; its dimension is an explicit binomial
# sum. No codec is built - this is counting, stated as counting.

def schumacher_entropy():
    return binary_entropy(SOURCE_P)


def typical_ks(n, delta=TYPICAL_DELTA):
    return [k for k in range(n + 1)
            if abs(k / n - SOURCE_P) <= delta + 1e-12]


def typical_dim(n, delta=TYPICAL_DELTA):
    return sum(math.comb(n, k) for k in typical_ks(n, delta))


def typical_mass(n, delta=TYPICAL_DELTA):
    return sum(math.comb(n, k) * (1.0 - SOURCE_P) ** (n - k)
               * SOURCE_P ** k for k in typical_ks(n, delta))


def min_dim_for_mass(n, target):
    """Smallest number of length-n sequences whose total probability
    reaches `target`, taking highest-probability sequences first
    (smallest k first, since the minority symbol is rarer). This is
    the counting lower bound any faithful subspace must respect."""
    remaining = target
    dim = 0
    for k in range(n + 1):
        per_seq = (1.0 - SOURCE_P) ** (n - k) * SOURCE_P ** k
        count = math.comb(n, k)
        group_mass = per_seq * count
        if group_mass >= remaining:
            dim += math.ceil(remaining / per_seq - 1e-9)
            return dim
        remaining -= group_mass
        dim += count
    return dim


def schumacher_report():
    rows = {"source_eigenvalues": [0.8, 0.2],
            "S_source": round(schumacher_entropy(), 6),
            "typical_delta": TYPICAL_DELTA}
    for n in SCHUMACHER_NS:
        dim = typical_dim(n)
        rows[f"n{n}"] = {
            "typical_ks": typical_ks(n),
            "typical_dim": dim,
            "rate_log2dim_over_n": round(math.log2(dim) / n, 6),
            "typical_mass": round(typical_mass(n), 6),
        }
    d_min = min_dim_for_mass(12, 0.9)
    rows["n12_min_dim_for_mass_0.9"] = d_min
    rows["n12_min_dim_rate"] = round(math.log2(d_min) / 12.0, 6)
    rows["counting_note"] = (
        "at n = 12 any set of sequences carrying probability 0.9 "
        "needs at least the stated dimension; its rate sits ABOVE S "
        "while the frequency-typical rate sits BELOW S - the two "
        "counts bracket S at finite n, which is all a counting "
        "argument claims")
    return rows


# ================================================================ 7. Inequalities + data processing
def mutual_information(rho_ab):
    """I(A:B) = S(A) + S(B) - S(AB) for a two-qubit state."""
    s_a = von_neumann_entropy(reduced(rho_ab, [2, 2], [0]))
    s_b = von_neumann_entropy(reduced(rho_ab, [2, 2], [1]))
    return s_a + s_b - von_neumann_entropy(rho_ab)


def kraus_depolarizing_single(p):
    """Single-qubit depolarizing Kraus list, E(rho) = (1-p) rho +
    p I/2 convention - the ONE channel used in this lab, for the
    data-processing check only (QuantumChannel-Lab owns channels)."""
    return [mscale(PAULI_I, math.sqrt(1.0 - 0.75 * p)),
            mscale(PAULI_X, math.sqrt(p / 4.0)),
            mscale(PAULI_Y, math.sqrt(p / 4.0)),
            mscale(PAULI_Z, math.sqrt(p / 4.0))]


def apply_local_depolarizing_b(rho_ab, p):
    """Apply the depolarizing map to qubit B only: sum_k (I x K_k)
    rho (I x K_k)^dagger."""
    out = zeros(4)
    for K in kraus_depolarizing_single(p):
        full = kron(PAULI_I, K)
        out = madd(out, mmul(full, mmul(rho_ab, dagger(full))))
    return out


def seeded_states():
    """Deterministically constructed states for the inequalities."""
    rho_ab = random_density_matrix(4, 112358)
    rho_abc = random_density_matrix(8, 314159)
    return rho_ab, rho_abc


def inequalities_report():
    rho_ab, rho_abc = seeded_states()
    s_ab = von_neumann_entropy(RHO_DP)
    s_a = von_neumann_entropy(reduced(RHO_DP, [2, 2], [0]))
    s_b = von_neumann_entropy(reduced(RHO_DP, [2, 2], [1]))
    # Strong subadditivity on the classically correlated GHZ mixture.
    mix = RHO_GHZ_MIX
    s_abc_m = von_neumann_entropy(mix)
    s_b_m = von_neumann_entropy(reduced(mix, [2, 2, 2], [1]))
    s_ab_m = von_neumann_entropy(reduced(mix, [2, 2, 2], [0, 1]))
    s_bc_m = von_neumann_entropy(reduced(mix, [2, 2, 2], [1, 2]))
    # Strong subadditivity on the seeded random tripartite state.
    s_abc_r = von_neumann_entropy(rho_abc)
    s_b_r = von_neumann_entropy(reduced(rho_abc, [2, 2, 2], [1]))
    s_ab_r = von_neumann_entropy(reduced(rho_abc, [2, 2, 2], [0, 1]))
    s_bc_r = von_neumann_entropy(reduced(rho_abc, [2, 2, 2], [1, 2]))
    i_before = mutual_information(RHO_DP)
    rho_after = apply_local_depolarizing_b(RHO_DP, 0.5)
    i_after = mutual_information(rho_after)
    rows = {
        "stated_state_S_AB": round(s_ab, 6),
        "stated_state_S_A_plus_S_B": round(s_a + s_b, 6),
        "subadditivity_gap": round(s_a + s_b - s_ab, 6),
        "araki_lieb_lhs_abs_diff": round(abs(s_a - s_b), 6),
        "ghz_S_ABC": round(von_neumann_entropy(RHO_GHZ), 6),
        "ghz_S_AB": round(
            von_neumann_entropy(reduced(RHO_GHZ, [2, 2, 2], [0, 1])), 6),
        "ghz_S_C": round(
            von_neumann_entropy(reduced(RHO_GHZ, [2, 2, 2], [2])), 6),
        "ssa_mixture_lhs_S_ABC_plus_S_B": round(s_abc_m + s_b_m, 6),
        "ssa_mixture_rhs_S_AB_plus_S_BC": round(s_ab_m + s_bc_m, 6),
        "ssa_random_lhs_S_ABC_plus_S_B": round(s_abc_r + s_b_r, 6),
        "ssa_random_rhs_S_AB_plus_S_BC": round(s_ab_r + s_bc_r, 6),
        "dataproc_I_before": round(i_before, 6),
        "dataproc_I_after_depolarizing_B_p0.5": round(i_after, 6),
        "dataproc_I_after_full_depolarizing": round(
            mutual_information(apply_local_depolarizing_b(RHO_DP, 1.0)), 6),
    }
    return rows


# ================================================================ 8. kNN classifier
# Features of a state/ensemble scenario: (S, purity, gap) where S is
# the von Neumann entropy of the state (or of the ensemble average),
# purity is Tr rho^2 of the same state, and gap is the
# information gap the scenario carries: S(A) - S(AB) for a bipartite
# state (the entanglement signature when the joint state is pure),
# chi - I_stated for an ensemble (information present in principle
# but not extracted by the stated measurement), 0 for a lone state.
# Labels come from the lab's own policy (model_label below).

def scenario_features(name):
    if name == "pure_product":
        return (von_neumann_entropy(RHO_0), purity(RHO_0), 0.0)
    if name == "pure_superposition":
        return (von_neumann_entropy(RHO_PLUS), purity(RHO_PLUS), 0.0)
    if name == "classical_maximally_mixed":
        return (von_neumann_entropy(RHO_MAXMIX_QUBIT),
                purity(RHO_MAXMIX_QUBIT), 0.0)
    if name == "classical_8020":
        return (von_neumann_entropy(RHO_CLASSICAL_8020),
                purity(RHO_CLASSICAL_8020), 0.0)
    if name == "bell_pair":
        gap = (von_neumann_entropy(reduced(RHO_BELL, [2, 2], [0]))
               - von_neumann_entropy(RHO_BELL))
        return (von_neumann_entropy(RHO_BELL), purity(RHO_BELL), gap)
    rep = accessible_report()
    if name == "ensemble_a":
        avg = ensemble_average(ENSEMBLES["a_two_nonorthogonal"])
        gap = holevo_chi(ENSEMBLES["a_two_nonorthogonal"]) \
            - rep["ensemble_a_I_helstrom_basis"]
        return (von_neumann_entropy(avg), purity(avg), gap)
    if name == "bb84_ensemble":
        avg = ensemble_average(ENSEMBLES["bb84_four_state"])
        gap = rep["bb84_four_state_gap_chi_minus_Iz"]
        return (von_neumann_entropy(avg), purity(avg), gap)
    if name == "trine_ensemble":
        avg = ensemble_average(ENSEMBLES["trine"])
        gap = rep["trine_gap_chi_minus_Iz"]
        return (von_neumann_entropy(avg), purity(avg), gap)
    raise KeyError(name)


CLASSIFIER_SCENARIOS = ("pure_product", "pure_superposition",
                        "classical_maximally_mixed", "classical_8020",
                        "bell_pair", "ensemble_a", "bb84_ensemble",
                        "trine_ensemble")


def model_label(S, pur, gap):
    """The verdict policy distilled to four labels."""
    if S <= 0.05 and pur >= 0.95:
        return "entangled-signature" if gap >= 0.5 else "pure"
    if gap >= 0.1:
        return "ensemble-informative"
    if S > 0.05:
        return "mixed-classical"
    return "pure"


def _training_grid():
    rows = []
    for S in (0.0, 0.3, 0.6, 0.72, 1.0, 1.585):
        for pur in (0.34, 0.5, 0.68, 0.75, 1.0):
            for gap in (0.0, 0.2, 0.54, 1.0):
                feats = (S, pur, gap)
                rows.append((feats, model_label(*feats)))
    return rows


TRAINING_GRID = _training_grid()


def classify_features(features, k=5):
    """Distance-weighted kNN over the policy-labelled grid."""
    ranked = []
    for feats, label in TRAINING_GRID:
        dist = math.sqrt(sum((a - b) ** 2
                             for a, b in zip(features, feats)))
        ranked.append((dist, feats, label))
    ranked.sort(key=lambda row: (row[0], row[1]))
    votes = {}
    for dist, _, label in ranked[:k]:
        votes[label] = votes.get(label, 0.0) + 1.0 / (dist + 1e-9)
    priority = {"pure": 0, "mixed-classical": 1,
                "ensemble-informative": 2, "entangled-signature": 3}
    return sorted(votes.items(), key=lambda kv: (-kv[1], priority[kv[0]]))[0][0]


def classifier_report():
    rows = {}
    for name in CLASSIFIER_SCENARIOS:
        feats = scenario_features(name)
        rows[name] = {
            "features_S_purity_gap": [round(v, 6) for v in feats],
            "policy": model_label(*feats),
            "knn": classify_features(feats),
        }
    return rows


# ================================================================ 9. Advisory seats
def _trace(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def argon4_decide(topic="quantuminformation-demo"):
    """Gemini Argon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-argon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Argon 4 Extended Thinking",
        "model_id": "gemini-argon-4",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all deployment gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _trace(payload),
    }


def claude_advisor(topic="quantuminformation-demo"):
    """Muse advisor seat: advises, can never override a HOLD."""
    return {
        "seat": "Muse",
        "role": "ADVISOR",
        "key": "names-only (MODEL_API_KEY name checked, value never read)",
        "live_calls": 0,
        "advice": "Print the grading before the number: chi for the {|0>, |+>} ensemble is h2((1 - 1/sqrt(2))/2) = 0.600876 from the average state's spectrum, the expression 1 - h2(...) = 0.399124 is the Helstrom measurement's accessible information on the same ensemble, and the Schumacher rates at n = 4, 8, 12 are finite-n counts that bracket S - then show the spectra and binomial sums that were actually computed.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["an eigenvalue spectrum flattening as entropy climbs to log2 of the dimension",
                  "two non-orthogonal state arrows with the Holevo chi arc between average-state entropy and accessible information",
                  "typical sequences lighting up inside a binomial histogram as the block length grows",
                  "a tripartite GHZ ledger where S(AB) and S(C) balance to the last digit",
                  "a bipartite ledger losing mutual information as one side is depolarized"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": argon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    # 0. Jacobi eigensolver refereed on known spectra first
    chk("jacobi_pauli_y_spectrum",
        all(abs(a - b) < 1e-12 for a, b in
            zip(hermitian_eigenvalues(PAULI_Y), (-1.0, 1.0))))
    chk("jacobi_complex_hermitian_2x2",
        all(abs(a - b) < 1e-12 for a, b in
            zip(hermitian_eigenvalues(mat([[2, 1j], [-1j, 3]])),
                ((5 - math.sqrt(5)) / 2, (5 + math.sqrt(5)) / 2))))
    xx_zz = madd(kron(PAULI_X, PAULI_X), kron(PAULI_Z, PAULI_Z))
    chk("jacobi_xx_plus_zz_spectrum",
        all(abs(a - b) < 1e-12 for a, b in
            zip(hermitian_eigenvalues(xx_zz), (-2.0, 0.0, 0.0, 2.0))))

    # 1. von Neumann entropy: exact anchors
    chk("entropy_pure_states_zero",
        abs(von_neumann_entropy(RHO_0)) < 1e-12
        and abs(von_neumann_entropy(RHO_PLUS)) < 1e-12
        and abs(von_neumann_entropy(RHO_BELL)) < 1e-12)
    chk("entropy_maximally_mixed_qubit_one",
        abs(von_neumann_entropy(RHO_MAXMIX_QUBIT) - 1.0) < 1e-12)
    chk("entropy_maximally_mixed_qutrit_log2_3",
        abs(von_neumann_entropy(RHO_MAXMIX_QUTRIT) - math.log2(3.0)) < 1e-12)
    chk("entropy_bell_reduced_one_bit",
        abs(von_neumann_entropy(reduced(RHO_BELL, [2, 2], [0])) - 1.0)
        < 1e-12
        and abs(von_neumann_entropy(reduced(RHO_BELL, [2, 2], [1])) - 1.0)
        < 1e-12)
    chk("entropy_classical_mixture_equals_shannon_8020",
        abs(von_neumann_entropy(RHO_CLASSICAL_8020)
            - shannon_entropy([0.8, 0.2])) < 1e-12)
    chk("entropy_classical_mixture_equals_shannon_3outcome",
        abs(von_neumann_entropy(RHO_CLASSICAL_3)
            - shannon_entropy([0.5, 0.3, 0.2])) < 1e-12)
    chk("entropy_unitary_invariance_seeded",
        abs(von_neumann_entropy(mmul(
            random_unitary(2, 777),
            mmul(RHO_CLASSICAL_8020, dagger(random_unitary(2, 777)))))
            - von_neumann_entropy(RHO_CLASSICAL_8020)) < 1e-9)
    rho_rand, _ = seeded_states()
    chk("entropy_bounds_random_states",
        all(-1e-12 <= von_neumann_entropy(r) <= math.log2(len(r)) + 1e-12
            for r in (random_density_matrix(2, 5),
                      random_density_matrix(3, 6), rho_rand)))
    chk("entropy_partial_trace_bell_is_maxmixed",
        mat_max_dev(reduced(RHO_BELL, [2, 2], [0]),
                    RHO_MAXMIX_QUBIT) < 1e-12)

    # 2. Renyi entropies: ordering + closed forms
    renyi_states = (RHO_0, RHO_MAXMIX_QUBIT, RHO_CLASSICAL_8020,
                    RHO_BELL, random_density_matrix(2, 20261118))
    chk("renyi_S2_le_S1_on_stated_states",
        all(renyi_entropy(r, 2.0) <= von_neumann_entropy(r) + 1e-12
            for r in renyi_states))
    chk("renyi_ordering_Sinf_le_S2_le_S1",
        all(renyi_entropy(r, math.inf) <= renyi_entropy(r, 2.0) + 1e-12
            for r in renyi_states))
    chk("renyi_pure_all_zero",
        abs(renyi_entropy(RHO_0, 2.0)) < 1e-12
        and abs(renyi_entropy(RHO_0, math.inf)) < 1e-12)
    chk("renyi_maxmixed_qubit_all_one",
        abs(renyi_entropy(RHO_MAXMIX_QUBIT, 2.0) - 1.0) < 1e-12
        and abs(renyi_entropy(RHO_MAXMIX_QUBIT, math.inf) - 1.0) < 1e-12)
    chk("min_entropy_classical_8020_closed_form",
        abs(renyi_entropy(RHO_CLASSICAL_8020, math.inf)
            + math.log2(0.8)) < 1e-12)
    chk("renyi_S2_is_minus_log2_purity",
        all(abs(renyi_entropy(r, 2.0) + math.log2(purity(r))) < 1e-9
            for r in renyi_states))

    # 3. Holevo chi from the definition, graded on closed forms
    chi_a = holevo_chi(ENSEMBLES["a_two_nonorthogonal"])
    chk("holevo_a_average_spectrum_closed_form",
        all(abs(a - b) < 1e-12 for a, b in
            zip(hermitian_eigenvalues(
                ensemble_average(ENSEMBLES["a_two_nonorthogonal"])),
                ((1.0 - 1.0 / math.sqrt(2.0)) / 2.0,
                 (1.0 + 1.0 / math.sqrt(2.0)) / 2.0))))
    chk("holevo_a_chi_equals_h2_closed_form",
        abs(chi_a - chi_a_closed_form()) < 1e-12)
    chk("holevo_a_chi_value_0.600876",
        abs(chi_a - 0.600876) < 1e-6)
    chk("holevo_bb84_chi_one_bit",
        abs(holevo_chi(ENSEMBLES["bb84_four_state"]) - 1.0) < 1e-12)
    chk("holevo_trine_average_is_maxmixed",
        mat_max_dev(ensemble_average(ENSEMBLES["trine"]),
                    RHO_MAXMIX_QUBIT) < 1e-12)
    chk("holevo_trine_chi_one_bit",
        abs(holevo_chi(ENSEMBLES["trine"]) - 1.0) < 1e-12)
    chk("holevo_chi_nonnegative_and_bounded",
        all(0.0 - 1e-12 <= holevo_chi(e) <= 1.0 + 1e-12
            for e in ENSEMBLES.values()))
    chk("holevo_brief_formula_is_not_chi",
        abs((1.0 - chi_a_closed_form()) - chi_a) > 0.1)

    # 4. Accessible information: stated measurements, Holevo bound
    acc = accessible_report()
    joint_h_raw = measurement_joint_probs(
        ENSEMBLES["a_two_nonorthogonal"], helstrom_basis_a())
    p_err_raw = joint_h_raw[0][1] + joint_h_raw[1][0]
    i_hel_raw = mutual_info_from_joint(joint_h_raw)
    chk("accessible_helstrom_error_closed_form",
        abs(p_err_raw - (1.0 - 1.0 / math.sqrt(2.0)) / 2.0) < 1e-12)
    chk("accessible_helstrom_I_equals_1_minus_h2_error",
        abs(i_hel_raw
            - (1.0 - binary_entropy(
                (1.0 - 1.0 / math.sqrt(2.0)) / 2.0))) < 1e-12)
    chk("accessible_helstrom_I_value_0.399124",
        abs(acc["ensemble_a_I_helstrom_basis"] - 0.399124) < 1e-6)
    chk("accessible_holevo_inequality_I_le_chi",
        acc["ensemble_a_I_helstrom_basis"] <= chi_a + 1e-12
        and acc["ensemble_a_I_z_basis"] <= chi_a + 1e-12)
    chk("accessible_z_basis_below_helstrom",
        acc["ensemble_a_I_z_basis"]
        < acc["ensemble_a_I_helstrom_basis"])
    chk("accessible_bb84_trine_gaps_positive",
        acc["bb84_four_state_gap_chi_minus_Iz"] > 0.1
        and acc["trine_gap_chi_minus_Iz"] > 0.1)

    # 5. Schumacher compression: explicit binomial counting
    S_src = schumacher_entropy()
    chk("schumacher_source_entropy_h2_0.2",
        abs(S_src - binary_entropy(0.2)) < 1e-12
        and abs(S_src - 0.721928) < 1e-6)
    chk("schumacher_typical_dims_exact",
        typical_dim(4) == 4 and typical_dim(8) == 36
        and typical_dim(12) == 286)
    rates = [math.log2(typical_dim(n)) / n for n in SCHUMACHER_NS]
    chk("schumacher_rates_below_S_and_rising",
        all(r < S_src for r in rates)
        and rates[0] < rates[1] < rates[2])
    chk("schumacher_rate_n12_within_0.05_of_S",
        abs(rates[2] - S_src) < 0.05)
    d_min = min_dim_for_mass(12, 0.9)
    chk("schumacher_min_dim_for_mass_0.9_exact",
        d_min == 692)
    chk("schumacher_counting_brackets_S",
        rates[2] < S_src < math.log2(d_min) / 12.0)
    chk("schumacher_typical_mass_finite_n_honest",
        0.4 < typical_mass(12) < 0.65 and typical_mass(12) < 0.9)

    # 6. Entropy inequalities on constructed states
    s_ab = von_neumann_entropy(RHO_DP)
    s_a = von_neumann_entropy(reduced(RHO_DP, [2, 2], [0]))
    s_b = von_neumann_entropy(reduced(RHO_DP, [2, 2], [1]))
    chk("subadditivity_stated_state",
        s_ab <= s_a + s_b + 1e-12)
    chk("subadditivity_seeded_random_state",
        von_neumann_entropy(rho_rand)
        <= von_neumann_entropy(reduced(rho_rand, [2, 2], [0]))
        + von_neumann_entropy(reduced(rho_rand, [2, 2], [1])) + 1e-12)
    chk("araki_lieb_stated_state",
        abs(s_a - s_b) <= s_ab + 1e-12)
    chk("araki_lieb_seeded_random_state",
        abs(von_neumann_entropy(reduced(rho_rand, [2, 2], [0]))
            - von_neumann_entropy(reduced(rho_rand, [2, 2], [1])))
        <= von_neumann_entropy(rho_rand) + 1e-12)
    chk("ghz_pure_tripartite_S_ABC_zero",
        abs(von_neumann_entropy(RHO_GHZ)) < 1e-12)
    chk("ghz_identity_S_AB_equals_S_C",
        abs(von_neumann_entropy(reduced(RHO_GHZ, [2, 2, 2], [0, 1]))
            - von_neumann_entropy(reduced(RHO_GHZ, [2, 2, 2], [2])))
        < 1e-12)
    chk("ghz_identity_S_A_equals_S_BC",
        abs(von_neumann_entropy(reduced(RHO_GHZ, [2, 2, 2], [0]))
            - von_neumann_entropy(reduced(RHO_GHZ, [2, 2, 2], [1, 2])))
        < 1e-12)
    chk("ghz_reduced_entropies_one_bit",
        abs(von_neumann_entropy(reduced(RHO_GHZ, [2, 2, 2], [0, 1]))
            - 1.0) < 1e-12)
    ineq = inequalities_report()
    chk("strong_subadditivity_ghz_mixture",
        ineq["ssa_mixture_lhs_S_ABC_plus_S_B"]
        <= ineq["ssa_mixture_rhs_S_AB_plus_S_BC"] + 1e-12)
    chk("strong_subadditivity_seeded_random",
        ineq["ssa_random_lhs_S_ABC_plus_S_B"]
        <= ineq["ssa_random_rhs_S_AB_plus_S_BC"] + 1e-12)
    chk("mutual_information_nonnegative",
        mutual_information(RHO_DP) >= -1e-12
        and mutual_information(rho_rand) >= -1e-12)

    # 7. Data processing: local depolarizing cannot raise I(A:B)
    chk("dataproc_depolarizing_reduces_mutual_info",
        ineq["dataproc_I_after_depolarizing_B_p0.5"]
        < ineq["dataproc_I_before"])
    chk("dataproc_full_depolarizing_zeroes_mutual_info",
        abs(ineq["dataproc_I_after_full_depolarizing"]) < 1e-9)
    chk("dataproc_local_map_preserves_reduced_A",
        mat_max_dev(reduced(apply_local_depolarizing_b(RHO_DP, 0.5),
                            [2, 2], [0]),
                    reduced(RHO_DP, [2, 2], [0])) < 1e-12)

    # 8. Classifier: labels come from the lab's own policy
    rep = classifier_report()
    chk("classifier_scenario_labels",
        rep["pure_product"]["knn"] == "pure"
        and rep["pure_superposition"]["knn"] == "pure"
        and rep["classical_maximally_mixed"]["knn"] == "mixed-classical"
        and rep["classical_8020"]["knn"] == "mixed-classical"
        and rep["bell_pair"]["knn"] == "entangled-signature"
        and rep["ensemble_a"]["knn"] == "ensemble-informative"
        and rep["bb84_ensemble"]["knn"] == "ensemble-informative"
        and rep["trine_ensemble"]["knn"] == "ensemble-informative")
    chk("classifier_knn_matches_policy_scenarios",
        all(row["knn"] == row["policy"] for row in rep.values()))
    chk("classifier_knn_matches_policy_grid",
        all(classify_features(feats) == label
            for feats, label in TRAINING_GRID))

    # gates + seats
    chk("hold_gates_14", len(HOLD_GATES) == 14
        and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_capacity_or_codec_hold",
        gate("capacity_or_codec_claim") == "HOLD")
    chk("gate_model_as_measurement_hold",
        gate("model_as_measurement_claim") == "HOLD")
    chk("gate_live_hardware_hold", gate("live_hardware_control") == "HOLD")
    chk("gate_investment_hold", gate("investment_claim") == "HOLD")
    chk("gate_certification_hold", gate("certification_claim") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    brains = brains_report()
    chk("argon4_no_override", brains["decider"]["can_override_hold"] is False
        and brains["decider"]["seat"]
        == "Gemini Argon 4 Extended Thinking"
        and brains["decider"]["model_id"] == "gemini-argon-4")
    chk("claude_no_override", brains["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", brains["flow"]["rendered"] is False
        and brains["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("QuantumInformation-Lab - entropy, Holevo chi, Schumacher counting")
    print("by Darion Kellar | MIT | pure stdlib | zero network | EDUCATION ONLY")
    print("=" * 68)
    print("\n[1] THE HONEST CORE - small density matrices, exact identities")
    print("    Entropies from a refereed Jacobi spectrum, chi from its")
    print("    definition, Schumacher rates from explicit binomial sums.")
    print("    No codec is built and no capacity is claimed for anything.")
    print("    GRADING NOTE: the brief's chi formula 1 - h2((1-1/sqrt2)/2)")
    print("    = 0.399124 is NOT chi - it is the Helstrom accessible")
    print("    information. True chi = h2((1-1/sqrt2)/2) = 0.600876.")
    print("\n[2] von Neumann entropy - graded on exact anchors")
    ent = entropy_report()
    for name in ("pure_|0>", "maximally_mixed_qubit",
                 "maximally_mixed_qutrit", "classical_0.8_0.2",
                 "bell_joint_AB", "bell_reduced_A"):
        row = ent[name]
        print(f"    {name:26s} S {row['S_von_neumann']:.6f} | "
              f"purity {row['purity']:.6f} | eigs {row['eigenvalues']}")
    print(f"    classical mixture S == Shannon: h2(0.2) = "
          f"{ent['shannon_0.8_0.2']:.6f}; qutrit anchor log2(3) = "
          f"{ent['log2_3']:.6f}")
    print("\n[3] Renyi entropies - S_inf <= S2 <= S1 on every stated state")
    for name, row in renyi_report().items():
        if isinstance(row, dict):
            print(f"    {name:26s} S1 {row['S1_von_neumann']:.6f} | "
                  f"S2 {row['S2_collision']:.6f} | "
                  f"S_min {row['S_min']:.6f}")
    print(f"    min-entropy of diag(0.8, 0.2) = -log2(0.8) = "
          f"{-math.log2(0.8):.6f} (closed form, asserted)")
    print("\n[4] Holevo chi - computed from the definition")
    hol = holevo_report()
    for name in ("a_two_nonorthogonal", "bb84_four_state", "trine"):
        row = hol[name]
        print(f"    {name:22s} chi {row['chi']:.6f} | "
              f"S(avg) {row['S_average']:.6f} | avg eigs "
              f"{row['avg_eigenvalues']}")
    print(f"    ensemble (a) closed form: chi = h2((1-1/sqrt2)/2) = "
          f"{hol['a_chi_closed_form_h2']:.6f}")
    print(f"    brief formula 1 - h2(...) = "
          f"{hol['a_brief_formula_1_minus_h2']:.6f} -> "
          f"{hol['a_brief_formula_is']}")
    print("\n[5] Accessible information - one stated measurement each")
    acc = accessible_report()
    print(f"    ensemble (a), Helstrom basis: I_acc "
          f"{acc['ensemble_a_I_helstrom_basis']:.6f} <= chi "
          f"{acc['ensemble_a_chi']:.6f} | error prob "
          f"{acc['ensemble_a_helstrom_error_prob']:.6f} "
          f"= (1 - 1/sqrt2)/2")
    print(f"    ensemble (a), Z basis: I {acc['ensemble_a_I_z_basis']:.6f} "
          f"(below the Helstrom value, still <= chi)")
    print(f"    BB84: chi {acc['bb84_four_state_chi']:.6f}, Z-basis I "
          f"{acc['bb84_four_state_I_z_basis']:.6f}, gap "
          f"{acc['bb84_four_state_gap_chi_minus_Iz']:.6f}")
    print(f"    trine: chi {acc['trine_chi']:.6f}, Z-basis I "
          f"{acc['trine_I_z_basis']:.6f}, gap "
          f"{acc['trine_gap_chi_minus_Iz']:.6f}")
    print("\n[6] Schumacher compression - counting, not a codec")
    sch = schumacher_report()
    print(f"    source eigenvalues (0.8, 0.2), S = h2(0.2) = "
          f"{sch['S_source']:.6f} bits per copy")
    for n in SCHUMACHER_NS:
        row = sch[f"n{n}"]
        print(f"    n = {n:2d} | typical ks {row['typical_ks']} | "
              f"dim {row['typical_dim']:4d} | rate "
              f"{row['rate_log2dim_over_n']:.6f} | mass "
              f"{row['typical_mass']:.6f}")
    print(f"    rates rise toward S from below: 0.500000 -> 0.646241 "
          f"-> 0.679989 -> S = {sch['S_source']:.6f}")
    print(f"    counting bound at n = 12: mass 0.9 needs dim >= "
          f"{sch['n12_min_dim_for_mass_0.9']} (rate "
          f"{sch['n12_min_dim_rate']:.6f} > S) - finite-n counts "
          f"bracket S; no codec is claimed")
    print("\n[7] Entropy inequalities - on states built in this file")
    ineq = inequalities_report()
    print(f"    subadditivity: S(AB) {ineq['stated_state_S_AB']:.6f} <= "
          f"S(A)+S(B) {ineq['stated_state_S_A_plus_S_B']:.6f}")
    print(f"    Araki-Lieb: |S(A)-S(B)| "
          f"{ineq['araki_lieb_lhs_abs_diff']:.6f} <= S(AB) "
          f"{ineq['stated_state_S_AB']:.6f}")
    print(f"    GHZ pure tripartite: S(ABC) {ineq['ghz_S_ABC']:.6f} = 0, "
          f"S(AB) {ineq['ghz_S_AB']:.6f} = S(C) {ineq['ghz_S_C']:.6f} "
          f"(exact identities)")
    print(f"    strong subadditivity (GHZ mixture): LHS "
          f"{ineq['ssa_mixture_lhs_S_ABC_plus_S_B']:.6f} <= RHS "
          f"{ineq['ssa_mixture_rhs_S_AB_plus_S_BC']:.6f}")
    print(f"    strong subadditivity (seeded random): LHS "
          f"{ineq['ssa_random_lhs_S_ABC_plus_S_B']:.6f} <= RHS "
          f"{ineq['ssa_random_rhs_S_AB_plus_S_BC']:.6f}")
    print("\n[8] Data processing - one local depolarizing map on B")
    print(f"    I(A:B) before {ineq['dataproc_I_before']:.6f} -> after "
          f"p = 0.5 {ineq['dataproc_I_after_depolarizing_B_p0.5']:.6f} "
          f"-> after p = 1 {ineq['dataproc_I_after_full_depolarizing']:.6f}")
    print("    local noise never raises mutual information (asserted)")
    print("\n[9] State/ensemble classifier (TinyML kNN, lab policy labels)")
    for name, row in classifier_report().items():
        print(f"    {name:28s} -> {row['knn']}")
    print("\n[10] Advisory seats")
    brains = brains_report()
    print(f"    decider: {brains['decider']['decision']} "
          f"trace={brains['decider']['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {brains['advisor']['can_override_hold']}")
    print(f"    flow rendered = {brains['flow']['rendered']} "
          f"live = {brains['flow']['live']}")
    print(f"\n[11] HOLD gates: {len(HOLD_GATES)}")
    for key in HOLD_GATES:
        print(f"    HOLD  {key}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "entropy":
        print(json.dumps(entropy_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "renyi":
        print(json.dumps(renyi_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holevo":
        print(json.dumps(holevo_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "accessible":
        print(json.dumps(accessible_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "schumacher":
        print(json.dumps(schumacher_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "inequalities":
        print(json.dumps(inequalities_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(classifier_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for key, value in HOLD_GATES.items():
            print(f"{key}: {value}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "capacity_or_codec_claim"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
