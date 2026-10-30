// Takes screenshots of the running Game Center so the layout can be checked by eye: npm run shots [baseUrl]
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const base = process.argv[2] ?? "http://127.0.0.1:8510";
mkdirSync("test-results", { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
await page.goto(base, { waitUntil: "networkidle" });
await page.waitForSelector("text=Who is likely to win?", { timeout: 15000 }).catch(() => {});
await page.waitForTimeout(800);
await page.screenshot({ path: "test-results/overview.png", fullPage: true });
for (const [tab, file] of [["Team matchup", "matchup"], ["Player props", "props"], ["Spread & total", "spread"], ["How to read this", "guide"]]) {
  await page.getByRole("tab", { name: tab }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `test-results/${file}.png`, fullPage: true });
}
await page.setViewportSize({ width: 420, height: 900 });
await page.getByRole("tab", { name: "Overview" }).click();
await page.waitForTimeout(500);
await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
await browser.close();
console.log(errors.length ? "BROWSER ERRORS:\n" + errors.join("\n") : "no browser errors");
