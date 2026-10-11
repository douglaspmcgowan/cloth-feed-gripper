import { test, expect } from "@playwright/test";
import { readJson } from "./helpers.mjs";

// Deployment shape. These do not depend on the viewport, so they run once.
test.describe("deployment", () => {
  test.beforeEach(({}, info) => {
    test.skip(info.project.name !== "desktop-1440-light", "viewport-independent; runs once");
  });

  for (const path of ["/AGENTS.md", "/TASK.md", "/SPEC.md", "/.agents/INDEX.md", "/.agents/AGENTS.md", "/package.json", "/vercel.json", "/scripts/sync.py", "/.git/config", "/../AGENTS.md"]) {
    test(`${path} is not served`, async ({ request }) => {
      const res = await request.get(path);
      expect(res.status()).toBe(404);
    });
  }

  test("vercel.json serves public/ with no framework or build", () => {
    const v = readJson("vercel.json");
    expect(v.outputDirectory).toBe("public");
    expect(v.framework).toBeNull();
    expect(v.buildCommand ?? null).toBeNull();
    expect(v.cleanUrls).toBe(true);
    const media = v.headers.find((h) => h.source.startsWith("/media/"));
    const cache = media.headers.find((h) => h.key === "Cache-Control").value;
    expect(Number(/max-age=(\d+)/.exec(cache)[1])).toBeGreaterThanOrEqual(31536000);
  });

  test("films are faststart and the posters are small", async ({ request }) => {
    for (const name of ["teaser_10s.mp4", "gripper_hype_1080p.mp4", "gripper_hype_vertical.mp4"]) {
      const res = await request.get(`/media/${name}`, { headers: { Range: "bytes=0-65535" } });
      expect([200, 206]).toContain(res.status());
      const head = await res.body();
      const moov = head.indexOf("moov");
      const mdat = head.indexOf("mdat");
      expect(moov, `${name}: moov atom not in the first 64 KB`).toBeGreaterThan(-1);
      expect(mdat === -1 || moov < mdat, `${name}: moov after mdat`).toBe(true);
    }
    for (const name of ["poster.webp", "poster_vertical.webp"]) {
      const res = await request.get(`/media/${name}`);
      expect((await res.body()).length, name).toBeLessThan(250 * 1024);
    }
  });

  test("provenance records the source commit and a hash for every served file", async () => {
    const p = readJson("public/provenance.json");
    expect(p.source.commit).toMatch(/^[0-9a-f]{40}$/);
    expect(p.files.length).toBeGreaterThan(5);
    for (const f of p.files) expect(f.sha256).toMatch(/^[0-9a-f]{64}$/);
  });
});
