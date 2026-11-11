"""
run_final.py - the post-prelim analyses (PROGRESS_REPORT section 7).

  A. sanity   : re-cost the stored greedy trade-off curve (LP via scipy/HiGHS)
  B. scaling  : 20..160 substations x 10 clusterings, MST-2D vs MST-terrain
  C. exact    : exhaustive optimum for k<=3 redundant pipes vs the greedy
  D. sens     : temperature regime, pressure class, slope-multiplier strength
  E. seasonal : part-load pumping and heat loss over a load-duration curve

Everything uses the repo's own modules; nothing is re-implemented except the
LP back-end (pulp is not installed here, scipy's HiGHS solves the same LP).
"""
from __future__ import annotations
import dataclasses, itertools, json, math, pickle, sys, time
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

sys.path.insert(0, "src")
import flow_lp, hydraulics as hyd, reliability as rel, thermal as th
from costs import euro_tac
from dataset import build_nodes, load_all
from dem import build_dem
from flow_lp import root_tree, solve_flows_tree
from mst import complete_graph_edges, euclidean_weights, kruskal, star_edges
from params import (EURO, WATER, TerrainParams, BURIAL_DEPTH, LAMBDA_PUR,
                    LAMBDA_SOIL, T_GROUND_C)
from terrain import TerrainCost, node_elevations

G = 9.81
STUDY = {"flat": "Bremen_040110000_c1", "hilly": "Stuttgart_081110000_c11"}
OUT = {}


# ------------------------------------------------------------------ LP backend
def solve_flows_lp_scipy(n, edges, demand, lengths=None, objective="gao", msg=False):
    demand = np.asarray(demand, float)
    m = len(edges)
    c = np.ones(2 * m)
    if objective == "transport" and lengths is not None:
        c = np.repeat(np.asarray(lengths, float), 2)
    rows, cols, vals = [], [], []
    for k, (u, v) in enumerate(edges):
        # var 2k: u->v, var 2k+1: v->u ; row g: inflow - outflow = demand[g]
        rows += [v, u, u, v]; cols += [2 * k, 2 * k, 2 * k + 1, 2 * k + 1]
        vals += [1, -1, 1, -1]
    A = coo_matrix((vals, (rows, cols)), shape=(n, 2 * m)).tocsr()
    r = linprog(c, A_eq=A, b_eq=demand, bounds=(0, None), method="highs")
    if r.status != 0:
        raise RuntimeError(r.message)
    return {e: float(abs(r.x[2 * k] - r.x[2 * k + 1])) for k, e in enumerate(edges)}


flow_lp.solve_flows_lp = solve_flows_lp_scipy


def route_z(dem, xy, edges, ds=25.0):
    return np.concatenate([dem.profile(xy[u], xy[v], ds=ds)[1] for u, v in edges])


def einfo(c, edges):
    pe = c.detail["per_edge"]
    return {e: {k: pe[e][k] for k in ("L3d", "dn", "u", "d_in")} for e in edges}


def load(tag):
    with open(f"results/{tag}_topologies.pkl", "rb") as fh:
        return pickle.load(fh)


DISTRICTS = {d.ident: d for d in load_all()}


# =================================================================== A. sanity
def part_A():
    print("\n[A] re-costing stored trade-off curves with the scipy LP")
    out = {}
    for tag in STUDY:
        P = load(tag)
        stored = json.load(open(f"results/tables/{tag}_results.json"))["tradeoff"]
        xy, z, dem_, M, dem = P["xy"], P["z"], P["demand"], P["M"], P["dem"]
        n = len(xy)
        edges = P["topo"]["MST-terrain"][0]
        added = [tuple(s["edge"]) for s in stored[1:]]
        rows = []
        for k in range(len(added) + 1):
            ek = list(edges) + added[:k]
            ck = euro_tac(n, ek, M, dem_, z, z_route=route_z(dem, xy, ek))
            rk = rel.evaluate(n, ek, dem_, einfo(ck, ek))
            rows.append(dict(k=k, specific=ck.specific_cost, stored=stored[k]["specific_cost"],
                             eud=rk.eud_MWh, stored_eud=stored[k]["eud_MWh"],
                             n1=rk.n1_served_fraction, bridges=rk.n_bridges))
            print(f"  {tag} k={k}  {ck.specific_cost:7.3f} (stored {stored[k]['specific_cost']:7.3f})"
                  f"  EUD {rk.eud_MWh:8.2f} (stored {stored[k]['eud_MWh']:8.2f})")
        out[tag] = rows
    OUT["A_sanity"] = out


# ================================================================== B. scaling
def one_network(district, dem, n_users, seed, tp=None, water=WATER, econ=EURO):
    nodes = build_nodes(district, n_users=n_users, full_load_hours=econ.full_load_hours, seed=seed)
    xy, demand = nodes.xy, nodes.demand_kW
    n = len(xy)
    z = node_elevations(dem, xy)
    M = TerrainCost(dem, params=tp, ds=25.0).matrices(xy)
    e2 = kruskal(n, list(complete_graph_edges(euclidean_weights(xy)))).edges
    et = kruskal(n, list(complete_graph_edges(M["W"]))).edges
    res = {}
    for name, e in (("MST-2D", e2), ("MST-terrain", et)):
        zr = route_z(dem, xy, e)
        c = euro_tac(n, e, M, demand, z, p=econ, water=water, z_route=zr)
        r = rel.evaluate(n, e, demand, einfo(c, e))
        res[name] = dict(specific=c.specific_cost, total=c.total, capital=c.capital,
                         pumping=c.pumping, heat=c.heat_loss, zones=c.n_zones,
                         L3d_km=c.length_3d / 1000, trench_km=c.trench_weighted / 1000,
                         route_relief=float(zr.max() - zr.min()), n1=r.n1_served_fraction,
                         eud=r.eud_MWh, pump_bar=c.pump_head_bar)
    same = {tuple(sorted(e)) for e in e2} == {tuple(sorted(e)) for e in et}
    a, b = res["MST-2D"], res["MST-terrain"]
    return dict(n=n_users, seed=seed, identical=same,
                n_diff=len({tuple(sorted(e)) for e in e2} ^ {tuple(sorted(e)) for e in et}) // 2,
                saving_pct=100 * (a["total"] - b["total"]) / a["total"],
                d_capital_pct=100 * (a["capital"] - b["capital"]) / a["total"],
                d_pumping_pct=100 * (a["pumping"] - b["pumping"]) / a["total"],
                d_heat_pct=100 * (a["heat"] - b["heat"]) / a["total"],
                d_trench_pct=100 * (a["trench_km"] - b["trench_km"]) / a["trench_km"],
                **{f"{k}_2d": v for k, v in a.items()}, **{f"{k}_t": v for k, v in b.items()})


def part_B(sizes=(20, 40, 60, 80, 120, 160), seeds=(42, 0, 1, 2, 3, 4, 5, 6, 7, 8)):
    print("\n[B] scaling and clustering robustness")
    out = {}
    for tag, ident in STUDY.items():
        d = DISTRICTS[ident]
        dem = build_dem(d.cells, cache=f"data/dem/{ident}.pkl")
        rows = []
        for n_users in sizes:
            t0 = time.time()
            for s in seeds:
                rows.append(one_network(d, dem, n_users, s))
            rr = [r for r in rows if r["n"] == n_users]
            sv = np.array([r["saving_pct"] for r in rr])
            print(f"  {tag} n={n_users:3d}  saving mean {sv.mean():+5.2f}% "
                  f"[{sv.min():+5.2f},{sv.max():+5.2f}]  identical {sum(r['identical'] for r in rr)}/10 "
                  f" dcap {np.mean([r['d_capital_pct'] for r in rr]):+5.2f} dpump {np.mean([r['d_pumping_pct'] for r in rr]):+5.2f}"
                  f" dtrench {np.mean([r['d_trench_pct'] for r in rr]):+5.2f}%"
                  f"  zones {sorted(set(r['zones_t'] for r in rr))} n1 {np.mean([r['n1_t'] for r in rr]):.2f}"
                  f"  cost {np.mean([r['specific_t'] for r in rr]):.2f}  ({time.time()-t0:.0f}s)")
        out[tag] = rows
    OUT["B_scaling"] = out


# ==================================================================== C. exact
def tree_paths(n, edges, root=0):
    parent, order = root_tree(n, edges, root)
    idx = {}
    for k, (u, v) in enumerate(edges):
        idx[(u, v)] = k; idx[(v, u)] = k
    depth = np.zeros(n, int)
    for v in order:
        if parent[v] >= 0:
            depth[v] = depth[parent[v]] + 1

    def path_mask(a, b):
        m = 0
        while a != b:
            if depth[a] < depth[b]:
                a, b = b, a
            m |= 1 << idx[(a, parent[a])]
            a = parent[a]
        return m
    return path_mask


def part_C():
    print("\n[C] exhaustive optimum vs greedy redundancy (k <= 3)")
    out = {}
    for tag in STUDY:
        P = load(tag)
        xy, z, demand, M, dem = P["xy"], P["z"], P["demand"], P["M"], P["dem"]
        n = len(xy)
        edges = list(P["topo"]["MST-terrain"][0])
        m = len(edges)
        base = euro_tac(n, edges, M, demand, z, z_route=route_z(dem, xy, edges))
        binfo = einfo(base, edges)
        r0 = rel.evaluate(n, edges, demand, binfo)
        w = np.array([r0.per_edge[e]["eud_MWh"] for e in edges])      # EUD carried by each bridge
        eud0 = w.sum()
        backup = r0.worst_case_kW
        pipe = hyd.select_pipe(hyd.mdot_from_load(backup, WATER.T_supply_C - WATER.T_return_C, WATER.cp),
                               WATER.rho, WATER.mu)
        unit = (EURO.C1 + EURO.C2 * pipe.d_casing) * EURO.crf
        pm = tree_paths(n, edges)
        tset = {tuple(sorted(e)) for e in edges}
        cands = [(u, v) for u in range(n) for v in range(u + 1, n)
                 if np.isfinite(M["W"][u, v]) and (u, v) not in tset]
        masks = np.array([pm(u, v) for u, v in cands], dtype=np.uint64)
        cost = np.array([unit * M["W"][u, v] for u, v in cands]) / base.total * 100.0   # % premium
        C = len(cands)

        # weight-of-mask lookup, 10 bits at a time
        nb = math.ceil(m / 10)
        tabs = []
        for b in range(nb):
            ww = w[10 * b:10 * b + 10]
            t = np.zeros(1 << 10)
            for i in range(len(ww)):
                t[(np.arange(1 << 10) >> i) & 1 == 1] += ww[i]
            tabs.append(t)

        def covered(mk):
            s = np.zeros(mk.shape)
            for b in range(nb):
                s += tabs[b][((mk >> np.uint64(10 * b)) & np.uint64(1023)).astype(np.int64)]
            return s

        # sanity: closed form == repo's flood-fill evaluation
        stored = json.load(open(f"results/tables/{tag}_results.json"))
        g_edges = [tuple(s["edge"]) for s in stored["augmentation"][1:]]
        gi = [cands.index(tuple(sorted(e))) for e in g_edges]
        gm = np.uint64(0)
        greedy = []
        for k, i in enumerate(gi, 1):
            gm |= masks[i]
            e_closed = eud0 - covered(np.array([gm]))[0]
            greedy.append(dict(k=k, edge=cands[i], cost=float(cost[gi[:k]].sum()),
                               eud_red=100 * (1 - e_closed / eud0),
                               stored_eud=stored["augmentation"][k]["eud_MWh"], eud=float(e_closed)))
            assert abs(e_closed - stored["augmentation"][k]["eud_MWh"]) < 1e-6 * eud0, (e_closed, stored["augmentation"][k]["eud_MWh"])

        # exhaustive enumeration
        NB = 4000
        cmax = 40.0
        best = {k: dict(maxcov=-1.0, set=None) for k in (1, 2, 3)}
        front = {k: np.full(NB, -1.0) for k in (1, 2, 3)}             # best coverage per cost bin
        front_set = {k: [None] * NB for k in (1, 2, 3)}

        def push(k, cov, cst, sets_fn):
            j = int(np.argmax(cov))
            if cov[j] > best[k]["maxcov"]:
                best[k] = dict(maxcov=float(cov[j]), set=sets_fn(j), cost=float(cst[j]))
            b = np.minimum((cst / cmax * NB).astype(int), NB - 1)
            order = np.argsort(cov)
            fb = front[k]
            # last write wins -> ascending order leaves the max per bin
            tmp = np.full(NB, -1.0); tmpi = np.full(NB, -1)
            tmp[b[order]] = cov[order]; tmpi[b[order]] = order
            upd = tmp > fb
            for bb in np.nonzero(upd)[0]:
                fb[bb] = tmp[bb]; front_set[k][bb] = sets_fn(int(tmpi[bb]))

        t0 = time.time()
        cov1 = covered(masks)
        push(1, cov1, cost, lambda j: (j,))
        I, J = np.triu_indices(C, 1)
        pmask = masks[I] | masks[J]
        pcost = cost[I] + cost[J]
        push(2, covered(pmask), pcost, lambda j: (int(I[j]), int(J[j])))
        # triples: i < j < k ; pairs are sorted by I so pairs with I > i form a suffix
        start = np.searchsorted(I, np.arange(C), side="right")        # first pair index with I > i
        n3 = 0
        for i in range(C - 2):
            s = start[i]
            mk = pmask[s:] | masks[i]
            cv = covered(mk)
            cs = pcost[s:] + cost[i]
            n3 += len(cv)
            push(3, cv, cs, lambda j, i=i, s=s: (i, int(I[s + j]), int(J[s + j])))
        print(f"  {tag}: {C} candidates, {len(I):,} pairs, {n3:,} triples in {time.time()-t0:.0f}s")

        res = dict(n_cands=C, n_pairs=int(len(I)), n_triples=int(n3), eud0=float(eud0),
                   unit_dn=pipe.dn, greedy=greedy, exact={}, frontier={})
        for k in (1, 2, 3):
            # Pareto frontier over <=k pipes: running max of coverage along cost
            f = np.maximum.reduce([front[j] for j in range(1, k + 1)])
            run = np.maximum.accumulate(f)
            xs = (np.arange(NB) + 0.5) * cmax / NB
            keep = run > np.concatenate([[-1], run[:-1]])
            res["frontier"][k] = dict(cost=xs[keep].tolist(), eud_red=(100 * run[keep] / eud0).tolist())
            g = greedy[k - 1]
            # best set with <=k pipes costing no more than the greedy's
            gb = min(int(g["cost"] / cmax * NB), NB - 1)
            opt_budget = 100 * run[gb] / eud0
            bs = best[k]
            res["exact"][k] = dict(
                max_eud_red=100 * bs["maxcov"] / eud0, max_set=[cands[i] for i in bs["set"]],
                max_cost=bs["cost"], greedy_eud_red=g["eud_red"], greedy_cost=g["cost"],
                best_within_greedy_budget=float(opt_budget),
                gap_pts=float(opt_budget - g["eud_red"]))
            print(f"    k={k} greedy -{g['eud_red']:.1f}% at +{g['cost']:.2f}% | best at same budget -{opt_budget:.1f}% "
                  f"| unconstrained max -{100*bs['maxcov']/eud0:.1f}% at +{bs['cost']:.2f}% {res['exact'][k]['max_set']}")
            # find the budget-constrained optimum set identity
            bb = int(np.argmax(np.where(np.arange(NB) <= gb, f, -1)))
            for j in range(k, 0, -1):
                if front[j][bb] == f[bb] and front_set[j][bb] is not None:
                    res["exact"][k]["budget_set"] = [cands[i] for i in front_set[j][bb]]
                    break

        # full N-1 re-costing of greedy vs exact sets (k=3)
        def full(extra):
            ek = edges + list(extra)
            c = euro_tac(n, ek, M, demand, z, z_route=route_z(dem, xy, ek))
            r = rel.evaluate(n, ek, demand, einfo(c, ek))
            return dict(set=[tuple(e) for e in extra], premium=100 * (c.total - base.total) / base.total,
                        specific=c.specific_cost, eud_red=100 * (1 - r.eud_MWh / r0.eud_MWh),
                        n1=r.n1_served_fraction, bridges=r.n_bridges)
        res["full_n1"] = {}
        for k in (1, 2, 3):
            res["full_n1"][k] = dict(greedy=full(g_edges[:k]),
                                     exact_budget=full(res["exact"][k]["budget_set"]),
                                     exact_max=full(res["exact"][k]["max_set"]))
            for nm, v in res["full_n1"][k].items():
                print(f"      N-1 sized k={k} {nm:13s} premium {v['premium']:+6.2f}%  EUD -{v['eud_red']:.1f}%  "
                      f"N-1 served {100*v['n1']:.1f}%  bridges {v['bridges']}")
        out[tag] = res
    OUT["C_exact"] = out


# ============================================================== D. sensitivity
WATER_90 = dataclasses.replace(WATER, T_supply_C=90.0, T_return_C=45.0, rho=965.3, cp=4205.0,
                               mu=3.15e-4, p_sat_supply=0.701e5)


def eval_topos(tag, water=WATER, econ=EURO):
    P = load(tag)
    dem = P["dem"]
    out = {}
    for name, (edges, nxy, ndem, nM) in P["topo"].items():
        nn = len(nxy)
        c = euro_tac(nn, edges, nM, ndem, node_elevations(dem, nxy), p=econ, water=water,
                     z_route=route_z(dem, nxy, edges))
        out[name] = dict(specific=c.specific_cost, zones=c.n_zones, capital=c.capital, pumping=c.pumping,
                         heat=c.heat_loss, zone_cost=c.zones, total=c.total, pump_bar=c.pump_head_bar)
    return out


def part_D():
    print("\n[D] sensitivity")
    out = {"temperature": {}, "pressure_class": {}, "slope_strength": {}, "prices": {}}
    for tag in STUDY:
        out["temperature"][tag] = {"110/50": eval_topos(tag), "90/45": eval_topos(tag, water=WATER_90)}
        for reg, r in out["temperature"][tag].items():
            sv = 100 * (r["MST-2D"]["total"] - r["MST-terrain"]["total"]) / r["MST-2D"]["total"]
            print(f"  {tag} {reg}: " + "  ".join(f"{k} {v['specific']:.2f}" for k, v in r.items())
                  + f" | terrain saving {sv:+.2f}% zones {r['MST-terrain']['zones']}")
        out["pressure_class"][tag] = {}
        for PN in (10, 16, 25):
            for reg, wat in (("110/50", WATER), ("90/45", WATER_90)):
                econ = dataclasses.replace(EURO, PN_rating=PN * 1e5)
                r = eval_topos(tag, water=wat, econ=econ)
                lim = (PN * 1e5 - wat.p_sat_supply - econ.p_cavitation_margin) / (wat.rho * G)
                out["pressure_class"][tag][f"PN{PN} {reg}"] = dict(
                    relief_limit_m=lim, zones=r["MST-terrain"]["zones"], specific=r["MST-terrain"]["specific"])
                print(f"  {tag} PN{PN} {reg}: one-zone relief limit {lim:5.0f} m, zones {r['MST-terrain']['zones']}, "
                      f"{r['MST-terrain']['specific']:.2f} EUR/MWh")
        # price / economic sensitivity of the terrain saving (trees fixed, re-costed)
        out["prices"][tag] = {}
        for label, econ in (("base", EURO),
                            ("elec -50%", dataclasses.replace(EURO, elec_price=EURO.elec_price * 0.5)),
                            ("elec +50%", dataclasses.replace(EURO, elec_price=EURO.elec_price * 1.5)),
                            ("heat -50%", dataclasses.replace(EURO, heat_price=EURO.heat_price * 0.5)),
                            ("heat +50%", dataclasses.replace(EURO, heat_price=EURO.heat_price * 1.5)),
                            ("discount 2%", dataclasses.replace(EURO, discount=0.02)),
                            ("discount 6%", dataclasses.replace(EURO, discount=0.06))):
            r = eval_topos(tag, econ=econ)
            sv = 100 * (r["MST-2D"]["total"] - r["MST-terrain"]["total"]) / r["MST-2D"]["total"]
            rank = sorted(r, key=lambda k: r[k]["specific"])
            out["prices"][tag][label] = dict(saving=sv, ranking=rank,
                                             specific={k: v["specific"] for k, v in r.items()})
            print(f"  {tag} {label:12s} terrain saving {sv:+.2f}%  ranking {rank}")
    # slope-multiplier strength: scale (a1, a2) and rebuild the tree, 10 clusterings, n=40
    base = TerrainParams()
    for tag, ident in STUDY.items():
        d = DISTRICTS[ident]
        dem = build_dem(d.cells, cache=f"data/dem/{ident}.pkl")
        rows = []
        for sc in (0.0, 0.5, 1.0, 1.5, 2.0):
            tp = dataclasses.replace(base, a1=base.a1 * sc, a2=base.a2 * sc)
            rr = [one_network(d, dem, 40, s, tp=tp) for s in (42, 0, 1, 2, 3, 4, 5, 6, 7, 8)]
            sv = np.array([r["saving_pct"] for r in rr])
            rows.append(dict(scale=sc, savings=sv.tolist(), seed42=float(sv[0]),
                             n_diff=[r["n_diff"] for r in rr],
                             d_capital=[r["d_capital_pct"] for r in rr], d_pumping=[r["d_pumping_pct"] for r in rr]))
            print(f"  {tag} slope x{sc}: saving seed42 {sv[0]:+.2f}%  mean {sv.mean():+.2f}% [{sv.min():+.2f},{sv.max():+.2f}]"
                  f"  edges changed {np.mean([r['n_diff'] for r in rr]):.1f}")
        out["slope_strength"][tag] = rows
    OUT["D_sensitivity"] = out


# ================================================================= E. seasonal
def duration_curve(m0, q0, N=8760):
    """Sochinsky load-duration curve: q(t) = 1 - (1-q0) t^((m0-q0)/(1-m0)).
    m0 = load factor (= full-load hours / 8760), q0 = minimum (summer) load ratio."""
    t = (np.arange(N) + 0.5) / N
    return 1 - (1 - q0) * t ** ((m0 - q0) / (1 - m0))


def seasonal(tag, name, q0=0.10, Ts_min=80.0):
    P = load(tag)
    dem = P["dem"]
    edges, nxy, ndem, nM = P["topo"][name]
    n = len(nxy)
    c = euro_tac(n, edges, nM, ndem, node_elevations(dem, nxy), z_route=route_z(dem, nxy, edges))
    pe = c.detail["per_edge"]
    parent, order = root_tree(n, edges, 0)
    feed = {}
    for (u, v) in edges:
        child = v if parent[v] == u else u
        feed[child] = (u, v)
    # node -> list of edges to the plant
    paths = []
    for node in range(n):
        if node == 0 or ndem[node] <= 0:
            continue
        p, cur = [], node
        while cur != 0:
            p.append(feed[cur]); cur = parent[cur]
        paths.append(p)
    m0 = EURO.full_load_hours / 8760.0
    q = duration_curve(m0, q0)
    Tr = WATER.T_return_C
    # bin the year into 40 load levels
    levels = np.linspace(q.min(), 1.0, 41)
    mid = 0.5 * (levels[1:] + levels[:-1])
    hours = np.histogram(q, bins=levels)[0].astype(float)
    Ptot_design = float(ndem[ndem > 0].sum())
    E_pump = E_loss = 0.0
    for phi, h in zip(mid, hours):
        if h == 0:
            continue
        Ts = Ts_min + (WATER.T_supply_C - Ts_min) * (phi - q0) / (1 - q0)   # weather-compensated supply
        scale = phi * (WATER.T_supply_C - Tr) / (Ts - Tr)                  # mass-flow ratio to design
        dp = {e: hyd.pressure_drop(pe[e]["mdot"] * scale, pe[e]["d_in"], pe[e]["L3d"], WATER.rho, WATER.mu)[0]
              for e in edges}
        worst = max(sum(dp[e] for e in p) for p in paths)
        mdot_tot = hyd.mdot_from_load(Ptot_design, WATER.T_supply_C - Tr, WATER.cp) * scale
        E_pump += hyd.pump_power(mdot_tot, 2 * worst, WATER.rho, EURO.pump_eta) * h / 1000.0   # kWh
        for e in edges:
            bp = th.BuriedPipe(pe[e]["d_in"], [r for r in __import__("params").DN_CATALOGUE if r[0] == pe[e]["dn"]][0][2],
                               pe[e]["d_casing"], BURIAL_DEPTH)
            E_loss += th.heat_loss_buried(bp, Ts, Tr, T_GROUND_C, LAMBDA_PUR, LAMBDA_SOIL) * pe[e]["L3d"] * h / 1000.0
    pump_cost = E_pump * EURO.elec_price
    loss_cost = E_loss * EURO.heat_price
    total = c.capital + c.zones + pump_cost + loss_cost
    return dict(design=dict(pumping=c.pumping, heat=c.heat_loss, total=c.total, specific=c.specific_cost,
                            pump_MWh=c.pumping / EURO.elec_price / 1000, loss_MWh=c.heat_loss_MWh),
                seasonal=dict(pumping=pump_cost, heat=loss_cost, total=total,
                              specific=total / c.delivered_MWh, pump_MWh=E_pump / 1000, loss_MWh=E_loss / 1000),
                check_energy=float((q.sum()) / 8760 / m0))


def part_E():
    print("\n[E] seasonal part-load operation")
    out = {}
    for tag in STUDY:
        out[tag] = {}
        for q0 in (0.05, 0.10, 0.20):
            rr = {name: seasonal(tag, name, q0=q0) for name in ("Star", "MST-2D", "MST-terrain", "ESMT", "RSMT")}
            sv_d = 100 * (rr["MST-2D"]["design"]["total"] - rr["MST-terrain"]["design"]["total"]) / rr["MST-2D"]["design"]["total"]
            sv_s = 100 * (rr["MST-2D"]["seasonal"]["total"] - rr["MST-terrain"]["seasonal"]["total"]) / rr["MST-2D"]["seasonal"]["total"]
            out[tag][f"q0={q0}"] = dict(topos=rr, saving_design=sv_d, saving_seasonal=sv_s)
            print(f"  {tag} q0={q0}: terrain saving design {sv_d:+.2f}% -> seasonal {sv_s:+.2f}% | "
                  + "  ".join(f"{k} {v['design']['specific']:.2f}->{v['seasonal']['specific']:.2f}" for k, v in rr.items())
                  + f" | MST-t pump {rr['MST-terrain']['design']['pump_MWh']:.0f}->{rr['MST-terrain']['seasonal']['pump_MWh']:.0f} MWh"
                  f" loss {rr['MST-terrain']['design']['loss_MWh']:.0f}->{rr['MST-terrain']['seasonal']['loss_MWh']:.0f} MWh")
    OUT["E_seasonal"] = out


if __name__ == "__main__":
    parts = sys.argv[1:] or list("ABCDE")
    for p in parts:
        globals()[f"part_{p}"]()
        with open(f"results/tables/final_{p}.json", "w") as fh:
            json.dump(OUT, fh, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else float(o))
        OUT.clear()
    print("\nDone.")
