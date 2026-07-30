"""Capability, complexity, and planning contracts for advanced experiments."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, Optional

import cascaqit
from packaging.version import InvalidVersion, Version

CapabilityStatus = Literal["available", "unavailable"]
ProfileStatus = Literal["available", "planned"]
ExperimentLevel = Literal["standard", "advanced"]
ExecutionPolicy = Literal["sync", "job", "rejected"]


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class Capability:
    capability_id: str
    label: str
    layer: Literal["sdk", "application", "sdk_application"]
    status: CapabilityStatus
    reason: str
    contract_tests: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.capability_id,
            "label": self.label,
            "layer": self.layer,
            "status": self.status,
            "reason": self.reason,
            "contractTests": list(self.contract_tests),
        }


class CapabilityRegistry:
    """Declare verified capabilities instead of inferring them from imports."""

    def __init__(self, sdk_version: Optional[str] = None) -> None:  # noqa: UP045
        self.sdk_version = sdk_version or str(
            getattr(cascaqit, "__version__", "unknown")
        )
        self._validated_sdk = self._is_validated_sdk(self.sdk_version)

    @staticmethod
    def _is_validated_sdk(version: str) -> bool:
        try:
            parsed = Version(version)
        except InvalidVersion:
            return False
        return Version("1.0.5a0") <= parsed < Version("1.0.6")

    def capabilities(self) -> tuple[Capability, ...]:
        sdk_status: CapabilityStatus = (
            "available" if self._validated_sdk else "unavailable"
        )
        sdk_reason = (
            f"CASCAQit {self.sdk_version} is in the validated 1.0.5 series."
            if self._validated_sdk
            else (
                f"CASCAQit {self.sdk_version} is outside the validated "
                "1.0.5 release series."
            )
        )
        return (
            Capability(
                "pauli_vqe",
                "Pauli Hamiltonian / Digital VQE",
                "sdk",
                sdk_status,
                sdk_reason,
                (
                    "test_variational_algorithms.py",
                    "test_biomedicine_electronic_structure.py",
                ),
            ),
            Capability(
                "qwc_measurement",
                "QWC grouped measurement",
                "sdk",
                sdk_status,
                sdk_reason,
                ("test_biomedicine_electronic_structure.py",),
            ),
            Capability(
                "digital_qaoa",
                "Digital QAOA",
                "sdk",
                sdk_status,
                sdk_reason,
                (
                    "test_biomedicine_peptide_landscape.py",
                    "test_biomedicine_rna_structure.py",
                ),
            ),
            Capability(
                "hybrid_dad",
                "Hybrid Digital-Analog-Digital QAOA",
                "sdk_application",
                sdk_status,
                sdk_reason,
                ("test_biomedicine_docking.py",),
            ),
            Capability(
                "experiment_planning",
                "Advanced experiment planning",
                "application",
                "available",
                "Complexity profiles, deterministic plans, and cost gates are enabled.",
                ("test_advanced_experiments.py",),
            ),
            Capability(
                "batch_execution",
                "Batch and sweep execution",
                "application",
                "available",
                "Persistent bounded local jobs execute independent run units.",
                ("test_local_jobs.py", "test_industry_domain_api.py"),
            ),
            Capability(
                "running_cancellation",
                "Cooperative cancellation of running jobs",
                "sdk_application",
                "unavailable",
                "CASCAQit optimizer and Backend checkpoints are not available.",
            ),
            Capability(
                "quantum_excited_states",
                "VQD or subspace excited-state algorithms",
                "sdk",
                "unavailable",
                "No released and validated excited-state result contract exists.",
            ),
            Capability(
                "constraint_preserving_mixer",
                "Constraint-preserving QAOA mixer",
                "sdk",
                "unavailable",
                "The released QAOA path uses penalty QUBO encoding.",
            ),
        )

    def is_available(self, capability_id: str) -> bool:
        return any(
            item.capability_id == capability_id and item.status == "available"
            for item in self.capabilities()
        )

    def to_dict(self) -> dict[str, Any]:
        capabilities = self.capabilities()
        return {
            "sdk": {
                "name": "CASCAQit",
                "version": self.sdk_version,
                "validatedRelease": self._validated_sdk,
                "validatedRange": ">=1.0.5a0,<1.0.6",
            },
            "capabilities": [item.to_dict() for item in capabilities],
        }


@dataclass(frozen=True)
class ComplexityProfile:
    case_id: str
    profile_id: str
    level: Literal["standard", "advanced_live", "research"]
    status: ProfileStatus
    max_logical_qubits: int
    max_problem_variables: int
    max_operator_terms: int
    max_measurement_groups: int
    max_shots: int
    max_objective_evaluations: int
    max_estimated_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "profileId": self.profile_id,
            "level": self.level,
            "status": self.status,
            "limits": {
                "logicalQubits": self.max_logical_qubits,
                "problemVariables": self.max_problem_variables,
                "operatorTerms": self.max_operator_terms,
                "measurementGroups": self.max_measurement_groups,
                "shots": self.max_shots,
                "objectiveEvaluations": self.max_objective_evaluations,
                "estimatedSeconds": self.max_estimated_seconds,
            },
        }


_STANDARD_LIMITS: dict[str, tuple[int, int, int, int]] = {
    "electronic_structure": (4, 0, 256, 64),
    "docking_match": (0, 12, 128, 0),
    "active_center": (2, 0, 16, 8),
    "peptide_landscape": (0, 16, 256, 0),
    "rna_structure": (0, 16, 256, 0),
    "protein_dynamics": (0, 16, 256, 0),
}

_ADVANCED_LIVE_AVAILABLE_CASES = {
    "electronic_structure",
    "docking_match",
    "active_center",
    "peptide_landscape",
}
_ADVANCED_PRESETS = {
    "electronic_structure": {"lih_potential_scan"},
    "docking_match": {
        "multi_pose_balanced",
        "multi_pose_geometry",
        "multi_pose_coverage",
    },
    "active_center": {"trinuclear_frustrated", "tetranuclear_ligand_field"},
    "peptide_landscape": {
        "octapeptide_hydrophobic",
        "octapeptide_charge_shift",
        "octapeptide_mutation",
    },
}


def profiles_for(case_id: str) -> tuple[ComplexityProfile, ...]:
    try:
        qubits, variables, terms, groups = _STANDARD_LIMITS[case_id]
    except KeyError as exc:
        raise ValueError(f"unknown biomedicine scenario: {case_id}") from exc
    return (
        ComplexityProfile(
            case_id,
            "standard",
            "standard",
            "available",
            qubits,
            variables,
            terms,
            groups,
            1024,
            80,
            30.0,
        ),
        ComplexityProfile(
            case_id,
            "advanced_live",
            "advanced_live",
            "available" if case_id in _ADVANCED_LIVE_AVAILABLE_CASES else "planned",
            6 if qubits else 0,
            16 if variables else 0,
            512,
            128 if qubits else 0,
            1024,
            80,
            60.0,
        ),
        ComplexityProfile(
            case_id,
            "research",
            "research",
            "planned",
            8 if qubits else 0,
            20 if variables else 0,
            1024,
            256 if qubits else 0,
            1024,
            80,
            300.0,
        ),
    )


def catalog_experiment_metadata(case_id: str) -> dict[str, Any]:
    return {
        "experimentLevels": ["standard", "advanced"],
        "complexityProfiles": [item.to_dict() for item in profiles_for(case_id)],
    }


def _resolve_profile(
    case_id: str,
    experiment_level: ExperimentLevel,
    requested_profile: Optional[str],  # noqa: UP045
) -> ComplexityProfile:
    profile_id = requested_profile or (
        "standard" if experiment_level == "standard" else "advanced_live"
    )
    profiles = {item.profile_id: item for item in profiles_for(case_id)}
    try:
        profile = profiles[profile_id]
    except KeyError as exc:
        raise ValueError(f"unknown complexity profile: {profile_id}") from exc
    if experiment_level == "standard" and profile.level != "standard":
        raise ValueError("standard experiment level requires the standard profile")
    if experiment_level == "advanced" and profile.level == "standard":
        raise ValueError("advanced experiment level requires an advanced profile")
    return profile


def _resource_snapshot(analysis: dict[str, Any]) -> dict[str, int]:
    resource = analysis.get("resource", {})
    problem = analysis.get("problem", {})
    variables = problem.get("variables", [])
    terms = problem.get("terms", [])
    return {
        "logicalQubits": int(resource.get("logicalQubits", 0)),
        "problemVariables": int(
            resource.get("logical_variables", len(variables) if variables else 0)
        ),
        "operatorTerms": int(
            resource.get(
                "termCount",
                resource.get("logical_terms", len(terms) if terms else 0),
            )
        ),
        "measurementGroups": int(resource.get("measurementGroups", 0)),
    }


def _diagnostic(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message, "stage": "planning"}


def _configuration_cost(
    configuration: dict[str, Any],
    recommended: dict[str, Any],
    baseline_seconds: float,
) -> float:
    shots = int(configuration.get("shots", recommended.get("shots", 64)))
    budget = int(
        configuration.get("parameter_budget", recommended.get("parameterBudget", 1))
    )
    starts = int(
        configuration.get("optimizer_starts", recommended.get("optimizerStarts", 1))
    )
    layers = int(configuration.get("layers", recommended.get("layers", 1)))
    ratios = (
        shots / max(1, int(recommended.get("shots", 64))),
        budget / max(1, int(recommended.get("parameterBudget", 1))),
        starts / max(1, int(recommended.get("optimizerStarts", 1))),
        layers / max(1, int(recommended.get("layers", 1))),
    )
    multiplier = 1.0
    for ratio in ratios:
        multiplier *= max(0.01, ratio)
    return baseline_seconds * multiplier


def build_experiment_plan(
    *,
    case_id: str,
    preset: str,
    experiment_level: ExperimentLevel,
    requested_profile: Optional[str],  # noqa: UP045
    analysis_points: list[tuple[dict[str, Any], dict[str, Any]]],
    configurations: list[dict[str, Any]],
    seeds: list[int],
    recommended_execution: dict[str, Any],
    capabilities: Optional[CapabilityRegistry] = None,  # noqa: UP045
) -> dict[str, Any]:
    """Build a deterministic, non-executing plan with explicit cost gates."""

    if not analysis_points:
        raise ValueError("experiment plan requires at least one analysis point")
    profile = _resolve_profile(case_id, experiment_level, requested_profile)
    registry = capabilities or CapabilityRegistry()
    normalized_configurations = configurations or [
        {
            "mode": "recommended",
            "algorithm": recommended_execution.get("algorithm", "recommended"),
            "layers": int(recommended_execution.get("layers", 1)),
            "shots": int(recommended_execution.get("shots", 64)),
            "parameter_budget": int(recommended_execution.get("parameterBudget", 1)),
            "optimizer_starts": int(recommended_execution.get("optimizerStarts", 1)),
        }
    ]
    normalized_seeds = seeds or [int(recommended_execution.get("seed", 23))]
    diagnostics: list[dict[str, str]] = []
    if profile.status != "available":
        diagnostics.append(
            _diagnostic(
                "COMPLEXITY_PROFILE_NOT_AVAILABLE",
                f"complexity profile {profile.profile_id} is planned but not released",
            )
        )
    if experiment_level == "advanced" and preset not in _ADVANCED_PRESETS.get(
        case_id, set()
    ):
        diagnostics.append(
            _diagnostic(
                "ADVANCED_PRESET_REQUIRED",
                f"preset {preset} is not registered for advanced experiments",
            )
        )

    execution_family = str(analysis_points[0][1].get("executionFamily", ""))
    required_capability = (
        "pauli_vqe" if execution_family == "pauli_vqe" else "digital_qaoa"
    )
    if execution_family not in {"pauli_vqe", "problem"}:
        diagnostics.append(
            _diagnostic(
                "EXECUTION_FAMILY_UNSUPPORTED",
                f"unsupported execution family: {execution_family or 'missing'}",
            )
        )
    elif not registry.is_available(required_capability):
        diagnostics.append(
            _diagnostic(
                "SDK_CAPABILITY_NOT_AVAILABLE",
                f"required capability {required_capability} is not available",
            )
        )
    if any(item.get("mode") == "hybrid" for item in normalized_configurations) and not (
        registry.is_available("hybrid_dad")
    ):
        diagnostics.append(
            _diagnostic(
                "HYBRID_CAPABILITY_NOT_AVAILABLE",
                "Hybrid D-A-D is not available in the validated SDK capability set",
            )
        )

    point_payloads = []
    limit_codes = {
        "logicalQubits": "LOGICAL_QUBITS_LIMIT_EXCEEDED",
        "problemVariables": "PROBLEM_VARIABLES_LIMIT_EXCEEDED",
        "operatorTerms": "OPERATOR_TERMS_LIMIT_EXCEEDED",
        "measurementGroups": "MEASUREMENT_GROUPS_LIMIT_EXCEEDED",
    }
    for index, (values, analysis) in enumerate(analysis_points):
        snapshot = _resource_snapshot(analysis)
        limits = {
            "logicalQubits": profile.max_logical_qubits,
            "problemVariables": profile.max_problem_variables,
            "operatorTerms": profile.max_operator_terms,
            "measurementGroups": profile.max_measurement_groups,
        }
        for key, limit in limits.items():
            actual = snapshot[key]
            if limit and actual > limit:
                diagnostics.append(
                    _diagnostic(
                        limit_codes[key],
                        f"{key}={actual} exceeds profile limit {limit}",
                    )
                )
        point_payloads.append(
            {
                "index": index,
                "values": values,
                "dataset": analysis["dataset"],
                "analysisHash": analysis.get("analysisHash"),
                "problemHash": analysis["problem"]["hash"],
                "completeDomainProblemHash": analysis["problem"].get(
                    "completeDomainProblemHash", analysis["problem"]["hash"]
                ),
                "quantumSubproblemHash": analysis["problem"].get(
                    "quantumSubproblemHash", analysis["problem"]["hash"]
                ),
                "resource": snapshot,
            }
        )

    for configuration in normalized_configurations:
        mode = str(configuration.get("mode", "recommended"))
        algorithm = str(
            configuration.get(
                "algorithm", recommended_execution.get("algorithm", "recommended")
            )
        )
        allowed_modes = (
            {"recommended", "digital", "hybrid"}
            if case_id == "docking_match"
            else {"recommended", "digital"}
        )
        expected_algorithm = (
            "qaoa"
            if case_id in {"docking_match", "peptide_landscape", "rna_structure"}
            else "vqe"
        )
        if mode not in allowed_modes:
            diagnostics.append(
                _diagnostic(
                    "EXECUTION_MODE_UNSUPPORTED",
                    f"mode {mode} is not supported by scenario {case_id}",
                )
            )
        if algorithm not in {"recommended", expected_algorithm}:
            diagnostics.append(
                _diagnostic(
                    "ALGORITHM_UNSUPPORTED",
                    f"algorithm {algorithm} is not supported by scenario {case_id}",
                )
            )
        shots = int(configuration.get("shots", recommended_execution.get("shots", 64)))
        budget = int(
            configuration.get(
                "parameter_budget", recommended_execution.get("parameterBudget", 1)
            )
        )
        if shots > profile.max_shots:
            diagnostics.append(
                _diagnostic(
                    "SHOTS_LIMIT_EXCEEDED",
                    f"shots={shots} exceeds profile limit {profile.max_shots}",
                )
            )
        if budget > profile.max_objective_evaluations:
            diagnostics.append(
                _diagnostic(
                    "OBJECTIVE_EVALUATION_LIMIT_EXCEEDED",
                    f"parameter_budget={budget} exceeds profile limit "
                    f"{profile.max_objective_evaluations}",
                )
            )

    run_count = (
        len(point_payloads) * len(normalized_configurations) * len(normalized_seeds)
    )
    baseline_seconds = float(recommended_execution.get("estimatedSeconds", 1.0))
    per_configuration_seconds = [
        _configuration_cost(item, recommended_execution, baseline_seconds)
        for item in normalized_configurations
    ]
    max_unit_seconds = max(per_configuration_seconds)
    estimated_seconds = (
        sum(per_configuration_seconds) * len(point_payloads) * len(normalized_seeds)
    )
    if max_unit_seconds > profile.max_estimated_seconds:
        diagnostics.append(
            _diagnostic(
                "ESTIMATED_COST_LIMIT_EXCEEDED",
                f"estimated unit cost {max_unit_seconds:.3f}s exceeds profile limit "
                f"{profile.max_estimated_seconds:.3f}s",
            )
        )
    if run_count > 1 and not registry.is_available("batch_execution"):
        diagnostics.append(
            _diagnostic(
                "BATCH_EXECUTION_NOT_AVAILABLE",
                "multi-run plans require the persistent local job manager",
            )
        )

    if diagnostics:
        execution_policy: ExecutionPolicy = "rejected"
    elif run_count == 1 and profile.level != "research":
        execution_policy = "sync"
    else:
        execution_policy = "job"

    complete_hash = _stable_hash(
        [
            {
                "values": item["values"],
                "dataset": item["dataset"],
                "problemHash": item["completeDomainProblemHash"],
            }
            for item in point_payloads
        ]
    )
    subproblem_hash = _stable_hash(
        {
            "selectionRule": "identity.v1",
            "problemHashes": [item["quantumSubproblemHash"] for item in point_payloads],
        }
    )
    plan_identity = {
        "caseId": case_id,
        "preset": preset,
        "experimentLevel": experiment_level,
        "profileId": profile.profile_id,
        "completeDomainProblemHash": complete_hash,
        "quantumSubproblemHash": subproblem_hash,
        "points": point_payloads,
        "configurations": normalized_configurations,
        "seeds": normalized_seeds,
        "runCount": run_count,
        "estimatedSeconds": estimated_seconds,
        "executionPolicy": execution_policy,
        "diagnostics": diagnostics,
    }
    return {
        "planId": _stable_hash(plan_identity),
        **plan_identity,
        "profile": profile.to_dict(),
        "maxUnitEstimatedSeconds": max_unit_seconds,
        "capabilitySnapshot": registry.to_dict(),
    }
