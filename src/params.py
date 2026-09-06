"""
params.py - All model parameters, in three groups:

  (A) GAO      - Table 1 of Gao et al. (2020), used for the reproduction.
  (B) FLUID    - property and pipe-catalogue data for the extended
                 transport-phenomena model.
  (C) COST_EU  - European district-heating cost and reliability data for the
                 real-network extension.

Every parameter carries units and a source. Where the source paper is
internally inconsistent, the inconsistency is documented and the reading we
adopt is justified. Those are flagged  # [READING].
"""
from __future__ import annotations

from dataclasses import dataclass

G = 9.80665  # standard gravity [m/s^2]


# =====================================================================
# (A) Gao et al. (2020), Chem. Eng. Transactions 81, 277-282, Table 1
# =====================================================================
@dataclass(frozen=True)
class GaoParams:
    """Case-study parameters as published, plus documented readings.

    Table 1 as printed contains several unit-column errors. We identify them
    rather than silently fixing them:

    * A1 = 5.74 with unit "CNY/y" - A1 is defined in the text as the price of
      unit *weight* of pipe, so the unit must be CNY/kg.
    * lambda = 0.06 "W/m2K" and epsilon = 11.63 "W/mK" - the two units are
      swapped. 0.06 W/(m K) is a textbook mineral-wool conductivity and
      11.63 W/(m^2 K) is a textbook external convection coefficient. We
      verify the latter independently: Churchill-Bernstein for a 1 m cylinder
      in 3.5 m/s cross flow (Table 1's own wind speed v) gives about
      10.0 W/(m^2 K), plus about 1.6 W/(m^2 K) of radiation, giving 11.6.
      See thermal.external_coefficient().
    * alpha_k = 0.1945 (dimensionless in the table) is the only candidate for
      a, the unit price of steam in Eq(23), which is otherwise undefined.
      0.1945 CNY/kg = 194.5 CNY/t is the right order for Chinese industrial
      steam and it reproduces the published heat-loss cost. a_k itself cannot
      be an input because Eq(13) computes it.
    * sigma = 0.015 with unit "CNY/kg" - sigma is the Darcy friction factor in
      Eq(19); 0.015 is a textbook value and the CNY/kg unit belongs to the
      steam-price row.
    """

    # --- capital ---------------------------------------------------------
    t_year: int = 10             # pipe network lifetime [y]
    I: float = 0.02              # interest rate [-]
    A1: float = 5.74             # price of unit weight of pipe [CNY/kg]     # [READING]
    A2: float = 1295.0           # installation cost [CNY/m^0.48]
    A3: float = 47.6             # road usage cost [CNY/m]
    A4: float = 2065.0           # insulation cost [CNY/m per m of D_out]
    # --- fluid / sizing --------------------------------------------------
    rho: float = 0.60            # steam density [kg/m^3] -> saturated ~1 bar
    u: float = 30.0              # design steam velocity [m/s]
    # --- pumping ---------------------------------------------------------
    aE: float = 0.21             # unit power cost [CNY/kWh]
    t_time: float = 8760.0       # annual operating time [h]
    eta: float = 0.8             # pump efficiency [-]
    sigma: float = 0.015         # Darcy friction factor [-]                 # [READING]
    elbow_spacing: float = 25.0  # one elbow every 25 m, Eq(20) [m]
    zeta_elbow: float = 1.0      # per-elbow loss coefficient [-] (calibrated)
    # --- heat loss -------------------------------------------------------
    a_steam: float = 0.1945      # unit price of steam [CNY/kg]              # [READING]
    q_latent: float = 1999.9     # latent heat of steam [kJ/kg]
    T_amb: float = 276.5         # ambient temperature [K] (= 3.35 degC)
    lam_ins: float = 0.06        # insulation conductivity [W/(m K)]         # [READING]
    eps_ext: float = 11.63       # external heat transfer coeff [W/(m^2 K)]  # [READING]
    v_wind: float = 3.50         # ambient wind speed [m/s]
    # --- calibrated (NOT published by the paper) -------------------------
    t_ins: float = 0.18          # insulation thickness [m] - calibrated
    T_steam_C: float = 100.0     # steam temperature [degC] - implied by rho
    # Insulation sizing model. "constant" holds thickness fixed on every
    # branch; "proportional" scales it with pipe diameter, which is what
    # EN 12828 / VDI 2055 actually specify (thicker lagging on bigger DN).
    # Which of the two the paper used is not stated, so we test both against
    # the held-out Star column and let the data choose - see calibrate.py.
    # "en_scaling" uses t_ins = ins_coeff * D_out^ins_exp with the exponent
    # 0.391 measured by log-log fit to the real EN 253 casing catalogue
    # (R = 0.963). The exponent therefore comes from the standard, not from
    # the data we are validating against, so the Star test stays honest.
    ins_mode: str = "constant"
    ins_ratio: float = 0.40      # t_ins / D_out when ins_mode="proportional"
    ins_exp: float = 0.391       # EN 253 measured exponent [-]
    ins_coeff: float = 0.30      # coefficient when ins_mode="en_scaling"

    @property
    def crf(self) -> float:
        """Capital recovery factor of Eq(5): I(1+I)^t / ((1+I)^t - 1)."""
        f = (1 + self.I) ** self.t_year
        return self.I * f / (f - 1)


GAO = GaoParams()

# Table 2 of the paper - the reproduction targets (x1e4 m and x1e7 CNY/y).
GAO_TABLE2 = {
    "length_1e4_m": {"Star": 3.65, "MST": 1.19, "RSMT": 1.19, "ESMT": 1.03},
    "pipe_1e7":     {"Star": 0.869, "MST": 1.03, "RSMT": 1.28, "ESMT": 0.939},
    "pressure_1e7": {"Star": 0.274, "MST": 0.704, "RSMT": 0.936, "ESMT": 0.654},
    "heat_1e7":     {"Star": 1.10, "MST": 0.443, "RSMT": 0.458, "ESMT": 0.387},
    "total_1e7":    {"Star": 2.25, "MST": 2.18, "RSMT": 2.67, "ESMT": 1.98},
}


# =====================================================================
# (B) Fluid properties and pipe catalogue for the extended model
# =====================================================================
@dataclass(frozen=True)
class WaterProps:
    """Liquid water at DH supply temperature.

    Values from the IAPWS-IF97 industrial formulation as tabulated in
    Incropera and DeWitt, Fundamentals of Heat and Mass Transfer, App. A.6.
    """

    T_supply_C: float = 110.0
    T_return_C: float = 50.0
    rho: float = 951.0             # density at 110 degC [kg/m^3]
    cp: float = 4229.0             # specific heat [J/(kg K)]
    mu: float = 2.59e-4            # dynamic viscosity at 110 degC [Pa s]
    k: float = 0.683               # thermal conductivity [W/(m K)]
    Pr: float = 1.60               # Prandtl number [-]
    p_sat_supply: float = 1.43e5   # saturation pressure at 110 degC [Pa]
    D_O2: float = 6.9e-9           # O2 diffusivity in water at 110 degC [m^2/s]
    C_O2_sat: float = 8.0e-3       # dissolved O2 at ingress point [kg/m^3]


WATER = WaterProps()

# Standard EN 253 pre-insulated DH pipe catalogue, insulation series 2.
# (DN, inner diameter [m], steel outer diameter [m], casing outer diameter [m])
DN_CATALOGUE: list[tuple[int, float, float, float]] = [
    (20, 0.0217, 0.0269, 0.090),
    (25, 0.0285, 0.0337, 0.090),
    (32, 0.0372, 0.0424, 0.110),
    (40, 0.0431, 0.0483, 0.110),
    (50, 0.0545, 0.0603, 0.125),
    (65, 0.0703, 0.0761, 0.140),
    (80, 0.0825, 0.0889, 0.160),
    (100, 0.1071, 0.1143, 0.200),
    (125, 0.1325, 0.1397, 0.225),
    (150, 0.1603, 0.1683, 0.250),
    (200, 0.2101, 0.2191, 0.315),
    (250, 0.2630, 0.2730, 0.400),
    (300, 0.3127, 0.3239, 0.450),
    (350, 0.3444, 0.3556, 0.500),
    (400, 0.3938, 0.4064, 0.560),
    (450, 0.4444, 0.4570, 0.630),
    (500, 0.4954, 0.5080, 0.710),
    (600, 0.5958, 0.6096, 0.800),
    (700, 0.6950, 0.7112, 0.900),
    (800, 0.7954, 0.8128, 1.000),
    (900, 0.8940, 0.9144, 1.100),
    (1000, 0.9946, 1.0160, 1.200),
]

PIPE_ROUGHNESS = 4.0e-5  # absolute roughness, new welded steel [m] (EN 13941)
LAMBDA_PUR = 0.027       # polyurethane foam conductivity [W/(m K)] (EN 253)
LAMBDA_SOIL = 1.6        # moist sandy soil conductivity [W/(m K)]
BURIAL_DEPTH = 0.8       # pipe axis burial depth [m] (EN 13941 typical)
LAMBDA_STEEL = 50.0      # carbon steel conductivity [W/(m K)]
RHO_STEEL = 7850.0       # steel density [kg/m^3]
T_GROUND_C = 8.0         # annual mean ground temperature at 0.8 m, DE [degC]

# Design velocity window for DH distribution pipes (EN 13941 / Frederiksen
# and Werner 2013): below 0.5 m/s sediment settles, above 3 m/s noise and
# erosion become limiting.
V_MIN, V_MAX = 0.5, 3.0


# =====================================================================
# (C) European district-heating cost and reliability data
# =====================================================================
@dataclass(frozen=True)
class EuroCost:
    """Cost model for the real German networks.

    Pipe capital cost uses the standard two-parameter DH trench-cost function
    C = C1 + C2 * dn  [EUR per trench metre], from Persson U. and Werner S.
    (2011), "Heat distribution and the future competitiveness of district
    heating", Applied Energy 88(3), 568-576.
    """

    C1: float = 212.0            # fixed trench cost [EUR/m]
    C2: float = 4790.0           # diameter-dependent cost [EUR/(m*m)]
    # Eurostat, non-household electricity price, Germany, H2 2025,
    # 2 000-20 000 MWh/y consumption band, excluding recoverable VAT.
    elec_price: float = 0.1922   # electricity price [EUR/kWh]
    # Marginal cost of replacing lost heat: Eurostat non-household gas price
    # for Germany divided by a 0.90 boiler efficiency.
    heat_price: float = 0.055    # value of heat lost [EUR/kWh]
    pump_eta: float = 0.75       # wire-to-water pump efficiency [-]
    lifetime: int = 30           # DH network economic lifetime [y]
    discount: float = 0.04       # real discount rate [-]
    # Annual full-load hours for existing German residential stock (~1800 h/a);
    # AixDHN demand is private-household heat, so this is the matching figure.
    full_load_hours: float = 1800.0    # annual full-load hours [h/y]
    op_hours: float = 5000.0           # annual pump operating hours [h/y]
    PN_rating: float = 16e5            # pipe pressure class PN16 [Pa]
    p_cavitation_margin: float = 0.5e5  # margin above p_sat [Pa]
    zone_hx_cost: float = 250_000.0    # pressure-zone heat exchanger station [EUR]

    @property
    def crf(self) -> float:
        f = (1 + self.discount) ** self.lifetime
        return self.discount * f / (f - 1)


EURO = EuroCost()


@dataclass(frozen=True)
class ReliabilityParams:
    """Failure statistics for buried DH pipe.

    Base rates from Valincius M. et al. (2015), "Integrated assessment of
    failure probability of the district heating network", Reliability
    Engineering and System Safety 133, 314-322, and Valincius et al. (2014),
    "Probability of Failure Assessment in District Heating Network":
        pre-insulated bonded pipe    0.02 failures/(km y)
        duct-channel pipe            0.19 failures/(km y)
        pipe inside buildings        0.31 failures/(km y)
        surface-corrosion mechanism  0.07 failures/(km y)
    Small diameters (DN <= 150) show elevated rates.
    """

    base_rate: float = 0.02        # pre-insulated bonded [1/(km y)]
    corrosion_rate: float = 0.07   # corrosion contribution [1/(km y)]
    small_dn_factor: float = 1.6   # multiplier for DN <= 150
    small_dn_threshold: int = 150
    repair_time_h: float = 12.0    # mean time to repair a burst [h]


RELIABILITY = ReliabilityParams()


# =====================================================================
# (D) Terrain / trenching cost model
# =====================================================================
@dataclass(frozen=True)
class TerrainParams:
    """Slope-dependent trenching cost multiplier.

    Pipeline construction cost rises sharply with ground gradient because of
    benching, anchor blocks and reduced plant productivity. We use the
    quadratic form f(s) = 1 + a1*s + a2*s^2 in ground slope s = tan(theta),
    fitted to the industry cost factors reported for pipeline terrain classes
    (flat 1.0, rolling ~1.6 at 15 deg, mountainous ~3.0 at 30 deg); see
    Rui Z. et al. (2011), "Historical pipeline construction cost analysis",
    Int. J. Oil, Gas and Coal Technology 4(3), 244-263.
    """

    a1: float = 1.176
    a2: float = 3.968
    max_slope: float = 0.60      # ~31 deg: steeper is not trenchable
    rock_slope: float = 0.25     # above this slope assume rock excavation
    rock_factor: float = 1.35    # extra multiplier for rock
