from __future__ import annotations

import pytest

from cascaqit_materials_demo.defect_adsorption import (
    DefectAdsorptionScenario,
    analyze_defect_adsorption,
    classic_material_solution,
    load_materials_fixture,
    material_input,
    material_values,
    run_defect_adsorption,
)

PRESETS = (
    "ceria_vacancy_co",
    "tio2_vacancy_water",
    "mos2_vacancy_hydrogen",
)


def test_fixture_has_joint_variables_periodicity_and_separate_coordinates() -> None:
    fixture = load_materials_fixture()

    assert len(fixture.domain["defectCandidates"]) == 3
    assert len(fixture.domain["adsorptionCandidates"]) == 8
    assert fixture.domain["periodicBoundary"]["wrap"] == [True, True]
    assert len(fixture.domain["symmetryOperations"]) >= 2
    assert set(fixture.domain["coordinateSystem"]) == {
        "material",
        "effective",
        "compiled",
    }


@pytest.mark.parametrize("preset", PRESETS)
def test_joint_qubo_has_conserved_ledger_and_hybrid_residual(preset: str) -> None:
    analysis = analyze_defect_adsorption(preset, {})
    variables = analysis["problem"]["variables"]
    hybrid = next(
        item for item in analysis["decision"]["modes"] if item["mode"] == "hybrid"
    )

    assert any(item.startswith("defect.") for item in variables)
    assert any(item.startswith("ads.") for item in variables)
    assert analysis["problem"]["coefficientLedger"]["balanced"] is True
    assert analysis["decision"]["recommendedMode"] == "hybrid"
    assert hybrid["geometryStatus"] == "verified"
    assert hybrid["analogTermCount"] > 0
    assert hybrid["digitalTermCount"] > 0
    assert hybrid["missingContributionIds"] == []
    assert hybrid["unexpectedInteractionPairs"] == []


@pytest.mark.parametrize("preset", PRESETS)
def test_exact_baseline_is_feasible_for_all_presets(preset: str) -> None:
    solution = classic_material_solution(preset)

    assert solution.feasible is True
    assert len(solution.selected_defect_ids) == 1
    assert len(solution.selected_adsorption_ids) == 2
    assert all(item["passed"] for item in solution.checks)


def test_controls_enforce_integer_defects_and_discrete_coverage() -> None:
    with pytest.raises(ValueError, match="integer"):
        material_values("ceria_vacancy_co", {"defect_count": 1.5})
    with pytest.raises(ValueError, match="coverage"):
        material_values("ceria_vacancy_co", {"coverage": 0.6})


def test_decoder_rejects_forbidden_and_overoccupied_configurations() -> None:
    scenario = DefectAdsorptionScenario()
    case_input = material_input(
        "ceria_vacancy_co", material_values("ceria_vacancy_co", {})
    )
    definition = scenario.build_definition(case_input)
    selected = {"defect.d0", "ads.a0", "ads.a1", "ads.c1"}
    values = {
        variable: int(variable in selected) for variable in definition.problem.variables
    }

    solution = scenario.decode_values(case_input, definition, values)

    assert solution.feasible is False
    failed = {item["id"] for item in solution.checks if not item["passed"]}
    assert "site_orientation_exclusion" in failed
    assert "allowed_defect_adsorption" in failed


def test_quantum_not_observed_never_uses_classic_fallback() -> None:
    payload = run_defect_adsorption(
        preset="ceria_vacancy_co",
        values={},
        mode="digital",
        shots=1,
        seed=23,
        layers=1,
        search_strategy="preset",
        parameter_budget=2,
        optimizer_starts=1,
    )

    if payload["domain"]["quantumStatus"] == "quantum_not_observed":
        assert payload["domain"]["quantumCandidate"] is None
    assert payload["domain"]["classicOptimum"]["source"] == "complete_enumeration"
    assert payload["audit"]["reportSchema"] == "materials.execution-report.v1"
