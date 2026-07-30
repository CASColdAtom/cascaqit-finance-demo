"""Versioned short-RNA candidate-pair QUBO and Digital QAOA execution."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from functools import cache
from itertools import product
from pathlib import Path
from typing import Any

from cascaqit.algorithms import QAOA, OptimizerConfig

from cascaqit_biomedicine_demo.catalog import BIOMEDICINE_SCENARIO_SPECS
from cascaqit_biomedicine_demo.fixtures import validate_manifest_contract
from cascaqit_biomedicine_demo.pauli_vqe import hash_payload
from cascaqit_industry_demo.audit import (
    finalize_stable_audit,
    local_backend_context,
)
from cascaqit_industry_demo.problem_model import (
    OptimizationProblemDefinition,
    QuboBuilder,
    TermGroup,
)

DATA_ROOT = Path(__file__).resolve().parent / "data" / "rna_structure"
_FIXTURE_ROOT = DATA_ROOT / "short_rna_pairing" / "1"
_PRESETS = {"hairpin_reference", "stem_competition", "limited_pseudoknot"}
_PAIR_TYPES = {"AU", "UA", "CG", "GC", "GU", "UG"}
_BRACKETS = (("(", ")"), ("[", "]"), ("{", "}"), ("<", ">"))


@dataclass(frozen=True)
class RNAFixture:
    manifest: dict[str, Any]
    domain: dict[str, Any]
    preset: dict[str, Any]
    manifest_hash: str


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"RNA fixture must contain an object: {path.name}")
    return value, raw


def _crosses(left: dict[str, Any], right: dict[str, Any]) -> bool:
    i, j = int(left["left"]), int(left["right"])
    k, right_endpoint = int(right["left"]), int(right["right"])
    return i < k < j < right_endpoint or k < i < right_endpoint < j


def _normalized_pair_ids(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def _validate_preset(preset_id: str, preset: dict[str, Any]) -> None:
    sequence = preset.get("sequence")
    if not isinstance(sequence, str) or not sequence or set(sequence) - set("ACGU"):
        raise ValueError(f"RNA preset {preset_id} has an invalid sequence")
    minimum_loop = preset.get("minimumLoop")
    if not isinstance(minimum_loop, int) or minimum_loop < 3:
        raise ValueError(f"RNA preset {preset_id} has an invalid minimum loop")
    candidates = preset.get("candidatePairs")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError(f"RNA preset {preset_id} has no candidate pairs")
    identifiers: set[str] = set()
    positions: set[tuple[int, int]] = set()
    for candidate in candidates:
        pair_id = candidate.get("id")
        left = candidate.get("left")
        right = candidate.get("right")
        if not isinstance(pair_id, str) or not pair_id or pair_id in identifiers:
            raise ValueError(f"RNA preset {preset_id} has duplicate pair IDs")
        if (
            not isinstance(left, int)
            or not isinstance(right, int)
            or left < 1
            or right > len(sequence)
            or right - left - 1 < minimum_loop
        ):
            raise ValueError(f"RNA candidate {pair_id} has invalid positions")
        if (left, right) in positions:
            raise ValueError(f"RNA preset {preset_id} repeats candidate positions")
        pair_type = f"{sequence[left - 1]}{sequence[right - 1]}"
        if pair_type != candidate.get("pairType") or pair_type not in _PAIR_TYPES:
            raise ValueError(f"RNA candidate {pair_id} has an invalid pair type")
        if pair_type in {"GU", "UG"} and not preset.get("allowWobble"):
            raise ValueError(f"RNA candidate {pair_id} uses undeclared G-U wobble")
        if not isinstance(candidate.get("score"), (int, float)):
            raise ValueError(f"RNA candidate {pair_id} has no numeric score")
        identifiers.add(pair_id)
        positions.add((left, right))

    allowed_crossings = {
        _normalized_pair_ids(*item) for item in preset.get("allowedCrossings", [])
    }
    by_id = {item["id"]: item for item in candidates}
    for left_id, right_id in allowed_crossings:
        if {left_id, right_id} - identifiers:
            raise ValueError("RNA allowed crossing references an unknown pair")
        if not _crosses(by_id[left_id], by_id[right_id]):
            raise ValueError("RNA allowed crossing does not geometrically cross")
    if preset.get("pseudoknotPolicy") == "forbidden" and allowed_crossings:
        raise ValueError("pseudoknot-free RNA preset declares allowed crossings")

    reference = preset.get("reference")
    if not isinstance(reference, dict):
        raise ValueError(f"RNA preset {preset_id} has no reference structure")
    reference_ids = reference.get("pairIds")
    if (
        not isinstance(reference_ids, list)
        or len(reference_ids) != len(set(reference_ids))
        or set(reference_ids) - identifiers
    ):
        raise ValueError("RNA reference structure contains unknown pairs")
    dot_bracket = reference.get("dotBracket")
    if not isinstance(dot_bracket, str) or len(dot_bracket) != len(sequence):
        raise ValueError("RNA reference dot-bracket length is inconsistent")
    selected = [by_id[pair_id] for pair_id in reference_ids]
    occupied: set[int] = set()
    for candidate in selected:
        positions = {int(candidate["left"]), int(candidate["right"])}
        if occupied & positions:
            raise ValueError("RNA reference structure pairs one nucleotide twice")
        occupied.update(positions)
    for index, left in enumerate(selected):
        for right in selected[index + 1 :]:
            if (
                _crosses(left, right)
                and _normalized_pair_ids(left["id"], right["id"])
                not in allowed_crossings
            ):
                raise ValueError("RNA reference structure violates pseudoknot policy")
    if _dot_bracket(len(sequence), selected) != dot_bracket:
        raise ValueError("RNA reference dot-bracket does not match reference pairs")


def load_rna_fixture(preset: str | None = None) -> RNAFixture:
    selected = preset or "hairpin_reference"
    if selected not in _PRESETS:
        raise ValueError(f"unknown RNA preset: {selected}")
    manifest, manifest_raw = _read_json(_FIXTURE_ROOT / "manifest.json")
    validate_manifest_contract(manifest)
    domain, domain_raw = _read_json(_FIXTURE_ROOT / "domain.json")
    artifacts = manifest.get("artifacts", [])
    if len(artifacts) != 1 or artifacts[0].get("path") != "domain.json":
        raise ValueError("RNA fixture artifact declaration is incomplete")
    if hashlib.sha256(domain_raw).hexdigest() != artifacts[0].get("sha256"):
        raise ValueError("RNA fixture checksum mismatch: domain.json")
    presets = domain.get("presets")
    if not isinstance(presets, dict) or set(presets) != _PRESETS:
        raise ValueError("RNA fixture preset registry is inconsistent")
    for preset_id, value in presets.items():
        _validate_preset(preset_id, value)
    default_order = sorted(
        item["id"] for item in presets["hairpin_reference"]["candidatePairs"]
    )
    if manifest.get("variable_order") != default_order:
        raise ValueError("RNA fixture variable order is inconsistent")
    return RNAFixture(
        manifest=manifest,
        domain=domain,
        preset=presets[selected],
        manifest_hash=hashlib.sha256(manifest_raw).hexdigest(),
    )


def rna_values(preset: str, overrides: dict[str, Any]) -> dict[str, Any]:
    fixture = load_rna_fixture(preset)
    unknown = set(overrides) - {"minimum_loop", "sequence"}
    if unknown:
        raise ValueError(f"unknown RNA control values: {', '.join(sorted(unknown))}")
    sequence = str(overrides.get("sequence", fixture.preset["sequence"]))
    if sequence != fixture.preset["sequence"]:
        raise ValueError("RNA sequence is fixed by the selected versioned preset")
    raw_loop = overrides.get("minimum_loop", fixture.preset["minimumLoop"])
    if isinstance(raw_loop, bool) or not isinstance(raw_loop, (int, float)):
        raise ValueError("minimum_loop must be an integer")
    minimum_loop = int(raw_loop)
    if minimum_loop != raw_loop or not 3 <= minimum_loop <= 6:
        raise ValueError("minimum_loop must be an integer between 3 and 6")
    return {"sequence": sequence, "minimum_loop": minimum_loop}


def _active_candidates(fixture: RNAFixture, minimum_loop: int) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in fixture.preset["candidatePairs"]
        if int(item["right"]) - int(item["left"]) - 1 >= minimum_loop
    ]


def _candidate_relations(
    fixture: RNAFixture, candidates: list[dict[str, Any]]
) -> tuple[
    tuple[tuple[str, str], ...],
    tuple[tuple[str, str], ...],
    tuple[tuple[str, str], ...],
]:
    shared: list[tuple[str, str]] = []
    crossing: list[tuple[str, str]] = []
    stacking: list[tuple[str, str]] = []
    allowed = {
        _normalized_pair_ids(*item)
        for item in fixture.preset.get("allowedCrossings", [])
    }
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            pair_ids = _normalized_pair_ids(left["id"], right["id"])
            left_positions = {int(left["left"]), int(left["right"])}
            right_positions = {int(right["left"]), int(right["right"])}
            if left_positions & right_positions:
                shared.append(pair_ids)
                continue
            if _crosses(left, right) and pair_ids not in allowed:
                crossing.append(pair_ids)
                continue
            if (
                int(left["left"]) + 1 == int(right["left"])
                and int(left["right"]) - 1 == int(right["right"])
            ) or (
                int(right["left"]) + 1 == int(left["left"])
                and int(right["right"]) - 1 == int(left["right"])
            ):
                stacking.append(pair_ids)
    return tuple(sorted(shared)), tuple(sorted(crossing)), tuple(sorted(stacking))


def _definition(preset: str, values: dict[str, Any]) -> OptimizationProblemDefinition:
    resolved = rna_values(preset, values)
    fixture = load_rna_fixture(preset)
    candidates = _active_candidates(fixture, resolved["minimum_loop"])
    variables = tuple(item["id"] for item in candidates)
    shared, crossing, stacking = _candidate_relations(fixture, candidates)
    energy_model = fixture.domain["energyModel"]
    unpaired_penalty = float(energy_model["unpairedPenalty"])
    stacking_bonus = float(energy_model["stackingBonus"])
    hard_penalty = float(energy_model["hardPenalty"])
    builder = QuboBuilder(variables)
    for candidate in candidates:
        variable = candidate["id"]
        builder.add_linear(
            variable,
            float(candidate["score"]),
            contribution_id=f"pair-energy:{variable}",
            group_id="pair_energy",
            source_rule=str(candidate["sourceRule"]),
            role="objective",
        )
        builder.add_linear(
            variable,
            -2.0 * unpaired_penalty,
            contribution_id=f"unpaired:{variable}",
            group_id="unpaired_penalty",
            source_rule="two_nucleotides_leave_unpaired_pool",
            role="objective",
        )
    for left, right in stacking:
        builder.add_quadratic(
            left,
            right,
            stacking_bonus,
            contribution_id=f"stack:{left}:{right}",
            group_id="stacking_bonus",
            source_rule="adjacent_nested_pair_stack",
            role="objective",
        )
    for group_id, pairs, source_rule in (
        ("nucleotide_exclusivity", shared, "one_pair_per_nucleotide"),
        ("pseudoknot_policy", crossing, "undeclared_crossing_forbidden"),
    ):
        for left, right in pairs:
            builder.add_quadratic(
                left,
                right,
                hard_penalty,
                contribution_id=f"{group_id}:{left}:{right}",
                group_id=group_id,
                source_rule=source_rule,
                role="constraint",
            )
    problem = builder.build(
        problem_id=f"biomedicine.rna.{fixture.manifest['dataset_id']}.{preset}",
        metadata={
            "preset": preset,
            "sequence": resolved["sequence"],
            "minimum_loop": resolved["minimum_loop"],
        },
    )
    return OptimizationProblemDefinition(
        case_id="rna_structure",
        title="RNA 二级结构集合与折叠路径",
        problem_kind="qubo",
        problem=problem,
        business_variables=variables,
        term_groups=(
            TermGroup("pair_energy", "候选碱基配对收益", "objective", variables),
            TermGroup("unpaired_penalty", "未配对核苷酸代价", "objective", variables),
            TermGroup("stacking_bonus", "相邻堆叠收益", "objective", pairs=stacking),
            TermGroup(
                "nucleotide_exclusivity",
                "单核苷酸配对互斥",
                "pairwise_conflict",
                pairs=shared,
            ),
            TermGroup(
                "pseudoknot_policy",
                "未声明交叉配对约束",
                "pairwise_conflict",
                pairs=crossing,
            ),
        ),
        coefficient_contributions=builder.contributions,
        metadata={
            "fixture": fixture,
            "values": resolved,
            "candidates": candidates,
            "shared": shared,
            "crossing": crossing,
            "stacking": stacking,
        },
    )


def _dot_bracket(sequence_length: int, selected: list[dict[str, Any]]) -> str:
    characters = ["."] * sequence_length
    layers: list[list[dict[str, Any]]] = []
    for candidate in sorted(selected, key=lambda item: (item["left"], -item["right"])):
        layer_index = next(
            (
                index
                for index, layer in enumerate(layers)
                if not any(_crosses(candidate, existing) for existing in layer)
            ),
            len(layers),
        )
        if layer_index == len(layers):
            layers.append([])
        layers[layer_index].append(candidate)
        opening, closing = _BRACKETS[min(layer_index, len(_BRACKETS) - 1)]
        characters[int(candidate["left"]) - 1] = opening
        characters[int(candidate["right"]) - 1] = closing
    return "".join(characters)


def _decode(
    bitstring: str,
    definition: OptimizationProblemDefinition,
    *,
    source: str,
) -> dict[str, Any]:
    candidates = definition.metadata["candidates"]
    by_id = {item["id"]: item for item in candidates}
    selected_ids = [
        variable
        for variable, bit in zip(definition.problem.variables, bitstring)
        if bit == "1"
    ]
    selected = [by_id[item] for item in selected_ids]
    shared = set(definition.metadata["shared"])
    crossing = set(definition.metadata["crossing"])
    selected_pairs = {
        _normalized_pair_ids(left, right)
        for index, left in enumerate(selected_ids)
        for right in selected_ids[index + 1 :]
    }
    shared_violations = sorted(selected_pairs & shared)
    crossing_violations = sorted(selected_pairs & crossing)
    feasible = not shared_violations and not crossing_violations
    fixture: RNAFixture = definition.metadata["fixture"]
    energy_model = fixture.domain["energyModel"]
    stacking = set(definition.metadata["stacking"])
    selected_stacks = selected_pairs & stacking
    unpaired_count = len(definition.metadata["values"]["sequence"]) - 2 * len(
        selected_ids
    )
    energy = (
        sum(float(item["score"]) for item in selected)
        + float(energy_model["unpairedPenalty"]) * unpaired_count
        + float(energy_model["stackingBonus"]) * len(selected_stacks)
    )
    reference_ids = set(fixture.preset["reference"]["pairIds"])
    overlap = len(set(selected_ids) & reference_ids)
    return {
        "source": source,
        "bitstring": bitstring,
        "pairIds": selected_ids,
        "pairs": selected,
        "pairCount": len(selected_ids),
        "unpairedCount": unpaired_count,
        "dotBracket": _dot_bracket(
            len(definition.metadata["values"]["sequence"]), selected
        ),
        "energy": round(energy, 10),
        "feasible": feasible,
        "referenceOverlap": overlap,
        "referenceOverlapRate": overlap / max(1, len(reference_ids)),
        "checks": [
            {
                "id": "one_pair_per_nucleotide",
                "passed": not shared_violations,
                "violations": [list(item) for item in shared_violations],
            },
            {
                "id": "pseudoknot_policy",
                "passed": not crossing_violations,
                "violations": [list(item) for item in crossing_violations],
            },
            {
                "id": "minimum_loop",
                "passed": True,
                "violations": [],
            },
        ],
    }


def _classic_exact(definition: OptimizationProblemDefinition) -> dict[str, Any]:
    candidates = [
        _decode("".join(bits), definition, source="classic_exact_enumeration")
        for bits in product("01", repeat=len(definition.problem.variables))
    ]
    feasible = [item for item in candidates if item["feasible"]]
    return min(
        feasible,
        key=lambda item: (item["energy"], -item["pairCount"], item["bitstring"]),
    )


def _classic_dynamic_programming(
    definition: OptimizationProblemDefinition,
) -> dict[str, Any]:
    sequence = definition.metadata["values"]["sequence"]
    candidates = definition.metadata["candidates"]
    by_left: dict[int, list[dict[str, Any]]] = {}
    for item in candidates:
        by_left.setdefault(int(item["left"]), []).append(item)
    unpaired_penalty = float(
        definition.metadata["fixture"].domain["energyModel"]["unpairedPenalty"]
    )

    @cache
    def solve(left: int, right: int) -> tuple[float, tuple[str, ...]]:
        if left > right:
            return 0.0, ()
        tail_energy, tail_ids = solve(left + 1, right)
        best = (unpaired_penalty + tail_energy, tail_ids)
        for candidate in by_left.get(left, []):
            partner = int(candidate["right"])
            if partner > right:
                continue
            inner_energy, inner_ids = solve(left + 1, partner - 1)
            outer_energy, outer_ids = solve(partner + 1, right)
            option = (
                float(candidate["score"]) + inner_energy + outer_energy,
                tuple(sorted((candidate["id"], *inner_ids, *outer_ids))),
            )
            if (option[0], option[1]) < (best[0], best[1]):
                best = option
        return best

    score, pair_ids = solve(1, len(sequence))
    selected = set(pair_ids)
    bitstring = "".join(
        "1" if variable in selected else "0"
        for variable in definition.problem.variables
    )
    result = _decode(bitstring, definition, source="classic_dynamic_programming")
    result["dynamicProgrammingScore"] = round(score, 10)
    result["scope"] = "pseudoknot_free_pair_score_baseline"
    return result


def _reference_structure(
    definition: OptimizationProblemDefinition,
) -> dict[str, Any]:
    fixture: RNAFixture = definition.metadata["fixture"]
    active = set(definition.problem.variables)
    reference_ids = [
        item for item in fixture.preset["reference"]["pairIds"] if item in active
    ]
    bitstring = "".join(
        "1" if variable in reference_ids else "0"
        for variable in definition.problem.variables
    )
    result = _decode(bitstring, definition, source="dataset_reference")
    result.update(
        {
            "kind": fixture.preset["reference"]["kind"],
            "sourceId": fixture.preset["reference"]["sourceId"],
            "sourceUri": fixture.preset["reference"].get("sourceUri"),
            "declaredDotBracket": fixture.preset["reference"]["dotBracket"],
            "completeReferencePairCount": len(fixture.preset["reference"]["pairIds"]),
        }
    )
    return result


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


def analyze_rna_structure(preset: str, values: dict[str, Any]) -> dict[str, Any]:
    resolved = rna_values(preset, values)
    fixture = load_rna_fixture(preset)
    definition = _definition(preset, resolved)
    candidates = definition.metadata["candidates"]
    reference_ids = set(fixture.preset["reference"]["pairIds"])
    sequence_length = len(resolved["sequence"])
    nodes = [
        {
            "id": f"nt.{index + 1}",
            "label": nucleotide,
            "group": "reference_pair"
            if any(
                item["id"] in reference_ids
                and index + 1 in {item["left"], item["right"]}
                for item in candidates
            )
            else "unpaired_or_candidate",
            "role": "nucleotide",
            "x": round(6 + index * 88 / max(1, sequence_length - 1), 4),
            "y": 68,
        }
        for index, nucleotide in enumerate(resolved["sequence"])
    ]
    edges = [
        {
            "source": f"nt.{item['left']}",
            "target": f"nt.{item['right']}",
            "kind": "reference_pair"
            if item["id"] in reference_ids
            else "candidate_pair",
            "score": float(item["score"]),
            "pairId": item["id"],
        }
        for item in candidates
    ]
    selection_hash = hash_payload(
        {
            "preset": preset,
            "minimumLoop": resolved["minimum_loop"],
            "candidateIds": list(definition.problem.variables),
        }
    )
    payload = {
        "kind": "biomedicine",
        "caseId": "rna_structure",
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
            "completeDomainProblemHash": hash_payload(fixture.preset["candidatePairs"]),
            "quantumSubproblemHash": definition.problem.stable_hash(),
            "selectionHash": selection_hash,
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
            "sequenceLength": sequence_length,
            "candidatePairs": len(candidates),
            "completeCandidatePairs": len(fixture.preset["candidatePairs"]),
        },
        "decision": {
            "recommendedMode": "digital",
            "reason": "配对互斥和假结策略形成通用约束 QUBO，使用 Digital QAOA。",
            "modes": [
                {
                    "mode": "digital",
                    "algorithm": "qaoa",
                    "availableAlgorithms": ["qaoa"],
                    "status": "recommended",
                    "reason": "完整候选配对 QUBO 进入数字线路。",
                },
                {
                    "mode": "hybrid",
                    "algorithm": "qaoa",
                    "availableAlgorithms": ["qaoa"],
                    "status": "unsuitable",
                    "reason": "候选配对没有经过验证的 Rydberg 几何，不构造 Hybrid。",
                },
                {
                    "mode": "analog",
                    "algorithm": "qaa",
                    "availableAlgorithms": ["qaa"],
                    "status": "unsuitable",
                    "reason": "原生 Analog 不能完整表达当前配对约束。",
                },
            ],
        },
        "domain": {
            "kind": "rna_structure",
            "modelLevel": fixture.domain["modelLevel"],
            "sequence": resolved["sequence"],
            "preset": preset,
            "minimumLoop": resolved["minimum_loop"],
            "pseudoknotPolicy": fixture.preset["pseudoknotPolicy"],
            "candidatePairs": candidates,
            "completeCandidatePairs": fixture.preset["candidatePairs"],
            "allowedCrossings": fixture.preset["allowedCrossings"],
            "energyModel": fixture.domain["energyModel"],
            "referenceStructure": _reference_structure(definition),
            "classicExact": _classic_exact(definition),
            "classicDynamicProgramming": _classic_dynamic_programming(definition),
            "nodes": nodes,
            "edges": edges,
            "limitations": fixture.manifest["limitations"],
        },
    }
    payload["analysisHash"] = hash_payload(payload)
    return payload


def run_rna_structure(
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
        raise ValueError("RNA 首个已校准模型只支持一层 Digital QAOA。")
    resolved = rna_values(preset, values)
    fixture = load_rna_fixture(preset)
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
        key=lambda item: (item["energy"], -item["count"], item["bitstring"]),
    )
    quantum_candidate = (
        feasible[0]
        if feasible
        else _decode(
            "0" * len(definition.problem.variables),
            definition,
            source="quantum_not_observed",
        )
        | {"count": 0, "feasible": False}
    )
    classic_exact = _classic_exact(definition)
    dynamic_programming = _classic_dynamic_programming(definition)
    reference = _reference_structure(definition)
    feasible_shots = sum(item["count"] for item in observed if item["feasible"])
    low_energy_shots = sum(
        item["count"]
        for item in observed
        if item["feasible"] and item["energy"] <= classic_exact["energy"] + 1.0
    )
    best = result.evaluations[result.best_evaluation_index]
    circuit = (
        qaoa.build_circuit()
        .bind(best.parameter_bind.values)
        .to_program()
        .to_dict()["circuit"]
    )
    analysis = analyze_rna_structure(preset, resolved)
    payload = {
        "kind": "biomedicine",
        "analysis": analysis,
        "domain": {
            "kind": "rna_structure_result",
            "quantumCandidate": quantum_candidate,
            "topObservedFeasible": feasible[:8],
            "observedFeasibleCount": len(feasible),
            "observedFeasibleRate": feasible_shots / max(1, shots),
            "lowEnergyCoverage": low_energy_shots / max(1, shots),
            "structureDiversity": len(
                {item["dotBracket"] for item in feasible if item["pairCount"] > 0}
            ),
            "classicExact": classic_exact,
            "classicDynamicProgramming": dynamic_programming,
            "referenceStructure": reference,
            "interpretation": (
                "QAOA counts 仅表示本次有限 shots 的观测频率，"
                "不是热力学概率或碱基配对概率。"
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
            "caseId": "rna_structure",
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
            "claimBoundary": "finite_versioned_rna_candidate_pair_model",
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
    return BIOMEDICINE_SCENARIO_SPECS["rna_structure"].to_dict()
