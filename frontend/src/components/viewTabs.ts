import {
  Atom,
  FileJson,
  Gauge,
  GitBranch,
  Network,
  Scale,
  type LucideIcon,
} from "lucide-react";

export type ViewId =
  | "business"
  | "scenario"
  | "mapping"
  | "quantum"
  | "comparison"
  | "audit";

export const viewTabs: ReadonlyArray<{
  id: ViewId;
  labelKey:
    | "businessResult"
    | "scenarioSituation"
    | "problemMapping"
    | "quantumExperiment"
    | "comparisonAnalysis"
    | "auditEvidence";
  icon: LucideIcon;
}> = [
  { id: "business", labelKey: "businessResult", icon: Gauge },
  { id: "scenario", labelKey: "scenarioSituation", icon: Network },
  { id: "mapping", labelKey: "problemMapping", icon: GitBranch },
  { id: "quantum", labelKey: "quantumExperiment", icon: Atom },
  { id: "comparison", labelKey: "comparisonAnalysis", icon: Scale },
  { id: "audit", labelKey: "auditEvidence", icon: FileJson },
];
