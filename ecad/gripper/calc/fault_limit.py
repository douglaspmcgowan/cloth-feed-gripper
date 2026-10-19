"""Nodal limit-lead cross-fault analysis derived from the board net model."""

import copy

import numpy as np

import _common as cm
import buck_design
import harness
import netmodel

FAULT_ID = "fault-limit-servo"
NOT_QUOTED = "not quoted"
SCENARIO = {"connector": "J4", "pin": 3, "proposed_ref": "R25", "proposed_net": "LIM_RAW"}
# Fixed-voltage boundaries used by the present conservative model.
SINK_BOUNDS = {
    "ground": (0.0, "ESD clamp return"),
    "controller": (0.0, "controller injection-current worst case"),
    "rail": (3.3, "regulated rail upper bound"),
}
# Symbol roles are topology, never circuit-specific net or reference names.
ROLE_TABLE = {
    "Device:R": "resistor",
    "Device:C": "open",
    "Device:C_Polarized": "open",
    "Device:D_TVS": "clamp",
    "controller_supply_pin": "1",
}
RATING_SOURCES = {
    "resistor": "repository has no continuous-power quote",
    "clamp": "repository has no continuous-current or clamp-power quote",
    "controller": "repository has no controller injection-current quote",
    "rail": "repository has no 3.3 V rail sink-current quote",
}

def _round(value):
    return float(format(value, ".7g"))

def _role(part):
    role = ROLE_TABLE.get(part["sym"])
    if role:
        return role
    if part["ref"] == SCENARIO["connector"] or part["sym"].startswith("Connector"):
        return "terminal"
    if part["sym"].startswith("gripper:ESP32"):
        return "controller"
    if part.get("virtual") or part["sym"].startswith("power:"):
        return "terminal"
    return None

def _network(model, source_net):
    reached = {source_net}
    elements = []
    pending = [source_net]
    while pending:
        net = pending.pop()
        controllers = [p for p in model.touching(net) if _role(p) == "controller"]
        if controllers:
            part = controllers[0]
            pin = next(key for key, value in part["pins"].items() if value == net)
            role = "rail" if pin == ROLE_TABLE["controller_supply_pin"] else "controller"
            elements.append((part, role, net, None))
            continue
        for part in model.touching(net):
            role = _role(part)
            if role in ("open", "terminal"):
                continue
            if role is None:
                raise ValueError("unknown part kind %s on reached net %s" % (part["ref"], net))
            nets = list(dict.fromkeys(part["pins"].values()))
            if role == "controller":
                pin = next(key for key, value in part["pins"].items() if value == net)
                sink_role = "rail" if pin == ROLE_TABLE["controller_supply_pin"] else role
                elements.append((part, sink_role, net, None))
                continue
            if len(nets) != 2:
                raise ValueError("part %s on net %s is not two-terminal" % (part["ref"], net))
            other = nets[1] if nets[0] == net else nets[0]
            item = (part, role, net, other)
            if not any(old[0]["ref"] == part["ref"] for old in elements):
                elements.append(item)
            if role == "resistor" and other not in reached:
                reached.add(other)
                pending.append(other)
    return reached, elements

def _boundaries(elements, source_net):
    bounds = {}
    sinks = {}
    for part, role, first, second in elements:
        if role == "clamp":
            clamp_net = first
            if clamp_net != source_net:
                bounds[clamp_net] = SINK_BOUNDS["ground"][0]
            sinks[part["ref"]] = ("clamp", clamp_net)
        elif role in ("controller", "rail"):
            bounds[first] = SINK_BOUNDS[role][0]
            name = "controller pin" if role == "controller" else "+3V3 rail"
            sinks[name] = (role, first)
    return bounds, sinks

def _solve(model, source_net, voltage):
    reached, elements = _network(model, source_net)
    bounds, sinks = _boundaries(elements, source_net)
    bounds[source_net] = voltage
    if not sinks:
        raise ValueError("network from net %s has no path to any sink" % source_net)
    resistors = [item for item in elements if item[1] == "resistor"]
    unknown = sorted(reached - set(bounds))
    matrix = np.zeros((len(unknown), len(unknown)))
    vector = np.zeros(len(unknown))
    index = {net: pos for pos, net in enumerate(unknown)}
    for part, _, first, second in resistors:
        conductance = 1.0 / netmodel.resistance_ohm(part["value"])
        for here, there in ((first, second), (second, first)):
            if here not in index:
                continue
            matrix[index[here], index[here]] += conductance
            if there in index:
                matrix[index[here], index[there]] -= conductance
            else:
                vector[index[here]] += conductance * bounds[there]
    try:
        solved = np.linalg.solve(matrix, vector) if unknown else []
    except np.linalg.LinAlgError as exc:
        raise ValueError("singular system from net %s" % source_net) from exc
    nodes = dict(bounds)
    nodes.update({net: float(solved[index[net]]) for net in unknown})
    return nodes, resistors, sinks, unknown

def _rating(part, role, fixtures):
    if part in fixtures:
        return fixtures[part]
    return {"value": NOT_QUOTED, "unit": "A or W", "source": RATING_SOURCES[role]}

def _stress(part, current, power, rating, stress_type="branch"):
    value = rating["value"]
    demand = power if rating.get("unit") == "W" else current
    verdict = "not evidenced" if value == NOT_QUOTED else ("met" if demand < value else "not met")
    return {"part": part, "current_A": _round(abs(current)), "power_W": power,
            "power_basis": stress_type, "rating": rating, "verdict": verdict}

def analyze(model=None, applied_v=None, current_limit_a=None, ratings=None):
    model = model or netmodel.NetModel()
    fixtures = ratings or {}
    voltage = _round(applied_v if applied_v is not None else max(buck_design.setpoint_range()))
    limit = _round(current_limit_a if current_limit_a is not None else cm.v("tps_ilim_min"))
    try:
        entry = model.connector_net(SCENARIO["connector"], SCENARIO["pin"])
    except KeyError as exc:
        raise ValueError("entry pin J4.3 is on no net") from exc
    if not entry:
        raise ValueError("entry pin J4.3 is on no net")
    nodes, resistors, sinks, unknown = _solve(model, entry, voltage)
    stresses = []
    branches = []
    for part, _, first, second in resistors:
        current = (nodes[first] - nodes[second]) / netmodel.resistance_ohm(part["value"])
        power = current * current * netmodel.resistance_ohm(part["value"])
        stresses.append(_stress(part["ref"], current, _round(power),
                                _rating(part["ref"], "resistor", fixtures)))
        branches.append({"part": part["ref"], "from": first, "to": second,
                         "current_A": _round(current)})
    source_limited = []
    for name, (role, net) in sinks.items():
        incoming = sum(-b["current_A"] if b["from"] == net else b["current_A"]
                       for b in branches if net in (b["from"], b["to"]))
        direct = net == entry and role == "clamp"
        current = limit if direct else incoming
        basis = "source-limited" if direct else "branch"
        if direct:
            source_limited.append(name)
        power = "not evidenced" if role == "clamp" else 0.0
        stresses.append(_stress(name, current, power, _rating(name, role, fixtures), basis))
    return _record(model, entry, voltage, limit, nodes, branches, stresses, source_limited, unknown)

def _record(model, entry, voltage, limit, nodes, branches, stresses, source_limited, unknown):
    stresses.sort(key=lambda item: item["part"] not in source_limited)
    status = "met" if all(x["verdict"] == "met" for x in stresses) and not source_limited else "not evidenced"
    unresolved = [x["part"] for x in stresses if x["verdict"] != "met"] + source_limited
    return {"id": FAULT_ID, "fault": "limit lead crossed to servo power",
            "entry": {"connector": SCENARIO["connector"], "pin": str(SCENARIO["pin"]),
                      "net": entry, "parts": [p["ref"] for p in model.touching(entry)]},
            "source": {"voltage_V": voltage, "current_limit_A": limit,
                       "power_bound_W": _round(voltage * limit),
                       "description": "servo rail; current bounded by U1 source limit"},
            "nodes_V": {key: _round(value) for key, value in sorted(nodes.items())},
            "kcl_A": {net: _round(sum(
                branch["current_A"] if branch["to"] == net else -branch["current_A"]
                for branch in branches if net in (branch["from"], branch["to"])
            )) for net in unknown},
            "branches": branches, "parts": stresses, "source_limited": source_limited,
            "status": status, "action": "protect J4 pin 3; resolve: " + ", ".join(dict.fromkeys(unresolved)),
            "missing_figures": [x["rating"]["source"] for x in stresses
                                if x["rating"]["value"] == NOT_QUOTED]}

def proposed(base=None, ratings=None):
    data = copy.deepcopy((base or netmodel.NetModel()).data)
    model = netmodel.NetModel(data)
    original = model.connector_net(SCENARIO["connector"], SCENARIO["pin"])
    model.move_pin(SCENARIO["connector"], SCENARIO["pin"], SCENARIO["proposed_net"])
    model.add_resistor(SCENARIO["proposed_ref"], "1k", SCENARIO["proposed_net"], original, rating_w=0.1)
    result = analyze(model, ratings=ratings)
    signal = harness.run()["signal"]
    result["timing"] = {"closed_low_V": 3.3 * 1000 / 5700,
                        "input_low_threshold_V": signal["limit_vil_mV"] / 1000,
                        "close_tau_s": (1000 + 4700 * 1000 / 5700) * model.data["elec"]["c_lim_F"],
                        "release_tau_s": 5700 * model.data["elec"]["c_lim_F"]}
    return result

def run():
    return {"as_drawn": analyze(), "proposed": proposed()}

def report(result):
    for label in ("as_drawn", "proposed"):
        row = result[label]
        print("%s: %.7g V at %s; %s" % (
            label, row["source"]["voltage_V"], row["entry"]["net"], row["status"]
        ))
        for part in row["parts"]:
            print("  %s: %.7g A, %s W (%s)" % (
                part["part"], part["current_A"], part["power_W"], part["power_basis"]
            ))
