"""
masstransfer.py - Mass transport in the distribution network.

Two mass-transfer problems matter for pipe-network topology, and both feed
back into the network design:

  (1) OXYGEN TRANSPORT AND CORROSION (liquid DH networks).
      Internal corrosion of carbon-steel DH pipe is controlled by the rate at
      which dissolved oxygen can be transported from the bulk water to the
      wall. The wall reaction is fast, so the process is mass-transfer
      limited and the penetration rate follows directly from a Sherwood
      correlation. Because the transfer coefficient depends on velocity and
      diameter, and those are set by the topology, the CHOICE OF TOPOLOGY
      CHANGES THE CORROSION RATE - which changes the failure rate used in the
      reliability analysis. This closes the loop between transport phenomena
      and network structure.

      Note the model reproduces, from mechanism alone, the empirical
      observation in the DH reliability literature that small-diameter pipe
      (DN <= 150) fails more often: k_m scales as u^0.83 D^-0.17, so narrow
      fast branches corrode faster.

  (2) CONDENSATION (steam networks, the Gao configuration).
      Heat loss through the insulation condenses steam, so there is an
      interphase mass flux along every pipe. This sets the steam quality
      delivered to the user and the condensate load returned to the plant.
      The presence of non-condensable gas adds a diffusional resistance that
      can cut the condensing coefficient by an order of magnitude.

Correlations
------------
  Linton W.H. & Sherwood T.K. (1950), Chem. Eng. Prog. 46, 258-264
      Sh = 0.023 Re^0.83 Sc^(1/3), the mass-transfer analogue of
      Dittus-Boelter, validated for dissolving pipe walls.
  Colburn A.P. & Hougen O.A. (1934), Ind. Eng. Chem. 26, 1178-1182
      condensation in the presence of a non-condensable gas.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from params import RHO_STEEL, WATER

# ---- stoichiometry of oxygen-driven corrosion of iron ---------------------
#     4 Fe + 3 O2 + 6 H2O -> 4 Fe(OH)3
M_FE, M_O2 = 55.845, 31.998
FE_PER_O2 = (4.0 / 3.0) * (M_FE / M_O2)      # kg Fe consumed per kg O2 = 2.327

# Dissolved-oxygen scenarios [kg/m^3]. The DH operating limit is set by
# VGB-S-010 / EN 12953 practice at 0.02 mg/L.
O2_SCENARIOS = {
    "well_deaerated": 2.0e-5,     # 0.02 mg/L - specification limit
    "poor_deaeration": 1.0e-4,    # 0.10 mg/L - degraded deaerator
    "air_saturated": 8.0e-3,      # 8 mg/L   - untreated makeup ingress
}


# ============================================================ (1) O2 -> corrosion
def schmidt_number(fluid=WATER) -> float:
    """Sc = mu / (rho D_AB) [-]."""
    return fluid.mu / (fluid.rho * fluid.D_O2)


def sherwood_linton(Re: float, Sc: float) -> float:
    """Sh = 0.023 Re^0.83 Sc^(1/3) (Linton & Sherwood, 1950)."""
    if Re < 2300:
        return 3.66                      # laminar fully developed
    return 0.023 * Re**0.83 * Sc ** (1.0 / 3.0)


def mass_transfer_coefficient(u: float, D: float, fluid=WATER) -> float:
    """Convective mass transfer coefficient k_m [m/s] for O2 to the wall."""
    if u <= 0 or D <= 0:
        return 0.0
    Re = fluid.rho * u * D / fluid.mu
    Sc = schmidt_number(fluid)
    return sherwood_linton(Re, Sc) * fluid.D_O2 / D


@dataclass
class CorrosionResult:
    k_m: float                # mass transfer coefficient [m/s]
    flux_O2: float            # O2 flux to wall [kg/(m^2 s)]
    penetration_mm_per_y: float
    years_to_perforate: float
    Re: float
    Sc: float
    Sh: float


def corrosion_rate(u: float, D: float, C_O2: float,
                   wall_thickness: float = 0.005, fluid=WATER) -> CorrosionResult:
    """Mass-transfer-limited internal corrosion of a carbon-steel pipe.

    Assumes the wall reaction is fast relative to transport, so the interface
    concentration is ~0 and the flux is N = k_m * C_bulk. The iron loss follows
    from stoichiometry and the penetration rate from the steel density.

    wall_thickness : nominal wall of the steel service pipe [m]
                     (5 mm is typical for DN200-DN400 DH pipe).
    """
    Re = fluid.rho * u * D / fluid.mu if D > 0 else 0.0
    Sc = schmidt_number(fluid)
    Sh = sherwood_linton(Re, Sc) if Re > 0 else 0.0
    k_m = mass_transfer_coefficient(u, D, fluid)
    flux = k_m * C_O2                                  # kg O2 /(m^2 s)
    fe_flux = FE_PER_O2 * flux                         # kg Fe /(m^2 s)
    pen_m_per_s = fe_flux / RHO_STEEL                  # m/s
    pen_mm_y = pen_m_per_s * 3.15576e7 * 1000.0        # mm/y
    years = wall_thickness * 1000.0 / pen_mm_y if pen_mm_y > 0 else float("inf")
    return CorrosionResult(k_m, flux, pen_mm_y, years, Re, Sc, Sh)


def corrosion_failure_multiplier(u: float, D: float, C_O2: float,
                                 reference_years: float = 50.0) -> float:
    """Scale the literature corrosion failure rate by predicted pipe life.

    The reliability literature reports a corrosion failure contribution of
    0.07 failures/(km y) as a fleet average. We keep that as the reference and
    scale it by (reference_life / predicted_life), so a branch that our mass
    transfer model says corrodes twice as fast carries twice the failure rate.
    Clipped to a sensible band so a single extreme branch cannot dominate.
    """
    res = corrosion_rate(u, D, C_O2)
    if not math.isfinite(res.years_to_perforate) or res.years_to_perforate <= 0:
        return 1.0
    return float(min(5.0, max(0.2, reference_years / res.years_to_perforate)))


# ============================================================ (2) condensation
def condensation_rate(q_per_m: float, h_fg_kJ_per_kg: float) -> float:
    """Condensate formed per metre of steam main [kg/(m s)].

    Every watt lost through the insulation condenses steam:
        mdot_cond' = q' / h_fg
    """
    if h_fg_kJ_per_kg <= 0:
        return 0.0
    return q_per_m / (h_fg_kJ_per_kg * 1000.0)


def steam_quality_profile(mdot_in: float, q_per_m: float, L: float,
                          h_fg_kJ_per_kg: float, x_in: float = 1.0,
                          n: int = 50):
    """Steam quality x along a pipe run of length L.

    Returns (s [m], x [-]). Quality falls linearly while the pressure (and
    hence h_fg) is roughly constant. A user receiving x < ~0.97 gets wet steam,
    which erodes control valves and cuts deliverable enthalpy - a real
    operational limit on how long a steam branch can be.
    """
    import numpy as np

    s = np.linspace(0.0, L, n)
    if mdot_in <= 0:
        return s, np.full_like(s, x_in)
    rate = condensation_rate(q_per_m, h_fg_kJ_per_kg)   # kg/(m s)
    x = x_in - rate * s / mdot_in
    return s, np.clip(x, 0.0, 1.0)


def makeup_water(total_mdot: float, return_ratio: float = 0.90) -> float:
    """Makeup water demand [kg/s] from an overall loop mass balance.

    Condensate return in industrial steam networks is typically 80-95 %;
    the balance is lost to flash, leaks and process consumption and must be
    replaced with treated water. Every kilogram of makeup carries fresh
    dissolved oxygen into the loop, which is what links this back to the
    corrosion model above.
    """
    return total_mdot * (1.0 - return_ratio)


def colburn_hougen_derating(y_ncg: float) -> float:
    """Fractional derating of the condensing coefficient by non-condensables.

    A simple engineering correlation to the Colburn-Hougen result: even a few
    mole per cent of air at the interface builds a diffusion barrier that the
    vapour must cross, cutting the condensing coefficient sharply. Used here
    to show why steam networks need air venting at every high point - a
    topology-dependent requirement, since a hilly route has more high points.
    """
    y = max(0.0, min(0.5, y_ncg))
    return 1.0 / (1.0 + 18.0 * y)
