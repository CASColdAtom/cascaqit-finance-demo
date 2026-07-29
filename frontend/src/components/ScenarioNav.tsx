import {
  Atom,
  Building2,
  ChartNoAxesCombined,
  Landmark,
  Layers3,
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
  atom: Atom,
  "building-2": Building2,
  "chart-no-axes-combined": ChartNoAxesCombined,
  landmark: Landmark,
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
        {domainId === "finance" ? t("financeScenarios") : t("biomedicineScenarios")}
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
                <small>{scenario.recommendedMode.toUpperCase()}</small>
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
