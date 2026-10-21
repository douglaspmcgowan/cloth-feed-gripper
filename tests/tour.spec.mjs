import { test, expect } from "@playwright/test";
import { noHorizontalScroll, watchErrors } from "./helpers.mjs";

const stops = [
  ["See the model", "#model", "model", "#door-model"],
  ["Check the fits", "#fit-findings", "fit", "#door-fit"],
  ["Follow the assembly", "#assembly", "assembly", "#door-assembly"],
  ["Read what is still open", "#open-requirements", "open", "#door-open"],
];

test("walkthrough assets meet the delivery budget and faststart contract", async ({ request }, info) => {
  test.skip(info.project.name !== "desktop-1440-light", "asset bytes do not depend on viewport");
  const video = await request.get("/media/review-walkthrough.mp4");
  expect(video.status()).toBe(200);
  const bytes = await video.body();
  expect(bytes.length).toBeLessThan(15_000_000);
  expect(bytes.indexOf("moov")).toBeGreaterThan(0);
  expect(bytes.indexOf("moov")).toBeLessThan(bytes.indexOf("mdat"));
  expect(bytes.includes(Buffer.from("avc1"))).toBe(true);
  const poster = await request.get("/media/review-walkthrough-poster.jpg");
  expect(poster.status()).toBe(200);
  expect((await poster.body()).length).toBeLessThan(250_000);
  const captions = await request.get("/media/review-walkthrough.vtt");
  expect(captions.status()).toBe(200);
  expect(await captions.text()).toContain("WEBVTT");
  for (const word of ["model", "fits", "assembly", "open"]) expect(await captions.text()).toContain(word);
});

test("guide opens, walks every door, goes back and finishes with focus restored", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/");
  const start = page.locator("#start-tour");
  await expect(page.locator("#tour-panel")).toBeHidden();
  await start.focus();
  await page.keyboard.press("Enter");
  await expect(start).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#tour-title")).toBeFocused();
  await expect(page.locator("#tour-back")).toBeDisabled();
  for (const [title, hash, , door] of stops) {
    await page.locator("#tour-next").click();
    await expect(page.locator("#tour-title")).toHaveText(title);
    await expect(page.locator("#tour-link")).toHaveAttribute("href", `/review/${hash}`);
    await expect(page.locator(door)).toHaveAttribute("aria-current", "step");
    const { scrollWidth, clientWidth } = await noHorizontalScroll(page);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
  }
  await page.locator("#tour-back").click();
  await expect(page.locator("#tour-title")).toHaveText("Follow the assembly");
  await page.locator("#tour-next").click();
  await page.locator("#tour-next").click();
  await expect(page.locator("#tour-panel")).toBeHidden();
  await expect(start).toBeFocused();
  await expect(page.locator(".door[aria-current]")).toHaveCount(0);
  await start.click();
  await page.keyboard.press("Escape");
  await expect(page.locator("#tour-panel")).toBeHidden();
  await expect(start).toBeFocused();
  expect(errors).toEqual([]);
});

for (let n = 0; n < stops.length; n++) {
  const [title, hash, view] = stops[n];
  test(`tour link reaches ${title}`, async ({ page }) => {
    await page.goto("/");
    await page.locator("#start-tour").click();
    for (let step = 0; step <= n; step++) await page.locator("#tour-next").click();
    await page.locator("#tour-link").click();
    await page.waitForURL(`**/review/${hash}`);
    await expect(page.locator(`.view#${view}`)).toBeVisible();
    await page.locator("#rail .homelink").click();
    await expect(page.locator("#start-tour")).toBeVisible();
  });
}

test("guide and motion preference remain usable when changed at runtime", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const requests = [];
  page.on("request", r => requests.push(r.url()));
  await page.goto("/");
  await page.locator("#start-tour").click();
  await page.locator("#tour-next").click();
  expect(await page.locator("#tour-content").evaluate(e => e.getAnimations().length)).toBe(0);
  expect(await page.locator("#teaser").evaluate(e => e.paused)).toBe(true);
  expect(requests.filter(url => /\.(mp4|webm)(\?|$)/.test(url))).toEqual([]);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.locator("#tour-next").click();
  await expect(page.locator("#tour-title")).toHaveText("Check the fits");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect.poll(() => page.locator("#teaser").evaluate(e => e.paused)).toBe(true);
});

test("explainer and captions download only after play, with native playback and a recovery message", async ({ page }) => {
  const requests = [];
  page.on("request", r => requests.push(new URL(r.url()).pathname));
  await page.goto("/");
  await page.locator("#play-explainer").scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);
  expect(requests.filter(url => /review-walkthrough\.(mp4|vtt)$/.test(url))).toEqual([]);
  await expect(page.locator("#explainer")).not.toHaveAttribute("src", /.+/);
  await page.locator("#play-explainer").click();
  await expect.poll(() => page.locator("#explainer").evaluate(v => v.currentTime)).toBeGreaterThan(0.2);
  const state = await page.locator("#explainer").evaluate(v => ({
    controls: v.controls, duration: v.duration, captions: v.textTracks[0]?.mode,
  }));
  expect(state.controls).toBe(true);
  expect(state.duration).toBeGreaterThanOrEqual(60);
  expect(state.duration).toBeLessThanOrEqual(90);
  expect(state.captions).toBe("showing");
  await page.locator("#close-explainer").click();
  await expect(page.locator("#play-explainer")).toBeFocused();
  expect(await page.locator("#explainer").evaluate(v => v.paused)).toBe(true);
  await page.route("**/media/review-walkthrough.mp4", route => route.abort());
  await page.reload();
  await page.locator("#play-explainer").click();
  await expect(page.locator("#explainer-status")).toContainText("could not be played");
  await expect(page.locator("#start-tour")).toBeEnabled();
});

test("facts failure keeps the guide and direct review routes available", async ({ page }) => {
  await page.route("**/facts.json", route => route.fulfill({ status: 503, body: "unavailable" }));
  await page.goto("/");
  await expect(page.locator("#facts")).toContainText("could not be loaded");
  await page.locator("#start-tour").click();
  await expect(page.locator("#tour-title")).toBeFocused();
  await expect(page.locator("#door-fit")).toHaveAttribute("href", "/review/#fit-findings");
});
