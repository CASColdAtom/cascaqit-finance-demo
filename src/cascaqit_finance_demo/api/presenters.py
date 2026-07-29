"""把金融领域、编译和执行对象转换为前端使用的 JSON 展示模型。"""

from __future__ import annotations

from dataclasses import asdict
from math import isclose, sqrt
from statistics import fmean, stdev
from typing import Any

from scipy.stats import t as student_t

from cascaqit_finance_demo.cases.constrained_selection import SelectionInput
from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS
from cascaqit_finance_demo.domain.models import (
    FraudRoutingInput,
    PortfolioInput,
    SettlementInput,
)

_SOURCE_RULE_LABELS = {
    "risk_return_objective": "风险收益目标",
    "pairwise_covariance_risk": "协方差风险",
    "fixed_holding_count": "固定持仓数",
    "sector_concentration_cap": "行业集中度上限",
    "minimum_defensive_holding": "防御资产下限",
    "settlement_value": "结算价值",
    "settlement_pairwise_conflict": "交易两两冲突",
    "trade_prerequisite": "交易前置依赖",
    "currency_liquidity_limit": "币种流动性上限",
    "settlement_batch_cap": "结算批次上限",
    "investigation_value": "调查任务价值",
    "fixed_investigator_slots": "固定调查席位",
    "shared_entity_parallel_conflict": "共享实体并行冲突",
    "value_cost_objective": "价值成本目标",
    "fixed_selection_count": "固定选择数量",
    "group_exact_count": "分组精确数量",
    "group_concentration_cap": "分组集中度上限",
    "maximum_resource_units": "资源单位上限",
    "minimum_resource_units": "资源单位下限",
    "selection_pairwise_conflict": "候选项两两冲突",
    "selection_prerequisite": "候选项前置依赖",
}
_IMPLEMENTATION_LABELS = {
    "pending_mode_allocation": "待执行模式分配",
    "digital_gate": "数字量子门",
    "analog_interaction": "原子相互作用",
    "analog_detuning_local": "局域失谐",
    "analog_detuning_global": "全局失谐",
    "hybrid_split": "模拟与数字共同承担",
}


def analysis_payload(
    case_id: str,
    case_input: Any,
    analysis: Any,
    *,
    term_mapping: tuple[Any, ...] = (),
) -> dict[str, Any]:
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
            "coefficientLedger": _coefficient_ledger_payload(
                analysis.definition,
                analysis.problem_analysis,
                term_mapping=term_mapping,
            ),
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
                    "availableAlgorithms": list(row.available_algorithms),
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


def execution_payload(
    case_id: str,
    case_input: Any,
    result: Any,
    *,
    repeated: Any | None = None,
) -> dict[str, Any]:
    """将一次真实执行整理为业务、量子实验和审计三个视图的数据。"""
    analysis = analysis_payload(
        case_id,
        case_input,
        result.analysis,
        term_mapping=tuple(result.execution.context.term_mapping),
    )
    payload = {
        "analysis": analysis,
        "business": _business_payload(case_id, case_input, result),
        "quantum": _quantum_payload(result),
        "audit": _audit_payload(result),
    }
    if repeated is not None:
        payload["statistics"] = _statistics_payload(repeated)
    return payload


def _coefficient_ledger_payload(
    definition: Any,
    problem_analysis: Any,
    *,
    term_mapping: tuple[Any, ...],
) -> dict[str, Any]:
    """连接业务贡献、Canonical QUBO 项和实际 Hamiltonian 实现。

    CASCAQit 在 QUBO 转 Ising Hamiltonian 时，一个二次项会同时影响两个局域场
    和一个耦合项。这里不靠变量名猜测，而是使用编译器公开的
    ``source_term_ids`` 建立多对多关系；执行后再用 ``term_mapping`` 补齐当前
    模式的 Analog/Digital 系数分配。
    """
    contributions = tuple(definition.coefficient_contributions)
    if not contributions:
        return {
            "applicability": "not_applicable_graph"
            if definition.problem_kind in {"graph", "mwis"}
            else "not_declared",
            "balanced": definition.problem_kind != "qubo",
            "hamiltonianBalanced": definition.problem_kind != "qubo",
            "contributionCount": 0,
            "canonicalTermCount": 0,
            "rows": [],
        }

    canonical = problem_analysis.canonical_problem
    canonical_coefficients = {"offset": float(canonical.offset)}
    canonical_coefficients.update(
        {item.term_id: float(item.coefficient) for item in canonical.linear_terms}
    )
    canonical_coefficients.update(
        {item.term_id: float(item.coefficient) for item in canonical.quadratic_terms}
    )
    contribution_totals: dict[str, float] = {}
    for item in contributions:
        contribution_totals[item.canonical_term_id] = (
            contribution_totals.get(item.canonical_term_id, 0.0) + item.coefficient
        )

    mapping_by_logical_id = {
        item.logical_term_id: item for item in term_mapping
    }
    logical_by_source: dict[str, list[Any]] = {}
    for logical_term in problem_analysis.logical_hamiltonian.terms:
        for source_term_id in logical_term.source_term_ids:
            logical_by_source.setdefault(source_term_id, []).append(logical_term)
    group_labels = {group.group_id: group.label for group in definition.term_groups}

    rows = []
    hamiltonian_effect_totals: dict[str, float] = {}
    for item in contributions:
        canonical_coefficient = canonical_coefficients.get(item.canonical_term_id, 0.0)
        conserved = isclose(
            contribution_totals[item.canonical_term_id],
            canonical_coefficient,
            rel_tol=1e-10,
            abs_tol=1e-10,
        )
        hamiltonian_terms = []
        for logical_term in logical_by_source.get(item.canonical_term_id, ()):
            mapped = mapping_by_logical_id.get(logical_term.term_id)
            contribution_effect = _qubo_contribution_hamiltonian_effect(
                term_kind=item.term_kind,
                coefficient=item.coefficient,
                operator=logical_term.operator,
            )
            canonical_term_effect = _qubo_contribution_hamiltonian_effect(
                term_kind=item.term_kind,
                coefficient=canonical_coefficient,
                operator=logical_term.operator,
            )
            hamiltonian_effect_totals[logical_term.term_id] = (
                hamiltonian_effect_totals.get(logical_term.term_id, 0.0)
                + contribution_effect
            )
            implementation = (
                "pending_mode_allocation" if mapped is None else mapped.implementation
            )
            hamiltonian_terms.append(
                {
                    "termId": logical_term.term_id,
                    "operator": logical_term.operator,
                    "targets": list(logical_term.targets),
                    "contributionEffect": contribution_effect,
                    "canonicalTermEffect": canonical_term_effect,
                    "logical": float(logical_term.coefficient),
                    "analog": (
                        None if mapped is None else float(mapped.analog_coefficient)
                    ),
                    "digital": (
                        None if mapped is None else float(mapped.digital_coefficient)
                    ),
                    "implementation": implementation,
                    "implementationLabel": _IMPLEMENTATION_LABELS.get(
                        implementation, implementation
                    ),
                    "allocationConserved": mapped is None
                    or isclose(
                        mapped.analog_coefficient + mapped.digital_coefficient,
                        mapped.logical_coefficient,
                        rel_tol=1e-10,
                        abs_tol=1e-10,
                    ),
                }
            )
        rows.append(
            {
                "contributionId": item.contribution_id,
                "groupId": item.group_id,
                "groupLabel": group_labels[item.group_id],
                "sourceRule": item.source_rule,
                "sourceRuleLabel": _SOURCE_RULE_LABELS.get(
                    item.source_rule, item.source_rule
                ),
                "role": item.role,
                "termKind": item.term_kind,
                "targets": list(item.targets),
                "contributionCoefficient": item.coefficient,
                "canonicalTermId": item.canonical_term_id,
                "canonicalCoefficient": canonical_coefficient,
                "hamiltonianTerms": hamiltonian_terms,
                "conserved": conserved,
            }
        )
    logical_coefficients = {
        item.term_id: float(item.coefficient)
        for item in problem_analysis.logical_hamiltonian.terms
    }
    hamiltonian_balanced = all(
        isclose(
            hamiltonian_effect_totals.get(term_id, 0.0),
            coefficient,
            rel_tol=1e-10,
            abs_tol=1e-10,
        )
        for term_id, coefficient in logical_coefficients.items()
    ) and all(
        nested["allocationConserved"]
        for row in rows
        for nested in row["hamiltonianTerms"]
    )
    return {
        "applicability": "qubo",
        "balanced": all(row["conserved"] for row in rows),
        "hamiltonianBalanced": hamiltonian_balanced,
        "contributionCount": len(rows),
        "canonicalTermCount": len(contribution_totals),
        "rows": rows,
    }


def _qubo_contribution_hamiltonian_effect(
    *, term_kind: str, coefficient: float, operator: str
) -> float:
    """计算一条 QUBO 系数对 Ising Hamiltonian 项的精确增量。

    CASCAQit 使用 ``x=(1-Z)/2``：线性项 ``a*x`` 对局域场贡献 ``-a/2``；
    二次项 ``b*x_i*x_j`` 对两个局域场各贡献 ``-b/4``，对 ``ZZ`` 耦合贡献
    ``b/4``。常数偏移不会进入物理 Hamiltonian。
    """
    if term_kind == "linear" and operator == "z":
        return -coefficient / 2.0
    if term_kind == "quadratic" and operator == "z":
        return -coefficient / 4.0
    if term_kind == "quadratic" and operator == "zz":
        return coefficient / 4.0
    return 0.0


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
                "id": item.scenario_id,
                "label": (
                    f"S {item.spot_shock:+.0%} / "
                    f"σ {item.volatility_shock:+.0%}"
                ),
                "group": "风险情景",
                "primary": f"压力价格 {item.stressed_price:.4f}",
                "secondary": f"P&L {item.pnl:+.4f}",
                "detail": f"风险权重 {item.normalized_risk_weight:.3f}",
            }
            for item in scenario.risk_scenarios(case_input)
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
    risk_scenarios = scenario.risk_scenarios(case_input)
    x_labels = [f"{shock:+.0%}" for shock in scenario.spot_shocks]
    y_labels = [f"{shock:+.0%}" for shock in scenario.volatility_shocks]
    cells = [
        {
            "id": item.scenario_id,
            "x": item.column,
            "y": item.row,
            "value": item.pnl,
            "label": (
                f"S {item.spot_shock:+.0%} / "
                f"σ {item.volatility_shock:+.0%}"
            ),
            "stressedPrice": item.stressed_price,
            "riskWeight": item.normalized_risk_weight,
            "delta": item.delta,
            "gamma": item.gamma,
            "vega": item.vega,
        }
        for item in risk_scenarios
    ]
    return {
        **visual,
        "kind": "derivatives-pnl-surface",
        "title": "衍生品压力情景损益",
        "subtitle": "经典链重估每个格点；绝对 P&L 权重进入 Analog 局域失谐。",
        "xLabel": "标的价格冲击",
        "yLabel": "波动率冲击",
        "matrix": {"xLabels": x_labels, "yLabels": y_labels, "cells": cells},
    }


def _matrix_cells(problem: Any) -> list[dict[str, Any]]:
    """把 QUBO 稀疏系数展开为前端热力图所需的矩阵单元。"""
    cells: dict[tuple[str, str], float] = {}
    for variable, coefficient in getattr(problem, "linear_terms", ()):
        cells[(variable, variable)] = float(coefficient)
    for node, weight in getattr(problem, "node_weights", ()):
        cells[(node, node)] = float(weight)
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
        scenario = PROBLEM_SCENARIOS[case_id]
        payload["pricing"] = asdict(scenario.price(case_input))
        payload["riskScenarios"] = [
            asdict(item) for item in scenario.risk_scenarios(case_input)
        ]
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
    if case_id == "derivatives":
        scenario = PROBLEM_SCENARIOS[case_id]
        for item in scenario.risk_scenarios(case_input):
            points.append(
                {
                    "id": item.scenario_id,
                    "label": (
                        f"S {item.spot_shock:+.0%} / "
                        f"σ {item.volatility_shock:+.0%}"
                    ),
                    "group": "风险情景",
                    "x": item.spot_shock,
                    "y": item.volatility_shock,
                    "size": 8.0 + 22.0 * item.normalized_risk_weight,
                    "selected": item.scenario_id in selected,
                    "detail": (
                        f"P&L {item.pnl:+.4f} / "
                        f"风险权重 {item.normalized_risk_weight:.3f}"
                    ),
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
        source = ()
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
    algorithm = result.execution.algorithm
    if algorithm == "vqe":
        logical_layers = ["|0>"]
        ansatz = result.execution.context.ansatz
        definition = None if ansatz is None else ansatz.definition
        axes = (
            ("ry",)
            if not isinstance(definition, dict)
            else tuple(definition.get("rotation_axes", ("ry",)))
        )
        for layer_index in range(layer_count):
            suffix = "" if layer_count == 1 else f"[{layer_index + 1}]"
            logical_layers.extend(
                [
                    *(f"{axis.upper()}{suffix}" for axis in axes),
                    f"CX{suffix}",
                ]
            )
        logical_layers.append("M")
    elif mode == "hybrid":
        logical_layers = ["H"]
        for layer_index in range(layer_count):
            suffix = "" if layer_count == 1 else f"[{layer_index + 1}]"
            logical_layers.extend(
                [f"U1{suffix}", f"A{suffix}", f"U2{suffix}", f"RX1{suffix}"]
            )
        logical_layers.append("M")
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
    optimization = result.execution.optimization
    optimizer = None
    if optimization is not None and optimization.optimizer is not None:
        config = optimization.optimizer
        termination = optimization.termination
        optimizer = {
            "method": config.method,
            "starts": config.starts,
            "perStartEvaluationBudget": config.max_evaluations,
            "maximumEvaluationCount": (
                None
                if config.max_evaluations is None
                else config.max_evaluations * config.starts
            ),
            "selectedStartIndex": optimization.selected_start_index,
            "startInitializations": [
                item.initialization for item in optimization.starts
            ],
            "terminationReason": None if termination is None else termination.reason,
            "backendExecutionCount": (
                None if termination is None else termination.backend_execution_count
            ),
        }
    ansatz = result.execution.context.ansatz
    ansatz_payload = None
    if ansatz is not None:
        ansatz_data = ansatz.to_dict()
        ansatz_payload = {
            "kind": ansatz.ansatz_kind,
            "layers": ansatz.layers,
            "parameterNames": list(ansatz.parameter_names),
            "parameterCount": len(ansatz.parameter_names),
            "circuitHash": ansatz.circuit_hash,
            "ansatzHash": ansatz.stable_hash(),
            "definition": ansatz_data.get("definition"),
        }
    layer_experiment = result.layer_experiment
    layer_evidence = None
    if layer_experiment is not None:
        layer_evidence = {
            "policy": "adaptive",
            "selectedLayers": layer_experiment.selected_layers,
            "executedLayers": [step.layers for step in layer_experiment.steps],
            "maxLayers": layer_experiment.max_layers,
            "minImprovement": layer_experiment.min_improvement,
            "stopReason": layer_experiment.stop_reason,
            "totalEvaluationCount": layer_experiment.total_evaluation_count,
            "steps": [
                {
                    "layers": step.layers,
                    "objective": step.execution.objective_value,
                    "improvementFromIncumbent": step.improvement_from_incumbent,
                    "materialImprovement": step.material_improvement,
                    "evaluationCount": len(step.execution.parameter_history),
                    "selected": step.layers == layer_experiment.selected_layers,
                }
                for step in layer_experiment.steps
            ],
        }
    else:
        layer_evidence = {
            "policy": "fixed",
            "selectedLayers": layer_count,
            "executedLayers": [layer_count],
            "maxLayers": layer_count,
            "minImprovement": 0.0,
            "stopReason": "fixed",
            "totalEvaluationCount": len(result.execution.parameter_history),
            "steps": [
                {
                    "layers": layer_count,
                    "objective": result.execution.objective_value,
                    "improvementFromIncumbent": None,
                    "materialImprovement": True,
                    "evaluationCount": len(result.execution.parameter_history),
                    "selected": True,
                }
            ],
        }
    return {
        "mode": mode,
        "algorithm": algorithm,
        "topology": result.execution.topology,
        "layerCount": layer_count,
        "searchStrategy": str(result.metadata.get("search_strategy", "explicit")),
        "evaluationCount": len(result.execution.parameter_history),
        "selectedEvaluationIndex": result.execution.selected_evaluation_index,
        "optimizer": optimizer,
        "ansatz": ansatz_payload,
        "layerEvidence": layer_evidence,
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


def _statistics_payload(repeated: Any) -> dict[str, Any]:
    """汇总独立量子运行的业务可行率、目标值区间和实际执行成本。"""
    runs = tuple(repeated.runs)
    objectives = tuple(float(item.execution.objective_value) for item in runs)
    objective_mean = fmean(objectives)
    if len(objectives) == 1:
        objective_std = 0.0
        interval_low = objective_mean
        interval_high = objective_mean
    else:
        objective_std = stdev(objectives)
        critical = float(
            student_t.ppf(
                (1.0 + repeated.confidence_level) / 2.0,
                len(objectives) - 1,
            )
        )
        margin = critical * objective_std / sqrt(len(objectives))
        interval_low = objective_mean - margin
        interval_high = objective_mean + margin

    rows = []
    feasible_count = 0
    for index, item in enumerate(runs):
        feasible = bool(getattr(item.business_candidate, "feasible", True))
        feasible_count += int(feasible)
        rows.append(
            {
                "index": index,
                "seed": item.evidence.seed,
                "quantumCandidateFeasible": feasible,
                "objective": float(item.execution.objective_value),
                "candidateObjective": float(
                    item.execution.best_observed_candidate.objective_value
                ),
                "evaluationCount": len(item.execution.parameter_history),
                "wallTimeSeconds": item.evidence.wall_time_seconds,
                "selected": index == repeated.representative_index,
                "diagnosticDisplaySource": item.metadata.get("displayed_source"),
            }
        )
    return {
        "repeatCount": len(runs),
        "feasibleCount": feasible_count,
        "feasibleRate": feasible_count / len(runs),
        "successSource": "quantum_business_candidate",
        "representativeRunIndex": repeated.representative_index,
        "objective": {
            "mean": objective_mean,
            "sampleStandardDeviation": objective_std,
            "confidenceLevel": repeated.confidence_level,
            "confidenceIntervalLow": interval_low,
            "confidenceIntervalHigh": interval_high,
        },
        "totalEvaluationCount": sum(
            len(item.execution.parameter_history) for item in runs
        ),
        "totalWallTimeSeconds": sum(item.evidence.wall_time_seconds for item in runs),
        "runs": rows,
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
