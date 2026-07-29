"""Finite 2D peptide conformation landscape and CASCAQit Digital QAOA."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from cascaqit.algorithms import QAOA, OptimizerConfig

from cascaqit_biomedicine_demo.audit import (
    finalize_stable_audit,
    local_backend_context,
)
from cascaqit_biomedicine_demo.catalog import BIOMEDICINE_SCENARIO_SPECS
from cascaqit_biomedicine_demo.fixtures import validate_manifest_contract
from cascaqit_biomedicine_demo.pauli_vqe import hash_payload
from cascaqit_biomedicine_demo.problem_model import (
    OptimizationProblemDefinition,
    QuboBuilder,
    TermGroup,
)

DATA_ROOT = (
    Path(__file__).resolve().parent
    / "data"
    / "peptide_landscape"
    / "six_residue_2d"
    / "1"
)

_PRESETS = {
    "hydrophobic_core": {"sequence": "HPPHHP", "contact_weight": 1.0},
    "charged_competition": {"sequence": "+-P-+H", "contact_weight": 1.0},
    "contact_limited": {"sequence": "HPHPPH", "contact_weight": 1.0},
}


@dataclass(frozen=True)
class PeptideFixture:
    manifest: dict[str, Any]
    domain: dict[str, Any]
    manifest_hash: str


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"peptide fixture must contain an object: {path.name}")
    return value, raw


def _derived_contacts(coordinates: list[list[int]]) -> list[list[int]]:
    contacts = []
    for left, right in combinations(range(len(coordinates)), 2):
        if right == left + 1:
            continue
        distance = sum(
            abs(coordinates[left][axis] - coordinates[right][axis]) for axis in (0, 1)
        )
        if distance == 1:
            contacts.append([left + 1, right + 1])
    return contacts


def load_peptide_fixture() -> PeptideFixture:
    manifest, manifest_raw = _read_json(DATA_ROOT / "manifest.json")
    validate_manifest_contract(manifest)
    domain, domain_raw = _read_json(DATA_ROOT / "domain.json")
    if hashlib.sha256(domain_raw).hexdigest() != manifest["artifacts"][0]["sha256"]:
        raise ValueError("peptide fixture checksum mismatch: domain.json")
    conformations = domain["conformations"]
    if not 8 <= len(conformations) <= 16:
        raise ValueError("peptide fixture requires 8 to 16 conformations")
    identifiers = set()
    coordinate_sets = set()
    for item in conformations:
        identifiers.add(item["id"])
        coordinates = item["coordinates"]
        if len(coordinates) != domain["residueCount"]:
            raise ValueError("peptide conformation residue count mismatch")
        if len({tuple(point) for point in coordinates}) != len(coordinates):
            raise ValueError("peptide conformation is not self-avoiding")
        for left, right in zip(coordinates, coordinates[1:]):
            if abs(left[0] - right[0]) + abs(left[1] - right[1]) != 1:
                raise ValueError("peptide conformation breaks chain continuity")
        if _derived_contacts(coordinates) != item["contacts"]:
            raise ValueError("peptide conformation contact graph mismatch")
        coordinate_sets.add(tuple(tuple(point) for point in coordinates))
    if len(identifiers) != len(conformations) or len(coordinate_sets) != len(
        conformations
    ):
        raise ValueError("peptide conformations must be unique")
    if manifest["variable_order"] != [
        f"conf.{item['id']}" for item in conformations
    ]:
        raise ValueError("peptide fixture variable order is inconsistent")
    return PeptideFixture(
        manifest=manifest,
        domain=domain,
        manifest_hash=hashlib.sha256(manifest_raw).hexdigest(),
    )


def peptide_values(preset: str, overrides: dict[str, Any]) -> dict[str, Any]:
    try:
        values = dict(_PRESETS[preset])
    except KeyError as exc:
        raise ValueError(f"unknown peptide preset: {preset}") from exc
    values.update(overrides)
    sequence = str(values["sequence"])
    if sequence not in {item["sequence"] for item in _PRESETS.values()}:
        raise ValueError("sequence must be one of the packaged six-residue presets")
    weight = float(values["contact_weight"])
    if not 0.5 <= weight <= 2.0:
        raise ValueError("contact_weight must be between 0.5 and 2.0")
    return {"sequence": sequence, "contact_weight": weight}


def _pair_score(left: str, right: str) -> float:
    pair = {left, right}
    if left in "+-" and right in "+-":
        return -1.2 if left != right else 0.8
    if "H" in pair and ("+" in pair or "-" in pair):
        return -0.2
    if left == right == "H":
        return -1.0
    if pair == {"H", "P"}:
        return -0.1
    if left == right == "P":
        return 0.05
    return 0.0


def _energy(
    preset: str, sequence: str, contacts: list[list[int]], weight: float
) -> float:
    energy = (
        sum(
            _pair_score(sequence[left - 1], sequence[right - 1])
            for left, right in contacts
        )
        * weight
    )
    if preset == "contact_limited" and len(contacts) > 1:
        energy += 0.9 * (len(contacts) - 1)
    return round(energy, 10)


def _landscape(preset: str, values: dict[str, Any]) -> list[dict[str, Any]]:
    fixture = load_peptide_fixture()
    return [
        {
            **item,
            "energy": _energy(
                preset, values["sequence"], item["contacts"], values["contact_weight"]
            ),
            "contactCount": len(item["contacts"]),
        }
        for item in fixture.domain["conformations"]
    ]


def _definition(preset: str, values: dict[str, Any]) -> OptimizationProblemDefinition:
    landscape = _landscape(preset, values)
    variables = tuple(f"conf.{item['id']}" for item in landscape)
    builder = QuboBuilder(variables)
    for variable, item in zip(variables, landscape):
        builder.add_linear(
            variable,
            item["energy"],
            contribution_id=f"energy:{item['id']}",
            group_id="contact_energy",
            source_rule="coarse_grained_contact_score",
            role="objective",
        )
    penalty = 2.0
    builder.add_squared_equality(
        {variable: 1.0 for variable in variables},
        rhs=1.0,
        penalty=penalty,
        contribution_id_prefix="exactly_one",
        group_id="exactly_one",
        source_rule="select_exactly_one_conformation",
    )
    problem = builder.build(
        problem_id=f"biomedicine.peptide.six-residue.{preset}",
        metadata={"preset": preset, "sequence": values["sequence"]},
    )
    return OptimizationProblemDefinition(
        case_id="peptide_landscape",
        title="小肽离散构象能景",
        problem_kind="qubo",
        problem=problem,
        business_variables=variables,
        term_groups=(
            TermGroup("contact_energy", "粗粒化接触能", "objective", variables),
            TermGroup(
                "exactly_one", "恰好选择一个构象", "global_constraint", variables
            ),
        ),
        coefficient_contributions=builder.contributions,
        metadata={"landscape": landscape, "penalty": penalty},
    )


def _solution(
    bitstring: str, definition: OptimizationProblemDefinition
) -> dict[str, Any]:
    selected = [
        variable
        for variable, bit in zip(definition.problem.variables, bitstring)
        if bit == "1"
    ]
    conformation_id = selected[0].split(".", 1)[1] if len(selected) == 1 else None
    item = next(
        (
            row
            for row in definition.metadata["landscape"]
            if row["id"] == conformation_id
        ),
        None,
    )
    return {
        "bitstring": bitstring,
        "conformationId": conformation_id,
        "energy": None if item is None else item["energy"],
        "contactCount": 0 if item is None else item["contactCount"],
        "coordinates": [] if item is None else item["coordinates"],
        "contacts": [] if item is None else item["contacts"],
        "feasible": len(selected) == 1,
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


def analyze_peptide_landscape(preset: str, values: dict[str, Any]) -> dict[str, Any]:
    resolved = peptide_values(preset, values)
    fixture = load_peptide_fixture()
    definition = _definition(preset, resolved)
    landscape = sorted(
        definition.metadata["landscape"], key=lambda x: (x["energy"], x["id"])
    )
    best = landscape[0]
    nodes = [
        {
            "id": f"res.{i + 1}",
            "label": residue,
            "group": residue,
            "role": "residue",
            "x": 50 + point[0] * 12,
            "y": 50 + point[1] * 12,
        }
        for i, (residue, point) in enumerate(
            zip(resolved["sequence"], best["coordinates"])
        )
    ]
    edges = [
        {"source": f"res.{i}", "target": f"res.{i + 1}", "kind": "chain", "score": 0.0}
        for i in range(1, 6)
    ] + [
        {
            "source": f"res.{left}",
            "target": f"res.{right}",
            "kind": "contact",
            "score": _pair_score(
                resolved["sequence"][left - 1], resolved["sequence"][right - 1]
            ),
        }
        for left, right in best["contacts"]
    ]
    payload = {
        "kind": "biomedicine",
        "caseId": "peptide_landscape",
        "executionFamily": "problem",
        "implementationStatus": "available",
        "dataset": {
            "id": fixture.manifest["dataset_id"],
            "version": fixture.manifest["version"],
            "manifestHash": fixture.manifest_hash,
            "sourceKind": fixture.manifest["source"]["kind"],
            "license": fixture.manifest["source"]["license"],
            "licenseCheckedAt": fixture.manifest["source"]["license_checked_at"],
            "allowedClaims": fixture.manifest["allowed_claims"],
            "limitations": fixture.manifest["limitations"],
        },
        "problem": {
            "id": definition.problem.problem_id,
            "type": "qubo",
            "hash": definition.problem.stable_hash(),
            "variables": list(definition.problem.variables),
            "terms": [
                {
                    "id": f"linear.{v}",
                    "operator": "linear",
                    "targets": [v],
                    "coefficient": c,
                }
                for v, c in definition.problem.linear_terms
            ]
            + [
                {
                    "id": f"quadratic.{left}.{right}",
                    "operator": "quadratic",
                    "targets": [left, right],
                    "coefficient": c,
                }
                for left, right, c in definition.problem.quadratic_terms
            ],
            "termGroups": [vars(group) for group in definition.term_groups],
            "coefficientLedger": _ledger(definition),
        },
        "resource": {
            "logical_variables": len(definition.problem.variables),
            "conformations": len(landscape),
        },
        "decision": {
            "recommendedMode": "digital",
            "reason": "one-hot 全局约束形成稠密 QUBO，使用 Digital QAOA 完整表达。",
            "modes": [
                {
                    "mode": "digital",
                    "algorithm": "qaoa",
                    "availableAlgorithms": ["qaoa"],
                    "status": "recommended",
                    "reason": "完整 QUBO 进入数字线路。",
                },
                {
                    "mode": "hybrid",
                    "algorithm": "qaoa",
                    "availableAlgorithms": ["qaoa"],
                    "status": "unsuitable",
                    "reason": "没有可审计且保留真实 residual 的局域 Analog core。",
                },
                {
                    "mode": "analog",
                    "algorithm": "qaa",
                    "availableAlgorithms": ["qaa"],
                    "status": "unsuitable",
                    "reason": "当前纯 Analog 目标不能完整表达 one-hot 稠密约束。",
                },
            ],
        },
        "domain": {
            "kind": "peptide_landscape",
            "modelLevel": fixture.domain["modelLevel"],
            "sequence": resolved["sequence"],
            "preset": preset,
            "contactWeight": resolved["contact_weight"],
            "conformations": landscape,
            "nodes": nodes,
            "edges": edges,
            "classicGroundIds": [
                item["id"] for item in landscape if item["energy"] == best["energy"]
            ],
            "limitations": fixture.manifest["limitations"],
        },
    }
    payload["analysisHash"] = hash_payload(payload)
    return payload


def run_peptide_landscape(
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
        raise ValueError("小肽首个已校准预设只支持一层 Digital QAOA。")
    resolved = peptide_values(preset, values)
    fixture = load_peptide_fixture()
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
        _solution(state, definition) | {"count": count}
        for state, count in counts.items()
    ]
    feasible = sorted(
        (item for item in observed if item["feasible"]),
        key=lambda x: (x["energy"], -x["count"], x["bitstring"]),
    )
    quantum_candidate = (
        feasible[0]
        if feasible
        else _solution("0" * len(definition.problem.variables), definition)
        | {"count": 0}
    )
    landscape = sorted(
        definition.metadata["landscape"], key=lambda x: (x["energy"], x["id"])
    )
    minimum = landscape[0]["energy"]
    classic_ground = [item for item in landscape if item["energy"] == minimum]
    best = result.evaluations[result.best_evaluation_index]
    circuit = (
        qaoa.build_circuit()
        .bind(best.parameter_bind.values)
        .to_program()
        .to_dict()["circuit"]
    )
    analysis = analyze_peptide_landscape(preset, resolved)
    payload = {
        "kind": "biomedicine",
        "analysis": analysis,
        "domain": {
            "kind": "peptide_landscape_result",
            "quantumCandidate": quantum_candidate,
            "topObservedFeasible": feasible[:5],
            "observedFeasibleCount": len(feasible),
            "classicGroundConformations": classic_ground,
            "fullLandscape": landscape,
            "energyGapFromGround": None
            if not quantum_candidate["feasible"]
            else quantum_candidate["energy"] - minimum,
            "interpretation": (
                "有限二维粗粒化构象库的无量纲接触能；不是蛋白结构或折叠动力学预测。"
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
                        "depth": i,
                        "name": str(g["name"]).upper(),
                        "targets": list(g.get("targets", ())),
                        "controls": list(g.get("controls", ())),
                        "parameters": g.get("parameters", {}),
                    }
                    for i, g in enumerate(circuit["gates"])
                ],
                "depth": len(circuit["gates"]),
            },
            "counts": [
                {"state": state, "count": count, "rank": i + 1}
                for i, (state, count) in enumerate(
                    sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:12]
                )
            ],
            "parameterHistory": [
                {
                    "index": i,
                    "objective": float(item.energy),
                    "parameters": dict(item.parameter_bind.values),
                    "selected": i == result.best_evaluation_index,
                }
                for i, item in enumerate(result.evaluations)
            ],
        },
        "audit": {
            "domainId": "biomedicine",
            "caseId": "peptide_landscape",
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
            "claimBoundary": "finite_2d_coarse_grained_landscape",
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
    return BIOMEDICINE_SCENARIO_SPECS["peptide_landscape"].to_dict()
