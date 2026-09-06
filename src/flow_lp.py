"""
flow_lp.py - Flow allocation over a chosen topology.

Implements the linear programme of Gao et al. Eq(7)-(12): decide the mass flow
in every branch given the node demands and the chosen set of connections.

    min  sum over arcs of w                                    Eq(7)
    s.t. sum(inflow) - sum(outflow) = W_gamma  at every node    Eq(8)
         w defined only where a connection exists               Eq(9)
         one direction per branch                               Eq(10)
         w >= 0                                                 Eq(11,12)

An important observation the paper does not make: on a TREE this LP is
degenerate. A spanning tree has exactly one feasible flow assignment, so the
optimiser has nothing to choose and the LP is an expensive identity. The LP
only becomes a real optimisation once the topology contains a cycle - which is
exactly what our reliability extension introduces. We therefore provide both:

  solve_flows_tree() - O(V) exact solution by depth-first accumulation, used
                       everywhere a tree is being evaluated (thousands of
                       times inside the reliability search);
  solve_flows_lp()   - the literal Eq(7)-(12) LP in PuLP, used for redundant
                       topologies and as an independent check on the tree
                       solver.
"""
from __future__ import annotations

from collections import defaultdict, deque

import numpy as np


# ------------------------------------------------------------------ tree solver
def build_adjacency(n: int, edges) -> list[list[int]]:
    adj: list[list[int]] = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    return adj


def root_tree(n: int, edges, root: int = 0):
    """Return (parent, order) with `order` a valid top-down BFS ordering."""
    adj = build_adjacency(n, edges)
    parent = [-1] * n
    seen = [False] * n
    order = []
    dq = deque([root])
    seen[root] = True
    while dq:
        u = dq.popleft()
        order.append(u)
        for v in adj[u]:
            if not seen[v]:
                seen[v] = True
                parent[v] = u
                dq.append(v)
    return parent, order


def solve_flows_tree(n: int, edges, demand, root: int = 0) -> dict:
    """Exact branch flows on a tree by accumulating subtree demand.

    demand[i] > 0 is a consumer draw, demand[0] < 0 is the plant supply.
    The flow in the branch above node v equals the total demand of the subtree
    rooted at v. Returns a dict keyed by the (u, v) tuples that were passed in.

    Raises ValueError if the edge set is not a spanning tree.
    """
    demand = np.asarray(demand, dtype=float)
    if len(edges) != n - 1:
        raise ValueError(f"not a spanning tree: {len(edges)} edges for {n} nodes")
    parent, order = root_tree(n, edges, root)
    if len(order) != n:
        raise ValueError("topology is disconnected")

    subtree = demand.copy()
    for v in reversed(order):            # leaves first
        p = parent[v]
        if p >= 0:
            subtree[p] += subtree[v]

    flows = {}
    for (u, v) in edges:
        child = v if parent[v] == u else u
        flows[(u, v)] = float(abs(subtree[child]))
    return flows


def subtree_demand(n: int, edges, demand, root: int = 0):
    """Demand disconnected by removing each edge (used by the reliability model).

    Returns dict edge -> total demand stranded on the far side of that edge.
    On a tree every edge is a bridge, so this is simply the subtree demand.
    """
    demand = np.asarray(demand, dtype=float)
    parent, order = root_tree(n, edges, root)
    sub = demand.copy()
    sub[root] = 0.0                       # the plant is not a load
    acc = sub.copy()
    for v in reversed(order):
        p = parent[v]
        if p >= 0:
            acc[p] += acc[v]
    out = {}
    for (u, v) in edges:
        child = v if parent[v] == u else u
        out[(u, v)] = float(acc[child])
    return out


# ------------------------------------------------------------------ LP solver
def solve_flows_lp(n: int, edges, demand, lengths=None,
                   objective: str = "gao", msg: bool = False) -> dict:
    """The literal Eq(7)-(12) linear programme.

    objective : "gao"       minimise the sum of branch flows, Eq(7)
                "transport" minimise sum(length * flow), the transport work,
                            which is the physically meaningful tie-break when
                            the topology contains cycles.

    Every undirected branch becomes two non-negative arcs, which is the
    standard way to encode the (-1)^r direction switch of Eq(8) and (10) in a
    linear programme.
    """
    import pulp

    demand = np.asarray(demand, dtype=float)
    prob = pulp.LpProblem("flow_allocation", pulp.LpMinimize)

    arcs = []
    for k, (u, v) in enumerate(edges):
        arcs.append((k, u, v))
        arcs.append((k, v, u))
    w = {
        (k, a, b): pulp.LpVariable(f"w_{k}_{a}_{b}", lowBound=0)
        for (k, a, b) in arcs
    }

    if objective == "transport" and lengths is not None:
        prob += pulp.lpSum(lengths[k] * w[(k, a, b)] for (k, a, b) in arcs)
    else:
        prob += pulp.lpSum(w.values())                       # Eq(7)

    inflow = defaultdict(list)
    outflow = defaultdict(list)
    for (k, a, b) in arcs:
        outflow[a].append(w[(k, a, b)])
        inflow[b].append(w[(k, a, b)])
    for g in range(n):                                       # Eq(8)
        prob += pulp.lpSum(inflow[g]) - pulp.lpSum(outflow[g]) == demand[g]

    status = prob.solve(pulp.PULP_CBC_CMD(msg=msg))
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(f"LP not optimal: {pulp.LpStatus[status]}")

    flows = {}
    for k, (u, v) in enumerate(edges):
        fwd = w[(k, u, v)].value() or 0.0
        rev = w[(k, v, u)].value() or 0.0
        flows[(u, v)] = float(abs(fwd - rev))
    return flows


def design_flows_n1(n: int, edges, demand, root: int = 0, lengths=None) -> dict:
    """Design flow in every branch under the N-1 criterion.

    A looped network must not be sized on its normal-operation flows. In
    normal operation a loop splits the load between two paths, so each pipe
    carries less - but the whole point of building the loop is that when one
    path is lost the other must carry EVERYTHING. Sizing on the split flow
    would produce a network that is cheaper on paper and unable to perform the
    duty it was built for.

    So the design flow of each branch is the worst case over
        {normal operation} U {failure of any one other branch}
    which is standard utility N-1 practice. On a tree this reduces to the
    ordinary tree flows, because no alternative path exists.
    """
    demand = np.asarray(demand, dtype=float)
    if len(edges) == n - 1:
        return solve_flows_tree(n, edges, demand, root)

    if lengths is None:
        lengths = [1.0] * len(edges)
    design = {e: 0.0 for e in edges}

    def _accumulate(sub_edges, sub_lengths):
        try:
            f = solve_flows_lp(n, sub_edges, demand, sub_lengths,
                               objective="transport")
        except Exception:
            return
        for e, v in f.items():
            design[e] = max(design[e], v)

    _accumulate(list(edges), list(lengths))          # normal operation
    for k in range(len(edges)):                       # each single failure
        sub = [e for j, e in enumerate(edges) if j != k]
        sl = [l for j, l in enumerate(lengths) if j != k]
        # only meaningful if the network survives this failure
        adj = [[] for _ in range(n)]
        for (u, v) in sub:
            adj[u].append(v)
            adj[v].append(u)
        seen = [False] * n
        stack = [root]
        seen[root] = True
        while stack:
            x = stack.pop()
            for y in adj[x]:
                if not seen[y]:
                    seen[y] = True
                    stack.append(y)
        if all(seen[i] or demand[i] <= 0 for i in range(n)):
            _accumulate(sub, sl)
    return design


def check_solvers_agree(n: int, edges, demand, tol: float = 1e-6) -> tuple[bool, float]:
    """Verify the O(V) tree solver against the Eq(7)-(12) LP on a tree."""
    a = solve_flows_tree(n, edges, demand)
    b = solve_flows_lp(n, edges, demand)
    err = max(abs(a[e] - b[e]) for e in edges) if edges else 0.0
    scale = max(1.0, max(abs(v) for v in a.values()) if a else 1.0)
    return err <= tol * scale, err
