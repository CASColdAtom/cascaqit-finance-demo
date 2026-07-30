"""Persistent bounded local experiment job tests."""

from __future__ import annotations

import json
import threading
import time

import pytest

from cascaqit_biomedicine_demo.local_jobs import (
    JobCancellationError,
    JobQueueFullError,
    LocalJobManager,
)


def _plan(plan_id: str, run_count: int = 1) -> dict:
    return {
        "planId": plan_id,
        "runCount": run_count,
        "points": [
            {
                "index": 0,
                "values": {"dataset": "fixture"},
                "analysisHash": "analysis",
                "problemHash": "problem",
            }
        ],
        "configurations": [{"mode": "digital"}],
        "seeds": list(range(run_count)),
    }


def _wait(manager: LocalJobManager, job_id: str) -> dict:
    for _ in range(200):
        job = manager.get(job_id)
        if job["status"] in {"succeeded", "partially_succeeded", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def test_job_persists_each_run_and_partial_success(tmp_path) -> None:
    manager = LocalJobManager(tmp_path / "jobs")

    def execute(unit):
        if unit.seed == 1:
            raise ValueError("isolated failure")
        return {"audit": {"reportHash": f"report-{unit.seed}"}}

    created = manager.submit(
        case_id="electronic_structure",
        preset="scan",
        plan=_plan("plan-partial", 3),
        executor=execute,
    )
    completed = _wait(manager, created["jobId"])
    persisted = json.loads(
        (tmp_path / "jobs" / created["jobId"] / "job.json").read_text()
    )

    assert completed["status"] == "partially_succeeded"
    assert completed["progress"] == {
        "total": 3,
        "completed": 3,
        "succeeded": 2,
        "failed": 1,
        "cancelled": 0,
    }
    assert persisted == completed
    assert [item["status"] for item in completed["runs"]] == [
        "succeeded",
        "failed",
        "succeeded",
    ]
    manager.shutdown()


def test_queue_is_bounded_and_queued_job_can_be_cancelled(tmp_path) -> None:
    manager = LocalJobManager(tmp_path / "jobs", max_queue=1)
    release = threading.Event()

    def blocked(_unit):
        release.wait(timeout=2)
        return {"audit": {"reportHash": "done"}}

    first = manager.submit(
        case_id="active_center",
        preset="scan",
        plan=_plan("plan-running"),
        executor=blocked,
    )
    for _ in range(100):
        if manager.get(first["jobId"])["status"] == "running":
            break
        time.sleep(0.01)
    second = manager.submit(
        case_id="active_center",
        preset="scan",
        plan=_plan("plan-queued"),
        executor=blocked,
    )
    with pytest.raises(JobQueueFullError):
        manager.submit(
            case_id="active_center",
            preset="scan",
            plan=_plan("plan-rejected"),
            executor=blocked,
        )
    cancelled = manager.cancel(second["jobId"])
    assert cancelled["status"] == "cancelled"
    with pytest.raises(JobCancellationError):
        manager.cancel(first["jobId"])
    release.set()
    _wait(manager, first["jobId"])
    manager.shutdown()


def test_restart_keeps_terminal_job_and_marks_interrupted_job_failed(tmp_path) -> None:
    jobs = tmp_path / "jobs"
    terminal = jobs / "terminal"
    interrupted = jobs / "interrupted"
    terminal.mkdir(parents=True)
    interrupted.mkdir(parents=True)
    (terminal / "job.json").write_text(
        json.dumps({"jobId": "terminal", "status": "succeeded", "runs": []})
    )
    (interrupted / "job.json").write_text(
        json.dumps(
            {
                "jobId": "interrupted",
                "status": "running",
                "runs": [{"status": "running"}, {"status": "pending"}],
            }
        )
    )

    manager = LocalJobManager(jobs)

    assert manager.get("terminal")["status"] == "succeeded"
    recovered = manager.get("interrupted")
    assert recovered["status"] == "failed"
    assert recovered["error"]["code"] == "SERVICE_RESTART_INTERRUPTED"
    assert {item["status"] for item in recovered["runs"]} == {"not_started"}
    manager.shutdown()
