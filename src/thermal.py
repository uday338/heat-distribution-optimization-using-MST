"""
thermal.py - Heat transfer in the distribution network.

Two configurations are modelled:

  (1) ABOVE-GROUND insulated steam main - the configuration of Gao et al.,
      where the outer boundary condition is forced convection plus radiation
      to ambient. Their Eq(24) lumps this into a single coefficient epsilon;
      we derive that coefficient from first principles and recover their
      published value, which validates our reading of their Table 1.

  (2) BURIED pre-insulated twin pipe - the configuration of a real European
      district heating network, where the outer boundary condition is
      conduction through soil to the ground surface, and the supply and
      return pipes thermally interact.

Correlations
------------
  Churchill S.W. & Bernstein M. (1977), J. Heat Transfer 99, 300-306
      external cross-flow over a cylinder.
  Gnielinski V. (1976), Int. Chem. Eng. 16, 359-368
      internal turbulent forced convection.
  Wallenten P. (1991) / Bohm B. (2000)
      buried twin-pipe heat loss with mutual thermal coupling.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from params import (
    BURIAL_DEPTH,
    LAMBDA_PUR,
    LAMBDA_SOIL,
    LAMBDA_STEEL,
    T_GROUND_C,
    WATER,
)

SIGMA_SB = 5.670374419e-8   # Stefan-Boltzmann constant [W/(m^2 K^4)]

# Dry air properties near 0-5 degC (Incropera & DeWitt, Table A.4)
AIR_K = 0.0243        # thermal conductivity [W/(m K)]
AIR_NU = 1.36e-5      # kinematic viscosity [m^2/s]
AIR_PR = 0.715        # Prandtl number [-]

CLADDING_EMISSIVITY = 0.25   # galvanised / aluminium cladding [-]


# ============================================================ external boundary
def churchill_bernstein(v: float, D: float, k: float = AIR_K,
                        nu: float = AIR_NU, Pr: float = AIR_PR) -> float:
    """Convective coefficient [W/(m^2 K)] for cross flow over a cylinder.

    Nu = 0.3 + 0.62 Re^0.5 Pr^(1/3) / [1+(0.4/Pr)^(2/3)]^0.25
              * [1 + (Re/282000)^(5/8)]^(4/5)
    Valid for Re*Pr > 0.2, which covers all pipe sizes here.
    """
    if v <= 0 or D <= 0:
        return 0.0
    Re = v * D / nu
    num = 0.62 * math.sqrt(Re) * Pr ** (1 / 3)
    den = (1 + (0.4 / Pr) ** (2 / 3)) ** 0.25
    tail = (1 + (Re / 282000.0) ** (5 / 8)) ** (4 / 5)
    Nu = 0.3 + (num / den) * tail
    return Nu * k / D


def radiation_coefficient(T_surf_C: float, T_amb_C: float,
                          emissivity: float = CLADDING_EMISSIVITY) -> float:
    """Linearised radiation coefficient h_r [W/(m^2 K)]."""
    Ts, Ta = T_surf_C + 273.15, T_amb_C + 273.15
    return emissivity * SIGMA_SB * (Ts * Ts + Ta * Ta) * (Ts + Ta)


def external_coefficient(v: float, D: float, T_surf_C: float, T_amb_C: float,
                         emissivity: float = CLADDING_EMISSIVITY) -> tuple[float, float, float]:
    """Combined external coefficient [W/(m^2 K)] = convection + radiation.

    Used to validate Gao et al.'s lumped epsilon = 11.63 W/(m^2 K): with their
    own Table 1 wind speed v = 3.5 m/s on a ~1 m main at ambient 3.35 degC,
    this returns about 11.5, confirming that the 11.63 value is the external
    coefficient and that the Table 1 units for lambda and epsilon are swapped.
    """
    h_c = churchill_bernstein(v, D)
    h_r = radiation_coefficient(T_surf_C, T_amb_C, emissivity)
    return h_c + h_r, h_c, h_r


# ============================================================ internal boundary
def gnielinski(mdot: float, D: float, fluid=WATER) -> float:
    """Internal convective coefficient [W/(m^2 K)], Gnielinski correlation.

    For DH flows Re is 1e4-1e6 so h_i is of order 1e3-1e4 W/(m^2 K) and the
    internal film is a negligible part of the total resistance - but it is
    included so the resistance network is complete and defensible.
    """
    from hydraulics import friction_factor, reynolds

    if mdot <= 0 or D <= 0:
        return 0.0
    Re = reynolds(mdot, D, fluid.rho, fluid.mu)
    if Re < 2300:
        return 3.66 * fluid.k / D          # fully developed laminar, const T
    f = friction_factor(Re, D)
    Pr = fluid.Pr
    Nu = ((f / 8) * (Re - 1000) * Pr) / (1 + 12.7 * math.sqrt(f / 8) * (Pr ** (2 / 3) - 1))
    return Nu * fluid.k / D


# ============================================================ above ground (Gao)
def heat_loss_above_ground(D_in: float, D_steel: float, t_ins: float,
                           T_fluid_C: float, T_amb_C: float,
                           lam_ins: float, h_ext: float) -> float:
    """Heat loss per metre [W/m] of an above-ground insulated pipe.

    Series cylindrical resistance:
        R = ln(D_ins/D_steel)/(2 pi lam_ins) + 1/(h_ext pi D_ins)
    The steel wall and internal film are negligible here but are omitted
    deliberately to match Gao Eq(24), which contains only these two terms.
    """
    D_ins = D_steel + 2 * t_ins
    R = math.log(D_ins / D_steel) / (2 * math.pi * lam_ins) + 1.0 / (h_ext * math.pi * D_ins)
    return (T_fluid_C - T_amb_C) / R


# ============================================================ buried (real DHN)
@dataclass
class BuriedPipe:
    d_in: float
    d_steel: float
    d_casing: float
    depth: float = BURIAL_DEPTH
    spacing: float | None = None   # centre-to-centre of supply/return [m]

    @property
    def centre_spacing(self) -> float:
        # Standard trench practice: casings laid with a small clear gap.
        return self.spacing if self.spacing is not None else self.d_casing + 0.15


def buried_resistances(p: BuriedPipe, lam_ins: float = LAMBDA_PUR,
                       lam_soil: float = LAMBDA_SOIL) -> tuple[float, float]:
    """Self and mutual thermal resistance [m K/W] of a buried twin pipe.

        R_self = ln(D_casing/D_steel)/(2 pi lam_ins)          (insulation)
               + ln(4 H / D_casing)/(2 pi lam_soil)           (soil to surface)
        R_mut  = ln(sqrt(1 + (2H/C)^2))/(2 pi lam_soil)       (pipe-to-pipe)

    The soil term is the standard buried-cylinder conduction shape factor for
    an isothermal surface; the mutual term is the image-source solution for
    two parallel cylinders.
    """
    R_ins = math.log(p.d_casing / p.d_steel) / (2 * math.pi * lam_ins)
    R_soil = math.log(4.0 * p.depth / p.d_casing) / (2 * math.pi * lam_soil)
    C = p.centre_spacing
    R_mut = math.log(math.sqrt(1.0 + (2.0 * p.depth / C) ** 2)) / (2 * math.pi * lam_soil)
    return R_ins + R_soil, R_mut


def heat_loss_buried(p: BuriedPipe, T_supply_C: float, T_return_C: float,
                     T_ground_C: float = T_GROUND_C,
                     lam_ins: float = LAMBDA_PUR,
                     lam_soil: float = LAMBDA_SOIL) -> float:
    """Total heat loss per trench metre [W/m] for a supply+return pair.

    For the symmetric twin-pipe problem the total loss reduces to the compact
    and widely used result

        q_total = (T_s + T_r - 2 T_ground) / (R_self + R_mut)

    The mutual term R_mut *reduces* total loss, because the warm supply pipe
    partially shields the cooler return pipe.
    """
    R_self, R_mut = buried_resistances(p, lam_ins, lam_soil)
    return (T_supply_C + T_return_C - 2.0 * T_ground_C) / (R_self + R_mut)


def temperature_decay(T_in_C: float, T_ground_C: float, q_per_K: float,
                      L: float, mdot: float, cp: float = WATER.cp) -> float:
    """Outlet temperature [degC] after length L.

    Energy balance mdot cp dT/dx = -(T - T_g)/R integrates to the exponential

        T(L) = T_g + (T_in - T_g) exp(-L / (mdot cp R))

    where q_per_K = 1/R is the loss per metre per kelvin of driving
    temperature difference.
    """
    if mdot <= 0 or L <= 0:
        return T_in_C
    return T_ground_C + (T_in_C - T_ground_C) * math.exp(-q_per_K * L / (mdot * cp))


# ============================================================ validation helper
def validate_gao_epsilon(D: float = 1.0, v: float = 3.50,
                         T_surf_C: float = 30.0, T_amb_C: float = 3.35) -> dict:
    """Reproduce Gao et al.'s epsilon = 11.63 W/(m^2 K) from first principles."""
    h, h_c, h_r = external_coefficient(v, D, T_surf_C, T_amb_C)
    return {
        "h_convection": h_c,
        "h_radiation": h_r,
        "h_total_derived": h,
        "h_published": 11.63,
        "relative_error_pct": 100.0 * (h - 11.63) / 11.63,
    }
