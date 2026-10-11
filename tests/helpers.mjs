import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const readJson = (rel) => JSON.parse(readFileSync(resolve(ROOT, rel), "utf8"));

export const MOJIBAKE = /Ã|â€|Â/;

/** Collect console errors, page errors and failed same-origin requests on a page. */
export function watchErrors(page) {
  const errors = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(`console: ${m.text()}`);
  });
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("response", (r) => {
    const url = new URL(r.url());
    if (url.hostname === "127.0.0.1" && r.status() >= 400) errors.push(`${r.status()} ${url.pathname}`);
  });
  return errors;
}

export const noHorizontalScroll = (page) =>
  page.evaluate(() => {
    const d = document.documentElement;
    return { scrollWidth: d.scrollWidth, clientWidth: d.clientWidth };
  });

/** Relative luminance of the page background, 0 (black) to 1 (white). */
export const backgroundLuminance = (page) =>
  page.evaluate(() => {
    const m = getComputedStyle(document.body).backgroundColor.match(/[\d.]+/g).map(Number);
    const [r, g, b] = m.slice(0, 3).map((v) => {
      const c = v / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  });
