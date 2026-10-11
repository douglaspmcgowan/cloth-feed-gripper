// The three real-browser jobs from the brief, run at 375 and 1440 wide, with screenshots.
//   node scripts/jobs.mjs [outDir]       default docs/screens
//   (a) watch the full film to its end, unmuted
//   (b) from the landing page, read which requirements fail
//   (c) reach the servo-horn clearance finding in the review app and get back to the landing page
import { chromium } from "@playwright/test";
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const out = resolve(process.argv[2] || "docs/screens");
mkdirSync(out, { recursive: true });
const port = 4700 + Math.floor(Math.random() * 200);
const server = spawn(process.execPath, ["scripts/serve.mjs", String(port)], { stdio: "ignore" });
await new Promise((r) => setTimeout(r, 800));
const base = `http://127.0.0.1:${port}`;

const browser = await chromium.launch({ args: ["--autoplay-policy=no-user-gesture-required"] });
try {
  for (const [w, h] of [[375, 812], [1440, 900]]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: "light", isMobile: w < 600, hasTouch: w < 600 });
    const page = await ctx.newPage();
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));

    await page.goto(base + "/", { waitUntil: "load" });
    // (a) film
    await page.locator("#play-full").click();
    await page.waitForFunction(() => { const v = document.getElementById("full"); return v.readyState >= 2 && v.currentTime > 0.5; }, null, { timeout: 60_000 });
    await page.waitForTimeout(8000);
    await page.screenshot({ path: `${out}/job-a-film-${w}.png` });
    const t0 = Date.now();
    await page.waitForFunction(() => document.getElementById("full").ended, null, { timeout: 120_000 });
    const film = await page.locator("#full").evaluate((v) => ({ src: v.currentSrc.split("/").pop(), duration: Math.round(v.duration), muted: v.muted, volume: v.volume, ended: v.ended, error: v.error && v.error.code }));
    console.log(w, "(a) film", JSON.stringify(film), "waited", Math.round((Date.now() - t0) / 1000), "s more");

    // (b) failing requirements
    await page.goto(base + "/", { waitUntil: "load" });
    await page.locator("#fails").scrollIntoViewIfNeeded();
    const fails = await page.locator("#fails li").allInnerTexts();
    console.log(w, "(b) failing requirements", JSON.stringify(fails));
    await page.screenshot({ path: `${out}/job-b-fails-${w}.png` });

    // (c) servo-horn clearance finding, then home
    await page.locator("#door-fit").scrollIntoViewIfNeeded();
    await page.locator("#door-fit").click();
    await page.waitForURL("**/review/#fit-findings", { timeout: 120_000 });
    await page.waitForTimeout(1500);
    const horn = await page.locator("#fit-findings").innerText();
    const line = horn.split("\n").filter((l) => /horn/i.test(l)).slice(0, 3);
    console.log(w, "(c) horn lines", JSON.stringify(line));
    await page.locator("#fit-findings").scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${out}/job-c-horn-${w}.png` });
    await page.locator("#rail .homelink").click();
    await page.waitForURL((u) => u.pathname === "/", { timeout: 60_000 });
    console.log(w, "(c) back home, h1:", await page.locator("h1").innerText());
    console.log(w, "console errors:", errors.length ? errors : "none");
    await ctx.close();
  }
} finally {
  await browser.close();
  server.kill();
}
