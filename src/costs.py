"""
costs.py - Total annual cost models.

Two independent implementations:

  gao_tac()  - the published model of Gao et al. (2020), Eq(1)-(24), coded
               literally so the reproduction is a fair test of THEIR model.
  euro_tac() - our extended model for a real buried hot-water network:
               discrete pipe sizing, Colebrook friction, buried twin-pipe heat
               loss, terrain-weighted trenching, and the pressure-zone
               penalty that terrain forces.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

import hydraulics as hyd
import thermal as th
from flow_lp import root_tree
from params import (
    BURIAL_DEPTH,
    EURO,
    G,
    GAO,
    LAMBDA_PUR,
    LAMBDA_SOIL,
    T_GROUND_C,
    WATER,
)

SECONDS_PER_HOUR = 3600.0


# =====================================================================
# (A) Gao et al. (2020) - literal implementation
# =====================================================================
def gao_diameters(W_kg_s: float, p=GAO) -> tuple[float, float, float]:
    """Eq(6), (15), (14): inner diameter, outer diameter, unit weight.

        D_in  = sqrt(4 W / (pi rho u))
        D_out = 1.052 D_in + 0.005251
        Wt    = 644.3 D_in^2 + 72.5 D_in + 0.4611
    """
    if W_kg_s <= 0:
        return 0.0, 0.0, 0.0
    d_in = math.sqrt(4.0 * W_kg_s / (math.pi * p.rho * p.u))
    d_out = 1.052 * d_in + 0.005251
    wt = 644.3 * d_in * d_in + 72.5 * d_in + 0.4611
    return d_in, d_out, wt


def gao_unit_price(d_out: float, wt: float, p=GAO) -> float:
    """Eq(13): a_k = A1*Wt + A2*D_out^0.48 + A3 + A4*D_out  [CNY/m]."""
    if d_out <= 0:
        return 0.0
    return p.A1 * wt + p.A2 * d_out**0.48 + p.A3 + p.A4 * d_out


def gao_heat_loss_per_m(d_out: float, p=GAO) -> float:
    """Eq(24): heat loss [kJ/(m s)] through the insulation.

        Q = pi (T - Ta) / (1000 (ln(Dn/D0)/(2 lambda) + 1/(eps Dn)))
    """
    if d_out <= 0:
        return 0.0
    d0 = d_out
    if p.ins_mode == "proportional":
        t = p.ins_ratio * d_out
    elif p.ins_mode == "en_scaling":
        t = p.ins_coeff * d_out**p.ins_exp
    else:
        t = p.t_ins
    dn = d_out + 2.0 * t
    T_amb_C = p.T_amb - 273.15
    denom = math.log(dn / d0) / (2.0 * p.lam_ins) + 1.0 / (p.eps_ext * dn)
    return math.pi * (p.T_steam_C - T_amb_C) / (1000.0 * denom)


def gao_zeta(S_k: float, S_parent: float) -> float:
    """Eq(21): local loss from the area change between a branch and its parent.

    Contraction (S_k < S_parent):  zeta = 0.5 (1 - S_k/S_parent)
    Expansion   (S_k > S_parent):  zeta = (1 - S_parent/S_k)^2
    """
    if S_parent <= 0 or S_k <= 0:
        return 0.0
    if S_k < S_parent:
        return 0.5 * (1.0 - S_k / S_parent)
    if S_k > S_parent:
        return (1.0 - S_parent / S_k) ** 2
    return 0.0


@dataclass
class GaoCost:
    pipe: float
    pressure: float
    heat: float
    total: float
    length: float
    detail: dict = field(default_factory=dict)

    def as_1e7(self) -> dict:
        return {
            "length_1e4_m": self.length / 1e4,
            "pipe_1e7": self.pipe / 1e7,
            "pressure_1e7": self.pressure / 1e7,
            "heat_1e7": self.heat / 1e7,
            "total_1e7": self.total / 1e7,
        }


def gao_tac(n: int, edges, lengths: dict, flows: dict, p=GAO,
            root: int = 0) -> GaoCost:
    """Total annual cost of a topology under the published Gao model.

    edges   : list of (u, v)
    lengths : {(u, v): L [m]}
    flows   : {(u, v): W [kg/s]} from the Eq(7)-(12) allocation
    """
    parent, order = root_tree(n, edges, root)
    # map each node to the edge feeding it, so we can find a branch's parent
    feed = {}
    for (u, v) in edges:
        child = v if parent[v] == u else u
        feed[child] = (u, v)

    areas, geom = {}, {}
    for e in edges:
        W = flows[e]
        d_in, d_out, wt = gao_diameters(W, p)
        geom[e] = (d_in, d_out, wt)
        areas[e] = math.pi * d_in * d_in / 4.0

    C_pipe = C_press = C_heat = L_tot = 0.0
    per_edge = {}
    for e in edges:
        u, v = e
        L = lengths[e]
        W = flows[e]
        d_in, d_out, wt = geom[e]
        L_tot += L

        # --- capital, Eq(5) + Eq(13)
        a_k = gao_unit_price(d_out, wt, p)
        cap = p.crf * a_k * L

        # --- pressure drop, Eq(16)-(22)
        child = v if parent[v] == u else u
        par_node = parent[child]
        pe = feed.get(par_node)
        zeta_k = gao_zeta(areas[e], areas[pe]) if pe is not None else 0.0
        zeta_E = p.zeta_elbow * L / p.elbow_spacing
        H_f = ((p.sigma * L / d_in if d_in > 0 else 0.0) + zeta_k + zeta_E) \
            * p.u**2 / (2.0 * G)
        Ne = H_f * W * G                       # Eq(18) available power [W]
        N = Ne / p.eta                         # Eq(17) shaft power [W]
        press = p.aE * p.t_time * N / 1000.0   # Eq(16) [CNY/y]

        # --- heat loss, Eq(23)+(24)
        Q = gao_heat_loss_per_m(d_out, p)      # [kJ/(m s)]
        heat = p.a_steam * Q * L * (p.t_time * SECONDS_PER_HOUR) / p.q_latent

        C_pipe += cap
        C_press += press
        C_heat += heat
        per_edge[e] = dict(L=L, W=W, d_in=d_in, d_out=d_out, a_k=a_k,
                           H_f=H_f, N=N, Q=Q, cap=cap, press=press, heat=heat)

    return GaoCost(
        pipe=C_pipe, pressure=C_press, heat=C_heat,
        total=C_pipe + C_press + C_heat, length=L_tot,
        detail={"per_edge": per_edge},
    )


# =====================================================================
# (B) Extended model for a real buried hot-water network
# =====================================================================
@dataclass
class EuroCost_:
    capital: float          # annualised pipe capital [EUR/y]
    pumping: float          # electricity for circulation [EUR/y]
    heat_loss: float        # value of heat lost to ground [EUR/y]
    zones: float            # annualised pressure-zone stations [EUR/y]
    total: float
    length_2d: float
    length_3d: float
    trench_weighted: float
    n_zones: int
    pump_head_bar: float
    heat_loss_MWh: float
    delivered_MWh: float
    detail: dict = field(default_factory=dict)

    @property
    def specific_cost(self) -> float:
        """EUR per MWh delivered - the scale-invariant comparison metric."""
        return self.total / max(self.delivered_MWh, 1e-9)


def euro_tac(n: int, edges, metrics: dict, demand_kW, z, p=EURO,
             water=WATER, root: int = 0, flows=None, z_route=None) -> EuroCost_:
    """Extended TAC for a real buried DH network on real terrain.

    metrics : output of terrain.TerrainCost.matrices() - needs L2d, L3d, W
    demand_kW : node design loads [kW], entry `root` negative (the plant)
    z : node elevations [m a.s.l.]

    Physics, in order:
      * mass flow from the load and the design temperature difference
      * discrete DN selection on velocity and specific pressure drop
      * Colebrook friction, giving a real pressure drop per branch
      * pump duty = worst supply+return path (static head cancels in the loop)
      * buried twin-pipe heat loss with mutual coupling
      * capital on the TERRAIN-WEIGHTED trench length
      * pressure-zone stations where the static profile exceeds PN16
    """
    from flow_lp import design_flows_n1, solve_flows_tree

    demand_kW = np.asarray(demand_kW, dtype=float)
    if flows is None:
        if len(edges) == n - 1:
            flows = solve_flows_tree(n, edges, demand_kW, root)
        else:
            # The topology contains cycles, so flow allocation is a genuine
            # optimisation rather than a forced accounting identity - this is
            # the only regime in which the Eq(7)-(12) LP does real work. Pipes
            # are sized on the N-1 design flow, not the normal split flow.
            lengths = [float(metrics["L3d"][u, v]) for (u, v) in edges]
            flows = design_flows_n1(n, edges, demand_kW, root, lengths)

    L2d, L3d, Wt = metrics["L2d"], metrics["L3d"], metrics["W"]
    dT = water.T_supply_C - water.T_return_C

    parent, order = root_tree(n, edges, root)
    per_edge = {}
    cap = q_loss_W = 0.0
    tot2d = tot3d = totw = 0.0

    for (u, v) in edges:
        load_kW = flows[(u, v)]
        mdot = hyd.mdot_from_load(load_kW, dT, water.cp)
        pipe = hyd.select_pipe(mdot, water.rho, water.mu)
        l2, l3, lw = L2d[u, v], L3d[u, v], Wt[u, v]
        if not np.isfinite(lw):
            lw = l3 * 10.0                      # infeasible route, heavy penalty

        dp, f, uu = hyd.pressure_drop(mdot, pipe.d_in, l3, water.rho, water.mu)

        bp = th.BuriedPipe(pipe.d_in, pipe.d_steel, pipe.d_casing, BURIAL_DEPTH)
        q_m = th.heat_loss_buried(bp, water.T_supply_C, water.T_return_C,
                                  T_GROUND_C, LAMBDA_PUR, LAMBDA_SOIL)

        cap += (p.C1 + p.C2 * pipe.d_casing) * lw
        q_loss_W += q_m * l3
        tot2d += l2
        tot3d += l3
        totw += lw
        per_edge[(u, v)] = dict(load_kW=load_kW, mdot=mdot, dn=pipe.dn,
                                d_in=pipe.d_in, d_casing=pipe.d_casing,
                                u=uu, f=f, dp=dp, q_per_m=q_m,
                                L2d=l2, L3d=l3, Lw=lw)

    # --- pump duty: the worst consumer path, supply + return -------------
    # Map each node to the edge that feeds it in the BFS tree. Built from the
    # parent array (not by scanning edges) so it stays correct when the
    # topology contains cycles and some edges are not tree edges.
    eset = {}
    for (u, v) in edges:
        eset[(u, v)] = (u, v)
        eset[(v, u)] = (u, v)
    feed = {v: eset[(parent[v], v)] for v in range(n)
            if parent[v] >= 0 and (parent[v], v) in eset}
    worst = 0.0
    for node in range(n):
        if node == root or demand_kW[node] <= 0:
            continue
        dpsum, cur, guard = 0.0, node, 0
        while cur != root and parent[cur] >= 0 and cur in feed and guard < n:
            dpsum += per_edge[feed[cur]]["dp"]
            cur = parent[cur]
            guard += 1
        worst = max(worst, dpsum)
    dp_pump = hyd.closed_loop_pump_dp(worst, worst)     # supply + return legs

    mdot_total = hyd.mdot_from_load(float(demand_kW[demand_kW > 0].sum()),
                                    dT, water.cp)
    P_pump_W = hyd.pump_power(mdot_total, dp_pump, water.rho, p.pump_eta)
    pumping = P_pump_W / 1000.0 * p.op_hours * p.elec_price

    # --- heat loss valued at the heat price ------------------------------
    heat_MWh = q_loss_W / 1e6 * 8760.0
    heat_cost = heat_MWh * 1000.0 * p.heat_price

    # --- pressure zones forced by terrain --------------------------------
    # The static pressure constraint applies along the WHOLE route, not only
    # at the substations: a pipe that dips through a valley between two nodes
    # sees that valley's pressure. z_route therefore carries every sampled
    # elevation along the chosen edges, and falls back to node elevations only
    # if profiles were not supplied.
    z_check = z if z_route is None else np.asarray(z_route, dtype=float)
    chk = hyd.static_pressure_check(z_check, rho=water.rho, PN=p.PN_rating,
                                    p_sat=water.p_sat_supply,
                                    margin=p.p_cavitation_margin)
    zone_cost = (chk.n_zones - 1) * p.zone_hx_cost * p.crf

    capital = cap * p.crf
    delivered = float(demand_kW[demand_kW > 0].sum()) * p.full_load_hours / 1000.0

    return EuroCost_(
        capital=capital, pumping=pumping, heat_loss=heat_cost, zones=zone_cost,
        total=capital + pumping + heat_cost + zone_cost,
        length_2d=tot2d, length_3d=tot3d, trench_weighted=totw,
        n_zones=chk.n_zones, pump_head_bar=dp_pump / 1e5,
        heat_loss_MWh=heat_MWh, delivered_MWh=delivered,
        detail={"per_edge": per_edge, "pressure": chk},
    )
