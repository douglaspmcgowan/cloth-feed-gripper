// Post-deploy guard: the public pages answer, and nothing outside public/ is reachable.
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

const served = [
  { path: "/", method: "GET" },
  { path: "/review/", method: "GET" },
  { path: "/facts.json", method: "GET" },
  { path: "/media/gripper_hype_1080p.mp4", method: "HEAD" },
  { path: "/licenses/so101-apache-2.0.txt", method: "GET" },
].map((c) => ({ ...c, want: 200 }));

const hidden = [
  "/AGENTS.md",
  "/TASK.md",
  "/README.md",
  "/SPEC.md",
  "/package.json",
  "/vercel.json",
  "/.agents/INDEX.md",
  "/scripts/sync.py",
  "/tests/deploy.spec.mjs",
  "/.gitignore",
  "/site.config.json",
].map((path) => ({ path, method: "GET", want: 404 }));

let ok = 0;
let failed = 0;
for (const { path, method, want } of [...served, ...hidden]) {
  let status;
  try {
    const res = await fetch(new URL(path, base), { method, redirect: "manual" });
    status = res.status;
    // Release the connection; a GET of a film would otherwise stream into memory.
    await res.body?.cancel();
  } catch (err) {
    status = `error: ${err.cause?.code ?? err.message}`;
  }
  const pass = status === want;
  pass ? ok++ : failed++;
  console.log(`${pass ? "ok  " : "FAIL"} ${method.padEnd(4)} ${path} -> ${status} (want ${want})`);
}

console.log(`check_live: ${ok} ok, ${failed} failed`);
process.exit(failed ? 1 : 0);
