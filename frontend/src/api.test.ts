import { afterEach, describe, expect, it, vi } from "vitest";

import { getScenarios } from "./api";

describe("API error handling", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("preserves the backend error_id in the user-visible error", async () => {
    const errorId = "1979d20b16f84d148d78f5299aceab33";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: vi.fn().mockResolvedValue({
          detail: {
            code: "INTERNAL_EXECUTION_ERROR",
            message: "内部执行失败，请使用 error_id 查询本地日志。",
            error_id: errorId,
          },
        }),
      }),
    );

    await expect(getScenarios("biomedicine")).rejects.toThrow(
      `内部执行失败，请使用 error_id 查询本地日志。（error_id: ${errorId}）`,
    );
  });
});
