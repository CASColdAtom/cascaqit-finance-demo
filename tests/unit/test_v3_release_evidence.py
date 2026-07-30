"""Tests for the aggregate V3 fixed-seed release evidence gate."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from scripts.validate_v3_release_evidence import (
    DEFAULT_EVIDENCE_ROOT,
    SOURCE_FILES,
    validate_evidence,
)


def test_v3_release_evidence_covers_all_eight_scenarios() -> None:
    result = validate_evidence()

    assert result["summary"] == {
        "scenarioCount": 8,
        "runCount": 84,
        "passedScenarioCount": 8,
        "failedScenarioCount": 0,
        "passed": True,
    }
    assert result["failures"] == []
    assert {row["caseId"] for row in result["scenarios"]} == {
        "electronic_structure",
        "docking_match",
        "active_center",
        "peptide_landscape",
        "rna_structure",
        "protein_dynamics",
        "defect_adsorption",
        "rydberg_dynamics",
    }


def test_v3_release_evidence_rejects_classic_protein_fallback(
    tmp_path: Path,
) -> None:
    for filename in SOURCE_FILES.values():
        shutil.copy2(DEFAULT_EVIDENCE_ROOT / filename, tmp_path / filename)
    path = tmp_path / SOURCE_FILES["protein_dynamics"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["summary"]["classicFallbackUsed"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_evidence(tmp_path)

    assert result["summary"]["passed"] is False
    assert result["summary"]["failedScenarioCount"] == 1
    assert any("protein_dynamics" in failure for failure in result["failures"])
