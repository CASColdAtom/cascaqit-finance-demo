"""Effective active-center Hamiltonian and observable evidence tests."""

from __future__ import annotations

import pytest

from cascaqit_biomedicine_demo.active_center import (
    active_center_values,
    analyze_active_center,
    load_active_center_fixture,
    run_active_center,
)


def test_fixture_defines_three_validated_presets() -> None:
    fixture = load_active_center_fixture()
    assert set(fixture.pauli["presets"]) == {
        "antiferromagnetic",
        "ligand_field",
        "coupling_imbalance",
    }
    assert fixture.manifest["logical_order"] == ["spin.m1", "spin.m2"]


@pytest.mark.parametrize(
    "preset", ["antiferromagnetic", "ligand_field", "coupling_imbalance"]
)
def test_analysis_builds_exchange_fields_and_exact_reference(preset: str) -> None:
    analysis = analyze_active_center(preset, {})
    assert {item["id"] for item in analysis["problem"]["terms"]} == {
        "exchange.xx",
        "exchange.yy",
        "exchange.zz",
        "field.m1",
        "field.m2",
    }
    assert analysis["implementationStatus"] == "available"
    assert analysis["decision"]["recommendedMode"] == "digital"
    assert analysis["domain"]["exactGroundEnergyMeV"] < 0


def test_input_changes_hamiltonian_and_analysis_hashes() -> None:
    first = analyze_active_center("antiferromagnetic", {})
    second = analyze_active_center(
        "antiferromagnetic", {"exchange_coupling": 1.4, "local_field": 0.2}
    )
    assert first["problem"]["hash"] != second["problem"]["hash"]
    assert first["analysisHash"] != second["analysisHash"]


def test_input_validation_rejects_out_of_scope_parameters() -> None:
    with pytest.raises(ValueError, match="exchange_coupling"):
        active_center_values("antiferromagnetic", {"exchange_coupling": -1})


def test_run_returns_backend_observables_and_one_hamiltonian_identity() -> None:
    run = run_active_center(
        preset="antiferromagnetic",
        values={},
        shots=512,
        seed=7,
        layers=1,
        parameter_budget=40,
        optimizer_starts=1,
    )
    assert run["audit"]["hamiltonianHash"] == run["audit"]["referenceHamiltonianHash"]
    assert (
        run["comparison"]["hamiltonianHash"] == run["comparison"]["vqeHamiltonianHash"]
    )
    assert {item["operator"] for item in run["domain"]["correlations"]} == {
        "XX",
        "YY",
        "ZZ",
    }
    assert {item["siteId"] for item in run["domain"]["magnetization"]} == {
        "spin.m1",
        "spin.m2",
    }
    assert sum(run["domain"]["sectorOccupancy"].values()) == pytest.approx(1.0)
    measured_terms = {
        term_id
        for group in run["quantum"]["measurement"]["groups"]
        for term_id in group["termExpectations"]
    }
    assert measured_terms == {
        "exchange.xx",
        "exchange.yy",
        "exchange.zz",
        "field.m1",
        "field.m2",
    }
    assert run["domain"]["absoluteErrorMeV"] < 0.02
    assert run["audit"]["claimBoundary"] == "effective_spin_model_only"
