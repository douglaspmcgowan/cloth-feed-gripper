// Browser tests for the public site. The server roots at public/, exactly as Vercel does, so anything
// outside that folder is a 404 here too.
//
//   npm test                         the full matrix: 3 sizes x light and dark
//   PW_CHANNEL=chrome npm test       run in installed Chrome instead of the bundled Chromium
import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.PW_PORT) || 4391;
const channel = process.env.PW_CHANNEL || undefined;

const SIZES = [
  { name: "desktop-1440", viewport: { width: 1440, height: 900 } },
  { name: "tablet-768", viewport: { width: 768, height: 1024 } },
  { name: "phone-375", viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true },
];

export default defineConfig({
  testDir: "tests",
  timeout: 150_000,
  expect: { timeout: 20_000 },
  fullyParallel: true,
  // The review app is a 10 MB page with a 3D scene; three or more at once starve a shared machine
  // (timeouts, crashed workers). Override with PW_WORKERS on a roomy one.
  workers: Number(process.env.PW_WORKERS) || 2,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    channel,
    trace: "off",
  },
  webServer: {
    command: `node scripts/serve.mjs ${PORT}`,
    url: `http://127.0.0.1:${PORT}/`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
  projects: SIZES.flatMap((size) =>
    ["light", "dark"].map((colorScheme) => ({
      name: `${size.name}-${colorScheme}`,
      use: { ...devices["Desktop Chrome"], ...size, viewport: size.viewport, colorScheme, deviceScaleFactor: 1 },
    })),
  ),
});
