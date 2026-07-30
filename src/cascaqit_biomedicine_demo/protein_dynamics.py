"""Versioned conformation-network path QUBO and Digital QAOA execution."""

from __future__ import annotations

import hashlib
import heapq
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cascaqit.algorithms import QAOA, OptimizerConfig
from cascaqit.problems import evaluate_qubo_bitstring

from cascaqit_biomedicine_demo.catalog import BIOMEDICINE_SCENARIO_SPECS
from cascaqit_biomedicine_demo.fixtures import validate_manifest_contract
from cascaqit_biomedicine_demo.pauli_vqe import hash_payload
from cascaqit_industry_demo.audit import finalize_stable_audit, local_backend_context
from cascaqit_industry_demo.problem_model import (
    OptimizationProblemDefinition,
    QuboBuilder,
    TermGroup,
)

DATA_ROOT = Path(__file__).resolve().parent / "data" / "protein_dynamics"
_FIXTURE_ROOT = DATA_ROOT / "adenylate_kinase_network" / "1"
_PRESETS = {"open_to_closed", "barrier_shift", "alternate_basin"}


@dataclass(frozen=True)
class ProteinDynamicsFixture:
    manifest: dict[str, Any]
    domain: dict[str, Any]
    preset: dict[str, Any]
    manifest_hash: str


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"protein fixture must contain an object: {path.name}")
    return value, raw


def _validate_domain(domain: dict[str, Any]) -> None:
    nodes = domain.get("nodes")
    transitions = domain.get("transitions")
    if not isinstance(nodes, list) or len(nodes) < 4:
        raise ValueError("protein network requires at least four states")
    if not isinstance(transitions, list) or not transitions:
        raise ValueError("protein network requires allowed transitions")
    node_ids = [item.get("id") for item in nodes]
    if any(not isinstance(item, str) or not item for item in node_ids):
        raise ValueError("protein states require stable identifiers")
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("protein state identifiers must be unique")
    for node in nodes:
        source = node.get("structureSource")
        if not isinstance(source, dict) or any(
            not isinstance(source.get(key), str) or not source[key]
            for key in ("kind", "identifier", "method")
        ):
            raise ValueError(f"protein state {node['id']} has no structure source")
        if not all(isinstance(node.get(key), (int, float)) for key in ("x", "y")):
            raise ValueError(f"protein state {node['id']} has invalid layout")
    profiles: set[str] | None = None
    transition_ids: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for transition in transitions:
        transition_id = transition.get("id")
        edge = (transition.get("from"), transition.get("to"))
        if (
            not isinstance(transition_id, str)
            or not transition_id
            or transition_id in transition_ids
        ):
            raise ValueError("protein transition identifiers must be unique")
        if edge[0] not in node_ids or edge[1] not in node_ids or edge[0] == edge[1]:
            raise ValueError(
                f"protein transition {transition_id} has invalid endpoints"
            )
        if edge in pairs:
            raise ValueError("protein network repeats a directed transition")
        if not isinstance(transition.get("structuralCost"), (int, float)):
            raise ValueError(
                f"protein transition {transition_id} has no structural cost"
            )
        weights = transition.get("barrierProfiles")
        if not isinstance(weights, dict) or any(
            not isinstance(value, (int, float)) for value in weights.values()
        ):
            raise ValueError(f"protein transition {transition_id} has invalid weights")
        current_profiles = set(weights)
        profiles = current_profiles if profiles is None else profiles
        if current_profiles != profiles:
            raise ValueError("protein transition weight profiles are inconsistent")
        transition_ids.add(transition_id)
        pairs.add(edge)
    presets = domain.get("presets")
    if not isinstance(presets, dict) or set(presets) != _PRESETS:
        raise ValueError("protein fixture preset registry is inconsistent")
    for preset_id, preset in presets.items():
        if preset.get("start") not in node_ids or preset.get("target") not in node_ids:
            raise ValueError(f"protein preset {preset_id} has invalid endpoints")
        if preset.get("weightProfile") not in (profiles or set()):
            raise ValueError(
                f"protein preset {preset_id} has an unknown weight profile"
            )
        path = preset.get("referencePath")
        if (
            not isinstance(path, list)
            or path[0] != preset["start"]
            or path[-1] != preset["target"]
        ):
            raise ValueError(
                f"protein preset {preset_id} has an invalid reference path"
            )
        if any((left, right) not in pairs for left, right in zip(path, path[1:])):
            raise ValueError(
                f"protein preset {preset_id} reference path is disconnected"
            )
    edge_weight = domain.get("edgeWeight")
    if (
        not isinstance(edge_weight, dict)
        or edge_weight.get("unit") != "dimensionless_model_cost"
    ):
        raise ValueError("protein edge-weight meaning and unit are required")


def load_protein_dynamics_fixture(
    preset: str | None = None,
) -> ProteinDynamicsFixture:
    selected = preset or "open_to_closed"
    if selected not in _PRESETS:
        raise ValueError(f"unknown protein dynamics preset: {selected}")
    manifest, manifest_raw = _read_json(_FIXTURE_ROOT / "manifest.json")
    validate_manifest_contract(manifest)
    domain, domain_raw = _read_json(_FIXTURE_ROOT / "domain.json")
    artifacts = manifest.get("artifacts", [])
    if len(artifacts) != 1 or artifacts[0].get("path") != "domain.json":
        raise ValueError("protein fixture artifact declaration is incomplete")
    if hashlib.sha256(domain_raw).hexdigest() != artifacts[0].get("sha256"):
        raise ValueError("protein fixture checksum mismatch: domain.json")
    _validate_domain(domain)
    declared_order = [item["id"] for item in domain["transitions"]]
    if manifest.get("variable_order") != declared_order:
        raise ValueError("protein fixture transition order is inconsistent")
    return ProteinDynamicsFixture(
        manifest=manifest,
        domain=domain,
        preset=domain["presets"][selected],
        manifest_hash=hashlib.sha256(manifest_raw).hexdigest(),
    )


def protein_dynamics_values(preset: str, overrides: dict[str, Any]) -> dict[str, Any]:
    fixture = load_protein_dynamics_fixture(preset)
    unknown = set(overrides) - {"maximum_steps", "barrier_weight"}
    if unknown:
        raise ValueError(
            f"unknown protein dynamics control values: {', '.join(sorted(unknown))}"
        )
    raw_steps = overrides.get("maximum_steps", 4)
    if isinstance(raw_steps, bool) or not isinstance(raw_steps, (int, float)):
        raise ValueError("maximum_steps must be an integer")
    maximum_steps = int(raw_steps)
    if maximum_steps != raw_steps or not 3 <= maximum_steps <= 4:
        raise ValueError("maximum_steps must be an integer between 3 and 4")
    raw_weight = overrides.get("barrier_weight", 1.0)
    if isinstance(raw_weight, bool) or not isinstance(raw_weight, (int, float)):
        raise ValueError("barrier_weight must be numeric")
    barrier_weight = float(raw_weight)
    if not 0.5 <= barrier_weight <= 2.0:
        raise ValueError("barrier_weight must be between 0.5 and 2.0")
    return {
        "maximum_steps": maximum_steps,
        "barrier_weight": barrier_weight,
        "start_state": fixture.preset["start"],
        "target_state": fixture.preset["target"],
        "weight_profile": fixture.preset["weightProfile"],
    }


def _weighted_edges(
    fixture: ProteinDynamicsFixture, barrier_weight: float
) -> list[dict[str, Any]]:
    profile = fixture.preset["weightProfile"]
    result = []
    for transition in fixture.domain["transitions"]:
        structural = float(transition["structuralCost"])
        barrier = float(transition["barrierProfiles"][profile])
        result.append(
            {
                **transition,
                "barrierProfile": profile,
                "barrierComponent": barrier,
                "cost": round(structural + barrier_weight * barrier, 10),
                "unit": fixture.domain["edgeWeight"]["unit"],
                "sourceMethod": fixture.domain["edgeWeight"]["sourceMethod"],
            }
        )
    return result


def _bounded_paths(
    edges: list[dict[str, Any]], start: str, target: str, maximum_steps: int
) -> list[dict[str, Any]]:
    outgoing: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        outgoing.setdefault(edge["from"], []).append(edge)
    queue: list[tuple[float, tuple[str, ...], tuple[str, ...]]] = [(0.0, (start,), ())]
    complete: list[dict[str, Any]] = []
    while queue:
        cost, path, edge_ids = heapq.heappop(queue)
        node = path[-1]
        if node == target:
            complete.append(
                {
                    "source": "classic_bounded_dijkstra",
                    "stateIds": list(path),
                    "transitionIds": list(edge_ids),
                    "pathLength": len(edge_ids),
                    "pathCost": round(cost, 10),
                    "costUnit": "dimensionless_model_cost",
                    "feasible": True,
                }
            )
            continue
        if len(edge_ids) >= maximum_steps:
            continue
        for edge in sorted(outgoing.get(node, ()), key=lambda item: item["id"]):
            next_node = edge["to"]
            if next_node in path:
                continue
            heapq.heappush(
                queue,
                (
                    cost + float(edge["cost"]),
                    (*path, next_node),
                    (*edge_ids, edge["id"]),
                ),
            )
    return sorted(
        complete,
        key=lambda item: (item["pathCost"], item["pathLength"], item["stateIds"]),
    )


def _select_active_subgraph(
    fixture: ProteinDynamicsFixture,
    edges: list[dict[str, Any]],
    maximum_steps: int,
) -> dict[str, Any]:
    start = fixture.preset["start"]
    target = fixture.preset["target"]
    paths = _bounded_paths(edges, start, target, maximum_steps)
    if not paths:
        raise ValueError("complete protein network has no bounded start-to-target path")
    limit = int(fixture.domain["selection"]["maximumActiveNodes"])
    selected = set(paths[0]["stateIds"])
    if len(selected) > limit:
        raise ValueError("connectivity-preserving path exceeds the active-node limit")
    nodes_by_id = {item["id"]: item for item in fixture.domain["nodes"]}
    while len(selected) < limit:
        candidates = []
        selected_basins = {nodes_by_id[item]["basin"] for item in selected}
        for node_id, node in nodes_by_id.items():
            if node_id in selected:
                continue
            coverage = sum(node_id in path["stateIds"] for path in paths[:8])
            diversity = int(node["basin"] not in selected_basins)
            candidates.append((-coverage, -diversity, node_id))
        if not candidates:
            break
        selected.add(min(candidates)[2])
    active_nodes = [item for item in fixture.domain["nodes"] if item["id"] in selected]
    active_edges = [
        item for item in edges if item["from"] in selected and item["to"] in selected
    ]
    active_paths = _bounded_paths(active_edges, start, target, maximum_steps)
    if not active_paths:
        raise ValueError("active protein subgraph removed every feasible path")
    excluded = [
        {
            "id": item["id"],
            "label": item["label"],
            "basin": item["basin"],
            "reason": "outside_connectivity_preserving_active_window",
        }
        for item in fixture.domain["nodes"]
        if item["id"] not in selected
    ]
    selection_payload = {
        "ruleVersion": fixture.domain["selection"]["ruleVersion"],
        "lockedPath": paths[0]["stateIds"],
        "activeNodeIds": [item["id"] for item in active_nodes],
        "activeTransitionIds": [item["id"] for item in active_edges],
        "excluded": excluded,
        "completeStateCount": len(fixture.domain["nodes"]),
        "selectedStateCount": len(active_nodes),
        "coverageRate": len(active_nodes) / len(fixture.domain["nodes"]),
        "completePathCount": len(paths),
        "activePathCount": len(active_paths),
        "connectivityPreserved": True,
        "startPreserved": start in selected,
        "targetPreserved": target in selected,
    }
    selection_payload["selectionHash"] = hash_payload(selection_payload)
    return {
        "nodes": active_nodes,
        "edges": active_edges,
        "paths": active_paths,
        "evidence": selection_payload,
    }


def _definition(preset: str, values: dict[str, Any]) -> OptimizationProblemDefinition:
    resolved = protein_dynamics_values(
        preset,
        {
            key: values[key]
            for key in ("maximum_steps", "barrier_weight")
            if key in values
        },
    )
    fixture = load_protein_dynamics_fixture(preset)
    weighted_edges = _weighted_edges(fixture, resolved["barrier_weight"])
    active = _select_active_subgraph(fixture, weighted_edges, resolved["maximum_steps"])
    start = resolved["start_state"]
    target = resolved["target_state"]
    choices = tuple(
        sorted(item["id"] for item in active["nodes"] if item["id"] != start)
    )
    slot_variables = tuple(
        tuple(f"slot.{slot}.{node_id}" for node_id in choices)
        for slot in range(resolved["maximum_steps"])
    )
    variables = tuple(variable for slot in slot_variables for variable in slot)
    penalties = fixture.domain["penalties"]
    edge_by_pair = {(item["from"], item["to"]): item for item in active["edges"]}
    builder = QuboBuilder(variables)

    for slot, slot_items in enumerate(slot_variables):
        builder.add_squared_equality(
            {variable: 1.0 for variable in slot_items},
            rhs=1.0,
            penalty=float(penalties["oneHot"]),
            contribution_id_prefix=f"slot-one-hot:{slot}",
            group_id="path_continuity",
            source_rule="exactly_one_state_per_time_slice",
        )

    for node_id, variable in zip(choices, slot_variables[0]):
        edge = edge_by_pair.get((start, node_id))
        if edge is None:
            builder.add_linear(
                variable,
                float(penalties["invalidTransition"]),
                contribution_id=f"start-invalid:{node_id}",
                group_id="start_endpoint",
                source_rule="first_slice_must_follow_start_state",
                role="constraint",
            )
        else:
            builder.add_linear(
                variable,
                float(edge["cost"]),
                contribution_id=f"start-cost:{edge['id']}",
                group_id="path_cost",
                source_rule=str(edge["sourceMethod"]),
                role="objective",
            )

    for slot in range(len(slot_variables) - 1):
        for left_node, left_variable in zip(choices, slot_variables[slot]):
            for right_node, right_variable in zip(choices, slot_variables[slot + 1]):
                edge = edge_by_pair.get((left_node, right_node))
                if left_node == target and right_node == target:
                    continue
                if edge is None:
                    builder.add_quadratic(
                        left_variable,
                        right_variable,
                        float(penalties["invalidTransition"]),
                        contribution_id=(
                            f"flow-invalid:{slot}:{left_node}:{right_node}"
                        ),
                        group_id="flow_conservation",
                        source_rule="adjacent_slices_require_allowed_direct_transition",
                        role="constraint",
                    )
                else:
                    builder.add_quadratic(
                        left_variable,
                        right_variable,
                        float(edge["cost"]),
                        contribution_id=f"transition-cost:{slot}:{edge['id']}",
                        group_id="path_cost",
                        source_rule=str(edge["sourceMethod"]),
                        role="objective",
                    )

    target_variable = f"slot.{resolved['maximum_steps'] - 1}.{target}"
    builder.add_squared_equality(
        {target_variable: 1.0},
        rhs=1.0,
        penalty=float(penalties["endpoint"]),
        contribution_id_prefix="target-endpoint",
        group_id="target_endpoint",
        source_rule="last_slice_is_target_state",
    )

    intermediate_choices = [item for item in choices if item != target]
    for node_id in intermediate_choices:
        for left_slot in range(len(slot_variables)):
            for right_slot in range(left_slot + 1, len(slot_variables)):
                builder.add_quadratic(
                    f"slot.{left_slot}.{node_id}",
                    f"slot.{right_slot}.{node_id}",
                    float(penalties["repeatedState"]),
                    contribution_id=f"cycle:{node_id}:{left_slot}:{right_slot}",
                    group_id="cycle_prohibition",
                    source_rule="non_target_state_may_appear_at_most_once",
                    role="constraint",
                )

    problem = builder.build(
        problem_id=f"biomedicine.protein-path.{fixture.manifest['dataset_id']}.{preset}",
        metadata={
            "preset": preset,
            "maximum_steps": resolved["maximum_steps"],
            "barrier_weight": resolved["barrier_weight"],
            "weight_profile": resolved["weight_profile"],
        },
    )
    return OptimizationProblemDefinition(
        case_id="protein_dynamics",
        title="蛋白构象状态网络离散转变路径",
        problem_kind="qubo",
        problem=problem,
        business_variables=variables,
        term_groups=(
            TermGroup("path_cost", "离散转变路径代价", "objective", variables),
            TermGroup("start_endpoint", "起点后继约束", "global_constraint", variables),
            TermGroup(
                "target_endpoint", "终点固定约束", "global_constraint", variables
            ),
            TermGroup(
                "path_continuity", "时间片单态连续约束", "global_constraint", variables
            ),
            TermGroup(
                "flow_conservation", "相邻时间片允许转移约束", "dependency", variables
            ),
            TermGroup(
                "cycle_prohibition",
                "重复状态与回路禁止",
                "pairwise_conflict",
                variables,
            ),
            TermGroup(
                "maximum_path_length",
                "有限时间片最大路径长度",
                "global_constraint",
                variables,
            ),
        ),
        coefficient_contributions=builder.contributions,
        metadata={
            "fixture": fixture,
            "values": resolved,
            "weighted_edges": weighted_edges,
            "active": active,
            "choices": choices,
            "slot_variables": slot_variables,
        },
    )


def _path_overlap(left: list[str], right: list[str]) -> float:
    left_edges = set(zip(left, left[1:]))
    right_edges = set(zip(right, right[1:]))
    union = left_edges | right_edges
    return len(left_edges & right_edges) / max(1, len(union))


def _decode(
    bitstring: str,
    definition: OptimizationProblemDefinition,
    *,
    source: str,
) -> dict[str, Any]:
    bit_by_variable = dict(zip(definition.problem.variables, bitstring))
    choices: tuple[str, ...] = definition.metadata["choices"]
    slot_variables: tuple[tuple[str, ...], ...] = definition.metadata["slot_variables"]
    selected_by_slot = [
        [
            node_id
            for node_id, variable in zip(choices, variables)
            if bit_by_variable[variable] == "1"
        ]
        for variables in slot_variables
    ]
    one_hot_ok = all(len(items) == 1 for items in selected_by_slot)
    selected_states = [items[0] for items in selected_by_slot if len(items) == 1]
    values = definition.metadata["values"]
    start = values["start_state"]
    target = values["target_state"]
    sequence = [start, *selected_states]
    first_target = next(
        (index for index, item in enumerate(sequence) if item == target), None
    )
    if first_target is None:
        path = sequence
        target_absorbing = False
    else:
        path = sequence[: first_target + 1]
        target_absorbing = all(item == target for item in sequence[first_target:])
    edge_by_pair = {
        (item["from"], item["to"]): item
        for item in definition.metadata["active"]["edges"]
    }
    path_pairs = list(zip(path, path[1:]))
    transitions_allowed = all(pair in edge_by_pair for pair in path_pairs)
    repeated = len(path) != len(set(path))
    starts_correctly = bool(path) and path[0] == start
    reaches_target = bool(path) and path[-1] == target and target_absorbing
    maximum_steps_ok = len(path_pairs) <= values["maximum_steps"]
    feasible = all(
        (
            one_hot_ok,
            starts_correctly,
            reaches_target,
            transitions_allowed,
            not repeated,
            maximum_steps_ok,
        )
    )
    transition_ids = [
        edge_by_pair[pair]["id"] for pair in path_pairs if pair in edge_by_pair
    ]
    path_cost = (
        round(sum(float(edge_by_pair[pair]["cost"]) for pair in path_pairs), 10)
        if transitions_allowed
        else None
    )
    classic_path = definition.metadata["active"]["paths"][0]["stateIds"]
    failures = []
    checks = (
        ("start_endpoint", starts_correctly),
        ("target_endpoint", reaches_target),
        ("flow_conservation", transitions_allowed),
        ("path_continuity", one_hot_ok and target_absorbing),
        ("cycle_prohibition", not repeated),
        ("maximum_path_length", maximum_steps_ok),
    )
    for check_id, passed in checks:
        if not passed:
            failures.append(check_id)
    return {
        "source": source,
        "bitstring": bitstring,
        "stateIds": path,
        "transitionIds": transition_ids,
        "pathLength": len(path_pairs),
        "pathCost": path_cost,
        "costUnit": "dimensionless_model_cost",
        "modelObjective": round(
            evaluate_qubo_bitstring(definition.problem, bitstring), 10
        ),
        "feasible": feasible,
        "pathOverlap": _path_overlap(path, classic_path) if feasible else 0.0,
        "failureReasons": failures,
        "checks": [{"id": check_id, "passed": passed} for check_id, passed in checks],
    }


def _classic_path_payload(
    definition: OptimizationProblemDefinition, *, active: bool
) -> dict[str, Any]:
    values = definition.metadata["values"]
    edges = (
        definition.metadata["active"]["edges"]
        if active
        else definition.metadata["weighted_edges"]
    )
    paths = _bounded_paths(
        edges,
        values["start_state"],
        values["target_state"],
        values["maximum_steps"],
    )
    if not paths:
        return {
            "source": "classic_bounded_dijkstra",
            "stateIds": [],
            "transitionIds": [],
            "pathLength": 0,
            "pathCost": None,
            "costUnit": "dimensionless_model_cost",
            "feasible": False,
            "scope": "active_subgraph" if active else "complete_network",
        }
    return {
        **paths[0],
        "scope": "active_subgraph" if active else "complete_network",
    }


def _ledger(definition: OptimizationProblemDefinition) -> dict[str, Any]:
    return {
        "balanced": True,
        "contributionCount": len(definition.coefficient_contributions),
        "canonicalTermCount": 1
        + len(definition.problem.linear_terms)
        + len(definition.problem.quadratic_terms),
        "rows": [
            {
                "contributionId": item.contribution_id,
                "groupId": item.group_id,
                "sourceRule": item.source_rule,
                "role": item.role,
                "termKind": item.term_kind,
                "targets": list(item.targets),
                "coefficient": item.coefficient,
                "canonicalTermId": item.canonical_term_id,
            }
            for item in definition.coefficient_contributions
        ],
    }


def analyze_protein_dynamics(preset: str, values: dict[str, Any]) -> dict[str, Any]:
    resolved = protein_dynamics_values(
        preset,
        {
            key: values[key]
            for key in ("maximum_steps", "barrier_weight")
            if key in values
        },
    )
    fixture = load_protein_dynamics_fixture(preset)
    definition = _definition(preset, resolved)
    active = definition.metadata["active"]
    weighted_edges = definition.metadata["weighted_edges"]
    complete_network_hash = hash_payload(
        {"nodes": fixture.domain["nodes"], "transitions": weighted_edges}
    )
    payload = {
        "kind": "biomedicine",
        "caseId": "protein_dynamics",
        "executionFamily": "problem",
        "implementationStatus": "available",
        "dataset": {
            "id": fixture.manifest["dataset_id"],
            "version": fixture.manifest["version"],
            "manifestHash": fixture.manifest_hash,
            "sourceKind": fixture.manifest["source"]["kind"],
            "sourceUri": fixture.manifest["source"]["uri"],
            "license": fixture.manifest["source"]["license"],
            "licenseCheckedAt": fixture.manifest["source"]["license_checked_at"],
            "allowedClaims": fixture.manifest["allowed_claims"],
            "limitations": fixture.manifest["limitations"],
        },
        "problem": {
            "id": definition.problem.problem_id,
            "type": "qubo",
            "hash": definition.problem.stable_hash(),
            "completeDomainProblemHash": complete_network_hash,
            "quantumSubproblemHash": definition.problem.stable_hash(),
            "selectionHash": active["evidence"]["selectionHash"],
            "variables": list(definition.problem.variables),
            "terms": [
                {
                    "id": f"linear.{variable}",
                    "operator": "linear",
                    "targets": [variable],
                    "coefficient": coefficient,
                }
                for variable, coefficient in definition.problem.linear_terms
            ]
            + [
                {
                    "id": f"quadratic.{left}.{right}",
                    "operator": "quadratic",
                    "targets": [left, right],
                    "coefficient": coefficient,
                }
                for left, right, coefficient in definition.problem.quadratic_terms
            ],
            "termGroups": [vars(group) for group in definition.term_groups],
            "coefficientLedger": _ledger(definition),
        },
        "resource": {
            "logical_variables": len(definition.problem.variables),
            "completeStates": len(fixture.domain["nodes"]),
            "activeStates": len(active["nodes"]),
            "completeTransitions": len(weighted_edges),
            "activeTransitions": len(active["edges"]),
            "maximumSteps": resolved["maximum_steps"],
        },
        "decision": {
            "recommendedMode": "digital",
            "reason": "时间片单态、允许转移、终点和禁止回路形成通用路径 QUBO。",
            "modes": [
                {
                    "mode": "digital",
                    "algorithm": "qaoa",
                    "availableAlgorithms": ["qaoa"],
                    "status": "recommended",
                    "reason": "完整路径约束进入 Digital QAOA。",
                },
                {
                    "mode": "hybrid",
                    "algorithm": "qaoa",
                    "availableAlgorithms": ["qaoa"],
                    "status": "unsuitable",
                    "reason": "构象网络没有经验证的 Rydberg 几何。",
                },
                {
                    "mode": "analog",
                    "algorithm": "qaa",
                    "availableAlgorithms": ["qaa"],
                    "status": "unsuitable",
                    "reason": "原生 Analog 不完整表达路径流守恒与时间片约束。",
                },
            ],
        },
        "domain": {
            "kind": "protein_dynamics",
            "modelLevel": fixture.domain["modelLevel"],
            "proteinLabel": fixture.domain["proteinLabel"],
            "preset": preset,
            "startState": resolved["start_state"],
            "targetState": resolved["target_state"],
            "maximumSteps": resolved["maximum_steps"],
            "barrierWeight": resolved["barrier_weight"],
            "weightProfile": resolved["weight_profile"],
            "edgeWeight": fixture.domain["edgeWeight"],
            "nodes": fixture.domain["nodes"],
            "edges": weighted_edges,
            "stateNodes": fixture.domain["nodes"],
            "transitions": weighted_edges,
            "activeNodes": active["nodes"],
            "activeEdges": active["edges"],
            "subproblemSelection": active["evidence"],
            "classicShortestPath": _classic_path_payload(definition, active=False),
            "classicActivePath": _classic_path_payload(definition, active=True),
            "referencePath": {
                "source": "fixture_reference_path",
                "stateIds": fixture.preset["referencePath"],
                "interpretation": (
                    "versioned teaching reference; not a kinetic trajectory"
                ),
            },
            "constraintEncoding": [
                {
                    "id": "start_endpoint",
                    "encoding": "implicit fixed start plus first-slice transition gate",
                },
                {
                    "id": "target_endpoint",
                    "encoding": "last time slice fixed to target",
                },
                {
                    "id": "flow_conservation",
                    "encoding": (
                        "adjacent slices permit only declared directed transitions"
                    ),
                },
                {
                    "id": "path_continuity",
                    "encoding": (
                        "exactly one state per time slice; target is absorbing padding"
                    ),
                },
                {
                    "id": "cycle_prohibition",
                    "encoding": "non-target state repeat penalties",
                },
                {"id": "maximum_path_length", "encoding": "finite time-slice horizon"},
            ],
            "limitations": fixture.manifest["limitations"],
        },
    }
    payload["analysisHash"] = hash_payload(payload)
    return payload


def run_protein_dynamics(
    *,
    preset: str,
    values: dict[str, Any],
    shots: int,
    seed: int,
    layers: int,
    parameter_budget: int,
    optimizer_starts: int,
) -> dict[str, Any]:
    if layers != 1:
        raise ValueError("蛋白路径首个已校准模型只支持一层 Digital QAOA。")
    resolved = protein_dynamics_values(
        preset,
        {
            key: values[key]
            for key in ("maximum_steps", "barrier_weight")
            if key in values
        },
    )
    fixture = load_protein_dynamics_fixture(preset)
    definition = _definition(preset, resolved)
    qaoa = QAOA(definition.problem, layers=layers)
    started = time.perf_counter()
    result = qaoa.run(
        optimizer=OptimizerConfig(
            method="COBYLA",
            max_iterations=parameter_budget,
            max_evaluations=parameter_budget,
            starts=optimizer_starts,
            seed=seed,
        ),
        final_shots=shots,
    )
    counts = dict(result.final_result.counts) if result.final_result else {}
    observed = [
        _decode(state, definition, source="quantum_observed") | {"count": count}
        for state, count in counts.items()
    ]
    feasible = sorted(
        (item for item in observed if item["feasible"]),
        key=lambda item: (item["pathCost"], -item["count"], item["bitstring"]),
    )
    quantum_candidate = feasible[0] if feasible else None
    feasible_shots = sum(item["count"] for item in feasible)
    failure_counts: dict[str, int] = {}
    for item in observed:
        if item["feasible"]:
            continue
        for reason in item["failureReasons"]:
            failure_counts[reason] = failure_counts.get(reason, 0) + item["count"]
    classic_shortest = _classic_path_payload(definition, active=False)
    classic_active = _classic_path_payload(definition, active=True)
    best = result.evaluations[result.best_evaluation_index]
    circuit = (
        qaoa.build_circuit()
        .bind(best.parameter_bind.values)
        .to_program()
        .to_dict()["circuit"]
    )
    analysis = analyze_protein_dynamics(
        preset,
        {
            "maximum_steps": resolved["maximum_steps"],
            "barrier_weight": resolved["barrier_weight"],
        },
    )
    payload = {
        "kind": "biomedicine",
        "analysis": analysis,
        "domain": {
            "kind": "protein_dynamics_result",
            "quantumStatus": "observed_feasible"
            if quantum_candidate
            else "quantum_not_observed",
            "quantumCandidate": quantum_candidate,
            "topObservedFeasible": feasible[:8],
            "observedFeasibleCount": len(feasible),
            "observedFeasibleRate": feasible_shots / max(1, shots),
            "classicShortestPath": classic_shortest,
            "classicActivePath": classic_active,
            "failureReasons": [
                {"id": key, "shotCount": value}
                for key, value in sorted(
                    failure_counts.items(), key=lambda item: (-item[1], item[0])
                )
            ],
            "interpretation": (
                "pathCost 是版本化状态网络中的无量纲离散模型代价，不表示真实时间、"
                "速率、驻留时间或蛋白分子动力学轨迹。"
                "QAOA counts 仅表示有限 shots 观测频次。"
            ),
        },
        "quantum": {
            "kind": "problem_qaoa",
            "mode": "digital",
            "algorithm": "qaoa",
            "summary": {
                "qubits": len(definition.problem.variables),
                "shots": shots,
                "evaluations": len(result.evaluations),
                "feasibleObserved": len(feasible),
            },
            "circuit": {
                "qubits": list(circuit["qubits"]),
                "gates": [
                    {
                        "depth": index,
                        "name": str(gate["name"]).upper(),
                        "targets": list(gate.get("targets", ())),
                        "controls": list(gate.get("controls", ())),
                        "parameters": gate.get("parameters", {}),
                    }
                    for index, gate in enumerate(circuit["gates"])
                ],
                "depth": len(circuit["gates"]),
            },
            "counts": [
                {"state": state, "count": count, "rank": index + 1}
                for index, (state, count) in enumerate(
                    sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:12]
                )
            ],
            "parameterHistory": [
                {
                    "index": index,
                    "objective": float(item.energy),
                    "parameters": dict(item.parameter_bind.values),
                    "selected": index == result.best_evaluation_index,
                }
                for index, item in enumerate(result.evaluations)
            ],
        },
        "audit": {
            "domainId": "biomedicine",
            "caseId": "protein_dynamics",
            "datasetId": fixture.manifest["dataset_id"],
            "datasetVersion": fixture.manifest["version"],
            "manifestHash": fixture.manifest_hash,
            "domainInputHash": hash_payload(
                {
                    "preset": preset,
                    "values": resolved,
                    "manifestHash": fixture.manifest_hash,
                }
            ),
            "conformationSetHash": hash_payload(fixture.domain["nodes"]),
            "transitionNetworkHash": analysis["problem"]["completeDomainProblemHash"],
            "selectionHash": analysis["problem"]["selectionHash"],
            "pathQuboHash": definition.problem.stable_hash(),
            "problemHash": definition.problem.stable_hash(),
            "hamiltonianHash": qaoa.hamiltonian.stable_hash(),
            "analysisHash": analysis["analysisHash"],
            "ansatzHash": result.ansatz.stable_hash(),
            "compileHash": result.ansatz.stable_hash(),
            "backend": local_backend_context(
                execution_family="problem_qaoa",
                mode="digital",
                simulation_method="state_vector",
            ),
            "executionHash": result.stable_hash(),
            "seed": seed,
            "shots": shots,
            "hardwareExecution": False,
            "cloudExecution": False,
            "networkAccessed": False,
            "wallTimeSeconds": time.perf_counter() - started,
            "optimalityClaim": "not_claimed",
            "claimBoundary": "finite_versioned_conformation_state_network",
        },
    }
    finalize_stable_audit(
        payload["audit"],
        configuration={
            "preset": preset,
            "values": resolved,
            "problemHash": definition.problem.stable_hash(),
            "hamiltonianHash": qaoa.hamiltonian.stable_hash(),
            "ansatzHash": result.ansatz.stable_hash(),
            "layers": layers,
            "shots": shots,
            "seed": seed,
            "optimizer": {
                "method": "COBYLA",
                "parameterBudget": parameter_budget,
                "starts": optimizer_starts,
            },
        },
        outcome={
            "domain": payload["domain"],
            "counts": payload["quantum"]["counts"],
            "parameterHistory": payload["quantum"]["parameterHistory"],
        },
    )
    payload["audit"]["resultHash"] = hash_payload(payload)
    return payload


def scenario_payload() -> dict[str, Any]:
    return BIOMEDICINE_SCENARIO_SPECS["protein_dynamics"].to_dict()
