"""同一交易结算 Problem 的 Digital 与 Hybrid 执行一致性测试。"""

from __future__ import annotations

from pathlib import Path

from cascaqit_finance_demo import ScenarioExecutor, SettlementScenario


def test_settlement_uses_one_problem_for_digital_and_hybrid(
    tmp_path: Path,
) -> None:
    """验证两种模式共享问题哈希和业务定义，仅物理实现路径不同。"""
    scenario = SettlementScenario()
    case_input = scenario.default_input()
    executor = ScenarioExecutor()
    digital = executor.run(
        scenario,
        case_input,
        mode="digital",
        parameter_sets=({"gamma_0": 0.16, "beta_0": 0.24},),
        shots=16,
        seed=29,
        report_path=tmp_path / "settlement-digital.html",
    )
    hybrid = executor.run(
        scenario,
        case_input,
        mode="hybrid",
        parameter_sets=({"gamma_0": 0.16, "beta_0": 0.24},),
        shots=16,
        seed=29,
        report_path=tmp_path / "settlement-hybrid.html",
    )

    assert digital.execution.problem_hash == hybrid.execution.problem_hash
    assert digital.execution.logical_order == hybrid.execution.logical_order
    assert sum(digital.execution.result.counts.values()) == 16
    assert sum(hybrid.execution.result.counts.values()) == 16
    assert hybrid.execution.topology == "dad"
    assert hybrid.analysis.mode_decision.for_mode("hybrid").analog_business_pairs
    assert hybrid.report_path and hybrid.report_path.exists()
