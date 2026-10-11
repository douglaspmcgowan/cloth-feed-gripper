import { test, expect } from "@playwright/test";
import { readJson, MOJIBAKE, watchErrors, noHorizontalScroll, backgroundLuminance } from "./helpers.mjs";

const facts = readJson("public/facts.json");
const site = readJson("site.config.json");

test.describe("landing page", () => {
  test("loads with no console errors, no sideways scroll and no mojibake", async ({ page }) => {
    const errors = watchErrors(page);
    await page.goto("/");
    await expect(page.locator("h1")).toBeVisible();
    await expect(page.locator("#facts .chips")).toBeVisible();
    await page.waitForLoadState("networkidle");

    const { scrollWidth, clientWidth } = await noHorizontalScroll(page);
    expect(scrollWidth, "page scrolls sideways").toBeLessThanOrEqual(clientWidth);

    const text = await page.evaluate(() => document.body.innerText);
    expect(text).not.toMatch(MOJIBAKE);
    expect(errors).toEqual([]);
  });

  test("follows the colour scheme", async ({ page }, info) => {
    await page.goto("/");
    const dark = info.project.name.endsWith("dark");
    const lum = await backgroundLuminance(page);
    if (dark) expect(lum).toBeLessThan(0.1);
    else expect(lum).toBeGreaterThan(0.6);
  });

  test("uses the review app's own palette tokens", async ({ page }) => {
    const read = () =>
      page.evaluate(() => {
        const s = getComputedStyle(document.documentElement);
        return ["--accent", "--bg", "--ink", "--surface", "--line"].map((k) => s.getPropertyValue(k).trim());
      });
    await page.goto("/");
    const landing = await read();
    await page.goto("/review/");
    const review = await read();
    expect(landing).toEqual(review);
    expect(landing.every(Boolean)).toBe(true);
  });

  test("hero poster shows, and nothing heavy loads before it is asked for", async ({ page }) => {
    const requested = [];
    page.on("request", (r) => requested.push(new URL(r.url()).pathname));
    await page.goto("/");
    const poster = await page.locator("#teaser").evaluate(
      (v) =>
        new Promise((resolve) => {
          const img = new Image();
          img.onload = () => resolve({ src: v.poster, w: img.naturalWidth, h: img.naturalHeight });
          img.onerror = () => resolve({ src: v.poster, w: 0, h: 0 });
          img.src = v.poster;
        }),
    );
    expect(poster.src).toContain("/media/poster.webp");
    expect(poster.w).toBeGreaterThan(0);
    const box = await page.locator("#teaser").boundingBox();
    expect(box.width).toBeGreaterThan(200);
    await page.waitForTimeout(1500);
    expect(requested.filter((p) => /gripper_hype/.test(p)), "full film fetched before play").toEqual([]);
  });

  test("the teaser loops muted without a click", async ({ page }) => {
    await page.goto("/");
    await page.waitForFunction(() => {
      const v = document.getElementById("teaser");
      return v.readyState >= 2 && v.currentTime > 0.2;
    });
    const v = await page.locator("#teaser").evaluate((e) => ({ muted: e.muted, loop: e.loop, inline: e.playsInline }));
    expect(v).toEqual({ muted: true, loop: true, inline: true });
  });

  test("the play control plays the full film with sound, in the cut that fits the screen", async ({ page }) => {
    const requested = [];
    page.on("request", (r) => requested.push(new URL(r.url()).pathname));
    await page.goto("/");
    const portraitPhone = await page.evaluate(() => matchMedia("(max-width: 600px) and (orientation: portrait)").matches);

    await page.locator("#play-full").click();
    await page.waitForFunction(() => {
      const v = document.getElementById("full");
      return !v.hidden && v.readyState >= 2 && v.currentTime > 0.3;
    });
    const first = await page.locator("#full").evaluate((v) => v.currentTime);
    await page.waitForTimeout(800);
    const state = await page.locator("#full").evaluate((v) => ({ t: v.currentTime, muted: v.muted, volume: v.volume, controls: v.controls, paused: v.paused, src: v.currentSrc }));
    expect(state.t).toBeGreaterThan(first);
    expect(state.paused).toBe(false);
    expect(state.controls).toBe(true);
    expect(state.muted).toBe(false);
    expect(state.volume).toBeGreaterThan(0);
    expect(state.src).toContain(portraitPhone ? "gripper_hype_vertical.mp4" : "gripper_hype_1080p.mp4");
    expect(requested.some((p) => p.includes(portraitPhone ? "gripper_hype_1080p" : "gripper_hype_vertical"))).toBe(false);

    await page.locator("#film-back").click();
    await expect(page.locator("#teaser")).toBeVisible();
    await expect(page.locator("#full")).toBeHidden();
  });

  test("states plainly that the design is unbuilt", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#stands")).toContainText("has not been built");
    await expect(page.locator("h1")).toContainText("gripper");
  });

  test("every figure shown is the figure in facts.json", async ({ page }) => {
    await page.goto("/");
    const text = (key) => page.locator(`[data-fact="${key}"]`).innerText();
    await expect(page.locator('[data-fact="requirements.total"]')).toHaveText(String(facts.requirements.total));
    for (const status of ["pass", "risk", "open", "fail"]) {
      expect(await text(`requirements.counts.${status}`)).toBe(String(facts.requirements.counts[status]));
    }
    expect(await text("decisions.total")).toBe(String(facts.decisions.total));
    expect(await text("bench_checks.total")).toBe(String(facts.bench_checks.total));

    const failing = facts.requirements.items.filter((i) => i.status === "fail");
    await expect(page.locator("#fails li")).toHaveCount(failing.length);
    for (const item of failing) await expect(page.locator("#fails")).toContainText(item.name);
    await expect(page.locator("#provenance")).toContainText(facts.source.commit.slice(0, 7));
  });

  test("credits name every third-party asset and serve its licence", async ({ page, request }) => {
    await page.goto("/");
    const credits = page.locator("#credits");
    for (const name of ["SO-ARM100", "Apache", "Archivo", "Public Sans", "three.js", "MIT"]) await expect(credits).toContainText(name);
    for (const href of ["/licenses/so101-apache-2.0.txt", "/licenses/archivo-ofl.txt"]) {
      const res = await request.get(href);
      expect(res.status(), href).toBe(200);
      expect((await res.text()).length).toBeGreaterThan(1000);
    }
    await expect(page.locator("#build-log")).toHaveAttribute("href", "https://build-log-eight.vercel.app/log/gripper-2026-09-22/");
  });

  test("canonical and social tags use the configured address", async ({ page }) => {
    await page.goto("/");
    const attr = (sel, name) => page.locator(sel).getAttribute(name);
    expect(await attr('link[rel="canonical"]', "href")).toBe(`${site.siteUrl}/`);
    expect(await attr('meta[property="og:url"]', "content")).toBe(`${site.siteUrl}/`);
    expect(await attr('meta[property="og:image"]', "content")).toBe(`${site.siteUrl}/media/og.jpg`);
    expect(await attr('meta[name="twitter:card"]', "content")).toBe("summary_large_image");
    expect(await page.locator('meta[name="theme-color"]').count()).toBe(2);
    expect(await attr('meta[name="viewport"]', "content")).toContain("viewport-fit=cover");
  });

  test("the og image is 1200 by 630", async ({ request }) => {
    const res = await request.get("/media/og.jpg");
    expect(res.status()).toBe(200);
    const buf = await res.body();
    // JPEG: find the first start-of-frame marker and read height and width.
    let i = 2;
    while (i < buf.length) {
      if (buf[i] !== 0xff) break;
      const marker = buf[i + 1];
      const len = buf.readUInt16BE(i + 2);
      if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) {
        expect({ h: buf.readUInt16BE(i + 5), w: buf.readUInt16BE(i + 7) }).toEqual({ h: 630, w: 1200 });
        return;
      }
      i += 2 + len;
    }
    throw new Error("no JPEG frame header found");
  });
});

test.describe("reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("shows the poster only: no teaser download, no playback", async ({ page }) => {
    const requested = [];
    page.on("request", (r) => requested.push(new URL(r.url()).pathname));
    await page.goto("/");
    await page.waitForTimeout(1500);
    const v = await page.locator("#teaser").evaluate((e) => ({ paused: e.paused, t: e.currentTime, poster: e.poster }));
    expect(v.paused).toBe(true);
    expect(v.t).toBe(0);
    expect(v.poster).toContain("/media/poster.webp");
    expect(requested.filter((p) => /\.mp4$/.test(p))).toEqual([]);
    await expect(page.locator("#play-full")).toBeVisible();
  });
});
