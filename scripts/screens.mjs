// Screenshots of the landing page and the review app at the three sizes, for inspection and docs.
//
//   node scripts/screens.mjs [outDir] [scheme]     default docs/screens, light
//
// Starts its own static server on a free port (scripts/serve.mjs logic is not reused so this file
// runs alone) and writes landing-<w>.png and review-<w>.png.
import { chromium } from "@playwright/test";
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const out = resolve(process.argv[2] || "docs/screens");
const scheme = process.argv[3] || "light";
const port = 4190 + Math.floor(Math.random() * 500);
mkdirSync(out, { recursive: true });

const server = spawn(process.execPath, ["scripts/serve.mjs", String(port)], { stdio: "ignore" });
await new Promise((r) => setTimeout(r, 800));

const sizes = [
  { w: 1440, h: 900 },
  { w: 768, h: 1024 },
  { w: 375, h: 812 },
];
const browser = await chromium.launch();
try {
  for (const { w, h } of sizes) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, reducedMotion: "no-preference", deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));

    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "load" });
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${out}/landing-${scheme}-${w}.png`, fullPage: false });
    await page.screenshot({ path: `${out}/landing-${scheme}-${w}-full.png`, fullPage: true });

    await page.goto(`http://127.0.0.1:${port}/review/#model`, { waitUntil: "load", timeout: 120_000 });
    await page.waitForTimeout(5000);
    await page.screenshot({ path: `${out}/review-${scheme}-${w}.png`, fullPage: false });
    console.log(w, "console errors:", errors.length ? errors : "none");
    await ctx.close();
  }
} finally {
  await browser.close();
  server.kill();
}
