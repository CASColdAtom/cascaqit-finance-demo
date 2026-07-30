import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const VIEWPORTS = [
  ["desktop", 1440, 900],
  ["compact", 1280, 720],
  ["mobile", 390, 844],
];

const BIOMEDICINE_CASES = [
  ["electronic_structure", "电子结构", false],
  ["docking_match", "构象匹配", false],
  ["active_center", "金属活性中心", false],
  ["peptide_landscape", "小肽能景", false],
  ["rna_structure", "RNA 折叠路径", false],
  ["protein_dynamics", "蛋白转变路径", false],
];

function option(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

async function layoutSnapshot(page) {
  return page.evaluate(() => {
    const visible = (element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return (
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        rect.width > 0 &&
        rect.height > 0
      );
    };
    const graphics = [...document.querySelectorAll("svg, canvas")]
      .filter(visible)
      .map((element) => {
        const rect = element.getBoundingClientRect();
        let marks = element.querySelectorAll(
          "circle, line, path, polyline, polygon, rect",
        ).length;
        if (element.tagName === "CANVAS") {
          try {
            const context = element.getContext("2d");
            const pixels = context.getImageData(0, 0, element.width, element.height).data;
            const stride = Math.max(4, Math.floor(pixels.length / (64 * 64 * 4)) * 4);
            marks = 0;
            for (let index = 3; index < pixels.length; index += stride) {
              if (pixels[index] > 0) marks += 1;
            }
          } catch {
            marks = 0;
          }
        }
        return {
          tag: element.tagName.toLowerCase(),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          marks,
        };
      });
    return {
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
      horizontalOverflow:
        Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) >
        window.innerWidth + 1,
      overflowElements: [...document.querySelectorAll("body *")]
        .filter((element) => {
          const rect = element.getBoundingClientRect();
          return rect.right > window.innerWidth + 1 || rect.width > window.innerWidth + 1;
        })
        .slice(0, 12)
        .map((element) => {
          const rect = element.getBoundingClientRect();
          return {
            tag: element.tagName.toLowerCase(),
            className: element.className?.toString().slice(0, 120) ?? "",
            left: Math.round(rect.left),
            right: Math.round(rect.right),
            width: Math.round(rect.width),
          };
        }),
      graphics,
    };
  });
}

async function assertLayout(page, label) {
  const snapshot = await layoutSnapshot(page);
  if (snapshot.horizontalOverflow) {
    throw new Error(
      `${label}: horizontal overflow (${snapshot.documentWidth} > ${snapshot.viewportWidth}) ${JSON.stringify(snapshot.overflowElements)}`,
    );
  }
  const structure = page.locator(".biomed-structure-canvas svg:visible");
  if ((await structure.count()) > 0) {
    const marks = await structure
      .first()
      .locator("circle, line, path, polyline, polygon")
      .count();
    if (marks === 0) throw new Error(`${label}: structure SVG contains no marks`);
  }
  const materialsStructures = page.locator(".materials-lattice-svg:visible");
  for (let index = 0; index < (await materialsStructures.count()); index += 1) {
    const marks = await materialsStructures
      .nth(index)
      .locator("circle, line, path, polyline, polygon, rect")
      .count();
    if (marks === 0) {
      throw new Error(`${label}: materials SVG ${index + 1} contains no marks`);
    }
  }
  return snapshot;
}

async function waitForPaintedCanvas(page, selector) {
  await page.locator(selector).first().waitFor({ timeout: 20_000 });
  await page.waitForFunction(
    (canvasSelector) =>
      [...document.querySelectorAll(canvasSelector)].some((element) => {
        if (!(element instanceof HTMLCanvasElement)) return false;
        const context = element.getContext("2d");
        if (!context || !element.width || !element.height) return false;
        const pixels = context.getImageData(0, 0, element.width, element.height).data;
        const stride = Math.max(4, Math.floor(pixels.length / (64 * 64 * 4)) * 4);
        for (let index = 3; index < pixels.length; index += stride) {
          if (pixels[index] > 0) return true;
        }
        return false;
      }),
    selector,
    { timeout: 20_000 },
  );
}

async function waitForAnalysis(page) {
  await page.locator(".view-stage").waitFor({ state: "visible" });
  await page.waitForFunction(
    () => document.querySelector(".view-stage")?.getAttribute("aria-busy") === "false",
  );
}

async function selectBiomedicine(page) {
  await page
    .getByRole("group", { name: "行业领域" })
    .getByRole("button", { name: "生物医药" })
    .click();
  await page.waitForURL("**/biomedicine/electronic_structure");
  await waitForAnalysis(page);
}

async function selectMaterials(page) {
  await page
    .getByRole("group", { name: "行业领域" })
    .getByRole("button", { name: "材料科学" })
    .click();
  await page.waitForURL("**/materials/defect_adsorption");
  await waitForAnalysis(page);
}

async function runViewport(browser, baseUrl, outputDir, name, width, height) {
  const page = await browser.newPage({ viewport: { width, height } });
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.locator(".app-shell-react").waitFor();
  await page.waitForFunction(() => document.title === "中科酷原行业量子实验台");
  await selectBiomedicine(page);
  for (const boundary of [
    "LOCAL SIMULATION",
    "NO HARDWARE EXECUTION",
    "RESEARCH DEMONSTRATION",
  ]) {
    if (!(await page.getByText(boundary, { exact: true }).isVisible())) {
      throw new Error(`${name}: global execution boundary is missing ${boundary}`);
    }
  }
  if (!(await page.getByRole("tab", { name: "对照分析" }).isVisible())) {
    throw new Error(`${name}: biomedicine comparison tab is missing`);
  }

  const result = {
    viewport: { width, height },
    scenarios: {},
  };
  for (const [caseId, shortTitle, previewOnly] of BIOMEDICINE_CASES) {
    if (caseId !== "electronic_structure") {
      await page.locator(".scenario-item", { hasText: shortTitle }).click();
      await page.waitForURL(`**/biomedicine/${caseId}`);
      await waitForAnalysis(page);
    }
    const runButton = page.locator(".run-button");
    const shouldBeDisabled = previewOnly;
    if ((await runButton.isDisabled()) !== shouldBeDisabled) {
      throw new Error(`${name}/${caseId}: unexpected run button enabled state`);
    }
    result.scenarios[caseId] = await assertLayout(page, `${name}/${caseId}`);
  }

  await page.locator(".scenario-item", { hasText: "金属活性中心" }).click();
  await page.waitForURL("**/biomedicine/active_center");
  await waitForAnalysis(page);
  if (!(await page.locator(".run-button").isVisible())) {
    await page.locator(".control-collapse").click();
  }
  await page.getByLabel("参数预设").selectOption("trinuclear_frustrated");
  await page.getByLabel("实验级别").selectOption("advanced");
  await page.getByText("RUN UNITS").waitFor({ timeout: 20_000 });
  await page.locator(".run-button").click();
  await page.getByRole("heading", { name: "高级实验运行单元" }).waitFor();
  await page.getByText("SUCCEEDED", { exact: true }).waitFor({ timeout: 90_000 });
  result.advancedJob = await assertLayout(page, `${name}/advanced-job`);
  await page.screenshot({
    path: path.join(outputDir, `advanced-job-${name}.png`),
    fullPage: true,
  });
  await page.getByLabel("实验级别").selectOption("standard");
  await page.getByLabel("参数预设").selectOption("antiferromagnetic");
  await waitForAnalysis(page);

  await page.locator(".scenario-item", { hasText: "构象匹配" }).click();
  await page.waitForURL("**/biomedicine/docking_match");
  await waitForAnalysis(page);
  if (!(await page.locator(".run-button").isVisible())) {
    await page.locator(".control-collapse").click();
  }
  await page.locator(".run-button").click();
  await page.locator(".docking-solution-grid").waitFor({ timeout: 60_000 });
  await page.waitForFunction(
    () => document.querySelector(".view-stage")?.getAttribute("aria-busy") === "false",
    undefined,
    { timeout: 60_000 },
  );
  const dockingText = await page.locator(".docking-result-view").innerText();
  for (const expected of ["QUANTUM FEASIBLE", "量子观测候选", "经典枚举最优", "共晶派生参考"]) {
    if (!dockingText.includes(expected)) {
      throw new Error(`${name}: docking result is missing ${expected}`);
    }
  }
  result.dockingRun = await assertLayout(page, `${name}/docking-run`);
  await page.screenshot({
    path: path.join(outputDir, `docking-result-${name}.png`),
    fullPage: true,
  });

  await page.getByRole("tab", { name: "对照分析" }).click();
  await page.getByRole("heading", { name: "构象匹配三方对照" }).waitFor();
  result.dockingComparison = await assertLayout(page, `${name}/docking-comparison`);

  await page.getByRole("tab", { name: "量子实验" }).click();
  await waitForPaintedCanvas(page, ".docking-quantum-view canvas");
  const dockingQuantum = await assertLayout(page, `${name}/docking-quantum`);
  if (!dockingQuantum.graphics.some((graphic) => graphic.tag === "canvas" && graphic.marks > 0)) {
    throw new Error(`${name}: docking quantum view contains no painted canvas`);
  }
  result.dockingQuantum = dockingQuantum;
  await page.screenshot({
    path: path.join(outputDir, `docking-quantum-${name}.png`),
    fullPage: true,
  });

  await page.locator(".scenario-item", { hasText: "金属活性中心" }).click();
  await page.waitForURL("**/biomedicine/active_center");
  await waitForAnalysis(page);
  if (!(await page.locator(".run-button").isVisible())) {
    await page.locator(".control-collapse").click();
  }
  await page.locator(".run-button").click();
  await page.locator(".active-center-result-view").waitFor({ timeout: 60_000 });
  await page.waitForFunction(
    () => document.querySelector(".view-stage")?.getAttribute("aria-busy") === "false",
    undefined,
    { timeout: 60_000 },
  );
  const activeCenterText = await page.locator(".active-center-result-view").innerText();
  for (const expected of [
    "HAMILTONIAN IDENTITY",
    "MATCH",
    "局域磁化与两点自旋关联",
    "总磁化扇区占据",
  ]) {
    if (!activeCenterText.includes(expected)) {
      throw new Error(`${name}: active-center result is missing ${expected}`);
    }
  }
  result.activeCenterRun = await assertLayout(page, `${name}/active-center-run`);
  await page.screenshot({
    path: path.join(outputDir, `active-center-result-${name}.png`),
    fullPage: true,
  });

  await page.getByRole("tab", { name: "对照分析" }).click();
  await page.getByRole("heading", { name: "有效自旋 Hamiltonian 对照" }).waitFor();
  result.activeCenterComparison = await assertLayout(
    page,
    `${name}/active-center-comparison`,
  );

  await page.getByRole("tab", { name: "量子实验" }).click();
  await waitForPaintedCanvas(page, ".view-stage canvas");
  const activeCenterQuantum = await assertLayout(
    page,
    `${name}/active-center-quantum`,
  );
  if (
    !activeCenterQuantum.graphics.some(
      (graphic) => graphic.tag === "canvas" && graphic.marks > 0,
    )
  ) {
    throw new Error(`${name}: active-center quantum view contains no painted canvas`);
  }
  result.activeCenterQuantum = activeCenterQuantum;

  await page.locator(".scenario-item", { hasText: "小肽能景" }).click();
  await page.waitForURL("**/biomedicine/peptide_landscape");
  await waitForAnalysis(page);
  if (!(await page.locator(".run-button").isVisible())) {
    await page.locator(".control-collapse").click();
  }
  await page.locator(".run-button").click();
  await page.locator(".peptide-result-view").waitFor({ timeout: 60_000 });
  await page.waitForFunction(
    () => document.querySelector(".view-stage")?.getAttribute("aria-busy") === "false",
    undefined,
    { timeout: 60_000 },
  );
  const peptideText = await page.locator(".peptide-result-view").innerText();
  for (const expected of ["QUANTUM CANDIDATE", "COMPLETE CLASSIC LANDSCAPE", "c00"]) {
    if (!peptideText.includes(expected)) {
      throw new Error(`${name}: peptide result is missing ${expected}`);
    }
  }
  result.peptideRun = await assertLayout(page, `${name}/peptide-run`);
  await page.screenshot({
    path: path.join(outputDir, `peptide-result-${name}.png`),
    fullPage: true,
  });

  await page.getByRole("tab", { name: "对照分析" }).click();
  await page.getByRole("heading", { name: "小肽候选与完整能景对照" }).waitFor();
  result.peptideComparison = await assertLayout(page, `${name}/peptide-comparison`);

  await page.getByRole("tab", { name: "量子实验" }).click();
  await waitForPaintedCanvas(page, ".peptide-quantum-view canvas");
  result.peptideQuantum = await assertLayout(page, `${name}/peptide-quantum`);

  await page.locator(".scenario-item", { hasText: "RNA 折叠路径" }).click();
  await page.waitForURL("**/biomedicine/rna_structure");
  await waitForAnalysis(page);
  if (!(await page.locator(".run-button").isVisible())) {
    await page.locator(".control-collapse").click();
  }
  const referenceArc = page.locator(".rna-analysis-view .rna-arc-diagram svg");
  if ((await referenceArc.locator("path.rna-pair-arc").count()) === 0) {
    throw new Error(`${name}: RNA analysis contains no pairing arcs`);
  }
  await page.locator(".run-button").click();
  await page.locator(".rna-result-view").waitFor({ timeout: 60_000 });
  await page.waitForFunction(
    () => document.querySelector(".view-stage")?.getAttribute("aria-busy") === "false",
    undefined,
    { timeout: 60_000 },
  );
  const rnaText = await page.locator(".rna-result-view").innerText();
  for (const expected of [
    "QUANTUM OBSERVED",
    "量子观测候选",
    "经典精确枚举",
    "数据集参考结构",
    "不是热力学概率或碱基配对概率",
  ]) {
    if (!rnaText.includes(expected)) {
      throw new Error(`${name}: RNA result is missing ${expected}`);
    }
  }
  result.rnaRun = await assertLayout(page, `${name}/rna-run`);
  await page.screenshot({
    path: path.join(outputDir, `rna-result-${name}.png`),
    fullPage: true,
  });

  await page.getByRole("tab", { name: "对照分析" }).click();
  await page.getByRole("heading", { name: "RNA 二级结构四方对照" }).waitFor();
  result.rnaComparison = await assertLayout(page, `${name}/rna-comparison`);

  await page.getByRole("tab", { name: "量子实验" }).click();
  await waitForPaintedCanvas(page, ".rna-quantum-view canvas");
  result.rnaQuantum = await assertLayout(page, `${name}/rna-quantum`);

  await page.locator(".scenario-item", { hasText: "蛋白转变路径" }).click();
  await page.waitForURL("**/biomedicine/protein_dynamics");
  await waitForAnalysis(page);
  if (!(await page.locator(".run-button").isVisible())) {
    await page.locator(".control-collapse").click();
  }
  const proteinNetwork = page.locator(".protein-analysis-view .protein-network svg");
  if ((await proteinNetwork.locator(".protein-state circle").count()) < 4) {
    throw new Error(`${name}: protein analysis contains too few state nodes`);
  }
  if ((await proteinNetwork.locator('.protein-transition[data-active="true"] line').count()) < 2) {
    throw new Error(`${name}: protein analysis contains no active transition subgraph`);
  }
  await page.locator(".run-button").click();
  await page.locator(".protein-result-view").waitFor({ timeout: 60_000 });
  await page.waitForFunction(
    () => document.querySelector(".view-stage")?.getAttribute("aria-busy") === "false",
    undefined,
    { timeout: 60_000 },
  );
  const proteinText = await page.locator(".protein-result-view").innerText();
  for (const expected of [
    "QUANTUM PATH",
    "量子观测候选",
    "经典完整网络基线",
    "不表示真实时间",
  ]) {
    if (!proteinText.includes(expected)) {
      throw new Error(`${name}: protein result is missing ${expected}`);
    }
  }
  result.proteinRun = await assertLayout(page, `${name}/protein-run`);
  await page.screenshot({
    path: path.join(outputDir, `protein-path-result-${name}.png`),
    fullPage: true,
  });

  await page.getByRole("tab", { name: "对照分析" }).click();
  await page.getByRole("heading", { name: "构象转变路径三方对照" }).waitFor();
  result.proteinComparison = await assertLayout(page, `${name}/protein-comparison`);

  await page.getByRole("tab", { name: "量子实验" }).click();
  await waitForPaintedCanvas(page, ".protein-quantum-view canvas");
  result.proteinQuantum = await assertLayout(page, `${name}/protein-quantum`);

  await page.locator(".scenario-item", { hasText: "电子结构" }).click();
  await page.waitForURL("**/biomedicine/electronic_structure");
  await waitForAnalysis(page);
  if (!(await page.locator(".run-button").isVisible())) {
    await page.locator(".control-collapse").click();
  }
  await page.locator(".run-button").click();
  await page.locator(".biomed-metric-band").waitFor({ timeout: 60_000 });
  await page.waitForFunction(
    () => document.querySelector(".view-stage")?.getAttribute("aria-busy") === "false",
    undefined,
    { timeout: 60_000 },
  );
  const resultText = await page.locator(".biomed-view").innerText();
  if (!resultText.includes("ABSOLUTE ERROR") || !resultText.includes("≤ 1.6 MHA")) {
    throw new Error(`${name}: H2 result evidence is incomplete: ${resultText}`);
  }
  result.h2Run = await assertLayout(page, `${name}/h2-run`);

  await page.getByRole("tab", { name: "对照分析" }).click();
  await page.getByRole("heading", { name: "小分子基态能量对照" }).waitFor();
  result.electronicComparison = await assertLayout(
    page,
    `${name}/electronic-comparison`,
  );

  await page.getByRole("tab", { name: "量子实验" }).click();
  await waitForPaintedCanvas(page, ".view-stage canvas");
  const quantum = await assertLayout(page, `${name}/quantum-view`);
  if (!quantum.graphics.some((graphic) => graphic.tag === "canvas" && graphic.marks > 0)) {
    throw new Error(`${name}: quantum view contains no painted canvas`);
  }
  result.quantumView = quantum;

  await page.locator(".preset-field select").selectOption("lih_active_space");
  await waitForAnalysis(page);
  if ((await page.getByLabel("分子与几何").inputValue()) !== "lih_sto3g_1600") {
    throw new Error(`${name}: LiH preset did not resolve its packaged dataset`);
  }
  await page.locator(".run-button").click();
  await page.getByText("LiH / VQE OBJECTIVE").waitFor({ timeout: 60_000 });
  await page.waitForFunction(
    () => document.querySelector(".view-stage")?.getAttribute("aria-busy") === "false",
    undefined,
    { timeout: 60_000 },
  );
  const lihText = await page.locator(".biomed-view").innerText();
  if (!lihText.includes("ERROR REPORTED")) {
    throw new Error(`${name}: LiH must report error without an accuracy claim`);
  }
  result.lihRun = await assertLayout(page, `${name}/lih-run`);

  await page.locator(".preset-field select").selectOption("h2o_minimal");
  await waitForAnalysis(page);
  if ((await page.getByLabel("分子与几何").inputValue()) !== "h2o_sto3g_equilibrium") {
    throw new Error(`${name}: H2O preset did not resolve its packaged dataset`);
  }
  await page.getByLabel("测量模型").selectOption("readout_demo");
  await waitForAnalysis(page);
  await page.locator(".run-button").click();
  await page.getByText("H2O / VQE OBJECTIVE").waitFor({ timeout: 60_000 });
  await page.getByText("READOUT-NOISE QWC", { exact: true }).first().waitFor({ timeout: 60_000 });
  await page.waitForFunction(
    () => document.querySelector(".view-stage")?.getAttribute("aria-busy") === "false",
    undefined,
    { timeout: 60_000 },
  );
  result.h2oNoiseRun = await assertLayout(page, `${name}/h2o-noise-run`);
  await page.getByRole("tab", { name: "量子实验" }).click();
  await page.getByText("READOUT NOISE", { exact: true }).first().waitFor({ timeout: 20_000 });
  await waitForPaintedCanvas(page, ".view-stage canvas");
  result.h2oNoiseQuantum = await assertLayout(page, `${name}/h2o-noise-quantum`);

  await page.screenshot({
    path: path.join(outputDir, `biomedicine-${name}.png`),
    fullPage: true,
  });

  await selectMaterials(page);
  result.materials = {
    defectAdsorption: await assertLayout(page, `${name}/defect-adsorption`),
  };
  let runButton = page.locator(".run-button");
  if (!(await runButton.isVisible())) {
    await page.locator(".control-collapse").click();
  }
  if (await runButton.isDisabled()) {
    throw new Error(`${name}/defect-adsorption: available run button is disabled`);
  }
  await runButton.click();
  await page.getByText("QUANTUM OBSERVED", { exact: true }).waitFor({
    timeout: 60_000,
  });
  await page.waitForFunction(
    () => document.querySelector(".view-stage")?.getAttribute("aria-busy") === "false",
    undefined,
    { timeout: 60_000 },
  );
  result.materials.defectResult = await assertLayout(
    page,
    `${name}/defect-adsorption-result`,
  );
  await page.getByRole("tab", { name: "量子实验" }).click();
  await page.getByText("构型位串 counts", { exact: true }).waitFor();
  await waitForPaintedCanvas(page, ".view-stage canvas");
  result.materials.defectQuantum = await assertLayout(
    page,
    `${name}/defect-adsorption-quantum`,
  );
  await page.getByRole("tab", { name: "对照分析" }).click();
  await page.getByText("EXACT ENUMERATION", { exact: true }).waitFor();
  await page.getByText("OFFLINE REFERENCE", { exact: true }).waitFor();
  result.materials.defectComparison = await assertLayout(
    page,
    `${name}/defect-adsorption-comparison`,
  );

  await page.locator(".scenario-item", { hasText: "Rydberg 动力学" }).click();
  await page.waitForURL("**/materials/rydberg_dynamics");
  await waitForAnalysis(page);
  runButton = page.locator(".run-button");
  if (!(await runButton.isVisible())) {
    await page.locator(".control-collapse").click();
  }
  if (await runButton.isDisabled()) {
    throw new Error(`${name}/rydberg-dynamics: available run button is disabled`);
  }
  const analogSnapshot = await assertLayout(page, `${name}/rydberg-dynamics`);
  if ((await page.locator(".rydberg-register-svg:visible").count()) !== 1) {
    throw new Error(`${name}/rydberg-dynamics: separate Rydberg register is missing`);
  }
  if ((await page.getByText("数字量子线路", { exact: true }).count()) !== 0) {
    throw new Error(`${name}/rydberg-dynamics: digital circuit leaked into pure Analog`);
  }
  const analogModes = await page.locator(".mode-segments").innerText();
  if (/digital|hybrid/i.test(analogModes)) {
    throw new Error(`${name}/rydberg-dynamics: non-Analog mode is visible`);
  }
  await runButton.click();
  await page.getByText("AHS COMPLETED", { exact: true }).waitFor({ timeout: 90_000 });
  await page.waitForFunction(
    () => document.querySelector(".view-stage")?.getAttribute("aria-busy") === "false",
    undefined,
    { timeout: 90_000 },
  );
  result.materials.rydbergResult = await assertLayout(
    page,
    `${name}/rydberg-dynamics-result`,
  );
  await page.getByRole("tab", { name: "量子实验" }).click();
  await page.getByText("终态位串 counts", { exact: true }).waitFor();
  await page.locator(".analog-dynamics-svg:visible").waitFor();
  result.materials.rydbergQuantum = await assertLayout(
    page,
    `${name}/rydberg-dynamics-quantum`,
  );
  if ((await page.getByText("数字量子线路", { exact: true }).count()) !== 0) {
    throw new Error(`${name}/rydberg-dynamics: digital circuit leaked after run`);
  }
  await page.getByRole("tab", { name: "对照分析" }).click();
  await page.getByText("AHS RK4 与 DOP853 对照", { exact: true }).waitFor();
  result.materials.rydbergComparison = await assertLayout(
    page,
    `${name}/rydberg-dynamics-comparison`,
  );
  result.materials.rydbergDynamics = analogSnapshot;
  await page.screenshot({
    path: path.join(outputDir, `materials-analog-${name}.png`),
    fullPage: true,
  });

  result.consoleErrors = consoleErrors;
  result.pageErrors = pageErrors;
  if (consoleErrors.length || pageErrors.length) {
    throw new Error(
      `${name}: browser errors: ${JSON.stringify({ consoleErrors, pageErrors })}`,
    );
  }
  await page.close();
  return result;
}

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const baseUrl = option("--base-url", "http://127.0.0.1:5173/");
const outputDir = path.resolve(
  option("--output-dir", path.join(scriptDir, "../../artifacts/browser-smoke")),
);
await mkdir(outputDir, { recursive: true });

const report = { baseUrl, viewports: {} };
const browser = await chromium.launch({
  headless: true,
  args: ["--no-proxy-server"],
});
try {
  for (const [name, width, height] of VIEWPORTS) {
    report.viewports[name] = await runViewport(
      browser,
      baseUrl,
      outputDir,
      name,
      width,
      height,
    );
  }
} finally {
  await browser.close();
}

const reportPath = path.join(outputDir, "report.json");
await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(`browser smoke passed: ${reportPath}`);
