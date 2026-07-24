"""多资产等权重投资组合选择及其 QUBO 映射。

场景问题是：从 ``N`` 项资产中恰好选择 ``K`` 项，并按等权重持有；在收益、
协方差风险、行业集中度和防御资产下限之间寻找能量最低的组合。每项资产对应
一个二元变量 ``x_i``，``x_i = 1`` 表示资产入选。

业务目标先把收益向量和协方差矩阵归一化，再写成：

``risk_weight * x.T @ covariance @ x / K^2``
``- (1 - risk_weight) * returns.T @ x / K``

QUBO 求解器最小化能量，因此风险为正项，收益为负项。固定持仓数、行业上限和
防御资产下限通过平方罚项进入同一个 QUBO；不等式使用有界二进制松弛变量改写
为等式。小规模演示还会穷举全部 ``K`` 资产组合，作为可行性检查和经典基线，
但该基线与量子采样候选在结果中分别保留。
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from dataclasses import replace
from typing import Any

import numpy as np
from cascaqit import QUBOProblemIR

from cascaqit_finance_demo.domain.models import (
    AssetInput,
    CaseIssue,
    ConstraintCheck,
    PortfolioInput,
    PortfolioPoint,
    PortfolioSolution,
)
from cascaqit_finance_demo.domain.qubo_builder import (
    QuboBuilder,
    bounded_binary_weights,
)


class PortfolioCase:
    """构建等权重投资组合 QUBO，并把候选位串还原为业务组合。

    这里不求连续权重：资产一旦入选，权重固定为 ``1 / selected_count``。
    这个约束让“是否持有”可以直接由二元变量表达，也让前端能够逐位解释结果。
    """

    case_id = "portfolio"

    def default_input(self) -> PortfolioInput:
        """生成八类资产及协方差矩阵，作为离线演示的默认市场。"""
        assets = (
            AssetInput("bank", "银行", "finance", 0.072, 0.131),
            AssetInput("technology", "科技", "growth", 0.128, 0.224),
            AssetInput("energy", "能源", "cyclical", 0.094, 0.192),
            AssetInput("consumer", "消费", "defensive", 0.077, 0.126, True),
            AssetInput("bond", "债券", "defensive", 0.043, 0.058, True),
            AssetInput("gold", "黄金", "commodity", 0.061, 0.102, True),
            AssetInput("healthcare", "医药", "defensive", 0.086, 0.144, True),
            AssetInput("infrastructure", "基础设施", "cyclical", 0.069, 0.097),
        )
        correlations = np.array(
            [
                [1.00, 0.38, 0.31, 0.42, -0.18, -0.08, 0.29, 0.47],
                [0.38, 1.00, 0.24, 0.44, -0.23, -0.06, 0.51, 0.33],
                [0.31, 0.24, 1.00, 0.28, -0.12, 0.16, 0.18, 0.54],
                [0.42, 0.44, 0.28, 1.00, -0.08, 0.02, 0.46, 0.36],
                [-0.18, -0.23, -0.12, -0.08, 1.00, 0.19, -0.15, -0.04],
                [-0.08, -0.06, 0.16, 0.02, 0.19, 1.00, 0.05, 0.11],
                [0.29, 0.51, 0.18, 0.46, -0.15, 0.05, 1.00, 0.27],
                [0.47, 0.33, 0.54, 0.36, -0.04, 0.11, 0.27, 1.00],
            ],
            dtype=float,
        )
        volatilities = np.array([asset.volatility for asset in assets])
        covariance = correlations * np.outer(volatilities, volatilities)
        return PortfolioInput(
            assets=assets,
            covariance=tuple(
                tuple(float(value) for value in row) for row in covariance
            ),
        )

    def validate(self, case_input: PortfolioInput) -> tuple[CaseIssue, ...]:
        """一次性检查资产、协方差、目标权重和组合约束的完整性。"""
        issues: list[CaseIssue] = []
        assets = case_input.assets
        size = len(assets)
        if size < 2:
            issues.append(
                CaseIssue("PORTFOLIO_TOO_SMALL", "assets", "至少需要两个资产。")
            )
        asset_ids = tuple(asset.asset_id for asset in assets)
        if len(asset_ids) != len(set(asset_ids)):
            issues.append(
                CaseIssue("ASSET_ID_DUPLICATE", "assets", "资产 ID 必须唯一。")
            )
        if not 1 <= case_input.selected_count <= size:
            issues.append(
                CaseIssue(
                    "SELECTED_COUNT_RANGE", "selected_count", "持仓数量超出资产范围。"
                )
            )
        if not 0.0 <= case_input.risk_weight <= 1.0:
            issues.append(
                CaseIssue(
                    "RISK_WEIGHT_RANGE", "risk_weight", "风险权重必须在 0 到 1 之间。"
                )
            )
        if case_input.sector_cap < 1:
            issues.append(
                CaseIssue("SECTOR_CAP_RANGE", "sector_cap", "行业上限必须为正整数。")
            )
        defensive_count = sum(asset.defensive for asset in assets)
        if not 0 <= case_input.minimum_defensive <= defensive_count:
            issues.append(
                CaseIssue(
                    "DEFENSIVE_FLOOR_RANGE",
                    "minimum_defensive",
                    "防御资产下限超出可用数量。",
                )
            )
        covariance = np.asarray(case_input.covariance, dtype=float)
        if covariance.shape != (size, size):
            issues.append(
                CaseIssue("COVARIANCE_SHAPE", "covariance", "协方差矩阵维度不匹配。")
            )
        elif not np.all(np.isfinite(covariance)):
            issues.append(
                CaseIssue("COVARIANCE_FINITE", "covariance", "协方差矩阵包含非有限值。")
            )
        elif not np.allclose(covariance, covariance.T, atol=1e-12):
            issues.append(
                CaseIssue("COVARIANCE_SYMMETRY", "covariance", "协方差矩阵必须对称。")
            )
        elif np.linalg.eigvalsh(covariance).min() < -1e-10:
            issues.append(
                CaseIssue("COVARIANCE_PSD", "covariance", "协方差矩阵必须半正定。")
            )
        if not issues and not self.exact_business_points(case_input):
            issues.append(
                CaseIssue(
                    "NO_FEASIBLE_PORTFOLIO", "constraints", "当前约束下没有可行组合。"
                )
            )
        return tuple(issues)

    def build_problem(self, case_input: PortfolioInput) -> QUBOProblemIR:
        """把收益风险目标、持仓数、行业上限和防御资产下限编码为 QUBO。

        构建顺序有意保持稳定：先加入无约束的风险收益目标，再依据该目标全部
        系数的绝对值和确定罚项尺度，最后编码三类硬约束。这样一条硬约束的
        最小违规代价会高于目标函数可能获得的总收益，避免优化器通过违规换取
        更低能量。
        """
        issues = self.validate(case_input)
        if issues:
            raise ValueError("; ".join(issue.message for issue in issues))

        asset_variables = tuple(
            f"asset_{index:02d}_{asset.asset_id}"
            for index, asset in enumerate(case_input.assets)
        )
        builder = QuboBuilder(asset_variables)
        returns, normalized_covariance = self._normalized_market_data(case_input)
        count = case_input.selected_count

        # 入选资产在业务层按等权重配置，因此收益项按 1/K 缩放，
        # 二次风险项按 1/K^2 缩放，保证 QUBO 能量与解码后的组合指标一致。
        for index, variable in enumerate(asset_variables):
            builder.add_linear(
                variable,
                case_input.risk_weight
                * normalized_covariance[index, index]
                / (count * count)
                - (1.0 - case_input.risk_weight) * returns[index] / count,
            )
        for left in range(len(asset_variables)):
            for right in range(left + 1, len(asset_variables)):
                builder.add_quadratic(
                    asset_variables[left],
                    asset_variables[right],
                    2.0
                    * case_input.risk_weight
                    * normalized_covariance[left, right]
                    / (count * count),
                )

        # ``sum(x_i) = K`` 是固定持仓数约束。罚项尺度以无约束目标的系数上界
        # 为基准，使可行解优先于任何靠破坏持仓数获得的目标改进。
        objective_bound = builder.absolute_coefficient_sum
        base_penalty = (objective_bound + 1.0) * case_input.penalty_multiplier
        builder.add_squared_equality(
            dict.fromkeys(asset_variables, 1.0),
            rhs=float(count),
            penalty=base_penalty,
        )

        by_sector: dict[str, list[str]] = {}
        defensive_variables: list[str] = []
        for asset, variable in zip(case_input.assets, asset_variables):
            by_sector.setdefault(asset.sector, []).append(variable)
            if asset.defensive:
                defensive_variables.append(variable)
        for sector, variables in sorted(by_sector.items()):
            if len(variables) <= case_input.sector_cap:
                continue
            # 行业上限 ``sum(x_i) <= cap`` 改写为
            # ``sum(x_i) + slack = cap``。slack 只能表示 0..cap，因而不存在
            # 通过负松弛值掩盖超限的路径。
            coefficients = dict.fromkeys(variables, 1.0)
            for index, weight in enumerate(
                bounded_binary_weights(case_input.sector_cap)
            ):
                slack = f"slack_sector_{sector}_{index:02d}"
                coefficients[slack] = float(weight)
            builder.add_squared_equality(
                coefficients,
                rhs=float(case_input.sector_cap),
                penalty=base_penalty * 1.2,
            )

        if case_input.minimum_defensive > 0:
            # 防御资产下限 ``sum(x_i) >= floor`` 改写为
            # ``sum(x_i) - slack = floor``。这里松弛变量系数取负，表示超过
            # 下限的合法余量，而不是允许少选防御资产。
            coefficients = dict.fromkeys(defensive_variables, 1.0)
            slack_max = len(defensive_variables) - case_input.minimum_defensive
            for index, weight in enumerate(bounded_binary_weights(slack_max)):
                slack = f"slack_defensive_floor_{index:02d}"
                coefficients[slack] = -float(weight)
            builder.add_squared_equality(
                coefficients,
                rhs=float(case_input.minimum_defensive),
                penalty=base_penalty * 1.3,
            )

        return builder.build(
            problem_id="finance.portfolio",
            metadata={
                "case_id": self.case_id,
                "business_variables": list(asset_variables),
                "bitstring_convention": "1 means selected in problem.variables order",
                "objective_bound": objective_bound,
                "base_penalty": base_penalty,
            },
        )

    def exact_business_points(
        self, case_input: PortfolioInput
    ) -> tuple[PortfolioPoint, ...]:
        """枚举固定持仓数的全部组合，仅保留满足行业和防御性约束的点。

        组合数为 ``C(N, K)``，只适合当前演示规模。它的作用是验证输入确实
        存在可行解，并给可视化提供有效组合集合；不应把这条穷举路径描述成
        可扩展到大规模资产池的经典优化器。
        """
        returns, normalized_covariance = self._normalized_market_data(case_input)
        covariance = np.asarray(case_input.covariance, dtype=float)
        points: list[PortfolioPoint] = []
        indices = range(len(case_input.assets))
        for selected in itertools.combinations(indices, case_input.selected_count):
            selected_assets = tuple(case_input.assets[index] for index in selected)
            sectors = Counter(asset.sector for asset in selected_assets)
            if sectors and max(sectors.values()) > case_input.sector_cap:
                continue
            if (
                sum(asset.defensive for asset in selected_assets)
                < case_input.minimum_defensive
            ):
                continue
            vector = np.zeros(len(case_input.assets), dtype=float)
            vector[list(selected)] = 1.0
            weights = vector / case_input.selected_count
            expected_return = float(
                sum(case_input.assets[index].expected_return for index in selected)
                / case_input.selected_count
            )
            volatility = float(math.sqrt(weights @ covariance @ weights))
            objective = self._business_objective(
                case_input, vector, returns, normalized_covariance
            )
            points.append(
                PortfolioPoint(
                    bitstring="".join(
                        "1" if index in selected else "0" for index in indices
                    ),
                    asset_ids=tuple(asset.asset_id for asset in selected_assets),
                    expected_return=expected_return,
                    volatility=volatility,
                    objective_value=objective,
                )
            )
        return tuple(sorted(points, key=lambda point: point.objective_value))

    def decode(
        self,
        case_input: PortfolioInput,
        problem: QUBOProblemIR,
        candidate: Any,
    ) -> PortfolioSolution:
        """按 Problem 变量名提取资产位，并忽略只服务于罚项的松弛变量。

        解码不直接信任 QUBO 能量。它根据原始业务输入重新计算持仓数、行业
        上限、防御资产下限、预期收益和波动率，最终由这些独立检查决定候选
        是否可行。
        """
        bitstring = str(candidate.bitstring)
        if len(bitstring) != len(problem.variables):
            raise ValueError("candidate bitstring does not match problem variables.")
        selected_values = dict(zip(problem.variables, bitstring))
        selected_indices = tuple(
            index
            for index, asset in enumerate(case_input.assets)
            if selected_values.get(f"asset_{index:02d}_{asset.asset_id}") == "1"
        )
        selected_assets = tuple(case_input.assets[index] for index in selected_indices)
        sectors = Counter(asset.sector for asset in selected_assets)
        checks = (
            ConstraintCheck(
                "cardinality",
                len(selected_assets) == case_input.selected_count,
                str(len(selected_assets)),
                str(case_input.selected_count),
            ),
            ConstraintCheck(
                "sector_cap",
                not sectors or max(sectors.values()) <= case_input.sector_cap,
                str(max(sectors.values(), default=0)),
                f"<= {case_input.sector_cap}",
            ),
            ConstraintCheck(
                "minimum_defensive",
                sum(asset.defensive for asset in selected_assets)
                >= case_input.minimum_defensive,
                str(sum(asset.defensive for asset in selected_assets)),
                f">= {case_input.minimum_defensive}",
            ),
        )
        vector = np.zeros(len(case_input.assets), dtype=float)
        vector[list(selected_indices)] = 1.0
        returns, normalized_covariance = self._normalized_market_data(case_input)
        covariance = np.asarray(case_input.covariance, dtype=float)
        if selected_indices:
            weights = vector / len(selected_indices)
            expected_return = float(
                sum(asset.expected_return for asset in selected_assets)
                / len(selected_assets)
            )
            volatility = float(math.sqrt(weights @ covariance @ weights))
        else:
            expected_return = 0.0
            volatility = 0.0
        return PortfolioSolution(
            bitstring=bitstring,
            selected_asset_ids=tuple(asset.asset_id for asset in selected_assets),
            expected_return=expected_return,
            volatility=volatility,
            objective_value=self._business_objective(
                case_input, vector, returns, normalized_covariance
            ),
            feasible=all(check.passed for check in checks),
            checks=checks,
        )

    def replace_market_data(
        self,
        case_input: PortfolioInput,
        *,
        expected_returns: tuple[float, ...],
        volatilities: tuple[float, ...],
    ) -> PortfolioInput:
        """应用用户编辑的收益率和波动率，同时保留原相关系数结构。"""
        if len(expected_returns) != len(case_input.assets) or len(volatilities) != len(
            case_input.assets
        ):
            raise ValueError("market vectors must match the asset count.")
        previous_volatilities = np.array(
            [asset.volatility for asset in case_input.assets], dtype=float
        )
        covariance = np.asarray(case_input.covariance, dtype=float)
        correlations = covariance / np.outer(
            previous_volatilities, previous_volatilities
        )
        new_volatilities = np.asarray(volatilities, dtype=float)
        updated_covariance = correlations * np.outer(new_volatilities, new_volatilities)
        updated_assets = tuple(
            replace(
                asset,
                expected_return=expected_returns[index],
                volatility=volatilities[index],
            )
            for index, asset in enumerate(case_input.assets)
        )
        return replace(
            case_input,
            assets=updated_assets,
            covariance=tuple(
                tuple(float(value) for value in row) for row in updated_covariance
            ),
        )

    def _normalized_market_data(
        self, case_input: PortfolioInput
    ) -> tuple[np.ndarray, np.ndarray]:
        """归一化收益和协方差，使两类目标项处于可比较的数值尺度。"""
        raw_returns = np.array(
            [asset.expected_return for asset in case_input.assets], dtype=float
        )
        spread = float(raw_returns.max() - raw_returns.min())
        normalized_returns = (
            np.ones_like(raw_returns)
            if spread <= 1e-15
            else (raw_returns - raw_returns.min()) / spread
        )
        covariance = np.asarray(case_input.covariance, dtype=float)
        scale = float(np.max(np.abs(covariance)))
        normalized_covariance = covariance if scale <= 1e-15 else covariance / scale
        return normalized_returns, normalized_covariance

    def _business_objective(
        self,
        case_input: PortfolioInput,
        vector: np.ndarray,
        normalized_returns: np.ndarray,
        normalized_covariance: np.ndarray,
    ) -> float:
        """使用与 QUBO 相同的风险收益权重计算可解释的业务目标值。"""
        count = case_input.selected_count
        risk = float(vector @ normalized_covariance @ vector) / (count * count)
        expected_return = float(vector @ normalized_returns) / count
        return (
            case_input.risk_weight * risk
            - (1.0 - case_input.risk_weight) * expected_return
        )
