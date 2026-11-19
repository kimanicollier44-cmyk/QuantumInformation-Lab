"""Tests for QuantumInformation-Lab. Every test grades a computed
number against a closed form or an exact identity in main.py."""
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main as qi

TOL = 1e-9


def test_jacobi_known_spectra():
    assert all(abs(a - b) < 1e-12 for a, b in
               zip(qi.hermitian_eigenvalues(qi.PAULI_Y), (-1.0, 1.0)))
    xx_zz = qi.madd(qi.kron(qi.PAULI_X, qi.PAULI_X),
                    qi.kron(qi.PAULI_Z, qi.PAULI_Z))
    assert all(abs(a - b) < 1e-12 for a, b in
               zip(qi.hermitian_eigenvalues(xx_zz), (-2.0, 0.0, 0.0, 2.0)))


def test_entropy_pure_and_maxmixed():
    assert abs(qi.von_neumann_entropy(qi.RHO_0)) < 1e-12
    assert abs(qi.von_neumann_entropy(qi.RHO_PLUS)) < 1e-12
    assert abs(qi.von_neumann_entropy(qi.RHO_MAXMIX_QUBIT) - 1.0) < 1e-12
    assert abs(qi.von_neumann_entropy(qi.RHO_MAXMIX_QUTRIT)
               - math.log2(3.0)) < 1e-12


def test_entropy_bell_joint_and_reduced():
    assert abs(qi.von_neumann_entropy(qi.RHO_BELL)) < 1e-12
    red = qi.reduced(qi.RHO_BELL, [2, 2], [0])
    assert abs(qi.von_neumann_entropy(red) - 1.0) < 1e-12
    assert qi.mat_max_dev(red, qi.RHO_MAXMIX_QUBIT) < 1e-12


def test_entropy_classical_equals_shannon():
    assert abs(qi.von_neumann_entropy(qi.RHO_CLASSICAL_8020)
               - qi.shannon_entropy([0.8, 0.2])) < 1e-12
    assert abs(qi.von_neumann_entropy(qi.RHO_CLASSICAL_3)
               - qi.shannon_entropy([0.5, 0.3, 0.2])) < 1e-12


def test_entropy_unitary_invariance():
    U = qi.random_unitary(2, 777)
    rotated = qi.mmul(U, qi.mmul(qi.RHO_CLASSICAL_8020, qi.dagger(U)))
    assert abs(qi.von_neumann_entropy(rotated)
               - qi.von_neumann_entropy(qi.RHO_CLASSICAL_8020)) < 1e-9


def test_renyi_ordering_and_closed_forms():
    for rho in (qi.RHO_0, qi.RHO_MAXMIX_QUBIT, qi.RHO_CLASSICAL_8020,
                qi.RHO_BELL):
        assert qi.renyi_entropy(rho, math.inf) \
            <= qi.renyi_entropy(rho, 2.0) + 1e-12
        assert qi.renyi_entropy(rho, 2.0) \
            <= qi.von_neumann_entropy(rho) + 1e-12
        assert abs(qi.renyi_entropy(rho, 2.0)
                   + math.log2(qi.purity(rho))) < 1e-9
    assert abs(qi.renyi_entropy(qi.RHO_CLASSICAL_8020, math.inf)
               + math.log2(0.8)) < 1e-12


def test_holevo_a_true_closed_form():
    chi = qi.holevo_chi(qi.ENSEMBLES["a_two_nonorthogonal"])
    expect = qi.binary_entropy((1.0 - 1.0 / math.sqrt(2.0)) / 2.0)
    assert abs(chi - expect) < 1e-12
    assert abs(chi - 0.600876) < 1e-6
    # The brief's 1 - h2(...) is NOT chi; it is the Helstrom I_acc.
    assert abs((1.0 - expect) - chi) > 0.1


def test_holevo_bb84_and_trine_one_bit():
    assert abs(qi.holevo_chi(qi.ENSEMBLES["bb84_four_state"]) - 1.0) < 1e-12
    assert qi.mat_max_dev(
        qi.ensemble_average(qi.ENSEMBLES["trine"]),
        qi.RHO_MAXMIX_QUBIT) < 1e-12
    assert abs(qi.holevo_chi(qi.ENSEMBLES["trine"]) - 1.0) < 1e-12


def test_accessible_helstrom_and_holevo_bound():
    rep = qi.accessible_report()
    chi = qi.holevo_chi(qi.ENSEMBLES["a_two_nonorthogonal"])
    assert abs(rep["ensemble_a_I_helstrom_basis"] - 0.399124) < 1e-6
    assert rep["ensemble_a_I_helstrom_basis"] <= chi + 1e-12
    assert rep["ensemble_a_I_z_basis"] < rep["ensemble_a_I_helstrom_basis"]
    joint = qi.measurement_joint_probs(
        qi.ENSEMBLES["a_two_nonorthogonal"], qi.helstrom_basis_a())
    p_err = joint[0][1] + joint[1][0]
    assert abs(p_err - (1.0 - 1.0 / math.sqrt(2.0)) / 2.0) < 1e-12
    assert abs(qi.mutual_info_from_joint(joint)
               - (1.0 - qi.binary_entropy(p_err))) < 1e-12


def test_schumacher_counting():
    S = qi.schumacher_entropy()
    assert abs(S - qi.binary_entropy(0.2)) < 1e-12
    assert qi.typical_dim(4) == 4
    assert qi.typical_dim(8) == 36
    assert qi.typical_dim(12) == 286
    rates = [math.log2(qi.typical_dim(n)) / n for n in (4, 8, 12)]
    assert rates[0] < rates[1] < rates[2] < S
    assert abs(rates[2] - S) < 0.05
    assert qi.min_dim_for_mass(12, 0.9) == 692
    assert math.log2(692) / 12 > S


def test_ghz_exact_identities():
    dims = [2, 2, 2]
    assert abs(qi.von_neumann_entropy(qi.RHO_GHZ)) < 1e-12
    s_ab = qi.von_neumann_entropy(qi.reduced(qi.RHO_GHZ, dims, [0, 1]))
    s_c = qi.von_neumann_entropy(qi.reduced(qi.RHO_GHZ, dims, [2]))
    assert abs(s_ab - s_c) < 1e-12 and abs(s_ab - 1.0) < 1e-12
    s_a = qi.von_neumann_entropy(qi.reduced(qi.RHO_GHZ, dims, [0]))
    s_bc = qi.von_neumann_entropy(qi.reduced(qi.RHO_GHZ, dims, [1, 2]))
    assert abs(s_a - s_bc) < 1e-12


def test_subadditivity_and_araki_lieb():
    for rho in (qi.RHO_DP, qi.random_density_matrix(4, 112358)):
        s_ab = qi.von_neumann_entropy(rho)
        s_a = qi.von_neumann_entropy(qi.reduced(rho, [2, 2], [0]))
        s_b = qi.von_neumann_entropy(qi.reduced(rho, [2, 2], [1]))
        assert s_ab <= s_a + s_b + 1e-12
        assert abs(s_a - s_b) <= s_ab + 1e-12


def test_strong_subadditivity():
    rep = qi.inequalities_report()
    assert rep["ssa_mixture_lhs_S_ABC_plus_S_B"] \
        <= rep["ssa_mixture_rhs_S_AB_plus_S_BC"] + 1e-12
    assert rep["ssa_random_lhs_S_ABC_plus_S_B"] \
        <= rep["ssa_random_rhs_S_AB_plus_S_BC"] + 1e-12


def test_data_processing():
    rep = qi.inequalities_report()
    assert rep["dataproc_I_after_depolarizing_B_p0.5"] \
        < rep["dataproc_I_before"]
    assert abs(rep["dataproc_I_after_full_depolarizing"]) < 1e-9
    after = qi.apply_local_depolarizing_b(qi.RHO_DP, 0.5)
    assert qi.mat_max_dev(qi.reduced(after, [2, 2], [0]),
                          qi.reduced(qi.RHO_DP, [2, 2], [0])) < 1e-12


def test_classifier_scenarios():
    rep = qi.classifier_report()
    assert rep["pure_product"]["knn"] == "pure"
    assert rep["pure_superposition"]["knn"] == "pure"
    assert rep["classical_maximally_mixed"]["knn"] == "mixed-classical"
    assert rep["classical_8020"]["knn"] == "mixed-classical"
    assert rep["bell_pair"]["knn"] == "entangled-signature"
    assert rep["ensemble_a"]["knn"] == "ensemble-informative"
    assert rep["bb84_ensemble"]["knn"] == "ensemble-informative"
    assert rep["trine_ensemble"]["knn"] == "ensemble-informative"
    assert all(row["knn"] == row["policy"] for row in rep.values())


def test_classifier_grid_consistency():
    for feats, label in qi.TRAINING_GRID:
        assert qi.classify_features(feats) == label


def test_hold_gates():
    assert len(qi.HOLD_GATES) == 14
    assert qi.gate("capacity_or_codec_claim") == "HOLD"
    assert qi.gate("model_as_measurement_claim") == "HOLD"
    assert qi.gate("live_hardware_control") == "HOLD"
    assert qi.gate("investment_claim") == "HOLD"
    assert qi.gate("certification_claim") == "HOLD"
    assert qi.gate("run_simulation") == "PROCEED"


def test_seats_never_override():
    brains = qi.brains_report()
    assert brains["decider"]["can_override_hold"] is False
    assert brains["decider"]["model_id"] == "gemini-argon-4"
    assert brains["advisor"]["can_override_hold"] is False
    assert brains["flow"]["rendered"] is False
    assert brains["flow"]["live"] == 0


def test_checks_all_pass():
    checks = qi.run_checks()
    assert all(ok for _, ok in checks), [n for n, ok in checks if not ok]
    assert len(checks) == 66


def test_cli_hold_demo_exit_2():
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent
                             / "main.py"), "hold-demo"],
        capture_output=True, text=True)
    assert proc.returncode == 2
    assert "HOLD" in proc.stdout


def test_cli_checks_command():
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent
                             / "main.py"), "checks"],
        capture_output=True, text=True)
    assert proc.returncode == 0
    assert "CHECKS 66/66" in proc.stdout


def test_demo_deterministic():
    main_py = str(Path(__file__).resolve().parent.parent / "main.py")
    a = subprocess.run([sys.executable, main_py, "demo"],
                       capture_output=True, text=True)
    b = subprocess.run([sys.executable, main_py, "demo"],
                       capture_output=True, text=True)
    assert a.stdout == b.stdout and a.returncode == 0
