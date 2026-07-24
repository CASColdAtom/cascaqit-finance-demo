"""合成衍生品场景使用的小型确定性经典定价实现。

这些价格和 Greeks 只作为业务基准；量子实验负责选择代表性风险情景，
不会把采样计数伪装成衍生品价格。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

ProductKind = Literal["european_call", "european_put", "asian_call", "up_and_out_call"]


@dataclass(frozen=True)
class DerivativeInput:
    """一次定价所需的合成市场参数、产品类型和 Monte Carlo 配置。"""

    product: ProductKind = "european_call"
    spot: float = 100.0
    strike: float = 102.0
    volatility: float = 0.24
    rate: float = 0.025
    maturity: float = 1.0
    barrier: float = 130.0
    paths: int = 2048
    observations: int = 12
    seed: int = 2026


@dataclass(frozen=True)
class DerivativePricingResult:
    """经典模型计算的参考价格和敏感度，明确不来自量子采样计数。"""

    product: ProductKind
    method: str
    reference_price: float
    cross_check_price: float | None
    delta: float
    gamma: float
    vega: float
    standard_error: float | None
    knockout_probability: float | None
    paths: int | None


def price_derivative(case_input: DerivativeInput) -> DerivativePricingResult:
    """按产品选择解析或模拟定价方法，并以有限差分计算 Greeks。"""
    _validate(case_input)
    if case_input.product in {"european_call", "european_put"}:
        is_call = case_input.product == "european_call"
        price = _black_scholes(case_input, is_call=is_call)
        cross_check = _binomial(case_input, is_call=is_call, steps=256)
        delta, gamma, vega = _finite_difference_greeks(
            case_input,
            lambda item: _black_scholes(item, is_call=is_call),
        )
        return DerivativePricingResult(
            product=case_input.product,
            method="Black-Scholes",
            reference_price=price,
            cross_check_price=cross_check,
            delta=delta,
            gamma=gamma,
            vega=vega,
            standard_error=None,
            knockout_probability=None,
            paths=None,
        )

    price, error, knockout = _monte_carlo(case_input)

    def mc_price(item: DerivativeInput) -> float:
        """为有限差分提供只返回价格的固定随机种子 Monte Carlo 函数。"""
        return _monte_carlo(item)[0]

    delta, gamma, vega = _finite_difference_greeks(case_input, mc_price)
    return DerivativePricingResult(
        product=case_input.product,
        method="固定 seed Monte Carlo",
        reference_price=price,
        cross_check_price=None,
        delta=delta,
        gamma=gamma,
        vega=vega,
        standard_error=error,
        knockout_probability=knockout,
        paths=case_input.paths,
    )


def _black_scholes(case_input: DerivativeInput, *, is_call: bool) -> float:
    """使用 Black-Scholes 闭式公式计算欧式看涨或看跌期权价格。"""
    root_t = math.sqrt(case_input.maturity)
    sigma_t = case_input.volatility * root_t
    d1 = (
        math.log(case_input.spot / case_input.strike)
        + (case_input.rate + 0.5 * case_input.volatility**2) * case_input.maturity
    ) / sigma_t
    d2 = d1 - sigma_t
    discount = math.exp(-case_input.rate * case_input.maturity)
    if is_call:
        return case_input.spot * _normal_cdf(
            d1
        ) - case_input.strike * discount * _normal_cdf(d2)
    return case_input.strike * discount * _normal_cdf(
        -d2
    ) - case_input.spot * _normal_cdf(-d1)


def _binomial(case_input: DerivativeInput, *, is_call: bool, steps: int) -> float:
    """使用重组二叉树为欧式期权提供独立的数值交叉检查。"""
    dt = case_input.maturity / steps
    up = math.exp(case_input.volatility * math.sqrt(dt))
    down = 1.0 / up
    growth = math.exp(case_input.rate * dt)
    probability = (growth - down) / (up - down)
    terminal = np.arange(steps + 1, dtype=float)
    prices = case_input.spot * up ** (steps - terminal) * down**terminal
    values = np.maximum(
        prices - case_input.strike if is_call else case_input.strike - prices,
        0.0,
    )
    discount = math.exp(-case_input.rate * dt)
    for _ in range(steps):
        values = discount * (
            probability * values[:-1] + (1.0 - probability) * values[1:]
        )
    return float(values[0])


def _monte_carlo(case_input: DerivativeInput) -> tuple[float, float, float | None]:
    """用固定种子路径模拟计算亚式或向上敲出看涨期权价格。"""
    rng = np.random.default_rng(case_input.seed)
    dt = case_input.maturity / case_input.observations
    shocks = rng.standard_normal((case_input.paths, case_input.observations))
    increments = (
        case_input.rate - 0.5 * case_input.volatility**2
    ) * dt + case_input.volatility * math.sqrt(dt) * shocks
    paths = case_input.spot * np.exp(np.cumsum(increments, axis=1))
    knockout_probability: float | None = None
    if case_input.product == "asian_call":
        payoff = np.maximum(paths.mean(axis=1) - case_input.strike, 0.0)
    else:
        knocked_out = np.max(paths, axis=1) >= case_input.barrier
        payoff = np.where(
            knocked_out,
            0.0,
            np.maximum(paths[:, -1] - case_input.strike, 0.0),
        )
        knockout_probability = float(np.mean(knocked_out))
    discounted = math.exp(-case_input.rate * case_input.maturity) * payoff
    return (
        float(np.mean(discounted)),
        float(np.std(discounted, ddof=1) / math.sqrt(case_input.paths)),
        knockout_probability,
    )


def _finite_difference_greeks(
    case_input: DerivativeInput,
    pricing_function,
) -> tuple[float, float, float]:
    """通过中心有限差分计算 Delta、Gamma 和 Vega，保持方法通用。"""
    spot_step = max(0.1, case_input.spot * 0.005)
    vol_step = 0.001
    up = _replace(case_input, spot=case_input.spot + spot_step)
    down = _replace(case_input, spot=case_input.spot - spot_step)
    base = pricing_function(case_input)
    up_price = pricing_function(up)
    down_price = pricing_function(down)
    delta = (up_price - down_price) / (2.0 * spot_step)
    gamma = (up_price - 2.0 * base + down_price) / (spot_step**2)
    vega = (
        pricing_function(
            _replace(case_input, volatility=case_input.volatility + vol_step)
        )
        - pricing_function(
            _replace(case_input, volatility=case_input.volatility - vol_step)
        )
    ) / (2.0 * vol_step)
    return float(delta), float(gamma), float(vega)


def _replace(case_input: DerivativeInput, **values) -> DerivativeInput:
    """复制不可变定价输入，仅替换有限差分需要扰动的字段。"""
    payload = case_input.__dict__ | values
    return DerivativeInput(**payload)


def _normal_cdf(value: float) -> float:
    """使用误差函数计算标准正态分布累积分布值。"""
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _validate(case_input: DerivativeInput) -> None:
    """集中验证产品枚举、正值市场参数和模拟规模下限。"""
    if case_input.product not in {
        "european_call",
        "european_put",
        "asian_call",
        "up_and_out_call",
    }:
        raise ValueError("unsupported derivative product.")
    if (
        min(
            case_input.spot,
            case_input.strike,
            case_input.volatility,
            case_input.maturity,
        )
        <= 0.0
    ):
        raise ValueError("spot, strike, volatility, and maturity must be positive.")
    if case_input.paths < 128 or case_input.observations < 2:
        raise ValueError("Monte Carlo paths or observations are too small.")
    if (
        case_input.product == "up_and_out_call"
        and case_input.barrier <= case_input.spot
    ):
        raise ValueError("barrier must be above spot for the up-and-out product.")
