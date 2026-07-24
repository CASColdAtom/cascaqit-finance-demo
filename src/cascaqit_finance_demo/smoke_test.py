"""离线安装完成后的低成本真实执行自检。"""

from __future__ import annotations

import asyncio

from cascaqit.simulators.planning import HostResourceSnapshot

from cascaqit_finance_demo.api.app import RunRequest, run_scenario


def main() -> None:
    """检查主机资源、依赖和 settlement 最小执行链路。"""

    host = HostResourceSnapshot.detect()
    if host.total_memory_bytes <= 0 or host.cpu_count <= 0:
        raise RuntimeError("主机资源探测返回了无效结果。")

    result = asyncio.run(
        run_scenario(
            "settlement",
            RunRequest(shots=16, parameter_points=1),
        )
    )
    if not {"scenario", "preset", "run"}.issubset(result):
        raise RuntimeError("settlement 自检响应缺少必要字段。")
    counts = result["run"]["quantum"]["counts"]
    if sum(int(item["count"]) for item in counts) != 16:
        raise RuntimeError("settlement 自检采样数不等于 16。")

    print(
        "Runtime smoke test passed: "
        f"memory={host.total_memory_bytes}, cpu={host.cpu_count}, shots=16"
    )


if __name__ == "__main__":
    main()
