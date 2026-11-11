"""G. Work added on 11 Nov: exact ILP for redundancy (k up to 8), relief sweep,
edge-swap at larger sizes, combined design, and which graph metric predicts cost."""
import json, sys, time, copy, dataclasses
import numpy as np
from multiprocessing import Pool
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix, csr_matrix, hstack, eye
import run_final as R
import run_final_F as F
from run_final import *

SEAS = dataclasses.replace(EURO, op_hours=5000 * 0.116, heat_price=EURO.heat_price * 0.816)
OUTD = "results/tables/"

# ---------------------------------------------------------------- shared: coverage model on a tree
def coverage_model(n, edges, M, demand, base_cost, einfo_, econ=EURO):
    r0 = rel.evaluate(n, edges, demand, einfo_)
    w = np.array([r0.per_edge[e]["eud_MWh"] for e in edges])
    pipe = hyd.select_pipe(hyd.mdot_from_load(r0.worst_case_kW, WATER.T_supply_C - WATER.T_return_C, WATER.cp), WATER.rho, WATER.mu)
    unit = (econ.C1 + econ.C2 * pipe.d_casing) * econ.crf
    pm = R.tree_paths(n, edges)
    tset = {tuple(sorted(e)) for e in edges}
    cands = [(u, v) for u in range(n) for v in range(u + 1, n) if np.isfinite(M["W"][u, v]) and (u, v) not in tset]
    masks = [pm(u, v) for u, v in cands]
    cost = np.array([unit * M["W"][u, v] for u, v in cands]) / base_cost * 100.0
    A = lil_matrix((len(edges), len(cands)))
    for c, mk in enumerate(masks):
        for e in range(len(edges)):
            if (mk >> e) & 1: A[e, c] = 1
    return dict(w=w, cands=cands, masks=masks, cost=cost, A=csr_matrix(A), r0=r0)

def cov(Mo, sel):
    mk = 0
    for i in sel: mk |= Mo["masks"][i]
    return sum(Mo["w"][e] for e in range(len(Mo["w"])) if (mk >> e) & 1)

def greedy_ratio(Mo, K):
    sel = []
    for _ in range(K):
        cur = cov(Mo, sel)
        best = max((i for i in range(len(Mo["cands"])) if i not in sel), key=lambda i: (cov(Mo, sel + [i]) - cur) / Mo["cost"][i])
        sel.append(best)
    return sel

def greedy_gain(Mo, K):
    sel = []
    for _ in range(K):
        best = max((i for i in range(len(Mo["cands"])) if i not in sel), key=lambda i: (cov(Mo, sel + [i]), -Mo["cost"][i]))
        sel.append(best)
    return sel

def ilp(Mo, k, budget=None):
    """max sum_e w_e y_e  s.t.  y_e <= sum_{c covers e} x_c ,  sum x <= k , [cost.x <= budget] , x,y binary"""
    E, Cn = Mo["A"].shape
    c = np.r_[np.zeros(Cn), -Mo["w"]]
    A1 = hstack([-Mo["A"], eye(E)]).tocsr()
    cons = [LinearConstraint(A1, -np.inf, 0), LinearConstraint(np.r_[np.ones(Cn), np.zeros(E)][None, :], 0, k)]
    if budget is not None:
        cons.append(LinearConstraint(np.r_[Mo["cost"], np.zeros(E)][None, :], 0, budget + 1e-9))
    t0 = time.time()
    r = milp(c, constraints=cons, integrality=np.ones(Cn + E), bounds=Bounds(0, 1), options=dict(mip_rel_gap=0))
    sel = [i for i in range(Cn) if r.x[i] > 0.5]
    return -r.fun, sel, time.time() - t0

def part_ilp():
    print("\n[G1] exact ILP for redundancy")
    out = {}
    C = json.load(open(OUTD + "final_C.json"))["C_exact"]
    for tag in STUDY:
        P = R.load(tag); xy, z, demand, M, dem = P["xy"], P["z"], P["demand"], P["M"], P["dem"]
        n = len(xy); edges = list(P["topo"]["MST-terrain"][0])
        base = euro_tac(n, edges, M, demand, z, z_route=R.route_z(dem, xy, edges))
        Mo = coverage_model(n, edges, M, demand, base.total, R.einfo(base, edges))
        eud0 = Mo["w"].sum(); rows = []
        gr = greedy_ratio(Mo, 8); gg = greedy_gain(Mo, 8)
        for k in range(1, 9):
            g_cov = cov(Mo, gr[:k]); g_cost = Mo["cost"][gr[:k]].sum()
            o_card, s_card, t1 = ilp(Mo, k)
            o_bud, s_bud, t2 = ilp(Mo, k, budget=g_cost)
            row = dict(k=k, greedy_red=100 * g_cov / eud0, greedy_cost=float(g_cost),
                       ilp_same_budget=100 * o_bud / eud0, ilp_max=100 * o_card / eud0,
                       ilp_max_cost=float(Mo["cost"][s_card].sum()), greedy_gain_red=100 * cov(Mo, gg[:k]) / eud0,
                       secs=t1 + t2, bridges_left_greedy=int(sum(1 for e in range(len(edges)) if not any((Mo["masks"][i] >> e) & 1 for i in gr[:k]))))
            if k <= 3:
                row["bruteforce_max"] = C[tag]["exact"][str(k)]["max_eud_red"]
                row["bruteforce_same_budget"] = C[tag]["exact"][str(k)]["best_within_greedy_budget"]
            rows.append(row)
            print(f"  {tag} k={k}: greedy -{row['greedy_red']:.1f}% (+{g_cost:.1f}%) | ILP same budget -{row['ilp_same_budget']:.1f}% | ILP max -{row['ilp_max']:.1f}% "
                  f"| pure-gain greedy -{row['greedy_gain_red']:.1f}% | bridges left {row['bridges_left_greedy']} | brute {row.get('bruteforce_same_budget','-')} {row.get('bruteforce_max','-')} ({row['secs']:.1f}s)")
        out[tag] = dict(rows=rows, n_vars=int(sum(Mo["A"].shape)), n_cands=len(Mo["cands"]))
    json.dump(out, open(OUTD + "final_G_ilp.json", "w"), indent=1, default=float)

# ---------------------------------------------------------------- G2 relief sweep
def relief_job(args):
    f, seed = args
    d = DISTRICTS[STUDY["hilly"]]
    dem = build_dem(d.cells, cache=f"data/dem/{STUDY['hilly']}.pkl")
    dem = copy.deepcopy(dem); zm = float(np.nanmean(dem.grid)); dem.grid = zm + f * (dem.grid - zm)
    r = R.one_network(d, dem, 40, seed, econ=SEAS)
    return dict(f=f, seed=seed, route_relief=r["route_relief_t"], zones=r["zones_t"], saving=r["saving_pct"],
                n_diff=r["n_diff"], cost=r["specific_t"], d_trench=r["d_trench_pct"])

def part_relief():
    print("\n[G2] relief sweep on Stuttgart terrain")
    fs = [0.0, 0.25, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.0, 1.25, 1.5]
    with Pool(4) as p: rows = p.map(relief_job, [(f, s) for f in fs for s in (42, 0, 1, 2, 3, 4, 5, 6, 7, 8)])
    for f in fs:
        rr = [r for r in rows if r["f"] == f]
        print(f"  x{f:4.2f}: route relief {np.mean([r['route_relief'] for r in rr]):5.0f} m [{min(r['route_relief'] for r in rr):.0f},{max(r['route_relief'] for r in rr):.0f}]"
              f"  zones {sorted(set(r['zones'] for r in rr))} (2+ in {sum(r['zones']>=2 for r in rr)}/10)  saving mean {np.mean([r['saving'] for r in rr]):+.2f}% median {np.median([r['saving'] for r in rr]):+.2f}%"
              f"  edges changed {np.mean([r['n_diff'] for r in rr]):.1f}  trench {np.mean([r['d_trench'] for r in rr]):+.2f}%")
    json.dump(rows, open(OUTD + "final_G_relief.json", "w"), indent=1, default=float)

# ---------------------------------------------------------------- G4 edge swap at larger sizes
def part_scale(sizes=(80,), seeds=(42, 0, 1, 2, 3)):
    print("\n[G4] edge swap at larger sizes", sizes)
    F.ECON = SEAS
    with Pool(4) as p: res = p.map(F.job, [(t, n, s) for n in sizes for t in ("hilly", "flat") for s in seeds], chunksize=1)
    json.dump(res, open(OUTD + f"final_G_scale_{'_'.join(map(str,sizes))}.json", "w"), indent=1, default=float)
    for n in sizes:
        for t in ("hilly", "flat"):
            rr = [r for r in res if r["tag"] == t and r["n"] == n]
            sv = [100 * (1 - r["ls_from_t"]["specific"] / r["mstt"]["specific"]) for r in rr]
            dl = [100 * (r["ls_from_t"]["L3d_km"] / r["mstt"]["L3d_km"] - 1) for r in rr]
            print(f"  {t} n={n}: saving mean {np.mean(sv):.1f}% [{min(sv):.1f},{max(sv):.1f}]  extra length {np.mean(dl):.1f}%  secs {np.mean([r['secs'] for r in rr]):.0f}")

# ---------------------------------------------------------------- G5 combined design + G3 metrics
def tree_metrics(S, edges):
    n = S["n"]; parent, order = root_tree(n, edges, 0)
    L = S["M"]["L3d"] if "L3d" in S["M"] else None
    depth = np.zeros(n); dist = np.zeros(n)
    for v in order:
        if parent[v] >= 0:
            depth[v] = depth[parent[v]] + 1
            dist[v] = dist[parent[v]] + np.hypot(*(S["xy"][v] - S["xy"][parent[v]]))
    d = S["demand"]; ok = d > 0
    return dict(mean_hops=float((depth[ok] * d[ok]).sum() / d[ok].sum()), max_hops=int(depth.max()),
                wdist_km=float((dist[ok] * d[ok]).sum() / d[ok].sum() / 1000), leaves=int(sum(1 for v in range(1, n) if not any(parent[u] == v for u in range(n)))))

def design_job(args):
    tag, seed = args
    F.ECON = SEAS
    S = F.prep(tag, 40, seed); n = S["n"]
    FS = json.load(open(OUTD + "final_F_seasonal.json"))
    r = [x for x in FS if x["tag"] == tag and x["seed"] == seed][0]
    out = dict(tag=tag, seed=seed, designs={}, metrics={})
    for name, key in (("MST map", "mst2d"), ("MST terrain", "mstt"), ("Edge swap", "ls_from_t")):
        edges = [tuple(e) for e in r[key]["edges"]]
        c = F.tac(S, edges); rr = rel.evaluate(n, edges, S["demand"], R.einfo(c, edges))
        out["metrics"][name] = dict(cost=c.specific_cost, L_km=c.length_3d / 1000, **tree_metrics(S, edges))
        if name == "MST map": continue
        out["designs"][name] = dict(cost=c.specific_cost, eud=rr.eud_MWh, n1=rr.n1_served_fraction, bridges=rr.n_bridges)
        Mo = coverage_model(n, edges, S["M"], S["demand"], c.total, R.einfo(c, edges), econ=SEAS)
        sel = greedy_ratio(Mo, 2)
        for k in (1, 2):
            ek = edges + [Mo["cands"][i] for i in sel[:k]]
            ck = F.tac(S, ek); rk = rel.evaluate(n, ek, S["demand"], R.einfo(ck, ek))
            out["designs"][f"{name} + {k} loop"] = dict(cost=ck.specific_cost, eud=rk.eud_MWh, n1=rk.n1_served_fraction, bridges=rk.n_bridges,
                                                       added=[list(map(int, Mo["cands"][i])) for i in sel[:k]])
    return out

def part_design():
    print("\n[G5] combined design and graph metrics")
    with Pool(4) as p: res = p.map(design_job, [(t, s) for t in ("hilly", "flat") for s in (42, 0, 1, 2, 3, 4, 5, 6, 7, 8)], chunksize=1)
    json.dump(res, open(OUTD + "final_G_design.json", "w"), indent=1, default=float)
    for t in ("hilly", "flat"):
        rr = [r for r in res if r["tag"] == t]
        print(" ", t, "seed 42:")
        for k, v in rr[0]["designs"].items(): print(f"     {k:22s} cost {v['cost']:.2f}  EUD {v['eud']:.0f}  N-1 served {100*v['n1']:.0f}%  bridges {v['bridges']}")
        for k in rr[0]["designs"]:
            print(f"     mean of 10  {k:22s} cost {np.mean([r['designs'][k]['cost'] for r in rr]):.2f}  EUD {np.mean([r['designs'][k]['eud'] for r in rr]):.0f}  N-1 {100*np.mean([r['designs'][k]['n1'] for r in rr]):.0f}%")
        X = [(m["cost"], m["L_km"], m["wdist_km"], m["mean_hops"], m["max_hops"]) for r in rr for m in r["metrics"].values()]
        X = np.array(X)
        for j, nm in ((1, "total length"), (2, "demand-weighted distance to plant"), (3, "demand-weighted hops"), (4, "max hops")):
            print(f"     corr(cost, {nm}) = {np.corrcoef(X[:,0], X[:,j])[0,1]:+.2f}   (30 trees)")
        A = np.c_[np.ones(len(X)), X[:, 1], X[:, 2]]; beta, *_ = np.linalg.lstsq(A, X[:, 0], rcond=None)
        pred = A @ beta; r2 = 1 - ((X[:, 0] - pred) ** 2).sum() / ((X[:, 0] - X[:, 0].mean()) ** 2).sum()
        A1 = A[:, :2]; b1, *_ = np.linalg.lstsq(A1, X[:, 0], rcond=None); r2a = 1 - ((X[:, 0] - A1 @ b1) ** 2).sum() / ((X[:, 0] - X[:, 0].mean()) ** 2).sum()
        print(f"     R2 length only {r2a:.2f} ; length + weighted distance {r2:.2f}")
        for nm in ("MST terrain", "Edge swap"):
            print(f"     {nm}: mean hops {np.mean([r['metrics'][nm]['mean_hops'] for r in rr]):.1f} max hops {np.mean([r['metrics'][nm]['max_hops'] for r in rr]):.1f} wdist {np.mean([r['metrics'][nm]['wdist_km'] for r in rr]):.2f} km leaves {np.mean([r['metrics'][nm]['leaves'] for r in rr]):.1f}")

if __name__ == "__main__":
    for a in sys.argv[1:]:
        if a.startswith("scale"): part_scale(tuple(int(x) for x in a.split(":")[1].split(",")), tuple(int(x) for x in a.split(":")[2].split(",")))
        else: globals()["part_" + a]()
