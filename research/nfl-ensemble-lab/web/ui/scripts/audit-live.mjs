// Screenshots the Live tab with a saved in-progress snapshot (data/cache/live_out.json), for when no game is on: npm run audit:live
// The game list and detail come from the real server; only /api/live/<gid> is served from the saved file and the game is shown as unfinished.
import { chromium } from "playwright";
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const base = process.argv[2] ?? "http://127.0.0.1:8510";
const gid = "2026_08_PHI_WAS";
const saved = readFileSync("../../data/cache/live_out.json", "utf8");
const out = "test-results/audit";
mkdirSync(out, { recursive: true });
const root = join(process.env.LOCALAPPDATA ?? "", "ms-playwright");
const dir = existsSync(root) ? readdirSync(root).filter((d) => d.startsWith("chromium-")).sort().pop() : null;
const exe = dir ? join(root, dir, "chrome-win64", "chrome.exe") : undefined;
const browser = await chromium.launch({ executablePath: exe && existsSync(exe) ? exe : undefined });
for (const [label, viewport] of [["desktop", { width: 1440, height: 1000 }], ["phone", { width: 390, height: 900 }]]) {
  const page = await browser.newPage({ viewport });
  await page.route(`**/api/live/${gid}`, (r) => r.fulfill({ status: 200, contentType: "application/json", body: saved }));
  await page.route(`**/api/game/${gid}`, async (r) => {
    const res = await r.fetch();
    const j = await res.json();
    await r.fulfill({ response: res, json: { ...j, completed: false } });
  });
  await page.goto(base, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.locator("button", { hasText: "PHI" }).first().evaluate((el) => el.click());
  await page.waitForTimeout(1500);
  await page.getByRole("tab", { name: "Live" }).click();
  await page.waitForTimeout(1500);
  const sec = page.locator('section[aria-label="Game state"]');
  await page.screenshot({ path: join(out, `${label}-live-mock.png`), fullPage: true });
  for (const stat of ["Receptions", "Touchdowns"]) {
    await page.getByRole("radio", { name: stat }).click();
    await page.waitForTimeout(700);
    await page.screenshot({ path: join(out, `${label}-live-${stat.toLowerCase()}.png`), fullPage: true });
  }
  console.log(label, "overflowX:", await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), "state section found:", await sec.count());
  await page.close();
}
await browser.close();
