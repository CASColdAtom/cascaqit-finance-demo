"""Advanced experiment run-unit and aggregation tests."""

from __future__ import annotations

from cascaqit_biomedicine_demo.advanced_runner import (
    aggregate_run_outcomes,
    execute_run_units,
    expand_run_units,
)


def _plan() -> dict:
    return {
        "planId": "plan-1",
        "points": [
            {
                "index": 0,
                "values": {"bond": 1.2},
                "analysisHash": "analysis-0",
                "problemHash": "problem-0",
            },
            {
                "index": 1,
                "values": {"bond": 1.6},
                "analysisHash": "analysis-1",
                "problemHash": "problem-1",
            },
        ],
        "configurations": [{"layers": 1}, {"layers": 2}],
        "seeds": [7, 23],
        "runCount": 8,
    }


def _electronic_run(error: float, report_hash: str) -> dict:
    return {
        "domain": {
            "absoluteErrorHartree": error,
            "exactOptimizedEnergy": -1.0 + error,
            "sampledConfirmationEnergy": -1.0 + error,
            "referenceEnergy": -1.0,
        },
        "audit": {"reportHash": report_hash},
    }


def test_run_units_have_stable_documented_expansion_order() -> None:
    first = expand_run_units(_plan())
    second = expand_run_units(_plan())

    assert first == second
    assert [
        (unit.point_index, unit.configuration_index, unit.seed) for unit in first
    ] == [
        (0, 0, 7),
        (0, 0, 23),
        (0, 1, 7),
        (0, 1, 23),
        (1, 0, 7),
        (1, 0, 23),
        (1, 1, 7),
        (1, 1, 23),
    ]
    assert len({unit.run_id for unit in first}) == 8


def test_partial_failure_keeps_quantum_runs_separate_without_fallback() -> None:
    units = expand_run_units(_plan())

    def execute(unit):
        if unit.point_index == 1 and unit.seed == 23:
            raise RuntimeError("simulated unit failure")
        return _electronic_run(unit.seed / 1000, f"report-{unit.run_id}")

    outcomes = execute_run_units("electronic_structure", units, execute)
    aggregate = aggregate_run_outcomes("electronic_structure", "plan-1", outcomes)

    assert aggregate["status"] == "partially_succeeded"
    assert aggregate["summary"]["succeededCount"] == 6
    assert aggregate["summary"]["failedCount"] == 2
    failed = [item for item in aggregate["runs"] if item["status"] == "failed"]
    assert all("metrics" not in item and "reportHash" not in item for item in failed)
    assert {item["error"]["message"] for item in failed} == {
        "simulated unit failure"
    }
    assert len(aggregate["pointSeries"]) == 2
    assert len(aggregate["configurationSummary"]) == 2


def test_aggregation_reports_median_and_interquartile_range() -> None:
    plan = _plan()
    units = expand_run_units(plan)
    errors = iter([0.001, 0.003, 0.005, 0.007, 0.009, 0.011, 0.013, 0.015])
    outcomes = execute_run_units(
        "electronic_structure",
        units,
        lambda unit: _electronic_run(next(errors), f"report-{unit.run_id}"),
    )
    aggregate = aggregate_run_outcomes("electronic_structure", "plan-1", outcomes)
    metric = aggregate["summary"]["primaryMetric"]

    assert aggregate["status"] == "succeeded"
    assert metric["median"] == 0.008
    assert metric["q1"] == 0.0045
    assert metric["q3"] == 0.0115
    assert len({item["reportHash"] for item in aggregate["runs"]}) == 8
