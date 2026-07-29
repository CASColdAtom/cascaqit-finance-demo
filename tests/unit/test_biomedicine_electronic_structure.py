"""Biomedicine fixture and Pauli/VQE domain tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cascaqit_biomedicine_demo.catalog import BIOMEDICINE_SCENARIO_SPECS
from cascaqit_biomedicine_demo.electronic_structure import (
    analyze_electronic_structure,
    electronic_values,
    run_electronic_structure,
)
from cascaqit_biomedicine_demo.fixtures import (
    ELECTRONIC_DATASET_PATHS,
    load_electronic_fixture,
)
from cascaqit_biomedicine_demo.pauli_vqe import (
    build_pauli_hamiltonian,
    exact_diagonalization,
)


def test_catalog_declares_four_biomedicine_scenarios_and_truthful_status() -> None:
    assert tuple(BIOMEDICINE_SCENARIO_SPECS) == (
        "electronic_structure",
        "docking_match",
        "active_center",
        "peptide_landscape",
    )
    electronic = BIOMEDICINE_SCENARIO_SPECS["electronic_structure"]
    assert electronic.implementation_status == "available"
    assert {item[0] for item in electronic.presets} == {
        "h2_bond_scan",
        "lih_active_space",
        "h2o_minimal",
    }
    assert {
        item.implementation_status for item in BIOMEDICINE_SCENARIO_SPECS.values()
    } == {"available"}


@pytest.mark.parametrize("dataset", tuple(ELECTRONIC_DATASET_PATHS))
def test_electronic_fixtures_have_reproducible_provenance_and_reference(
    dataset: str,
) -> None:
    fixture = load_electronic_fixture(dataset)
    parameters = fixture.manifest["generation"]["parameters"]
    assert parameters["final_qubit_count"] == len(fixture.manifest["logical_order"])
    assert parameters["tapered_qubit_count"] == 2
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "generate_electronic_structure_fixtures.py"
    )
    assert hashlib.sha256(script.read_bytes()).hexdigest() == fixture.manifest[
        "generation"
    ]["script_sha256"]
    hamiltonian = build_pauli_hamiltonian(fixture.pauli)
    exact = exact_diagonalization(hamiltonian)["energy"]
    assert exact == pytest.approx(
        fixture.manifest["reference"]["exact_ground_energy_hartree"], abs=1e-10
    )
    assert fixture.manifest["source"]["license_checked_at"] == "2026-07-30"
    assert fixture.manifest["allowed_claims"]


def test_h2_scan_contains_three_consistent_reference_points() -> None:
    analysis = analyze_electronic_structure("h2_bond_scan", {})
    scan = analysis["domain"]["bondScanReference"]
    assert [item["bondLengthAngstrom"] for item in scan] == [0.5, 0.735, 1.5]
    assert sum(item["selected"] for item in scan) == 1
    assert min(scan, key=lambda item: item["exactGroundEnergy"])[
        "bondLengthAngstrom"
    ] == 0.735


@pytest.mark.parametrize(
    ("preset", "molecule", "qubits"),
    (
        ("h2_bond_scan", "H2", 2),
        ("lih_active_space", "LiH", 4),
        ("h2o_minimal", "H2O", 4),
    ),
)
def test_all_electronic_presets_analyze_real_pauli_hamiltonians(
    preset: str, molecule: str, qubits: int
) -> None:
    analysis = analyze_electronic_structure(preset, {})
    assert analysis["problem"]["type"] == "pauli_hamiltonian"
    assert analysis["resource"]["logicalQubits"] == qubits
    assert analysis["resource"]["termCount"] >= 4
    assert analysis["resource"]["measurementGroups"] >= 2
    assert analysis["decision"]["recommendedMode"] == "digital"
    assert analysis["domain"]["molecule"] == molecule
    assert len(analysis["problem"]["hash"]) == 64
    assert len(analysis["analysisHash"]) == 64


def test_electronic_values_reject_unknown_dataset_and_noise_model() -> None:
    with pytest.raises(ValueError, match="dataset"):
        electronic_values("h2_bond_scan", {"dataset": "arbitrary"})
    with pytest.raises(ValueError, match="noise_model"):
        electronic_values("h2o_minimal", {"noise_model": "hardware"})


@pytest.mark.parametrize(
    ("preset", "accuracy_claim"),
    (
        ("h2_bond_scan", "h2_equilibrium_benchmark"),
        ("lih_active_space", "error_report_only"),
        ("h2o_minimal", "error_report_only"),
    ),
)
def test_all_electronic_presets_execute_vqe_and_keep_accuracy_claim_scoped(
    preset: str, accuracy_claim: str
) -> None:
    run = run_electronic_structure(
        preset=preset,
        values={},
        shots=32,
        seed=7,
        layers=1,
        parameter_budget=40,
        optimizer_starts=2,
    )
    assert run["domain"]["absoluteErrorHartree"] < 0.002
    assert run["domain"]["accuracyClaim"] == accuracy_claim
    assert run["domain"]["withinChemicalAccuracy"] is (
        True if preset == "h2_bond_scan" else None
    )
    assert sum(run["quantum"]["counts"].values()) == 32
    assert run["audit"]["hardwareExecution"] is False
    assert run["audit"]["networkAccessed"] is False
    assert len(run["audit"]["backendHash"]) == 64
    assert len(run["audit"]["reportHash"]) == 64


def test_h2o_readout_noise_keeps_ideal_and_noisy_qwc_evidence_separate() -> None:
    run = run_electronic_structure(
        preset="h2o_minimal",
        values={"noise_model": "readout_demo"},
        shots=32,
        seed=7,
        layers=1,
        parameter_budget=40,
        optimizer_starts=2,
    )
    assert run["domain"]["noisySampledConfirmationEnergy"] is not None
    assert run["comparison"]["vqeNoisySampledEnergy"] is not None
    assert run["quantum"]["measurement"]["groups"]
    assert run["quantum"]["measurement"]["noisyGroups"]
    assert run["audit"]["noiseModelHash"]
    noisy_evidence = run["quantum"]["measurement"]["noisyGroups"][0][
        "executionEvidence"
    ]
    assert noisy_evidence["noise_report"]["truthfulness"] == (
        "measurement_model_only"
    )
