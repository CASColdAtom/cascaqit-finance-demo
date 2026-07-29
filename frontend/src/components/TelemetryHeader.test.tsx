// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n";
import { TelemetryHeader } from "./TelemetryHeader";

afterEach(cleanup);

describe("TelemetryHeader", () => {
  it("omits the synthetic-data badge from the top-right status strip", () => {
    render(
      <I18nProvider initialLanguage="zh">
        <TelemetryHeader />
      </I18nProvider>,
    );

    const header = screen.getByRole("banner");
    expect(within(header).getByText("实验服务在线")).toBeTruthy();
    expect(within(header).getByText("执行可审计")).toBeTruthy();
    expect(within(header).queryByText(/演示|demo/i)).toBeNull();
  });

  it("exposes the finance and biomedicine domain switch", () => {
    const onDomain = vi.fn();
    render(
      <I18nProvider initialLanguage="zh">
        <TelemetryHeader domainId="finance" onDomain={onDomain} />
      </I18nProvider>,
    );

    expect(screen.getByRole("button", { name: "金融" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "生物医药" }));
    expect(onDomain).toHaveBeenCalledWith("biomedicine");
  });
});
