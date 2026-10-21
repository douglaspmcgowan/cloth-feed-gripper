// Captures the primary professor flow against the running `npm run serve` instance.
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { tmpdir } from "node:os";
const out = resolve(process.argv[2] || resolve(tmpdir(), "cfg-w5-demo", "after"));
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const results = [];
try {
  for (const scheme of ["light", "dark"]) for (const [width, height] of [[1440,900],[768,1024],[375,812]]) {
    const context = await browser.newContext({ viewport: { width, height }, colorScheme: scheme, reducedMotion: "reduce" });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
    await page.goto("http://127.0.0.1:4173/");
    await page.locator("#facts .chips").waitFor();
    await page.screenshot({ path: resolve(out, `landing-${scheme}-${width}.png`) });
    await page.screenshot({ path: resolve(out, `landing-${scheme}-${width}-full.png`), fullPage: true });
    await page.locator("#start-tour").click();
    await page.locator("#tour-next").click();
    await page.locator("#tour-next").click();
    await page.locator("#tour-panel").screenshot({ path: resolve(out, `tour-${scheme}-${width}.png`) });
    const scroll = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
    await page.locator("#tour-link").click();
    await page.locator("#fit-findings").waitFor();
    await page.screenshot({ path: resolve(out, `review-fit-${scheme}-${width}.png`) });
    await page.locator("#rail .homelink").click();
    await page.locator("#play-explainer").click();
    await page.waitForFunction(() => document.getElementById("explainer").currentTime > .2);
    await page.locator("#explainer").evaluate(v => { v.pause(); v.currentTime = 35; });
    await page.waitForFunction(() => !document.getElementById("explainer").seeking);
    await page.locator(".walkthrough").screenshot({ path: resolve(out, `explainer-${scheme}-${width}.png`) });
    await page.locator("#close-explainer").click();
    results.push({ scheme, width, errors, scroll, primaryFlow: "guide → fit finding → Home → walkthrough → close" });
    await context.close();
  }
} finally { await browser.close(); }
writeFileSync(resolve(out, "flow.json"), JSON.stringify(results, null, 2) + "\n", { encoding: "utf8" });
console.log(JSON.stringify(results));
if (results.some(r => r.errors.length || r.scroll.scroll > r.scroll.width)) process.exitCode = 1;
