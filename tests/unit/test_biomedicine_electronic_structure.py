"""Biomedicine fixture and Pauli/VQE domain tests."""

from __future__ import annotations

import numpy as np
import pytest

from cascaqit_biomedicine_demo.catalog import BIOMEDICINE_SCENARIO_SPECS
from cascaqit_biomedicine_demo.electronic_structure import (
    analyze_electronic_structure,
    run_electronic_structure,
)
from cascaqit_biomedicine_demo.fixtures import load_h2_fixture


def test_catalog_declares_four_biomedicine_scenarios_and_truthful_status() -> None:
    assert tuple(BIOMEDICINE_SCENARIO_SPECS) == (
        "electronic_structure",
        "docking_match",
        "active_center",
        "peptide_landscape",
    )
    assert (
        BIOMEDICINE_SCENARIO_SPECS["electronic_structure"].implementation_status
        == "available"
    )
    assert {
        item.implementation_status for item in BIOMEDICINE_SCENARIO_SPECS.values()
    } == {"available", "preview"}


def test_h2_fixture_checksums_and_reference_energy_match_pauli_matrix() -> None:
    fixture = load_h2_fixture()
    pauli = fixture.pauli
    identity = np.eye(2)
    x = np.array([[0.0, 1.0], [1.0, 0.0]])
    z = np.diag([1.0, -1.0])
    matrices = {"X": x, "Z": z}
    hamiltonian = float(pauli["constant"]) * np.eye(4)
    for term in pauli["terms"]:
        factors = {target: basis for target, basis in term["factors"]}
        operator = np.kron(
            matrices.get(factors.get("q0", ""), identity),
            matrices.get(factors.get("q1", ""), identity),
        )
        hamiltonian += float(term["coefficient"]) * operator
    exact = float(np.linalg.eigvalsh(hamiltonian)[0])
    assert exact == pytest.approx(
        fixture.manifest["reference"]["exact_ground_energy_hartree"], abs=1e-12
    )


def test_h2_analysis_uses_cascaqit_pauli_and_qwc_contracts() -> None:
    analysis = analyze_electronic_structure()
    assert analysis["problem"]["type"] == "pauli_hamiltonian"
    assert analysis["resource"] == {
        "logicalQubits": 2,
        "termCount": 4,
        "measurementGroups": 2,
        "parameterCount": 4,
    }
    assert analysis["decision"]["recommendedMode"] == "digital"
    assert len(analysis["problem"]["hash"]) == 64
    assert len(analysis["analysisHash"]) == 64


def test_h2_recommended_vqe_reaches_declared_accuracy_and_executes_qwc() -> None:
    run = run_electronic_structure(
        shots=32,
        seed=23,
        layers=1,
        parameter_budget=40,
        optimizer_starts=2,
    )
    assert run["domain"]["withinChemicalAccuracy"] is True
    assert run["domain"]["absoluteErrorHartree"] <= 0.0016
    assert run["quantum"]["summary"]["measurementGroups"] == 2
    assert run["quantum"]["summary"]["totalMeasurementShots"] == 64
    assert sum(run["quantum"]["counts"].values()) == 32
    assert run["audit"]["hardwareExecution"] is False
    assert run["audit"]["networkAccessed"] is False
