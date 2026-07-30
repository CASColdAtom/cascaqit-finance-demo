"""Effective active-center Hamiltonian and observable evidence tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

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
    ("preset", "sites", "paths", "terms"),
    [
        ("trinuclear_frustrated", 3, 3, 12),
        ("tetranuclear_ligand_field", 4, 4, 16),
    ],
)
def test_advanced_fixtures_expand_generic_spin_networks(
    preset: str, sites: int, paths: int, terms: int
) -> None:
    fixture = load_active_center_fixture(preset)
    analysis = analyze_active_center(preset, {})

    assert len(fixture.pauli["logical_order"]) == sites
    assert len(fixture.pauli["presets"][preset]["exchange_paths"]) == paths
    assert len(analysis["problem"]["terms"]) == terms
    assert analysis["resource"]["logicalQubits"] == sites
    assert analysis["domain"]["exactFirstGapMeV"] >= 0
    assert (
        analysis["domain"]["exactFirstGapSource"]
        == "classical_exact_diagonalization"
    )
    assert analysis["problem"]["templateHash"] != analysis["problem"]["hash"]


def test_generated_fixtures_record_current_generator_hash() -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "generate_active_center_fixtures.py"
    )
    expected = hashlib.sha256(script.read_bytes()).hexdigest()
    for preset in (
        "antiferromagnetic",
        "trinuclear_frustrated",
        "tetranuclear_ligand_field",
    ):
        assert (
            load_active_center_fixture(preset).manifest["generation"]["script_sha256"]
            == expected
        )


@pytest.mark.parametrize(
    "preset", ["antiferromagnetic", "ligand_field", "coupling_imbalance"]
)
def test_analysis_builds_exchange_fields_and_exact_reference(preset: str) -> None:
    analysis = analyze_active_center(preset, {})
    fixture = load_active_center_fixture()
    reference = fixture.manifest["reference"]["standard_presets"][preset]
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
    assert analysis["domain"]["exactGroundEnergyMeV"] == pytest.approx(
        reference["exact_ground_energy_mev"], abs=1e-12
    )


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


def test_multicenter_vqe_returns_all_site_and_path_observables() -> None:
    run = run_active_center(
        preset="trinuclear_frustrated",
        values={},
        shots=128,
        seed=7,
        layers=2,
        parameter_budget=20,
        optimizer_starts=1,
    )

    assert len(run["domain"]["magnetization"]) == 3
    assert len(run["domain"]["correlations"]) == 9
    assert {item["pathId"] for item in run["domain"]["correlations"]} == {
        "exchange.m1-m2",
        "exchange.m2-m3",
        "exchange.m3-m1",
    }
    assert run["comparison"]["exactFirstGapSource"] == (
        "classical_exact_diagonalization"
    )
    assert run["audit"]["templateHamiltonianHash"] != run["audit"]["hamiltonianHash"]
