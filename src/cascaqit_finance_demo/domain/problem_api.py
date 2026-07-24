"""金融领域对 CASCAQit 统一 Problem API 的语义封装。

CASCAQit 的 Problem IR 负责机器可编译的问题表达，本模块额外保留金融业务变量、
项分组和模式决策证据，使编译后的物理项仍可追溯到原始业务含义。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from cascaqit.problems import GraphProblemIR, IsingModelIR, QUBOProblemIR

ProblemMode = Literal["digital", "hybrid", "analog"]
ModeStatus = Literal["recommended", "comparable", "unsuitable"]
ProblemKind = Literal["qubo", "graph", "ising"]
TermKind = Literal[
    "objective",
    "pairwise_conflict",
    "global_constraint",
    "dependency",
    "auxiliary_penalty",
]


@dataclass(frozen=True)
class FinanceTermGroup:
    """与规范化 Problem IR 并存的业务项分组，用于保持语义可追溯。"""

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
class FinanceProblemDefinition:
    """一个可编译 Problem 及其金融变量、项分组和首选执行模式。"""

    case_id: str
    title: str
    problem_kind: ProblemKind
    problem: QUBOProblemIR | GraphProblemIR | IsingModelIR
    preferred_mode: ProblemMode
    business_variables: tuple[str, ...]
    auxiliary_variables: tuple[str, ...] = ()
    term_groups: tuple[FinanceTermGroup, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def analog_business_pairs(self) -> tuple[tuple[str, str], ...]:
        """返回可映射为原子相互作用的业务冲突对，并去重、排序。"""
        pairs = {
            tuple(sorted(pair))
            for group in self.term_groups
            if group.kind == "pairwise_conflict"
            for pair in group.pairs
        }
        return tuple(sorted(pairs))


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
    """所有可运行金融场景必须实现的最小协议。"""

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
