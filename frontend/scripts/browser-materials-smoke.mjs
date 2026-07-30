import { execFileSync } from "node:child_process";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const VIEWPORTS = [
  ["desktop", 1440, 900],
  ["compact", 1280, 720],
  ["mobile", 390, 844],
];

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDir, "../..");
const staticRoot = path.join(projectRoot, "src/cascaqit_finance_demo/static");
const outputDir = path.join(projectRoot, "artifacts/browser-smoke-phase12");
const origin = "http://workbench.local";

const fixtureProgram = String.raw`
import json
from fastapi.testclient import TestClient
from cascaqit_finance_demo.api.app import app

client = TestClient(app)

def get(path):
    response = client.get(path)
    response.raise_for_status()
    return response.json()

def analyze(domain, case_id, preset):
    response = client.post(
        f"/api/domains/{domain}/scenarios/{case_id}/analyze",
        json={"preset": preset, "values": {}},
    )
    response.raise_for_status()
    return response.json()

print(json.dumps({
    "financeScenarios": get("/api/domains/finance/scenarios"),
    "financeAnalysis": analyze("finance", "portfolio", "base"),
    "materialsScenarios": get("/api/domains/materials/scenarios"),
    "materialsAnalysis": {
        "defect_adsorption": analyze(
            "materials", "defect_adsorption", "ceria_vacancy_co"
        ),
        "rydberg_dynamics": analyze(
            "materials", "rydberg_dynamics", "perfect_lattice"
        ),
    },
}, ensure_ascii=False))
`;

const fixtures = JSON.parse(
  execFileSync("python3", ["-c", fixtureProgram], {
    cwd: projectRoot,
    encoding: "utf8",
    env: {
      ...process.env,
      CASCAQIT_INDUSTRY_DATA_DIR: "/tmp/cascaqit-industry-browser-data",
      PYTHONPATH: [
        path.join(projectRoot, "src"),
        path.resolve(projectRoot, "../cascaqit-new/CASCAQit/src"),
      ].join(path.delimiter),
    },
  }),
);

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
};

function jsonBody(value) {
  return {
    body: JSON.stringify(value),
    contentType: "application/json; charset=utf-8",
    status: 200,
  };
}

async function serveWorkbench(route) {
  const request = route.request();
  const url = new URL(request.url());
  const pathname = url.pathname;
  if (pathname === "/api/domains/finance/scenarios") {
    await route.fulfill(jsonBody(fixtures.financeScenarios));
    return;
  }
  if (pathname === "/api/domains/finance/scenarios/portfolio/analyze") {
    await route.fulfill(jsonBody(fixtures.financeAnalysis));
    return;
  }
  if (pathname === "/api/domains/materials/scenarios") {
    await route.fulfill(jsonBody(fixtures.materialsScenarios));
    return;
  }
  const materialMatch = pathname.match(
    /^\/api\/domains\/materials\/scenarios\/([^/]+)\/analyze$/,
  );
  if (materialMatch && fixtures.materialsAnalysis[materialMatch[1]]) {
    await route.fulfill(jsonBody(fixtures.materialsAnalysis[materialMatch[1]]));
    return;
  }
  if (pathname.startsWith("/api/")) {
    await route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
    return;
  }

  const assetPath = pathname.startsWith("/assets/")
    ? path.join(staticRoot, pathname)
    : path.join(staticRoot, "index.html");
  try {
    await route.fulfill({
      body: await readFile(assetPath),
      contentType:
        contentTypes[path.extname(assetPath)] ?? "application/octet-stream",
      status: 200,
    });
  } catch {
    await route.fulfill({ status: 404, body: "Not Found" });
  }
}

async function waitForAnalysis(page) {
  await page.locator(".view-stage").waitFor({ state: "visible" });
  await page.waitForFunction(
    () => document.querySelector(".view-stage")?.getAttribute("aria-busy") === "false",
  );
}

async function layoutSnapshot(page) {
  return page.evaluate(() => {
    const viewportWidth = window.innerWidth;
    const documentWidth = Math.max(
      document.documentElement.scrollWidth,
      document.body.scrollWidth,
    );
    return {
      viewportWidth,
      documentWidth,
      horizontalOverflow: documentWidth > viewportWidth + 1,
      overflowElements: [...document.querySelectorAll("body *")]
        .filter((element) => {
          const rect = element.getBoundingClientRect();
          return rect.right > viewportWidth + 1 || rect.width > viewportWidth + 1;
        })
        .slice(0, 12)
        .map((element) => ({
          tag: element.tagName.toLowerCase(),
          className: element.className?.toString().slice(0, 120) ?? "",
          left: Math.round(element.getBoundingClientRect().left),
          right: Math.round(element.getBoundingClientRect().right),
        })),
    };
  });
}

async function assertNoOverflow(page, label) {
  const snapshot = await layoutSnapshot(page);
  if (snapshot.horizontalOverflow) {
    throw new Error(`${label}: horizontal overflow ${JSON.stringify(snapshot)}`);
  }
  return snapshot;
}

async function assertMarkedSvg(page, selector, label) {
  const svg = page.locator(selector);
  await svg.waitFor({ state: "visible" });
  const marks = await svg.locator("circle, line, path, polyline, polygon, rect").count();
  if (marks === 0) throw new Error(`${label}: SVG contains no visible model marks`);
  const box = await svg.boundingBox();
  if (!box || box.width < 80 || box.height < 80) {
    throw new Error(`${label}: SVG is not meaningfully sized ${JSON.stringify(box)}`);
  }
  return { marks, width: Math.round(box.width), height: Math.round(box.height) };
}

async function exposeControls(page) {
  const runButton = page.locator(".run-button");
  if (!(await runButton.isVisible())) await page.locator(".control-collapse").click();
  return runButton;
}

async function runViewport(browser, name, width, height) {
  const page = await browser.newPage({ viewport: { width, height } });
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.route(`${origin}/**`, serveWorkbench);
  await page.goto(origin, { waitUntil: "networkidle" });
  await page.locator(".app-shell-react").waitFor();
  await page.waitForFunction(() => document.title === "中科酷原行业量子实验台");
  await waitForAnalysis(page);

  const domainSwitch = page.getByRole("group", { name: "行业领域" });
  for (const domain of ["金融", "生物医药", "材料科学"]) {
    if (!(await domainSwitch.getByRole("button", { name: domain }).isVisible())) {
      throw new Error(`${name}: domain switch is missing ${domain}`);
    }
  }
  await domainSwitch.getByRole("button", { name: "材料科学" }).click();
  await page.waitForURL("**/materials/defect_adsorption");
  await waitForAnalysis(page);

  const result = {
    viewport: { width, height },
    defectAdsorption: {
      layout: await assertNoOverflow(page, `${name}/defect-adsorption`),
      lattice: await assertMarkedSvg(
        page,
        ".materials-lattice-svg:visible",
        `${name}/defect-adsorption`,
      ),
    },
  };
  let runButton = await exposeControls(page);
  if (!(await runButton.isDisabled())) {
    throw new Error(`${name}/defect-adsorption: preview run button is enabled`);
  }

  await page.locator(".scenario-item", { hasText: "Rydberg 动力学" }).click();
  await page.waitForURL("**/materials/rydberg_dynamics");
  await waitForAnalysis(page);
  runButton = await exposeControls(page);
  if (!(await runButton.isDisabled())) {
    throw new Error(`${name}/rydberg-dynamics: preview run button is enabled`);
  }
  if ((await page.getByText("数字量子线路", { exact: true }).count()) !== 0) {
    throw new Error(`${name}/rydberg-dynamics: digital circuit leaked into pure Analog`);
  }
  const analogModes = await page.locator(".mode-segments").innerText();
  if (/digital|hybrid/i.test(analogModes)) {
    throw new Error(`${name}/rydberg-dynamics: non-Analog mode is visible`);
  }
  result.rydbergDynamics = {
    layout: await assertNoOverflow(page, `${name}/rydberg-dynamics`),
    materialLattice: await assertMarkedSvg(
      page,
      ".materials-figure-section:not(:has(.rydberg-register-svg)) .materials-lattice-svg",
      `${name}/rydberg-material-lattice`,
    ),
    rydbergRegister: await assertMarkedSvg(
      page,
      ".rydberg-register-svg",
      `${name}/rydberg-register`,
    ),
  };
  await page.screenshot({
    path: path.join(outputDir, `materials-analog-structure-${name}.png`),
    fullPage: true,
  });

  await page.getByRole("tab", { name: "量子实验" }).click();
  result.rydbergDynamics.pulse = await assertMarkedSvg(
    page,
    ".materials-pulse-svg",
    `${name}/rydberg-pulse`,
  );
  result.rydbergDynamics.quantumLayout = await assertNoOverflow(
    page,
    `${name}/rydberg-quantum`,
  );
  if ((await page.getByText("数字量子线路", { exact: true }).count()) !== 0) {
    throw new Error(`${name}/rydberg-quantum: digital circuit leaked into pure Analog`);
  }
  await page.screenshot({
    path: path.join(outputDir, `materials-analog-pulse-${name}.png`),
    fullPage: true,
  });

  await page.getByRole("tab", { name: "领域结果" }).click();
  await page.getByText("ANALOG ONLY", { exact: true }).waitFor();
  result.rydbergDynamics.resultLayout = await assertNoOverflow(
    page,
    `${name}/rydberg-result`,
  );
  result.consoleErrors = consoleErrors;
  result.pageErrors = pageErrors;
  if (consoleErrors.length || pageErrors.length) {
    throw new Error(
      `${name}: browser errors ${JSON.stringify({ consoleErrors, pageErrors })}`,
    );
  }
  await page.close();
  return result;
}

await mkdir(outputDir, { recursive: true });
const report = { origin, viewports: {} };
const browser = await chromium.launch({
  headless: true,
  args: ["--no-proxy-server"],
});
try {
  for (const [name, width, height] of VIEWPORTS) {
    report.viewports[name] = await runViewport(browser, name, width, height);
  }
} finally {
  await browser.close();
}

const reportPath = path.join(outputDir, "report.json");
await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(`materials browser smoke passed: ${reportPath}`);
