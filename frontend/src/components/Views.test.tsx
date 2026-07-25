// @vitest-environment jsdom

import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { RunPayload } from "../types";
import { I18nProvider } from "../i18n";
import { AuditView } from "./Views";

afterEach(cleanup);

const run = {
  audit: {
    caseId: "portfolio",
    mode: "digital",
    problemHash: "problem-hash",
    analysisHash: "analysis-hash",
    compileHash: "compile-hash",
    executionHash: "execution-hash",
    targetId: "local-neutral-atom",
    backend: "LocalBackend",
    executionKind: "local_simulation",
    seed: 23,
    shots: 32,
    wallTimeSeconds: 0.125,
    hardwareExecution: false,
    cloudExecution: false,
    networkAccessed: false,
    optimalityClaim: "not_claimed",
    reportPath: null,
  },
} as unknown as RunPayload;

describe("AuditView", () => {
  it("keeps the execution summary focused on mode and run parameters", () => {
    const { container } = render(
      <I18nProvider initialLanguage="zh">
        <AuditView run={run} mode="digital" />
      </I18nProvider>,
    );

    const labels = Array.from(container.querySelectorAll(".audit-section dt")).map(
      (item) => item.textContent,
    );
    expect(labels).toEqual(["Mode", "Seed", "Shots", "Wall time"]);
    expect(container.querySelector(".audit-boundary")).toBeNull();
    expect(container.textContent).not.toContain("本地数值模拟，非量子真机");
  });
});
