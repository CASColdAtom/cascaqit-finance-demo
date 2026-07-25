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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from cascaqit.problems import GraphProblemIR, IsingModelIR, QUBOProblemIR

ProblemMode = Literal["digital", "hybrid", "analog"]
ModeStatus = Literal["recommended", "comparable", "unsuitable"]
ProblemKind = Literal["qubo", "graph", "ising"]
GeometrySource = Literal["business_native", "verified_embedding"]
GeometryStatus = Literal["verified", "missing", "distorted"]
TermKind = Literal[
    "objective",
    "pairwise_conflict",
    "global_constraint",
    "dependency",
    "auxiliary_penalty",
]


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
    problem: QUBOProblemIR | GraphProblemIR | IsingModelIR
    business_variables: tuple[str, ...]
    auxiliary_variables: tuple[str, ...] = ()
    term_groups: tuple[FinanceTermGroup, ...] = ()
    analog_candidate_group_ids: tuple[str, ...] = ()
    geometry_evidence: FinanceGeometryEvidence | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

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
