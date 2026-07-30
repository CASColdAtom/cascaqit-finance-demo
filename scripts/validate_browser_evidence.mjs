import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";

const evidenceDir = path.resolve(
  process.argv[2] ?? "artifacts/browser-smoke-v3",
);
const report = JSON.parse(
  await readFile(path.join(evidenceDir, "report.json"), "utf8"),
);

const expectedViewports = {
  desktop: { width: 1440, height: 900 },
  compact: { width: 1280, height: 720 },
  mobile: { width: 390, height: 844 },
};
const expectedCases = [
  "active_center",
  "docking_match",
  "electronic_structure",
  "peptide_landscape",
  "protein_dynamics",
  "rna_structure",
];
const screenshotPrefixes = [
  "active-center-result",
  "advanced-job",
  "biomedicine",
  "docking-quantum",
  "docking-result",
  "materials-analog",
  "peptide-result",
  "protein-path-result",
  "rna-result",
];
const canvasEvidence = [
  "activeCenterQuantum",
  "dockingQuantum",
  "h2oNoiseQuantum",
  "peptideQuantum",
  "proteinQuantum",
  "quantumView",
  "rnaQuantum",
];

assert.equal(report.schema, "industry.browser-acceptance.v1");
assert.match(report.generatedAt, /^\d{4}-\d{2}-\d{2}T/);
assert.equal(typeof report.revision, "string");
assert.ok(report.revision.length > 0);
assert.equal(report.browser?.name, "chromium");
assert.equal(typeof report.browser?.version, "string");
assert.ok(report.browser.version.length > 0);
assert.deepEqual(
  Object.keys(report.viewports).sort(),
  Object.keys(expectedViewports).sort(),
);

function assertOverflowFree(value, label) {
  if (!value || typeof value !== "object") return;
  if (Object.hasOwn(value, "horizontalOverflow")) {
    assert.equal(value.horizontalOverflow, false, `${label} has horizontal overflow`);
  }
  for (const [key, nested] of Object.entries(value)) {
    assertOverflowFree(nested, `${label}.${key}`);
  }
}

for (const [viewportName, expectedViewport] of Object.entries(expectedViewports)) {
  const viewport = report.viewports[viewportName];
  assert.deepEqual(viewport.viewport, expectedViewport);
  assert.deepEqual(Object.keys(viewport.scenarios).sort(), expectedCases);
  assert.deepEqual(viewport.frontierOutlook, {
    biomedicine: true,
    materials: true,
  });
  assert.deepEqual(viewport.consoleErrors, []);
  assert.deepEqual(viewport.pageErrors, []);
  assert.ok(viewport.materials?.defectAdsorption);
  assert.ok(viewport.materials?.rydbergResult);
  assert.ok(viewport.materials?.rydbergQuantum);
  assertOverflowFree(viewport, viewportName);

  for (const evidenceName of canvasEvidence) {
    const graphics = viewport[evidenceName]?.graphics ?? [];
    assert.ok(
      graphics.some((graphic) => graphic.tag === "canvas" && graphic.marks > 0),
      `${viewportName}.${evidenceName} has no painted canvas evidence`,
    );
  }
  const materialGraphics = viewport.materials.defectQuantum?.graphics ?? [];
  assert.ok(
    materialGraphics.some(
      (graphic) => graphic.tag === "canvas" && graphic.marks > 0,
    ),
    `${viewportName}.materials.defectQuantum has no painted canvas evidence`,
  );

  for (const prefix of screenshotPrefixes) {
    const screenshot = path.join(evidenceDir, `${prefix}-${viewportName}.png`);
    const metadata = await stat(screenshot);
    assert.ok(metadata.size > 1024, `${screenshot} is empty or truncated`);
  }
}

console.log(
  JSON.stringify({
    evidenceDir,
    revision: report.revision,
    browser: report.browser,
    viewportCount: Object.keys(expectedViewports).length,
    scenarioCount: expectedCases.length + 2,
    screenshotCount: screenshotPrefixes.length * Object.keys(expectedViewports).length,
    passed: true,
  }),
);
