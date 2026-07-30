"""Run the fixed-seed release calibration for material Analog AHS dynamics."""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cascaqit

from cascaqit_materials_demo.rydberg_dynamics import run_rydberg_dynamics

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "docs" / "process" / "evidence" / "materials_analog_calibration.json"
)
PRESETS = ("perfect_lattice", "single_vacancy", "multi_defect_impurity")
SEEDS = (7, 23, 41)


def calibrate() -> dict[str, Any]:
    runs = []
    for preset in PRESETS:
        for seed in SEEDS:
            started = time.perf_counter()
            run = run_rydberg_dynamics(
                preset=preset,
                values={"sample_count": 9},
                shots=128,
                seed=seed,
                time_steps=320,
            )
            seconds = time.perf_counter() - started
            comparison = run["domain"]["comparison"]
            summary = run["quantum"]["summary"]
            counts_total = sum(
                item["count"] for item in run["quantum"]["terminalCounts"]
            )
            passed = (
                comparison["maxOccupationAbsoluteError"] < 1e-3
                and comparison["maxCorrelationAbsoluteError"] < 1e-3
                and comparison["terminalStateFidelity"] > 0.999
                and comparison["maxAnalogNormError"] < 1e-9
                and comparison["maxClassicNormError"] < 1e-9
                and counts_total == 128
                and summary["digitalGateCount"] == 0
                and summary["digitalResidualCount"] == 0
                and summary["hybridBlockCount"] == 0
            )
            audit = run["audit"]
            runs.append(
                {
                    "preset": preset,
                    "seed": seed,
                    "seconds": seconds,
                    "sampleCount": summary["sampleCount"],
                    "shotsPerTime": summary["shotsPerTime"],
                    "terminalCountsTotal": counts_total,
                    "comparison": comparison,
                    "pureAnalog": {
                        "digitalGateCount": summary["digitalGateCount"],
                        "digitalResidualCount": summary["digitalResidualCount"],
                        "hybridBlockCount": summary["hybridBlockCount"],
                    },
                    "hashes": {
                        key: audit[key]
                        for key in (
                            "manifestHash",
                            "analysisHash",
                            "compileHash",
                            "executionHash",
                            "resultHash",
                            "trajectoryHash",
                            "classicReferenceHash",
                            "initialStateHash",
                            "pulseScheduleHash",
                            "rydbergLayoutHash",
                            "backendHash",
                            "configurationHash",
                            "outcomeHash",
                            "reportHash",
                        )
                    },
                    "passed": passed,
                }
            )
    return {
        "schema": "materials.analog-release-calibration.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cascaqitVersion": str(cascaqit.__version__),
            "cascaqitModule": str(Path(cascaqit.__file__).resolve()),
        },
        "configuration": {
            "presets": list(PRESETS),
            "seeds": list(SEEDS),
            "sampleCount": 9,
            "shotsPerTime": 128,
            "timeStepsAtTerminal": 320,
            "execution": "independent_prefix_ahs_from_declared_initial_state",
            "classicReference": "scipy_dop853",
        },
        "thresholds": {
            "maxOccupationAbsoluteError": 1e-3,
            "maxCorrelationAbsoluteError": 1e-3,
            "minimumTerminalStateFidelity": 0.999,
            "maxNormError": 1e-9,
        },
        "summary": {
            "runCount": len(runs),
            "passedCount": sum(item["passed"] for item in runs),
            "failedCount": sum(not item["passed"] for item in runs),
            "maximumSeconds": max(item["seconds"] for item in runs),
            "maximumOccupationAbsoluteError": max(
                item["comparison"]["maxOccupationAbsoluteError"] for item in runs
            ),
            "maximumCorrelationAbsoluteError": max(
                item["comparison"]["maxCorrelationAbsoluteError"] for item in runs
            ),
            "minimumTerminalStateFidelity": min(
                item["comparison"]["terminalStateFidelity"] for item in runs
            ),
            "passed": all(item["passed"] for item in runs),
        },
        "runs": runs,
        "claimBoundary": (
            "Local four-site effective-model simulation only; no hardware, material "
            "transport, lifetime, or quantum-advantage claim."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    evidence = calibrate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"output": str(args.output), "summary": evidence["summary"]},
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
