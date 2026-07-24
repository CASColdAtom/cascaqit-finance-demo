"""反欺诈调查编排的 Hybrid Problem 端到端执行测试。"""

from __future__ import annotations

from pathlib import Path

from cascaqit_finance_demo import FraudRoutingScenario, ScenarioExecutor


def test_fraud_routing_runs_recommended_hybrid_problem(tmp_path: Path) -> None:
    """验证共享实体冲突进入 Analog 块，调查席位仍由 Digital 项约束。"""
    scenario = FraudRoutingScenario()
    result = ScenarioExecutor().run(
        scenario,
        scenario.default_input(),
        parameter_sets=({"gamma_0": 0.16, "beta_0": 0.24},),
        shots=16,
        seed=37,
        report_path=tmp_path / "fraud-hybrid.html",
    )

    assert result.mode == "hybrid"
    assert sum(result.execution.result.counts.values()) == 16
    assert result.baseline_solution is not None
    assert result.displayed_solution.feasible is True
    assert result.definition.metadata["decision_scope"] == "investigation routing only"
    assert result.evidence.hardware_execution is False
    assert result.report_path and result.report_path.exists()
