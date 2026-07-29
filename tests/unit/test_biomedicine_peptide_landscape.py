"""Finite peptide landscape validation, QUBO, and QAOA tests."""

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
