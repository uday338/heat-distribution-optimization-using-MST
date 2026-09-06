"""
run_real.py - The main study: topology optimisation of two REAL German
district-heating networks, one on flat ground and one in hilly terrain.

Everything in this pipeline is driven by measured data:
    node locations   AixDHN census-cell coordinates (RWTH Aachen EBC, MIT)
    heat demand      AixDHN annual household DH demand [MWh/y]
    terrain          NASA SRTM 30 m elevation, via OpenTopoData
    pipe geometry    EN 253 pre-insulated catalogue
    costs            Persson & Werner (2011) trench function; Eurostat energy
    failure rates    Valincius et al. (2015)

Topologies compared:
    Star            every consumer on its own dedicated pipe
    MST-2D          minimum spanning tree on map distance (what Gao et al. do)
    MST-terrain     minimum spanning tree on terrain-weighted construction cost
    ESMT            Euclidean Steiner tree (free routing)
    RSMT            Rectilinear Steiner tree (street-grid routing)
    MST-terrain+R   terrain MST with greedy redundant edges (our reliability
                    extension)
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time

import numpy as np

sys.path.insert(0, "src")

import reliability as rel
import structure as st
from costs import euro_tac
from dataset import build_nodes, load_all
from dem import build_dem
from flow_lp import solve_flows_tree
from mst import (
    adjacency_from_matrix,
    complete_graph_edges,
    euclidean_weights,
    kruskal,
    prim,
    star_edges,
)
from params import EURO, WATER
from steiner import esmt, extend_demands, rsmt
from terrain import TerrainCost, node_elevations, relief_stats

STUDY = {
    "flat": ("Bremen_040110000_c1", "Bremen (North German Plain)"),
    "hilly": ("Stuttgart_081110000_c11", "Stuttgart (Neckar basin)"),
}
N_USERS = 40
OUT = "results"


def route_elevations(dem, xy, edges, ds: float = 25.0):
    """Every sampled elevation along the pipes of a topology.

    The pressure-rating constraint has to be checked along the route, not just
    at the substations, because a trench that crosses a valley experiences
    that valley's static head.
    """
    zs = []
    for (u, v) in edges:
        _, z = dem.profile(xy[u], xy[v], ds=ds)
        zs.append(z)
    return np.concatenate(zs) if zs else np.array([0.0])


def _edge_info(cost_obj, edges):
    """Extract the per-branch hydraulic info the reliability model needs."""
    pe = cost_obj.detail["per_edge"]
    return {
        e: {"L3d": pe[e]["L3d"], "dn": pe[e]["dn"],
            "u": pe[e]["u"], "d_in": pe[e]["d_in"]}
        for e in edges
    }


def analyse_district(tag: str, ident: str, label: str) -> dict:
    print(f"\n{'='*74}\n{label}   [{ident}]\n{'='*74}")
    ds = {d.ident: d for d in load_all()}
    district = ds[ident]

    # ---- nodes from real census cells, demand from real annual heat sales
    nodes = build_nodes(district, n_users=N_USERS,
                        full_load_hours=EURO.full_load_hours)
    xy, demand = nodes.xy, nodes.demand_kW
    n = len(xy)
    print(f"  {district.n_cells} census cells -> {N_USERS} substations + 1 plant")
    print(f"  real annual demand {district.dh_demand_MWh:,.0f} MWh/y "
          f"({district.households:,} households)")
    print(f"  design load {demand[demand>0].sum():,.0f} kW "
          f"at {EURO.full_load_hours:.0f} full-load hours")

    # ---- real terrain
    dem = build_dem(district.cells, step=100.0, cache=f"data/dem/{ident}.pkl")
    z = node_elevations(dem, xy)
    rs = relief_stats(z)
    print(f"  SRTM relief across nodes: {rs['z_min']:.0f}..{rs['z_max']:.0f} m "
          f"(range {rs['relief_m']:.0f} m, sd {rs['z_std']:.1f} m)")

    tc = TerrainCost(dem, ds=25.0)
    print("  computing terrain-weighted route costs for all node pairs ...")
    t0 = time.time()
    M = tc.matrices(xy)
    print(f"    {n*(n-1)//2} candidate routes in {time.time()-t0:.1f}s")

    W2d = euclidean_weights(xy)
    Wterr = M["W"]

    # ---- topologies -----------------------------------------------------
    topo = {}
    topo["Star"] = (star_edges(n), xy, demand, M)

    e_mst = kruskal(n, list(complete_graph_edges(W2d))).edges
    topo["MST-2D"] = (e_mst, xy, demand, M)

    e_terr = kruskal(n, list(complete_graph_edges(Wterr))).edges
    topo["MST-terrain"] = (e_terr, xy, demand, M)

    # Steiner trees introduce new junction nodes, so they need their own
    # terrain matrices and their own elevations.
    for name, fn in [("ESMT", esmt), ("RSMT", rsmt)]:
        print(f"  building {name} ...")
        s = fn(xy)
        sxy = s.xy
        sdem = extend_demands(demand, len(s.steiner_points))
        sM = TerrainCost(dem, ds=25.0).matrices(sxy)
        topo[name] = (s.edges, sxy, sdem, sM)
        print(f"    {len(s.steiner_points)} Steiner points, "
              f"length {s.length/1000:.2f} km vs MST {s.mst_length/1000:.2f} km "
              f"({s.gain_pct:+.2f} %)")

    # ---- evaluate -------------------------------------------------------
    results = {}
    for name, (edges, nxy, ndem, nM) in topo.items():
        nn = len(nxy)
        nz = node_elevations(dem, nxy)
        zr = route_elevations(dem, nxy, edges)
        c = euro_tac(nn, edges, nM, ndem, nz, z_route=zr)
        info = _edge_info(c, edges)
        r = rel.evaluate(nn, edges, ndem, info)
        s = st.analyse(nn, edges, nM["L3d"], ndem)
        results[name] = dict(
            n_nodes=nn, n_edges=len(edges),
            length_2d_km=c.length_2d / 1000, length_3d_km=c.length_3d / 1000,
            trench_km=c.trench_weighted / 1000,
            capital=c.capital, pumping=c.pumping, heat_loss=c.heat_loss,
            zones=c.zones, total=c.total,
            specific_cost=c.specific_cost, n_zones=c.n_zones,
            pump_head_bar=c.pump_head_bar, heat_loss_MWh=c.heat_loss_MWh,
            delivered_MWh=c.delivered_MWh,
            eud_MWh=r.eud_MWh, worst_case_kW=r.worst_case_kW,
            n1_served=r.n1_served_fraction, n_bridges=r.n_bridges,
            **s,
        )
        print(f"    {name:12s} {c.length_3d/1000:6.2f} km  "
              f"TAC {c.total/1e6:6.3f} M EUR/y  "
              f"{c.specific_cost:6.2f} EUR/MWh  "
              f"zones {c.n_zones}  N-1 served {100*r.n1_served_fraction:5.1f}%")

    # ---- reliability extension on the terrain MST ------------------------
    print("\n  reliability augmentation (greedy redundant edges):")
    edges, nxy, ndem, nM = topo["MST-terrain"]
    base = euro_tac(n, edges, nM, ndem, z,
                    z_route=route_elevations(dem, nxy, edges))
    base_info = _edge_info(base, edges)

    def cost_fn(u, v, backup_kW):
        import hydraulics as hyd
        mdot = hyd.mdot_from_load(max(backup_kW, 1.0),
                                  WATER.T_supply_C - WATER.T_return_C, WATER.cp)
        pipe = hyd.select_pipe(mdot, WATER.rho, WATER.mu)
        lw = nM["W"][u, v]
        if not np.isfinite(lw):
            lw = nM["L3d"][u, v] * 10
        return (EURO.C1 + EURO.C2 * pipe.d_casing) * lw * EURO.crf

    def info_fn(u, v, backup_kW):
        import hydraulics as hyd
        mdot = hyd.mdot_from_load(max(backup_kW, 1.0),
                                  WATER.T_supply_C - WATER.T_return_C, WATER.cp)
        pipe = hyd.select_pipe(mdot, WATER.rho, WATER.mu)
        if (u, v) in base_info:
            return base_info[(u, v)]
        return {"L3d": nM["L3d"][u, v], "dn": pipe.dn,
                "u": pipe.u, "d_in": pipe.d_in}

    cands = [(u, v) for u in range(n) for v in range(u + 1, n)
             if np.isfinite(nM["W"][u, v])]
    aug_edges, steps = rel.greedy_augment(
        n, edges, ndem, cands, cost_fn, info_fn, base.total, k_max=4)

    # The greedy search ranks candidate edges cheaply. The reported
    # trade-off curve is then recomputed properly: at every step the whole
    # network is re-sized under the N-1 criterion, which is the only sizing
    # that reflects what the redundancy is actually for.
    print("  re-costing the trade-off curve with full N-1 sizing:")
    added = [s.edge for s in steps if s.edge is not None]
    curve = []
    for k in range(len(added) + 1):
        ek = list(edges) + added[:k]
        ck = euro_tac(n, ek, nM, ndem, z,
                      z_route=route_elevations(dem, nxy, ek))
        rk = rel.evaluate(n, ek, ndem, _edge_info(ck, ek))
        curve.append(dict(
            k=k, edge=added[k - 1] if k else None,
            total=ck.total, specific_cost=ck.specific_cost,
            cost_premium_pct=100.0 * (ck.total - base.total) / base.total,
            eud_MWh=rk.eud_MWh,
            eud_reduction_pct=100.0 * (curve[0]["eud_MWh"] - rk.eud_MWh)
            / max(curve[0]["eud_MWh"], 1e-12) if curve else 0.0,
            n1_served_fraction=rk.n1_served_fraction,
            n_bridges=rk.n_bridges,
            length_3d_km=ck.length_3d / 1000,
        ))
        print(f"    k={k}  TAC {ck.specific_cost:6.2f} EUR/MWh  "
              f"premium {curve[-1]['cost_premium_pct']:+6.2f}%  "
              f"EUD -{curve[-1]['eud_reduction_pct']:5.1f}%  "
              f"N-1 served {100*rk.n1_served_fraction:5.1f}%  "
              f"bridges {rk.n_bridges}")

    aug_cost = euro_tac(n, aug_edges, nM, ndem, z,
                        z_route=route_elevations(dem, nxy, aug_edges))
    aug_info = _edge_info(aug_cost, aug_edges)
    aug_r = rel.evaluate(n, aug_edges, ndem, aug_info)
    results["MST-terrain+R"] = dict(
        n_nodes=n, n_edges=len(aug_edges),
        length_2d_km=aug_cost.length_2d / 1000,
        length_3d_km=aug_cost.length_3d / 1000,
        trench_km=aug_cost.trench_weighted / 1000,
        capital=aug_cost.capital, pumping=aug_cost.pumping,
        heat_loss=aug_cost.heat_loss, zones=aug_cost.zones,
        total=aug_cost.total, specific_cost=aug_cost.specific_cost,
        n_zones=aug_cost.n_zones, pump_head_bar=aug_cost.pump_head_bar,
        heat_loss_MWh=aug_cost.heat_loss_MWh,
        delivered_MWh=aug_cost.delivered_MWh,
        eud_MWh=aug_r.eud_MWh, worst_case_kW=aug_r.worst_case_kW,
        n1_served=aug_r.n1_served_fraction, n_bridges=aug_r.n_bridges,
        **st.analyse(n, aug_edges, nM["L3d"], ndem),
    )

    payload = dict(
        tag=tag, ident=ident, label=label,
        district=dict(name=district.name, state=district.state,
                      area_km2=district.area_km2,
                      demand_MWh=district.dh_demand_MWh,
                      households=district.households, cells=district.n_cells),
        relief=rs, results=results,
        augmentation=[s.__dict__ for s in steps],
        tradeoff=curve,
    )
    with open(f"{OUT}/tables/{tag}_results.json", "w") as fh:
        json.dump(payload, fh, indent=1, default=float)
    with open(f"{OUT}/{tag}_topologies.pkl", "wb") as fh:
        pickle.dump(dict(xy=xy, z=z, demand=demand, M=M, topo=topo,
                         aug_edges=aug_edges, dem=dem), fh)
    return payload


if __name__ == "__main__":
    os.makedirs(f"{OUT}/tables", exist_ok=True)
    out = {}
    for tag, (ident, label) in STUDY.items():
        out[tag] = analyse_district(tag, ident, label)
    with open(f"{OUT}/tables/summary.json", "w") as fh:
        json.dump(out, fh, indent=1, default=float)
    print("\nDone.")
