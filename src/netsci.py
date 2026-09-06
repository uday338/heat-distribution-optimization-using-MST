"""
netsci.py - The network-science core of the project.

Every metric here is a standard graph-theoretic quantity from the course
syllabus, and every one of them is used to answer a concrete pipe-network
engineering question. The mapping is the point of the project:

  GRAPH CONCEPT                     ENGINEERING QUESTION IT ANSWERS
  ------------------------------    ----------------------------------------
  adjacency / degree matrix         how many pipes meet at each manifold
  Laplacian spectrum, algebraic     how hard is the network to break apart -
    connectivity (Fiedler value)      a direct, continuous robustness measure
  edge connectivity, bridges        can ANY single pipe failure cut supply?
                                      (Menger: a tree has edge connectivity 1)
  spectral bisection                where should the pressure zones be split
                                      when terrain exceeds the PN rating?
  betweenness centrality            which pipe carries the most source-to-load
                                      paths, i.e. which one must not fail
  eigenvector centrality / PageRank  which junctions are structurally central
  degree distribution vs ER and     is the cost-optimal topology structurally
    configuration-model nulls         special, or just a random tree?
  clustering / transitivity          trees have zero triangles; redundancy
                                      introduces them, and that is measurable
  modularity, community detection    natural sub-network boundaries, which are
                                      candidate service or isolation districts
  percolation under random vs        does the network fail gracefully, or does
    targeted edge removal             attacking the trunk collapse it?

References
----------
  Fiedler M. (1973), Czechoslovak Math. J. 23, 298-305 - algebraic connectivity
  Newman M.E.J., Networks: An Introduction, OUP - the course text
  Clauset, Newman & Moore (2004) - greedy modularity communities
"""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import numpy as np


# ---------------------------------------------------------------- matrices
def adjacency(n: int, edges, W=None) -> np.ndarray:
    """Weighted adjacency matrix A."""
    A = np.zeros((n, n))
    for (u, v) in edges:
        w = float(W[u, v]) if W is not None else 1.0
        A[u, v] = A[v, u] = w
    return A


def laplacian(A: np.ndarray) -> np.ndarray:
    """Combinatorial Laplacian L = D - A."""
    return np.diag(A.sum(axis=1)) - A


def spectrum(n: int, edges, W=None, normalise: bool = True):
    """Laplacian eigenvalues and the Fiedler vector.

    For robustness comparisons the edge weight should be a CONDUCTANCE, not a
    length: a long pipe is a weak connection. We therefore use 1/length when
    weights are supplied, which is the physically meaningful choice and is
    what makes the Fiedler value comparable across topologies.
    """
    if W is not None and normalise:
        Wc = np.zeros_like(W, dtype=float)
        for (u, v) in edges:
            L = float(W[u, v])
            Wc[u, v] = Wc[v, u] = 1.0 / L if L > 0 else 0.0
        A = adjacency(n, edges, Wc)
    else:
        A = adjacency(n, edges, None)
    L = laplacian(A)
    vals, vecs = np.linalg.eigh(L)
    order = np.argsort(vals)
    vals = vals[order]
    vecs = vecs[:, order]
    return vals, vecs


def algebraic_connectivity(n: int, edges, W=None) -> float:
    """Fiedler value lambda_2: zero iff the graph is disconnected.

    The larger it is, the more edge-disjoint paths hold the network together.
    A spanning tree sits close to zero; every redundant pipe raises it. This
    gives a CONTINUOUS robustness measure to complement the binary
    'is there a bridge?' test.
    """
    vals, _ = spectrum(n, edges, W)
    return float(vals[1]) if len(vals) > 1 else 0.0


def fiedler_vector(n: int, edges, W=None) -> np.ndarray:
    _, vecs = spectrum(n, edges, W)
    return vecs[:, 1]


# ---------------------------------------------------------------- connectivity
def connectivity_report(n: int, edges) -> dict:
    """Edge connectivity, bridges, and cycle rank."""
    g = nx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from(edges)
    bridges = list(nx.bridges(g)) if nx.is_connected(g) else []
    return {
        "edge_connectivity": int(nx.edge_connectivity(g)) if nx.is_connected(g) else 0,
        "node_connectivity": int(nx.node_connectivity(g)) if nx.is_connected(g) else 0,
        "n_bridges": len(bridges),
        "bridge_fraction": len(bridges) / max(len(edges), 1),
        "cycle_rank": g.number_of_edges() - n + nx.number_connected_components(g),
        "is_2_edge_connected": nx.is_connected(g) and len(bridges) == 0,
    }


# ---------------------------------------------------------------- centrality
def centralities(n: int, edges, W=None) -> dict:
    g = nx.Graph()
    g.add_nodes_from(range(n))
    for (u, v) in edges:
        g.add_edge(u, v, length=float(W[u, v]) if W is not None else 1.0)
    deg = dict(g.degree())
    btw = nx.betweenness_centrality(g, weight="length")
    clo = nx.closeness_centrality(g, distance="length")
    try:
        eig = nx.eigenvector_centrality_numpy(g)
    except Exception:
        eig = {i: float("nan") for i in range(n)}
    pr = nx.pagerank(g, weight=None)
    return {"degree": deg, "betweenness": btw, "closeness": clo,
            "eigenvector": eig, "pagerank": pr}


# ---------------------------------------------------------------- null models
def null_model_comparison(n: int, edges, trials: int = 200, seed: int = 0) -> dict:
    """Is this topology structurally special, or just a random tree?

    Compares the observed degree sequence and path lengths against:
      * Erdos-Renyi G(n, m) with the same number of edges
      * a uniformly random labelled spanning tree (Cayley's formula sample)
    A cost-optimal geometric tree should be far less degree-heterogeneous
    than a random tree, because geometry forbids long-range edges.
    """
    rng = np.random.default_rng(seed)
    g = nx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from(edges)
    deg = np.array([d for _, d in g.degree()], dtype=float)
    obs = {"mean_degree": deg.mean(), "max_degree": deg.max(), "var_degree": deg.var()}

    er_max, rt_max, rt_var = [], [], []
    m = len(edges)
    for _ in range(trials):
        try:
            ger = nx.gnm_random_graph(n, m, seed=int(rng.integers(1 << 30)))
            d = np.array([x for _, x in ger.degree()], dtype=float)
            er_max.append(d.max())
        except Exception:
            pass
        grt = nx.random_labeled_tree(n, seed=int(rng.integers(1 << 30))) \
            if hasattr(nx, "random_labeled_tree") else nx.random_tree(n, seed=int(rng.integers(1 << 30)))
        d = np.array([x for _, x in grt.degree()], dtype=float)
        rt_max.append(d.max())
        rt_var.append(d.var())

    return {
        "observed": obs,
        "er_max_degree_mean": float(np.mean(er_max)) if er_max else float("nan"),
        "random_tree_max_degree_mean": float(np.mean(rt_max)),
        "random_tree_var_degree_mean": float(np.mean(rt_var)),
        "degree_var_ratio_vs_random_tree": float(obs["var_degree"] / np.mean(rt_var))
        if np.mean(rt_var) > 0 else float("nan"),
    }


def structural_summary(n: int, edges, W=None) -> dict:
    g = nx.Graph()
    g.add_nodes_from(range(n))
    for (u, v) in edges:
        g.add_edge(u, v, length=float(W[u, v]) if W is not None else 1.0)
    out = {
        "transitivity": float(nx.transitivity(g)),
        "avg_clustering": float(nx.average_clustering(g)),
        "algebraic_connectivity": algebraic_connectivity(n, edges, W),
    }
    try:
        out["assortativity"] = float(nx.degree_assortativity_coefficient(g))
    except Exception:
        out["assortativity"] = float("nan")
    try:
        comms = list(nx.community.greedy_modularity_communities(g))
        out["n_communities"] = len(comms)
        out["modularity"] = float(nx.community.modularity(g, comms))
    except Exception:
        out["n_communities"] = -1
        out["modularity"] = float("nan")
    return out


# ---------------------------------------------------------------- spectral zones
def spectral_pressure_zones(n: int, edges, z, rho: float, g_acc: float,
                            PN: float, p_top: float, max_zones: int = 8):
    """Partition the network into hydraulic pressure zones by spectral bisection.

    This is the course's spectral bisection algorithm doing real engineering
    work. On hilly ground a single zone cannot satisfy

        p_sat + margin  <=  p(z)  <=  PN

    everywhere, because the static spread rho*g*(z_max - z_min) exceeds the
    usable pressure band. The network must be split, each zone served through
    a heat exchanger that breaks the static column.

    Splitting arbitrarily is bad: a zone boundary should cut FEW pipes (each
    cut needs an exchanger station) while separating nodes of different
    elevation. That is exactly a balanced minimum-cut problem, and the Fiedler
    vector of the Laplacian is the classical relaxation of it. We recursively
    bisect any zone whose internal relief still violates the pressure band.

    Returns (labels, n_zones, n_cut_edges).
    """
    z = np.asarray(z, dtype=float)
    usable = PN - p_top
    if usable <= 0:
        return np.zeros(n, dtype=int), max_zones, 0

    def relief_ok(idx):
        return rho * g_acc * (z[idx].max() - z[idx].min()) <= usable

    labels = np.zeros(n, dtype=int)
    active = [np.arange(n)]
    next_label = 1
    while active and next_label < max_zones:
        idx = active.pop(0)
        if len(idx) <= 2 or relief_ok(idx):
            continue
        sub_edges = [(u, v) for (u, v) in edges if u in set(idx) and v in set(idx)]
        remap = {int(k): i for i, k in enumerate(idx)}
        se = [(remap[u], remap[v]) for (u, v) in sub_edges]
        if len(se) == 0:
            continue
        try:
            fv = fiedler_vector(len(idx), se, None)
        except Exception:
            break
        # bisect on the median of the Fiedler vector for a balanced cut
        mask = fv > np.median(fv)
        if mask.all() or (~mask).all():
            break
        part_a, part_b = idx[~mask], idx[mask]
        labels[part_b] = next_label
        next_label += 1
        active.extend([part_a, part_b])

    cut = sum(1 for (u, v) in edges if labels[u] != labels[v])
    return labels, int(labels.max() + 1), cut


# ---------------------------------------------------------------- percolation
def percolation(n: int, edges, demand, mode: str = "random",
                trials: int = 60, seed: int = 0, root: int = 0):
    """Served-demand curve as pipes are progressively removed.

    mode = "random"   independent random failures (ageing, third-party damage)
           "targeted" remove highest-edge-betweenness pipes first (worst case:
                      an attacker, or simply the pipes that matter most)

    Returns (fraction_removed, mean_served_fraction).
    """
    from reliability import stranded_demand  # local import avoids a cycle

    demand = np.asarray(demand, dtype=float)
    load = np.where(demand > 0, demand, 0.0)
    total = load.sum()
    m = len(edges)
    rng = np.random.default_rng(seed)
    ks = np.arange(0, m)
    served = np.zeros(len(ks))

    if mode == "targeted":
        g = nx.Graph()
        g.add_nodes_from(range(n))
        g.add_edges_from(edges)
        eb = nx.edge_betweenness_centrality(g)
        rank = sorted(range(m),
                      key=lambda j: -eb.get(edges[j], eb.get(edges[j][::-1], 0.0)))
        orders = [rank]
    else:
        orders = [list(rng.permutation(m)) for _ in range(trials)]

    for order in orders:
        removed = set()
        for ki, k in enumerate(ks):
            if k > 0:
                removed.add(order[k - 1])
            adj = [[] for _ in range(n)]
            for j, (u, v) in enumerate(edges):
                if j in removed:
                    continue
                adj[u].append(v)
                adj[v].append(u)
            seen = np.zeros(n, dtype=bool)
            stack = [root]
            seen[root] = True
            while stack:
                x = stack.pop()
                for y in adj[x]:
                    if not seen[y]:
                        seen[y] = True
                        stack.append(y)
            served[ki] += load[seen].sum() / max(total, 1e-9)
    served /= len(orders)
    return ks / m, served
