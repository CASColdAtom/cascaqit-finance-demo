"""Versioned joint defect-and-adsorption QUBO with local CASCAQit execution."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Any, Literal

from cascaqit_industry_demo.audit import (
    finalize_stable_audit,
    hash_payload,
    local_backend_context,
)
from cascaqit_industry_demo.problem_executor import ScenarioExecutor
from cascaqit_industry_demo.problem_model import (
    OptimizationProblemDefinition,
    QuboBuilder,
    TermGroup,
    with_isolated_pair_geometry,
)

DATA_ROOT = (
    Path(__file__).resolve().parent
    / "data"
    / "defect_adsorption"
    / "surface_configurations"
    / "1"
)
PRESETS = {
    "ceria_vacancy_co",
    "tio2_vacancy_water",
    "mos2_vacancy_hydrogen",
}


@dataclass(frozen=True)
class MaterialsFixture:
    manifest: dict[str, Any]
    domain: dict[str, Any]
    reference: dict[str, Any]
    manifest_hash: str


@dataclass(frozen=True)
class DefectAdsorptionInput:
    preset: str
    defect_count: int
    coverage: float
    interaction_weight: float

    @property
    def adsorption_count(self) -> int:
        return int(round(self.coverage * 4.0))


@dataclass(frozen=True)
class DomainIssue:
    field: str
    message: str


@dataclass(frozen=True)
class MaterialSolution:
    bitstring: str
    selected_defect_ids: tuple[str, ...]
    selected_adsorption_ids: tuple[str, ...]
    model_objective: float
    physical_model_energy: float
    energy_components: dict[str, float]
    feasible: bool
    checks: tuple[dict[str, Any], ...]


def _read_object(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"materials fixture must contain an object: {path.name}")
    return value, raw


def load_materials_fixture() -> MaterialsFixture:
    manifest, manifest_raw = _read_object(DATA_ROOT / "manifest.json")
    for key in ("dataset_id", "version", "source", "generation", "units"):
        if not manifest.get(key):
            raise ValueError(f"materials fixture manifest is missing {key}")
    loaded: dict[str, dict[str, Any]] = {}
    for artifact in manifest.get("artifacts", ()):
        name = str(artifact.get("path", ""))
        if name not in {"domain.json", "reference.json"}:
            raise ValueError(f"unsupported materials fixture artifact: {name}")
        value, raw = _read_object(DATA_ROOT / name)
        if hashlib.sha256(raw).hexdigest() != artifact.get("sha256"):
            raise ValueError(f"materials fixture checksum mismatch: {name}")
        loaded[name] = value
    if set(loaded) != {"domain.json", "reference.json"}:
        raise ValueError("materials fixture is incomplete")
    domain = loaded["domain.json"]
    variable_order = [item["id"] for item in domain["defectCandidates"]]
    variable_order.extend(item["id"] for item in domain["adsorptionCandidates"])
    if manifest.get("variable_order") != variable_order:
        raise ValueError("materials fixture variable order is inconsistent")
    if set(domain.get("presets", ())) != PRESETS:
        raise ValueError("materials fixture presets are inconsistent")
    pairs = [tuple(item) for item in domain["localConflictPairs"]]
    endpoints = [variable for pair in pairs for variable in pair]
    if len(endpoints) != len(set(endpoints)):
        raise ValueError("materials Hybrid conflict groups must be disjoint")
    return MaterialsFixture(
        manifest=manifest,
        domain=domain,
        reference=loaded["reference.json"],
        manifest_hash=hashlib.sha256(manifest_raw).hexdigest(),
    )


def material_values(preset: str, overrides: dict[str, Any]) -> dict[str, Any]:
    if preset not in PRESETS:
        raise ValueError(f"unknown materials preset: {preset}")
    values: dict[str, Any] = {
        "defect_count": 1,
        "coverage": 0.5,
        "interaction_weight": 1.0,
    }
    values.update(overrides)
    case_input = material_input(preset, values)
    issues = DefectAdsorptionScenario().validate(case_input)
    if issues:
        raise ValueError("; ".join(item.message for item in issues))
    return {
        "defect_count": case_input.defect_count,
        "coverage": case_input.coverage,
        "interaction_weight": case_input.interaction_weight,
    }


def material_input(preset: str, values: dict[str, Any]) -> DefectAdsorptionInput:
    defect_count = values.get("defect_count", 1)
    if isinstance(defect_count, bool) or not isinstance(defect_count, (int, float)):
        raise ValueError("defect_count must be an integer from 1 to 3")
    if not float(defect_count).is_integer():
        raise ValueError("defect_count must be an integer from 1 to 3")
    return DefectAdsorptionInput(
        preset=preset,
        defect_count=int(defect_count),
        coverage=float(values.get("coverage", 0.5)),
        interaction_weight=float(values.get("interaction_weight", 1.0)),
    )


class DefectAdsorptionScenario:
    case_id = "defect_adsorption"
    title = "催化表面缺陷与吸附协同构型优化"

    def __init__(self, fixture: MaterialsFixture | None = None) -> None:
        self.fixture = fixture or load_materials_fixture()

    def default_input(self) -> DefectAdsorptionInput:
        return material_input("ceria_vacancy_co", {})

    def validate(self, case_input: DefectAdsorptionInput) -> tuple[DomainIssue, ...]:
        issues: list[DomainIssue] = []
        if case_input.preset not in PRESETS:
            issues.append(DomainIssue("preset", "unknown materials preset"))
        if not 1 <= case_input.defect_count <= 3:
            issues.append(DomainIssue("defect_count", "defect_count must be 1..3"))
        if not any(
            math.isclose(case_input.coverage, value, abs_tol=1e-9)
            for value in (0.25, 0.5, 0.75, 1.0)
        ):
            issues.append(
                DomainIssue("coverage", "coverage must be 0.25, 0.5, 0.75, or 1.0")
            )
        if not 0.2 <= case_input.interaction_weight <= 2.0:
            issues.append(
                DomainIssue("interaction_weight", "interaction_weight must be 0.2..2.0")
            )
        return tuple(issues)

    def build_definition(
        self, case_input: DefectAdsorptionInput
    ) -> OptimizationProblemDefinition:
        domain = self.fixture.domain
        model = domain["presets"][case_input.preset]
        defect_ids = tuple(item["id"] for item in domain["defectCandidates"])
        adsorption_ids = tuple(item["id"] for item in domain["adsorptionCandidates"])
        builder = QuboBuilder((*defect_ids, *adsorption_ids))
        for variable in defect_ids:
            builder.add_linear(
                variable,
                float(model["defectFormation"][variable]),
                contribution_id=f"formation:{variable}",
                group_id="formation_energy",
                source_rule="offline_defect_formation_surrogate",
                role="objective",
            )
        for variable in adsorption_ids:
            builder.add_linear(
                variable,
                float(model["adsorptionEnergy"][variable]),
                contribution_id=f"adsorption:{variable}",
                group_id="adsorption_energy",
                source_rule="offline_adsorption_surrogate",
                role="objective",
            )
        for left, right, coefficient in model["synergies"]:
            builder.add_quadratic(
                left,
                right,
                float(coefficient),
                contribution_id=f"synergy:{left}:{right}",
                group_id="defect_adsorption_synergy",
                source_rule="declared_defect_adsorption_synergy",
                role="objective",
            )
        for left, right, coefficient in model["neighborInteractions"]:
            builder.add_quadratic(
                left,
                right,
                case_input.interaction_weight * float(coefficient),
                contribution_id=f"neighbor:{left}:{right}",
                group_id="neighbor_interactions",
                source_rule="periodic_neighbor_interaction",
                role="objective",
            )

        hard_penalty = 8.0
        local_pairs = tuple(
            tuple(str(value) for value in pair) for pair in domain["localConflictPairs"]
        )
        for left, right in local_pairs:
            builder.add_quadratic(
                left,
                right,
                hard_penalty,
                contribution_id=f"local_conflict:{left}:{right}",
                group_id="local_conflicts",
                source_rule="same_site_or_molecule_orientation_exclusion",
                role="constraint",
            )
        builder.add_squared_equality(
            {variable: 1.0 for variable in defect_ids},
            rhs=float(case_input.defect_count),
            penalty=hard_penalty,
            contribution_id_prefix="defect_stoichiometry",
            group_id="defect_stoichiometry",
            source_rule="exact_defect_count",
        )
        builder.add_squared_equality(
            {variable: 1.0 for variable in adsorption_ids},
            rhs=float(case_input.adsorption_count),
            penalty=hard_penalty,
            contribution_id_prefix="coverage",
            group_id="coverage",
            source_rule="exact_adsorption_coverage",
        )
        forbidden_pairs = tuple(
            tuple(str(value) for value in pair)
            for pair in model["forbiddenCombinations"]
        )
        for left, right in forbidden_pairs:
            builder.add_quadratic(
                left,
                right,
                hard_penalty,
                contribution_id=f"forbidden:{left}:{right}",
                group_id="allowed_combinations",
                source_rule="declared_defect_adsorption_compatibility",
                role="constraint",
            )
        problem = builder.build(
            problem_id=f"materials.defect-adsorption.{case_input.preset}",
            metadata={
                "dataset_id": self.fixture.manifest["dataset_id"],
                "manifest_hash": self.fixture.manifest_hash,
                "material_coordinates": domain["coordinateSystem"]["material"],
                "effective_coordinates": domain["coordinateSystem"]["effective"],
                "compiled_coordinates": domain["coordinateSystem"]["compiled"],
            },
        )
        problem, geometry = with_isolated_pair_geometry(problem, local_pairs)
        return OptimizationProblemDefinition(
            case_id=self.case_id,
            title=self.title,
            problem_kind="qubo",
            problem=problem,
            business_variables=(*defect_ids, *adsorption_ids),
            term_groups=(
                TermGroup("formation_energy", "缺陷形成能", "objective", defect_ids),
                TermGroup("adsorption_energy", "吸附能", "objective", adsorption_ids),
                TermGroup(
                    "defect_adsorption_synergy",
                    "缺陷-吸附协同",
                    "objective",
                    pairs=tuple((left, right) for left, right, _ in model["synergies"]),
                ),
                TermGroup(
                    "neighbor_interactions",
                    "周期近邻相互作用",
                    "objective",
                    pairs=tuple(
                        (left, right)
                        for left, right, _ in model["neighborInteractions"]
                    ),
                ),
                TermGroup(
                    "local_conflicts",
                    "同位点与取向互斥",
                    "pairwise_conflict",
                    pairs=local_pairs,
                ),
                TermGroup(
                    "defect_stoichiometry",
                    "缺陷数量与化学计量",
                    "global_constraint",
                    defect_ids,
                ),
                TermGroup(
                    "coverage", "吸附覆盖度", "global_constraint", adsorption_ids
                ),
                TermGroup(
                    "allowed_combinations",
                    "允许的缺陷-吸附组合",
                    "pairwise_conflict",
                    pairs=forbidden_pairs,
                ),
            ),
            coefficient_contributions=builder.contributions,
            analog_candidate_group_ids=("local_conflicts",),
            geometry_evidence=geometry,
            metadata={
                "dataset_id": self.fixture.manifest["dataset_id"],
                "manifest_hash": self.fixture.manifest_hash,
                "scientific_boundary": "packaged_discrete_configuration_model_only",
            },
        )

    def decode(
        self,
        case_input: DefectAdsorptionInput,
        definition: OptimizationProblemDefinition,
        candidate: Any,
    ) -> MaterialSolution:
        decoded = getattr(candidate, "decoded", None)
        if decoded is not None and "binary_values" in decoded:
            values = {
                key: int(value) for key, value in decoded["binary_values"].items()
            }
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
        case_input: DefectAdsorptionInput,
        definition: OptimizationProblemDefinition,
        values: dict[str, int],
        *,
        bitstring: str | None = None,
    ) -> MaterialSolution:
        domain = self.fixture.domain
        model = domain["presets"][case_input.preset]
        defects = tuple(
            item["id"]
            for item in domain["defectCandidates"]
            if values.get(item["id"], 0) == 1
        )
        adsorptions = tuple(
            item["id"]
            for item in domain["adsorptionCandidates"]
            if values.get(item["id"], 0) == 1
        )
        selected = set((*defects, *adsorptions))
        local_violations = [
            pair
            for pair in domain["localConflictPairs"]
            if set(pair).issubset(selected)
        ]
        forbidden_violations = [
            pair
            for pair in model["forbiddenCombinations"]
            if set(pair).issubset(selected)
        ]
        checks = (
            {
                "id": "defect_stoichiometry",
                "label": "缺陷数量 / 化学计量",
                "passed": len(defects) == case_input.defect_count,
                "actual": len(defects),
                "expected": case_input.defect_count,
            },
            {
                "id": "adsorption_coverage",
                "label": "吸附覆盖度",
                "passed": len(adsorptions) == case_input.adsorption_count,
                "actual": len(adsorptions),
                "expected": case_input.adsorption_count,
            },
            {
                "id": "site_orientation_exclusion",
                "label": "同位点 / 同分子取向互斥",
                "passed": not local_violations,
                "actual": len(local_violations),
                "expected": 0,
            },
            {
                "id": "allowed_defect_adsorption",
                "label": "允许的缺陷-吸附组合",
                "passed": not forbidden_violations,
                "actual": len(forbidden_violations),
                "expected": 0,
            },
        )
        components = {
            "defectFormation": sum(
                float(model["defectFormation"][item]) for item in defects
            ),
            "adsorption": sum(
                float(model["adsorptionEnergy"][item]) for item in adsorptions
            ),
            "synergy": sum(
                float(coefficient)
                for left, right, coefficient in model["synergies"]
                if left in selected and right in selected
            ),
            "neighbor": sum(
                case_input.interaction_weight * float(coefficient)
                for left, right, coefficient in model["neighborInteractions"]
                if left in selected and right in selected
            ),
        }
        if bitstring is None:
            bitstring = "".join(
                str(int(values.get(variable, 0)))
                for variable in definition.problem.variables
            )
        return MaterialSolution(
            bitstring=bitstring,
            selected_defect_ids=defects,
            selected_adsorption_ids=adsorptions,
            model_objective=_qubo_value(definition.problem, values),
            physical_model_energy=sum(components.values()),
            energy_components=components,
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
    scenario: DefectAdsorptionScenario,
    case_input: DefectAdsorptionInput,
    definition: OptimizationProblemDefinition,
) -> tuple[MaterialSolution, ...]:
    solutions = []
    variables = tuple(definition.problem.variables)
    for bits in product((0, 1), repeat=len(variables)):
        solution = scenario.decode_values(
            case_input, definition, dict(zip(variables, bits))
        )
        if solution.feasible:
            solutions.append(solution)
    return tuple(
        sorted(solutions, key=lambda item: (item.model_objective, item.bitstring))
    )


def classic_material_solution(
    preset: str, values: dict[str, Any] | None = None
) -> MaterialSolution:
    scenario = DefectAdsorptionScenario()
    case_input = material_input(preset, material_values(preset, values or {}))
    definition = scenario.build_definition(case_input)
    return _classic_solutions(scenario, case_input, definition)[0]


def _mode_payload(decision: Any) -> dict[str, Any]:
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
                "diagnosticCodes": [
                    item.replace("FINANCE_", "MATERIALS_")
                    for item in row.diagnostic_codes
                ],
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
    scenario: DefectAdsorptionScenario,
    case_input: DefectAdsorptionInput,
    analysis: Any,
) -> dict[str, Any]:
    fixture = scenario.fixture
    domain = fixture.domain
    model = domain["presets"][case_input.preset]
    definition = analysis.definition
    canonical = analysis.problem_analysis.canonical_problem
    mapping = analysis.problem_analysis.mapping_plan
    defect_sites = {item["site"] for item in domain["defectCandidates"]}
    nodes = [
        {
            **item,
            "role": "defect_candidate"
            if item["id"] in defect_sites
            else "lattice_site",
        }
        for item in domain["latticeNodes"]
    ]
    payload = {
        "kind": "materials",
        "caseId": "defect_adsorption",
        "executionFamily": "problem",
        "implementationStatus": "available",
        "dataset": {
            "id": fixture.manifest["dataset_id"],
            "version": fixture.manifest["version"],
            "manifestHash": fixture.manifest_hash,
            "sourceKind": fixture.manifest["source"]["kind"],
            "license": fixture.manifest["source"]["license"],
            "sourceUri": fixture.manifest["source"]["uri"],
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
            "kind": "defect_adsorption",
            "modelLevel": domain["modelLevel"],
            "surface": model["surface"],
            "adsorbateLabel": model["adsorbate"],
            "nodes": nodes,
            "defectCandidates": domain["defectCandidates"],
            "adsorptionCandidates": domain["adsorptionCandidates"],
            "adsorbates": [
                {
                    "id": item["id"],
                    "site": item["site"],
                    "label": model["adsorbate"],
                    "orientation": item["orientation"],
                }
                for item in domain["adsorptionCandidates"]
            ],
            "periodicBoundary": domain["periodicBoundary"],
            "symmetryOperations": domain["symmetryOperations"],
            "localConflictPairs": domain["localConflictPairs"],
            "forbiddenCombinations": model["forbiddenCombinations"],
            "coordinateIdentities": {
                "material": {
                    "unit": "fractional_surface_cell",
                    "source": "fixture",
                },
                "effective": {
                    "unit": "logical_candidate_id",
                    "source": "symmetry_canonicalization",
                },
                "compiled": {
                    "unit": "um",
                    "source": "CASCAQit_mapping_plan",
                },
            },
            "targets": {
                "defectCount": case_input.defect_count,
                "coverage": case_input.coverage,
                "adsorptionCount": case_input.adsorption_count,
            },
            "energyModel": {
                "defectFormation": model["defectFormation"],
                "adsorption": model["adsorptionEnergy"],
                "synergies": model["synergies"],
                "neighborInteractions": model["neighborInteractions"],
                "interactionWeight": case_input.interaction_weight,
                "unit": "dimensionless educational energy",
            },
            "limitations": domain["limitations"],
        },
    }
    payload["analysisHash"] = hash_payload(payload)
    return payload


def analyze_defect_adsorption(preset: str, values: dict[str, Any]) -> dict[str, Any]:
    resolved = material_values(preset, values)
    scenario = DefectAdsorptionScenario()
    case_input = material_input(preset, resolved)
    analysis = ScenarioExecutor().analyze(scenario, case_input)
    return _analysis_payload(scenario, case_input, analysis)


def _solution_payload(solution: MaterialSolution, source: str) -> dict[str, Any]:
    return {
        "source": source,
        "bitstring": solution.bitstring,
        "selectedDefectIds": list(solution.selected_defect_ids),
        "selectedAdsorptionIds": list(solution.selected_adsorption_ids),
        "modelObjective": solution.model_objective,
        "physicalModelEnergy": solution.physical_model_energy,
        "energyComponents": solution.energy_components,
        "feasible": solution.feasible,
        "checks": list(solution.checks),
    }


def _reference_solution(
    scenario: DefectAdsorptionScenario,
    case_input: DefectAdsorptionInput,
    definition: OptimizationProblemDefinition,
) -> MaterialSolution:
    reference = scenario.fixture.reference["presets"][case_input.preset]
    selected = set((*reference["defectIds"], *reference["adsorptionIds"]))
    values = {
        variable: int(variable in selected) for variable in definition.problem.variables
    }
    return scenario.decode_values(case_input, definition, values)


def _waveforms(program: dict[str, Any] | None) -> dict[str, list[dict[str, float]]]:
    if program is None:
        return {name: [] for name in ("rabi", "detuning", "phase")}
    terms = program.get("hamiltonian", {}).get("terms", {})
    output: dict[str, list[dict[str, float]]] = {}
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


def _quantum_payload(result: Any, candidate: MaterialSolution) -> dict[str, Any]:
    native = result.execution.context.native_program.to_dict()
    circuits: list[dict[str, Any]] = []
    blocks: list[str] = []
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
    selected = set((*candidate.selected_defect_ids, *candidate.selected_adsorption_ids))
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
        "circuit": {
            "qubits": list(result.execution.logical_order),
            "gates": gates,
            "depth": len(gates),
        },
        "atoms": [
            {
                "id": site.logical_id,
                "x": float(site.position[0]),
                "y": float(site.position[1]),
                "selected": site.logical_id in selected,
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
            "qubits": len(result.execution.logical_order),
            "shots": result.execution.result.shots,
            "evaluations": len(result.execution.parameter_history),
        },
    }


def run_defect_adsorption(
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
    resolved = material_values(preset, values)
    scenario = DefectAdsorptionScenario()
    case_input = material_input(preset, resolved)
    result = ScenarioExecutor().run(
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
    observed_by_state: dict[str, MaterialSolution] = {}
    feasible_shots = 0
    for state, count in result.execution.result.counts.items():
        decoded = scenario.decode_values(
            case_input,
            definition,
            dict(zip(definition.problem.variables, (int(bit) for bit in state))),
            bitstring=state,
        )
        if decoded.feasible:
            observed_by_state[state] = decoded
            feasible_shots += int(count)
    observed = sorted(
        observed_by_state.values(),
        key=lambda item: (item.model_objective, item.bitstring),
    )
    sampled = result.business_candidate
    quantum_candidate = (
        _solution_payload(sampled, "quantum_observed") if sampled.feasible else None
    )
    analysis = _analysis_payload(scenario, case_input, result.analysis)
    payload = {
        "kind": "materials",
        "analysis": analysis,
        "domain": {
            "kind": "defect_adsorption_result",
            "quantumStatus": "observed_feasible"
            if quantum_candidate is not None
            else "quantum_not_observed",
            "quantumCandidate": quantum_candidate,
            "bestObservedRaw": _solution_payload(sampled, "quantum_observed_raw"),
            "classicOptimum": _solution_payload(classic[0], "complete_enumeration"),
            "offlineReference": _solution_payload(reference, "offline_reference"),
            "topObservedFeasible": [
                _solution_payload(item, "quantum_observed") for item in observed[:5]
            ],
            "observedFeasibleCount": len(observed),
            "feasibleShotRatio": feasible_shots / shots,
            "interpretation": (
                "给定版本化离散模型内的无量纲构型目标；不表示催化活性、速率、"
                "选择性或可合成性。QAOA counts 仅为观测频次。"
            ),
        },
        "quantum": _quantum_payload(result, sampled),
        "audit": {
            "domainId": "materials",
            "caseId": "defect_adsorption",
            "datasetId": scenario.fixture.manifest["dataset_id"],
            "datasetVersion": scenario.fixture.manifest["version"],
            "manifestHash": scenario.fixture.manifest_hash,
            "domainInputHash": hash_payload(asdict(case_input)),
            "problemHash": result.execution.problem_hash,
            "analysisHash": result.execution.analysis_hash,
            "compileHash": result.execution.compile_hash,
            "executionHash": result.execution.execution_hash,
            "resultHash": result.evidence.result_hash,
            "backend": local_backend_context(
                execution_family="problem_qaoa",
                mode=result.mode,
                simulation_method=(
                    "hybrid_state_vector" if result.mode == "hybrid" else "state_vector"
                ),
            ),
            "seed": seed,
            "shots": shots,
            "hardwareExecution": False,
            "cloudExecution": False,
            "networkAccessed": False,
            "wallTimeSeconds": result.evidence.wall_time_seconds,
            "optimalityClaim": result.execution.optimality_claim,
            "claimBoundary": "packaged_discrete_material_configuration",
            "configurationSchema": "materials.execution-configuration.v1",
            "outcomeSchema": "materials.execution-outcome.v1",
            "reportSchema": "materials.execution-report.v1",
        },
    }
    finalize_stable_audit(
        payload["audit"],
        configuration={
            "input": asdict(case_input),
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
    payload["audit"]["resultPresentationHash"] = hash_payload(payload["domain"])
    return payload
