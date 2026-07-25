"""四类衍生品在推荐配置下的完整重估、Analog 编译和业务解码验收。"""

from __future__ import annotations

from cascaqit_finance_demo.api.catalog import SCENARIO_SPECS, preset_input
from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS
from cascaqit_finance_demo.quantum.problem_executor import ScenarioExecutor


def test_all_derivative_products_run_distinct_weighted_analog_problems() -> None:
    """验证四类产品均运行自身的 MWIS，且结果来自量子采样候选。

    这里使用与界面相同的推荐配置，避免只证明低层编译可行，却遗漏参数绑定、
    本地执行、MWIS 解码或业务约束复核阶段的问题。
    """
    scenario = PROBLEM_SCENARIOS["derivatives"]
    profile = SCENARIO_SPECS["derivatives"].recommended_execution
    executor = ScenarioExecutor()
    problem_hashes: set[str] = set()

    for preset in (
        "european_call",
        "european_put",
        "asian_call",
        "up_and_out_call",
    ):
        result = executor.run(
            scenario,
            preset_input("derivatives", preset),
            mode="recommended",
            shots=profile.shots,
            seed=profile.seed,
            layers=profile.layers,
            search_strategy=profile.search_strategy,
            parameter_budget=profile.parameter_budget,
        )

        assert result.mode == "analog"
        assert result.business_candidate.feasible is True
        assert result.metadata["displayed_source"] == "best_observed"
        assert sum(result.execution.result.counts.values()) == profile.shots
        problem_hashes.add(result.definition.problem.stable_hash())

    assert len(problem_hashes) == 4
