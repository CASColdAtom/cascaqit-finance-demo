"""Finite peptide landscape validation, QUBO, and QAOA tests."""

import hashlib
from pathlib import Path

import pytest

from cascaqit_biomedicine_demo.peptide_landscape import (
    _definition,
    analyze_peptide_landscape,
    load_peptide_fixture,
    peptide_values,
    run_peptide_landscape,
)


def test_fixture_contains_ten_validated_self_avoiding_conformations() -> None:
    fixture = load_peptide_fixture()
    assert len(fixture.domain["conformations"]) == 10
    assert {len(item["contacts"]) for item in fixture.domain["conformations"]} == {
        0,
        1,
        2,
    }


@pytest.mark.parametrize(
    "preset", ("hydrophobic_core", "charged_competition", "contact_limited")
)
def test_presets_build_balanced_one_hot_qubo_and_complete_landscape(
    preset: str,
) -> None:
    values = peptide_values(preset, {})
    fixture = load_peptide_fixture()
    definition = _definition(preset, values)
    analysis = analyze_peptide_landscape(preset, values)
    reference = fixture.manifest["reference"]["standard_presets"][preset]
    assert len(definition.problem.variables) == 10
    assert len(analysis["domain"]["conformations"]) == 10
    assert analysis["problem"]["coefficientLedger"]["balanced"] is True
    assert analysis["decision"]["recommendedMode"] == "digital"
    assert list(definition.problem.variables) == fixture.manifest["variable_order"]
    assert analysis["domain"]["classicGroundIds"] == reference[
        "ground_conformation_ids"
    ]
    ground_energy = min(
        item["energy"] for item in analysis["domain"]["conformations"]
    )
    assert ground_energy == pytest.approx(reference["ground_energy"])


def test_calibrated_qaoa_observes_low_energy_feasible_candidate() -> None:
    run = run_peptide_landscape(
        preset="hydrophobic_core",
        values={},
        shots=256,
        seed=7,
        layers=1,
        parameter_budget=24,
        optimizer_starts=1,
    )
    candidate = run["domain"]["quantumCandidate"]
    assert candidate["feasible"] is True
    assert run["domain"]["observedFeasibleCount"] >= 1
    assert run["domain"]["energyGapFromGround"] <= 0.1
    assert run["domain"]["classicGroundConformations"]
    assert run["audit"]["hardwareExecution"] is False


def test_advanced_fixture_has_48_validated_basin_labeled_conformations() -> None:
    fixture = load_peptide_fixture("octapeptide_hydrophobic")
    repeated = load_peptide_fixture("octapeptide_hydrophobic")
    conformations = fixture.domain["conformations"]

    assert len(conformations) == 48
    assert fixture.domain["residueCount"] == 8
    assert {item["basinId"] for item in conformations} == {
        f"basin.{index:02d}" for index in range(8)
    }
    assert fixture.manifest_hash == repeated.manifest_hash


def test_advanced_peptide_manifest_tracks_generator_source() -> None:
    fixture = load_peptide_fixture("octapeptide_hydrophobic")
    generator = (
        Path(__file__).resolve().parents[2]
        / fixture.manifest["generation"]["script"]
    )

    assert hashlib.sha256(generator.read_bytes()).hexdigest() == fixture.manifest[
        "generation"
    ]["script_sha256"]


@pytest.mark.parametrize(
    "preset",
    (
        "octapeptide_hydrophobic",
        "octapeptide_charge_shift",
        "octapeptide_mutation",
    ),
)
def test_advanced_activity_window_preserves_ground_and_major_basins(
    preset: str,
) -> None:
    values = peptide_values(preset, {})
    first = analyze_peptide_landscape(preset, values)
    second = analyze_peptide_landscape(preset, values)
    selection = first["domain"]["subproblemSelection"]
    active_ids = {item["id"] for item in first["domain"]["conformations"]}
    active_basins = {
        item["basinId"] for item in first["domain"]["conformations"]
    }

    assert len(first["domain"]["fullLandscape"]) == 48
    assert len(first["domain"]["conformations"]) == 12
    assert len(first["problem"]["variables"]) == 12
    assert len(first["problem"]["terms"]) == 78
    assert set(first["domain"]["classicGroundIds"]).issubset(active_ids)
    assert set(selection["majorBasins"]).issubset(active_basins)
    assert selection["selectionHash"] == second["problem"]["selectionHash"]
    assert len(selection["excluded"]) == 36
    assert first["problem"]["completeDomainProblemHash"] != first["problem"][
        "quantumSubproblemHash"
    ]
    assert first["problem"]["selectionHash"] not in {
        first["problem"]["completeDomainProblemHash"],
        first["problem"]["quantumSubproblemHash"],
    }


def test_advanced_qaoa_smoke_never_substitutes_classic_ground() -> None:
    run = run_peptide_landscape(
        preset="octapeptide_hydrophobic",
        values={},
        shots=8,
        seed=7,
        layers=1,
        parameter_budget=4,
        optimizer_starts=1,
    )
    candidate = run["domain"]["quantumCandidate"]

    assert run["quantum"]["summary"]["qubits"] == 12
    assert candidate["source"] in {"quantum_observed", "quantum_not_observed"}
    assert run["domain"]["classicGroundConformations"]
