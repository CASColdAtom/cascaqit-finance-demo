"""金融算法策略的模式、场景、层数和预算边界测试。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS
from cascaqit_finance_demo.domain.problem_api import FinanceVQEAnsatzConfig
from cascaqit_finance_demo.quantum import FinanceAlgorithmPolicy


def _definition(case_id: str):
    """构造标准预设对应的真实金融 Problem，避免用伪对象绕过场景声明。"""
    scenario = PROBLEM_SCENARIOS[case_id]
    return scenario.build_definition(scenario.default_input())


@pytest.mark.parametrize(
    ("case_id", "entanglement", "max_layers", "budget"),
    [
        ("portfolio", "circular", 1, 14),
        ("collateral", "linear", 2, 10),
        ("liquidity", "linear", 1, 18),
        ("credit_limits", "linear", 1, 16),
    ],
)
def test_digital_scenarios_declare_internal_vqe_without_changing_recommended_qaoa(
    case_id: str,
    entanglement: str,
    max_layers: int,
    budget: int,
) -> None:
    """四个场景允许显式 VQE，但推荐算法和客户页面仍保持 QAOA。"""
    definition = _definition(case_id)
    policy = FinanceAlgorithmPolicy()

    recommended = policy.resolve(
        definition,
        mode="digital",
        algorithm="recommended",
        layer_policy="fixed",
        layers=1,
        max_layers=2,
        min_improvement=0.0,
        search_strategy="continuous",
        parameter_budget=budget,
        optimizer_starts=1,
        explicit_parameters=False,
    )
    vqe = policy.resolve(
        definition,
        mode="digital",
        algorithm="vqe",
        layer_policy="fixed",
        layers=1,
        max_layers=2,
        min_improvement=0.0,
        search_strategy="continuous",
        parameter_budget=budget,
        optimizer_starts=1,
        explicit_parameters=False,
    )

    assert definition.digital_algorithms == ("qaoa", "vqe")
    assert definition.published_digital_algorithms == ("qaoa",)
    assert recommended.resolved_algorithm == "qaoa"
    assert recommended.problem_hash == definition.problem.stable_hash()
    assert recommended.optimizer_method == "COBYLA"
    assert recommended.per_start_evaluation_budget == budget
    assert vqe.resolved_algorithm == "vqe"
    assert vqe.ansatz.rotation_axes == ("ry",)
    assert vqe.ansatz.entanglement == entanglement
    assert definition.vqe_ansatz.max_layers == max_layers


def test_discrete_plan_records_that_no_optimizer_will_run() -> None:
    """离散参数评估不能在计划中伪装成连续优化。"""
    definition = _definition("settlement")

    plan = FinanceAlgorithmPolicy().resolve(
        definition,
        mode="hybrid",
        algorithm="qaoa",
        layer_policy="fixed",
        layers=1,
        max_layers=2,
        min_improvement=0.0,
        search_strategy="preset",
        parameter_budget=2,
        optimizer_starts=1,
        explicit_parameters=False,
    )

    assert plan.problem_hash == definition.problem.stable_hash()
    assert plan.optimizer_method is None
    assert plan.per_start_evaluation_budget is None


@pytest.mark.parametrize(
    ("case_id", "mode", "algorithm", "message"),
    [
        ("settlement", "hybrid", "vqe", "unavailable"),
        ("derivatives", "analog", "qaoa", "unavailable"),
    ],
)
def test_policy_rejects_unvalidated_mode_algorithm_combinations(
    case_id: str,
    mode: str,
    algorithm: str,
    message: str,
) -> None:
    """未验收的算法组合必须失败，不能自动换成当前默认算法。"""
    with pytest.raises(ValueError, match=message):
        FinanceAlgorithmPolicy().resolve(
            _definition(case_id),
            mode=mode,  # type: ignore[arg-type]
            algorithm=algorithm,  # type: ignore[arg-type]
            layer_policy="fixed",
            layers=1,
            max_layers=2,
            min_improvement=0.0,
            search_strategy="continuous",
            parameter_budget=12,
            optimizer_starts=1,
            explicit_parameters=False,
        )


@pytest.mark.parametrize(
    ("case_id", "insufficient_budget", "minimum_budget"),
    [
        ("portfolio", 13, 14),
        ("collateral", 9, 10),
        ("liquidity", 17, 18),
        ("credit_limits", 15, 16),
    ],
)
def test_policy_uses_each_vqe_parameter_count_for_continuous_budget_floor(
    case_id: str,
    insufficient_budget: int,
    minimum_budget: int,
) -> None:
    """VQE 预算下限必须按场景的真实变量数计算，不能沿用通用最小值。"""
    with pytest.raises(
        ValueError,
        match=rf"parameter_budget >= {minimum_budget}",
    ):
        FinanceAlgorithmPolicy().resolve(
            _definition(case_id),
            mode="digital",
            algorithm="vqe",
            layer_policy="fixed",
            layers=1,
            max_layers=2,
            min_improvement=0.0,
            search_strategy="continuous",
            parameter_budget=insufficient_budget,
            optimizer_starts=1,
            explicit_parameters=False,
        )


@pytest.mark.parametrize("case_id", ["portfolio", "liquidity", "credit_limits"])
def test_larger_vqe_scenarios_reject_a_second_layer(case_id: str) -> None:
    """辅助位较多的场景不能开放超出当前优化预算的第二层 VQE。"""
    with pytest.raises(ValueError, match="supports fixed layers from 1 to 1"):
        FinanceAlgorithmPolicy().resolve(
            _definition(case_id),
            mode="digital",
            algorithm="vqe",
            layer_policy="fixed",
            layers=2,
            max_layers=2,
            min_improvement=0.0,
            search_strategy="continuous",
            parameter_budget=24,
            optimizer_starts=1,
            explicit_parameters=False,
        )


def test_vqe_capability_and_ansatz_contract_cannot_drift_apart() -> None:
    """算法声明和 Ansatz 必须成对出现，防止策略运行到一半才发现配置缺失。"""
    with pytest.raises(ValueError, match="must declare a vqe_ansatz"):
        replace(_definition("portfolio"), vqe_ansatz=None)

    with pytest.raises(ValueError, match="requires vqe in digital_algorithms"):
        replace(
            _definition("settlement"),
            vqe_ansatz=FinanceVQEAnsatzConfig(),
        )


def test_adaptive_layers_require_continuous_optimization() -> None:
    """自动选层必须保留真实连续优化，不能用离散点扫描冒充。"""
    with pytest.raises(ValueError, match="require continuous optimization"):
        FinanceAlgorithmPolicy().resolve(
            _definition("portfolio"),
            mode="digital",
            algorithm="qaoa",
            layer_policy="adaptive",
            layers=1,
            max_layers=3,
            min_improvement=0.0,
            search_strategy="preset",
            parameter_budget=2,
            optimizer_starts=1,
            explicit_parameters=False,
        )
