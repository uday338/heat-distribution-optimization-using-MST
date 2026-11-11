"""F. Flow-aware edge-swap local search: minimise TAC directly, starting from an MST."""
import json, sys, time, pickle
import numpy as np
from multiprocessing import Pool
import run_final as R
from run_final import *

def prep(tag, n_users=40, seed=42):
    d = DISTRICTS[STUDY[tag]]
    dem = build_dem(d.cells, cache=f"data/dem/{STUDY[tag]}.pkl")
    nodes = build_nodes(d, n_users=n_users, full_load_hours=EURO.full_load_hours, seed=seed)
    xy, demand = nodes.xy, nodes.demand_kW
    n = len(xy); z = node_elevations(dem, xy)
    M = TerrainCost(dem, ds=25.0).matrices(xy)
    zlo = np.zeros((n, n)); zhi = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            zz = dem.profile(xy[i], xy[j], ds=25.0)[1]
            zlo[i, j] = zlo[j, i] = zz.min(); zhi[i, j] = zhi[j, i] = zz.max()
    return dict(xy=xy, demand=demand, n=n, z=z, M=M, zlo=zlo, zhi=zhi, dem=dem)

ECON = EURO
def tac(S, edges):
    zr = np.array([S["zlo"][u, v] for u, v in edges] + [S["zhi"][u, v] for u, v in edges])
    return euro_tac(S["n"], edges, S["M"], S["demand"], S["z"], p=ECON, z_route=zr)

def local_search(S, edges, knn=8, max_sweeps=30):
    n = S["n"]; W = S["M"]["W"]
    edges = [tuple(e) for e in edges]
    cur = tac(S, edges).total
    cands = set()
    for u in range(n):
        for v in np.argsort(W[u])[1:knn + 1]:
            if np.isfinite(W[u, v]): cands.add((min(u, int(v)), max(u, int(v))))
    cands = sorted(cands)
    n_eval = swaps = 0
    for sweep in range(max_sweeps):
        improved = False
        for (u, v) in cands:
            tset = {tuple(sorted(e)) for e in edges}
            if (u, v) in tset: continue
            parent, order = root_tree(n, edges, 0)
            depth = {0: 0}
            for x in order:
                if parent[x] >= 0: depth[x] = depth[parent[x]] + 1
            a, b, path = u, v, []
            while a != b:
                if depth[a] < depth[b]: a, b = b, a
                path.append(tuple(sorted((a, parent[a])))); a = parent[a]
            best = None
            for rem in path:
                trial = [e for e in edges if tuple(sorted(e)) != rem] + [(u, v)]
                c = tac(S, trial).total; n_eval += 1
                if c < cur - 1e-6 and (best is None or c < best[0]): best = (c, trial)
            if best:
                cur, edges = best; improved = True; swaps += 1
        if not improved: break
    return edges, cur, dict(n_eval=n_eval, swaps=swaps, sweeps=sweep + 1)

def summarise(S, edges):
    c = tac(S, edges)
    r = rel.evaluate(S["n"], edges, S["demand"], einfo(c, edges))
    return dict(specific=c.specific_cost, total=c.total, capital=c.capital, pumping=c.pumping, heat=c.heat_loss,
                L3d_km=c.length_3d / 1000, zones=c.n_zones, n1=r.n1_served_fraction, eud=r.eud_MWh,
                pump_bar=c.pump_head_bar, edges=[list(map(int, e)) for e in edges])

def job(args):
    tag, n_users, seed = args
    S = prep(tag, n_users, seed)
    n = S["n"]
    e2 = kruskal(n, list(complete_graph_edges(euclidean_weights(S["xy"])))).edges
    et = kruskal(n, list(complete_graph_edges(S["M"]["W"]))).edges
    t0 = time.time()
    ls_t, _, st_t = local_search(S, et)
    ls_2, _, st_2 = local_search(S, e2)
    out = dict(tag=tag, n=n_users, seed=seed, mst2d=summarise(S, e2), mstt=summarise(S, et),
               ls_from_t=summarise(S, ls_t), ls_from_2d=summarise(S, ls_2), stats_t=st_t, stats_2d=st_2,
               secs=time.time() - t0)
    a = out
    print(f"  {tag} n={n_users} seed={seed}: MST-2D {a['mst2d']['specific']:.2f}  MST-terrain {a['mstt']['specific']:.2f}  "
          f"LS(from terrain) {a['ls_from_t']['specific']:.2f} [{st_t['swaps']} swaps, {a['ls_from_t']['L3d_km']:.2f} km vs {a['mstt']['L3d_km']:.2f}]  "
          f"LS(from 2D) {a['ls_from_2d']['specific']:.2f}  ({out['secs']:.0f}s)", flush=True)
    return out

if __name__ == "__main__":
    import dataclasses
    if len(sys.argv) > 1 and sys.argv[1] == "seasonal":
        ECON = dataclasses.replace(EURO, op_hours=5000 * 0.116, heat_price=EURO.heat_price * 0.816)
    jobs = [(t, 40, s) for t in ("hilly", "flat") for s in (42, 0, 1, 2, 3, 4, 5, 6, 7, 8)]
    with Pool(4) as p:
        res = p.map(job, jobs, chunksize=1)
    json.dump(res, open("results/tables/final_F%s.json" % ("_seasonal" if ECON is not EURO else ""), "w"), indent=1, default=float)
