"""衍生品经典参考定价与 Analog 风险网格单元测试。"""

from __future__ import annotations

from dataclasses import replace

import pytest
from cascaqit.problems import MWISProblemIR

from cascaqit_finance_demo.api.presenters import analysis_payload, execution_payload
from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS
from cascaqit_finance_demo.quantum.problem_executor import ScenarioExecutor


@pytest.mark.parametrize(
    "product",
    ["european_call", "european_put", "asian_call", "up_and_out_call"],
)
def test_reference_pricing_is_positive_and_deterministic(product: str) -> None:
    """验证四类产品价格为正，并在固定输入和随机种子下可复现。"""
    scenario = PROBLEM_SCENARIOS["derivatives"]
    case_input = replace(scenario.default_input(), product=product)

    first = scenario.price(case_input)
    second = scenario.price(case_input)

    assert first == second
    assert first.reference_price >= 0.0
    assert first.method in {"Black-Scholes", "固定 seed Monte Carlo"}


def test_risk_grid_recommends_complete_analog_problem() -> None:
    """验证完整风险图可由 AHS 表达时推荐 Analog 而非人工 Hybrid。"""
    scenario = PROBLEM_SCENARIOS["derivatives"]
    analysis = ScenarioExecutor().analyze(scenario, scenario.default_input())

    assert analysis.mode_decision.recommended_mode == "analog"
    analog = analysis.mode_decision.for_mode("analog")
    assert analog.compiler_feasible
    assert analog.digital_term_count == 0
    assert len(analysis.definition.problem.nodes) == 9
    assert analysis.definition.problem_kind == "mwis"
    assert isinstance(analysis.definition.problem, MWISProblemIR)
    assert analysis.definition.metadata["counts_feed_pricing"] is False


@pytest.mark.parametrize(
    "product",
    ["european_call", "european_put", "asian_call", "up_and_out_call"],
)
def test_risk_revaluation_is_deterministic_and_drives_mwis_weights(
    product: str,
) -> None:
    """验证九格重估、P&L 归一化和 MWIS 权重使用同一份领域事实。"""
    scenario = PROBLEM_SCENARIOS["derivatives"]
    case_input = replace(scenario.default_input(), product=product)

    first = scenario.risk_scenarios(case_input)
    second = scenario.risk_scenarios(case_input)
    definition = scenario.build_definition(case_input)
    weights = dict(definition.problem.node_weights)

    assert first == second
    assert len(first) == 9
    assert next(item for item in first if item.scenario_id == "risk_1_1").pnl == 0.0
    assert all(0.0 < item.normalized_risk_weight <= 1.0 for item in first)
    assert max(item.normalized_risk_weight for item in first) == pytest.approx(1.0)
    assert weights == pytest.approx(
        {item.scenario_id: item.normalized_risk_weight for item in first}
    )


def test_four_products_produce_distinct_weighted_problem_hashes() -> None:
    """验证产品重估差异进入 Problem 身份，而不是复用固定风险图。"""
    scenario = PROBLEM_SCENARIOS["derivatives"]
    definitions = [
        scenario.build_definition(replace(scenario.default_input(), product=product))
        for product in (
            "european_call",
            "european_put",
            "asian_call",
            "up_and_out_call",
        )
    ]

    assert len({item.problem.stable_hash() for item in definitions}) == 4
    assert len({item.problem.node_weights for item in definitions}) == 4


def test_barrier_scenario_already_knocked_out_at_start_has_zero_local_risk() -> None:
    """验证压力起点触障时不把无效状态继续送入障碍期权定价器。"""
    scenario = PROBLEM_SCENARIOS["derivatives"]
    case_input = replace(
        scenario.default_input(),
        product="up_and_out_call",
        spot=120.0,
        barrier=130.0,
    )
    scenarios = scenario.risk_scenarios(case_input)
    knocked_out = [
        item for item in scenarios if item.stressed_spot >= case_input.barrier
    ]

    assert knocked_out
    assert all(item.stressed_price == 0.0 for item in knocked_out)
    assert all(item.delta == item.gamma == item.vega == 0.0 for item in knocked_out)


def test_mwis_weights_enter_analog_local_detuning_without_digital_residual() -> None:
    """验证风险权重真正进入 AHS 局域失谐，不只停留在 Problem 元数据。"""
    scenario = PROBLEM_SCENARIOS["derivatives"]
    executor = ScenarioExecutor()
    analysis = executor.analyze(scenario, scenario.default_input())
    compiled = executor.compiler.compile(
        analysis.definition.problem,
        mode="analog",
        algorithm="qaa",
        target=executor.target,
    )
    feasibility = analysis.problem_analysis.mapping_plan.feasibility_for("analog")
    local_terms = compiled.program.to_ir().hamiltonian.local_detuning_terms
    addressing = local_terms[0].to_dict()["addressing"]

    assert feasibility.digital_term_ids == ()
    assert len(local_terms) == 1
    assert tuple(addressing["site_ids"]) == analysis.definition.problem.nodes
    assert tuple(addressing["weights"][0]) == pytest.approx(
        tuple(weight for _, weight in analysis.definition.problem.node_weights)
    )


def test_analysis_payload_uses_the_same_revaluation_facts_as_the_problem() -> None:
    """验证输入表、P&L 热图和 Problem 权重没有各自重复计算。"""
    scenario = PROBLEM_SCENARIOS["derivatives"]
    case_input = replace(scenario.default_input(), product="asian_call")
    analysis = ScenarioExecutor().analyze(scenario, case_input)
    payload = analysis_payload("derivatives", case_input, analysis)
    facts = {item.scenario_id: item for item in scenario.risk_scenarios(case_input)}
    visual_cells = {
        item["id"]: item for item in payload["scenarioVisual"]["matrix"]["cells"]
    }
    diagonal_weights = {
        item["left"]: item["value"]
        for item in payload["problem"]["matrix"]["cells"]
        if item["left"] == item["right"]
    }

    assert {item["id"] for item in payload["inputRows"]} == set(facts)
    assert set(visual_cells) == set(facts)
    for scenario_id, fact in facts.items():
        assert visual_cells[scenario_id]["value"] == pytest.approx(fact.pnl)
        assert visual_cells[scenario_id]["stressedPrice"] == pytest.approx(
            fact.stressed_price
        )
        assert visual_cells[scenario_id]["riskWeight"] == pytest.approx(
            fact.normalized_risk_weight
        )
        assert diagonal_weights[scenario_id] == pytest.approx(
            fact.normalized_risk_weight
        )


def test_analog_risk_grid_runs_without_changing_price() -> None:
    """验证 Analog 情景选择不会篡改独立经典定价链路的价格。"""
    scenario = PROBLEM_SCENARIOS["derivatives"]
    case_input = scenario.default_input()
    price_before = scenario.price(case_input)
    result = ScenarioExecutor().run(
        scenario,
        case_input,
        mode="analog",
        parameter_sets=({"anneal_time": 0.6, "omega_max": 1.0},),
        shots=8,
        seed=17,
    )
    price_after = scenario.price(case_input)

    assert result.mode == "analog"
    assert sum(result.execution.result.counts.values()) == 8
    assert price_before == price_after
    assert "reference_price" not in result.execution.to_dict()
    assert (
        tuple(item.scenario_id for item in result.business_candidate.selected_scenarios)
        == result.business_candidate.selected_scenario_ids
    )
    payload = execution_payload("derivatives", case_input, result)
    assert payload["business"]["pricing"]["reference_price"] == pytest.approx(
        price_before.reference_price
    )
    assert len(payload["business"]["riskScenarios"]) == 9
