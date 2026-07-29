"""Domain-neutral contracts shared by industry QUBO execution paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

ProblemMode = Literal["digital", "hybrid", "analog"]
ProblemAlgorithm = Literal["qaoa", "vqe", "qaa"]
RequestedAlgorithm = Literal["recommended", "qaoa", "vqe", "qaa"]
LayerPolicy = Literal["fixed", "adaptive"]
ModeStatus = Literal["recommended", "comparable", "unsuitable"]
GeometryStatus = Literal["verified", "missing", "distorted"]
GeometrySource = Literal["business_native", "verified_embedding"]


class ProblemDefinition(Protocol):
    """Structural contract consumed by the shared compiler and mode advisor."""

    case_id: str
    title: str
    problem: Any
    business_variables: tuple[str, ...]
    analog_candidate_group_ids: tuple[str, ...]
    digital_algorithms: tuple[Literal["qaoa", "vqe"], ...]
    published_digital_algorithms: tuple[Literal["qaoa", "vqe"], ...]
    vqe_ansatz: Any | None
    geometry_evidence: Any | None

    @property
    def analog_business_pairs(self) -> tuple[tuple[str, str], ...]: ...

    @property
    def analog_candidate_groups(self) -> tuple[Any, ...]: ...


class ProblemScenario(Protocol):
    """Minimum domain behavior required by the shared Problem executor."""

    case_id: str
    title: str

    def default_input(self) -> Any: ...

    def validate(self, case_input: Any) -> tuple[Any, ...]: ...

    def build_definition(self, case_input: Any) -> ProblemDefinition: ...

    def decode(
        self, case_input: Any, definition: ProblemDefinition, candidate: Any
    ) -> Any: ...


@dataclass(frozen=True)
class ModeDecisionRow:
    mode: ProblemMode
    algorithm: ProblemAlgorithm
    available_algorithms: tuple[ProblemAlgorithm, ...]
    status: ModeStatus
    compiler_feasible: bool
    business_suitable: bool
    reason: str
    diagnostic_codes: tuple[str, ...] = ()
    analog_business_pairs: tuple[tuple[str, str], ...] = ()
    covered_group_ids: tuple[str, ...] = ()
    missing_contribution_ids: tuple[str, ...] = ()
    unexpected_analog_term_ids: tuple[str, ...] = ()
    unexpected_interaction_pairs: tuple[tuple[str, str], ...] = ()
    geometry_status: GeometryStatus = "missing"
    geometry_source: GeometrySource | None = None
    layout_policy: str = "unavailable"
    declared_contribution_count: int = 0
    covered_contribution_count: int = 0
    analog_term_count: int = 0
    digital_term_count: int = 0


@dataclass(frozen=True)
class ModeDecision:
    recommended_mode: ProblemMode
    reason: str
    rows: tuple[ModeDecisionRow, ...]

    def for_mode(self, mode: ProblemMode) -> ModeDecisionRow:
        for row in self.rows:
            if row.mode == mode:
                return row
        raise ValueError(f"unknown Problem mode: {mode!r}")


@dataclass(frozen=True)
class ScenarioAnalysis:
    definition: ProblemDefinition
    problem_analysis: Any
    mode_decision: ModeDecision


@dataclass(frozen=True)
class AlgorithmPlan:
    requested_algorithm: RequestedAlgorithm
    resolved_algorithm: ProblemAlgorithm
    problem_hash: str
    layer_policy: LayerPolicy
    requested_layers: int
    max_layers: int
    min_improvement: float
    search_strategy: str
    parameter_budget: int
    optimizer_method: str | None
    per_start_evaluation_budget: int | None
    optimizer_starts: int
    ansatz: Any | None = None


@dataclass(frozen=True)
class ExecutionEvidence:
    backend: str
    execution_kind: str
    result_hash: str
    seed: int
    shots: int
    wall_time_seconds: float
    hardware_execution: bool
    cloud_execution: bool
    network_accessed: bool


@dataclass(frozen=True)
class ExperimentResult:
    case_id: str
    mode: ProblemMode
    algorithm_plan: AlgorithmPlan
    definition: ProblemDefinition
    analysis: ScenarioAnalysis
    execution: Any
    business_candidate: Any
    baseline_solution: Any | None
    displayed_solution: Any
    evidence: ExecutionEvidence
    layer_experiment: Any | None = None
    report_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RepeatedExperimentResult:
    representative: ExperimentResult
    runs: tuple[ExperimentResult, ...]
    representative_index: int
    confidence_level: float = 0.95


@dataclass(frozen=True)
class LayerCalibrationResult:
    mode: ProblemMode
    algorithm_plan: AlgorithmPlan
    analysis: ScenarioAnalysis
    experiment: Any
    business_candidates: tuple[Any, ...]

    @property
    def feasible_count(self) -> int:
        return sum(
            bool(getattr(candidate, "feasible", True))
            for candidate in self.business_candidates
        )

    @property
    def feasible_rate(self) -> float:
        return self.feasible_count / len(self.business_candidates)
