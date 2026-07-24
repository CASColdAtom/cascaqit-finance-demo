"""离散金融优化场景共享的泛型协议。"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from cascaqit import QUBOProblemIR

from cascaqit_finance_demo.domain.models import CaseIssue

InputT = TypeVar("InputT")
PointT = TypeVar("PointT")
SolutionT = TypeVar("SolutionT")


class FinanceOptimizationCase(Protocol[InputT, PointT, SolutionT]):
    """金融侧 QUBO 映射必须实现的构建、枚举和解码契约。"""

    case_id: str

    def default_input(self) -> InputT:
        """返回可直接运行的默认合成业务输入。"""
        ...

    def validate(self, case_input: InputT) -> tuple[CaseIssue, ...]:
        """检查输入范围、标识唯一性和约束可行性。"""
        ...

    def build_problem(self, case_input: InputT) -> QUBOProblemIR:
        """将通过验证的业务输入编码为 QUBO Problem IR。"""
        ...

    def exact_business_points(self, case_input: InputT) -> tuple[PointT, ...]:
        """枚举小规模场景的精确可行点，用于基线和可行性检查。"""
        ...

    def decode(
        self,
        case_input: InputT,
        problem: QUBOProblemIR,
        candidate: Any,
    ) -> SolutionT:
        """按 Problem 变量顺序解码候选，并从原始输入复核业务指标。"""
        ...
