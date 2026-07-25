"""金融领域对 CASCAQit 统一 Problem API 的语义封装。

业务场景先生成 CASCAQit 能编译的 QUBO、Graph 或 Ising Problem IR，再用
``FinanceProblemDefinition`` 补充业务变量、辅助变量、项分组和几何证据。这样
编译器处理数学结构，金融层保留“这个变量代表哪项资产/交易、这对相互作用来自
哪个业务冲突”的解释。

数据沿以下方向流动：

``业务输入 -> FinanceScenario -> Problem IR + 金融语义 -> 编译分析``
``-> 模式选择 -> Digital/Hybrid/Analog 程序 -> 采样候选 -> 业务解码复核``

其中 ``pairwise_conflict`` 是 Analog 映射唯一认可的业务冲突来源。普通目标项、
全局约束、依赖和 slack 罚项不会因为存在二次系数就自动宣称为 Analog 业务项。
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from cascaqit.problems import (
    GraphProblemIR,
    IsingModelIR,
    MWISProblemIR,
    QUBOProblemIR,
)

ProblemMode = Literal["digital", "hybrid", "analog"]
ModeStatus = Literal["recommended", "comparable", "unsuitable"]
ProblemKind = Literal["qubo", "graph", "mwis", "ising"]
GeometrySource = Literal["business_native", "verified_embedding"]
GeometryStatus = Literal["verified", "missing", "distorted"]
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
class FinanceCoefficientContribution:
    """一条业务规则对某个规范 QUBO 系数的原始贡献。

    多条业务规则可以落到同一个 ``canonical_term_id``。账本保留每条原始贡献，
    最终 QUBO 则保存聚合后的系数；两者必须逐项守恒。平方罚项会被拆成常数、
    线性和二次贡献，因此界面能够解释展开后的每一个实际系数。
    """

    contribution_id: str
    group_id: str
    source_rule: str
    term_kind: CoefficientTermKind
    targets: tuple[str, ...]
    coefficient: float
    role: CoefficientRole

    def __post_init__(self) -> None:
        """校验标识、目标数量和数值，并规范无向二次项的变量顺序。"""
        for field_name in ("contribution_id", "group_id", "source_rule"):
            value = getattr(self, field_name)
            if (
                not isinstance(value, str)
                or not value.strip()
                or value != value.strip()
            ):
                raise ValueError(f"{field_name} must be a non-empty trimmed string.")
        if self.term_kind not in {"offset", "linear", "quadratic"}:
            raise ValueError("term_kind must be offset, linear, or quadratic.")
        if self.role not in {"objective", "constraint", "auxiliary"}:
            raise ValueError("role must be objective, constraint, or auxiliary.")
        targets = tuple(self.targets)
        expected_size = {"offset": 0, "linear": 1, "quadratic": 2}[self.term_kind]
        if len(targets) != expected_size:
            raise ValueError(
                f"{self.term_kind} contributions require {expected_size} targets."
            )
        if any(
            not isinstance(target, str)
            or not target.strip()
            or target != target.strip()
            for target in targets
        ):
            raise ValueError("contribution targets must be non-empty trimmed strings.")
        if self.term_kind == "quadratic":
            if targets[0] == targets[1]:
                raise ValueError("quadratic contribution targets must be distinct.")
            targets = tuple(sorted(targets))
        coefficient = float(self.coefficient)
        if not math.isfinite(coefficient):
            raise ValueError("contribution coefficient must be finite.")
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "coefficient", coefficient)

    @property
    def canonical_term_id(self) -> str:
        """返回与 CASCAQit Canonical QUBO 项一致的稳定标识。"""
        if self.term_kind == "offset":
            return "offset"
        return ".".join((self.term_kind, *self.targets))

    @classmethod
    def from_mapping(
        cls, data: Mapping[str, object]
    ) -> FinanceCoefficientContribution:
        """从 Problem metadata 的 JSON 兼容字典恢复不可变贡献对象。"""
        return cls(
            contribution_id=str(data["contribution_id"]),
            group_id=str(data["group_id"]),
            source_rule=str(data["source_rule"]),
            term_kind=str(data["term_kind"]),  # type: ignore[arg-type]
            targets=tuple(str(item) for item in data.get("targets", ())),
            coefficient=float(data["coefficient"]),
            role=str(data["role"]),  # type: ignore[arg-type]
        )


def coefficient_contributions_from_problem(
    problem: QUBOProblemIR,
) -> tuple[FinanceCoefficientContribution, ...]:
    """读取由 ``QuboBuilder`` 写入 Problem metadata 的逐系数来源账本。"""
    raw = problem.metadata.get("coefficient_contributions", ())
    if not isinstance(raw, (list, tuple)):
        raise ValueError("coefficient_contributions metadata must be a sequence.")
    if any(not isinstance(item, Mapping) for item in raw):
        raise ValueError("each coefficient contribution must be a mapping.")
    return tuple(FinanceCoefficientContribution.from_mapping(item) for item in raw)


@dataclass(frozen=True)
class FinanceTermGroup:
    """与规范化 Problem IR 并存的业务项分组，用于保持语义可追溯。

    ``variables`` 用于目标或全局约束等变量集合，``pairs`` 用于两两业务冲突。
    分组不改变 Problem IR 系数，只为模式判断、审计和界面解释提供来源证据。
    """

    group_id: str
    label: str
    kind: TermKind
    variables: tuple[str, ...] = ()
    pairs: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """冻结对象创建后统一容器类型和变量对顺序，保证哈希与展示稳定。"""
        object.__setattr__(self, "variables", tuple(self.variables))
        object.__setattr__(
            self,
            "pairs",
            tuple(tuple(sorted(pair)) for pair in self.pairs),
        )


@dataclass(frozen=True)
class FinanceGeometryEvidence:
    """业务变量到参考原子坐标的来源与预期 interaction 图。

    ``expected_interactions`` 是允许进入 Analog core 的业务边；
    ``forbidden_interactions`` 是 Problem 中存在、但必须留在 Digital residual 的
    二次项。模式顾问还会检查全部物理 interaction，因此即使补边没有对应 QUBO
    项，也不能绕过几何保真门禁。
    """

    source: GeometrySource
    coordinate_unit: str
    positions: tuple[tuple[str, tuple[float, float]], ...]
    expected_interactions: tuple[tuple[str, str], ...]
    forbidden_interactions: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """规范化变量、坐标和无向边顺序，保证前后端展示可复现。"""
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
class FinanceProblemDefinition:
    """一个可编译 Problem 及其金融变量、项分组和映射证据。

    ``business_variables`` 可被解码回金融对象；``auxiliary_variables`` 只负责
    罚项或 slack，不应作为资产、交易或告警展示。模式必须由编译事实、完整
    Analog 分组和几何保真共同推导，场景不能预填首选结果。
    """

    case_id: str
    title: str
    problem_kind: ProblemKind
    problem: QUBOProblemIR | GraphProblemIR | MWISProblemIR | IsingModelIR
    business_variables: tuple[str, ...]
    auxiliary_variables: tuple[str, ...] = ()
    term_groups: tuple[FinanceTermGroup, ...] = ()
    coefficient_contributions: tuple[FinanceCoefficientContribution, ...] = ()
    analog_candidate_group_ids: tuple[str, ...] = ()
    geometry_evidence: FinanceGeometryEvidence | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """核对账本引用和 QUBO 系数守恒，阻止错误来源进入编译与展示层。"""
        object.__setattr__(self, "business_variables", tuple(self.business_variables))
        object.__setattr__(self, "auxiliary_variables", tuple(self.auxiliary_variables))
        object.__setattr__(self, "term_groups", tuple(self.term_groups))
        object.__setattr__(
            self, "coefficient_contributions", tuple(self.coefficient_contributions)
        )
        object.__setattr__(
            self, "analog_candidate_group_ids", tuple(self.analog_candidate_group_ids)
        )
        group_ids = tuple(group.group_id for group in self.term_groups)
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("term group IDs must be unique.")
        contribution_ids = tuple(
            item.contribution_id for item in self.coefficient_contributions
        )
        if len(contribution_ids) != len(set(contribution_ids)):
            raise ValueError("coefficient contribution IDs must be unique.")
        unknown_groups = sorted(
            {
                item.group_id
                for item in self.coefficient_contributions
                if item.group_id not in set(group_ids)
            }
        )
        if unknown_groups:
            raise ValueError(
                "coefficient contributions reference unknown groups: "
                + ", ".join(unknown_groups)
            )
        if isinstance(self.problem, QUBOProblemIR):
            if not self.coefficient_contributions:
                raise ValueError(
                    "QUBO finance definitions require a coefficient ledger."
                )
            _require_qubo_ledger_conservation(
                self.problem, self.coefficient_contributions
            )

    @property
    def analog_business_pairs(self) -> tuple[tuple[str, str], ...]:
        """返回允许映射为原子相互作用的候选分组边，并去重、排序。"""
        pairs = {
            tuple(sorted(pair))
            for group in self.term_groups
            if group.group_id in self.analog_candidate_group_ids
            for pair in group.pairs
        }
        return tuple(sorted(pairs))

    @property
    def analog_candidate_groups(self) -> tuple[FinanceTermGroup, ...]:
        """返回按定义顺序排列的 Analog core 候选分组。"""
        candidates = set(self.analog_candidate_group_ids)
        return tuple(
            group for group in self.term_groups if group.group_id in candidates
        )


def _require_qubo_ledger_conservation(
    problem: QUBOProblemIR,
    contributions: tuple[FinanceCoefficientContribution, ...],
) -> None:
    """逐项比较贡献聚合值与最终 QUBO，包含被多条规则共同影响的系数。"""
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
        if any(target not in problem.variables for target in item.targets):
            raise ValueError(
                f"coefficient contribution {item.contribution_id!r} references "
                "an unknown QUBO variable."
            )
        actual[item.canonical_term_id] = (
            actual.get(item.canonical_term_id, 0.0) + item.coefficient
        )
    all_terms = set(expected) | set(actual)
    mismatched = [
        term_id
        for term_id in sorted(all_terms)
        if not math.isclose(
            actual.get(term_id, 0.0),
            expected.get(term_id, 0.0),
            rel_tol=1e-10,
            abs_tol=1e-10,
        )
    ]
    if mismatched:
        raise ValueError(
            "coefficient ledger does not conserve QUBO terms: "
            + ", ".join(mismatched)
        )


@dataclass(frozen=True)
class ModeDecisionRow:
    """一种执行模式的编译可行性、业务适配性和项分配统计。"""

    mode: ProblemMode
    algorithm: Literal["qaoa", "qaa"]
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
    """推荐执行模式及所有候选模式的完整判断证据。"""

    recommended_mode: ProblemMode
    reason: str
    rows: tuple[ModeDecisionRow, ...]

    def for_mode(self, mode: ProblemMode) -> ModeDecisionRow:
        """按模式名返回决策行；未知模式立即报错，避免静默降级。"""
        for row in self.rows:
            if row.mode == mode:
                return row
        raise ValueError(f"unknown Problem mode: {mode!r}")


@dataclass(frozen=True)
class ScenarioAnalysis:
    """编译和执行之前生成的场景定义、编译器分析与模式建议。"""

    definition: FinanceProblemDefinition
    problem_analysis: Any
    mode_decision: ModeDecision


@dataclass(frozen=True)
class FinanceExperimentResult:
    """一次场景运行产生的业务结果、量子执行事实、基线和审计证据。"""

    case_id: str
    mode: ProblemMode
    definition: FinanceProblemDefinition
    analysis: ScenarioAnalysis
    execution: Any
    business_candidate: Any
    baseline_solution: Any | None
    displayed_solution: Any
    evidence: Any
    report_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinanceRepeatedExperimentResult:
    """同一业务输入和执行配置下的一组独立量子运行。

    ``representative`` 只从本组量子运行中选择：优先选择业务可行候选，再按采样
    候选的 Hamiltonian 目标值排序。经典基线仍可用于单次结果对照，但不会进入
    重复运行成功率，也不会被选作本组代表结果。
    """

    representative: FinanceExperimentResult
    runs: tuple[FinanceExperimentResult, ...]
    representative_index: int
    confidence_level: float = 0.95


class FinanceScenario(Protocol):
    """所有可运行金融场景必须实现的最小协议。

    协议刻意把建模和解码放在同一个场景对象中：构建阶段定义变量语义，解码
    阶段必须使用同一语义还原候选并独立复核约束。
    """

    case_id: str
    title: str

    def default_input(self) -> Any:
        """返回可离线、确定性运行的默认业务输入。"""
        ...

    def validate(self, case_input: Any) -> tuple[Any, ...]:
        """验证业务输入并返回全部可定位问题，不在首个错误处中断。"""
        ...

    def build_definition(self, case_input: Any) -> FinanceProblemDefinition:
        """把业务输入转换为带金融语义的统一 Problem 定义。"""
        ...

    def decode(
        self, case_input: Any, definition: FinanceProblemDefinition, candidate: Any
    ) -> Any:
        """将编译器候选位串还原为业务结果，并独立复核约束。"""
        ...
