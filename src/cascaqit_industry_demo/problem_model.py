"""Domain-neutral QUBO semantics shared by industry optimization demos."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal

from cascaqit import QUBOProblemIR

TermKind = Literal[
    "objective",
    "pairwise_conflict",
    "global_constraint",
    "dependency",
    "auxiliary_penalty",
]
CoefficientTermKind = Literal["offset", "linear", "quadratic"]
CoefficientRole = Literal["objective", "constraint", "auxiliary"]


@dataclass(frozen=True)
class CoefficientContribution:
    """One domain rule's contribution to a canonical QUBO coefficient."""

    contribution_id: str
    group_id: str
    source_rule: str
    term_kind: CoefficientTermKind
    targets: tuple[str, ...]
    coefficient: float
    role: CoefficientRole

    def __post_init__(self) -> None:
        expected = {"offset": 0, "linear": 1, "quadratic": 2}[self.term_kind]
        targets = tuple(self.targets)
        if len(targets) != expected:
            raise ValueError(f"{self.term_kind} contribution target count is invalid")
        if self.term_kind == "quadratic":
            if targets[0] == targets[1]:
                raise ValueError("quadratic contribution targets must differ")
            targets = tuple(sorted(targets))
        if not math.isfinite(float(self.coefficient)):
            raise ValueError("contribution coefficient must be finite")
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "coefficient", float(self.coefficient))

    @property
    def canonical_term_id(self) -> str:
        if self.term_kind == "offset":
            return "offset"
        return ".".join((self.term_kind, *self.targets))


@dataclass(frozen=True)
class TermGroup:
    group_id: str
    label: str
    kind: TermKind
    variables: tuple[str, ...] = ()
    pairs: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "variables", tuple(self.variables))
        object.__setattr__(
            self,
            "pairs",
            tuple(tuple(sorted(pair)) for pair in self.pairs),
        )


@dataclass(frozen=True)
class GeometryEvidence:
    source: Literal["business_native", "verified_embedding"]
    coordinate_unit: str
    positions: tuple[tuple[str, tuple[float, float]], ...]
    expected_interactions: tuple[tuple[str, str], ...]
    forbidden_interactions: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "positions", tuple(sorted(self.positions)))
        object.__setattr__(
            self,
            "expected_interactions",
            tuple(sorted(tuple(sorted(pair)) for pair in self.expected_interactions)),
        )
        object.__setattr__(
            self,
            "forbidden_interactions",
            tuple(sorted(tuple(sorted(pair)) for pair in self.forbidden_interactions)),
        )


@dataclass(frozen=True)
class OptimizationProblemDefinition:
    """A QUBO plus domain variables, coefficient ledger, and geometry evidence."""

    case_id: str
    title: str
    problem_kind: Literal["qubo"]
    problem: QUBOProblemIR
    business_variables: tuple[str, ...]
    auxiliary_variables: tuple[str, ...] = ()
    term_groups: tuple[TermGroup, ...] = ()
    coefficient_contributions: tuple[CoefficientContribution, ...] = ()
    analog_candidate_group_ids: tuple[str, ...] = ()
    digital_algorithms: tuple[Literal["qaoa", "vqe"], ...] = ("qaoa",)
    published_digital_algorithms: tuple[Literal["qaoa", "vqe"], ...] = ("qaoa",)
    vqe_ansatz: None = None
    geometry_evidence: GeometryEvidence | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        groups = {group.group_id for group in self.term_groups}
        if len(groups) != len(self.term_groups):
            raise ValueError("term group IDs must be unique")
        if not self.coefficient_contributions:
            raise ValueError(
                "industry QUBO definitions require a coefficient ledger"
            )
        if any(item.group_id not in groups for item in self.coefficient_contributions):
            raise ValueError(
                "coefficient contribution references an unknown term group"
            )
        _require_ledger_conservation(self.problem, self.coefficient_contributions)

    @property
    def analog_business_pairs(self) -> tuple[tuple[str, str], ...]:
        selected = set(self.analog_candidate_group_ids)
        return tuple(
            sorted(
                {
                    tuple(sorted(pair))
                    for group in self.term_groups
                    if group.group_id in selected
                    for pair in group.pairs
                }
            )
        )

    @property
    def analog_candidate_groups(self) -> tuple[TermGroup, ...]:
        selected = set(self.analog_candidate_group_ids)
        return tuple(group for group in self.term_groups if group.group_id in selected)


def _require_ledger_conservation(
    problem: QUBOProblemIR,
    contributions: tuple[CoefficientContribution, ...],
) -> None:
    expected = {"offset": float(problem.offset)}
    expected.update(
        {f"linear.{variable}": float(value) for variable, value in problem.linear_terms}
    )
    expected.update(
        {
            f"quadratic.{left}.{right}": float(value)
            for left, right, value in problem.quadratic_terms
        }
    )
    actual: dict[str, float] = {}
    for item in contributions:
        actual[item.canonical_term_id] = (
            actual.get(item.canonical_term_id, 0.0) + item.coefficient
        )
    mismatches = [
        term_id
        for term_id in sorted(set(expected) | set(actual))
        if not math.isclose(
            expected.get(term_id, 0.0),
            actual.get(term_id, 0.0),
            rel_tol=1e-10,
            abs_tol=1e-10,
        )
    ]
    if mismatches:
        raise ValueError("QUBO coefficient ledger mismatch: " + ", ".join(mismatches))


class QuboBuilder:
    """Small deterministic QUBO builder with a source contribution ledger."""

    def __init__(self, variables: tuple[str, ...] = ()) -> None:
        self._variables = {name: None for name in variables}
        self._linear: dict[str, float] = {}
        self._quadratic: dict[tuple[str, str], float] = {}
        self._offset = 0.0
        self._contributions: list[CoefficientContribution] = []
        self._ids: set[str] = set()

    @property
    def variables(self) -> tuple[str, ...]:
        return tuple(sorted(self._variables))

    @property
    def contributions(self) -> tuple[CoefficientContribution, ...]:
        return tuple(self._contributions)

    def add_linear(
        self,
        variable: str,
        coefficient: float,
        *,
        contribution_id: str,
        group_id: str,
        source_rule: str,
        role: CoefficientRole,
    ) -> None:
        self._variables[variable] = None
        value = float(coefficient)
        self._linear[variable] = self._linear.get(variable, 0.0) + value
        self._record(
            contribution_id,
            group_id,
            source_rule,
            "linear",
            (variable,),
            value,
            role,
        )

    def add_quadratic(
        self,
        left: str,
        right: str,
        coefficient: float,
        *,
        contribution_id: str,
        group_id: str,
        source_rule: str,
        role: CoefficientRole,
    ) -> None:
        self._variables[left] = self._variables[right] = None
        value = float(coefficient)
        if left == right:
            self._linear[left] = self._linear.get(left, 0.0) + value
            kind: CoefficientTermKind = "linear"
            targets = (left,)
        else:
            targets = tuple(sorted((left, right)))
            self._quadratic[targets] = self._quadratic.get(targets, 0.0) + value
            kind = "quadratic"
        self._record(
            contribution_id,
            group_id,
            source_rule,
            kind,
            targets,
            value,
            role,
        )

    def add_squared_equality(
        self,
        coefficients: Mapping[str, float],
        *,
        rhs: float,
        penalty: float,
        contribution_id_prefix: str,
        group_id: str,
        source_rule: str,
        role: CoefficientRole = "constraint",
    ) -> None:
        items = tuple(
            sorted((key, float(value)) for key, value in coefficients.items())
        )
        for variable, weight in items:
            self.add_linear(
                variable,
                penalty * (weight * weight - 2.0 * rhs * weight),
                contribution_id=f"{contribution_id_prefix}:linear:{variable}",
                group_id=group_id,
                source_rule=source_rule,
                role=role,
            )
        for index, (left, left_weight) in enumerate(items):
            for right, right_weight in items[index + 1 :]:
                self.add_quadratic(
                    left,
                    right,
                    2.0 * penalty * left_weight * right_weight,
                    contribution_id=f"{contribution_id_prefix}:quadratic:{left}:{right}",
                    group_id=group_id,
                    source_rule=source_rule,
                    role=role,
                )
        offset = penalty * rhs * rhs
        self._offset += offset
        self._record(
            f"{contribution_id_prefix}:offset",
            group_id,
            source_rule,
            "offset",
            (),
            offset,
            role,
        )

    def build(self, *, problem_id: str, metadata: Mapping[str, Any]) -> QUBOProblemIR:
        payload = dict(metadata)
        payload["coefficient_contributions"] = [
            asdict(item) for item in self._contributions
        ]
        return QUBOProblemIR.from_terms(
            problem_id=problem_id,
            variables=self.variables,
            linear_terms={k: v for k, v in self._linear.items() if abs(v) > 1e-14},
            quadratic_terms={
                k: v for k, v in self._quadratic.items() if abs(v) > 1e-14
            },
            offset=self._offset,
            metadata=payload,
        )

    def _record(
        self,
        contribution_id: str,
        group_id: str,
        source_rule: str,
        term_kind: CoefficientTermKind,
        targets: tuple[str, ...],
        coefficient: float,
        role: CoefficientRole,
    ) -> None:
        if contribution_id in self._ids:
            raise ValueError(f"duplicate contribution ID: {contribution_id}")
        self._ids.add(contribution_id)
        self._contributions.append(
            CoefficientContribution(
                contribution_id,
                group_id,
                source_rule,
                term_kind,
                targets,
                coefficient,
                role,
            )
        )


def with_isolated_pair_geometry(
    problem: QUBOProblemIR,
    pairs: tuple[tuple[str, str], ...],
) -> tuple[QUBOProblemIR, GeometryEvidence]:
    """Bind four disjoint conflict pairs to an exact 6/28 micrometer layout."""
    normalized = tuple(sorted(tuple(sorted(pair)) for pair in pairs))
    endpoints = tuple(variable for pair in normalized for variable in pair)
    if len(endpoints) != len(set(endpoints)):
        raise ValueError("isolated-pair geometry requires disjoint conflict pairs")
    units: list[tuple[str, ...]] = [tuple(pair) for pair in normalized]
    units.extend((item,) for item in sorted(set(problem.variables) - set(endpoints)))
    if len(units) > 16:
        raise ValueError("isolated-pair geometry supports at most 16 layout units")
    axis = (-42.0, -14.0, 14.0, 42.0)
    positions: dict[str, tuple[float, float]] = {}
    for index, unit in enumerate(units):
        center = (axis[index % 4], axis[index // 4])
        if len(unit) == 2:
            positions[unit[0]] = (center[0] - 3.0, center[1])
            positions[unit[1]] = (center[0] + 3.0, center[1])
        else:
            positions[unit[0]] = center
    positioned = replace(problem, variable_positions=tuple(sorted(positions.items())))
    pair_set = set(normalized)
    quadratic = {
        tuple(sorted((left, right)))
        for left, right, _coefficient in problem.quadratic_terms
    }
    return positioned, GeometryEvidence(
        source="verified_embedding",
        coordinate_unit="um",
        positions=tuple(sorted(positions.items())),
        expected_interactions=normalized,
        forbidden_interactions=tuple(sorted(quadratic - pair_set)),
    )
