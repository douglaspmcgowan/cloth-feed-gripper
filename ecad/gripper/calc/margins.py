"""Machine-readable ordering gate for every quantified electrical requirement."""

import re
from pathlib import Path

import _common as cm
import buck_design
import droop_sim
import fault_limit
import fsr_frontend
import harness
import ina219_budget
import margin_inputs
import power_budget
import trace_width

FW = Path(cm.REPO) / "firmware/gripper/config.h"
UNEVIDENCED = "margin positive, uncertainty not evidenced"
STATUSES = ("met", "at risk", "not met", "not evidenced", "not met pending measurement", UNEVIDENCED)
COMBINATION_RULE = "worst-case sum of absolute endpoint sensitivities"


def firmware_value(name, root=None):
    path = Path(root, "firmware/gripper/config.h") if root else FW
    match = re.search(
        r"^#define\s+" + re.escape(name) + r"\s+([0-9.]+)", path.read_text(encoding="utf-8"), re.M
    )
    if not match:
        raise ValueError("missing firmware constant " + name)
    return float(match.group(1))


def _loop_case(case):
    return (
        "Vin {vin:g} V, load {iload:g} A, bulk x{cb_scale:g}, ceramic x{cer_factor:g}, "
        "ESR {esr_b:g} ohm, crossover {fc:.0f} Hz"
    ).format(**case)


def validate_input_class(item):
    """Reject generic missing evidence and false exact classifications."""
    constant = item.get("constant")
    if item.get("class") == "exact" and constant and constant.endswith("_tol"):
        raise AssertionError("%s is a tolerance and cannot be exact" % constant)
    if item.get("class") == "missing":
        required = ("part", "parameter", "where")
        absent = [name for name in required if not item.get(name)]
        if absent:
            raise AssertionError("missing entry lacks %s" % ", ".join(absent))
        if "quote or measure the error band" in item.get("source", ""):
            raise AssertionError("generic missing entry is forbidden")
    return True


def validate_uncertainty(row):
    """Reject stored uncertainty that is not reproduced by its components."""
    components = row["uncertainty_components"]
    for item in components:
        validate_input_class(item)
    missing = [item for item in components if item["band"] is None]
    for item in components:
        recompute = item.get("recompute")
        if recompute and recompute["operation"] == "fraction_of":
            expected_sensitivity = recompute["nominal"] * max(abs(x) for x in item["band"])
            if item["sensitivity"] != expected_sensitivity:
                raise AssertionError(
                    "%s sensitivity does not equal endpoint recomputation for %s" % (row["id"], item["input"])
                )
    expected = sum(abs(item["sensitivity"]) for item in components if item["band"] is not None)
    if row["uncertainty"] != expected:
        raise AssertionError("%s uncertainty does not equal its endpoint sensitivities" % row["id"])
    if not components and not row["extreme_inputs"]:
        raise AssertionError("%s has neither uncertainty components nor extreme inputs" % row["id"])
    declared = set(row.get("declared_inputs", ()))
    recorded = set(row.get("recorded_inputs", ()))
    if declared != recorded:
        absent = sorted(recorded - declared)
        extra = sorted(declared - recorded)
        raise AssertionError("%s input set differs; missing %s; extra %s" % (row["id"], absent, extra))
    return True



def _source_tag(name):
    return cm.K.C[name]["tag"] if name in cm.K.C else None


def _row(
    key,
    quantity,
    limit,
    demand,
    unit,
    case,
    source,
    uncertainty=None,
    pending=None,
    action=None,
    components=None,
    extremes=None,
):
    with margin_inputs.pending_recording() as observed:
        pass
    margin = limit - demand
    if components is None:
        components = [margin_inputs.missing_component(source)]
    missing = [item["source"] for item in components if item["band"] is None]
    known = [item for item in components if item["band"] is not None]
    uncertainty_value = sum(abs(item["sensitivity"]) for item in known)
    if margin < 0:
        status = "not met pending measurement" if missing or pending else "not met"
    elif missing:
        status = UNEVIDENCED
    elif margin < uncertainty_value:
        status = "at risk"
    else:
        status = "met"
    observed_inputs, modules = margin_inputs.consume_modules(observed)
    observed_inputs = sorted(observed_inputs)
    if not observed_inputs:
        raise AssertionError("%s has zero observed inputs" % key)
    observed_evidence = {name: dict(margin_inputs.evidence(name), source_tag=_source_tag(name))
                         for name in observed_inputs}
    observed_missing = [name for name in observed_inputs
                        if observed_evidence[name]["class"] == "missing"]
    observed_unclassified = [name for name in observed_inputs
                             if observed_evidence[name]["class"] == "unclassified"]
    for name in observed_missing:
        item = observed_evidence[name]
        message = "%s — %s; find in %s" % (
            item["part"], item["parameter"], item["where"])
        if message not in missing:
            missing.append(message)
    if observed_missing and status == "met":
        status = UNEVIDENCED
    if observed_unclassified:
        missing.extend("unclassified: " + name for name in observed_unclassified)
        if status == "met":
            status = UNEVIDENCED
    return {
        "id": key,
        "quantity": quantity,
        "limit": limit,
        "demand": demand,
        "unit": unit,
        "case": case,
        "scenario": case,
        "source": source,
        "margin": margin,
        "uncertainty": uncertainty_value,
        "uncertainty_source": "; ".join(item["source"] for item in components),
        "uncertainty_components": components,
        "observed_inputs": observed_inputs,
        "input_evidence": observed_evidence,
        "modules_read": modules,
        "combination": COMBINATION_RULE,
        "extreme_inputs": extremes or [],
        "missing_figures": missing,
        "status": status,
        "action": action or (pending or ("; ".join(missing) if missing else "none")),
    }


def _requirement_family_1(pb, bd, ds, fs, ina, tr, hr, root, overrides, worst, stall, drop, trip, force):
    return [
        _row(
            "input-fuse-hold",
            "fuse hold current",
            cm.v("f1_hold"),
            worst["iin_A"],
            "A",
            "Fit A worst input",
            "f1_hold",
            components=[
                {
                    "input": "F1 MF-MSMF260/16X hold-current tolerance at 25 C",
                    "class": "missing",
                    "band": None,
                    "source": "missing: F1 MF-MSMF260/16X — hold-current tolerance at 25 C; "
                    "find in datasheet electrical characteristics table",
                    "sensitivity": None,
                    "part": "F1 MF-MSMF260/16X",
                    "parameter": "hold-current tolerance at 25 C",
                    "where": "datasheet electrical characteristics table",
                }
            ],
            extremes=[
                {
                    "input": "defined Fit A input scenarios",
                    "class": "evaluated at extreme",
                    "extreme": "maximum input current",
                    "reason": "finite design scenario set",
                }
            ],
        ),
        _row(
            "input-fuse-trip",
            "fuse trip current",
            cm.v("f1_trip"),
            worst["iin_A"],
            "A",
            "Fit A worst input",
            "f1_trip",
        ),
        _row(
            "buck-current-limit",
            "minimum switch limit",
            cm.v("tps_ilim_min"),
            drop["ipeak_max_A"],
            "A",
            "Fit A fastest stall step",
            "tps_ilim_min",
        ),
    ]


def _requirement_family_2(pb, bd, ds, fs, ina, tr, hr, root, overrides, worst, stall, drop, trip, force):
    return [
        _row(
            "buck-thermal",
            "junction-rise allowance",
            cm.v("buck_junction_rise_limit_c"),
            stall["U1_rise_K"],
            "C",
            "Fit A stall at 12 V",
            "R26",
        ),
        _row(
            "trace-current",
            "wide trace current",
            overrides.get("trace_current_A", tr["max_current_A_at_10C"]["wide"]),
            margin_inputs.read("trace_demand_A"),
            "A",
            "Fit A stall",
            "trace_width",
        ),
        _row(
            "trace-neck-current",
            "pad-neck current",
            tr["max_current_A_at_10C"]["neck"],
            margin_inputs.read("trace_demand_A"),
            "A",
            "Fit A stall",
            "trace_width",
            pending="measure duration",
            action="verify transient heating or widen neck",
        ),
    ]


def _requirement_family_3(pb, bd, ds, fs, ina, tr, hr, root, overrides, worst, stall, drop, trip, force):
    return [
        _row(
            "trace-temperature",
            "wide trace temperature rise",
            cm.v("trace_temp_rise_limit_c"),
            tr["rise_C"]["wide_stall"],
            "C",
            "Fit A stall",
            "trace_width",
        ),
        _row(
            "trace-drop",
            "servo path drop",
            cm.v("trace_servo_drop_limit_mv"),
            tr["board"]["servo_path_drop_mV_at_stall_upper"],
            "mV",
            "Fit A stall",
            "trace_width",
        ),
        _row(
            "shunt-power",
            "shunt rating",
            cm.v("rs1_rating"),
            stall["RS1_W"],
            "W",
            "Fit A stall at 12 V",
            "rs1_rating",
            components=[
                {
                    "input": "RS1 resistance tolerance",
                    "class": "quoted",
                    "constant": "rs1_tol",
                    "band": [-cm.v("rs1_tol"), cm.v("rs1_tol")],
                    "source": "constants.py:138, RS1 0.1 ohm 1 percent design value",
                    "sensitivity": stall["RS1_W"] * cm.v("rs1_tol"),
                    "recompute": {
                        "operation": "fraction_of",
                        "nominal": stall["RS1_W"],
                    },
                }
            ],
            extremes=[
                {
                    "input": "Fit A stall current at 12 V",
                    "class": "evaluated at extreme",
                    "extreme": "maximum dissipation scenario",
                    "reason": "finite fitted motor scenario set",
                }
            ],
        ),
    ]


def _requirement_family_4(pb, bd, ds, fs, ina, tr, hr, root, overrides, worst, stall, drop, trip, force):
    return [
        _row(
            "sense-range", "current full scale", ina["shunt_fs_A"], margin_inputs.read("trace_demand_A"), "A", "Fit A stall", "ina219_budget"
        ),
        _row(
            "current-error",
            "current-reading error budget",
            cm.v("ina_current_error_limit_a"),
            ina["budget"]["worst_A"],
            "A",
            "worst-case trip reading",
            "ina219_budget",
        ),
        _row(
            "detection-time",
            "stall-detection deadline",
            ina["delay"]["r20_limit_s"],
            ina["delay"]["max_s"],
            "s",
            "five-sample window",
            "ina219_budget",
        ),
    ]


def _requirement_family_5(pb, bd, ds, fs, ina, tr, hr, root, overrides, worst, stall, drop, trip, force):
    return [
        _row(
            "fsr-node-high",
            "ADC high linear limit",
            cm.v("esp_adc_max_mv"),
            cm.node_mv(force),
            "mV",
            f"{force:g} N firmware cap",
            "esp_adc_max_mv",
        ),
        _row(
            "force-reading-error",
            "force-reading error",
            cm.v("harness_force_error_limit_n"),
            max(abs(x["err_N"]) for x in hr["signal"]["fsr_error"]),
            "N",
            "8 N harness wire error",
            "harness",
        ),
        _row(
            "adc-charge",
            "ADC reservoir droop",
            cm.v("fsr_adc_droop_limit_mv"),
            fs["adc"]["reservoir_droop_mV_at_2450"],
            "mV",
            "2450 mV ADC input",
            "fsr_frontend",
        ),
    ]


def _requirement_family_6(pb, bd, ds, fs, ina, tr, hr, root, overrides, worst, stall, drop, trip, force):
    return [
        _row(
            "filter-delay",
            "filter delay budget",
            cm.v("ctrl_lag_budget_s"),
            fs["filter_delay_worst_s"],
            "s",
            "open FSR worst RC",
            "fsr_frontend",
        ),
        _row(
            "firmware-trip-10N",
            "firmware trip current",
            trip,
            ina["hold"][10.0]["A"]["with_offset_A"],
            "A",
            "10 N cap Fit A",
            "R20",
        ),
        _row(
            "firmware-trip-8N",
            "firmware trip current",
            trip,
            ina["hold"][8.0]["A"]["with_offset_A"],
            "A",
            "8 N cap Fit A",
            "R20",
        ),
    ]


def _requirement_family_7(pb, bd, ds, fs, ina, tr, hr, root, overrides, worst, stall, drop, trip, force):
    return [
        _row(
            "adapter-current",
            "adapter current",
            overrides.get("adapter_current_A", cm.v("adapter_current_a")),
            pb["adapter"]["rating_with_25pct_margin_A"],
            "A",
            "Fit A worst plus 25 percent",
            "power_budget",
        ),
        _row(
            "droop-servo-min",
            "servo minimum",
            drop["plug_min_V"],
            cm.v("servo_vmin"),
            "V",
            "Fit A fastest stall step",
            "droop_sim",
        ),
        _row(
            "servo-voltage-max",
            "servo maximum",
            cm.v("servo_vmax"),
            max(buck_design.setpoint_range()),
            "V",
            "idle high setpoint",
            "buck_design",
            components=[],
            extremes=[
                {
                    "input": "U1 reference minimum/maximum and R6/R7 0.1 percent tolerances",
                    "class": "evaluated at extreme",
                    "extreme": "maximum set-point corner",
                    "reason": "buck_design.setpoint_range evaluates all endpoints",
                }
            ],
        ),
    ]


def _requirement_family_8(pb, bd, ds, fs, ina, tr, hr, root, overrides, worst, stall, drop, trip, force):
    return [
        _row(
            "plug-band-low",
            "plug lower calibration edge",
            hr["servo_20awg"]["cases"][0]["plug_low_V"],
            cm.v("harness_plug_band_v")[0],
            "V",
            "Fit A hold low setpoint",
            "harness",
        ),
        _row(
            "plug-band-high",
            "plug upper calibration edge",
            cm.v("harness_plug_band_v")[1],
            hr["servo_20awg"]["cases"][0]["plug_high_V"],
            "V",
            "Fit A hold high setpoint",
            "harness",
        ),
        _row(
            "loop-phase",
            "phase margin",
            bd["worst_pm"],
            cm.v("buck_phase_margin_min_deg"),
            "deg",
            _loop_case(bd["worst_pm_case"]),
            "buck_design",
        ),
    ]


def _requirement_family_9(pb, bd, ds, fs, ina, tr, hr, root, overrides, worst, stall, drop, trip, force):
    return [
        _row(
            "loop-gain",
            "gain margin",
            bd["worst_gm"],
            cm.v("buck_gain_margin_min_db"),
            "dB",
            _loop_case(bd["worst_gm_case"]),
            "buck_design",
        ),
        _row(
            "uvlo-range",
            "UVLO start below adapter minimum",
            cm.v("adapter_min_v"),
            bd["uvlo_start_range_V"][1],
            "V",
            "UVLO upper tolerance",
            "buck_design",
        ),
        _row(
            "regulator-headroom",
            "5 V regulator input headroom",
            pb["esp_stall_vbuck_min"],
            pb["ldo_min_input_V"],
            "V",
            "Fit A stall minimum buck",
            "power_budget",
        ),
    ]


def _requirement_family_10(pb, bd, ds, fs, ina, tr, hr, root, overrides, worst, stall, drop, trip, force):
    return [
        _row(
            "limit-switch-low",
            "input-low threshold",
            hr["signal"]["limit_vil_mV"],
            hr["signal"]["limit_low_mV"],
            "mV",
            "closed limit switch",
            "harness",
        ),
    ]


def _requirement_rows(pb, bd, ds, fs, ina, tr, hr, root, overrides):
    worst = max(pb["input"], key=lambda x: x["iin_A"])
    stall = max(
        x for x in pb["dissipation"] if x["fit"] == "A" and x["scenario"] == "stall" and x["vin"] == 12.0
    )
    drop = min(ds["cases"], key=lambda x: x["plug_min_V"])
    trip = firmware_value("STALL_CURRENT_A", root)
    force = firmware_value("F_CAP_N", root)
    args = (pb, bd, ds, fs, ina, tr, hr, root, overrides, worst, stall, drop, trip, force)
    rows = []
    rows.extend(_requirement_family_1(*args))
    rows.extend(_requirement_family_2(*args))
    rows.extend(_requirement_family_3(*args))
    rows.extend(_requirement_family_4(*args))
    rows.extend(_requirement_family_5(*args))
    rows.extend(_requirement_family_6(*args))
    rows.extend(_requirement_family_7(*args))
    rows.extend(_requirement_family_8(*args))
    rows.extend(_requirement_family_9(*args))
    rows.extend(_requirement_family_10(*args))
    for case in pb["bulk"]["regen"]:
        energy = case.get("energy_mJ", case.get("returned_mJ", 0))
        rows.append(
            _row(
                "regen-energy-%gmJ" % energy,
                "returned-energy voltage",
                cm.v("servo_vmax"),
                case["v_peak_V"],
                "V",
                "%g mJ returned energy" % energy,
                "power_budget",
                pending="validate returned energy",
                action="measure returned energy",
            )
        )
    return rows


def run(overrides=None, root=None):
    old = {}
    for key, value in (overrides or {}).items():
        if key in cm.K.C:
            old[key] = cm.K.C[key]["value"]
            cm.K.C[key]["value"] = value
    try:
        pb = margin_inputs.capture_module("power_budget", power_budget.run)
        bd = margin_inputs.capture_module("buck_design", buck_design.run)
        ds = margin_inputs.capture_module("droop_sim", droop_sim.run)
        fs = margin_inputs.capture_module("fsr_frontend", fsr_frontend.run)
        ina = margin_inputs.capture_module("ina219_budget", ina219_budget.run)
        tr = margin_inputs.capture_module("trace_width", trace_width.run)
        hr = margin_inputs.capture_module("harness", harness.run)
        margin_inputs._PENDING.clear()
        margin_inputs.validate_registry(root or cm.REPO)
        rows = _requirement_rows(pb, bd, ds, fs, ina, tr, hr, root, overrides or {})
        for row in rows:
            validate_uncertainty(row)
        faults = [fault_limit.analyze()]
        counts = {status: sum(x["status"] == status for x in rows + faults) for status in STATUSES}
        return {"rows": rows, "faults": faults, "counts": counts}
    finally:
        for key, value in old.items():
            cm.K.C[key]["value"] = value


def report(result):
    cols = [
        [x[k] for k in ("id", "limit", "demand", "margin", "unit", "uncertainty", "status", "case")]
        for x in result["rows"]
    ]
    print(cm.table(cols, ["id", "limit", "demand", "margin", "unit", "uncertainty", "status", "case"]))
    print("counts:", result["counts"])


def _uncertainty_text(row):
    value = "%.7g" % row["uncertainty"]
    if not row.get("missing_figures"):
        return value
    count = len(row["missing_figures"])
    return "known subtotal %s; %d band(s) missing" % (value, count)


def _component_text(row):
    parts = []
    for item in row.get("uncertainty_components", []):
        band = "missing band" if item["band"] is None else str(item["band"])
        parts.append("%s: %s (%s)" % (item["input"], band, item["source"]))
    if not parts:
        return "none; demand already evaluated at listed extremes"
    return "; ".join(parts)


def _display_number(value):
    """Apply the repository's seven-significant-figure storage rule before display."""
    return value if isinstance(value, str) else float(format(value, ".7g"))


def order_block(result):
    rows = result.get("rows")
    faults = result.get("faults")
    if not isinstance(rows, list):
        raise AssertionError("required rows register is missing")
    if not isinstance(faults, list):
        raise AssertionError("required faults register is missing")
    limit_faults = [row for row in faults if row.get("id") == "fault-limit-servo"]
    if not limit_faults:
        raise AssertionError("required fault row fault-limit-servo is missing")
    if len(limit_faults) != 1:
        raise AssertionError("required fault row fault-limit-servo is duplicated")
    for index, row in enumerate(faults + rows):
        row_id = row.get("id", "row %d" % index)
        assert "status" in row, "%s status is missing" % row_id
        assert "action" in row, "%s action is missing" % row_id
        unclassified = [name for name, item in row.get("input_evidence", {}).items()
                        if item.get("class") == "unclassified"]
        if unclassified and row["status"] == "met":
            raise AssertionError("%s is met with unclassified inputs" % row_id)
        if row in faults and (not row.get("parts") or not row.get("branches")):
            raise AssertionError("%s has status but no computed parts and branches" % row_id)
        if row in faults and row["status"] == "met":
            open_parts = [part["part"] for part in row["parts"] if part["verdict"] != "met"]
            if open_parts:
                raise AssertionError(
                    "%s on %s cannot be met; unprotected or unevidenced %s"
                    % (row_id, row["entry"]["net"], ", ".join(open_parts))
                )
    blocking = ("at risk", "not met", "not evidenced", "not met pending measurement", UNEVIDENCED)
    open_rows = [x for x in rows + faults if x["status"] in blocking]
    state = "DO NOT ORDER" if open_rows else "ORDER GATE PASSED"
    lines = [
        "<!-- ORDER-STATUS:BEGIN -->",
        "## Order status — " + state,
        "",
        "Input provenance uses per-module read granularity; each row lists modules read in margins.json.",
        "",
    ]
    for row in open_rows:
        missing = row.get("missing_figures", [])
        detail = row["action"]
        if missing and "; ".join(missing) not in detail:
            clean = [item.removeprefix("missing: ") for item in missing]
            detail += "; missing: " + "; ".join(clean)
        lines.append("- `%s`: %s" % (row["id"], detail))
    groups = {}
    unclassified = {}
    for row in rows:
        for item in row.get("uncertainty_components", []):
            if item.get("class") == "missing":
                key = (item["part"], item["parameter"])
                groups.setdefault(key, {"method": "datasheet lookup", "rows": set(), "where": set()})
                groups[key]["where"].add(item["where"])
                groups[key]["rows"].add(row["id"])
        for item in row.get("input_evidence", {}).values():
            if item.get("class") == "missing":
                key = (item["part"], item["parameter"])
                groups.setdefault(key, {"method": item["method"], "rows": set(), "where": set()})
                groups[key]["where"].add(item["where"])
                groups[key]["rows"].add(row["id"])
        for name, item in row.get("input_evidence", {}).items():
            if item.get("class") == "unclassified":
                unclassified.setdefault(name, set()).add(row["id"])
    if groups:
        lines += ["", "### Missing figures by part", ""]
        for key, detail in sorted(groups.items()):
            part, parameter = key
            location = "; ".join(sorted(detail["where"]))
            lines.append("- **%s:** %s — %s; %s; blocks %s" % (
                part, parameter, location, detail["method"],
                ", ".join(sorted(detail["rows"]))))
    if unclassified:
        lines += ["", "### Unclassified inputs", ""]
        for name, blocked_rows in sorted(unclassified.items()):
            lines.append("- **%s:** blocks %s" % (name, ", ".join(sorted(blocked_rows))))
    lines += ["", "Uncertainties combine by " + COMBINATION_RULE + ".", ""]
    lines.append("| id | margin | uncertainty | components | status |")
    lines.append("|---|---:|---:|---|---|")
    for row in rows:
        lines.append(
            "| %s | %.7g %s | %s | %s | %s |"
            % (
                row["id"],
                row["margin"],
                row["unit"],
                _uncertainty_text(row),
                _component_text(row).replace("|", "\\|"),
                row["status"],
            )
        )
    lines += ["", "### Computed faults", ""]
    lines.append("| id | entry | applied | part | current | power | rating | verdict |")
    lines.append("|---|---|---:|---|---:|---:|---|---|")
    for fault in faults:
        for item in fault["parts"]:
            rating = item["rating"]
            lines.append(
                "| %s | %s | %.6g V | %s | %.6g A | %s W | %s (%s) | %s |"
                % (
                    fault["id"], fault["entry"]["net"], fault["source"]["voltage_V"],
                    item["part"], _display_number(item["current_A"]),
                    _display_number(item["power_W"]), rating["value"],
                    rating["source"], item["verdict"],
                )
            )
    proposal = fault_limit.proposed()
    lines += ["", "#### Proposed in-memory protection", ""]
    lines.append("| entry | part | current | power | rating | verdict |")
    lines.append("|---|---|---:|---:|---|---|")
    for item in proposal["parts"]:
        rating = item["rating"]
        lines.append(
            "| %s | %s | %.6g A | %s W | %s (%s) | %s |"
            % (proposal["entry"]["net"], item["part"], _display_number(item["current_A"]),
               _display_number(item["power_W"]), rating["value"], rating["source"], item["verdict"])
        )
    timing = proposal["timing"]
    lines.append("")
    lines.append(
        "Closed low %.6g V against %.6g V VIL; close tau %.6g s; release tau %.6g s."
        % (timing["closed_low_V"], timing["input_low_threshold_V"], timing["close_tau_s"],
           timing["release_tau_s"])
    )
    lines.append("<!-- ORDER-STATUS:END -->")
    return "\n".join(lines)


def generated_blocks(result=None):
    result = result or run()
    fitted = cm.ELEC["r_fsr_fixed_ohm"]
    front = fsr_frontend.run()
    lines = ["<!-- R15-CHOICE:BEGIN -->", "**R15 force-cap choice:**"]
    for cap in (10.0, 8.0):
        row = front["caps"][cap]
        node = cm.node_mv(cap, fitted)
        lines.append(
            "- %.0f N: fitted %.2f kohm gives %.1f mV (%+.1f mV to the %.0f mV linear limit); best E96 is %.2f kohm at %.1f mV."
            % (
                cap,
                fitted / 1000,
                node,
                cm.v('fsr_adc_max_mv') - node,
                cm.v('fsr_adc_max_mv'),
                row["r_e96_ohm"] / 1000,
                row["node_at_cap_e96_mV"],
            )
        )
    recommendations = "; ".join(
        "%.2f kohm for %.0f N" % (front["caps"][cap]["r_e96_ohm"] / 1000, cap) for cap in (10.0, 8.0)
    )
    lines += [
        "Fit R15 for the selected force cap (%s), and set firmware `R_FSR_FIXED_OHM` to the same resistance."
        % recommendations,
        "<!-- R15-CHOICE:END -->",
    ]
    return order_block(result), "\n".join(lines)


def replace_block(text, marker, replacement):
    begin = "<!-- %s:BEGIN -->" % marker
    end = "<!-- %s:END -->" % marker
    if text.count(begin) != 1 or text.count(end) != 1 or text.index(begin) > text.index(end):
        raise ValueError("expected exactly one ordered %s marker pair" % marker)
    return text[: text.index(begin)] + replacement + text[text.index(end) + len(end) :]


def render_note(text, result=None):
    order, r15 = generated_blocks(result)
    return replace_block(replace_block(text, "ORDER-STATUS", order), "R15-CHOICE", r15)
