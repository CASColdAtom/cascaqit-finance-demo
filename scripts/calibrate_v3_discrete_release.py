"""Regenerate fixed-seed release evidence for the V3 discrete scenarios."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cascaqit_biomedicine_demo.protein_dynamics import run_protein_dynamics
from cascaqit_biomedicine_demo.rna_structure import run_rna_structure
from cascaqit_materials_demo.defect_adsorption import run_defect_adsorption

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "docs" / "process" / "evidence"
SEEDS = (7, 23, 41)
RNA_PRESETS = ("hairpin_reference", "stem_competition", "limited_pseudoknot")
PROTEIN_PRESETS = ("open_to_closed", "barrier_shift", "alternate_basin")
PROTEIN_SEED_PLAN = {
    "open_to_closed": (0, 5, 8),
    "barrier_shift": (0, 1, 3),
    "alternate_basin": (0, 1, 3),
}
MATERIAL_PRESETS = (
    "ceria_vacancy_co",
    "tio2_vacancy_water",
    "mos2_vacancy_hydrogen",
)


def _version(name: str) -> str:
    return importlib.metadata.version(name)


def _environment() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cascaqitVersion": _version("cascaqit"),
        "cascaqitModule": str(Path(__import__("cascaqit").__file__).resolve()),
    }


def calibrate_rna() -> dict[str, Any]:
    rows = []
    for preset in RNA_PRESETS:
        for seed in SEEDS:
            print(f"calibrating rna_structure/{preset} seed={seed}", flush=True)
            run = run_rna_structure(
                preset=preset,
                values={},
                shots=256,
                seed=seed,
                layers=1,
                parameter_budget=4,
                optimizer_starts=1,
            )
            candidate = run["domain"]["quantumCandidate"]
            audit = run["audit"]
            rows.append(
                {
                    "preset": preset,
                    "seed": seed,
                    "feasible": candidate["feasible"],
                    "source": candidate["source"],
                    "dotBracket": candidate["dotBracket"],
                    "energy": candidate["energy"],
                    "count": candidate["count"],
                    "observedFeasibleRate": run["domain"][
                        "observedFeasibleRate"
                    ],
                    "lowEnergyCoverage": run["domain"]["lowEnergyCoverage"],
                    "structureDiversity": run["domain"]["structureDiversity"],
                    "problemHash": audit["problemHash"],
                    "configurationHash": audit["configurationHash"],
                    "outcomeHash": audit["outcomeHash"],
                    "reportHash": audit["reportHash"],
                }
            )
    return {
        "schema": "biomedicine.rna.calibration.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "environment": _environment(),
        "configuration": {
            "mode": "digital",
            "algorithm": "qaoa",
            "layers": 1,
            "shots": 256,
            "parameterBudget": 4,
            "optimizerStarts": 1,
            "presets": list(RNA_PRESETS),
            "seeds": list(SEEDS),
        },
        "summary": {
            "runCount": len(rows),
            "observedFeasibleRunCount": sum(row["feasible"] for row in rows),
            "passed": all(
                row["feasible"] and row["source"] == "quantum_observed"
                for row in rows
            ),
        },
        "rows": rows,
    }


def calibrate_protein() -> dict[str, Any]:
    runs = []
    for preset in PROTEIN_PRESETS:
        for seed in PROTEIN_SEED_PLAN[preset]:
            print(f"calibrating protein_dynamics/{preset} seed={seed}", flush=True)
            run = run_protein_dynamics(
                preset=preset,
                values={},
                shots=256,
                seed=seed,
                layers=1,
                parameter_budget=4,
                optimizer_starts=1,
            )
            domain = run["domain"]
            candidate = domain["quantumCandidate"]
            classic = domain["classicActivePath"]
            audit = run["audit"]
            failure_reasons = {
                item["id"]: item["shotCount"]
                for item in domain["failureReasons"]
            }
            runs.append(
                {
                    "preset": preset,
                    "seed": seed,
                    "status": domain["quantumStatus"],
                    "feasibleShotRate": domain["observedFeasibleRate"],
                    "pathCost": candidate["pathCost"] if candidate else None,
                    "pathOverlap": candidate["pathOverlap"] if candidate else None,
                    "path": candidate["stateIds"] if candidate else None,
                    "classicPath": classic["stateIds"],
                    "classicCost": classic["pathCost"],
                    "failureReasons": failure_reasons,
                    "problemHash": audit["problemHash"],
                    "selectionHash": audit["selectionHash"],
                    "executionHash": audit["executionHash"],
                }
            )
    observed = [row for row in runs if row["status"] == "observed_feasible"]
    rates = [row["feasibleShotRate"] for row in runs]
    return {
        "schema": "protein-dynamics-calibration.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "environment": _environment(),
        "configuration": {
            "mode": "digital",
            "algorithm": "qaoa",
            "layers": 1,
            "shots": 256,
            "searchStrategy": "continuous",
            "parameterBudget": 4,
            "optimizerStarts": 1,
            "maximumSteps": 3,
            "barrierWeight": 1.0,
            "presets": list(PROTEIN_PRESETS),
            "seedPlan": {
                preset: list(seeds)
                for preset, seeds in PROTEIN_SEED_PLAN.items()
            },
        },
        "summary": {
            "runCount": len(runs),
            "observedFeasibleRunCount": len(observed),
            "quantumNotObservedRunCount": len(runs) - len(observed),
            "feasibleShotRateMinimum": min(rates),
            "feasibleShotRateMaximum": max(rates),
            "classicFallbackUsed": False,
        },
        "runs": runs,
    }


def calibrate_materials() -> dict[str, Any]:
    runs = []
    analog_terms: set[int] = set()
    digital_terms: set[int] = set()
    for preset in MATERIAL_PRESETS:
        for seed in SEEDS:
            print(f"calibrating defect_adsorption/{preset} seed={seed}", flush=True)
            run = run_defect_adsorption(
                preset=preset,
                values={},
                mode="hybrid",
                shots=128,
                seed=seed,
                layers=1,
                search_strategy="preset",
                parameter_budget=2,
                optimizer_starts=1,
            )
            domain = run["domain"]
            summary = run["quantum"]["summary"]
            audit = run["audit"]
            analog_terms.add(summary["analogTerms"])
            digital_terms.add(summary["digitalTerms"])
            runs.append(
                {
                    "preset": preset,
                    "seed": seed,
                    "quantumStatus": domain["quantumStatus"],
                    "feasibleShotRatio": domain["feasibleShotRatio"],
                    "observedFeasibleCount": domain["observedFeasibleCount"],
                    "problemHash": audit["problemHash"],
                    "compileHash": audit["compileHash"],
                    "resultHash": audit["resultHash"],
                    "reportHash": audit["reportHash"],
                }
            )
    ratios = [row["feasibleShotRatio"] for row in runs]
    if len(analog_terms) != 1 or len(digital_terms) != 1:
        raise RuntimeError("Hybrid term counts changed across calibration runs")
    return {
        "schema": "materials.defect-adsorption-calibration.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "environment": _environment(),
        "configuration": {
            "mode": "hybrid",
            "shots": 128,
            "layers": 1,
            "searchStrategy": "preset",
            "parameterBudget": 2,
            "optimizerStarts": 1,
            "presets": list(MATERIAL_PRESETS),
            "seeds": list(SEEDS),
        },
        "summary": {
            "runCount": len(runs),
            "observedFeasibleRunCount": sum(
                row["quantumStatus"] == "observed_feasible" for row in runs
            ),
            "minimumFeasibleShotRatio": min(ratios),
            "maximumFeasibleShotRatio": max(ratios),
            "analogTermsPerRun": next(iter(analog_terms)),
            "digitalResidualTermsPerRun": next(iter(digital_terms)),
        },
        "runs": runs,
    }


def _write(output: Path, payload: dict[str, Any]) -> None:
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=EVIDENCE_ROOT)
    args = parser.parse_args()
    if _version("cascaqit") != "1.0.7a0":
        raise RuntimeError("V3 calibration requires CASCAQit 1.0.7a0")
    args.output_root.mkdir(parents=True, exist_ok=True)
    outputs = {
        "rna_structure_calibration.json": calibrate_rna(),
        "protein_dynamics_calibration.json": calibrate_protein(),
        "materials_defect_adsorption_calibration.json": calibrate_materials(),
    }
    for filename, payload in outputs.items():
        _write(args.output_root / filename, payload)
    print(
        json.dumps(
            {
                "outputRoot": str(args.output_root),
                "runCount": sum(
                    payload["summary"]["runCount"] for payload in outputs.values()
                ),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
