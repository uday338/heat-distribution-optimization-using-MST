"""
reliability.py - Fault tolerance of a pipe network, and how to buy it.

The problem, stated precisely
-----------------------------
Every edge of a TREE is a bridge. Cutting any one edge splits the graph, and
every consumer on the far side from the plant loses supply completely. This is
true of the MST, and equally true of the Steiner trees - adding Steiner points
makes the network cheaper, not more robust. It is the structural price of
minimum length, and it is the limitation Gao et al. explicitly leave open:

    "However, reliability of pipe network is not quantified. Therefore, it is
     not guaranteed that the network topology is the best. In future, this
     work will further extend to consider reliability."

Metrics implemented
-------------------
  N-1 worst case        largest demand lost to any single pipe failure [kW]
  EUD                   Expected Unserved Demand [MWh/y], the probabilistic
                        metric: sum over edges of (failure rate) x (repair
                        time) x (demand stranded). This is the right metric
                        because it weights a failure by how likely that
                        specific pipe is to fail, which depends on its length,
                        its diameter, and - through the mass transfer model -
                        how fast it corrodes.
  N-1 served fraction   share of demand that survives the worst single failure

Failure rates come from the DH reliability literature (Valincius et al. 2015)
and are modulated per-branch by the oxygen mass transfer model in
masstransfer.py, so topology feeds into corrosion feeds into reliability.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from masstransfer import corrosion_failure_multiplier
from params import RELIABILITY


# ---------------------------------------------------------------- connectivity
def stranded_demand(n: int, edges, demand, root: int = 0) -> dict:
    """Demand disconnected from the plant by the failure of each edge.

    Works for ANY topology, including one with cycles: for each edge we remove
    it, flood-fill from the plant, and total the demand that can no longer be
    reached. On a tree this reduces to the subtree demand; with redundant
    edges most entries become zero, which is the whole point.
    """
    demand = np.asarray(demand, dtype=float)
    load = np.where(demand > 0, demand, 0.0)
    out = {}
    for k, e in enumerate(edges):
        adj = [[] for _ in range(n)]
        for j, (u, v) in enumerate(edges):
            if j == k:
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
        out[e] = float(load[~seen].sum())
    return out


def is_bridge_free(n: int, edges, demand, root: int = 0) -> bool:
    return all(v <= 1e-9 for v in stranded_demand(n, edges, demand, root).values())


# ---------------------------------------------------------------- failure rates
def edge_failure_rate(length_m: float, dn: int, u: float = 0.0,
                      d_in: float = 0.0, C_O2: float = 2.0e-5,
                      p=RELIABILITY, use_corrosion_model: bool = True) -> float:
    """Failure rate of one branch [failures/year].

        lambda = (base + corrosion) * L[km] * f_DN * f_corrosion

    f_DN captures the empirical observation that DN <= 150 fails more often.
    f_corrosion comes from our own mass transfer model, so a branch running
    fast in a narrow pipe - which is what a cost-minimal tree produces on its
    leaf branches - is correctly penalised.
    """
    L_km = length_m / 1000.0
    rate = (p.base_rate + p.corrosion_rate) * L_km
    if dn <= p.small_dn_threshold:
        rate *= p.small_dn_factor
    if use_corrosion_model and u > 0 and d_in > 0:
        rate *= corrosion_failure_multiplier(u, d_in, C_O2)
    return rate


# ---------------------------------------------------------------- metrics
@dataclass
class ReliabilityResult:
    eud_MWh: float               # expected unserved demand [MWh/y]
    worst_case_kW: float         # N-1 worst single failure [kW]
    worst_edge: tuple | None
    n1_served_fraction: float    # share of demand surviving the worst failure
    total_demand_kW: float
    n_bridges: int
    per_edge: dict = field(default_factory=dict)

    @property
    def eud_ppm(self) -> float:
        """EUD as parts per million of annual delivered energy."""
        return self.eud_MWh


def evaluate(n: int, edges, demand, edge_info: dict, root: int = 0,
             C_O2: float = 2.0e-5, p=RELIABILITY) -> ReliabilityResult:
    """Full reliability assessment of a topology.

    edge_info : {(u, v): {"L3d":.., "dn":.., "u":.., "d_in":..}} - the
                hydraulic result for each branch, so failure rates can depend
                on real diameters and velocities.
    """
    demand = np.asarray(demand, dtype=float)
    total = float(demand[demand > 0].sum())
    strand = stranded_demand(n, edges, demand, root)

    eud = 0.0
    per = {}
    worst_kW, worst_e = 0.0, None
    bridges = 0
    for e in edges:
        info = edge_info.get(e, {})
        lam = edge_failure_rate(
            info.get("L3d", 0.0), info.get("dn", 999),
            info.get("u", 0.0), info.get("d_in", 0.0), C_O2, p,
        )
        lost_kW = strand[e]
        # unserved energy = rate [1/y] * outage [h] * stranded load [kW] -> kWh/y
        unserved_MWh = lam * p.repair_time_h * lost_kW / 1000.0
        eud += unserved_MWh
        if lost_kW > 1e-9:
            bridges += 1
        if lost_kW > worst_kW:
            worst_kW, worst_e = lost_kW, e
        per[e] = dict(rate=lam, stranded_kW=lost_kW, eud_MWh=unserved_MWh)

    return ReliabilityResult(
        eud_MWh=eud, worst_case_kW=worst_kW, worst_edge=worst_e,
        n1_served_fraction=1.0 - worst_kW / max(total, 1e-9),
        total_demand_kW=total, n_bridges=bridges, per_edge=per,
    )


# ---------------------------------------------------------------- augmentation
@dataclass
class AugmentationStep:
    k: int
    edge: tuple | None
    added_cost: float            # annualised cost of the new pipe [EUR/y]
    cum_cost: float
    eud_MWh: float
    worst_case_kW: float
    n1_served_fraction: float
    cost_premium_pct: float
    eud_reduction_pct: float


def greedy_augment(n, tree_edges, demand, candidate_edges, edge_cost_fn,
                   edge_info_fn, base_cost: float, k_max: int = 4,
                   root: int = 0, C_O2: float = 2.0e-5, verbose: bool = True):
    """Add redundant pipes one at a time, best value for money first.

    At each step we score every candidate edge by

        (reduction in expected unserved demand) / (annualised cost of the pipe)

    and commit the best one. This is the classic greedy submodular-style
    heuristic: EUD reduction has diminishing returns, so greedy is a sound and
    interpretable choice, and it produces the reliability-cost trade-off curve
    directly.

    edge_cost_fn : (u, v, backup_kW) -> annualised cost [EUR/y]
    edge_info_fn : (u, v, backup_kW) -> dict for the failure-rate model
    """
    cur = list(tree_edges)
    info = {e: edge_info_fn(*e, 0.0) for e in cur}
    # branches of the tree keep their real operating info
    base_r = evaluate(n, cur, demand, info, root, C_O2)
    steps = [AugmentationStep(0, None, 0.0, 0.0, base_r.eud_MWh,
                              base_r.worst_case_kW, base_r.n1_served_fraction,
                              0.0, 0.0)]
    cum = 0.0
    tree_set = {tuple(sorted(e)) for e in cur}

    for step in range(1, k_max + 1):
        best = None
        for c in candidate_edges:
            cs = tuple(sorted(c))
            if cs in tree_set:
                continue
            # a redundant pipe is sized for the load it must back-feed
            strand = stranded_demand(n, cur, demand, root)
            backup_kW = max(strand.values()) if strand else 0.0
            trial = cur + [c]
            tinfo = dict(info)
            tinfo[c] = edge_info_fn(c[0], c[1], backup_kW)
            r = evaluate(n, trial, demand, tinfo, root, C_O2)
            cost = edge_cost_fn(c[0], c[1], backup_kW)
            gain = base_r.eud_MWh - r.eud_MWh if step == 1 else steps[-1].eud_MWh - r.eud_MWh
            if cost <= 0:
                continue
            score = gain / cost
            if best is None or score > best[0]:
                best = (score, c, cost, r, tinfo)
        if best is None:
            break
        _, c, cost, r, tinfo = best
        cur.append(c)
        info = tinfo
        tree_set.add(tuple(sorted(c)))
        cum += cost
        steps.append(AugmentationStep(
            k=step, edge=c, added_cost=cost, cum_cost=cum,
            eud_MWh=r.eud_MWh, worst_case_kW=r.worst_case_kW,
            n1_served_fraction=r.n1_served_fraction,
            cost_premium_pct=100.0 * cum / base_cost,
            eud_reduction_pct=100.0 * (steps[0].eud_MWh - r.eud_MWh) / max(steps[0].eud_MWh, 1e-12),
        ))
        if verbose:
            s = steps[-1]
            print(f"    +edge {c}  cost +{s.cost_premium_pct:5.2f}%  "
                  f"EUD -{s.eud_reduction_pct:5.1f}%  "
                  f"N-1 served {100*s.n1_served_fraction:5.1f}%")
    return cur, steps
