"""金融 Demo 参数搜索策略的确定性与边界测试。"""

from __future__ import annotations

import math

import pytest

from cascaqit_finance_demo.quantum import (
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
