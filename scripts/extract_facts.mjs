// Reads the figures the landing page shows out of the review app itself.
//
// The review app (cad/gripper/viewer.html in berkeley-ai-tutor) embeds its data as `const D={...}`
// and computes its own requirement table, mass check and bench-check list from it in plain
// top-level script code. This script runs that code, and only that code, in a bare `node:vm`
// context and prints the results as JSON. Nothing here is typed in by hand, so a figure on the
// landing page cannot drift from the number the review app shows for the same thing.
//
// Usage: node scripts/extract_facts.mjs <viewer.html>   (JSON on stdout)
import { readFileSync } from "node:fs";
import vm from "node:vm";

const file = process.argv[2];
if (!file) {
  console.error("usage: node scripts/extract_facts.mjs <viewer.html>");
  process.exit(2);
}
const html = readFileSync(file, "utf8");

const dStart = html.indexOf("const D={");
if (dStart < 0) throw new Error("data line `const D={` not found in the review app");
const dEnd = html.indexOf("\n", dStart);
const dLine = html.slice(dStart, dEnd);

const from = html.indexOf("/* ---------- utilities ---------- */");
const to = html.indexOf("const VIEWS={");
if (from < 0 || to < 0 || to < from) throw new Error("review app script layout changed: utilities..VIEWS not found");
const logic = html.slice(from, to);

// `document` and `localStorage` are only touched inside function bodies the facts never call; a
// stub that throws makes any top-level use fail loudly instead of returning a wrong figure.
const trap = () => {
  throw new Error("review app script touched the DOM at load time; extract_facts.mjs needs updating");
};
const sandbox = { document: new Proxy({}, { get: trap }), localStorage: new Proxy({}, { get: trap }), window: {} };
vm.createContext(sandbox);
vm.runInContext(
  `"use strict";\n${dLine}\n${logic}\n` +
    `globalThis.__facts = {REQ, REQC, MASS, LIMIT_G, NCHECK, CHECKS, THERM_FAIL, THERM_N, TOLB: TOLB.length, TOLB_PASS: TOLB.filter(r=>r.v).length};`,
  sandbox,
  { filename: "viewer.html#facts", timeout: 20000 },
);
const f = sandbox.__facts;

// Decisions are static markup in the open-items view.
const decBlock = html.slice(html.indexOf('id="open-decisions"'));
const decisions = [...decBlock.matchAll(/<section id="(open-decision-[a-z0-9-]+)"><h2>(.*?)<\/h2>/g)].map((m) => ({
  id: m[1],
  title: m[2].replace(/&Oslash;/g, "Ø").replace(/&plusmn;/g, "±").replace(/&minus;/g, "−").replace(/&sup3;/g, "³").replace(/&times;/g, "×").replace(/&[a-z]+;/g, ""),
}));
const decEnd = decBlock.indexOf('id="open-checks"');
const decisionsInView = decEnd > 0 ? decisions.filter((d) => decBlock.indexOf(`id="${d.id}"`) < decEnd) : decisions;

const status = (s) => (s === "met" ? "pass" : s);
const out = {
  requirements: {
    total: f.REQ.length,
    counts: { pass: f.REQC.pass, risk: f.REQC.risk, fail: f.REQC.fail, open: f.REQC.open },
    items: f.REQ.map(([name, st, evidence, evidenceId]) => ({ name, status: status(st), evidence, evidenceId })),
  },
  mass: {
    total_g_incl_cloth: f.MASS.total_g_incl_cloth,
    com_mm_past_horn: f.MASS.com_u_past_H,
    mass_moment_gmm: f.MASS.mass_moment_gmm,
    budget_gmm: f.MASS.budget_gmm,
    budget_use: f.MASS.budget_use,
    within_budget: !!f.MASS.ok,
    mass_limit_g: f.LIMIT_G,
  },
  thermal: { cases_failing: f.THERM_FAIL, cases_total: f.THERM_N },
  tolerances: { stacks_total: f.TOLB, stacks_passing_as_designed: f.TOLB_PASS },
  decisions: { total: decisionsInView.length, items: decisionsInView },
  bench_checks: { total: f.NCHECK, views: Object.keys(f.CHECKS).length },
};
process.stdout.write(JSON.stringify(out, null, 2) + "\n");
