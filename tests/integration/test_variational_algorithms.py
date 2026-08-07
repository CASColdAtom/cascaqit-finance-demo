"""QAOA 自动选层、VQE 和发布前层数校准的真实执行测试。"""

from __future__ import annotations

import pytest

from cascaqit_finance_demo import (
    CollateralScenario,
    FraudRoutingScenario,
    ScenarioExecutor,
    SettlementScenario,
)
from cascaqit_finance_demo.api.catalog import preset_input
from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS


@pytest.mark.parametrize(
    ("case_id", "budget", "parameter_count", "entanglement"),
    [
        ("portfolio", 14, 12, "circular"),
        ("collateral", 10, 8, "linear"),
        ("liquidity", 18, 16, "linear"),
        ("credit_limits", 16, 14, "linear"),
    ],
)
def test_digital_scenarios_execute_real_hardware_efficient_vqe(
    case_id: str,
    budget: int,
    parameter_count: int,
    entanglement: str,
) -> None:
    """VQE 必须真实进入编译、连续优化、采样和业务解码，不只返回配置字段。"""
    scenario = PROBLEM_SCENARIOS[case_id]
    result = ScenarioExecutor().run(
        scenario,
        scenario.default_input(),
        mode="digital",
        algorithm="vqe",
        search_strategy="continuous",
        parameter_budget=budget,
        optimizer_starts=1,
        shots=4,
        seed=7,
    )

    ansatz = result.execution.context.ansatz
    assert result.execution.algorithm == "vqe"
    assert result.algorithm_plan.resolved_algorithm == "vqe"
    assert result.algorithm_plan.problem_hash == result.execution.problem_hash
    assert result.algorithm_plan.optimizer_method == "COBYLA"
    assert result.algorithm_plan.per_start_evaluation_budget == budget
    assert ansatz is not None
    assert ansatz.ansatz_kind == "hardware_efficient"
    assert ansatz.definition["rotation_axes"] == ("ry",)
    assert ansatz.definition["entanglement"] == entanglement
    assert len(result.execution.context.parameter_schema.parameters) == parameter_count
    assert len(result.execution.parameter_history) == budget
    assert sum(result.execution.result.counts.values()) == 4


def test_collateral_qaoa_and_vqe_share_problem_and_decoder_contract() -> None:
    """算法对照只能替换 Ansatz，不能偷偷改变 Problem 或解码语义。"""
    scenario = CollateralScenario()
    case_input = scenario.default_input()
    executor = ScenarioExecutor()
    common = {
        "mode": "digital",
        "layers": 1,
        "search_strategy": "continuous",
        "parameter_budget": 10,
        "optimizer_starts": 1,
        "shots": 2,
        "seed": 19,
    }

    qaoa = executor.run(scenario, case_input, algorithm="qaoa", **common)
    vqe = executor.run(scenario, case_input, algorithm="vqe", **common)

    assert qaoa.execution.problem_hash == vqe.execution.problem_hash
    assert qaoa.execution.analysis_hash == vqe.execution.analysis_hash
    assert qaoa.execution.logical_order == vqe.execution.logical_order
    assert (
        qaoa.execution.context.analysis.logical_hamiltonian.stable_hash()
        == vqe.execution.context.analysis.logical_hamiltonian.stable_hash()
    )
    assert qaoa.execution.baseline == vqe.execution.baseline
    assert qaoa.definition.problem is qaoa.analysis.definition.problem
    assert vqe.definition.problem is vqe.analysis.definition.problem


def test_adaptive_qaoa_keeps_all_layers_and_decodes_selected_execution() -> None:
    """自动选层保留逐层证据，金融候选只能来自 SDK 选中的执行结果。"""
    scenario = CollateralScenario()
    result = ScenarioExecutor().run(
        scenario,
        scenario.default_input(),
        mode="digital",
        algorithm="qaoa",
        layer_policy="adaptive",
        max_layers=2,
        search_strategy="continuous",
        parameter_budget=6,
        optimizer_starts=1,
        shots=4,
        seed=11,
    )

    experiment = result.layer_experiment
    assert experiment is not None
    assert tuple(step.layers for step in experiment.steps) in {(1,), (1, 2)}
    assert result.execution is experiment.selected_execution
    assert result.metadata["layers"] == experiment.selected_layers
    assert result.metadata["parameter_set_count"] == experiment.total_evaluation_count
    assert (
        result.business_candidate.bitstring
        == scenario.decode(
            scenario.default_input(),
            result.definition,
            experiment.selected_execution.best_observed_candidate,
        ).bitstring
    )


def test_layer_calibration_uses_paired_repeats_and_quantum_candidates() -> None:
    """发布校准使用 SDK 配对重复实验，并单独复核每个量子候选的业务约束。"""
    scenario = CollateralScenario()
    result = ScenarioExecutor().calibrate_layers(
        scenario,
        scenario.default_input(),
        mode="digital",
        algorithm="qaoa",
        max_layers=1,
        repeats=2,
        parameter_budget=4,
        optimizer_starts=1,
        shots=1,
        seed=7,
    )

    assert result.experiment.selected_layers == 1
    assert result.experiment.total_optimization_count == 2
    assert len(result.business_candidates) == 2
    assert 0.0 <= result.feasible_rate <= 1.0


def test_hqla_calibration_selects_p2_and_stops_after_p3_regression() -> None:
    """p=2 获得可信改善后继续检查 p=3，并在回退时保留 p=2。"""
    result = ScenarioExecutor().calibrate_layers(
        CollateralScenario(),
        preset_input("collateral", "hqla"),
        mode="digital",
        algorithm="qaoa",
        max_layers=3,
        repeats=3,
        parameter_budget=12,
        optimizer_starts=1,
        shots=1,
        seed=7,
    )

    experiment = result.experiment
    assert tuple(step.layers for step in experiment.steps) == (1, 2, 3)
    assert experiment.selected_layers == 2
    assert experiment.stop_reason == "patience_exhausted"
    assert experiment.steps[1].comparison.lower_confidence_bound > 0.0
    assert experiment.steps[1].material_improvement is True
    assert experiment.steps[2].comparison.lower_confidence_bound < 0.0
    assert experiment.steps[2].material_improvement is False
    assert experiment.total_optimization_count == 9


@pytest.mark.parametrize("scenario_type", [SettlementScenario, FraudRoutingScenario])
def test_hybrid_qaoa_supports_two_complete_dad_layers(scenario_type: type) -> None:
    """两层 Hybrid 必须保留完整 D-A-D 结构和逐层独立参数。"""
    scenario = scenario_type()
    result = ScenarioExecutor().run(
        scenario,
        scenario.default_input(),
        mode="hybrid",
        algorithm="qaoa",
        layers=2,
        parameter_sets=(
            {
                "gamma_0": 0.16,
                "beta_0": 0.24,
                "gamma_1": 0.12,
                "beta_1": 0.20,
            },
        ),
        shots=1,
        seed=29,
    )

    context = result.execution.context
    assert result.execution.topology == "dad"
    assert [block.block_type for block in context.native_program.blocks] == [
        "digital",
        "analog",
        "digital",
        "analog",
        "digital",
        "measure",
    ]
    assert {item.name for item in context.parameter_schema.parameters} == {
        "gamma_0",
        "gamma_1",
        "beta_0",
        "beta_1",
    }
    assert sum(result.execution.result.counts.values()) == 1
    assert all(
        item.analog_coefficient + item.digital_coefficient
        == pytest.approx(item.logical_coefficient)
        for item in context.term_mapping
    )
