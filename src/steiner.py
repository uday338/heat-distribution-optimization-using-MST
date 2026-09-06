"""
steiner.py - Steiner minimal tree heuristics (the paper's ESMT and RSMT).

A spanning tree may only branch AT a user node. A Steiner tree is allowed to
introduce extra junction points anywhere in the plane, so pipes can meet at a
purpose-built manifold rather than being forced to route via a customer. That
is why a Steiner tree is never longer than the MST, and typically 3-12 %
shorter (the Steiner ratio bounds the Euclidean gain at 1 - sqrt(3)/2 = 13.4 %
in the worst case, Du & Hwang 1992).

Two metrics matter for pipe networks:

  ESMT (Euclidean)   - free routing. Steiner points have degree 3 with 120 deg
                       angles between branches (Torricelli/Fermat geometry).
  RSMT (Rectilinear) - routing constrained to a street grid, which is what a
                       real urban trench must follow. Optimal Steiner points
                       can be restricted to the Hanan grid: the intersections
                       of horizontal and vertical lines through the terminals
                       (Hanan 1966).

Algorithm
---------
Iterated 1-Steiner (Kahng & Robins, 1992, IEEE Trans. CAD 11(7), 893-902):
repeatedly add the single candidate point that most reduces the MST length,
until no candidate helps. It is simple, deterministic, and in practice lands
within about 0.5 % of the optimal Steiner tree - more than accurate enough
here, and far more transparent than calling a black-box GeoSteiner binary.

IMPORTANT CAVEAT, carried through to the reliability analysis: a Steiner tree
is still a TREE. Every edge is still a bridge, so a single pipe failure still
strands everything downstream. Steiner points reduce COST, not fault
tolerance. Fault tolerance requires cycles - see reliability.py. The two are
complementary, and combining them is the strongest design (see
augment_steiner_with_redundancy()).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np

from mst import complete_graph_edges, kruskal


# ---------------------------------------------------------------- metrics
def dist_matrix(xy: np.ndarray, metric: str = "euclidean") -> np.ndarray:
    d = xy[:, None, :] - xy[None, :, :]
    if metric == "rectilinear":
        return np.abs(d).sum(-1)
    return np.sqrt((d * d).sum(-1))


def mst_length(xy: np.ndarray, metric: str = "euclidean") -> float:
    W = dist_matrix(xy, metric)
    return kruskal(len(xy), list(complete_graph_edges(W))).weight


def mst_edges_of(xy: np.ndarray, metric: str = "euclidean"):
    W = dist_matrix(xy, metric)
    return kruskal(len(xy), list(complete_graph_edges(W))).edges, W


# ---------------------------------------------------------------- candidates
def fermat_point(a, b, c, iters: int = 64) -> np.ndarray:
    """Torricelli/Fermat point of a triangle: minimises the sum of distances.

    Solved by Weiszfeld iteration, which is the geometric-median algorithm and
    converges for any triangle. If one interior angle is >= 120 deg the optimum
    collapses onto that vertex, which Weiszfeld reproduces automatically.
    """
    pts = np.array([a, b, c], dtype=float)
    p = pts.mean(axis=0)
    for _ in range(iters):
        d = np.linalg.norm(pts - p, axis=1)
        if np.any(d < 1e-12):
            return pts[int(np.argmin(d))]
        w = 1.0 / d
        new = (pts * w[:, None]).sum(0) / w.sum()
        if np.linalg.norm(new - p) < 1e-10:
            return new
        p = new
    return p


def hanan_grid(xy: np.ndarray) -> np.ndarray:
    """All (x_i, y_j) intersections - provably contains an optimal RSMT."""
    xs = np.unique(xy[:, 0])
    ys = np.unique(xy[:, 1])
    gx, gy = np.meshgrid(xs, ys)
    return np.column_stack([gx.ravel(), gy.ravel()])


def _neighbour_triples(xy: np.ndarray, metric: str, k: int = 6):
    """Triples of mutually-near terminals - the only ones worth testing.

    Testing all C(n,3) triples is O(n^3) MST evaluations. A Steiner point is
    only ever useful between nodes that are already close, so we restrict to
    triples drawn from each node's k nearest neighbours. This keeps the
    heuristic near-identical in quality at a fraction of the cost.
    """
    W = dist_matrix(xy, metric)
    n = len(xy)
    k = min(k, n - 1)
    seen = set()
    for i in range(n):
        nb = np.argsort(W[i])[1 : k + 1]
        for a, b in itertools.combinations(nb, 2):
            t = tuple(sorted((i, int(a), int(b))))
            if t not in seen:
                seen.add(t)
                yield t


def candidate_points(xy: np.ndarray, metric: str, max_candidates: int = 4000):
    """Candidate Steiner points for the given metric."""
    if metric == "rectilinear":
        cand = hanan_grid(xy)
    else:
        cand = np.array([fermat_point(xy[i], xy[j], xy[k])
                         for i, j, k in _neighbour_triples(xy, metric)])
    if len(cand) == 0:
        return np.zeros((0, 2))
    # drop candidates coincident with an existing node
    W = np.sqrt(((cand[:, None, :] - xy[None, :, :]) ** 2).sum(-1))
    cand = cand[W.min(axis=1) > 1e-6]
    if len(cand) > max_candidates:
        idx = np.random.default_rng(0).choice(len(cand), max_candidates, replace=False)
        cand = cand[idx]
    return cand


# ---------------------------------------------------------------- main routine
@dataclass
class SteinerResult:
    xy: np.ndarray               # terminals followed by accepted Steiner points
    n_terminals: int
    steiner_points: np.ndarray
    edges: list
    length: float
    mst_length: float
    metric: str

    @property
    def gain_pct(self) -> float:
        """Percentage reduction against the spanning tree on the same nodes."""
        if self.mst_length <= 0:
            return 0.0
        return 100.0 * (self.mst_length - self.length) / self.mst_length


def iterated_1steiner(xy: np.ndarray, metric: str = "euclidean",
                      max_points: int | None = None, tol: float = 1e-9,
                      verbose: bool = False) -> SteinerResult:
    """Iterated 1-Steiner heuristic (Kahng & Robins 1992)."""
    terminals = np.asarray(xy, dtype=float)
    n_term = len(terminals)
    base = mst_length(terminals, metric)
    cur = terminals.copy()
    cur_len = base
    added: list[np.ndarray] = []
    if max_points is None:
        max_points = n_term - 2          # cannot exceed n-2 Steiner points

    while len(added) < max_points:
        cand = candidate_points(cur, metric)
        if len(cand) == 0:
            break
        best_gain, best_p = 0.0, None
        for p in cand:
            trial = np.vstack([cur, p])
            L = mst_length(trial, metric)
            gain = cur_len - L
            if gain > best_gain + tol:
                best_gain, best_p = gain, p
        if best_p is None:
            break
        cur = np.vstack([cur, best_p])
        cur_len -= best_gain
        added.append(best_p)
        if verbose:
            print(f"    +Steiner point {len(added)}: gain {best_gain:8.1f} m "
                  f"-> {cur_len:10.1f} m")

    # Prune Steiner points that ended up with degree <= 2 (they add nothing).
    edges, W = mst_edges_of(cur, metric)
    deg = np.zeros(len(cur), dtype=int)
    for u, v in edges:
        deg[u] += 1
        deg[v] += 1
    keep = [i for i in range(len(cur)) if i < n_term or deg[i] >= 3]
    if len(keep) < len(cur):
        cur = cur[keep]
        edges, W = mst_edges_of(cur, metric)
        cur_len = float(sum(W[u, v] for u, v in edges))

    return SteinerResult(
        xy=cur, n_terminals=n_term, steiner_points=cur[n_term:],
        edges=edges, length=cur_len, mst_length=base, metric=metric,
    )


def esmt(xy, **kw) -> SteinerResult:
    """Euclidean Steiner minimal tree (free routing)."""
    return iterated_1steiner(xy, metric="euclidean", **kw)


def rsmt(xy, **kw) -> SteinerResult:
    """Rectilinear Steiner minimal tree (street-grid routing)."""
    return iterated_1steiner(xy, metric="rectilinear", **kw)


# ---------------------------------------------------------------- demands
def extend_demands(demand, n_steiner: int) -> np.ndarray:
    """Steiner points are junction manifolds: they draw zero load.

    Their demand entry is 0, so the flow solver routes through them without
    any extraction - which is exactly what a physical tee does.
    """
    demand = np.asarray(demand, dtype=float)
    return np.concatenate([demand, np.zeros(n_steiner)])
