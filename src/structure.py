"""
structure.py - Structural / topological characterisation of a pipe network.

These are the network-science metrics that distinguish a cost-optimal
topology from a naive one, and they have direct engineering meaning:

  degree distribution     how many pipes meet at a node; a degree-1 node is a
                          dead end, a high-degree node is a manifold that needs
                          a physical junction chamber
  hub / max degree        the busiest junction - a single point of failure and
                          the most expensive civil structure
  network diameter        longest shortest-path, in hops and in metres; sets
                          the worst-case transport delay and temperature drop
  betweenness centrality  fraction of source-to-consumer paths crossing a node
                          or edge; on a tree the trunk edges carry everything,
                          which is exactly why tree networks are fragile
  characteristic length   mean plant-to-consumer distance, which drives both
                          pumping head and heat loss per unit delivered
"""
from __future__ import annotations

import numpy as np


def to_networkx(n: int, edges, W=None):
    import networkx as nx

    g = nx.Graph()
    g.add_nodes_from(range(n))
    for (u, v) in edges:
        w = float(W[u, v]) if W is not None else 1.0
        g.add_edge(u, v, weight=w, length=w)
    return g


def analyse(n: int, edges, W=None, demand=None, root: int = 0) -> dict:
    """Structural metrics of one topology. Returns a flat dict of scalars."""
    import networkx as nx

    g = to_networkx(n, edges, W)
    deg = np.array([d for _, d in g.degree()])

    # --- degree structure
    out = {
        "mean_degree": float(deg.mean()),
        "max_degree": int(deg.max()),
        "hub_node": int(np.argmax(deg)),
        "n_leaves": int((deg == 1).sum()),
        "n_junctions": int((deg >= 3).sum()),
        "leaf_fraction": float((deg == 1).sum() / n),
    }

    # --- distances (hop count and physical metres)
    try:
        out["diameter_hops"] = int(nx.diameter(g))
    except Exception:
        out["diameter_hops"] = -1
    if W is not None:
        try:
            lengths = dict(nx.all_pairs_dijkstra_path_length(g, weight="length"))
            allv = [v for d in lengths.values() for v in d.values()]
            out["diameter_m"] = float(max(allv))
            out["mean_path_m"] = float(np.mean(allv))
            out["mean_plant_dist_m"] = float(
                np.mean([lengths[root][j] for j in range(n) if j != root])
            )
            out["max_plant_dist_m"] = float(
                max(lengths[root][j] for j in range(n) if j != root)
            )
        except Exception:
            pass

    # --- centrality
    bt = nx.betweenness_centrality(g, weight="length")
    out["max_betweenness"] = float(max(bt.values()))
    out["mean_betweenness"] = float(np.mean(list(bt.values())))
    eb = nx.edge_betweenness_centrality(g, weight="length")
    out["max_edge_betweenness"] = float(max(eb.values())) if eb else 0.0

    # --- how tree-like / how redundant
    out["n_independent_cycles"] = int(g.number_of_edges() - n + nx.number_connected_components(g))
    try:
        out["assortativity"] = float(nx.degree_assortativity_coefficient(g))
    except Exception:
        out["assortativity"] = float("nan")

    # --- demand-weighted load concentration on the trunk
    if demand is not None and W is not None:
        dem = np.asarray(demand, dtype=float)
        load = np.where(dem > 0, dem, 0.0)
        tot = load.sum()
        if tot > 0:
            try:
                lengths = dict(nx.single_source_dijkstra_path_length(g, root, weight="length"))
                out["demand_weighted_dist_m"] = float(
                    sum(load[j] * lengths.get(j, 0.0) for j in range(n)) / tot
                )
            except Exception:
                pass
    return out


def degree_histogram(n: int, edges) -> dict[int, int]:
    deg = np.zeros(n, dtype=int)
    for u, v in edges:
        deg[u] += 1
        deg[v] += 1
    vals, counts = np.unique(deg, return_counts=True)
    return {int(k): int(c) for k, c in zip(vals, counts)}
