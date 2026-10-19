"""Registry and read recorder for physical inputs used by margin calculations."""

from contextlib import contextmanager
from functools import wraps
from pathlib import Path

_ACTIVE = None
_PENDING = set()
MODULE_READS = {}


def recorded_cache(function):
    """Memoize a calculation while replaying its physical-input reads."""
    memo = {}

    @wraps(function)
    def wrapper(*args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))
        if key not in memo:
            with recording() as observed:
                result = function(*args, **kwargs)
            memo[key] = (result, frozenset(observed))
        result, observed = memo[key]
        for name in sorted(observed):
            record(name)
        return result

    wrapper.cache_clear = memo.clear
    return wrapper


def exact(value, reason):
    return {"value": value, "class": "exact", "reason": reason}


def quoted(value, file, line, figure, band):
    return {"value": value, "class": "quoted", "file": file, "line": line,
            "figure": figure, "band": band}


def missing(value, part, parameter, where, method="datasheet lookup"):
    return {
        "value": value, "class": "missing", "part": part, "parameter": parameter,
        "where": where, "method": method,
    }


INPUTS = {
    "fuse_hold_A": missing(2.6, "F1 MF-MSMF260/16X", "hold-current tolerance at 25 C", "datasheet electrical characteristics table"),
    "servo_stall_fit_A": missing(3.77, "servo Fit A dyno specimen", "stall-current fit confidence interval", "DESIGN-BASIS.md section 10 force/current sweep", "bench measurement"),
    "servo_voltage_V": exact(6.8, "finite Fit A rated-voltage scenario"),
    "cable_resistance_ohm": missing(0.03331, "servo harness", "finished loop resistance", "DESIGN-BASIS.md section 10 harness milliohm step", "bench measurement"),
    "input_voltage_V": quoted(12.0, "ecad/gripper/design.py", 26, "-10 %", [-0.10, 0.10]),
    "buck_diode_drop_V": missing(0.50, "D2 B540C", "forward voltage at load current", "manufacturer datasheet forward-voltage curve"),
    "buck_switch_resistance_ohm": missing(0.190, "U1 TPS54560BDDAR", "switch resistance over temperature", "datasheet electrical characteristics table"),
    "inductor_dcr_ohm": missing(0.015, "L1 SRP1245A-100M", "DCR tolerance", "manufacturer datasheet electrical table"),
    "buck_efficiency": missing(0.85, "U1 buck stage", "conversion efficiency at Fit A load", "DESIGN-BASIS.md section 10 efficiency bench step", "bench measurement"),
    "load_5v_A": missing(0.25, "5 V rail assembly", "maximum load current", "DESIGN-BASIS.md section 10 rail-load bench step", "bench measurement"),
    "regulator_ilim_min_A": missing(6.3, "U1 TPS54560BDDAR", "current-limit test-condition variation", "datasheet electrical characteristics table"),
    "load_step_fit_A": missing(3.77, "servo Fit A dyno specimen", "load-step current fit confidence interval", "DESIGN-BASIS.md section 10 force/current sweep", "bench measurement"),
    "setpoint_endpoints_V": missing(6.5, "U1 feedback network", "reference and resistor endpoint bands", "U1 and resistor datasheets"),
    "inductance_H": missing(10e-6, "L1 SRP1245A-100M", "inductance tolerance and bias derating", "manufacturer datasheet curves"),
    "bulk_capacitance_F": quoted(1000e-6, "ecad/gripper/calc/constants.py", 116,
                                  "+/-20 %", [-0.20, 0.20]),
    "bulk_esr_ohm": missing(0.030, "C12 1000 uF", "ESR after temperature and ageing", "DESIGN-BASIS.md section 10 load-step step", "bench measurement"),
    "wiring_impedance_ohm": missing(0.05, "servo power path", "assembled wiring impedance", "DESIGN-BASIS.md section 10 harness milliohm step", "bench measurement"),
    "shunt_resistance_ohm": missing(0.1, "RS1 WSLP1206R1000FEA", "resistance over temperature", "manufacturer datasheet and calibration step"),
    "trace_width_mil": exact(100.0, "routed geometry measured from PCB"),
    "copper_thickness_oz": missing(1.0, "PCB copper", "finished copper thickness tolerance", "PCB fabricator stack-up certificate"),
    "ipc_relation": exact(0.048, "IPC-2221 external-layer curve definition"),
    "trace_rise_target_C": exact(10.0, "design requirement target"),
    "trace_demand_A": missing(3.77, "servo Fit A dyno specimen", "stall-current fit confidence interval", "DESIGN-BASIS.md section 10 force/current sweep", "bench measurement"),
    "ina_offset_V": missing(200e-6, "U2 INA219AIDR", "offset over operating conditions", "datasheet electrical characteristics table"),
    "ina_gain_error": missing(0.005, "U2 INA219AIDR", "gain error over operating conditions", "datasheet electrical characteristics table"),
    "ina_gain_drift": missing(1e-5, "U2 INA219AIDR", "gain drift limit", "datasheet electrical characteristics table"),
    "shunt_tolerance": quoted(0.01, "ecad/gripper/calc/constants.py", 138, "1 %", [-0.01, 0.01]),
    "shunt_tcr": quoted(100e-6, "ecad/gripper/calc/constants.py", 139,
                           "100 ppm/K", [-100e-6, 100e-6]),
    "filter_resistance_ohm": exact(10.0, "schematic component value"),
    "bias_mismatch_A": missing(20e-6, "U2 INA219AIDR", "input bias-current mismatch", "datasheet electrical characteristics table"),
    "adc_lsb_V": exact(10e-6, "INA219 register scale definition"),
    "trip_current_A": exact(2.5, "firmware configured threshold"),
    "adc_endpoint_mV": missing(2450.0, "U3 ESP32-WROOM-32E", "ADC linear-range endpoint variation", "DESIGN-BASIS.md section 10 ADC sweep", "bench measurement"),
    "firmware_force_cap_N": exact(10.0, "firmware configured threshold"),
    "rail_3v3_mV": quoted(3300.0, "ecad/gripper/calc/constants.py", 84,
                            "+/-1 %", [-0.01, 0.01]),
    "r15_ohm": quoted(2700.0, "ecad/gripper/design.py", 247, "0.1%", [-0.001, 0.001]),
    "fsr_fit_coefficient": missing(6109.0, "FSR sensor", "fit coefficient confidence interval", "DESIGN-BASIS.md section 10 force sweep", "bench measurement"),
    "fsr_fit_exponent": missing(0.8195, "FSR sensor", "fit exponent confidence interval", "DESIGN-BASIS.md section 10 force sweep", "bench measurement"),
    "servo_max_V": missing(6.8, "servo", "maximum permitted voltage tolerance", "servo manufacturer datasheet"),
    "returned_energy_J": missing(0.020, "servo system", "returned energy at release", "DESIGN-BASIS.md section 10 regeneration step", "bench measurement"),
    "wrist_capacitance_F": missing(470e-6, "wrist capacitor", "capacitance after bias temperature and ageing", "manufacturer datasheet"),
    "ceramic_capacitance_F": missing(47e-6, "47 uF ceramics", "effective capacitance at DC bias", "manufacturer DC-bias curves"),
}

# Values whose authoritative definition is this registry.  Evidence records are
# stripped below so INPUTS never becomes a second physical-value store.
VALUES = {name: item.pop("value") for name, item in INPUTS.items()}


class RecordingMapping:
    """Read-only view which records physical reads without copying its source."""

    def __init__(self, source, prefix, aliases=None):
        self._source = source
        self._prefix = prefix
        self._aliases = aliases or {}

    def __getitem__(self, key):
        record(self._aliases.get(key, "%s.%s" % (self._prefix, key)))
        return self._source[key]

    def __iter__(self):
        record(self._prefix + ".*")
        return iter(self._source)

    def __len__(self):
        return len(self._source)

    def __contains__(self, key):
        record(self._prefix + ".*")
        return key in self._source

    def __setitem__(self, key, value):
        self._source[key] = value

    def __delitem__(self, key):
        del self._source[key]

    def get(self, key, default=None):
        if key in self._source:
            return self[key]
        return default


class ResultView:
    """Nested result view which records the producing module on every read."""

    def __init__(self, value, module):
        self._value = value
        self._module = module

    def __getitem__(self, key):
        record_module(self._module)
        value = self._value[key]
        return ResultView(value, self._module) if isinstance(value, (dict, list)) else value

    def __iter__(self):
        record_module(self._module)
        if isinstance(self._value, list):
            return iter(ResultView(value, self._module) if isinstance(value, (dict, list)) else value
                        for value in self._value)
        return iter(self._value)

    def __len__(self):
        return len(self._value)

    def keys(self):
        record_module(self._module)
        return self._value.keys()

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default


@contextmanager
def recording():
    global _ACTIVE
    prior = _ACTIVE
    observed = set()
    _PENDING.clear()
    _ACTIVE = observed
    try:
        yield observed
    finally:
        _ACTIVE = prior


@contextmanager
def pending_recording():
    """Claim reads made while evaluating the immediately following row."""
    global _ACTIVE
    prior = _ACTIVE
    observed = set(_PENDING)
    _PENDING.clear()
    _ACTIVE = observed
    try:
        yield observed
    finally:
        _ACTIVE = prior


def read(name):
    """Return a registered value and record the physical read in the active row."""
    if name not in INPUTS:
        raise KeyError("unregistered physical input " + name)
    record(name)
    return VALUES[name]


def record(name):
    _PENDING.add(name)
    if _ACTIVE is not None:
        _ACTIVE.add(name)


def record_module(name):
    record("module:" + name)


def capture_module(name, function):
    """Run a module calculation and retain the physical names it actually read."""
    _PENDING.clear()
    with recording() as observed:
        result = function()
    reads = {item for item in observed if not item.startswith("module:")}
    if not reads:
        raise AssertionError("module %s recorded no physical inputs" % name)
    MODULE_READS[name] = reads
    _PENDING.clear()
    return ResultView(result, name)


def consume_modules(observed):
    modules = sorted(item[7:] for item in observed if item.startswith("module:"))
    names = {item for item in observed if not item.startswith("module:")}
    for module in modules:
        names.update(MODULE_READS.get(module, ()))
    return names, modules


def evidence(name):
    return dict(INPUTS.get(name, {"class": "unclassified", "band": None}))


def validate_registry(root):
    """Validate evidence shape; quoted evidence must resolve to its literal line."""
    for name, item in INPUTS.items():
        cls = item.get("class")
        if cls not in {"exact", "quoted", "evaluated at extreme", "missing", "unclassified"}:
            raise AssertionError("%s has invalid class" % name)
        if cls == "exact" and not item.get("reason"):
            raise AssertionError("%s exact input lacks reason" % name)
        if cls == "missing" and not all(item.get(k) for k in ("part", "parameter", "where", "method")):
            raise AssertionError("%s missing input lacks acquisition details" % name)
        if cls == "quoted":
            path = Path(root, item["file"])
            lines = path.read_text(encoding="utf-8").splitlines()
            line = lines[item["line"] - 1]
            if item["figure"] not in line:
                raise AssertionError("%s quoted figure is absent from source line" % name)
"""Physical uncertainty evidence used by the electrical margin register."""

MISSING_BY_SOURCE = {
    "f1_trip": (
        "F1 MF-MSMF260/16X",
        "trip-current tolerance at 25 C",
        "datasheet electrical characteristics table",
    ),
    "tps_ilim_min": (
        "U1 TPS54560BDDAR",
        "current-limit test-condition variation",
        "datasheet electrical characteristics table",
    ),
    "R26": (
        "U1 TPS54560BDDAR",
        "junction-to-ambient thermal resistance for the assembled PCB",
        "DESIGN-BASIS.md section 10 thermal-rise bench step",
    ),
    "trace_width": (
        "PCB copper",
        "finished copper thickness tolerance",
        "PCB fabricator stack-up certificate",
    ),
    "rs1_rating": (
        "RS1 WSLP1206R1000FEA",
        "power-rating derating above 70 C",
        "datasheet performance curves",
    ),
    "ina219_budget": (
        "U2 INA219AIDR",
        "input-filter source-impedance mismatch",
        "DESIGN-BASIS.md section 10 current-calibration bench step",
    ),
    "esp_adc_max_mv": (
        "U3 ESP32-WROOM-32E",
        "ADC linear-range endpoint variation",
        "DESIGN-BASIS.md section 10 ADC sweep bench step",
    ),
    "harness": (
        "J1/J2/J3 harness assembly",
        "finished conductor resistance and contact-resistance range",
        "DESIGN-BASIS.md section 10 harness milliohm bench step",
    ),
    "fsr_frontend": (
        "C17 100 nF",
        "capacitance tolerance",
        "C17 manufacturer datasheet capacitance-tolerance table",
    ),
    "R20": (
        "servo Fit A dyno specimen",
        "torque-constant and hold-current fit confidence interval",
        "DESIGN-BASIS.md section 10 force/current sweep",
    ),
    "power_budget": (
        "PS1 12 V 3 A adapter",
        "rated-current capability over temperature",
        "adapter datasheet output-current table",
    ),
    "droop_sim": (
        "C12 1000 uF",
        "capacitance and ESR after bias, temperature, and ageing",
        "DESIGN-BASIS.md section 10 load-step bench step",
    ),
    "buck_design": (
        "U1 TPS54560BDDAR compensation network",
        "small-signal plant/model error band",
        "DESIGN-BASIS.md section 10 loop-response bench step",
    ),
}


def missing_component(source):
    """Return a specific, actionable missing physical figure."""
    part, parameter, location = MISSING_BY_SOURCE[source]
    message = "missing: %s — %s; find in %s" % (part, parameter, location)
    return {
        "input": "%s %s" % (part, parameter),
        "class": "missing",
        "band": None,
        "source": message,
        "sensitivity": None,
        "part": part,
        "parameter": parameter,
        "where": location,
    }
