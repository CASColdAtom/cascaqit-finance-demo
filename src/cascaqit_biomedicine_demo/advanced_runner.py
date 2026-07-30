"""Deterministic run-unit expansion and aggregation for advanced experiments."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from statistics import median
from typing import Any


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ExperimentRunUnit:
    """One independently executable point/configuration/seed combination."""

    run_id: str
    plan_id: str
    point_index: int
    values: dict[str, Any]
    analysis_hash: str
    problem_hash: str
    configuration_index: int
    configuration: dict[str, Any]
    seed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "runId": self.run_id,
            "planId": self.plan_id,
            "pointIndex": self.point_index,
            "values": self.values,
            "analysisHash": self.analysis_hash,
            "problemHash": self.problem_hash,
            "configurationIndex": self.configuration_index,
            "configuration": self.configuration,
            "seed": self.seed,
        }


def expand_run_units(plan: dict[str, Any]) -> tuple[ExperimentRunUnit, ...]:
    """Expand a plan in the documented point/configuration/seed order."""

    plan_id = str(plan["planId"])
    units: list[ExperimentRunUnit] = []
    for point in plan["points"]:
        for configuration_index, configuration in enumerate(plan["configurations"]):
            for seed in plan["seeds"]:
                identity = {
                    "planId": plan_id,
                    "pointIndex": int(point["index"]),
                    "analysisHash": str(point["analysisHash"]),
                    "problemHash": str(point["problemHash"]),
                    "configurationIndex": configuration_index,
                    "configuration": configuration,
                    "seed": int(seed),
                }
                units.append(
                    ExperimentRunUnit(
                        run_id=_stable_hash(identity),
                        plan_id=plan_id,
                        point_index=int(point["index"]),
                        values=dict(point["values"]),
                        analysis_hash=str(point["analysisHash"]),
                        problem_hash=str(point["problemHash"]),
                        configuration_index=configuration_index,
                        configuration=dict(configuration),
                        seed=int(seed),
                    )
                )
    if len(units) != int(plan["runCount"]):
        raise ValueError("expanded run count does not match experiment plan")
    return tuple(units)


def _metric_payload(case_id: str, run: dict[str, Any]) -> dict[str, Any]:
    domain = run["domain"]
    if case_id == "electronic_structure":
        return {
            "primaryMetric": float(domain["absoluteErrorHartree"]),
            "primaryMetricName": "absolute_error_hartree",
            "vqeEnergy": float(domain["exactOptimizedEnergy"]),
            "sampledEnergy": float(domain["sampledConfirmationEnergy"]),
            "referenceEnergy": float(domain["referenceEnergy"]),
        }
    if case_id == "active_center":
        return {
            "primaryMetric": float(domain["absoluteErrorMeV"]),
            "primaryMetricName": "absolute_error_mev",
            "vqeEnergy": float(domain["vqeExactEnergyMeV"]),
            "sampledEnergy": float(domain["sampledEnergyMeV"]),
            "referenceEnergy": float(domain["exactGroundEnergyMeV"]),
            "classicFirstGapMeV": float(domain["exactFirstGapMeV"]),
            "classicFirstGapSource": domain["exactFirstGapSource"],
            "magnetization": domain["magnetization"],
            "correlations": domain["correlations"],
        }
    raise ValueError(f"unsupported Pauli experiment case: {case_id}")


def execute_run_units(
    case_id: str,
    units: Iterable[ExperimentRunUnit],
    executor: Callable[[ExperimentRunUnit], dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Execute independent units and retain failures without a result fallback."""

    outcomes: list[dict[str, Any]] = []
    for unit in units:
        try:
            run = executor(unit)
            audit = run.get("audit", {})
            report_hash = audit.get("reportHash") or audit.get("resultHash")
            if not isinstance(report_hash, str):
                raise ValueError("run result does not contain an auditable report hash")
            outcomes.append(
                {
                    **unit.to_dict(),
                    "status": "succeeded",
                    "reportHash": report_hash,
                    "metrics": _metric_payload(case_id, run),
                }
            )
        except Exception as exc:  # noqa: BLE001 - each unit is an isolation boundary
            outcomes.append(
                {
                    **unit.to_dict(),
                    "status": "failed",
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                }
            )
    return tuple(outcomes)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _summarize(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [item for item in outcomes if item["status"] == "succeeded"]
    values = [float(item["metrics"]["primaryMetric"]) for item in successful]
    return {
        "runCount": len(outcomes),
        "succeededCount": len(successful),
        "failedCount": len(outcomes) - len(successful),
        "successRate": len(successful) / len(outcomes) if outcomes else 0.0,
        "primaryMetric": (
            {
                "name": successful[0]["metrics"]["primaryMetricName"],
                "median": median(values),
                "q1": _percentile(values, 0.25),
                "q3": _percentile(values, 0.75),
                "minimum": min(values),
                "maximum": max(values),
            }
            if values
            else None
        ),
    }


def aggregate_run_outcomes(
    case_id: str,
    plan_id: str,
    outcomes: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate independent evidence without merging counts or failed results."""

    items = list(outcomes)
    succeeded = sum(item["status"] == "succeeded" for item in items)
    if succeeded == len(items):
        status = "succeeded"
    elif succeeded:
        status = "partially_succeeded"
    else:
        status = "failed"

    point_indices = sorted({int(item["pointIndex"]) for item in items})
    configuration_indices = sorted(
        {int(item["configurationIndex"]) for item in items}
    )
    point_series = [
        {
            "pointIndex": index,
            "values": next(
                item["values"] for item in items if int(item["pointIndex"]) == index
            ),
            **_summarize(
                [item for item in items if int(item["pointIndex"]) == index]
            ),
        }
        for index in point_indices
    ]
    configuration_summary = [
        {
            "configurationIndex": index,
            "configuration": next(
                item["configuration"]
                for item in items
                if int(item["configurationIndex"]) == index
            ),
            **_summarize(
                [
                    item
                    for item in items
                    if int(item["configurationIndex"]) == index
                ]
            ),
        }
        for index in configuration_indices
    ]
    identity = {
        "schema": "biomedicine.experiment-aggregate.v1",
        "caseId": case_id,
        "planId": plan_id,
        "status": status,
        "outcomes": [
            {
                "runId": item["runId"],
                "status": item["status"],
                "reportHash": item.get("reportHash"),
                "error": item.get("error"),
            }
            for item in items
        ],
    }
    return {
        **identity,
        "aggregateHash": _stable_hash(identity),
        "summary": _summarize(items),
        "pointSeries": point_series,
        "configurationSummary": configuration_summary,
        "runs": items,
    }
