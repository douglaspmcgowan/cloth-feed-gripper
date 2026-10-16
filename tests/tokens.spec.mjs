// Every custom property the pages read must come from a source. A var(--name) with no fallback and no
// definition resolves to nothing: the element silently loses its colour, size or position, and no error
// is raised. This spec finds each such use on both pages, in every size and scheme in playwright.config.mjs.
//
// A name counts as resolved when either
//   1. it has a computed value on some element at load (the root for page tokens such as --measure), or
//   2. the served HTML, stylesheets or scripts declare it, for properties the page sets only on demand
//      (--sw on a placeholder thumbnail, --zw and --zh when a drawing sheet is zoomed, --sheet-h on .sheet).
// DESIGN.md "Where each token is defined" lists the source of each one.
import { test, expect } from "@playwright/test";
import { watchErrors } from "./helpers.mjs";

const PAGES = [
  { path: "/", ready: "h1" },
  { path: "/review/", ready: ".sheet" },
];

test.describe("custom properties", () => {
  for (const { path, ready } of PAGES) {
    test(`every var() without a fallback resolves on ${path}`, async ({ page }) => {
      const errors = watchErrors(page);
      await page.goto(path);
      await expect(page.locator(ready).first()).toBeAttached();

      const result = await page.evaluate(async () => {
        const cs = (el, n) => getComputedStyle(el).getPropertyValue(n).trim();
        const css = [];
        const walk = (rules) => {
          for (const r of rules) {
            css.push(r.cssText);
            if (r.cssRules) walk(r.cssRules);
          }
        };
        for (const sheet of document.styleSheets) {
          try {
            walk(sheet.cssRules);
          } catch {
            // a cross-origin sheet has no rules to read; every stylesheet here is same-origin
          }
        }
        const inline = [...document.querySelectorAll("[style]")].map((el) => el.getAttribute("style"));

        const used = new Set();
        for (const m of [...css, ...inline].join("\n").matchAll(/var\(\s*(--[\w-]+)\s*(,?)/g)) {
          if (m[2] !== ",") used.add(m[1]);
        }

        const source = [document.documentElement.outerHTML, ...css, ...inline];
        for (const s of document.querySelectorAll("script[src]")) source.push(await (await fetch(s.src)).text());
        const text = source.join("\n");

        const els = [...document.querySelectorAll("*")];
        const unresolved = [];
        for (const name of used) {
          if (els.some((el) => cs(el, name) !== "")) continue;
          const esc = name.replace(/-/g, "\\-");
          if (!new RegExp(`${esc}\\s*:|["']${esc}["']`).test(text)) unresolved.push(name);
        }
        return { used: used.size, unresolved };
      });

      expect(result.used, "no custom properties found, so the check is not reading the page").toBeGreaterThan(0);
      expect(result.unresolved, "custom properties used with no fallback and no definition").toEqual([]);
      expect(errors).toEqual([]);
    });
  }

  test("the landing page tokens have a computed value on the root", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toBeVisible();
    const values = await page.evaluate(() => {
      const root = getComputedStyle(document.documentElement);
      return Object.fromEntries(["--measure", "--wrap", "--fs-d"].map((n) => [n, root.getPropertyValue(n).trim()]));
    });
    for (const [name, value] of Object.entries(values)) expect(value, name).not.toBe("");
  });
});
