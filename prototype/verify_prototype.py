"""Render and smoke-test the standalone finance Demo prototype."""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parent
PAGE_URI = (ROOT / "index.html").as_uri()
SCREENSHOTS = ROOT / "screenshots"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def _assert_page_geometry(page: Page, *, require_charts: bool = True) -> None:
    geometry = page.evaluate(
        """() => ({
            bodyScrollWidth: document.body.scrollWidth,
            bodyClientWidth: document.body.clientWidth,
            svgCount: document.querySelectorAll('.view svg').length,
            emptySvgCount: Array.from(document.querySelectorAll('.view svg'))
                .filter((svg) => {
                    const box = svg.getBoundingClientRect();
                    return box.width < 100 || box.height < 100;
                }).length,
            clippedControls: Array.from(document.querySelectorAll('button, select, input'))
                .filter((node) => {
                    if (node.getClientRects().length === 0) return false;
                    const box = node.getBoundingClientRect();
                    const intentionallyScrollable = node.closest('.data-editor, .tabs');
                    return !intentionallyScrollable && (
                        box.width < 1 || box.height < 1 || box.right > document.body.clientWidth + 1
                    );
                }).length,
        })"""
    )
    assert geometry["bodyScrollWidth"] <= geometry["bodyClientWidth"] + 1
    if require_charts:
        assert geometry["svgCount"] >= 1
    assert geometry["emptySvgCount"] == 0
    assert geometry["clippedControls"] == 0


def main() -> None:
    """Open key views at desktop and mobile widths and save screenshots."""
    SCREENSHOTS.mkdir(exist_ok=True)
    errors: list[str] = []
    with sync_playwright() as playwright:
        launch = {"headless": True}
        if CHROME.exists():
            launch["executable_path"] = str(CHROME)
        browser = playwright.chromium.launch(**launch)

        desktop = browser.new_page(viewport={"width": 1440, "height": 900})
        desktop.on("pageerror", lambda error: errors.append(str(error)))
        desktop.goto(PAGE_URI)
        desktop.wait_for_load_state("domcontentloaded")
        _assert_page_geometry(desktop)
        assert desktop.get_by_text("业务对象").is_visible()
        assert desktop.get_by_text("QUBO terms").is_visible()
        desktop.get_by_text("业务数据与约束").click()
        assert desktop.locator(".record-toggle").count() == 8
        desktop.screenshot(path=SCREENSHOTS / "portfolio-desktop.png", full_page=True)

        desktop.get_by_role("tab", name="场景分析").click()
        assert desktop.get_by_text("四类压力场景回测").is_visible()
        assert desktop.get_by_text("4 个预设均可运行").is_visible()
        _assert_page_geometry(desktop)
        desktop.screenshot(path=SCREENSHOTS / "portfolio-scenarios-desktop.png", full_page=True)

        desktop.get_by_role("button", name="交易结算").click()
        desktop.get_by_text("业务数据与约束").click()
        assert desktop.locator(".record-toggle").count() == 10
        desktop.get_by_role("tab", name="量子实验").click()
        _assert_page_geometry(desktop)
        assert desktop.get_by_text("2 × 3 · equal x/y scale").is_visible()
        assert desktop.get_by_text("Rabi · Detuning · Phase").is_visible()
        assert desktop.locator('svg[data-count-total="256"]').count() == 1
        desktop.screenshot(path=SCREENSHOTS / "settlement-hybrid-desktop.png", full_page=True)

        desktop.get_by_role("button", name="运行优化").click()
        desktop.wait_for_timeout(1700)
        assert desktop.get_by_text("已完成", exact=True).is_visible()

        scenario_expectations = {
            "投资组合": [("基准市场", "9.2%"), ("利率上行", "7.3%"), ("权益回撤", "6.8%"), ("商品冲击", "10.1%")],
            "交易结算": [("日常批次", "¥ 13.8M"), ("流动性收紧", "¥ 10.3M"), ("重点客户优先", "¥ 12.1M")],
            "调查编排": [("账户接管", "78%"), ("团伙交易", "89%"), ("商户异常", "¥ 7.6M")],
            "抵押品分配": [("日常补缴", "¥ 11.6M"), ("市场波动", "¥ 12.4M"), ("保留优质资产", "¥ 10.8M")],
            "流动性调度": [("基准流动性", "100%"), ("日终压力", "100%"), ("跨币种短缺", "100%")],
            "授信额度": [("稳健配置", "¥ 18.5M"), ("收益优先", "¥ 21.2M"), ("行业集中压降", "¥ 16.9M")],
            "衍生品定价": [("欧式看涨", "¥ 10.96"), ("欧式看跌", "¥ 7.24"), ("亚式期权", "¥ 7.05"), ("障碍期权", "¥ 2.15")],
        }

        for case_name in ("投资组合", "交易结算", "调查编排", "抵押品分配", "流动性调度", "授信额度", "衍生品定价"):
            desktop.get_by_role("button", name=case_name).click()
            expected_records = {"投资组合": 8, "交易结算": 10, "调查编排": 12, "抵押品分配": 9, "流动性调度": 12, "授信额度": 10, "衍生品定价": 8}[case_name]
            scenario = desktop.locator("#scenario")
            assert scenario.locator("option").count() == len(scenario_expectations[case_name])
            for scenario_name, expected_metric in scenario_expectations[case_name]:
                scenario.select_option(label=scenario_name)
                assert desktop.locator(".metric-value").first.text_content() == expected_metric
                assert scenario_name in desktop.locator("#result-state").text_content()
            desktop.get_by_text("业务数据与约束").click()
            assert desktop.locator(".record-toggle").count() == expected_records
            for tab_name in ("业务结果", "场景分析", "模型与求解", "量子实验"):
                desktop.get_by_role("tab", name=tab_name).click()
                _assert_page_geometry(desktop)
            desktop.get_by_role("tab", name="场景分析").click()
            assert desktop.get_by_text("已加载的业务场景").is_visible()
            if case_name == "抵押品分配":
                desktop.screenshot(path=SCREENSHOTS / "collateral-scenarios-desktop.png", full_page=True)
            if case_name == "流动性调度":
                desktop.screenshot(path=SCREENSHOTS / "treasury-scenarios-desktop.png", full_page=True)
            if case_name == "授信额度":
                desktop.get_by_role("tab", name="业务结果").click()
                desktop.screenshot(path=SCREENSHOTS / "credit-desktop.png", full_page=True)
            if case_name == "衍生品定价":
                desktop.get_by_role("tab", name="模型与求解").click()
                assert desktop.get_by_text("价格来自经典参考方法").is_visible()
                assert desktop.locator("#view").get_by_text("QUBO").count() == 0
                desktop.get_by_role("tab", name="量子实验").click()
                assert desktop.get_by_text("counts 不参与价格计算").is_visible()
                assert desktop.locator('svg[data-count-total="256"]').count() == 1
                desktop.screenshot(path=SCREENSHOTS / "derivatives-quantum-desktop.png", full_page=True)
                desktop.get_by_role("tab", name="业务结果").click()
                desktop.screenshot(path=SCREENSHOTS / "derivatives-desktop.png", full_page=True)
            desktop.get_by_role("tab", name="审计证据").click()
            _assert_page_geometry(desktop, require_charts=False)

        with desktop.expect_download() as derivative_download_info:
            desktop.get_by_role("button", name="下载原型结果 JSON").click()
        derivative_download = derivative_download_info.value
        assert derivative_download.suggested_filename == "derivatives-prototype-result.json"
        derivative_result = json.loads(Path(derivative_download.path()).read_text())
        assert derivative_result["pricing"]["reference_model"] == "deterministic Monte Carlo"
        assert derivative_result["sampling_experiment"]["purpose"] == "distribution encoding only; not a pricing source"
        assert derivative_result["sampling_experiment"]["full_qae"] is False

        desktop.get_by_role("button", name="调查编排").click()
        desktop.get_by_role("tab", name="审计证据").click()
        with desktop.expect_download() as download_info:
            desktop.get_by_role("button", name="下载原型结果 JSON").click()
        assert download_info.value.suggested_filename == "fraud-prototype-result.json"

        desktop.get_by_role("button", name="Switch language").click()
        assert desktop.get_by_role(
            "heading", name="Fraud review task routing"
        ).is_visible()

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.on("pageerror", lambda error: errors.append(str(error)))
        mobile.goto(PAGE_URI)
        mobile.wait_for_load_state("domcontentloaded")
        _assert_page_geometry(mobile)
        mobile.get_by_role("tab", name="模型与求解").click()
        _assert_page_geometry(mobile)
        mobile.screenshot(path=SCREENSHOTS / "portfolio-mobile.png", full_page=True)
        mobile.get_by_role("button", name="衍生品定价").click()
        mobile.get_by_role("tab", name="量子实验").click()
        _assert_page_geometry(mobile)

        compact = browser.new_page(viewport={"width": 1280, "height": 720})
        compact.on("pageerror", lambda error: errors.append(str(error)))
        compact.goto(PAGE_URI)
        compact.get_by_role("button", name="调查编排").click()
        compact.get_by_role("tab", name="场景分析").click()
        _assert_page_geometry(compact)
        compact.screenshot(path=SCREENSHOTS / "fraud-scenarios-1280.png", full_page=True)

        browser.close()

    assert errors == [], errors
    print("prototype verification passed: 23 presets, 7 cases, 5 tabs, editable data, Hybrid, derivatives pricing, and responsive views")


if __name__ == "__main__":
    main()
