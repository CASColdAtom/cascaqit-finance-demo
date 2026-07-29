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
  ["electronic_structure", "电子结构"],
  ["docking_match", "构象匹配"],
  ["active_center", "金属活性中心"],
  ["peptide_landscape", "小肽能景"],
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

  const result = {
    viewport: { width, height },
    scenarios: {},
  };
  for (const [caseId, shortTitle] of BIOMEDICINE_CASES) {
    if (caseId !== "electronic_structure") {
      await page.locator(".scenario-item", { hasText: shortTitle }).click();
      await page.waitForURL(`**/biomedicine/${caseId}`);
      await waitForAnalysis(page);
    }
    const runButton = page.locator(".run-button");
    const shouldBeDisabled = false;
    if ((await runButton.isDisabled()) !== shouldBeDisabled) {
      throw new Error(`${name}/${caseId}: unexpected run button enabled state`);
    }
    result.scenarios[caseId] = await assertLayout(page, `${name}/${caseId}`);
  }

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
    "CORRELATION / XX",
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

  await page.getByRole("tab", { name: "量子实验" }).click();
  await waitForPaintedCanvas(page, ".peptide-quantum-view canvas");
  result.peptideQuantum = await assertLayout(page, `${name}/peptide-quantum`);

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
  const resultText = await page.locator(".biomed-metric-band").innerText();
  if (!resultText.includes("ABSOLUTE ERROR") || !resultText.includes("mHa")) {
    throw new Error(`${name}: H2 result evidence is incomplete`);
  }
  result.h2Run = await assertLayout(page, `${name}/h2-run`);

  await page.getByRole("tab", { name: "量子实验" }).click();
  await waitForPaintedCanvas(page, ".view-stage canvas");
  const quantum = await assertLayout(page, `${name}/quantum-view`);
  if (!quantum.graphics.some((graphic) => graphic.tag === "canvas" && graphic.marks > 0)) {
    throw new Error(`${name}: quantum view contains no painted canvas`);
  }
  result.quantumView = quantum;

  await page.screenshot({
    path: path.join(outputDir, `biomedicine-${name}.png`),
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
