"""投资组合统一 Problem 的 Digital QAOA 执行测试。"""

from __future__ import annotations

from pathlib import Path

from cascaqit_finance_demo import PortfolioScenario, ScenarioExecutor


def test_portfolio_problem_run_returns_counts_baseline_and_report(
    tmp_path: Path,
) -> None:
    """验证执行同时产出计数、经典基线、审计哈希和 HTML 报告。"""
    scenario = PortfolioScenario()
    report = tmp_path / "portfolio-problem.html"
    result = ScenarioExecutor().run(
        scenario,
        scenario.default_input(),
        mode="digital",
        parameter_sets=({"gamma_0": 0.16, "beta_0": 0.24},),
        shots=32,
        seed=23,
        report_path=report,
    )

    assert result.execution.mode == "digital"
    assert sum(result.execution.result.counts.values()) == 32
    assert result.baseline_solution is not None
    assert result.displayed_solution.feasible is True
    assert result.evidence.execution_kind == "local_simulation"
    assert result.report_path == report.resolve()
    assert "finance.portfolio" in report.read_text(encoding="utf-8")


def test_fixed_seed_reproduces_problem_counts() -> None:
    """验证相同随机种子和参数扫描可复现完全一致的采样计数。"""
    scenario = PortfolioScenario()
    case_input = scenario.default_input()
    kwargs = {
        "mode": "digital",
        "parameter_sets": ({"gamma_0": 0.16, "beta_0": 0.24},),
        "shots": 24,
        "seed": 41,
    }

    first = ScenarioExecutor().run(scenario, case_input, **kwargs)
    second = ScenarioExecutor().run(scenario, case_input, **kwargs)

    assert first.execution.result.counts == second.execution.result.counts
    assert first.business_candidate.bitstring == second.business_candidate.bitstring
