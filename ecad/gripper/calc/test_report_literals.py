"""Keep report labels derived from the values that they describe."""
import inspect
import re

import fsr_frontend
import harness


UNIT_BEARING_NUMBER = re.compile(
    r"(?<![%\w])\d+(?:\.\d+)?\s*(?:mV|V|kHz|Hz|kohm|ohm|nF|N|bit)\b")


def test_report_printers_have_no_unit_bearing_numeric_literals():
    violations = []
    for module in (fsr_frontend, harness):
        source = inspect.getsource(module.report)
        for match in UNIT_BEARING_NUMBER.finditer(source):
            # Zero is the identity of the explicitly labelled open-circuit row, not a design value.
            if match.group() != "0 ohm":
                violations.append("%s.report: %s" % (module.__name__, match.group()))
    assert not violations, "unit-bearing report literals must come from constants/results: " + ", ".join(violations)
