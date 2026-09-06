"""
benchmark.py - Kruskal vs Prim on the same networks, and scaling behaviour.

Both algorithms return a tree of identical total weight (the MST weight is
unique when edge weights are distinct), so the interesting question is cost,
not correctness. On the complete graphs used for pipe-network design,
E = V(V-1)/2, so:

    Kruskal  O(E log E) = O(V^2 log V)   - dominated by sorting all V^2/2 edges
    Prim     O(E log V) = O(V^2 log V)   - same order, but with a much smaller
                                           constant, because it never sorts the
                                           full edge list

Kruskal has one saving grace we measure explicitly: it can stop as soon as
V-1 edges are accepted, so it often examines only a small fraction of the
sorted list. We report that fraction.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from mst import (
    adjacency_from_matrix,
    prim_dense,
    complete_graph_edges,
    euclidean_weights,
    kruskal,
    prim,
)


@dataclass
class BenchRow:
    n: int
    n_edges: int
    kruskal_s: float
    prim_s: float
    prim_dense_s: float
    networkx_s: float
    weight: float
    kruskal_examined: int
    kruskal_rejected: int
    speedup: float


def benchmark(sizes=(25, 50, 100, 200, 400, 800, 1600), repeats: int = 3,
              seed: int = 0, with_networkx: bool = True,
              verbose: bool = True) -> list[BenchRow]:
    rng = np.random.default_rng(seed)
    rows = []
    for n in sizes:
        xy = rng.random((n, 2)) * 5000.0
        W = euclidean_weights(xy)

        tk = tp = td = tn = np.inf
        for _ in range(repeats):
            edges = list(complete_graph_edges(W))     # built outside the timer
            t0 = time.perf_counter()
            rk = kruskal(n, edges)
            tk = min(tk, time.perf_counter() - t0)

            adj = adjacency_from_matrix(W)
            t0 = time.perf_counter()
            rp = prim(n, adj)
            tp = min(tp, time.perf_counter() - t0)

            t0 = time.perf_counter()
            rd = prim_dense(W)
            td = min(td, time.perf_counter() - t0)

        if with_networkx and n <= 800:
            import networkx as nx
            g = nx.Graph()
            for u, v, w in complete_graph_edges(W):
                g.add_edge(u, v, weight=w)
            t0 = time.perf_counter()
            nx.minimum_spanning_tree(g, algorithm="kruskal")
            tn = time.perf_counter() - t0
        else:
            tn = float("nan")

        assert abs(rk.weight - rp.weight) < 1e-6, "Kruskal and Prim disagree"
        assert abs(rk.weight - rd.weight) < 1e-6, "dense Prim disagrees"
        rows.append(BenchRow(
            n=n, n_edges=n * (n - 1) // 2, kruskal_s=tk, prim_s=tp,
            prim_dense_s=td,
            networkx_s=tn, weight=rk.weight,
            kruskal_examined=rk.n_considered, kruskal_rejected=rk.n_rejected,
            speedup=tk / tp if tp > 0 else float("nan"),
        ))
        if verbose:
            r = rows[-1]
            print(f"  n={n:5d} E={r.n_edges:8d} | Kruskal {tk*1000:8.2f} ms | "
                  f"Prim-heap {tp*1000:9.2f} ms | Prim-dense {td*1000:8.2f} ms | "
                  f"Kruskal examined {100*r.kruskal_examined/r.n_edges:5.1f}% of edges")
    return rows


def fit_scaling(rows) -> dict:
    """Empirical exponent alpha in t ~ V^alpha, by log-log regression."""
    n = np.array([r.n for r in rows], dtype=float)
    out = {}
    for name, t in [("kruskal", [r.kruskal_s for r in rows]),
                    ("prim", [r.prim_s for r in rows]),
                    ("prim_dense", [r.prim_dense_s for r in rows])]:
        t = np.array(t, dtype=float)
        m = t > 0
        a, b = np.polyfit(np.log(n[m]), np.log(t[m]), 1)
        out[name] = float(a)
    return out
