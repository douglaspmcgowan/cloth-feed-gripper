# Electrical calculation outputs

`python ecad/gripper/calc/run_all.py --check` regenerates the evidence and compares closed-form (`exact`) values byte-for-byte after seven-significant-figure serialization. Values produced by LSODA, or derived from them, are `integrated`: they are stored to five significant figures and compared with `100 * rtol * max(abs(old), abs(new)) + 100 * atol`, using the solver's `rtol=1e-6` and `atol=1e-9`. A normal run retains a committed integrated value—and therefore its JSON, text, and generated note rendering—when it remains within that tolerance.
