"""
hydraulics.py - Momentum transport in the distribution network.

This replaces the constant friction factor of Gao et al. (their sigma = 0.015,
Eq 19) with a proper Reynolds- and roughness-dependent treatment, adds real
discrete pipe sizing, and adds the static-pressure analysis that terrain makes
necessary.

Physics implemented
-------------------
1. Darcy-Weisbach with Colebrook-White friction (Colebrook, 1939), with the
   Haaland (1983) explicit form available for speed.
2. Discrete pipe selection from the EN 253 catalogue on the two criteria real
   DH designers use: velocity window and specific pressure drop.
3. The mechanical energy balance including the elevation term, and the
   important consequence that in a CLOSED loop the static term cancels.
4. The static pressure profile p(z), which does NOT cancel, and the two
   constraints it must satisfy on hilly ground: the pressure class of the
   pipe at the low point, and the cavitation/flashing margin at the high point.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from params import (
    DN_CATALOGUE,
    EURO,
    G,
    PIPE_ROUGHNESS,
    V_MAX,
    V_MIN,
    WATER,
)

# Design limit on specific pressure drop for DH distribution mains
# (Frederiksen & Werner, District Heating and Cooling, 2013, ch. 9).
R_MAX_PA_PER_M = 100.0


# ---------------------------------------------------------------- friction
def reynolds(mdot: float, D: float, rho: float, mu: float) -> float:
    """Re = rho u D / mu = 4 mdot / (pi D mu)."""
    if D <= 0 or mdot <= 0:
        return 0.0
    return 4.0 * mdot / (math.pi * D * mu)


def friction_factor(Re: float, D: float, eps: float = PIPE_ROUGHNESS,
                    method: str = "colebrook") -> float:
    """Darcy friction factor f [-].

    Laminar below Re = 2300 (f = 64/Re); turbulent from Colebrook-White,
    solved by fixed-point iteration on 1/sqrt(f), which converges in a
    handful of steps for all practical Re. `method="haaland"` uses the
    explicit approximation, accurate to about 2 %.
    """
    if Re <= 0:
        return 0.0
    if Re < 2300:
        return 64.0 / Re
    rr = eps / D
    if method == "haaland":
        inv = -1.8 * math.log10((rr / 3.7) ** 1.11 + 6.9 / Re)
        return 1.0 / (inv * inv)
    inv = -2.0 * math.log10(rr / 3.7 + 5.74 / Re**0.9)   # Swamee-Jain seed
    for _ in range(40):
        new = -2.0 * math.log10(rr / 3.7 + 2.51 * inv / Re)
        if abs(new - inv) < 1e-12:
            inv = new
            break
        inv = new
    return 1.0 / (inv * inv)


def velocity(mdot: float, D: float, rho: float) -> float:
    """Bulk velocity [m/s] from mass flow and inner diameter."""
    if D <= 0:
        return 0.0
    return 4.0 * mdot / (rho * math.pi * D * D)


def pressure_drop(mdot: float, D: float, L: float, rho: float, mu: float,
                  eps: float = PIPE_ROUGHNESS) -> tuple[float, float, float]:
    """Frictional pressure drop over a pipe run.

    Returns (dp [Pa], f [-], u [m/s]) using dp = f (L/D) (rho u^2 / 2).
    """
    if mdot <= 0 or D <= 0 or L <= 0:
        return 0.0, 0.0, 0.0
    u = velocity(mdot, D, rho)
    Re = reynolds(mdot, D, rho, mu)
    f = friction_factor(Re, D, eps)
    dp = f * (L / D) * rho * u * u / 2.0
    return dp, f, u


# ---------------------------------------------------------------- pipe sizing
@dataclass(frozen=True)
class PipeSize:
    dn: int
    d_in: float       # inner diameter [m]
    d_steel: float    # steel outer diameter [m]
    d_casing: float   # casing outer diameter [m]
    u: float          # resulting velocity [m/s]
    R: float          # resulting specific pressure drop [Pa/m]


def select_pipe(mdot: float, rho: float = WATER.rho, mu: float = WATER.mu,
                r_max: float = R_MAX_PA_PER_M, u_max: float = V_MAX) -> PipeSize:
    """Choose the smallest catalogue pipe that satisfies both design criteria.

    Real networks cannot use the continuous diameter of Gao Eq(6); they use
    catalogue sizes. We pick the smallest DN for which

        u <= u_max            (noise and erosion limit)
        R  <= r_max           (specific pressure drop limit, Pa/m)

    and fall back to the largest catalogue size if none qualifies.
    """
    if mdot <= 0:
        dn, di, ds, dc = DN_CATALOGUE[0]
        return PipeSize(dn, di, ds, dc, 0.0, 0.0)
    best = None
    for dn, di, ds, dc in DN_CATALOGUE:
        u = velocity(mdot, di, rho)
        dp, _, _ = pressure_drop(mdot, di, 1.0, rho, mu)
        if u <= u_max and dp <= r_max:
            best = PipeSize(dn, di, ds, dc, u, dp)
            break
    if best is None:
        dn, di, ds, dc = DN_CATALOGUE[-1]
        u = velocity(mdot, di, rho)
        dp, _, _ = pressure_drop(mdot, di, 1.0, rho, mu)
        best = PipeSize(dn, di, ds, dc, u, dp)
    return best


def mdot_from_load(load_kW: float, dT: float | None = None,
                   cp: float = WATER.cp) -> float:
    """Mass flow [kg/s] carrying a thermal load with cooling dT.

    mdot = Q / (cp * dT). The supply/return temperature difference is the
    single most important DH design parameter - a larger dT moves the same
    heat in a smaller pipe.
    """
    if dT is None:
        dT = WATER.T_supply_C - WATER.T_return_C
    return load_kW * 1000.0 / (cp * dT)


# ------------------------------------------------- mechanical energy balance
def pump_power(mdot: float, dp: float, rho: float = WATER.rho,
               eta: float = EURO.pump_eta) -> float:
    """Shaft power [W] to raise pressure by dp: P = mdot*dp/(rho*eta)."""
    if mdot <= 0 or dp <= 0:
        return 0.0
    return mdot * dp / (rho * eta)


def static_head(dz: float, rho: float = WATER.rho) -> float:
    """Hydrostatic pressure difference [Pa] over an elevation change dz [m].

    This is the term Gao et al. omit. For their steam (rho = 0.6 kg/m3) it is
    negligible; for liquid water (rho ~ 950 kg/m3) it is three orders of
    magnitude larger and dominates on hilly ground.
    """
    return rho * G * dz


def closed_loop_pump_dp(friction_supply: float, friction_return: float) -> float:
    """Pump pressure rise required by a CLOSED supply/return loop.

    The static elevation term cancels round a closed circuit: whatever head is
    spent climbing to a consumer is recovered coming back down. The pump
    therefore only has to overcome friction in both legs. Getting this wrong
    (adding rho*g*dz to the pump duty) is a common modelling error and would
    overstate hilly-network pumping cost by orders of magnitude.
    """
    return friction_supply + friction_return


# ---------------------------------------------------------------- static pressure
@dataclass
class PressureCheck:
    feasible: bool
    p_max: float          # highest static pressure anywhere [Pa]
    p_min: float          # lowest static pressure anywhere [Pa]
    z_low: float
    z_high: float
    limit_PN: float
    limit_cav: float
    n_zones: int          # pressure zones needed to make the network feasible
    violation_bar: float  # by how much PN is exceeded [bar], 0 if feasible


def static_pressure_check(z: np.ndarray, z_pump: float | None = None,
                          rho: float = WATER.rho,
                          PN: float = EURO.PN_rating,
                          p_sat: float = WATER.p_sat_supply,
                          margin: float = EURO.p_cavitation_margin) -> PressureCheck:
    """Does one pressure zone survive this terrain?

    The static pressure at elevation z, referenced to the pump house, is

        p(z) = p_ref + rho g (z_pump - z)

    We set p_ref so that the highest point of the network sits exactly at the
    cavitation limit p_sat + margin (the least-pressure design that still
    prevents flashing), then ask whether the lowest point stays inside the
    pipe pressure class PN.

    The number of pressure zones needed is ceil(required span / usable span).
    """
    z = np.asarray(z, dtype=float)
    z_low, z_high = float(z.min()), float(z.max())
    if z_pump is None:
        z_pump = z_low

    p_top = p_sat + margin                       # required at the high point
    p_bottom = p_top + rho * G * (z_high - z_low)

    usable = PN - p_top                          # pressure span one zone can hold
    required = rho * G * (z_high - z_low)
    n_zones = max(1, int(math.ceil(required / usable))) if usable > 0 else 99
    feasible = p_bottom <= PN
    return PressureCheck(
        feasible=feasible,
        p_max=p_bottom,
        p_min=p_top,
        z_low=z_low,
        z_high=z_high,
        limit_PN=PN,
        limit_cav=p_sat + margin,
        n_zones=n_zones,
        violation_bar=max(0.0, (p_bottom - PN) / 1e5),
    )
