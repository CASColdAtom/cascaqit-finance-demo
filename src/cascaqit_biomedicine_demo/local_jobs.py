"""Bounded, persistent local job execution for advanced experiments."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from cascaqit_biomedicine_demo.advanced_runner import (
    ExperimentRunUnit,
    expand_run_units,
)

TERMINAL_STATUSES = {
    "succeeded",
    "partially_succeeded",
    "failed",
    "cancelled",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class JobNotFoundError(KeyError):
    """Raised when a caller requests an unknown job identifier."""


class JobQueueFullError(RuntimeError):
    """Raised before creating a job when the bounded queue is full."""


class JobCancellationError(RuntimeError):
    """Raised when the requested cancellation cannot be honored."""


class LocalJobManager:
    """Run one local experiment at a time and persist every state transition."""

    def __init__(self, storage_dir: Path, *, max_queue: int = 4) -> None:
        if max_queue < 1:
            raise ValueError("max_queue must be at least one")
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.max_queue = max_queue
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="biomedicine-job"
        )
        self._jobs: dict[str, dict[str, Any]] = {}
        self._futures: dict[str, Future[None]] = {}
        self._load_existing()

    def _job_path(self, job_id: str) -> Path:
        return self.storage_dir / job_id / "job.json"

    def _write(self, job: dict[str, Any]) -> None:
        path = self._job_path(str(job["jobId"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        payload = json.dumps(
            job, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8")
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)

    def _load_existing(self) -> None:
        for path in sorted(self.storage_dir.glob("*/job.json")):
            try:
                job = json.loads(path.read_text(encoding="utf-8"))
                job_id = str(job["jobId"])
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if job.get("status") not in TERMINAL_STATUSES:
                job["status"] = "failed"
                job["finishedAt"] = _now()
                job["error"] = {
                    "code": "SERVICE_RESTART_INTERRUPTED",
                    "message": (
                        "The local process stopped before the job reached a terminal "
                        "state."
                    ),
                }
                for unit in job.get("runs", []):
                    if unit.get("status") in {"pending", "running"}:
                        unit["status"] = "not_started"
                self._write(job)
            self._jobs[job_id] = job

    def submit(
        self,
        *,
        case_id: str,
        preset: str,
        plan: dict[str, Any],
        executor: Callable[[ExperimentRunUnit], dict[str, Any]],
    ) -> dict[str, Any]:
        units = expand_run_units(plan)
        with self._lock:
            active = sum(
                job["status"] not in TERMINAL_STATUSES for job in self._jobs.values()
            )
            if active >= self.max_queue + 1:
                raise JobQueueFullError("the local experiment queue is full")
            job_id = uuid4().hex
            created = _now()
            job = {
                "schema": "biomedicine.local-job.v1",
                "jobId": job_id,
                "caseId": case_id,
                "preset": preset,
                "planId": plan["planId"],
                "status": "queued",
                "createdAt": created,
                "updatedAt": created,
                "startedAt": None,
                "finishedAt": None,
                "progress": {
                    "total": len(units),
                    "completed": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "cancelled": 0,
                },
                "canCancelPending": True,
                "canCancelRunning": False,
                "runs": [unit.to_dict() | {"status": "pending"} for unit in units],
                "aggregate": None,
            }
            job["jobHash"] = _stable_hash(job)
            self._jobs[job_id] = job
            self._write(job)
            self._futures[job_id] = self._executor.submit(
                self._run_job, job_id, units, executor
            )
            return deepcopy(job)

    def _run_job(
        self,
        job_id: str,
        units: tuple[ExperimentRunUnit, ...],
        executor: Callable[[ExperimentRunUnit], dict[str, Any]],
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if job["status"] == "cancelled":
                return
            job["status"] = "running"
            job["startedAt"] = _now()
            job["updatedAt"] = job["startedAt"]
            self._write(job)
        for index, unit in enumerate(units):
            with self._lock:
                job = self._jobs[job_id]
                job["runs"][index]["status"] = "running"
                job["updatedAt"] = _now()
                self._write(job)
            try:
                result = executor(unit)
                audit = result.get("audit", {})
                report_hash = audit.get("reportHash") or audit.get("resultHash")
                if not isinstance(report_hash, str):
                    raise ValueError(
                        "run result does not contain an auditable report hash"
                    )
                outcome = {
                    "status": "succeeded",
                    "reportHash": report_hash,
                    "resultHash": _stable_hash(result),
                }
            except Exception as exc:  # noqa: BLE001 - run units are isolation boundaries
                outcome = {
                    "status": "failed",
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
            with self._lock:
                job = self._jobs[job_id]
                job["runs"][index].update(outcome)
                job["progress"]["completed"] += 1
                job["progress"][outcome["status"]] += 1
                job["updatedAt"] = _now()
                self._write(job)
        with self._lock:
            job = self._jobs[job_id]
            succeeded = int(job["progress"]["succeeded"])
            failed = int(job["progress"]["failed"])
            job["status"] = (
                "succeeded"
                if succeeded and not failed
                else "partially_succeeded"
                if succeeded
                else "failed"
            )
            job["finishedAt"] = _now()
            job["updatedAt"] = job["finishedAt"]
            aggregate_identity = {
                "planId": job["planId"],
                "status": job["status"],
                "runs": [
                    {
                        "runId": item["runId"],
                        "status": item["status"],
                        "reportHash": item.get("reportHash"),
                        "error": item.get("error"),
                    }
                    for item in job["runs"]
                ],
            }
            job["aggregate"] = {
                **job["progress"],
                "aggregateHash": _stable_hash(aggregate_identity),
            }
            self._write(job)

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            try:
                return deepcopy(self._jobs[job_id])
            except KeyError as exc:
                raise JobNotFoundError(job_id) from exc

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            try:
                job = self._jobs[job_id]
            except KeyError as exc:
                raise JobNotFoundError(job_id) from exc
            if job["status"] == "running":
                raise JobCancellationError(
                    "running CASCAQit optimization cannot be cancelled cooperatively"
                )
            if job["status"] != "queued":
                raise JobCancellationError(
                    f"job in status {job['status']} cannot be cancelled"
                )
            future = self._futures.get(job_id)
            if future is None or not future.cancel():
                raise JobCancellationError("queued job has already started")
            job["status"] = "cancelled"
            job["finishedAt"] = _now()
            job["updatedAt"] = job["finishedAt"]
            for unit in job["runs"]:
                unit["status"] = "cancelled"
            job["progress"]["cancelled"] = job["progress"]["total"]
            self._write(job)
            return deepcopy(job)

    def shutdown(self, *, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)
