"""Build cad/gripper/viewer.html: extracts compact data from the analysis JSONs and
base64-embeds the GLB + SO-101 context mesh into the template parts vw_*.html."""
import base64, json, math, re, sys, os
from pathlib import Path
from fit3d_inputs import validate_result

SP = Path(__file__).resolve().parent
ROOT = Path(os.environ["VW_ROOT"]) if os.environ.get("VW_ROOT") else SP.parents[2]
RES = ROOT / "analysis/gripper/results"
OUT = Path(os.environ["VW_OUT"]) if os.environ.get("VW_OUT") else ROOT / "cad/gripper/viewer.html"
F3P = Path(os.environ["VW_FIT3D"]) if os.environ.get("VW_FIT3D") else ROOT / "cad/gripper/out/fit3d.json"
if F3P.exists():
    try:
        validate_result(json.loads(F3P.read_text(encoding="utf-8")), ROOT / "cad/gripper")
    except ValueError as error:
        raise SystemExit(str(error)) from error


def J(p):
    txt = Path(p).read_text(encoding="utf-8")
    return json.loads(txt)


def clean(o, nd=4):
    if isinstance(o, float):
        if math.isnan(o) or math.isinf(o):
            return None
        return round(o, nd)
    if isinstance(o, dict):
        return {k: clean(v, nd) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v, nd) for v in o]
    return o


def ds(a, n):
    if len(a) <= n:
        return a
    step = len(a) / n
    return [a[int(i * step)] for i in range(n)] + [a[-1]]


D = {}
D["fitreq"] = J(ROOT / "cad/gripper/fit_requirements.json")

# ---- CAD parts + fitcheck
parts = J(ROOT / "cad/gripper/out/parts.json")
fit = J(ROOT / "cad/gripper/out/fitcheck.json")
D["parts"] = clean(parts, 3)
D["fit"] = clean(fit, 3)

# ---- concept
cn = J(ROOT / "docs/gripper/figures/concept_numbers.json")
pg = cn["pugh"]
D["pugh"] = clean({
    "weights": pg["weights"],
    "concepts": {k: {kk: v[kk] for kk in ("name", "transmission", "actuator", "stock", "force_margin", "mass_moment_gmm", "mass_g", "pct_budget", "close_time_s", "passes_R19")} for k, v in pg["concepts"].items()},
    "scores": pg["scores"],
    "total": pg["weighted_total"],
    "rank": pg["rank"],
    "sens": {k: v["totals"] for k, v in pg["sensitivity"].items()},
    "top_by_case": pg["top_by_case"],
}, 3)
D["trans"] = clean({k: {"name": v.get("name"), "mm": v.get("mass_moment"), "close": v.get("close_time_s"), "T_LC1": v.get("T_servo_LC1_Nm")} for k, v in cn["transmissions"].items() if isinstance(v, dict) and "name" in v}, 3)

# ---- payload / torque
pt = J(RES / "payload_torque.json")
g = pt["grip"]
kits = pt["payload"]["allowable_hardware_mass_worst_pose"]
D["grip"] = clean({k: g[k] for k in ("F_target_N", "F_cap_N", "theta_contact_deg", "F_target_asym_nail_N", "T_hold_Nm", "T_hold_kgcm", "T_hold_no_tension_term_Nm", "tension_term_Nm", "T_peak_Nm", "T_peak_kgcm", "stall_needed_kgcm", "lever_vs_L", "jaw_angle", "speed", "tornado_T_hold_kgcm", "T_hold_vs_rc")}, 3)
D["kits"] = clean({"d_mm": kits["d_mm"], "kits": {k: {c: {"gov": v[c]["governing_g"], "stat": v[c]["static_hold_g"], "dyn": v[c]["dynamic_g"]} for c in v} for k, v in kits["kits"].items()}}, 2)
D["rollup"] = clean(pt["rollup_design_point_A17"], 4)
D["breakeven"] = clean(pt["breakeven_design_rail_low_end"], 3)
D["inputs"] = clean({k: (v["value"] if isinstance(v, dict) and "value" in v else v) for k, v in pt["inputs"].items() if isinstance(v, dict) and "value" in v and not isinstance(v["value"], dict)}, 4)
run = pt["runs"]["r40_design"]
score = {}
for key in ("trade", "trade_vendor_consistent"):
    for c in run[key].get("candidates", []):
        score.setdefault(c["id"], c.get("score"))
acts = []
for a in run["actuators"] + run["fallback_branch"]:
    acts.append({
        "id": a["id"], "model": a.get("model"), "kind": a.get("kind"), "price": a.get("price"),
        "mass": a.get("mass_g"), "stock": a.get("stock"), "stall": a.get("stall_kgcm"),
        "hm": a.get("hold_margin"), "hmv": a.get("hold_margin_vendor_rule"), "close": a.get("close_time_s"),
        "arm": a.get("arm_util_C001_7p4V"), "rcmax": a.get("r_c_max_mm"), "tmesh": a.get("T_mesh_LC3_Nm"),
        "fb": a.get("feedback"), "vmax": a.get("voltage_max_V"), "fail": a.get("fail", []), "pass": a.get("pass"),
        "score": a.get("score", score.get(a["id"])), "N": a.get("N"),
    })
D["acts"] = clean(acts, 3)
D["actrec"] = clean(run["recommendation"], 3)
D["weights"] = run["trade_vendor_consistent"]["weights"]

# ---- FEA
fea = {}
mesh_cache = {}
for name in ("fea_tip", "fea_mid", "fea_point", "fea_tip_nl_cap", "fea_mid_nl_cap"):
    d = J(RES / f"{name}.json")
    key = (len(d["nodes"]), d["nodes"][0], d["nodes"][-1])
    if key not in mesh_cache:
        mesh_cache[key] = f"m{len(mesh_cache)}"
        fea[mesh_cache[key]] = {"nodes": [round(v, 3) for v in d["nodes"]], "el": d["elements"]}
    e = {"mesh": mesh_cache[key], "case": d["case"], "F": d["F_N"], "E": d["E_MPa"], "linear": d["linear"],
         "u": [round(v, 4) for v in d["displacement"]], "vm": [round(v, 3) for v in d["von_mises"]],
         "F56": d.get("F_N_equivalent_at_E56")}
    if "green_lagrange_strain_max_principal" in d:
        e["gl"] = [round(v, 4) for v in d["green_lagrange_strain_max_principal"]]
    fea[name] = e
D["fea"] = fea
sw = J(RES / "fea_sweep.json")
cols = ["rib_angle", "ribs", "wall", "rib_thickness", "tip_width", "mass_g", "k_tip_E67", "k_tip_E56", "k_mid", "vm_p99_tip", "window_ok", "feasible_linear", "feasible"]
D["sweep"] = {"cols": cols, "rows": clean([[r.get(c) for c in cols] for r in sw["rows"]], 3),
              "counts": clean(sw["counts"], 3), "verdict": clean(sw["verdict"], 3), "rec": clean(sw["recommended"], 3),
              "screened": clean(sw.get("screened"), 3)}
fs = J(RES / "fea_summary.json")
D["fea_summary_keys"] = list(fs.keys())[:40]

# ---- gears
gj = J(RES / "gears.json")
swp = gj["sweep"]
D["gears"] = clean({
    "modules": swp["modules"], "teeth": swp["teeth"],
    "bmin": swp["bmin_maps"],
    "per_pair": {k: {kk: v[kk] for kk in ("n_eval", "n_pass", "n_pass_margin", "best_margin_any")} for k, v in swp["per_pair"].items()},
    "rec": gj["recommendation"],
    "lc": gj["load_cases"]["at_rec_print"],
}, 4)


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1e-12
    dmax, idx = 0, 0
    for i in range(1, len(pts) - 1):
        x0, y0 = pts[i]
        d = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / L
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        return rdp(pts[: idx + 1], eps)[:-1] + rdp(pts[idx:], eps)
    return [pts[0], pts[-1]]


svg = (ROOT / "cad/gripper/gear_profile.svg").read_text(encoding="utf-8")
prof = {}
for gid in ("GEAR_A", "GEAR_B"):
    m = re.search(r'id="%s" d="([^"]+)"' % gid, svg)
    nums = re.findall(r"(-?\d+\.\d+),(-?\d+\.\d+)", m.group(1))
    pts = [(float(a), float(b)) for a, b in nums]
    sys.setrecursionlimit(20000)
    far = max(range(len(pts)), key=lambda i: (pts[i][0]-pts[0][0])**2 + (pts[i][1]-pts[0][1])**2)
    s = rdp(pts[: far + 1], 0.004)[:-1] + rdp(pts[far:], 0.004)
    prof[gid] = {"n_src": len(pts), "pts": [[round(x, 3), round(y, 3)] for x, y in s]}
vb = re.search(r'viewBox="([^"]+)"', svg).group(1)
prof["viewBox"] = [float(v) for v in vb.split()]
D["gprof"] = prof

# ---- dyno
dy = J(RES / "dyno.json")
se = dy["series"]
dc = se["duty_cycle_A_mech"]
idx = list(range(0, len(dc["t"]), 3))
D["duty"] = clean({k: [dc[k][i] for i in idx] for k in ("t", "theta_cmd", "theta_A", "F", "F_fsr", "T_servo", "T_mesh", "i", "P_elec", "tension")}, 3)
cz = se["close_zoom"]
idx = list(range(0, len(cz["t"]), 2))
D["closez"] = clean({k: [cz[k][i] for i in idx] for k in ("t", "theta_cmd", "theta_A", "F", "F_fsr", "T_servo", "i")}, 4)
th = se["thermal_30min_A_amb40"]
idx = list(range(0, len(th["t"]), 4))
D["therm"] = clean({k: [th[k][i] for i in idx] for k in ("t", "T_winding", "T_case")}, 2)
D["percycle"] = clean(se["per_cycle_30min_A_amb40"], 3)
ts = dy["test1_torque_speed"]
D["tspeed"] = clean({k: {kk: ts[k][kk] for kk in ts[k]} for k in ts}, 4)
D["therm_cases"] = clean(dy["test3_duty_cycle"]["thermal_30min"], 2)
D["rank"] = clean(dy["fatigue"]["ranking_named_options"], 4)
D["shock"] = clean(dy["test4_shock"], 3)
D["motor_fit"] = clean(dy["motor_fit"]["fits"], 4)
D["dyno_close"] = clean({k: v for k, v in dy["test3_duty_cycle"].items() if k != "thermal_30min" and not isinstance(v, list)}, 3)

# ---- tolerances
tol = J(ROOT / "analysis/gripper/tolstack/results/summary.json")["stacks"]
tr = []
for r in tol:
    mc = r.get("mc") or {}
    tr.append({"id": r["id"], "t": r.get("title"), "nom": r.get("nominal"), "wc": r.get("wc"), "rss": r.get("rss_dist") or r.get("rss_classic"),
               "mc": [mc.get("p0135"), mc.get("p99865")] if mc else None, "out": mc.get("out_pct"), "cpk": mc.get("cpk_percentile"),
               "spec": r.get("spec"), "method": r.get("method"), "v": r.get("verdict"), "p": r.get("pass"), "blk": r.get("blocked_by"), "own": r.get("own_verdict")})
    vf = ROOT / "analysis/gripper/tolstack/results" / (r["id"] + ".json")
    tr[-1]["vl"] = (J(vf).get("variant_label") or "") if vf.exists() else ""
D["tol"] = clean(tr, 4)

# ---- revision B BOM tables, with CAD masses rather than rounded prose masses
bom_md = (ROOT / "cad/gripper/drawings/BOM.md").read_text(encoding="utf-8")
sections = {}
for heading, body in re.findall(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", bom_md, re.M | re.S):
    sections[heading] = body
def table_rows(body):
    return [[x.strip() for x in line.strip("|").split("|")] for line in body.splitlines()
            if line.startswith("| ") and not line.startswith("|---") and not line.startswith("| Part") and not line.startswith("| Item")]
printed = table_rows(sections["Printed parts"])
bought = table_rows(sections["Bought parts"])
mass = table_rows(sections["Mass and cost"])
total = next(c for c in mass if c[0].startswith("**total"))
bom = {"parts": [], "fast": [], "off": ["servo tester or controller", "thermocouple", "consumables"],
       "total": {"g": float(total[4].strip("*")), "usd": float(total[5].strip("*"))}}
rows = []
for c in printed:
    name, q = c[0], int(c[1])
    bom["parts"].append({"part": name, "qty": q, "mat": c[2], "proc": c[5], "g": parts["parts"][name]["mass_g"], "usd": float(c[7]), "bought": False})
    rows.append({"k": name, "name": name, "qty": q, "mat": c[2], "proc": c[5], "g": parts["parts"][name]["mass_g"], "usd": float(c[7]), "kind": "printed", "part": name})
for name, label in (("servo", "Servo"), ("horn", "Horn")):
    c = next(c for c in bought if c[0] == label)
    rows.append({"k": name, "name": name, "qty": 1, "mat": "", "proc": "bought", "g": parts["parts"][name]["mass_g"], "usd": float(c[4]), "kind": "bought", "part": name})
rows.append({"k": "fsr_sensor_b", "name": "FSR", "qty": 1, "mat": "", "proc": "bought", "g": parts["parts"]["fsr_sensor_b"]["mass_g"], "usd": float(next(c[4] for c in bought if c[0] == "FSR")), "kind": "bought", "part": "fsr_sensor_b"})
fm = {nm: g for items in parts["fastener_masses_g"].values() for nm, g, _ in items}
if abs(fm["pegs + M2 screw"] - (2 * 0.59 + 0.65)) > 0.001:
    raise SystemExit("BOM finger pegs and root bolts no longer match the CAD fastener mass")
shims = sorted(nm for nm in fm if nm.startswith("shim "))
if len(shims) != 1:
    raise SystemExit(f"BOM line 'Shims' needs one current shim item in parts.json; found {shims}")
shim = shims[0]
FAST_MAP = [  # BOM line -> current CAD item, group; validate every mapped row
    ("Dog set screws", "dog set screw M3x10", "fasteners_a"),
    ("Knuckle pins", "pin h8 3x16", "fasteners"),
    ("Knuckle bushes", "bronze bush 3x6x10", "fasteners_a fasteners_b"),
    ("Shims", shim, "fasteners"),
    ("Deck locating pins", "locating pin h8 3x6", "fasteners"),
    ("Horn screws", "M3x6 horn screw", "fasteners"),
    ("Deck screws", "M3x6 deck screw", "fasteners"),
    ("Heat-set inserts", "M3 heat-set insert", "fasteners"),
    ("Ear screws", "M3x10 ear screw", "fasteners"),
    ("Compression limiters", "limiter sleeve 5x3.2x2.55", "fasteners"),
    ("Washers", "washer M3 7x3.2x0.5", "fasteners"),
    ("Nuts", "nut M3", "fasteners"),
    ("Front plate screws", "M3x16 plate screw", "fasteners"),
    ("Finger pegs", "pegs + M2 screw", "fasteners_a fasteners_b"),
    ("Finger root bolts", "pegs + M2 screw", "fasteners_a fasteners_b"),
]
for label, item, group in FAST_MAP:
    if sum(c[0] == label for c in bought) != 1:
        raise SystemExit(f"BOM line {label!r} is missing or duplicated in the current BOM")
    if item is None or not any(nm == item for grp in group.split() for nm, _, _ in parts["fastener_masses_g"][grp]):
        raise SystemExit(f"BOM line {label!r} has no matching item {item!r} in parts.json")
for c in bought:
    name, q, each = c[0], int(c[1]), float(c[4])
    if name in ("Servo", "Horn", "FSR") or name in ("Servo tester or controller", "Thermocouple", "Consumables"):
        continue
    hit = next((m for m in FAST_MAP if name == m[0]), None)
    if not hit and name not in ("Horn centre screw", "Camera-pad inserts (optional)"):
        raise SystemExit(f"BOM line {name!r} has no current fastener item mapping in parts.json")
    if hit:
        item, group = hit[1:]
        unit_mass = fm[item]
        if name in ("Finger pegs", "Finger root bolts"):
            unit_mass = 0.59 if name == "Finger pegs" else 0.65
        g = round(unit_mass * q, 3)
    else:
        item, group, g = "", "", 0.0  # horn centre screw is not represented in the CAD assembly
    bom["fast"].append([name, q, each])
    rows.append({"k": "fx-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"), "name": name, "qty": q, "mat": "", "proc": "bought" if hit else "bought; not modelled in CAD", "g": g,
                 "usd": round(each * q, 2), "each": each, "kind": "fastener" if hit else "bought", "part": group, "item": item})
D["bom"] = bom
asm_items = J(ROOT / "cad/gripper/assembly/steps.json").get("fastener_items", []) if (ROOT / "cad/gripper/assembly/steps.json").exists() else []
ASM_PREFIX = {"Dog set screws": "dog_screw_", "Knuckle pins": "pin_", "Knuckle bushes": "bush_",
              "Shims": "shim_", "Deck locating pins": "locpin_", "Horn screws": "horn_screw_",
              "Deck screws": "deck_screw_", "Heat-set inserts": "insert_", "Ear screws": "ear_screw_",
              "Compression limiters": "limiter_", "Washers": "washer_", "Nuts": "nut_",
              "Front plate screws": "plate_screw_", "Finger pegs": "peg_", "Finger root bolts": "m2_"}
for r in rows:
    if r["kind"] == "fastener":
        prefix = ASM_PREFIX.get(r["name"])
        r["items"] = sorted(i["id"] for i in asm_items if prefix and i["id"].startswith(prefix))
        if prefix and asm_items and len(r["items"]) != r["qty"]:
            raise SystemExit("assembly items do not match the BOM line %s: %d of %d" % (r["name"], len(r["items"]), r["qty"]))
D["bomx"] = rows
D["bomx_check"] = {"g": round(sum(r["g"] for r in rows), 2), "usd": round(sum(r["usd"] for r in rows), 2)}
if abs(D["bomx_check"]["g"] - bom["total"]["g"]) > 0.06 or abs(D["bomx_check"]["usd"] - bom["total"]["usd"]) > 0.011:
    raise SystemExit("BOM rows do not add up to the BOM total: %r vs %r" % (D["bomx_check"], bom["total"]))

# ---- 3D fit audit (fit3d.py): per pair, gap at each jaw angle with the two closest points; roll; press fits
if F3P.exists():
    f3 = J(F3P)
    TH = f3["thetas"]
    pairs = []
    for t in f3["jaw_pairs"]:
        if t["d_min"] is None:
            continue
        key = lambda th: "%g" % th
        pairs.append({"a": t["a"], "b": t["b"], "kind": t["kind"], "dmin": t["d_min"], "thmin": t["theta_at_min"], "vmax": t["v_max"],
                      "status": t["status"], "requirement_id": t.get("requirement_id"),
                      "required_mm": t.get("requirement_minimum_mm"), "allowance_mm": t.get("sampling_allowance_mm"),
                      "no_requirement_reason": t.get("no_requirement_reason"),
                      "governing_checks": t.get("governing_checks", []),
                      "d": [t["d"].get(key(th)) for th in TH], "p": [t["pts"].get(key(th)) for th in TH], "v": [t["v"].get(key(th), 0) for th in TH]})
    def headline_status(pair):
        """A governed row whose feature check fails or is at risk counts as such, not as governed elsewhere."""
        checks = [check["status"] for check in pair["governing_checks"]]
        if pair["status"] != "governed elsewhere":
            return pair["status"]
        if not checks or any(check not in ("met", "at risk") for check in checks):
            return "fail"
        return "at risk" if "at risk" in checks else pair["status"]
    counts = {status: sum(headline_status(pair) == status for pair in pairs)
              for status in ("fail", "at risk", "met", "governed elsewhere", "no requirement")}
    D["fit3d"] = clean({"th": TH, "pairs": pairs, "static": f3["static_overlaps"], "roll": f3.get("roll", []), "roll_err": f3.get("roll_error"),
                        "pair_status_counts": counts, "verdict": f3.get("verdict"),
                        "roll_check": f3.get("roll_frame_check_mm"),
                        # per finding: section cut, nearness patches, worst case under the stated tolerances; overlap solids; insertion paths
                        "detail": f3.get("detail", {}), "overlaps": f3.get("overlaps", []), "builds": f3.get("builds", []),
                        "near_threshold_mm": f3.get("near_threshold_mm"), "tight_mm": f3.get("tight_mm")}, 4)
else:
    raise SystemExit("fit3d.json is missing; rerun uv run --with cadquery python cad/gripper/fit3d.py")

# ---- part thumbnails rendered from this page's own 3D model by make_thumbs.py
thp = SP / "thumbs.json"
D["thumbs"] = J(thp) if thp.exists() else {}

# ---- assembly plan (cad/gripper/assembly/steps.json)
asp = ROOT / "cad/gripper/assembly/steps.json"
D["asm"] = clean(J(asp), 3) if asp.exists() else None

# ---- drawings and static figures, embedded as data URIs
def uri(p):
    mime = {".svg": "image/svg+xml", ".png": "image/png"}[p.suffix]
    return "data:%s;base64,%s" % (mime, base64.b64encode(p.read_bytes().replace(b"\r\n", b"\n") if p.suffix == ".svg" else p.read_bytes()).decode())


IMG = {}
for n in ("housing", "knuckle_a", "knuckle_b", "finger_a", "wrist_mount", "fitcheck", "fitcheck_iso"):
    IMG["draw_" + n] = ROOT / "cad/gripper/drawings" / (n + ".svg")
for n in ("concept_T1_spur_1to1.svg", "concept_T2_unequal_ratio.svg", "concept_T3_rack_pinion.svg", "concept_T4_fourbar.svg",
          "concept_T5_worm.svg", "concept_T6_tendon.svg", "camera_views.png", "camera_top.png", "camera_side.png"):
    IMG[n.rsplit(".", 1)[0]] = ROOT / "docs/gripper/figures" / n
D["img"] = {k: uri(p) for k, p in IMG.items()}

# ---- drawing sheets: the files stay as they are; the embedded copy is made readable in the page.
# Part sheets: footer notes are lifted out as text (shown beside the sheet) and the sheet is cropped above them.
# Fit sheets: they carry no viewBox, so one is fitted to the drawn paths.
NOTE_SUBS = [
    (r"&amp;", "&"), (r"envelope X ([\d.]+) x Y ([\d.]+) x Z ([\d.]+) mm", "Envelope \\1 × \\2 × \\3 mm (X, Y, Z)"), (r"\s*at \[\[.*?\]\](?: \(x, z\))?", ""),
    (r", fix \d+\)", ")"), (r"(\d) dia puck", "Ø\\1 puck"), (r"\bL ([\d.]+), W ([\d.]+)", r"Length \1, width \2"), (r" - measure", "; measure"),
    (r"\bperp dia ", "square within Ø"), (r"\bpos dia ", "position Ø"), (r"\s*\[[^\]]*\]", ""), (r"\s*\((?:D\d+|fix \d+|[a-z_]+\.md \d+|base layout only)\)", ""), (r"\s*\(frame [GI], theta 0\)", ", jaw at 0\u00b0"),
    (r"\(frame I\)", ""), (r"GD&T:?\s*", ""), (r"\bT\d+[A-Z]? says it", "the screw-depth stack says it"),
    (r"Gear m ([\d.]+) z (\d+) alpha (\d+) x ([\d.]+) b ([\d.]+) a_w ([\d.]+) jt ([\d.]+)", "Gear: module \\1, \\2 teeth, \\3\u00b0 pressure angle, \\5 wide, centre distance \\6, backlash \\7"),
    (r"; profile = gear_profile\.dxf GEAR_[AB]", ""), (r"\s*\(tooth on -X at theta 0\)", ""), (r"\ba = ([\d.]+)", r"centre distance \1"), (r"\br_c = ([\d.]+)", r"moment arm \1"),
    (r"\s*\(clamp line y0 = [-\d.]+\)", ""), (r"; pad face x_f = [\d.]+ \(local\)", ""), (r"H at y = ([\d.]+) in frame G", r"Horn face \1 above the pivots"), (r"H\+", "the horn face +"),
    (r"\|\s*([A-D])(?:\s*\(M\))?\s*\|\s*([A-D])(?:\s*\(M\))?\s*\|\s*([A-D])\s*\|", r"to \1, \2 and \3"), (r"\|\s*([A-D])(?:\s*\(M\))?\s*\|\s*([A-D])(?:\s*\(M\))?\s*\|", r"to \1 and \2"), (r"\|\s*([A-D])\s*\|", r"to \1"),
    (r"\s*\(M\)", ""), (r"\bperp dia\b", "square within \u00d8"), (r"\bperp\b", "square within"), (r"\bpos dia\b", "position \u00d8"), (r"\bpos\b", "position"), (r"\bpar\b", "parallel within"),
    (r"\bdia ", "\u00d8"), (r"\+/-", "\u00b1"), (r"(\d) deg\b", "\\1\u00b0"), (r"\btheta 0\b", "0\u00b0"), (r"\bBC\b", "bolt circle"), (r"\bFSR 402\b", "the force sensor"), (r"\.\.", " to "),
    (r"(\d)x(\d)", "\\1 \u00d7 \\2"), (r" x ", " \u00d7 "), (r"(\d)x ", "\\1 \u00d7 "), (r" ~", " about "), (r"\s+([.,;:])", r"\1"), (r"\s{2,}", " "),
]


def plain_note(s):
    for a, b in NOTE_SUBS:
        s = re.sub(a, b, s)
    return s.strip().rstrip(".")


def prep_sheet(text):
    notes = []
    if 'font-family="monospace"' in text:
        foot = [(float(y), re.sub(r"<[^>]+>", "", body)) for y, body in re.findall(r'<text x="10" y="([\d.]+)" font-size="9\.5">(.*?)</text>', text, re.S)]
        text = re.sub(r'<text x="10" y="[\d.]+" font-size="9\.5">.*?</text>\s*', "", text, flags=re.S)
        text = text.replace('font-family="monospace"', 'font-family="Segoe UI, system-ui, sans-serif"')
        if foot:
            hgt = int(min(y for y, _ in foot) - 14)
            text = re.sub(r'height="700" viewBox="0 0 760 700"', 'height="%d" viewBox="0 0 760 %d"' % (hgt, hgt), text, count=1)
        for _, body in sorted(foot):
            for part in re.split(r"(?<=[^\d])\.\s+(?=\S)", body):
                p = plain_note(part)
                if p:
                    notes.append(p[0].upper() + p[1:])
    elif "viewBox" not in text[:400]:
        m = re.search(r'transform="scale\(([-\d.]+),\s*([-\d.]+)\)\s*translate\(([-\d.]+),\s*([-\d.]+)\)"', text)
        ds = re.findall(r'<path d="([^"]+)"', text)
        box = None
        if m and ds and all(re.fullmatch(r"[ML\s\d.,eE+-]+", d) for d in ds):
            sx, sy, tx, ty = map(float, m.groups())
            nums = [float(v) for d in ds for v in re.findall(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?", d)]
            xs = [sx * (v + tx) for v in nums[0::2]]
            ys = [sy * (v + ty) for v in nums[1::2]]
            pad = 10
            box = (min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad)
        vb = "%.1f %.1f %.1f %.1f" % box if box else "0 0 700 600"
        w, h = (box[2], box[3]) if box else (700, 600)
        text = re.sub(r'width="700\.0"\s+height="600\.0"', 'width="%.1f" height="%.1f" viewBox="%s"' % (w, h, vb), text, count=1)
    return text, notes


D["sheet_notes"] = {}
for n in ("housing", "knuckle_a", "knuckle_b", "finger_a", "wrist_mount", "fitcheck", "fitcheck_iso"):
    raw = IMG["draw_" + n].read_text(encoding="utf-8").replace("\r\n", "\n")
    svg_txt, notes = prep_sheet(raw)
    D["img"]["draw_" + n] = "data:image/svg+xml;base64," + base64.b64encode(svg_txt.encode("utf-8")).decode()
    if notes:
        D["sheet_notes"]["draw_" + n] = notes

# ---- concept sketches: the embedded copy drops the in-image title, the numbers box and the internal codes; the page gives the numbers as text
SKETCH_CROP = {"concept_T1_spur_1to1": (515, 500), "concept_T2_unequal_ratio": (980, 446), "concept_T3_rack_pinion": (940, 530),
               "concept_T4_fourbar": (560, 480), "concept_T5_worm": (660, 480), "concept_T6_tendon": (560, 610)}
SKETCH_SUBS = [(r"\s*\((?:C\d\w*|M\d+)\)", ""), (r"\bFSR\b", "force-sensor"), (r"\bDRV8833\b", "DRV8833 driver")]


def prep_sketch(text, crop):
    top = 56
    text = re.sub(r'<text x="16" y="(?:26|44)"[^>]*>.*?</text>\s*', "", text, flags=re.S)
    b = re.search(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)" fill="#f9fafb"[^>]*/>\s*', text)
    if b:
        bx, by, bw, bh = map(float, b.groups())
        text = text.replace(b.group(0), "")
        text = re.sub(r'<text x="([-\d.]+)" y="([-\d.]+)"[^>]*>.*?</text>\s*',
                      lambda q: "" if bx <= float(q.group(1)) <= bx + bw and by <= float(q.group(2)) <= by + bh else q.group(0), text, flags=re.S)
    for a, r in SKETCH_SUBS:
        text = re.sub(a, r, text)
    w, bottom = crop
    return re.sub(r'viewBox="0 0 [\d.]+ [\d.]+" width="[\d.]+" height="[\d.]+"', 'viewBox="0 %d %d %d" width="%d" height="%d"' % (top, w, bottom - top, w, bottom - top), text, count=1)


for n, crop in SKETCH_CROP.items():
    raw = IMG[n].read_text(encoding="utf-8").replace("\r\n", "\n")
    D["img"][n] = "data:image/svg+xml;base64," + base64.b64encode(prep_sketch(raw, crop).encode("utf-8")).decode()

# ---- camera
cam = J(RES / "camera.json")
D["cam"] = clean([[r["placement"], r["kind"], r["camera"], r.get("feed_crit_visible_min"), r.get("ppm_crit_min"), r.get("pass_feed"), r.get("pass_approach"), (r.get("mass") or {}).get("total_g"), r.get("score")] for r in cam["all"]], 3)
D["cam_mount"] = clean(cam["mount"], 3)
D["cam_top"] = clean(cam["ranking_top20"][:10], 3)

# ---- firmware and controls (W2b-1): simulation, proving gates, transition table from controls.md
fws = J(ROOT / "analysis/gripper/firmware_sim/results/fw_sim.json")
gates = J(ROOT / "analysis/gripper/firmware_sim/results/gates.json")
ctl = (ROOT / "docs/gripper/analysis/controls.md").read_text(encoding="utf-8")
tbl = ctl.split("<!-- table:begin -->")[1].split("<!-- table:end -->")[0]
rows, touts = [], []
for line in tbl.splitlines():
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) == 7 and cells[0].isdigit():
        rows.append([cells[1], cells[2], cells[3] == "yes", cells[5], cells[6]])
    elif len(cells) == 2 and cells[1].isdigit():
        touts.append([cells[0], int(cells[1])])
rev = ctl.split("<!-- review:begin -->")[1].split("<!-- review:end -->")[0].strip() if "<!-- review:begin -->" in ctl else ""
m = re.search(r"\*\*Verdict: ([A-Za-z]+)", rev)
SER = fws["series"]
D["fw"] = clean({
    "cases": fws["cases"], "sweep": fws["sweep_k"], "noise": fws["noise"], "steps": fws["steps"],
    "faults": {k: {kk: v[kk] for kk in ("F_max_N", "final_state")} for k, v in fws["sensor_faults"].items()},
    "derived": fws["derived"], "config": fws["config"],
    "ser": {k: {kk: ds(v[kk], 250) for kk in v} for k, v in SER.items()},
    "gates": gates, "table": rows, "timeouts": touts, "verdict": m.group(1) if m else None,
}, 3)

# ---- params excerpts
pj = J(ROOT / "cad/gripper/params.json")
D["params"] = clean({k: pj.get(k) for k in ("gear", "motion", "grip", "servo", "wrist_mount", "camera_pad") if k in pj}, 4)

# ---- meshes
ctx = J(SP / "so101_context.json")
D["ctx"] = ctx
glb = base64.b64encode((ROOT / "cad/gripper/out/web/gripper_closed.glb").read_bytes()).decode()
ctxb = base64.b64encode((SP / "so101_context.bin").read_bytes()).decode()

data_js = json.dumps(D, separators=(",", ":"), allow_nan=False, sort_keys=True).replace("</", "<" + chr(92) + "/")
# fragments, in order: 1 style, 2-4 markup, 5 data + shell, 6 the 3D engine and model view, 11 fit check, 12 parts, 13 assembly, 7-8 and 10 view scripts (10 is firmware and controls), 9 last because it starts the page
FRAGS = ["vw_%d.html" % i for i in (1, 2, 3, 4, 5, 6, 11, 12, 13, 7, 8, 10, 9)]
html = "".join((SP / f).read_text(encoding="utf-8").replace("\r\n", "\n") for f in FRAGS)
html = html.replace("/*__DATA__*/", "const D=" + data_js + ";")
html = html.replace("__GLB_B64__", glb).replace("__CTX_B64__", ctxb)
OUT.write_text(html, encoding="utf-8", newline="\n")
print("data KB", len(data_js) // 1024, "glb KB", len(glb) // 1024, "ctx KB", len(ctxb) // 1024, "total MB", round(len(html.encode()) / 1e6, 2))
print("gear pts", {k: (v["n_src"], len(v["pts"])) for k, v in prof.items() if k.startswith("G")})
print("fea meshes", [k for k in fea if k.startswith("m")])
