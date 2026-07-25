// @vitest-environment jsdom

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
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
    expect(within(header).queryByText("合成演示数据")).toBeNull();
  });
});
