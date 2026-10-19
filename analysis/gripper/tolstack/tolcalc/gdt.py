"""GD&T -> equivalent +/- conversions and fastener formulas.

Conventions follow ASME Y14.5 as summarised in public references (no copied text):
- Position / coaxiality: a diametral zone of dia t lets the axis sit anywhere within
  radius t/2 of true position, so along any single stack direction it is +/- t/2.
  Coordinate to position: dia = 2*sqrt(dx^2 + dy^2)  (Tec-Ease tip 110, GD&T Basics).
  An MMC modifier adds bonus = (actual size - MMC size) to t.
- Circular / total runout: FIM t = 2 * eccentricity, so radial offset = t/2.
- Profile (bilateral, equally disposed): +/- t/2 normal to the surface.
  Unequally disposed (the U modifier, Y14.5-2009 onward): 'outer' of the zone lies
  outside material, t - outer inside.
- Flatness / straightness: a form zone t; as a location contribution use +/- t/2
  about the mean surface.
- Orientation (perpendicularity / parallelism / angularity), zone t over feature
  length L: tilt <= t/L rad, so displacement at distance d from the feature's
  mid-length is +/- t*d/L; without a lever it is +/- t/2 at the feature ends.
- Fasteners (ASME Y14.5 appendix formulas, Tec-Ease tip 110):
  floating  H = F + T       (both parts have clearance holes)
  fixed     H = F + T1 + T2 (one part threaded or pressed)
  H = hole MMC (smallest hole), F = fastener MMC (largest fastener).
"""
from __future__ import annotations

import math

POSITION_TYPES = {"position", "coaxiality", "concentricity", "symmetry"}
RUNOUT_TYPES = {"runout", "circular_runout", "total_runout"}
FORM_TYPES = {"flatness", "straightness", "circularity", "cylindricity"}
ORIENT_TYPES = {"perpendicularity", "parallelism", "angularity"}
PROFILE_TYPES = {"profile", "profile_surface", "profile_line"}


def position_to_pm(zone: float, bonus: float = 0.0) -> float:
    return (zone + bonus) / 2.0


def coords_to_position(dx: float, dy: float) -> float:
    return 2.0 * math.hypot(dx, dy)


def runout_to_radial(fim: float) -> float:
    return fim / 2.0


def orientation_to_pm(zone: float, length: float | None = None, lever: float | None = None) -> float:
    if length and lever is not None:
        return zone * lever / length
    return zone / 2.0


def profile_limits(zone: float, outer: float | None = None) -> tuple[float, float]:
    if outer is None:
        return zone / 2.0, -zone / 2.0
    if not 0.0 <= outer <= zone:
        raise ValueError("profile 'outer' must lie in [0, zone]")
    return outer, outer - zone


def floating_fastener_T(H: float, F: float) -> float:
    """Position tolerance (dia) available to EACH part, floating fastener."""
    return H - F


def fixed_fastener_total(H: float, F: float) -> float:
    """T1 + T2 (dia) shared by the clearance-hole part and the threaded part."""
    return H - F


def fixed_fastener_H(F: float, T1: float, T2: float) -> float:
    return F + T1 + T2


def floating_fastener_H(F: float, T: float) -> float:
    return F + T


def convert(gdt: dict) -> tuple[float, float]:
    """Return (upper, lower) signed deviations equivalent to a GD&T callout."""
    kind = str(gdt["type"]).lower()
    zone = float(gdt["zone"])
    if kind in POSITION_TYPES:
        pm = position_to_pm(zone, float(gdt.get("bonus", 0.0)))
        return pm, -pm
    if kind in RUNOUT_TYPES:
        pm = runout_to_radial(zone)
        return pm, -pm
    if kind in FORM_TYPES:
        return zone / 2.0, -zone / 2.0
    if kind in ORIENT_TYPES:
        pm = orientation_to_pm(zone, gdt.get("length"), gdt.get("lever"))
        return pm, -pm
    if kind in PROFILE_TYPES:
        return profile_limits(zone, gdt.get("outer"))
    raise ValueError(f"unknown GD&T type: {kind}")
