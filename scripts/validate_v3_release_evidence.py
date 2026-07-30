"""Validate and aggregate fixed-seed evidence for the eight V3 demo scenarios."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE_ROOT = ROOT / "docs" / "process" / "evidence"
DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "industry_v3_release_acceptance.json"
SEEDS = {7, 23, 41}
BASE_PRESETS = {
    "electronic_structure": {
        "h2_bond_scan",
        "lih_active_space",
        "h2o_minimal",
        "lih_potential_scan",
    },
    "docking_match": {
        "reference_pose",
        "strict_geometry",
        "pharmacophore_coverage",
        "multi_pose_balanced",
    },
    "active_center": {
        "antiferromagnetic",
        "ligand_field",
        "coupling_imbalance",
        "trinuclear_frustrated",
    },
    "peptide_landscape": {
        "hydrophobic_core",
        "charged_competition",
        "contact_limited",
        "octapeptide_hydrophobic",
    },
}
NEW_PRESETS = {
    "rna_structure": {
        "hairpin_reference",
        "stem_competition",
        "limited_pseudoknot",
    },
    "protein_dynamics": {
        "open_to_closed",
        "barrier_shift",
        "alternate_basin",
    },
    "defect_adsorption": {
        "ceria_vacancy_co",
        "tio2_vacancy_water",
        "mos2_vacancy_hydrogen",
    },
    "rydberg_dynamics": {
        "perfect_lattice",
        "single_vacancy",
        "multi_defect_impurity",
    },
}
SOURCE_FILES = {
    "biomedicine_v2": "biomedicine_release_calibration.json",
    "rna_structure": "rna_structure_calibration.json",
    "protein_dynamics": "protein_dynamics_calibration.json",
    "defect_adsorption": "materials_defect_adsorption_calibration.json",
    "rydberg_dynamics": "materials_analog_calibration.json",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_hash(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _expected_combinations(
    presets: set[str], seeds: set[int] = SEEDS
) -> set[tuple[str, int]]:
    return set(product(presets, seeds))


def validate_evidence(evidence_root: Path = DEFAULT_EVIDENCE_ROOT) -> dict[str, Any]:
    failures: list[str] = []
    sources: dict[str, dict[str, Any]] = {}
    payloads: dict[str, dict[str, Any]] = {}
    for source_id, filename in SOURCE_FILES.items():
        path = evidence_root / filename
        if not path.is_file():
            failures.append(f"missing evidence file: {filename}")
            continue
        payloads[source_id] = _load(path)
        sources[source_id] = {
            "file": filename,
            "sha256": _sha256(path),
            "schema": payloads[source_id].get("schema"),
            "generatedAt": payloads[source_id].get("generatedAt"),
        }

    scenarios: list[dict[str, Any]] = []
    base = payloads.get("biomedicine_v2")
    if base is not None:
        records = base.get("records", [])
        seed_plan = base.get("fixedSeedPlan", {})
        if base.get("summary", {}).get("passed") is not True:
            failures.append("biomedicine V2 calibration summary is not passed")
        for scenario_id, presets in BASE_PRESETS.items():
            rows = [row for row in records if row.get("scenario") == scenario_id]
            actual = {
                (row.get("preset"), row.get("seed"))
                for row in rows
                if isinstance(row.get("seed"), int)
            }
            planned = {
                (preset, seed)
                for preset, seeds in seed_plan.get(scenario_id, {}).items()
                for seed in seeds
            }
            passed = (
                set(seed_plan.get(scenario_id, {})) == presets
                and actual == planned
                and len(rows) == 12
                and all(row.get("passed") is True for row in rows)
                and all(
                    all(_is_hash(value) for value in row.get("audit", {}).values())
                    for row in rows
                )
            )
            if not passed:
                failures.append(f"{scenario_id}: incomplete V2 fixed-seed evidence")
            scenarios.append(
                {
                    "domainId": "biomedicine",
                    "caseId": scenario_id,
                    "runCount": len(rows),
                    "presetCount": len(presets),
                    "status": "passed" if passed else "failed",
                    "source": SOURCE_FILES["biomedicine_v2"],
                }
            )

    rna = payloads.get("rna_structure")
    if rna is not None:
        rows = rna.get("rows", [])
        actual = {(row.get("preset"), row.get("seed")) for row in rows}
        passed = (
            actual == _expected_combinations(NEW_PRESETS["rna_structure"])
            and len(rows) == 9
            and all(row.get("feasible") is True for row in rows)
            and all(row.get("source") == "quantum_observed" for row in rows)
            and all(
                all(
                    _is_hash(row.get(key))
                    for key in (
                        "problemHash",
                        "configurationHash",
                        "outcomeHash",
                        "reportHash",
                    )
                )
                for row in rows
            )
        )
        if not passed:
            failures.append("rna_structure: incomplete fixed-seed evidence")
        scenarios.append(
            _scenario_summary("biomedicine", "rna_structure", rows, passed)
        )

    protein = payloads.get("protein_dynamics")
    if protein is not None:
        rows = protein.get("runs", [])
        summary = protein.get("summary", {})
        actual = {(row.get("preset"), row.get("seed")) for row in rows}
        passed = (
            actual == _expected_combinations(NEW_PRESETS["protein_dynamics"])
            and len(rows) == 9
            and summary.get("runCount") == 9
            and summary.get("observedFeasibleRunCount") == 6
            and summary.get("quantumNotObservedRunCount") == 3
            and summary.get("classicFallbackUsed") is False
            and all(
                row.get("status")
                in {"observed_feasible", "quantum_not_observed"}
                for row in rows
            )
            and all(
                row.get("path") is None
                for row in rows
                if row.get("status") == "quantum_not_observed"
            )
            and all(_is_hash(row.get("executionHash")) for row in rows)
        )
        if not passed:
            failures.append(
                "protein_dynamics: incomplete or fallback-contaminated evidence"
            )
        scenarios.append(
            _scenario_summary("biomedicine", "protein_dynamics", rows, passed)
        )

    materials = payloads.get("defect_adsorption")
    if materials is not None:
        rows = materials.get("runs", [])
        summary = materials.get("summary", {})
        actual = {(row.get("preset"), row.get("seed")) for row in rows}
        passed = (
            actual == _expected_combinations(NEW_PRESETS["defect_adsorption"])
            and len(rows) == 9
            and summary.get("observedFeasibleRunCount") == 9
            and summary.get("analogTermsPerRun") == 15
            and summary.get("digitalResidualTermsPerRun") == 32
            and all(row.get("quantumStatus") == "observed_feasible" for row in rows)
            and all(
                all(
                    _is_hash(row.get(key))
                    for key in (
                        "problemHash",
                        "compileHash",
                        "resultHash",
                        "reportHash",
                    )
                )
                for row in rows
            )
        )
        if not passed:
            failures.append("defect_adsorption: incomplete Hybrid calibration evidence")
        scenarios.append(
            _scenario_summary("materials", "defect_adsorption", rows, passed)
        )

    analog = payloads.get("rydberg_dynamics")
    if analog is not None:
        rows = analog.get("runs", [])
        summary = analog.get("summary", {})
        actual = {(row.get("preset"), row.get("seed")) for row in rows}
        passed = (
            actual == _expected_combinations(NEW_PRESETS["rydberg_dynamics"])
            and len(rows) == 9
            and summary.get("passed") is True
            and summary.get("passedCount") == 9
            and all(row.get("passed") is True for row in rows)
            and all(
                row.get("pureAnalog")
                == {
                    "digitalGateCount": 0,
                    "digitalResidualCount": 0,
                    "hybridBlockCount": 0,
                }
                for row in rows
            )
            and all(
                all(_is_hash(value) for value in row.get("hashes", {}).values())
                for row in rows
            )
        )
        if not passed:
            failures.append("rydberg_dynamics: incomplete Pure Analog evidence")
        scenarios.append(
            _scenario_summary("materials", "rydberg_dynamics", rows, passed)
        )

    expected_ids = set(BASE_PRESETS) | set(NEW_PRESETS)
    actual_ids = {scenario["caseId"] for scenario in scenarios}
    if actual_ids != expected_ids:
        failures.append(
            "scenario coverage mismatch: "
            f"expected {sorted(expected_ids)}, got {sorted(actual_ids)}"
        )
    return {
        "schema": "industry.v3-release-evidence.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "scenarios": scenarios,
        "summary": {
            "scenarioCount": len(scenarios),
            "runCount": sum(row["runCount"] for row in scenarios),
            "passedScenarioCount": sum(row["status"] == "passed" for row in scenarios),
            "failedScenarioCount": sum(row["status"] != "passed" for row in scenarios),
            "passed": not failures and len(scenarios) == 8,
        },
        "failures": failures,
        "claimBoundary": (
            "Local simulation release evidence only; no hardware, quantum-advantage, "
            "drug, clinical, material-property, or full-atom dynamics claim."
        ),
    }


def _scenario_summary(
    domain_id: str,
    case_id: str,
    rows: list[dict[str, Any]],
    passed: bool,
) -> dict[str, Any]:
    return {
        "domainId": domain_id,
        "caseId": case_id,
        "runCount": len(rows),
        "presetCount": len(NEW_PRESETS[case_id]),
        "status": "passed" if passed else "failed",
        "source": SOURCE_FILES[case_id],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = validate_evidence(args.evidence_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}))
    if not result["summary"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
