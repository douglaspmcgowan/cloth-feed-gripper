import { test, expect } from "@playwright/test";
import { MOJIBAKE, watchErrors, noHorizontalScroll, backgroundLuminance } from "./helpers.mjs";

const DOORS = [
  { door: "#door-model", hash: "#model", view: "model" },
  { door: "#door-fit", hash: "#fit-findings", view: "fit" },
  { door: "#door-assembly", hash: "#assembly", view: "assembly" },
  { door: "#door-open", hash: "#open-requirements", view: "open" },
];

const activeView = (page) => page.evaluate(() => document.querySelector(".view:not([hidden])")?.id);

/** Count the distinct colours (quantised) in a screenshot, drawn through an image so GPU buffers are read safely. */
async function distinctColours(page, locator) {
  const png = await locator.screenshot();
  return page.evaluate(async (b64) => {
    const img = new Image();
    img.src = `data:image/png;base64,${b64}`;
    await img.decode();
    const c = document.createElement("canvas");
    c.width = img.naturalWidth;
    c.height = img.naturalHeight;
    const g = c.getContext("2d");
    g.drawImage(img, 0, 0);
    const d = g.getImageData(0, 0, c.width, c.height).data;
    const seen = new Set();
    for (let i = 0; i < d.length; i += 16) seen.add(((d[i] >> 4) << 8) | ((d[i + 1] >> 4) << 4) | (d[i + 2] >> 4));
    return seen.size;
  }, png.toString("base64"));
}

test.describe("design review app", () => {
  test("loads with no console errors, no sideways scroll and no mojibake", async ({ page }) => {
    const errors = watchErrors(page);
    await page.goto("/review/");
    await expect(page.locator("#rail")).toBeVisible();
    await page.waitForFunction(() => window.__v3ready === true, null, { timeout: 60_000 });
    const { scrollWidth, clientWidth } = await noHorizontalScroll(page);
    expect(scrollWidth, "page scrolls sideways").toBeLessThanOrEqual(clientWidth);
    expect(await page.evaluate(() => document.body.innerText)).not.toMatch(MOJIBAKE);
    expect(errors).toEqual([]);
  });

  test("is a complete document: metadata, favicon and the light reset", async ({ page }) => {
    await page.goto("/review/");
    const meta = (sel, name) => page.locator(sel).getAttribute(name);
    expect(await page.locator("html").getAttribute("lang")).toBe("en");
    expect(await meta('meta[name="viewport"]', "content")).toContain("viewport-fit=cover");
    expect(await meta('meta[name="description"]', "content")).toBeTruthy();
    expect(await meta('link[rel="canonical"]', "href")).toMatch(/\/review\/$/);
    expect(await meta('meta[property="og:image"]', "content")).toMatch(/og\.jpg$/);
    expect(await meta('meta[name="twitter:card"]', "content")).toBeTruthy();
    expect(await page.locator('meta[name="theme-color"]').count()).toBe(2);
    expect(await meta('link[rel="icon"]', "href")).toBe("/favicon.svg");
    expect(await page.locator("html").getAttribute("data-theme")).toBeNull();
    expect(await page.evaluate(() => getComputedStyle(document.body).margin)).toBe("0px");
  });

  test("follows the colour scheme", async ({ page }, info) => {
    await page.goto("/review/");
    const lum = await backgroundLuminance(page);
    if (info.project.name.endsWith("dark")) expect(lum).toBeLessThan(0.1);
    else expect(lum).toBeGreaterThan(0.6);
  });

  test("the 3D canvas draws something", async ({ page }) => {
    await page.goto("/review/#model");
    await page.waitForFunction(() => window.__v3ready === true, null, { timeout: 60_000 });
    const canvas = page.locator('.view:not([hidden]) canvas[aria-label^="3D model"]');
    await expect(canvas).toBeVisible();
    await expect.poll(() => distinctColours(page, canvas), { timeout: 30_000 }).toBeGreaterThan(12);
  });

  for (const { door, hash, view } of DOORS) {
    test(`landing door ${door} lands on the ${view} view`, async ({ page }) => {
      await page.goto("/");
      await page.locator(door).scrollIntoViewIfNeeded();
      await page.locator(door).click();
      await page.waitForURL(`**/review/${hash}`);
      await expect.poll(() => activeView(page)).toBe(view);
      const target = hash.slice(1);
      if (target !== view) await expect(page.locator(`#${target}`)).toBeAttached();
    });
  }

  test("the fit door reaches the servo horn clearance finding, and Home returns to the landing page", async ({ page }) => {
    await page.goto("/");
    await page.locator("#door-fit").click();
    await page.waitForURL("**/review/#fit-findings");
    await expect.poll(() => activeView(page)).toBe("fit");
    await expect(page.locator("#fit-findings")).toContainText(/horn/i);

    const home = page.locator("#rail .homelink");
    await expect(home).toBeVisible();
    await home.click();
    await page.waitForURL((u) => u.pathname === "/");
    await expect(page.locator("h1")).toContainText("gripper");
  });

  test("the failing requirement links from the landing page to its evidence", async ({ page }) => {
    await page.goto("/");
    const link = page.locator("#fails a").first();
    await expect(link).toBeVisible();
    const href = await link.getAttribute("href");
    await link.click();
    await page.waitForURL(`**${href}`);
    await expect(page.locator(`#${href.split("#")[1]}`)).toBeAttached();
    await expect.poll(() => activeView(page)).toBeTruthy();
  });
});
