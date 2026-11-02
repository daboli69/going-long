// Headless visual audit of the running Game Center: npm run audit [baseUrl]
// Renders the main views at desktop and phone width, clicks through the tabs, and records horizontal overflow, console errors, layout shift and
// elements that stick out of the viewport. Screenshots go to test-results/audit/ for review by eye.
import { chromium } from "playwright";
import { existsSync, mkdirSync, writeFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const base = process.argv[2] ?? "http://127.0.0.1:8510";
const out = "test-results/audit";
mkdirSync(out, { recursive: true });

// The Playwright build that npm installed may not match the browser on disk, so use whichever Chromium is there.
const root = join(process.env.LOCALAPPDATA ?? "", "ms-playwright");
const dir = existsSync(root) ? readdirSync(root).filter((d) => d.startsWith("chromium-")).sort().pop() : null;
const exe = dir ? join(root, dir, "chrome-win64", "chrome.exe") : undefined;
const browser = await chromium.launch({ executablePath: exe && existsSync(exe) ? exe : undefined });

const report = [];
for (const [label, viewport] of [["desktop", { width: 1440, height: 900 }], ["phone", { width: 390, height: 844 }]]) {
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && !/404/.test(m.text()) && errors.push(m.text()));
  await page.addInitScript(() => {
    window.__cls = 0;
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: "layout-shift", buffered: true });
  });
  await page.goto(base, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const steps = [
    ["games", async () => {}],
    ["live", async () => { const t = page.getByRole("tab", { name: "Live" }); if (await t.count()) { await t.click(); await page.waitForTimeout(2500); } else { report.push({ view: label, note: "no Live tab (no game in progress)" }); } }],
    ["results", async () => { await page.getByRole("tab", { name: "Results", exact: true }).click(); await page.waitForTimeout(4000); }],
    ["rankings", async () => { await page.getByRole("tab", { name: "Player rankings" }).click(); await page.waitForTimeout(6000); }],
    ["market", async () => { await page.getByRole("tab", { name: "Market value" }).click(); await page.waitForTimeout(4000); }],
  ];
  for (const [name, go] of steps) {
    await go();
    const stats = await page.evaluate(() => {
      const w = document.documentElement.clientWidth;
      const wide = [...document.querySelectorAll("body *")].filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.right > w + 1; }).slice(0, 5).map((el) => el.tagName + "." + String(el.className).slice(0, 60));
      return { overflowX: document.documentElement.scrollWidth > w, scrollWidth: document.documentElement.scrollWidth, clientWidth: w, wide, cls: Number(window.__cls.toFixed(4)) };
    });
    await page.screenshot({ path: join(out, `${label}-${name}.png`), fullPage: false });
    report.push({ view: label, step: name, ...stats });
  }
  report.push({ view: label, errors });
  await page.close();
}
await browser.close();
writeFileSync(join(out, "report.json"), JSON.stringify(report, null, 1));
console.log(JSON.stringify(report, null, 1));
