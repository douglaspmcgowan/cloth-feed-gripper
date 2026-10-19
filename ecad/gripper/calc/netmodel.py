"""Read the board's authoritative parts and nets without invoking a generator."""

import copy
import importlib.util
from pathlib import Path


def load_design(path=None):
    """Import design.py, whose documented top level only constructs data."""
    source = Path(path) if path else Path(__file__).parents[1] / "design.py"
    spec = importlib.util.spec_from_file_location("gripper_design_data", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {"parts": copy.deepcopy(module.PARTS), "elec": copy.deepcopy(module.ELEC)}


class NetModel:
    def __init__(self, data=None):
        self.data = data or load_design()
        self.parts = {part["ref"]: part for part in self.data["parts"]}

    def connector_net(self, reference, pin):
        return self.parts[reference]["pins"][str(pin)]

    def touching(self, net):
        return [part for part in self.parts.values() if net in part["pins"].values()]

    def series_between(self, first, second):
        found = []
        for part in self.parts.values():
            nets = set(part["pins"].values())
            if nets == {first, second} and part["sym"] == "Device:R":
                found.append(part)
        return found

    def move_pin(self, reference, pin, net):
        self.parts[reference]["pins"][str(pin)] = net

    def add_resistor(self, reference, value, first, second, rating_w=None):
        part = {
            "ref": reference,
            "sym": "Device:R",
            "value": value,
            "fp": "Resistor_SMD:R_0603_1608Metric",
            "pins": {"1": first, "2": second},
            "rating_W": rating_w,
            "rating_source": "proposed protection specification",
        }
        self.parts[reference] = part


def resistance_ohm(value):
    token = value.split()[0].lower().replace("ohm", "")
    if token.endswith("k"):
        return float(token[:-1]) * 1000
    if token.endswith("r"):
        return float(token[:-1])
    if "r" in token:
        return float(token.replace("r", "."))
    return float(token)
