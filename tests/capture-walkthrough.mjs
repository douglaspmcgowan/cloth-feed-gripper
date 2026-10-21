// Reproduce the shipped screen recording. Requires installed Chromium and ffmpeg.
// node tests/capture-walkthrough.mjs <absolute ffmpeg path> [temp output directory]
import { chromium } from "@playwright/test";
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const encoder = process.argv[2];
if (!encoder) throw new Error("Pass an installed ffmpeg executable");
const out = resolve(process.argv[3] || resolve(tmpdir(), "cfg-w5-demo", "recording"));
const media = resolve(root, "public/media");
mkdirSync(out, { recursive: true });
const port = 45132;
const base = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, [resolve(root, "scripts/serve.mjs"), String(port)], { stdio: "ignore", windowsHide: true });
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, colorScheme: "light", reducedMotion: "reduce", recordVideo: { dir: out, size: { width: 1280, height: 720 } } });
const page = await context.newPage();
const video = page.video();
const began = Date.now();
const cues = [];
function cue(text) {
  const now = (Date.now() - began) / 1000;
  if (cues.length) cues[cues.length - 1].end = now;
  cues.push({ start: now, text });
}
try {
  await page.goto(base);
  cue("Cloth-feed gripper: a design for guiding cotton into a sewing machine. Designed and simulated; not built or measured.");
  await page.waitForTimeout(5000);
  await page.locator("#start-tour").click();
  cue("Start the guided tour. Each stop gives you a question to ask and a direct route into the working review.");
  await page.waitForTimeout(6000);
  const captions = [
    ["See the model. Check how the mechanism moves before reading the calculations.", "Orbit the model, move the jaw and explode the parts. This is CAD geometry, not a physical prototype."],
    ["Check the fits. Start with the servo horn clearance finding.", "Read the gap and its method. Manufacturing and assembly still need to confirm these predicted clearances."],
    ["Follow the assembly. A final position does not prove that a part can be installed.", "Inspect the build sequence, insertion directions and tool reach. Pay attention to the at-risk steps."],
    ["Read what is still open. Separate calculated results from measurements.", "Review requirement statuses, unresolved decisions and bench checks. Use these to plan what a first prototype must establish."],
  ];
  for (let index = 0; index < captions.length; index++) {
    if (index > 0) { await page.goto(base); await page.locator("#start-tour").click(); }
    for (let step = 0; step <= index; step++) await page.locator("#tour-next").click();
    cue(captions[index][0]);
    await page.waitForTimeout(4000);
    await page.locator("#tour-link").click();
    await page.waitForFunction(() => document.querySelector(".view:not([hidden])"));
    if (index === 0) {
      await page.waitForFunction(() => window.__v3ready === true);
      await page.getByRole("button", { name: "Explode", exact: true }).click();
    }
    cue(captions[index][1]);
    if (index === 0) await page.screenshot({ path: resolve(out, "poster.png") });
    await page.waitForTimeout(10000);
  }
  await page.goto(base);
  await page.locator("#stands").scrollIntoViewIfNeeded();
  cue("Return to the evidence summary. Follow a failed requirement to its source, or open the remaining work to continue the review yourself.");
  await page.waitForTimeout(5000);
  cues[cues.length - 1].end = (Date.now() - began) / 1000;
} finally {
  await context.close();
  await browser.close();
  server.kill();
}
function stamp(seconds) {
  return new Date(Math.round(seconds * 1000)).toISOString().slice(11, 23);
}
const vtt = "WEBVTT\n\n" + cues.map(c => `${stamp(c.start)} --> ${stamp(c.end)}\n${c.text}\n`).join("\n");
writeFileSync(resolve(media, "review-walkthrough.vtt"), vtt, { encoding: "utf8" });
writeFileSync(resolve(out, "capture.json"), JSON.stringify({ cues, recordedSeconds: cues.at(-1).end }, null, 2) + "\n", { encoding: "utf8" });
const recorded = await video.path();
const encoded = spawnSync(encoder, ["-y", "-i", recorded, "-i", resolve(media, "review-walkthrough.vtt"), "-map", "0:v:0", "-map", "1:0", "-c:v", "libx264", "-preset", "fast", "-crf", "28", "-r", "20", "-pix_fmt", "yuv420p", "-c:s", "mov_text", "-disposition:s:0", "default", "-movflags", "+faststart", resolve(media, "review-walkthrough.mp4")], { stdio: "inherit", windowsHide: true });
if (encoded.status !== 0) throw new Error("Walkthrough encoding failed");
const poster = spawnSync(encoder, ["-y", "-i", resolve(out, "poster.png"), "-frames:v", "1", "-q:v", "5", resolve(media, "review-walkthrough-poster.jpg")], { stdio: "inherit", windowsHide: true });
if (poster.status !== 0) throw new Error("Poster encoding failed");
const bytes = statSync(resolve(media, "review-walkthrough.mp4")).size;
if (bytes >= 15_000_000) throw new Error(`Walkthrough exceeds 15 MB: ${bytes}`);
if (statSync(resolve(media, "review-walkthrough-poster.jpg")).size >= 250_000) throw new Error("Poster exceeds 250 KB");
if (cues.at(-1).end < 60 || cues.at(-1).end > 90) throw new Error("Walkthrough outside 60–90 second budget");
console.log(`walkthrough: ${cues.at(-1).end.toFixed(2)} seconds; ${bytes} bytes; ${recorded}`);
