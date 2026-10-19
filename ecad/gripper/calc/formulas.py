"""Pure, reviewable equations used by converted calculation modules."""


def formula(source):
    """Mark a pure equation and retain its review citation."""
    def decorate(function):
        function.formula_source = source
        return function
    return decorate


@formula("Capacitor energy, E = C(V2^2 - V1^2)/2")
def capacitor_energy(capacitance, voltage_squared_difference):
    """Coefficients: 2 is the capacitor-energy denominator."""
    return capacitance * voltage_squared_difference / 2


@formula("Amplitude ratio in decibels, 20 log10(amplitude ratio)")
def amplitude_db(amplitude_ratio):
    """Coefficients: 20 converts an amplitude ratio to decibels."""
    return 20 * amplitude_ratio


@formula("Phase margin, PM = 180 degrees + loop phase")
def phase_margin(loop_phase_degrees):
    """Coefficients: 180 degrees translates loop phase to phase margin."""
    return 180 + loop_phase_degrees


@formula("Ridley sampled current-loop quality factor")
def ridley_quality_factor(modulator_factor, duty_cycle):
    """Coefficients: 1 is identity; 0.5 is the half-switching-frequency term."""
    return 1 / (modulator_factor * (1 - duty_cycle) - 0.5)


@formula("Hard-switched transition loss, P = Vin I tr fsw / 2")
def switching_transition_loss(vin, current, transition_time, switching_frequency):
    """Coefficients: 2 averages the linear voltage-current transition."""
    return vin * current * transition_time * switching_frequency / 2


@formula("Round upward to the nearest half unit")
def round_up_half(value, ceiling):
    """Coefficients: 2 converts between units and half-units."""
    return ceiling(value * 2) / 2


@formula("Half of one quantisation interval")
def half_interval(interval):
    """Coefficients: 0.5 is one half interval."""
    return 0.5 * interval


@formula("E96 preferred value, round(round(10^(k/96) to 2 places) x 10^decade to 1 place)")
def e96_value(step, decade_exponent, rounder):
    """Coefficients: 10 is the decade base; 96.0 is the E96 steps per decade; 2 and 1 are rounding places."""
    return rounder(rounder(10 ** (step / 96.0), 2) * 10 ** decade_exponent, 1)


@formula("Converter step, LSB = full scale / 2^bits")
def adc_step(full_scale, bits):
    """Coefficients: 2 is the binary base of an n-bit converter."""
    return full_scale / 2 ** bits


@formula("Settling to half an LSB, t = R C ln(2^(bits + 1))")
def half_lsb_settling_time(resistance, capacitance, bits, logarithm):
    """Coefficients: 2 is the binary base; 1 adds the half-LSB bit."""
    return resistance * capacitance * logarithm(2 ** (bits + 1))
