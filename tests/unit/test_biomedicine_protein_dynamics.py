"""Versioned protein state-network, path QUBO, and QAOA behavior tests."""

from __future__ import annotations

from copy import deepcopy

import pytest

from cascaqit_biomedicine_demo.protein_dynamics import (
    _decode,
    _definition,
    _validate_domain,
    analyze_protein_dynamics,
    load_protein_dynamics_fixture,
    protein_dynamics_values,
    run_protein_dynamics,
)


def _path_bitstring(definition, state_ids: list[str]) -> str:
    target = definition.metadata["values"]["target_state"]
    slot_count = len(definition.metadata["slot_variables"])
    padded = [*state_ids[1:], *([target] * slot_count)][:slot_count]
    selected = {
        f"slot.{slot}.{node_id}" for slot, node_id in enumerate(padded)
    }
    return "".join(
        "1" if variable in selected else "0"
        for variable in definition.problem.variables
    )


@pytest.mark.parametrize(
    "preset", ("open_to_closed", "barrier_shift", "alternate_basin")
)
def test_protein_fixture_preserves_endpoints_path_and_balanced_qubo(
    preset: str,
) -> None:
    fixture = load_protein_dynamics_fixture(preset)
    analysis = analyze_protein_dynamics(preset, {"maximum_steps": 4})
    selection = analysis["domain"]["subproblemSelection"]

    assert fixture.domain["edgeWeight"]["unit"] == "dimensionless_model_cost"
    assert analysis["implementationStatus"] == "available"
    assert analysis["decision"]["recommendedMode"] == "digital"
    assert analysis["problem"]["coefficientLedger"]["balanced"] is True
    assert selection["startPreserved"] is True
    assert selection["targetPreserved"] is True
    assert selection["connectivityPreserved"] is True
    assert selection["activePathCount"] >= 2
    assert len(selection["activeNodeIds"]) == 4
    assert analysis["domain"]["classicShortestPath"]["feasible"] is True
    assert analysis["domain"]["classicActivePath"]["feasible"] is True
    assert 9 <= analysis["resource"]["logical_variables"] <= 12


def test_protein_path_qubo_declares_every_required_constraint() -> None:
    definition = _definition(
        "open_to_closed", {"maximum_steps": 4, "barrier_weight": 1.0}
    )
    group_ids = {item.group_id for item in definition.term_groups}

    assert {
        "start_endpoint",
        "target_endpoint",
        "flow_conservation",
        "path_continuity",
        "cycle_prohibition",
        "maximum_path_length",
    } <= group_ids
    assert {
        item.group_id for item in definition.coefficient_contributions
    } >= {
        "start_endpoint",
        "target_endpoint",
        "flow_conservation",
        "path_continuity",
        "cycle_prohibition",
    }


def test_protein_decoder_accepts_bounded_path_and_rejects_loop_or_gap() -> None:
    definition = _definition(
        "open_to_closed", {"maximum_steps": 4, "barrier_weight": 1.0}
    )
    classic = definition.metadata["active"]["paths"][0]
    feasible = _decode(
        _path_bitstring(definition, classic["stateIds"]),
        definition,
        source="test",
    )

    assert feasible["feasible"] is True
    assert feasible["stateIds"] == classic["stateIds"]
    assert feasible["pathLength"] <= 4
    assert feasible["pathCost"] == classic["pathCost"]

    choices = definition.metadata["choices"]
    target = definition.metadata["values"]["target_state"]
    intermediate = next(item for item in choices if item != target)
    loop_states = [
        definition.metadata["values"]["start_state"],
        intermediate,
        intermediate,
        target,
    ]
    loop = _decode(
        _path_bitstring(definition, loop_states), definition, source="test"
    )
    missing = _decode(
        "0" * len(definition.problem.variables), definition, source="test"
    )

    assert loop["feasible"] is False
    assert "cycle_prohibition" in loop["failureReasons"]
    assert missing["feasible"] is False
    assert "path_continuity" in missing["failureReasons"]
    assert "target_endpoint" in missing["failureReasons"]


def test_protein_fixture_rejects_disconnected_reference_and_invalid_controls() -> None:
    fixture = load_protein_dynamics_fixture("open_to_closed")
    invalid = deepcopy(fixture.domain)
    invalid["presets"]["open_to_closed"]["referencePath"] = [
        "state.open",
        "state.closed",
    ]

    with pytest.raises(ValueError, match="reference path is disconnected"):
        _validate_domain(invalid)
    with pytest.raises(ValueError, match="between 3 and 4"):
        protein_dynamics_values("open_to_closed", {"maximum_steps": 5})
    with pytest.raises(ValueError, match="between 0.5 and 2.0"):
        protein_dynamics_values("open_to_closed", {"barrier_weight": 2.1})


@pytest.mark.parametrize("seed", (7, 23, 41))
def test_protein_qaoa_never_uses_classic_fallback(seed: int) -> None:
    run = run_protein_dynamics(
        preset="open_to_closed",
        values={"maximum_steps": 3, "barrier_weight": 1.0},
        shots=64,
        seed=seed,
        layers=1,
        parameter_budget=4,
        optimizer_starts=1,
    )

    candidate = run["domain"]["quantumCandidate"]
    assert run["domain"]["classicShortestPath"]["source"] == (
        "classic_bounded_dijkstra"
    )
    assert run["audit"]["hardwareExecution"] is False
    if candidate is None:
        assert run["domain"]["quantumStatus"] == "quantum_not_observed"
    else:
        assert candidate["source"] == "quantum_observed"
        assert candidate["feasible"] is True
        assert candidate["pathCost"] is not None
    assert "time" not in {
        key.lower() for key in (candidate or run["domain"]["classicShortestPath"])
    }
