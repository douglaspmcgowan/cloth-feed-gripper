// Post-deploy guard: the public pages answer with the right content, and nothing outside public/ is reachable.
//
//   node scripts/check_live.mjs <base-url>      e.g. https://cloth-feed-gripper.vercel.app
//
// Prints one line per path and a final "check_live: N ok, M failed"; exits 1 on any failure.
// No dependencies: Node 18 or later (global fetch).

const base = process.argv[2];
if (!base || !/^https?:\/\//.test(base)) {
  console.error("usage: node scripts/check_live.mjs <base-url>");
  process.exit(2);
}

// A 200 alone would pass a placeholder or the wrong deployment, so the two text pages are also read.
const served = [
  { path: "/", method: "GET", body: (text) => text.includes("<title>Cloth-feed gripper</title>") },
  { path: "/review/", method: "GET" },
  {
    path: "/facts.json",
    method: "GET",
    body: (text) => Number.isInteger(JSON.parse(text).requirements.total),
  },
  { path: "/media/gripper_hype_1080p.mp4", method: "HEAD" },
  { path: "/licenses/so101-apache-2.0.txt", method: "GET" },
].map((c) => ({ ...c, want: 200 }));

const hidden = [
  "/AGENTS.md",
  "/CLAUDE.md",
  "/TASK.md",
  "/LOG.md",
  "/README.md",
  "/SPEC.md",
  "/package.json",
  "/vercel.json",
  "/.agents/INDEX.md",
  "/.git/config",
  "/.gitignore",
  "/.env.example",
  "/.sync/state.json",
  "/scripts/sync.py",
  "/scripts/check_public.py",
  "/scripts/public-allowlist.txt",
  "/tests/deploy.spec.mjs",
  "/node_modules/.package-lock.json",
  "/public/index.html",
  "/public/facts.json",
  "/site.config.json",
].map((path) => ({ path, method: "GET", want: 404 }));

let ok = 0;
let failed = 0;
for (const { path, method, want, body } of [...served, ...hidden]) {
  let status;
  let note = "";
  try {
    const res = await fetch(new URL(path, base), { method, redirect: "manual" });
    status = res.status;
    if (body && status === want) {
      let good = false;
      try {
        good = Boolean(body(await res.text()));
      } catch {
        good = false;
      }
      if (!good) {
        status = `${status} with unexpected content`;
        note = " and the expected content";
      }
    } else {
      // Release the connection; a GET of a film would otherwise stream into memory.
      await res.body?.cancel();
    }
  } catch (err) {
    status = `error: ${err.cause?.code ?? err.message}`;
  }
  const pass = status === want;
  pass ? ok++ : failed++;
  console.log(`${pass ? "ok  " : "FAIL"} ${method.padEnd(4)} ${path} -> ${status} (want ${want}${note})`);
}

console.log(`check_live: ${ok} ok, ${failed} failed`);
// Set the code and let Node end by itself: process.exit() here aborts on Windows while sockets close.
process.exitCode = failed ? 1 : 0;
