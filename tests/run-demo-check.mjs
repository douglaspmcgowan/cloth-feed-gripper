// Isolate this linked lane from another checkout's default test port.
// node tests/run-demo-check.mjs [Playwright arguments]
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../", import.meta.url));
const result = spawnSync(process.execPath, ["node_modules/@playwright/test/cli.js", "test", ...process.argv.slice(2)], {
  cwd: root, env: { ...process.env, PW_PORT: "45131" }, stdio: "inherit",
});
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
