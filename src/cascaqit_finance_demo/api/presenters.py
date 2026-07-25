"""把金融领域、编译和执行对象转换为前端使用的 JSON 展示模型。"""

from __future__ import annotations

from dataclasses import asdict, replace
from math import sqrt
from typing import Any

from cascaqit_finance_demo.cases.constrained_selection import SelectionInput
from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS
from cascaqit_finance_demo.domain.models import (
    FraudRoutingInput,
    PortfolioInput,
    SettlementInput,
)


def analysis_payload(case_id: str, case_input: Any, analysis: Any) -> dict[str, Any]:
    """输出编译器分析事实，同时避免泄漏 Bokeh 或 Python 专用对象。"""
    problem = analysis.definition.problem
    mapping = analysis.problem_analysis.mapping_plan
    canonical = analysis.problem_analysis.canonical_problem
    variables = tuple(getattr(problem, "variables", getattr(problem, "nodes", ())))
    cells = _matrix_cells(problem)
    return {
        "caseId": case_id,
        "inputRows": _input_rows(case_id, case_input),
        "problem": {
            "id": canonical.problem_id,
            "type": canonical.problem_type,
            "hash": canonical.problem_hash,
            "variables": list(variables),
            "matrix": {"variables": list(variables), "cells": cells},
            "termGroups": [asdict(group) for group in analysis.definition.term_groups],
        },
        "resource": dict(mapping.resource_estimate),
        "layout": [
            {
                "id": site.logical_id,
                "x": float(site.position[0]),
                "y": float(site.position[1]),
            }
            for site in mapping.layout.sites
        ],
        "scenarioVisual": _scenario_visual(case_id, case_input),
        "decision": {
            "recommendedMode": analysis.mode_decision.recommended_mode,
            "reason": analysis.mode_decision.reason,
            "modes": [
                {
                    "mode": row.mode,
                    "algorithm": row.algorithm,
                    "status": row.status,
                    "compilerFeasible": row.compiler_feasible,
                    "businessSuitable": row.business_suitable,
                    "reason": row.reason,
                    "diagnosticCodes": list(row.diagnostic_codes),
                    "analogTermCount": row.analog_term_count,
                    "digitalTermCount": row.digital_term_count,
                    "analogBusinessPairs": [
                        list(pair) for pair in row.analog_business_pairs
                    ],
                    "coveredGroupIds": list(row.covered_group_ids),
                    "missingContributionIds": list(row.missing_contribution_ids),
                    "unexpectedAnalogTermIds": list(row.unexpected_analog_term_ids),
                    "unexpectedInteractionPairs": [
                        list(pair) for pair in row.unexpected_interaction_pairs
                    ],
                    "geometryStatus": row.geometry_status,
                    "geometrySource": row.geometry_source,
                    "layoutPolicy": row.layout_policy,
                    "declaredContributionCount": row.declared_contribution_count,
                    "coveredContributionCount": row.covered_contribution_count,
                }
                for row in analysis.mode_decision.rows
            ],
        },
    }


def execution_payload(case_id: str, case_input: Any, result: Any) -> dict[str, Any]:
    """将一次真实执行整理为业务、量子实验和审计三个视图的数据。"""
    analysis = analysis_payload(case_id, case_input, result.analysis)
    return {
        "analysis": analysis,
        "business": _business_payload(case_id, case_input, result),
        "quantum": _quantum_payload(result),
        "audit": _audit_payload(result),
    }


def _input_rows(case_id: str, case_input: Any) -> list[dict[str, str]]:
    """按场景提取适合紧凑表格展示的主要输入行。"""
    rows: list[dict[str, str]] = []
    if isinstance(case_input, PortfolioInput):
        rows = [
            {
                "id": asset.asset_id,
                "label": asset.name,
                "group": asset.sector,
                "primary": f"{asset.expected_return:.1%}",
                "secondary": f"{asset.volatility:.1%}",
                "detail": "防御资产" if asset.defensive else "风险资产",
            }
            for asset in case_input.assets
        ]
    elif isinstance(case_input, SettlementInput):
        rows = [
            {
                "id": item.trade_id,
                "label": item.trade_id,
                "group": item.currency,
                "primary": f"{item.notional_m:.1f}m",
                "secondary": f"P{item.priority}",
                "detail": (
                    f"额度 {item.cash_units} / "
                    f"依赖 {','.join(item.requires) or '-'}"
                ),
            }
            for item in case_input.instructions
        ]
    elif isinstance(case_input, FraudRoutingInput):
        rows = [
            {
                "id": item.alert_id,
                "label": item.alert_id,
                "group": item.entity_id,
                "primary": f"风险 {item.risk_score:.0f}",
                "secondary": f"{item.exposure_m:.1f}m",
                "detail": f"{item.age_hours:.0f}h / {item.estimated_hours:.1f} 工时",
            }
            for item in case_input.alerts
        ]
    elif isinstance(case_input, SelectionInput):
        rows = [
            {
                "id": item.item_id,
                "label": item.label,
                "group": item.group,
                "primary": f"{item.value:.2f}",
                "secondary": f"{item.cost:.2f}",
                "detail": f"{item.detail} / units {item.units}",
            }
            for item in case_input.items
        ]
    else:
        scenario = PROBLEM_SCENARIOS[case_id]
        rows = [
            {
                "id": scenario._node_id(row, column),
                "label": f"S {spot:+.0%} / σ {vol:+.0%}",
                "group": "风险情景",
                "primary": f"S={case_input.spot * (1 + spot):.1f}",
                "secondary": f"σ={max(0.01, case_input.volatility + vol):.1%}",
                "detail": "Analog 候选",
            }
            for row, vol in enumerate(scenario.volatility_shocks)
            for column, spot in enumerate(scenario.spot_shocks)
        ]
    return rows


def _scenario_visual(case_id: str, case_input: Any) -> dict[str, Any]:
    """构造运行前后共用的业务原生图表模型，不掺入量子结果。"""
    visual = {
        "kind": "",
        "title": "",
        "subtitle": "",
        "xLabel": "",
        "yLabel": "",
        "categories": [],
        "nodes": [],
        "edges": [],
        "points": [],
        "matrix": {"xLabels": [], "yLabels": [], "cells": []},
        "series": [],
    }
    if isinstance(case_input, PortfolioInput):
        names = [asset.name for asset in case_input.assets]
        cells = []
        for row, left in enumerate(case_input.assets):
            for column, right in enumerate(case_input.assets):
                diagonal_product = (
                    case_input.covariance[row][row]
                    * case_input.covariance[column][column]
                )
                denominator = sqrt(max(0.0, diagonal_product))
                correlation = (
                    case_input.covariance[row][column] / denominator
                    if denominator > 0.0
                    else 0.0
                )
                cells.append(
                    {
                        "id": f"{left.asset_id}:{right.asset_id}",
                        "x": column,
                        "y": row,
                        "value": max(-1.0, min(1.0, correlation)),
                        "label": f"{left.name} / {right.name}",
                    }
                )
        return {
            **visual,
            "kind": "portfolio-correlation",
            "title": "资产相关性矩阵",
            "subtitle": "由当前协方差与波动率计算，显示组合风险的稠密连接。",
            "xLabel": "资产",
            "yLabel": "资产",
            "matrix": {"xLabels": names, "yLabels": names, "cells": cells},
        }

    if isinstance(case_input, SettlementInput):
        network = _business_network(case_id, case_input) or {"nodes": [], "edges": []}
        nodes = [
            {
                **node,
                "label": node["id"],
                "role": "trade",
                "detail": next(
                    f"P{item.priority} / {item.cash_units} 资金单位"
                    for item in case_input.instructions
                    if item.trade_id == node["id"]
                ),
            }
            for node in network["nodes"]
        ]
        return {
            **visual,
            "kind": "settlement-network",
            "title": "交易冲突与前置依赖",
            "subtitle": "实线表示不可同批结算，虚线箭头表示前置依赖。",
            "categories": sorted({item.currency for item in case_input.instructions}),
            "nodes": nodes,
            "edges": network["edges"],
        }

    if isinstance(case_input, FraudRoutingInput):
        entity_counts: dict[str, int] = {}
        for alert in case_input.alerts:
            entity_counts[alert.entity_id] = entity_counts.get(alert.entity_id, 0) + 1
        nodes = [
            {
                "id": alert.alert_id,
                "label": alert.alert_id,
                "group": "告警",
                "role": "alert",
                "value": alert.risk_score,
                "detail": f"风险 {alert.risk_score:.0f} / {alert.exposure_m:.1f}m",
            }
            for alert in case_input.alerts
        ] + [
            {
                "id": entity_id,
                "label": entity_id,
                "group": "关键实体",
                "role": "entity",
                "value": count,
                "detail": f"关联 {count} 条告警",
            }
            for entity_id, count in sorted(entity_counts.items())
        ]
        edges = [
            {
                "source": alert.alert_id,
                "target": alert.entity_id,
                "kind": "association",
                "value": 1.0,
            }
            for alert in case_input.alerts
        ]
        return {
            **visual,
            "kind": "fraud-entity-network",
            "title": "告警与关键实体网络",
            "subtitle": "共享实体形成局域冲突，节点大小表示告警风险。",
            "categories": ["告警", "关键实体"],
            "nodes": nodes,
            "edges": edges,
        }

    if isinstance(case_input, SelectionInput):
        if case_id == "collateral":
            groups = sorted({item.group for item in case_input.items})
            nodes = [
                {
                    "id": item.item_id,
                    "label": item.label.split(" -> ", 1)[0],
                    "group": "抵押品",
                    "role": "source",
                    "value": item.units,
                    "detail": item.detail,
                }
                for item in case_input.items
            ] + [
                {
                    "id": f"requirement:{group}",
                    "label": group,
                    "group": "保证金需求",
                    "role": "target",
                    "value": sum(
                        item.units for item in case_input.items if item.group == group
                    ),
                    "detail": "保证金需求桶",
                }
                for group in groups
            ]
            edges = [
                {
                    "id": item.item_id,
                    "source": item.item_id,
                    "target": f"requirement:{item.group}",
                    "kind": "allocation",
                    "value": float(item.units),
                    "label": item.label,
                }
                for item in case_input.items
            ]
            return {
                **visual,
                "kind": "collateral-flow",
                "title": "抵押品与保证金需求流",
                "subtitle": "流宽表示覆盖单位，运行后高亮当前分配路径。",
                "categories": ["抵押品", "保证金需求"],
                "nodes": nodes,
                "edges": edges,
            }

        if case_id == "liquidity":
            points = []
            by_currency: dict[str, list[dict[str, Any]]] = {}
            for item in case_input.items:
                minute = _minute_from_detail(item.detail)
                point = {
                    "id": item.item_id,
                    "label": item.label,
                    "group": item.group,
                    "x": minute,
                    "y": float(item.units),
                    "value": item.value,
                    "size": float(item.units),
                    "detail": item.detail,
                }
                points.append(point)
                by_currency.setdefault(item.group, []).append(point)
            series = []
            for currency, items in sorted(by_currency.items()):
                cumulative = 0.0
                series_points = []
                for point in sorted(items, key=lambda item: item["x"]):
                    cumulative += point["y"]
                    series_points.append(
                        {"x": point["x"], "y": cumulative, "id": point["id"]}
                    )
                series.append(
                    {"name": currency, "group": currency, "points": series_points}
                )
            return {
                **visual,
                "kind": "liquidity-timeline",
                "title": "日内资金动作与累计覆盖",
                "subtitle": "散点为可选动作，折线为各币种候选资金的累计覆盖。",
                "xLabel": "日内时点",
                "yLabel": "资金单位",
                "categories": sorted(by_currency),
                "points": points,
                "series": series,
            }

        return {
            **visual,
            "kind": "credit-capital-map",
            "title": "资本效率与行业集中度",
            "subtitle": "横轴为资本成本，纵轴为风险调整价值，气泡大小表示资本占用。",
            "xLabel": "资本成本",
            "yLabel": "风险调整价值",
            "categories": sorted({item.group for item in case_input.items}),
            "points": [
                {
                    "id": item.item_id,
                    "label": item.label,
                    "group": item.group,
                    "x": item.cost,
                    "y": item.value,
                    "value": item.value / item.cost if item.cost else 0.0,
                    "size": float(item.units),
                    "detail": item.detail,
                }
                for item in case_input.items
            ],
        }

    scenario = PROBLEM_SCENARIOS[case_id]
    base_price = scenario.price(case_input).reference_price
    x_labels = [f"{shock:+.0%}" for shock in scenario.spot_shocks]
    y_labels = [f"{shock:+.0%}" for shock in scenario.volatility_shocks]
    cells = []
    for row, volatility_shock in enumerate(scenario.volatility_shocks):
        for column, spot_shock in enumerate(scenario.spot_shocks):
            stressed_spot = case_input.spot * (1.0 + spot_shock)
            stressed_volatility = max(0.01, case_input.volatility + volatility_shock)
            if (
                case_input.product == "up_and_out_call"
                and stressed_spot >= case_input.barrier
            ):
                stressed_price = 0.0
            else:
                stressed_price = scenario.price(
                    replace(
                        case_input,
                        spot=stressed_spot,
                        volatility=stressed_volatility,
                    )
                ).reference_price
            cells.append(
                {
                    "id": scenario._node_id(row, column),
                    "x": column,
                    "y": row,
                    "value": stressed_price - base_price,
                    "label": f"S {spot_shock:+.0%} / σ {volatility_shock:+.0%}",
                }
            )
    return {
        **visual,
        "kind": "derivatives-pnl-surface",
        "title": "衍生品压力情景损益",
        "subtitle": "每个格点由经典定价链重估；Analog 只选择代表情景。",
        "xLabel": "标的价格冲击",
        "yLabel": "波动率冲击",
        "matrix": {"xLabels": x_labels, "yLabels": y_labels, "cells": cells},
    }


def _matrix_cells(problem: Any) -> list[dict[str, Any]]:
    """把 QUBO 稀疏系数展开为前端热力图所需的矩阵单元。"""
    cells: dict[tuple[str, str], float] = {}
    for variable, coefficient in getattr(problem, "linear_terms", ()):
        cells[(variable, variable)] = float(coefficient)
    for left, right, coefficient in getattr(problem, "quadratic_terms", ()):
        cells[(left, right)] = float(coefficient)
        cells[(right, left)] = float(coefficient)
    for left, right in getattr(problem, "edges", ()):
        cells[(left, right)] = 1.0
        cells[(right, left)] = 1.0
    return [
        {"left": left, "right": right, "value": value}
        for (left, right), value in sorted(cells.items())
    ]


def _business_payload(case_id: str, case_input: Any, result: Any) -> dict[str, Any]:
    """组合已展示解、候选解、经典基线、业务指标和关系网络。"""
    solution = result.displayed_solution
    selected = _selected_business_ids(solution)
    points = _business_points(case_id, case_input, result, selected)
    rows = []
    input_rows = _input_rows(case_id, case_input)
    reasons = getattr(solution, "exclusion_reasons", {})
    for row in input_rows:
        is_selected = row["id"] in selected
        rows.append(
            {
                **row,
                "selected": is_selected,
                "reason": "当前方案"
                if is_selected
                else reasons.get(row["id"], "未进入当前候选"),
            }
        )
    payload = {
        "metrics": _business_metrics(case_id, case_input, result),
        "chart": {
            **{
                "portfolio": {
                    "kind": "efficient-frontier",
                    "title": "可行组合与当前候选",
                    "xLabel": "波动率",
                    "yLabel": "预期收益",
                },
                "settlement": {
                    "kind": "settlement-bubbles",
                    "title": "结算金额与流动性占用",
                    "xLabel": "流动性占用 / 资金单位",
                    "yLabel": "名义金额 / m",
                },
                "fraud_routing": {
                    "kind": "risk-bubbles",
                    "title": "调查风险与金额覆盖",
                    "xLabel": "涉案金额 / m",
                    "yLabel": "风险分",
                },
                "collateral": {
                    "kind": "allocation-bars",
                    "title": "抵押品候选业务价值",
                    "xLabel": "业务价值",
                    "yLabel": "候选资产",
                },
                "liquidity": {
                    "kind": "funding-timeline",
                    "title": "入选资金动作时序",
                    "xLabel": "日内时点",
                    "yLabel": "资金单位",
                },
                "credit_limits": {
                    "kind": "capital-bubbles",
                    "title": "额度档位资本效率",
                    "xLabel": "资本成本",
                    "yLabel": "风险调整价值",
                },
                "derivatives": {
                    "kind": "risk-grid",
                    "title": "Analog 代表风险情景",
                    "xLabel": "标的价格冲击",
                    "yLabel": "波动率冲击",
                },
            }[case_id],
            "points": points,
        },
        "selection": rows,
        "checks": [asdict(check) for check in getattr(solution, "checks", ())],
        "displayedSource": result.metadata["displayed_source"],
        "candidate": asdict(result.business_candidate),
        "baseline": None
        if result.baseline_solution is None
        else asdict(result.baseline_solution),
        "network": _business_network(case_id, case_input),
    }
    if case_id == "derivatives":
        payload["pricing"] = asdict(PROBLEM_SCENARIOS[case_id].price(case_input))
    return payload


def _selected_business_ids(solution: Any) -> set[str]:
    """从不同场景结果的选择字段中提取统一业务 ID 集合。"""
    for field in (
        "selected_asset_ids",
        "selected_trade_ids",
        "selected_alert_ids",
        "selected_item_ids",
        "selected_scenario_ids",
    ):
        if hasattr(solution, field):
            return set(getattr(solution, field))
    return set()


def _business_points(
    case_id: str, case_input: Any, result: Any, selected: set[str]
) -> list[dict[str, Any]]:
    """把各类业务对象投影为散点图统一坐标、大小和选中状态。"""
    points: list[dict[str, Any]] = []
    if case_id == "portfolio":
        scenario = PROBLEM_SCENARIOS[case_id]
        for point in scenario.case.exact_business_points(case_input):
            points.append(
                {
                    "id": point.bitstring,
                    "label": " / ".join(point.asset_ids),
                    "group": "可行组合",
                    "x": point.volatility,
                    "y": point.expected_return,
                    "size": 8,
                    "selected": set(point.asset_ids) == selected,
                    "detail": f"目标 {point.objective_value:.4f}",
                }
            )
        return points
    if isinstance(case_input, SelectionInput):
        for item in case_input.items:
            x_value = (
                float(_minute_from_detail(item.detail))
                if case_id == "liquidity"
                else item.cost
            )
            y_value = float(item.units) if case_id == "liquidity" else item.value
            points.append(
                {
                    "id": item.item_id,
                    "label": item.label,
                    "group": item.group,
                    "x": x_value,
                    "y": y_value,
                    "size": max(8.0, min(30.0, float(item.units) * 2.5)),
                    "selected": item.item_id in selected,
                    "detail": item.detail,
                }
            )
        return points
    if isinstance(case_input, SettlementInput):
        source = (
            (
                item.trade_id,
                item.currency,
                item.cash_units,
                item.notional_m,
                item.priority,
            )
            for item in case_input.instructions
        )
    elif isinstance(case_input, FraudRoutingInput):
        source = (
            (
                item.alert_id,
                item.entity_id,
                item.exposure_m,
                item.risk_score,
                item.age_hours,
            )
            for item in case_input.alerts
        )
    else:
        scenario = PROBLEM_SCENARIOS[case_id]
        source = (
            (scenario._node_id(row, column), "风险情景", spot, vol, 1)
            for row, vol in enumerate(scenario.volatility_shocks)
            for column, spot in enumerate(scenario.spot_shocks)
        )
    for item_id, group, x_value, y_value, size_value in source:
        points.append(
            {
                "id": item_id,
                "label": item_id,
                "group": group,
                "x": float(x_value),
                "y": float(y_value),
                "size": max(8.0, min(30.0, float(size_value) * 2.5)),
                "selected": item_id in selected,
                "detail": group,
            }
        )
    return points


def _minute_from_detail(detail: str) -> int:
    """解析流动性动作详情中的固定时刻，并转换为日内分钟。"""
    time_text = detail.split(" / ", 1)[0]
    hours, minutes = (int(part) for part in time_text.split(":"))
    return hours * 60 + minutes


def _business_metrics(
    case_id: str, case_input: Any, result: Any
) -> list[dict[str, str]]:
    """按结果类型选取四个最能解释当前业务方案的摘要指标。"""
    solution = result.displayed_solution
    if hasattr(solution, "expected_return"):
        values = (
            ("预期收益", f"{solution.expected_return:.2%}", "组合年化"),
            ("波动率", f"{solution.volatility:.2%}", "等权组合"),
            ("入选资产", str(len(solution.selected_asset_ids)), "当前持仓"),
            ("业务约束", "通过" if solution.feasible else "未通过", "原始输入复核"),
        )
    elif hasattr(solution, "settled_notional_m"):
        values = (
            ("结算金额", f"{solution.settled_notional_m:.1f}m", "当前批次"),
            ("交易数", str(len(solution.selected_trade_ids)), "入选指令"),
            ("业务目标", f"{solution.business_objective:.3f}", "越低越优"),
            ("约束", "通过" if solution.feasible else "未通过", "流动性与依赖"),
        )
    elif hasattr(solution, "risk_coverage"):
        values = (
            ("风险覆盖", f"{solution.risk_coverage:.1%}", "入选告警"),
            ("金额覆盖", f"{solution.exposure_coverage:.1%}", "涉案金额"),
            ("调查任务", str(len(solution.selected_alert_ids)), "当前席位"),
            ("预计工时", f"{solution.estimated_work_hours:.1f}h", "人工复核"),
        )
    elif hasattr(solution, "total_value"):
        values = (
            ("业务价值", f"{solution.total_value:.2f}", "入选合计"),
            ("总成本", f"{solution.total_cost:.2f}", "资源成本"),
            ("资源单位", str(solution.total_units), "当前方案"),
            ("约束", "通过" if solution.feasible else "未通过", "业务复核"),
        )
    else:
        pricing = PROBLEM_SCENARIOS[case_id].price(case_input)
        values = (
            ("参考价格", f"{pricing.reference_price:.4f}", pricing.method),
            ("Delta", f"{pricing.delta:.4f}", "价格敏感度"),
            ("Gamma", f"{pricing.gamma:.4f}", "Delta 曲率"),
            ("Vega", f"{pricing.vega:.4f}", "波动率敏感度"),
        )
    return [
        {"label": label, "value": value, "context": context}
        for label, value, context in values
    ]


def _business_network(case_id: str, case_input: Any) -> dict[str, Any] | None:
    """为结算和反欺诈场景构建真实冲突、依赖或共享实体关系网。"""
    if isinstance(case_input, SettlementInput):
        nodes = [
            {"id": item.trade_id, "group": item.currency, "value": item.notional_m}
            for item in case_input.instructions
        ]
        edges = []
        seen = set()
        for item in case_input.instructions:
            for target in item.conflicts:
                key = tuple(sorted((item.trade_id, target)))
                if key not in seen:
                    edges.append(
                        {"source": key[0], "target": key[1], "kind": "conflict"}
                    )
                    seen.add(key)
            for target in item.requires:
                edges.append(
                    {"source": item.trade_id, "target": target, "kind": "dependency"}
                )
        return {"nodes": nodes, "edges": edges}
    if isinstance(case_input, FraudRoutingInput):
        nodes = [
            {"id": item.alert_id, "group": item.entity_id, "value": item.risk_score}
            for item in case_input.alerts
        ]
        edges = []
        for index, left in enumerate(case_input.alerts):
            for right in case_input.alerts[index + 1 :]:
                if left.entity_id == right.entity_id:
                    edges.append(
                        {
                            "source": left.alert_id,
                            "target": right.alert_id,
                            "kind": "conflict",
                        }
                    )
        return {"nodes": nodes, "edges": edges}
    return None


def _quantum_payload(result: Any) -> dict[str, Any]:
    """从 Native Program 和执行结果提取线路、原子、波形、计数与项映射。"""
    native = result.execution.context.native_program.to_dict()
    mode = result.mode
    circuits: list[dict[str, Any]] = []
    analog_program = None
    blocks: list[str] = []
    if mode == "digital":
        circuits = [native["circuit"]]
    elif mode == "hybrid":
        for block in native["blocks"]:
            block_type = block["block_type"]
            blocks.append(block_type)
            if "circuit" in block:
                circuits.append(block["circuit"])
            if block_type == "analog":
                analog_program = block["program"]
            if block_type == "measure":
                targets = [
                    target
                    for measurement in block.get("measurements", ())
                    for target in measurement.get("targets", ())
                ]
                circuits.append(
                    {
                        "qubits": list(result.execution.logical_order),
                        "gates": [
                            {
                                "name": "m",
                                "targets": [target],
                                "controls": [],
                                "parameters": {},
                            }
                            for target in targets
                        ],
                    }
                )
    else:
        analog_program = native
    selected = _selected_variables(result)
    sites = result.execution.context.analysis.mapping_plan.layout.sites
    term_mapping = result.execution.context.term_mapping
    layer_count = int(result.metadata.get("layers", 1))
    if mode == "hybrid":
        logical_layers = ["H", "U1", "A", "U2", "RX1", "M"]
    elif mode == "digital":
        logical_layers = ["H"]
        for layer_index in range(layer_count):
            suffix = "" if layer_count == 1 else f"[{layer_index + 1}]"
            logical_layers.extend(
                [f"U1{suffix}", f"U2{suffix}", f"RX1{suffix}"]
            )
        logical_layers.append("M")
    else:
        logical_layers = ["PREP", "AHS", "MEASURE"]
    return {
        "mode": mode,
        "algorithm": result.execution.algorithm,
        "topology": result.execution.topology,
        "layerCount": layer_count,
        "searchStrategy": str(result.metadata.get("search_strategy", "explicit")),
        "evaluationCount": len(result.execution.parameter_history),
        "selectedEvaluationIndex": result.execution.selected_evaluation_index,
        "blocks": blocks,
        "layers": logical_layers,
        "circuit": _flatten_circuits(circuits),
        "atoms": [
            {
                "id": site.logical_id,
                "x": float(site.position[0]),
                "y": float(site.position[1]),
                "selected": site.logical_id in selected,
            }
            for site in sites
        ],
        "waveforms": _waveforms(analog_program),
        "counts": _counts(result.execution.result.counts),
        "parameterHistory": [
            {
                "index": item.evaluation_index,
                "objective": item.objective_value,
                "parameters": dict(item.parameter_bind.values),
                "selected": item.evaluation_index
                == result.execution.selected_evaluation_index,
            }
            for item in result.execution.parameter_history
        ],
        "termMapping": [
            {
                "operator": item.operator,
                "targets": list(item.targets),
                "logical": item.logical_coefficient,
                "analog": item.analog_coefficient,
                "digital": item.digital_coefficient,
                "implementation": item.implementation,
            }
            for item in term_mapping
        ],
        "summary": {
            "analogTerms": sum(
                abs(item.analog_coefficient) > 1e-12 for item in term_mapping
            ),
            "digitalTerms": sum(
                abs(item.digital_coefficient) > 1e-12 for item in term_mapping
            ),
            "qubits": len(result.execution.logical_order),
            "shots": result.execution.result.shots,
        },
    }


def _flatten_circuits(circuits: list[dict[str, Any]]) -> dict[str, Any]:
    """按实际执行顺序合并多个数字块，并为每个门分配稳定深度。"""
    gates = []
    qubits: list[str] = []
    depth = 0
    for circuit in circuits:
        if not qubits:
            qubits = list(circuit.get("qubits", ()))
        all_gates = list(circuit.get("gates", ()))
        for measurement in circuit.get("measurements", ()):
            all_gates.extend(
                {
                    "name": "m",
                    "targets": [target],
                    "controls": [],
                    "parameters": {},
                }
                for target in measurement.get("targets", ())
            )
        for gate in all_gates:
            gates.append(
                {
                    "depth": depth,
                    "name": str(gate.get("name", "u")).upper(),
                    "targets": list(gate.get("targets", ())),
                    "controls": list(gate.get("controls", ())),
                    "parameters": gate.get("parameters", {}),
                }
            )
            depth += 1
    return {"qubits": qubits, "gates": gates, "depth": depth}


def _selected_variables(result: Any) -> set[str]:
    """按逻辑变量顺序读取展示解位串，得到入选的原子或量子位。"""
    bitstring = result.displayed_solution.bitstring
    logical = tuple(
        getattr(
            result.definition.problem,
            "variables",
            getattr(result.definition.problem, "nodes", ()),
        )
    )
    return {variable for variable, bit in zip(logical, bitstring) if bit == "1"}


def _waveforms(program: dict[str, Any] | None) -> dict[str, list[dict[str, float]]]:
    """提取 Rabi、Detuning 和 Phase 的真实时间点并生成统一绘图数据。

    局域失谐没有全局曲线时展示绝对值最大的局域包络；只做幅值归一化，
    同时保留 ``raw`` 原值，绝不为演示效果伪造脉冲形状。
    """
    if program is None:
        return {name: [] for name in ("rabi", "detuning", "phase")}
    terms = program.get("hamiltonian", {}).get("terms", {})
    durations = []
    for name in ("rabi", "detuning", "phase"):
        candidate = terms.get(name)
        if not isinstance(candidate, dict):
            continue
        raw_times = candidate.get("times")
        if raw_times:
            durations.append(max(float(value) for value in raw_times))
        elif candidate.get("duration") is not None:
            durations.append(float(candidate["duration"]))
    shared_duration = max(durations, default=1.0)

    output: dict[str, list[dict[str, float]]] = {}
    for name in ("rabi", "detuning", "phase"):
        waveform = terms.get(name)
        if name == "detuning" and isinstance(waveform, dict):
            local_values = [
                float(item["waveform"]["values"][0])
                for item in terms.get("local_detuning_terms", ())
                if item.get("waveform", {}).get("values")
            ]
            if local_values and not any(waveform.get("values", ())):
                waveform = {**waveform, "values": [max(local_values, key=abs)]}
        if waveform is None or isinstance(waveform, (int, float)):
            value = 0.0 if waveform is None else float(waveform)
            times = [0.0, shared_duration]
            values = [value, value]
        else:
            duration = float(waveform.get("duration", shared_duration))
            values = [float(value) for value in waveform.get("values", (0.0,))]
            raw_times = waveform.get("times")
            if raw_times is None:
                times = [0.0, duration]
                values = [values[0], values[0]]
            else:
                times = [float(value) for value in raw_times]
                if len(times) == 1:
                    times = [times[0], duration]
                if len(values) == 1:
                    values = [values[0], values[0]]
        scale = max((abs(value) for value in values), default=1.0) or 1.0
        output[name] = [
            {"time": time, "value": value / scale, "raw": value}
            for time, value in zip(times, values)
        ]
    return output


def _counts(counts: Any) -> list[dict[str, Any]]:
    """按计数降序返回前十二个态，其余态合并为可解释的尾部桶。"""
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    top = ordered[:12]
    remainder = sum(value for _state, value in ordered[12:])
    if remainder:
        top.append(("其他状态", remainder))
    return [
        {"state": state, "count": int(value), "rank": index + 1}
        for index, (state, value) in enumerate(top)
    ]


def _audit_payload(result: Any) -> dict[str, Any]:
    """输出从问题到执行的哈希链、目标机和运行环境边界。"""
    return {
        "caseId": result.case_id,
        "mode": result.mode,
        "problemHash": result.execution.problem_hash,
        "analysisHash": result.execution.analysis_hash,
        "compileHash": result.execution.compile_hash,
        "executionHash": result.execution.execution_hash,
        "targetId": result.execution.context.analysis.mapping_plan.target_id,
        "backend": result.evidence.backend,
        "executionKind": result.evidence.execution_kind,
        "seed": result.evidence.seed,
        "shots": result.evidence.shots,
        "wallTimeSeconds": result.evidence.wall_time_seconds,
        "hardwareExecution": result.evidence.hardware_execution,
        "cloudExecution": result.evidence.cloud_execution,
        "networkAccessed": result.evidence.network_accessed,
        "optimalityClaim": result.execution.optimality_claim,
        "reportPath": None if result.report_path is None else str(result.report_path),
    }
