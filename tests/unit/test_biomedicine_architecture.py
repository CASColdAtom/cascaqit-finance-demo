"""Architecture guards for the biomedicine domain boundary."""

from pathlib import Path
from typing import get_args

from cascaqit_finance_demo.quantum.problem_executor import (
    ScenarioExecutor as FinanceScenarioExecutor,
)
from cascaqit_industry_demo.problem_api import ModeStatus
from cascaqit_industry_demo.problem_executor import ScenarioExecutor


def test_biomedicine_package_does_not_import_finance_domain() -> None:
    """Biomedicine models and executors must not acquire Finance package coupling."""

    package = Path("src/cascaqit_biomedicine_demo")
    offenders = [
        path
        for path in package.glob("*.py")
        if "cascaqit_finance_demo" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_finance_executor_is_a_compatibility_export_of_industry_executor() -> None:
    """The legacy finance import remains stable without owning shared execution code."""

    assert FinanceScenarioExecutor is ScenarioExecutor


def test_industry_mode_status_matches_the_public_workbench_contract() -> None:
    assert get_args(ModeStatus) == ("recommended", "comparable", "unsuitable")
