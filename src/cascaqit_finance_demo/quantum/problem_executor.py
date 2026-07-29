"""Compatibility exports for the domain-neutral industry Problem executor."""

from cascaqit_industry_demo.problem_executor import (
    ParameterSearchStrategy,
    ProblemAlgorithmPolicy,
    ProblemModeAdvisor,
    ScenarioExecutor,
    build_optimizer_config,
    default_parameter_sets,
    generate_parameter_sets,
)

# Preserve the public names used by existing finance integrations.
FinanceAlgorithmPolicy = ProblemAlgorithmPolicy
FinanceModeAdvisor = ProblemModeAdvisor

__all__ = [
    "FinanceAlgorithmPolicy",
    "FinanceModeAdvisor",
    "ParameterSearchStrategy",
    "ScenarioExecutor",
    "build_optimizer_config",
    "default_parameter_sets",
    "generate_parameter_sets",
]
