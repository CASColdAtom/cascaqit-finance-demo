"""金融 Demo 参数搜索策略的确定性与边界测试。"""

from __future__ import annotations

import math

import pytest

from cascaqit_finance_demo.quantum import (
    build_optimizer_config,
    default_parameter_sets,
    generate_parameter_sets,
)


def test_multilayer_presets_expand_to_exact_qaoa_schema() -> None:
    """验证 p 层预设恰好包含 p 个 gamma 和 p 个 beta。"""
    points = default_parameter_sets("digital", layers=3)

    assert len(points) == 2
    assert all(
        set(point)
        == {
            "gamma_0",
            "gamma_1",
            "gamma_2",
            "beta_0",
            "beta_1",
            "beta_2",
        }
        for point in points
    )


def test_seeded_sample_is_reproducible_and_respects_angle_domains() -> None:
    """验证固定 seed 生成完全一致且位于约定角度区间内的多层参数。"""
    first = generate_parameter_sets(
        "digital", layers=2, strategy="seeded_sample", budget=8, seed=41
    )
    second = generate_parameter_sets(
        "digital", layers=2, strategy="seeded_sample", budget=8, seed=41
    )

    assert first == second
    assert len(first) == 8
    assert all(
        0.0 <= value <= math.pi
        for point in first
        for name, value in point.items()
        if name.startswith("gamma_")
    )
    assert all(
        -math.pi / 2.0 <= value <= math.pi / 2.0
        for point in first
        for name, value in point.items()
        if name.startswith("beta_")
    )


def test_grid_search_honors_budget_without_duplicate_points() -> None:
    """验证一层二维网格严格遵守预算并且不产生重复坐标。"""
    points = generate_parameter_sets(
        "digital", layers=1, strategy="grid", budget=12, seed=7
    )

    assert len(points) == 12
    assert len({(point["gamma_0"], point["beta_0"]) for point in points}) == 12


def test_continuous_optimizer_uses_explicit_per_start_budget() -> None:
    """连续优化必须把单起点评估预算和起点数分别交给 CASCAQit。"""
    config = build_optimizer_config(
        mode="hybrid",
        layers=1,
        evaluation_budget=8,
        starts=3,
        seed=41,
    )

    assert config.method == "COBYLA"
    assert config.max_iterations == 8
    assert config.max_evaluations == 8
    assert config.starts == 3
    assert config.seed == 41
    assert config.gradient is None


@pytest.mark.parametrize(
    ("mode", "layers", "evaluation_budget", "starts"),
    [
        ("analog", 2, 8, 1),
        ("digital", 1, 3, 1),
        ("digital", 1, 8, 0),
        ("digital", 1, 8, 4),
    ],
)
def test_continuous_optimizer_rejects_unsupported_budget_shape(
    mode: str,
    layers: int,
    evaluation_budget: int,
    starts: int,
) -> None:
    """连续优化不静默修正层数、过小预算或越界起点数。"""
    with pytest.raises(ValueError):
        build_optimizer_config(  # type: ignore[arg-type]
            mode=mode,
            layers=layers,
            evaluation_budget=evaluation_budget,
            starts=starts,
            seed=7,
        )


def test_discrete_search_rejects_optimizer_starts() -> None:
    """多起点参数不能在离散扫描中被静默忽略。"""
    from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS
    from cascaqit_finance_demo.quantum import ScenarioExecutor

    scenario = PROBLEM_SCENARIOS["portfolio"]
    with pytest.raises(ValueError, match="only with continuous"):
        ScenarioExecutor().run(
            scenario,
            scenario.default_input(),
            search_strategy="preset",
            optimizer_starts=2,
            shots=1,
        )


@pytest.mark.parametrize(
    ("mode", "layers", "strategy", "budget"),
    [
        ("hybrid", 2, "preset", 2),
        ("analog", 1, "seeded_sample", 2),
        ("digital", 2, "grid", 4),
        ("digital", 1, "preset", 3),
        ("digital", 1, "seeded_sample", 25),
    ],
)
def test_parameter_search_rejects_unsupported_shapes(
    mode: str,
    layers: int,
    strategy: str,
    budget: int,
) -> None:
    """验证层数、策略或预算越界时明确失败。"""
    with pytest.raises(ValueError):
        generate_parameter_sets(  # type: ignore[arg-type]
            mode,
            layers=layers,
            strategy=strategy,
            budget=budget,
            seed=7,
        )
