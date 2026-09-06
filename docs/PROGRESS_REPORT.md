# Progress Report — Prelim Review

**Graph-Theoretic Topology Optimisation of District-Heating Pipe Networks**
Network Science · CLL798D / CHL7903 · Pathway 1 (reproduce and extend)
Prelim review, 09 September 2026

---

## 1. What changed since the abstract, and why

The approved abstract proposed reproducing Gao et al. (2020) and extending it with a
reliability metric. Two things forced a widening of scope, both discovered by actually
working with the sources rather than by re-reading them.

**(a) The dataset does not contain what we assumed.** The abstract states that AixDHN
would supply "node/coordinate data" for the extension network. It does not. AixDHN
contains district *polygons*, one aggregate annual demand per district, and the list of
100 m census cells making up each district — **no pipes, no diameters, no per-node
demand**. This was verified against the repository's own README and its data files
before any use. We therefore construct the node set ourselves by clustering the real
census cells into substations, which is how a district-heating network is physically
laid out (one substation serves a block of buildings). The assumption is stated
explicitly wherever it matters.

**(b) The reference paper's published results are not internally consistent.** Detailed
in §4. This is not a reason to abandon Pathway 1 — it is the most useful thing a
reproduction can find — but it does mean the reproduction became a *validation and
critique* exercise rather than a number-matching one, and the weight of the project
moved to the extension.

The project therefore now has a sharper thesis than the abstract:

> On flat ground a minimum spanning tree is the right answer. On real terrain it is
> neither minimum-cost nor necessarily buildable — and because every tree edge is a
> bridge, it is never robust. Terrain belongs in the edge weight, pressure class belongs
> in the constraints, and reliability belongs in the objective.

---

## 2. Method

### 2.1 Network construction (real data)

Two German districts were selected from the 1,380 in AixDHN to maximise relief contrast
at comparable scale:

| | Bremen | Stuttgart |
|---|---|---|
| Setting | North German Plain | Neckar basin |
| Annual DH demand | 611,716 MWh/y | 247,766 MWh/y |
| Households | 38,794 | 28,520 |
| Census cells | 1,508 | 840 |
| Relief along routes | **63 m** | **282 m** |

Each district's real census cells are clustered (k-means, fixed seed) into 40 substation
nodes plus one plant, sited at the cell nearest the demand centroid. District demand is
allocated between substations in proportion to census-cell count — the finest allocation
the data supports — and converted to a design load at 1,800 annual full-load hours.

Terrain comes from NASA SRTM 30 m, downloaded as 100 m rasters over each district
(29,248 elevation points total) and sampled every 25 m along every candidate route.

### 2.2 Edge weights

Gao et al. weight edges by straight-line distance. We weight them by terrain-resolved
construction cost:

```
w(e) = Σ_segments  √(Δx² + Δz²) · f(s),   f(s) = 1 + 1.176 s + 3.968 s²
```

where `s = tan θ` is the local ground gradient, and `f` is fitted to published pipeline
terrain cost classes (flat 1.0, rolling ≈1.6 at 15°, mountainous ≈3.0 at 30°). Routes
steeper than 31° are treated as untrenchable.

### 2.3 Cost model

Two independent implementations:

- **`gao_tac`** — the published model, Eq(1)–(24), coded literally, so the reproduction
  tests *their* model rather than ours.
- **`euro_tac`** — the extended model: discrete EN 253 pipe selection on both velocity
  and specific pressure drop; Darcy–Weisbach with Colebrook–White friction; buried
  twin-pipe heat loss with soil shape factor and supply/return mutual coupling;
  terrain-weighted trenching capital via the Persson–Werner cost function; and
  pressure-zone stations where terrain forces them.

### 2.4 Algorithms — all implemented from scratch

`kruskal` (union–find with path compression and union by rank), `prim` (binary-heap
frontier), `prim_dense` (O(V²) array frontier), `iterated_1steiner` (ESMT via Fermat
points, RSMT via the Hanan grid), `greedy_augment` (redundant-edge selection), and
`spectral_pressure_zones` (recursive Fiedler bisection). All three MST implementations
are verified to return identical tree weight and cross-checked against NetworkX.

---

## 3. Validation

Before trusting any result, the physics was checked against independent references.

**The strongest check.** Gao et al.'s Table 1 prints λ and ε with swapped units. Rather
than assume the swap, we derived ε independently from Churchill–Bernstein cross-flow
over a 1 m cylinder at the paper's own wind speed v = 3.50 m/s, plus radiation from
galvanised cladding:

```
h_convection = 10.228 W·m⁻²K⁻¹
h_radiation  =  1.383
h_total      = 11.611          published: 11.630     error −0.16 %
```

This simultaneously validates our thermal model and *proves* the units are swapped.

Other checks that passed:

- ρ = 0.60 kg/m³ implies saturated steam near 1 atm, so T ≈ 100 °C — consistent with the
  paper's own statement that "only low-pressure steam is considered".
- Back-calculated mean heat loss on the reproduced MST is 121 W/m, normal for an
  insulated steam main.
- The O(V) tree flow solver agrees with the literal Eq(7)–(12) LP to 5×10⁻⁵.
- Insulation thickness scaling was taken from the real EN 253 catalogue
  (`t = 0.1025 · D^0.391`, R = 0.963) rather than fitted, keeping the held-out test fair.

---

## 4. Reproduction of Gao et al. (2020), and two findings against it

The paper publishes no coordinates, demands, insulation thickness or steam temperature,
so a literal reproduction is impossible. We instead performed an inverse reconstruction:
search the number of users and the layout to match **both** published pipe lengths
simultaneously. The star/MST length ratio is the identifying constraint, because star
length grows like *n* while MST length grows like √*n*.

```
n = 33 users on a 2.99 km site
star  36,500.0 m   (target 36,500,  error −0.00 %)
MST   11,900.4 m   (target 11,900,  error +0.00 %)
ratio  3.067       (paper 3.067)
```

Three unpublished parameters were then calibrated **on the MST column only** — total
steam demand 87.5 kg/s, insulation 167.6 mm, elbow ζ = 0.598 — all physically
plausible. The **Star column was held out** as an out-of-sample test.

### Finding 1 — Table 2 is not internally self-consistent

The published Star pipe cost (0.869×10⁷) is *lower* than the MST (1.03×10⁷) despite
3.07× the pipe length. Under the paper's own Eq(13)–(14), that cost ratio requires a
total steam demand of **357 kg/s**, whereas the absolute MST pipe cost requires
**87.5 kg/s** — a **3× contradiction**. No single demand reproduces both.

### Finding 2 — the reported ESMT sits at a proved geometric bound

The Du–Hwang Steiner ratio theorem proves `L_SMT / L_MST ≥ √3/2 = 0.86603` for any
planar point set. The paper reports 1.03/1.19 = **0.86555**. This is within table
rounding, but it places the reported values at the extreme edge of what is geometrically
attainable, and well beyond the ≈3–4 % gain typical of realistic point sets.

### Model discrimination

Three insulation-sizing rules were calibrated on the MST column and judged on the
held-out Star column. The physically grounded EN-standard scaling wins on heat loss
(−15.9 % error, vs −34.6 % for constant thickness and +20.5 % for proportional), but no
model reproduces the Star breakdown — consistent with Finding 1.

---

## 5. Results

### 5.1 Terrain changes the optimal tree

| | Bremen (flat) | Stuttgart (hilly) |
|---|---|---|
| Star | 147.9 km, 31.09 EUR/MWh | 104.7 km, 43.72 EUR/MWh |
| MST (map distance) | 49.0 km, 18.88 EUR/MWh | 32.86 km, 23.09 EUR/MWh |
| **MST (terrain-weighted)** | identical to MST-2D | **32.89 km, 22.39 EUR/MWh (−3.0 %)** |
| ESMT | 47.3 km, 18.03 EUR/MWh | 31.41 km, 21.77 EUR/MWh |
| RSMT | 49.1 km, 18.84 EUR/MWh | 32.85 km, 20.87 EUR/MWh |

Terrain weighting saves 3.0 % of total annual cost in Stuttgart for a tree that is
**longer** in metres, and returns the *identical* tree in flat Bremen — the control
experiment behaving exactly as it must.

### 5.2 Terrain makes the cost-optimal tree infeasible

The binding constraint is not pumping cost — in a closed supply/return loop the static
head **cancels**, so pumping is friction-only. The binding constraint is *pressure
class*:

```
static head over 282 m of relief   ρgΔz = 26.3 bar
pipe pressure class                PN16 = 16 bar
maximum relief one zone can hold          151 m
```

Stuttgart therefore requires **2 pressure zones**; Bremen requires 1. Zone boundaries
are chosen by recursive **spectral bisection** of the network Laplacian — a balanced
minimum-cut problem, since every pipe crossing a boundary needs a heat-exchanger
station. This is the course's spectral bisection used directly as a hydraulic design
tool.

### 5.3 Every tree edge is a bridge — and Steiner trees are worse

| Topology (Stuttgart) | EUR/MWh | bridges | N−1 demand served |
|---|---|---|---|
| Star | 43.72 | 40 | **95.6 %** |
| MST-2D | 23.09 | 40 | 33.1 % |
| MST-terrain | 22.39 | 40 | **0.0 %** |
| ESMT | 21.77 | 57 | 0.0 % |
| RSMT | **20.87** | 59 | 0.0 % |
| MST-terrain +R | 26.46 | **17** | **91.9 %** |

A Steiner tree is still a tree. Steiner points buy length — RSMT is the cheapest
topology — but they concentrate flow into shared trunks, so the network becomes *more*
fragile. **Steiner solves cost; only cycles solve faults.**

### 5.4 The reliability–cost trade-off

Expected Unserved Demand, `EUD = Σ_e λ_e · MTTR · D_stranded(e)`, uses real DH failure
rates modulated per branch by our own oxygen mass-transfer corrosion model. Redundant
edges are chosen greedily, and every point on the curve is re-costed with the whole
network **re-sized under the N−1 criterion** — a looped network must carry full load
when one path is lost, so it cannot be sized on normal split flows.

Stuttgart, first redundant pipe: **+4.3 % total annual cost, −57.2 % EUD**, N−1 demand
served rises from 0 % to 67.9 %. Under targeted attack the plain tree collapses to 3 %
served after 12 % of pipes are cut; the looped network still holds 87 %.

### 5.5 Algorithm benchmark — contradicting our own earlier claim

Our prelim slides predicted that graph density would favour Prim. It favours the *dense
array* Prim; heap-Prim is the worst choice:

| V = 1600, E = 1,279,200 | runtime | fitted α |
|---|---|---|
| Kruskal (union–find) | 420 ms | 2.08 |
| Prim (binary heap) | 6,114 ms | 2.52 |
| **Prim (dense array)** | **28.8 ms** | **1.09** |

Kruskal beats heap-Prim by terminating early — at V = 1600 it examines only **0.7 %** of
the sorted edge list. Asymptotic order alone does not pick the algorithm; density and
implementation constants do.

### 5.6 Structural characterisation

Adding four redundant pipes raises algebraic connectivity λ₂ by **2.4×**
(1.67 → 4.03 ×10⁻⁵), cuts bridges from **40 to 17**, and lowers maximum edge betweenness
from 0.676 to 0.442. The terrain MST has modularity 0.698 — strong community structure,
identifying natural isolation districts — while the star scores 0.000.

---

## 6. Assumptions

All assumptions are tabulated with justifications in `docs/DATA_SOURCES.md`, which also
classifies every number in the project as measured, published, derived, or assumed. The
ones that most affect conclusions:

1. Substations obtained by clustering real census cells (AixDHN has none).
2. District demand split ∝ census-cell count (no finer allocation exists in the data).
3. Plant sited at the cell nearest the demand centroid (no plant location in the data).
4. Supply/return 110/50 °C; a 90/45 °C 4GDH case is shown for comparison.
5. PN16 pipe class; the relief threshold is reported as a curve, not a single number.
6. Steiner trees built by the iterated 1-Steiner heuristic, not exact GeoSteiner.

---

## 7. Remaining work before the final

- Scale to 100+ substations and test whether the terrain advantage grows with resolution.
- Replace greedy augmentation with an exact ILP for k ≤ 3 to bound the greedy optimality
  gap.
- Seasonal operation — ambient temperature and part-load, not only design load.
- Sensitivity sweep on ΔT (110/50 vs 90/45) and on pipe pressure class.
- A third district in the Erzgebirge to test the 151 m single-zone threshold directly.
- Individual contribution statement and code appendix for the final report.

---

## 8. Declaration of Tool Usage — mandatory reflection

### 8.1 What was most challenging?

The hardest part was not the algorithms — it was discovering that **neither of our two
primary sources contained what we assumed they did**. The dataset had no pipe network,
and the reference paper's results could not be reproduced from its own equations. Both
discoveries came from working with the sources directly rather than trusting their
descriptions, and both required deciding whether to abandon or reframe the project. We
reframed: the inconsistency in the paper became a result in its own right, and the
missing dataset structure forced a defensible network-construction method.

The second hardest part was hydraulic correctness. Two errors were caught and fixed
during development, both of which would have produced confident, wrong answers:

- **Static head in a closed loop.** Adding ρgΔz to the pump duty is the intuitive move
  and it is wrong — the return leg recovers the head. The real terrain penalty is the
  *pressure-class* constraint, not pumping energy. Getting this backwards would have
  overstated hilly pumping cost by three orders of magnitude.
- **N−1 sizing of looped networks.** Our first augmented result showed redundancy making
  the network *cheaper*, because the LP split flow between two paths and every pipe was
  re-sized smaller. That is physically absurd for redundancy: each path must carry full
  load when the other is lost. Re-sizing under the N−1 criterion turned a −13 % artefact
  into a correct +18 % premium.

### 8.2 Tool use, and observed limitations

An LLM-based assistant (Claude) was used for code development, literature search, and
drafting. Observed limitations and how they were handled:

- **Plausible-but-unverified parameters.** The initial parameter set contained
  reasonable-looking economic values with no source. These were replaced with cited
  figures (Eurostat H2 2025 electricity, Persson–Werner trench cost, Valinčius failure
  rates), and every number in the project was then audited into
  `docs/DATA_SOURCES.md` under measured / published / derived / assumed.
- **Ambiguous source reading.** The paper's Table 1 has mislabelled units, and several
  readings were possible. Rather than accept an assumption, we derived ε independently
  and matched the published value to 0.16 %, which settled the question on evidence.
- **Physics errors that look correct.** The two hydraulic errors in §8.1 were both
  produced with confident explanatory comments attached. They were caught by sanity-
  checking outputs against expectation (redundancy must not reduce cost), not by
  reading the code.
- **A stray non-English comment** and some dead code appeared in generated modules and
  were removed on review.

The working practice that mattered was: verify every external claim against the actual
file or the actual number, and treat any result that "looks too good" as a bug until
proven otherwise.

---

## 9. Reproducing this work

```bash
pip install numpy scipy matplotlib networkx pandas scikit-learn pulp pypdf pillow
python fetch_dems.py      # downloads real SRTM terrain (~8 min)
python run_real.py        # main analysis on both real districts
python make_figures.py    # all nine figures
python build/make_deck.py # presentation deck
```

Full source in `src/` (16 modules), data provenance in `docs/DATA_SOURCES.md`, results
in `results/`.
