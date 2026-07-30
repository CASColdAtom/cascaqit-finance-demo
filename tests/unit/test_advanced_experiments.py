"""V2 capability, complexity profile, and deterministic planning tests."""

from __future__ import annotations

from cascaqit_biomedicine_demo.advanced_experiments import (
    CapabilityRegistry,
    build_experiment_plan,
    profiles_for,
)


def _analysis(*, qubits: int = 4, variables: int = 0, terms: int = 12) -> dict:
    variable_ids = [f"q{i}" for i in range(qubits or variables)]
    return {
        "executionFamily": "pauli_vqe" if qubits else "problem",
        "dataset": {"id": "fixture.test", "version": "1", "manifestHash": "m"},
        "problem": {
            "hash": "problem-hash",
            "variables": variable_ids,
            "terms": [{"id": f"t{i}"} for i in range(terms)],
        },
        "resource": {
            "logicalQubits": qubits,
            "logical_variables": variables,
            "termCount": terms,
            "measurementGroups": 3 if qubits else 0,
        },
        "analysisHash": "analysis-hash",
    }


def _recommended() -> dict:
    return {
        "algorithm": "vqe",
        "layers": 1,
        "shots": 64,
        "seed": 23,
        "parameterBudget": 40,
        "optimizerStarts": 1,
        "estimatedSeconds": 1.25,
    }


def test_capability_registry_requires_validated_sdk_series() -> None:
    supported = CapabilityRegistry("1.0.5a0")
    unsupported = CapabilityRegistry("1.0.6")

    assert supported.is_available("pauli_vqe") is True
    assert unsupported.is_available("pauli_vqe") is False
    assert supported.is_available("experiment_planning") is True
    assert supported.is_available("batch_execution") is True
    assert supported.to_dict()["sdk"]["validatedRange"] == ">=1.0.5a0,<1.0.6"


def test_profiles_keep_released_and_planned_levels_separate() -> None:
    profiles = profiles_for("electronic_structure")

    assert [item.profile_id for item in profiles] == [
        "standard",
        "advanced_live",
        "research",
    ]
    assert profiles[0].status == "available"
    assert profiles[1].status == "available"
    assert profiles[1].max_logical_qubits == 6
    assert profiles[2].max_logical_qubits == 8


def test_standard_plan_is_stable_and_synchronous() -> None:
    arguments = {
        "case_id": "electronic_structure",
        "preset": "h2_bond_scan",
        "experiment_level": "standard",
        "requested_profile": None,
        "analysis_points": [({"dataset": "h2"}, _analysis())],
        "configurations": [],
        "seeds": [],
        "recommended_execution": _recommended(),
        "capabilities": CapabilityRegistry("1.0.5a0"),
    }

    first = build_experiment_plan(**arguments)
    second = build_experiment_plan(**arguments)

    assert first == second
    assert first["executionPolicy"] == "sync"
    assert first["runCount"] == 1
    assert first["diagnostics"] == []
    assert len(first["planId"]) == 64
    assert first["completeDomainProblemHash"] != first["quantumSubproblemHash"]


def test_unreleased_advanced_batch_plan_reports_all_blockers() -> None:
    plan = build_experiment_plan(
        case_id="electronic_structure",
        preset="advanced_reference",
        experiment_level="advanced",
        requested_profile="advanced_live",
        analysis_points=[({"geometry": 0.7}, _analysis())],
        configurations=[],
        seeds=[7, 23, 41],
        recommended_execution=_recommended(),
        capabilities=CapabilityRegistry("1.0.5a0"),
    )

    assert plan["runCount"] == 3
    assert plan["executionPolicy"] == "rejected"
    assert {item["code"] for item in plan["diagnostics"]} == {
        "ADVANCED_PRESET_REQUIRED",
    }


def test_standard_profile_rejects_resource_and_cost_overflow() -> None:
    plan = build_experiment_plan(
        case_id="electronic_structure",
        preset="h2_bond_scan",
        experiment_level="standard",
        requested_profile="standard",
        analysis_points=[({"dataset": "oversized"}, _analysis(qubits=5))],
        configurations=[
            {
                "shots": 1024,
                "parameter_budget": 80,
                "optimizer_starts": 3,
                "layers": 3,
            }
        ],
        seeds=[7],
        recommended_execution=_recommended(),
        capabilities=CapabilityRegistry("1.0.5a0"),
    )

    codes = {item["code"] for item in plan["diagnostics"]}
    assert "LOGICAL_QUBITS_LIMIT_EXCEEDED" in codes
    assert "ESTIMATED_COST_LIMIT_EXCEEDED" in codes
    assert plan["executionPolicy"] == "rejected"


def test_plan_enforces_sdk_capability_snapshot() -> None:
    plan = build_experiment_plan(
        case_id="electronic_structure",
        preset="h2_bond_scan",
        experiment_level="standard",
        requested_profile="standard",
        analysis_points=[({"dataset": "h2"}, _analysis())],
        configurations=[],
        seeds=[],
        recommended_execution=_recommended(),
        capabilities=CapabilityRegistry("1.0.6"),
    )

    assert plan["executionPolicy"] == "rejected"
    assert {item["code"] for item in plan["diagnostics"]} == {
        "SDK_CAPABILITY_NOT_AVAILABLE"
    }


def test_plan_rejects_configuration_that_would_change_execution_family() -> None:
    plan = build_experiment_plan(
        case_id="peptide_landscape",
        preset="octapeptide_hydrophobic",
        experiment_level="advanced",
        requested_profile="advanced_live",
        analysis_points=[({}, _analysis(qubits=0, variables=12, terms=78))],
        configurations=[{"mode": "hybrid", "algorithm": "vqe"}],
        seeds=[7, 23],
        recommended_execution={**_recommended(), "algorithm": "qaoa"},
        capabilities=CapabilityRegistry("1.0.5a0"),
    )

    assert plan["executionPolicy"] == "rejected"
    assert {item["code"] for item in plan["diagnostics"]} == {
        "EXECUTION_MODE_UNSUPPORTED",
        "ALGORITHM_UNSUPPORTED",
    }
