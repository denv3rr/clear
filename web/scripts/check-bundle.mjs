import fs from "node:fs";
import path from "node:path";

const assetsDir = path.resolve("dist", "assets");

if (!fs.existsSync(assetsDir)) {
  console.error("Bundle check: dist/assets not found. Run `npm run build` first.");
  process.exit(1);
}

const assets = fs
  .readdirSync(assetsDir, { withFileTypes: true })
  .filter((entry) => entry.isFile())
  .map((entry) => ({
    name: entry.name,
    bytes: fs.statSync(path.join(assetsDir, entry.name)).size,
  }));

const jsAssets = assets
  .filter((asset) => asset.name.endsWith(".js"))
  .sort((left, right) => right.bytes - left.bytes);

const budgets = [
  { label: "initial-shell", pattern: /^index-.*\.js$/, maxBytes: 80 * 1024, failOnExceed: true },
  { label: "react-vendor", pattern: /^react-vendor-.*\.js$/, maxBytes: 90 * 1024, failOnExceed: true },
  { label: "shared-vendor", pattern: /^vendor-.*\.js$/, maxBytes: 800 * 1024, failOnExceed: true },
  { label: "globe-vendor", pattern: /^globe-.*\.js$/, maxBytes: 1000 * 1024, failOnExceed: false },
  { label: "plotly", pattern: /^plotly-.*\.js$/, maxBytes: 5200 * 1024, failOnExceed: false },
];

function formatKiB(bytes) {
  return `${(bytes / 1024).toFixed(1)} KiB`;
}

console.log("Bundle check: top JS assets");
for (const asset of jsAssets.slice(0, 10)) {
  console.log(`- ${asset.name}: ${formatKiB(asset.bytes)}`);
}

let hasFailure = false;

console.log("\nBundle check: budgets");
for (const budget of budgets) {
  const asset = jsAssets.find((entry) => budget.pattern.test(entry.name));
  if (!asset) {
    console.log(`- ${budget.label}: not emitted`);
    continue;
  }
  const ok = asset.bytes <= budget.maxBytes;
  const status = ok ? "ok" : budget.failOnExceed ? "fail" : "warn";
  console.log(
    `- ${budget.label}: ${status} (${formatKiB(asset.bytes)} / ${formatKiB(budget.maxBytes)})`
  );
  if (!ok && budget.failOnExceed) {
    hasFailure = true;
  }
}

if (hasFailure) {
  console.error("\nBundle check failed: one or more hot-path chunks exceeded budget.");
  process.exit(1);
}

console.log("\nBundle check passed.");
