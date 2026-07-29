"""Discrete docking fixture, QUBO, and Hybrid gate tests."""

from __future__ import annotations

import pytest

from cascaqit_biomedicine_demo.docking import (
    DockingMatchScenario,
    analyze_docking_match,
    classic_docking_solution,
    docking_input,
    load_docking_fixture,
    run_docking_match,
)


def test_1hsg_fixture_has_audited_source_and_cross_references() -> None:
    fixture = load_docking_fixture()
    source = fixture.manifest["source"]
    assert source["pdb_id"] == "1HSG"
    assert source["ligand_component_id"] == "MK1"
    assert source["ligand_name"] == "INDINAVIR"
    assert source["license"] == "CC0-1.0"
    assert len(source["source_file_sha256"]) == 64
    assert len(fixture.domain["poses"]) == 2
    assert len(fixture.domain["matches"]) == 8
    assert len(fixture.domain["conflicts"]) == 4


@pytest.mark.parametrize(
    "preset",
    ("reference_pose", "strict_geometry", "pharmacophore_coverage"),
)
def test_docking_presets_build_conserved_qubo_with_classic_baseline(
    preset: str,
) -> None:
    scenario = DockingMatchScenario()
    definition = scenario.build_definition(docking_input(preset, {}))
    assert len(definition.problem.variables) == 11
    assert definition.auxiliary_variables == ("slack.coverage",)
    assert len(definition.analog_business_pairs) == 4
    assert definition.coefficient_contributions
    assert definition.geometry_evidence is not None
    assert definition.geometry_evidence.source == "verified_embedding"
    baseline = classic_docking_solution(preset)
    assert baseline.feasible is True
    assert baseline.coverage >= 2


def test_docking_analysis_recommends_real_hybrid_split() -> None:
    payload = analyze_docking_match("reference_pose", {})
    hybrid = next(
        item for item in payload["decision"]["modes"] if item["mode"] == "hybrid"
    )
    assert payload["decision"]["recommendedMode"] == "hybrid"
    assert hybrid["status"] == "recommended"
    assert hybrid["coveredContributionCount"] == 4
    assert hybrid["declaredContributionCount"] == 4
    assert hybrid["geometryStatus"] == "verified"
    assert hybrid["analogTermCount"] > 0
    assert hybrid["digitalTermCount"] > 0
    assert not any(code.startswith("FINANCE_") for code in hybrid["diagnosticCodes"])


@pytest.mark.parametrize("seed", (1, 6, 7))
def test_calibrated_hybrid_seeds_observe_feasible_quantum_candidate(seed: int) -> None:
    run = run_docking_match(
        preset="reference_pose",
        values={},
        mode="hybrid",
        shots=128,
        seed=seed,
        layers=1,
        search_strategy="continuous",
        parameter_budget=12,
        optimizer_starts=1,
    )
    domain = run["domain"]
    assert domain["quantumCandidate"]["feasible"] is True
    assert domain["observedFeasibleCount"] >= 1
    assert domain["classicOptimum"]["feasible"] is True
    assert domain["coCrystalReference"]["feasible"] is True
    assert domain["quantumCandidate"]["source"] == "quantum_observed"
    assert domain["classicOptimum"]["source"] == "complete_enumeration"
    assert domain["coCrystalReference"]["source"] == "co_crystal_reference"
    assert run["quantum"]["summary"]["analogTerms"] > 0
    assert run["quantum"]["summary"]["digitalTerms"] > 0
    assert run["quantum"]["blocks"] == [
        "digital",
        "analog",
        "digital",
        "measure",
    ]
    assert run["audit"]["hardwareExecution"] is False
    assert run["audit"]["networkAccessed"] is False


def test_digital_qaoa_is_available_as_a_separate_comparison_path() -> None:
    run = run_docking_match(
        preset="reference_pose",
        values={},
        mode="digital",
        shots=16,
        seed=7,
        layers=1,
        search_strategy="preset",
        parameter_budget=2,
        optimizer_starts=1,
    )
    assert run["quantum"]["mode"] == "digital"
    assert run["quantum"]["summary"]["analogTerms"] == 0
    assert run["quantum"]["summary"]["digitalTerms"] > 0
    assert run["domain"]["classicOptimum"]["feasible"] is True
