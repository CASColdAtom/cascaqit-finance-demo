import {
  Activity,
  Atom,
  Building2,
  ChartNoAxesCombined,
  GitBranch,
  Grid3X3,
  Landmark,
  Layers3,
  Network,
  Orbit,
  Route,
  ScanSearch,
  Sigma,
  Waves,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { DomainId, ScenarioSpec } from "../types";
import { useI18n } from "../i18n";

const icons: Record<string, LucideIcon> = {
  activity: Activity,
  atom: Atom,
  "building-2": Building2,
  "chart-no-axes-combined": ChartNoAxesCombined,
  "git-branch": GitBranch,
  "grid-3x3": Grid3X3,
  landmark: Landmark,
  network: Network,
  orbit: Orbit,
  route: Route,
  "layers-3": Layers3,
  "scan-search": ScanSearch,
  sigma: Sigma,
  waves: Waves,
};

interface ScenarioNavProps {
  scenarios: ScenarioSpec[];
  activeId: string;
  onSelect: (scenario: ScenarioSpec) => void;
  domainId?: DomainId;
}

export function ScenarioNav({ scenarios, activeId, onSelect, domainId = "finance" }: ScenarioNavProps) {
  const { t } = useI18n();
  return (
    <nav className="scenario-nav" aria-label={t("experiments")}>
      <div className="nav-section-label">
        {domainId === "finance"
          ? t("financeScenarios")
          : domainId === "biomedicine"
            ? t("biomedicineScenarios")
            : t("materialsScenarios")}
      </div>
      <div className="scenario-list">
        {scenarios.map((scenario, index) => {
          const Icon = icons[scenario.icon] ?? ChartNoAxesCombined;
          const active = scenario.caseId === activeId;
          return (
            <button
              className={`scenario-item accent-${scenario.accent}`}
              data-active={active}
              aria-current={active ? "page" : undefined}
              key={scenario.caseId}
              onClick={() => onSelect(scenario)}
              type="button"
            >
              <span className="scenario-index">{String(index + 1).padStart(2, "0")}</span>
              <span className="scenario-icon" aria-hidden="true">
                <Icon size={18} strokeWidth={1.7} />
              </span>
              <span className="scenario-copy">
                <strong>{scenario.shortTitle}</strong>
                <small>
                  {scenario.implementationStatus === "preview"
                    ? "PREVIEW"
                    : scenario.recommendedMode.toUpperCase()}
                </small>
              </span>
              <span className="scenario-signal" aria-hidden="true" />
            </button>
          );
        })}
      </div>
      <div className="nav-footprint" aria-label={t("execution")}>
        <span>{t("execution")}</span>
        <span>{t("syntheticData")}</span>
        <span>{t("auditReady")}</span>
      </div>
    </nav>
  );
}
