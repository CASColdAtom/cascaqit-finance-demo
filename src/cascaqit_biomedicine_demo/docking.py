"""Offline 1HSG discrete docking-match QUBO and CASCAQit execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Any, Literal

from cascaqit_biomedicine_demo.audit import (
    finalize_stable_audit,
    local_backend_context,
)
from cascaqit_biomedicine_demo.problem_model import (
    OptimizationProblemDefinition,
    QuboBuilder,
    TermGroup,
    with_isolated_pair_geometry,
)
from cascaqit_industry_demo.problem_executor import ScenarioExecutor

DATA_ROOT = (
    Path(__file__).resolve().parent / "data" / "docking_match" / "1hsg_indinavir" / "1"
)
MATCH_PREFIX = "match."
POSE_PREFIX = "select."
SLACK_VARIABLE = "slack.coverage"


@dataclass(frozen=True)
class DockingFixture:
    manifest: dict[str, Any]
    domain: dict[str, Any]
    reference: dict[str, Any]
    manifest_hash: str


@dataclass(frozen=True)
class DockingInput:
    preset: str
    match_weight: float
    collision_penalty: float
    coverage_weight: float
    geometry_weight: float
    strain_weight: float


@dataclass(frozen=True)
class DomainIssue:
    field: str
    message: str


@dataclass(frozen=True)
class DockingSolution:
    bitstring: str
    pose_id: str | None
    selected_match_ids: tuple[str, ...]
    model_objective: float
    domain_score: float
    coverage: int
    reference_overlap: int
    feasible: bool
    checks: tuple[dict[str, Any], ...]


_PRESET_DEFAULTS: dict[str, dict[str, float]] = {
    "reference_pose": {
        "match_weight": 0.65,
        "collision_penalty": 2.4,
        "coverage_weight": 0.6,
        "geometry_weight": 0.8,
        "strain_weight": 1.0,
    },
    "strict_geometry": {
        "match_weight": 0.55,
        "collision_penalty": 3.6,
        "coverage_weight": 0.55,
        "geometry_weight": 1.4,
        "strain_weight": 1.2,
    },
    "pharmacophore_coverage": {
        "match_weight": 0.55,
        "collision_penalty": 2.8,
        "coverage_weight": 1.1,
        "geometry_weight": 0.8,
        "strain_weight": 1.0,
    },
}


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _read_object(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"docking fixture must contain an object: {path.name}")
    return value, raw


def load_docking_fixture() -> DockingFixture:
    manifest, manifest_raw = _read_object(DATA_ROOT / "manifest.json")
    loaded: dict[str, dict[str, Any]] = {}
    for artifact in manifest.get("artifacts", ()):
        name = str(artifact["path"])
        if name not in {"domain.json", "reference.json"}:
            raise ValueError(f"unsupported docking fixture artifact: {name}")
        value, raw = _read_object(DATA_ROOT / name)
        if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
            raise ValueError(f"docking fixture checksum mismatch: {name}")
        loaded[name] = value
    if set(loaded) != {"domain.json", "reference.json"}:
        raise ValueError("docking fixture is incomplete")
    domain = loaded["domain.json"]
    match_ids = {str(item["id"]) for item in domain["matches"]}
    pose_ids = {str(item["id"]) for item in domain["poses"]}
    if len(match_ids) != 8 or len(pose_ids) != 2:
        raise ValueError("docking fixture requires two poses and eight matches")
    for item in domain["matches"]:
        if item["pose_id"] not in pose_ids:
            raise ValueError("docking match references an unknown pose")
    for conflict in domain["conflicts"]:
        if {conflict["left"], conflict["right"]} - match_ids:
            raise ValueError("docking conflict references an unknown match")
    return DockingFixture(
        manifest=manifest,
        domain=domain,
        reference=loaded["reference.json"],
        manifest_hash=hashlib.sha256(manifest_raw).hexdigest(),
    )


def docking_values(preset: str, overrides: dict[str, Any]) -> dict[str, float]:
    try:
        values = dict(_PRESET_DEFAULTS[preset])
    except KeyError as exc:
        raise ValueError(f"unknown docking preset: {preset}") from exc
    for key in ("match_weight", "collision_penalty", "coverage_weight"):
        if key in overrides:
            values[key] = float(overrides[key])
    return values


def docking_input(preset: str, values: dict[str, Any]) -> DockingInput:
    resolved = docking_values(preset, values)
    return DockingInput(preset=preset, **resolved)


def _match_variable(match_id: str) -> str:
    return f"{MATCH_PREFIX}{match_id.removeprefix('match.')}"


def _pose_variable(pose_id: str) -> str:
    return f"{POSE_PREFIX}{pose_id.removeprefix('pose.')}"


class DockingMatchScenario:
    case_id = "docking_match"
    title = "靶点口袋与配体候选构象匹配"

    def __init__(self, fixture: DockingFixture | None = None) -> None:
        self.fixture = fixture or load_docking_fixture()

    def default_input(self) -> DockingInput:
        return docking_input("reference_pose", {})

    def validate(self, case_input: DockingInput) -> tuple[DomainIssue, ...]:
        issues = []
        ranges = {
            "match_weight": (0.2, 1.0),
            "collision_penalty": (1.0, 4.0),
            "coverage_weight": (0.2, 1.5),
        }
        for field, (minimum, maximum) in ranges.items():
            value = float(getattr(case_input, field))
            if not minimum <= value <= maximum:
                issues.append(
                    DomainIssue(
                        field, f"{field} must be between {minimum} and {maximum}"
                    )
                )
        return tuple(issues)

    def build_definition(
        self, case_input: DockingInput
    ) -> OptimizationProblemDefinition:
        fixture = self.fixture
        domain = fixture.domain
        matches = tuple(domain["matches"])
        poses = tuple(domain["poses"])
        match_variables = tuple(_match_variable(str(item["id"])) for item in matches)
        pose_variables = tuple(_pose_variable(str(item["id"])) for item in poses)
        business = (*match_variables, *pose_variables)
        builder = QuboBuilder((*business, SLACK_VARIABLE))

        for item, variable in zip(matches, match_variables):
            match_id = str(item["id"])
            builder.add_linear(
                variable,
                -case_input.match_weight * float(item["quality"]),
                contribution_id=f"reward:{match_id}",
                group_id="match_objective",
                source_rule="geometric_match_reward",
                role="objective",
            )
            deviation = float(item["distance_deviation"]) + float(
                item["angle_deviation"]
            )
            builder.add_linear(
                variable,
                case_input.geometry_weight * deviation,
                contribution_id=f"deviation:{match_id}",
                group_id="match_objective",
                source_rule="distance_angle_deviation",
                role="objective",
            )
            if bool(item["critical"]):
                builder.add_linear(
                    variable,
                    -case_input.coverage_weight,
                    contribution_id=f"critical:{match_id}",
                    group_id="match_objective",
                    source_rule="critical_feature_reward",
                    role="objective",
                )

        for item, variable in zip(poses, pose_variables):
            builder.add_linear(
                variable,
                case_input.strain_weight * float(item["strain"]),
                contribution_id=f"strain:{item['id']}",
                group_id="match_objective",
                source_rule="pose_strain_penalty",
                role="objective",
            )

        conflict_pairs = tuple(
            (
                _match_variable(str(item["left"])),
                _match_variable(str(item["right"])),
            )
            for item in domain["conflicts"]
        )
        for conflict, (left, right) in zip(domain["conflicts"], conflict_pairs):
            builder.add_quadratic(
                left,
                right,
                4.0 * case_input.collision_penalty,
                contribution_id=f"conflicts:{left}:{right}",
                group_id="conflicts",
                source_rule=str(conflict["rule"]),
                role="constraint",
            )

        hard_penalty = 6.0 + case_input.collision_penalty
        builder.add_squared_equality(
            {variable: 1.0 for variable in pose_variables},
            rhs=1.0,
            penalty=hard_penalty,
            contribution_id_prefix="pose_unique",
            group_id="pose_unique",
            source_rule="single_pose_selection",
        )
        pose_by_id = {
            str(item["id"]): variable for item, variable in zip(poses, pose_variables)
        }
        for item, variable in zip(matches, match_variables):
            pose_variable = pose_by_id[str(item["pose_id"])]
            builder.add_linear(
                variable,
                hard_penalty,
                contribution_id=f"dependency:linear:{variable}",
                group_id="dependencies",
                source_rule="match_requires_pose",
                role="constraint",
            )
            builder.add_quadratic(
                variable,
                pose_variable,
                -hard_penalty,
                contribution_id=f"dependency:quadratic:{variable}:{pose_variable}",
                group_id="dependencies",
                source_rule="match_requires_pose",
                role="constraint",
            )
        builder.add_squared_equality(
            {
                **{variable: 1.0 for variable in match_variables},
                SLACK_VARIABLE: -1.0,
            },
            rhs=float(domain["minimum_coverage"]),
            penalty=hard_penalty,
            contribution_id_prefix="coverage_minimum",
            group_id="coverage",
            source_rule="minimum_feature_coverage_with_slack",
        )
        problem = builder.build(
            problem_id=f"biomedicine.docking.1hsg.{case_input.preset}",
            metadata={
                "dataset_id": fixture.manifest["dataset_id"],
                "manifest_hash": fixture.manifest_hash,
                "business_variables": list(business),
                "auxiliary_variables": [SLACK_VARIABLE],
            },
        )
        problem, geometry = with_isolated_pair_geometry(problem, conflict_pairs)
        return OptimizationProblemDefinition(
            case_id=self.case_id,
            title=self.title,
            problem_kind="qubo",
            problem=problem,
            business_variables=tuple(business),
            auxiliary_variables=(SLACK_VARIABLE,),
            term_groups=(
                TermGroup(
                    "match_objective",
                    "匹配奖励、几何偏差与构象应变",
                    "objective",
                    tuple(business),
                ),
                TermGroup(
                    "conflicts",
                    "特征、占位与空间冲突",
                    "pairwise_conflict",
                    pairs=conflict_pairs,
                ),
                TermGroup(
                    "pose_unique", "单一构象", "global_constraint", pose_variables
                ),
                TermGroup(
                    "dependencies", "匹配依赖构象", "dependency", tuple(business)
                ),
                TermGroup(
                    "coverage", "最低特征覆盖", "global_constraint", match_variables
                ),
                TermGroup(
                    "slack", "覆盖辅助变量", "auxiliary_penalty", (SLACK_VARIABLE,)
                ),
            ),
            coefficient_contributions=builder.contributions,
            analog_candidate_group_ids=("conflicts",),
            geometry_evidence=geometry,
            metadata={
                "dataset_id": fixture.manifest["dataset_id"],
                "manifest_hash": fixture.manifest_hash,
                "scientific_boundary": "discrete_match_score_only",
            },
        )

    def decode(
        self,
        case_input: DockingInput,
        definition: OptimizationProblemDefinition,
        candidate: Any,
    ) -> DockingSolution:
        decoded = getattr(candidate, "decoded", None)
        if decoded is not None and "binary_values" in decoded:
            values = dict(decoded["binary_values"])
        else:
            values = dict(
                zip(
                    definition.problem.variables,
                    (int(bit) for bit in str(candidate.bitstring)),
                )
            )
        return self.decode_values(
            case_input,
            definition,
            values,
            bitstring=str(candidate.bitstring),
        )

    def decode_values(
        self,
        case_input: DockingInput,
        definition: OptimizationProblemDefinition,
        values: dict[str, int],
        *,
        bitstring: str | None = None,
    ) -> DockingSolution:
        domain = self.fixture.domain
        selected_poses = tuple(
            str(item["id"])
            for item in domain["poses"]
            if values.get(_pose_variable(str(item["id"])), 0) == 1
        )
        selected_matches = tuple(
            str(item["id"])
            for item in domain["matches"]
            if values.get(_match_variable(str(item["id"])), 0) == 1
        )
        selected_set = set(selected_matches)
        conflict_violations = tuple(
            item
            for item in domain["conflicts"]
            if item["left"] in selected_set and item["right"] in selected_set
        )
        match_by_id = {str(item["id"]): item for item in domain["matches"]}
        dependency_violations = tuple(
            match_id
            for match_id in selected_matches
            if match_by_id[match_id]["pose_id"] not in selected_poses
        )
        coverage = len(selected_matches)
        slack = int(values.get(SLACK_VARIABLE, 0))
        minimum = int(domain["minimum_coverage"])
        coverage_equation = coverage - slack == minimum
        checks = (
            {
                "id": "single_pose",
                "label": "单一构象",
                "passed": len(selected_poses) == 1,
                "actual": len(selected_poses),
                "expected": 1,
            },
            {
                "id": "match_pose_dependency",
                "label": "匹配与构象一致",
                "passed": not dependency_violations,
                "actual": len(dependency_violations),
                "expected": 0,
            },
            {
                "id": "pairwise_conflicts",
                "label": "特征、占位与碰撞冲突",
                "passed": not conflict_violations,
                "actual": len(conflict_violations),
                "expected": 0,
            },
            {
                "id": "minimum_coverage",
                "label": "最低特征覆盖",
                "passed": coverage >= minimum and coverage_equation,
                "actual": coverage,
                "expected": f">={minimum}",
            },
        )
        objective = _qubo_value(definition.problem, values)
        domain_score = 0.0
        for match_id in selected_matches:
            item = match_by_id[match_id]
            domain_score += case_input.match_weight * float(item["quality"])
            domain_score -= case_input.geometry_weight * (
                float(item["distance_deviation"]) + float(item["angle_deviation"])
            )
            if bool(item["critical"]):
                domain_score += case_input.coverage_weight
        pose_by_id = {str(item["id"]): item for item in domain["poses"]}
        for pose_id in selected_poses:
            domain_score -= case_input.strain_weight * float(
                pose_by_id[pose_id]["strain"]
            )
        reference_matches = set(domain["reference"]["match_ids"])
        if bitstring is None:
            bitstring = "".join(
                str(int(values.get(variable, 0)))
                for variable in definition.problem.variables
            )
        return DockingSolution(
            bitstring=bitstring,
            pose_id=selected_poses[0] if len(selected_poses) == 1 else None,
            selected_match_ids=selected_matches,
            model_objective=objective,
            domain_score=domain_score,
            coverage=coverage,
            reference_overlap=len(selected_set & reference_matches),
            feasible=all(bool(item["passed"]) for item in checks),
            checks=checks,
        )


def _qubo_value(problem: Any, values: dict[str, int]) -> float:
    value = float(problem.offset)
    value += sum(
        float(coefficient) * values.get(variable, 0)
        for variable, coefficient in problem.linear_terms
    )
    value += sum(
        float(coefficient) * values.get(left, 0) * values.get(right, 0)
        for left, right, coefficient in problem.quadratic_terms
    )
    return value


def _classic_solutions(
    scenario: DockingMatchScenario,
    case_input: DockingInput,
    definition: OptimizationProblemDefinition,
) -> tuple[DockingSolution, ...]:
    solutions = []
    variables = tuple(definition.problem.variables)
    for bits in product((0, 1), repeat=len(variables)):
        values = dict(zip(variables, bits))
        solution = scenario.decode_values(case_input, definition, values)
        if solution.feasible:
            solutions.append(solution)
    return tuple(
        sorted(solutions, key=lambda item: (item.model_objective, item.bitstring))
    )


def _reference_solution(
    scenario: DockingMatchScenario,
    case_input: DockingInput,
    definition: OptimizationProblemDefinition,
) -> DockingSolution:
    domain = scenario.fixture.domain
    reference = domain["reference"]
    values = {variable: 0 for variable in definition.problem.variables}
    values[_pose_variable(str(reference["pose_id"]))] = 1
    for match_id in reference["match_ids"]:
        values[_match_variable(str(match_id))] = 1
    return scenario.decode_values(case_input, definition, values)


def classic_docking_solution(
    preset: str, values: dict[str, Any] | None = None
) -> DockingSolution:
    """Return the exact feasible baseline for one packaged docking preset."""
    scenario = DockingMatchScenario()
    case_input = docking_input(preset, values or {})
    definition = scenario.build_definition(case_input)
    solutions = _classic_solutions(scenario, case_input, definition)
    if not solutions:
        raise ValueError(f"docking preset has no feasible classical solution: {preset}")
    return solutions[0]


def _mode_payload(decision: Any) -> dict[str, Any]:
    def code(value: str) -> str:
        return value.replace("FINANCE_", "BIOMEDICINE_")

    return {
        "recommendedMode": decision.recommended_mode,
        "reason": decision.reason,
        "modes": [
            {
                "mode": row.mode,
                "algorithm": row.algorithm,
                "availableAlgorithms": list(row.available_algorithms),
                "status": row.status,
                "reason": row.reason,
                "compilerFeasible": row.compiler_feasible,
                "businessSuitable": row.business_suitable,
                "diagnosticCodes": [code(item) for item in row.diagnostic_codes],
                "analogTermCount": row.analog_term_count,
                "digitalTermCount": row.digital_term_count,
                "analogBusinessPairs": [
                    list(pair) for pair in row.analog_business_pairs
                ],
                "coveredGroupIds": list(row.covered_group_ids),
                "missingContributionIds": list(row.missing_contribution_ids),
                "unexpectedAnalogTermIds": list(row.unexpected_analog_term_ids),
                "unexpectedInteractionPairs": [
                    list(pair) for pair in row.unexpected_interaction_pairs
                ],
                "geometryStatus": row.geometry_status,
                "geometrySource": row.geometry_source,
                "layoutPolicy": row.layout_policy,
                "declaredContributionCount": row.declared_contribution_count,
                "coveredContributionCount": row.covered_contribution_count,
            }
            for row in decision.rows
        ],
    }


def _analysis_payload(
    scenario: DockingMatchScenario,
    case_input: DockingInput,
    analysis: Any,
) -> dict[str, Any]:
    fixture = scenario.fixture
    definition = analysis.definition
    canonical = analysis.problem_analysis.canonical_problem
    mapping = analysis.problem_analysis.mapping_plan
    domain = fixture.domain
    visual_edges = [
        {
            "source": item["ligand_feature"],
            "target": item["pocket_feature"],
            "kind": item["interaction"],
            "score": float(item["quality"]),
            "matchId": item["id"],
            "poseId": item["pose_id"],
            "critical": bool(item["critical"]),
        }
        for item in domain["matches"]
    ]
    payload = {
        "kind": "biomedicine",
        "caseId": "docking_match",
        "executionFamily": "problem",
        "implementationStatus": "available",
        "dataset": {
            "id": fixture.manifest["dataset_id"],
            "version": fixture.manifest["version"],
            "manifestHash": fixture.manifest_hash,
            "sourceKind": fixture.manifest["source"]["kind"],
            "license": fixture.manifest["source"]["license"],
            "sourceUri": fixture.manifest["source"]["uri"],
            "sourceChecksum": fixture.manifest["source"]["source_file_sha256"],
            "licensePolicyUri": fixture.manifest["source"]["license_policy_uri"],
            "licenseCheckedAt": fixture.manifest["source"]["license_checked_at"],
            "allowedClaims": fixture.manifest["allowed_claims"],
            "limitations": [*fixture.manifest["limitations"], *domain["limitations"]],
        },
        "problem": {
            "id": canonical.problem_id,
            "type": "qubo",
            "hash": canonical.problem_hash,
            "variables": list(definition.problem.variables),
            "terms": [
                {
                    "id": item.term_id,
                    "operator": "linear",
                    "targets": [item.variable],
                    "coefficient": float(item.coefficient),
                }
                for item in canonical.linear_terms
            ]
            + [
                {
                    "id": item.term_id,
                    "operator": "quadratic",
                    "targets": [item.left, item.right],
                    "coefficient": float(item.coefficient),
                }
                for item in canonical.quadratic_terms
            ],
            "termGroups": [asdict(group) for group in definition.term_groups],
            "coefficientLedger": {
                "balanced": True,
                "contributionCount": len(definition.coefficient_contributions),
                "canonicalTermCount": 1
                + len(canonical.linear_terms)
                + len(canonical.quadratic_terms),
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
            },
        },
        "resource": dict(mapping.resource_estimate),
        "layout": [
            {"id": site.logical_id, "x": site.position[0], "y": site.position[1]}
            for site in mapping.layout.sites
        ],
        "decision": _mode_payload(analysis.mode_decision),
        "domain": {
            "kind": "docking_match",
            "modelLevel": "离散配体特征与口袋特征匹配",
            "structure": domain["structure"],
            "poses": domain["poses"],
            "matches": domain["matches"],
            "conflicts": domain["conflicts"],
            "minimumCoverage": domain["minimum_coverage"],
            "nodes": domain["visual"]["nodes"],
            "edges": visual_edges,
            "reference": domain["reference"],
            "weights": asdict(case_input),
            "limitations": domain["limitations"],
        },
    }
    payload["analysisHash"] = _hash(payload)
    return payload


def analyze_docking_match(preset: str, values: dict[str, Any]) -> dict[str, Any]:
    scenario = DockingMatchScenario()
    case_input = docking_input(preset, values)
    analysis = ScenarioExecutor().analyze(scenario, case_input)
    return _analysis_payload(scenario, case_input, analysis)


def _solution_payload(solution: DockingSolution, source: str) -> dict[str, Any]:
    return {
        "source": source,
        "bitstring": solution.bitstring,
        "poseId": solution.pose_id,
        "selectedMatchIds": list(solution.selected_match_ids),
        "modelObjective": solution.model_objective,
        "domainScore": solution.domain_score,
        "coverage": solution.coverage,
        "referenceOverlap": solution.reference_overlap,
        "feasible": solution.feasible,
        "checks": list(solution.checks),
    }


def _waveforms(program: dict[str, Any] | None) -> dict[str, list[dict[str, float]]]:
    if program is None:
        return {name: [] for name in ("rabi", "detuning", "phase")}
    terms = program.get("hamiltonian", {}).get("terms", {})
    output = {}
    for name in ("rabi", "detuning", "phase"):
        waveform = terms.get(name)
        if not isinstance(waveform, dict):
            output[name] = []
            continue
        values = [float(value) for value in (waveform.get("values") or (0.0,))]
        times = [float(value) for value in (waveform.get("times") or ())]
        duration = float(waveform.get("duration", max(times, default=1.0)))
        if not times:
            times = [0.0, duration]
        if len(values) == 1:
            values = [values[0], values[0]]
        scale = max((abs(value) for value in values), default=1.0) or 1.0
        output[name] = [
            {"time": time, "value": value / scale, "raw": value}
            for time, value in zip(times, values)
        ]
    return output


def _quantum_payload(result: Any) -> dict[str, Any]:
    native = result.execution.context.native_program.to_dict()
    circuits = []
    blocks = []
    analog_program = None
    if result.mode == "digital":
        circuits = [native["circuit"]]
    else:
        for block in native.get("blocks", ()):
            blocks.append(block["block_type"])
            if "circuit" in block:
                circuits.append(block["circuit"])
            if block["block_type"] == "analog":
                analog_program = block["program"]
    gates = []
    qubits = list(result.execution.logical_order)
    for circuit in circuits:
        for gate in circuit.get("gates", ()):
            gates.append(
                {
                    "depth": len(gates),
                    "name": str(gate.get("name", "u")).upper(),
                    "targets": list(gate.get("targets", ())),
                    "controls": list(gate.get("controls", ())),
                    "parameters": gate.get("parameters", {}),
                }
            )
    term_mapping = tuple(result.execution.context.term_mapping)
    counts = sorted(
        result.execution.result.counts.items(), key=lambda item: (-item[1], item[0])
    )[:12]
    return {
        "kind": "problem_qaoa",
        "mode": result.mode,
        "algorithm": result.execution.algorithm,
        "topology": result.execution.topology,
        "layerCount": int(result.metadata["layers"]),
        "blocks": blocks,
        "layers": ["H", "U1", "A", "U2", "RX1", "M"]
        if result.mode == "hybrid"
        else ["H", "U1", "U2", "RX1", "M"],
        "circuit": {"qubits": qubits, "gates": gates, "depth": len(gates)},
        "atoms": [
            {
                "id": site.logical_id,
                "x": float(site.position[0]),
                "y": float(site.position[1]),
                "selected": site.logical_id
                in set(result.business_candidate.selected_match_ids),
            }
            for site in result.execution.context.analysis.mapping_plan.layout.sites
        ],
        "waveforms": _waveforms(analog_program),
        "counts": [
            {"state": state, "count": int(count), "rank": index + 1}
            for index, (state, count) in enumerate(counts)
        ],
        "parameterHistory": [
            {
                "index": item.evaluation_index,
                "objective": item.objective_value,
                "parameters": dict(item.parameter_bind.values),
                "selected": item.evaluation_index
                == result.execution.selected_evaluation_index,
            }
            for item in result.execution.parameter_history
        ],
        "termMapping": [
            {
                "termId": item.logical_term_id,
                "operator": item.operator,
                "targets": list(item.targets),
                "logical": item.logical_coefficient,
                "analog": item.analog_coefficient,
                "digital": item.digital_coefficient,
                "implementation": item.implementation,
            }
            for item in term_mapping
        ],
        "summary": {
            "analogTerms": sum(
                abs(item.analog_coefficient) > 1e-12 for item in term_mapping
            ),
            "digitalTerms": sum(
                abs(item.digital_coefficient) > 1e-12 for item in term_mapping
            ),
            "qubits": len(qubits),
            "shots": result.execution.result.shots,
            "evaluations": len(result.execution.parameter_history),
        },
    }


def run_docking_match(
    *,
    preset: str,
    values: dict[str, Any],
    mode: Literal["recommended", "digital", "hybrid"],
    shots: int,
    seed: int,
    layers: int,
    search_strategy: Literal["preset", "grid", "seeded_sample", "continuous"],
    parameter_budget: int,
    optimizer_starts: int,
) -> dict[str, Any]:
    scenario = DockingMatchScenario()
    case_input = docking_input(preset, values)
    executor = ScenarioExecutor()
    result = executor.run(
        scenario,
        case_input,
        mode=mode,
        algorithm="qaoa",
        layers=layers,
        search_strategy=search_strategy,
        parameter_budget=parameter_budget,
        optimizer_starts=optimizer_starts,
        shots=shots,
        seed=seed,
    )
    definition = result.definition
    classic = _classic_solutions(scenario, case_input, definition)
    reference = _reference_solution(scenario, case_input, definition)
    observed = []
    for candidate in result.execution.candidates:
        decoded = scenario.decode(case_input, definition, candidate)
        if decoded.feasible and decoded.bitstring not in {
            item.bitstring for item in observed
        }:
            observed.append(decoded)
    observed.sort(key=lambda item: (item.model_objective, item.bitstring))
    analysis = _analysis_payload(scenario, case_input, result.analysis)
    quantum_candidate = result.business_candidate
    payload = {
        "kind": "biomedicine",
        "analysis": analysis,
        "domain": {
            "kind": "docking_match_result",
            "quantumCandidate": _solution_payload(
                quantum_candidate, "quantum_observed"
            ),
            "classicOptimum": _solution_payload(classic[0], "complete_enumeration"),
            "coCrystalReference": _solution_payload(reference, "co_crystal_reference"),
            "topObservedFeasible": [
                _solution_payload(item, "quantum_observed") for item in observed[:5]
            ],
            "observedFeasibleCount": len(observed),
            "interpretation": (
                "无量纲离散匹配评分；不表示结合自由能、Kd、Ki、IC50 或药效。"
            ),
        },
        "quantum": _quantum_payload(result),
        "audit": {
            "domainId": "biomedicine",
            "caseId": "docking_match",
            "datasetId": scenario.fixture.manifest["dataset_id"],
            "datasetVersion": scenario.fixture.manifest["version"],
            "manifestHash": scenario.fixture.manifest_hash,
            "domainInputHash": _hash(
                {
                    "input": asdict(case_input),
                    "manifestHash": scenario.fixture.manifest_hash,
                }
            ),
            "problemHash": result.execution.problem_hash,
            "analysisHash": result.execution.analysis_hash,
            "compileHash": result.execution.compile_hash,
            "executionHash": result.execution.execution_hash,
            "resultHash": result.evidence.result_hash,
            "backend": local_backend_context(
                execution_family="problem_qaoa",
                mode=result.mode,
                simulation_method=(
                    "hybrid_state_vector"
                    if result.mode == "hybrid"
                    else "state_vector"
                ),
            ),
            "seed": seed,
            "shots": shots,
            "hardwareExecution": False,
            "cloudExecution": False,
            "networkAccessed": False,
            "wallTimeSeconds": result.evidence.wall_time_seconds,
            "optimalityClaim": result.execution.optimality_claim,
            "claimBoundary": "discrete_candidate_pose_matching",
        },
    }
    finalize_stable_audit(
        payload["audit"],
        configuration={
            "input": asdict(case_input),
            "problemHash": result.execution.problem_hash,
            "analysisHash": result.execution.analysis_hash,
            "compileHash": result.execution.compile_hash,
            "mode": result.mode,
            "layers": layers,
            "shots": shots,
            "seed": seed,
            "optimizer": {
                "searchStrategy": search_strategy,
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
    payload["audit"]["resultPresentationHash"] = _hash(payload["domain"])
    return payload
