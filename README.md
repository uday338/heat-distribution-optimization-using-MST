# Graph-Theoretic Topology Optimisation of District-Heating Pipe Networks

**Network Science — CLL798D / CHL7903 — Project**

Minimum spanning trees, Steiner trees and reliability-aware redundancy applied
to two **real** German district-heating networks, on **real** SRTM terrain,
with a transport-phenomena cost model (momentum, heat and mass transfer).

---

## The question

A pipe network is a graph. Choosing its topology is choosing a subgraph, and
the choice fixes capital cost, pumping cost, heat loss, and — the part usually
left out — how the network fails.

The classical answer is a **minimum spanning tree**: the shortest connected,
loop-free layout. This project asks three questions that the classical answer
does not settle:

1. **Is minimum *length* the same as minimum *cost*?**
   Not on real ground. A tree that is 0.1 % longer but avoids a 200 m climb is
   cheaper to build. We weight edges by terrain-resolved construction cost
   derived from a real DEM, and the optimal tree changes.

2. **Is a cost-optimal tree even feasible?**
   In Stuttgart, no. The static head over the network's relief exceeds the
   PN16 pipe pressure class, so a single-pressure-zone network cannot be
   built. We locate the required pressure zones by **spectral bisection** of
   the network Laplacian.

3. **What does fault tolerance cost?**
   Every edge of a tree is a bridge — one pipe failure strands everything
   downstream. Adding Steiner points makes the network *cheaper*, not safer.
   We quantify the trade-off with Expected Unserved Demand and buy redundancy
   greedily, sizing the result under the N-1 criterion.

---

## Headline results

| | Bremen (flat, 63 m relief) | Stuttgart (hilly, 282 m relief) |
|---|---|---|
| Real annual demand | 611,716 MWh/y, 38,794 households | 247,766 MWh/y, 28,520 households |
| Star baseline | 147.9 km, 31.1 EUR/MWh | 104.7 km, 43.7 EUR/MWh |
| MST (map distance) | 49.0 km, 18.9 EUR/MWh | 32.9 km, 23.1 EUR/MWh |
| **MST (terrain-weighted)** | identical to MST-2D | **22.4 EUR/MWh (−3.0 %)** |
| Pressure zones required | 1 | **2 (single zone infeasible)** |
| Worst single pipe failure | strands 49 % of load | strands **100 %** of load |
| Redundancy (+4 pipes, N-1 sized) | see trade-off curve | see trade-off curve |

Terrain weighting changes nothing on flat ground and saves 3.0 % in the hills —
which is the control experiment behaving exactly as it should.

---

## Network science content

Every graph concept in the course maps onto a design decision:

| Graph concept | Engineering question it answers |
|---|---|
| Adjacency / degree matrix | how many pipes meet at each manifold |
| Laplacian spectrum, algebraic connectivity λ₂ | how hard is the network to break apart |
| Edge connectivity, bridges (Menger) | can *any* single pipe failure cut supply? |
| **Spectral bisection** | where to split the hydraulic pressure zones |
| Betweenness centrality | which pipe must not fail |
| Eigenvector centrality, PageRank | which junctions are structurally central |
| Degree distribution vs ER / random-tree nulls | is the optimum structurally special? |
| Clustering, transitivity | trees have no triangles; redundancy adds them |
| Modularity, community detection | natural isolation districts |
| Percolation (random vs targeted) | graceful degradation or collapse? |
| Cayley's formula | why enumeration is hopeless (m^(m−2) trees) |

---

## Algorithms — implemented from scratch

| Algorithm | Complexity | Notes |
|---|---|---|
| `kruskal` | O(E log E) | union-find, path compression + union by rank |
| `prim` | O(E log V) | binary-heap frontier, lazy stale-entry discard |
| `prim_dense` | O(V²) | array frontier, vectorised relaxation |
| `iterated_1steiner` | heuristic | ESMT (Fermat points) and RSMT (Hanan grid) |
| `greedy_augment` | submodular greedy | redundant-edge selection |
| `spectral_pressure_zones` | recursive Fiedler bisection | pressure zoning |

All three MST implementations are verified to return identical tree weight, and
cross-checked against NetworkX.

**Benchmark finding (contradicts the usual textbook expectation).** On complete
graphs the dense array Prim wins decisively; heap-Prim is the *worst* choice:

| V | E | Kruskal | Prim (heap) | Prim (dense) |
|---|---|---|---|---|
| 400 | 79,800 | 18.1 ms | 109.1 ms | 5.2 ms |
| 800 | 319,600 | 84.3 ms | 882.4 ms | 11.7 ms |
| 1600 | 1,279,200 | 419.8 ms | 6114.4 ms | **28.8 ms** |

Fitted exponents: Kruskal α = 2.08, Prim-heap α = 2.52, Prim-dense α = 1.09.
Kruskal does better than expected because it terminates early — at V = 1600 it
examines only **0.7 %** of the sorted edge list.

---

## Transport phenomena

| Transport | What we model | Why the topology cares |
|---|---|---|
| **Momentum** | Darcy–Weisbach with Colebrook–White friction; EN 253 discrete pipe sizing on velocity *and* specific pressure drop; closed-loop pump duty | replaces a constant friction factor; real networks buy DN300, not 0.287 m |
| | static pressure profile p(z), PN rating and cavitation limits | terrain, not length, decides feasibility |
| **Heat** | buried twin-pipe resistance with soil shape factor and mutual coupling; Churchill–Bernstein + radiation for above-ground; exponential temperature decay | heat loss scales with length, so it rewards short trees |
| **Mass** | O₂ transport to the wall (Linton–Sherwood) → corrosion penetration → pipe life → failure rate | **closes the loop**: topology sets velocity and diameter, which set corrosion, which sets reliability |
| | condensation mass flux, steam quality, makeup water, non-condensable derating | steam-network limits on branch length |

The mass-transfer model reproduces, from mechanism alone, the empirical
observation in the reliability literature that DN ≤ 150 pipe fails more often:
`k_m ∝ u^0.83 D^-0.17`, so narrow fast branches corrode faster.

---

## Repository layout

```
src/
  params.py        all parameters, with units, sources, documented readings
  geo.py           EPSG:3035 <-> WGS84 (Snyder), SRTM elevation fetch
  dem.py           DEM raster download, caching, route profiling
  dataset.py       AixDHN loader, census-cell clustering into substations
  terrain.py       terrain-weighted route costing from the real DEM
  mst.py           Kruskal, Prim (heap), Prim (dense), union-find
  steiner.py       ESMT / RSMT via iterated 1-Steiner
  flow_lp.py       Eq(7)-(12) LP, O(V) tree solver, N-1 design flows
  hydraulics.py    friction, pipe selection, pump duty, static pressure
  thermal.py       buried and above-ground heat loss, correlations
  masstransfer.py  O2 -> corrosion -> failure rate; condensation
  costs.py         Gao TAC model; extended European TAC model
  reliability.py   EUD, N-1, greedy redundancy augmentation
  netsci.py        Laplacian, centrality, communities, percolation, zoning
  structure.py     structural metrics per topology
  benchmark.py     MST algorithm timing and scaling
  calibrate.py     Gao case-study reconstruction and validation
  plots.py         figure styling and network drawing

fetch_dems.py      one-off SRTM download
run_real.py        main study on the two real districts
make_figures.py    all presentation figures
docs/DATA_SOURCES.md   provenance of every number
results/           figures, tables, cached topologies
```

## Running it

```bash
pip install numpy scipy matplotlib networkx pandas scikit-learn pulp pypdf
python fetch_dems.py      # ~8 min, downloads real SRTM terrain
python run_real.py        # main analysis
python make_figures.py    # figures
```

## Data

All data is real and cited. See `docs/DATA_SOURCES.md` for the full table,
including an explicit list of what is measured, published, derived, and
assumed. Principal sources: **AixDHN** (RWTH Aachen EBC, MIT licence),
**NASA SRTM 30 m**, **Eurostat** energy prices, **EN 253 / EN 13941**, and the
reliability statistics of **Valinčius et al. (2015)**.
