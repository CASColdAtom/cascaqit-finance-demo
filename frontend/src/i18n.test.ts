import { describe, expect, it } from "vitest";
import { scenarioFrontierOutlook, translateContent } from "./i18n";

const serverTextSamples = [
  "债券 / 医药",
  "slack_group_制造_00",
  "P2 / 1 资金单位",
  "11h / 2.0 工时",
  "风险 92 / 1.8m",
  "关联 2 条告警",
  "实体 E-17 并行上限",
  "与 T-009 冲突",
  "前置交易 T-008 未入选",
  "额度 1 / 依赖 T-004",
  "09:30 CNY 内部划拨",
  "信用债 C -> 双边一",
  "制造企业 A / 低档",
  "目标 -0.0614",
  "风险、金额和时效",
  "流动性占用 / 资金单位",
  "目标值未进入当前候选",
  "Analog 业务项或 Digital residual 为空，不构成 Hybrid。",
];

describe("translateContent", () => {
  it("removes Chinese residue from representative API display values", () => {
    for (const sample of serverTextSamples) {
      expect(translateContent(sample)).not.toMatch(/[\u3400-\u9fff]/);
    }
  });

  it("preserves identifiers while translating their domain segment", () => {
    expect(translateContent("slack_group_制造_00")).toBe(
      "slack_group_Manufacturing_00",
    );
    expect(translateContent("与 T-009 冲突")).toBe("Conflicts with T-009");
  });
});

describe("scenarioFrontierOutlook", () => {
  const caseIds = [
    "electronic_structure",
    "docking_match",
    "active_center",
    "peptide_landscape",
    "rna_structure",
    "protein_dynamics",
    "defect_adsorption",
    "rydberg_dynamics",
  ];

  it.each(["zh", "en"] as const)(
    "provides distinct %s copy for every biomedical and materials scenario",
    (language) => {
      const descriptions = caseIds.map((caseId) =>
        scenarioFrontierOutlook(caseId, language),
      );
      expect(descriptions.every(Boolean)).toBe(true);
      expect(new Set(descriptions).size).toBe(caseIds.length);
    },
  );

  it("does not fall back to generic copy for an unregistered scenario", () => {
    expect(scenarioFrontierOutlook("future_scenario", "zh")).toBeNull();
  });

  it("keeps frontier copy focused on advantages instead of limitation language", () => {
    for (const caseId of caseIds) {
      expect(scenarioFrontierOutlook(caseId, "zh")).not.toMatch(
        /不替代|不代表|不能|不是|尚未|仅适用/,
      );
      expect(scenarioFrontierOutlook(caseId, "en")).not.toMatch(
        /\b(?:not|cannot|doesn't|does not)\b/i,
      );
    }
  });
});
