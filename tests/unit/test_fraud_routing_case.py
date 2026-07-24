"""反欺诈调查编排 QUBO 与业务约束单元测试。"""

from __future__ import annotations

from dataclasses import replace

from cascaqit_finance_demo.cases.fraud_routing import FraudRoutingCase


def test_default_routing_problem_has_only_business_variables() -> None:
    """验证默认告警模型无需辅助变量，Problem 位均能对应真实告警。"""
    case = FraudRoutingCase()
    case_input = case.default_input()

    problem = case.build_problem(case_input)
    feasible = case.exact_business_points(case_input)

    assert len(problem.variables) == 12
    assert problem.metadata["decision_scope"] == "investigation routing only"
    assert len(feasible) > 1
    assert len(feasible[0].selected_alert_ids) == 4
    assert feasible[0].feasible is True


def test_shared_entity_conflict_is_rechecked_after_decoding() -> None:
    """验证解码器独立发现同时选择同实体告警造成的并行冲突。"""
    case = FraudRoutingCase()
    case_input = case.default_input()

    solution = case.decode_alert_selection(
        case_input,
        (1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 0),
    )

    checks = {check.name: check for check in solution.checks}
    assert checks["investigator_slots"].passed is True
    assert checks["entity_parallel_cap"].passed is False
    assert solution.feasible is False


def test_entity_parallel_cap_two_allows_shared_entities() -> None:
    """验证并行上限放宽为二后，同实体告警不再被错误判为冲突。"""
    case = FraudRoutingCase()
    case_input = replace(case.default_input(), entity_parallel_cap=2)

    solution = case.decode_alert_selection(
        case_input,
        (1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 0),
    )

    assert solution.feasible is True
