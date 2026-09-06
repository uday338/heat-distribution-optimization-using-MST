# Data Sources and Provenance

Every quantity used anywhere in this project, classified as **MEASURED** (real
downloaded data), **PUBLISHED** (a value or correlation taken from a cited
source), **DERIVED** (computed by us from measured/published inputs), or
**ASSUMED** (a modelling choice we made, always with a justification and,
where it matters, a sensitivity test).

Nothing in the pipeline is a placeholder or invented number.

---

## 1. MEASURED — real data downloaded and used as-is

### 1.1 District-heating network geometry and demand

| Item | Value / extent | Source |
|---|---|---|
| Node coordinates | 100 m census-grid cells, EPSG:3035 | AixDHN `DH_cells` |
| Annual heat demand | Bremen 611,716 MWh/y; Stuttgart 247,766 MWh/y | AixDHN `DH_demand` |
| Households served | Bremen 38,794; Stuttgart 28,520 | AixDHN `DH_supplied_households` |
| Network area | Bremen 69.81 km²; Stuttgart 23.68 km² | AixDHN `area` |
| Census cells | Bremen 1,508; Stuttgart 840 | AixDHN |

**Source.** RWTH Aachen University, E.ON Energy Research Center, Institute for
Energy Efficient Buildings and Indoor Climate (EBC) — *AixDHN: District Heating
Networks Dataset from Clustered Census Data*.
<https://github.com/RWTH-EBC/AixDHN> — **MIT Licence**.
Files used: `GeoJSON-Files/ExistingNetworks/heatgrids_Bremen.geojson`,
`heatgrids_Baden-Wuerttemberg.geojson`, `heatgrids_Thueringen.geojson`.
Downloaded 2026-09-06; local copies in `data/aixdhn/`.

> **Important correction to our own abstract.** The abstract stated that AixDHN
> would supply "node/coordinate data" for a pipe network. It does **not**
> contain pipes, pipe lengths, diameters, or per-node demand — only district
> polygons, aggregate annual demand, and the census cells making up each
> district. We verified this against the repository's own README before use,
> and built the node set ourselves by clustering the real census cells (see
> §4.1). This is stated openly rather than glossed over.

### 1.2 Terrain

| Item | Value | Source |
|---|---|---|
| Elevation model | SRTM 30 m (SRTMGL1 v3) | NASA / USGS |
| Bremen DEM | 155 × 126 grid @ 100 m, −26 … 37 m a.s.l. | 19,530 sampled points |
| Stuttgart DEM | 113 × 86 grid @ 100 m, 211 … 493 m a.s.l. | 9,718 sampled points |
| Relief (nodes) | Bremen 13 m; Stuttgart 144 m | derived from DEM |
| Relief (full routes) | Bremen 63 m; Stuttgart 282 m | derived from DEM |

**Source.** NASA Shuttle Radar Topography Mission, SRTMGL1 v3, served by
OpenTopoData (<https://www.opentopodata.org/datasets/srtm/>). Retrieved
2026-09-06; cached rasters in `data/dem/`.

### 1.3 Economic data

| Item | Value | Source |
|---|---|---|
| Electricity price (pumping) | 0.1922 EUR/kWh | Eurostat, non-household, Germany, H2 2025, 2,000–20,000 MWh/y band, excl. recoverable VAT |
| Heat value (losses) | 0.055 EUR/kWh | Eurostat non-household gas price ÷ 0.90 boiler efficiency |

Eurostat electricity price statistics:
<https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Electricity_price_statistics>

---

## 2. PUBLISHED — values and correlations from the literature

### 2.1 The reference paper

Gao W., Deng P., He Y., Wu Y., Wang Y., Wang S., Zhou Y. (2020),
*Topology Optimization of Pipe Network in a Distributed Energy System*,
**Chemical Engineering Transactions 81**, 277–282.
DOI: [10.3303/CET2081047](https://doi.org/10.3303/CET2081047) ·
PDF: <https://www.aidic.it/cet/20/81/047.pdf>

Used: Table 1 parameters, Table 2 results, Eq(1)–(24). Full extracted text in
`docs/gao2020_extracted_text.txt`.

**Documented inconsistencies in the published Table 1** (see `src/params.py`,
flagged `# [READING]`) — we identify these rather than silently correcting them:

| Printed | Problem | Reading adopted | Justification |
|---|---|---|---|
| `A1 = 5.74 CNY/y` | A1 is defined in the text as price per unit *weight* | CNY/kg | dimensional consistency of Eq(13) |
| `λ = 0.06 W/m²K` | units swapped with ε | W/(m·K) | textbook mineral-wool conductivity |
| `ε = 11.63 W/mK` | units swapped with λ | W/(m²·K) | **independently derived: 11.611 (0.16 % error)** — see §3.1 |
| `α_k = 0.1945` (no unit) | `a_k` is *computed* by Eq(13), cannot be an input | steam price `a` = 0.1945 CNY/kg | only undefined symbol in Eq(23); 194.5 CNY/t is correct for Chinese industrial steam; reproduces the published heat-loss cost |
| `σ = 0.015 CNY/kg` | σ is the friction factor in Eq(19) | dimensionless | textbook value; the CNY/kg unit belongs to the steam-price row |

### 2.2 Cost model

Persson U. & Werner S. (2011), *Heat distribution and the future
competitiveness of district heating*, **Applied Energy 88(3)**, 568–576.
→ trench cost `C = C1 + C2·d` with `C1 = 212 EUR/m`, `C2 = 4790 EUR/m²`.

Rui Z., Metz P.A., Reynolds D.B., Chen G., Zhou X. (2011), *Historical pipeline
construction cost analysis*, **Int. J. Oil, Gas and Coal Technology 4(3)**,
244–263. → terrain cost classes (flat 1.0, rolling ≈1.6 @ 15°,
mountainous ≈3.0 @ 30°), fitted to `f(s) = 1 + 1.176 s + 3.968 s²`.

### 2.3 Reliability

Valinčius M., Žutautaitė I., Dundulis G., Rimkevičius S., Janulionis R.,
Bakas R. (2015), *Integrated assessment of failure probability of the district
heating network*, **Reliability Engineering & System Safety 133**, 314–322.
<https://www.sciencedirect.com/science/article/abs/pii/S0951832014002385>

Valinčius M. et al. (2014), *Probability of Failure Assessment in District
Heating Network*. <https://www.davidpublisher.com/Public/uploads/Contribute/5583c34ee9b88.pdf>

| Failure mode | Rate [failures/(km·y)] |
|---|---|
| Pre-insulated bonded pipe | 0.02 |
| Duct-channel pipe | 0.19 |
| Pipe inside buildings | 0.31 |
| Surface corrosion mechanism | 0.07 |
| DN ≤ 150 | elevated (factor 1.6 applied) |

### 2.4 Transport-phenomena correlations

| Correlation | Use | Source |
|---|---|---|
| Colebrook–White | Darcy friction factor | Colebrook (1939), *J. Inst. Civ. Eng.* 11, 133–156 |
| Haaland | explicit friction approximation | Haaland (1983), *J. Fluids Eng.* 105, 89–90 |
| Churchill–Bernstein | external cross-flow over cylinder | Churchill & Bernstein (1977), *J. Heat Transfer* 99, 300–306 |
| Gnielinski | internal turbulent convection | Gnielinski (1976), *Int. Chem. Eng.* 16, 359–368 |
| Linton–Sherwood | O₂ mass transfer to pipe wall, `Sh = 0.023 Re^0.83 Sc^(1/3)` | Linton & Sherwood (1950), *Chem. Eng. Prog.* 46, 258–264 |
| Colburn–Hougen | condensation with non-condensables | Colburn & Hougen (1934), *Ind. Eng. Chem.* 26, 1178–1182 |
| Buried twin-pipe resistance | heat loss with mutual coupling | Wallentén (1991); Bøhm (2000) |

### 2.5 Graph theory

| Result | Use | Source |
|---|---|---|
| Algebraic connectivity λ₂ | continuous robustness measure | Fiedler (1973), *Czech. Math. J.* 23, 298–305 |
| Iterated 1-Steiner heuristic | ESMT / RSMT construction | Kahng & Robins (1992), *IEEE Trans. CAD* 11(7), 893–902 |
| Hanan grid | optimal RSMT Steiner candidates | Hanan (1966), *SIAM J. Appl. Math.* 14, 255–265 |
| Steiner ratio √3/2 | bound on achievable Steiner gain | Du & Hwang (1992), *Algorithmica* 7, 121–135 |
| Greedy modularity communities | sub-network detection | Clauset, Newman & Moore (2004) |
| Course text | general network science | Newman M.E.J., *Networks: An Introduction*, OUP |

### 2.6 Standards and property data

| Item | Source |
|---|---|
| EN 253 pre-insulated pipe catalogue (DN20–DN1000, inner/steel/casing diameters) | EN 253 series-2 insulation |
| Pipe roughness 4×10⁻⁵ m; burial depth 0.8 m | EN 13941 |
| PUR conductivity 0.027 W/(m·K) | EN 253 |
| Design velocity window 0.5–3.0 m/s | Frederiksen & Werner, *District Heating and Cooling* (2013), ch. 9 |
| Specific pressure drop limit 100 Pa/m | Frederiksen & Werner (2013), ch. 9 |
| Water properties at 110 °C | IAPWS-IF97, as tabulated in Incropera & DeWitt, App. A.6 |
| Air properties near 0–5 °C | Incropera & DeWitt, Table A.4 |
| Dissolved-O₂ limit 0.02 mg/L | VGB-S-010 / EN 12953 practice |

---

## 3. DERIVED — computed by us, and independently checkable

### 3.1 Validation of the paper's ε (strongest single check)

Churchill–Bernstein for a 1 m cylinder in the paper's own Table 1 wind speed
`v = 3.50 m/s` at ambient 3.35 °C, plus radiation from galvanised cladding
(ε_emis = 0.25):

```
h_convection = 10.228 W/(m² K)
h_radiation  =  1.383 W/(m² K)
h_total      = 11.611 W/(m² K)
published    = 11.630 W/(m² K)      →  error −0.16 %
```

This is computed from an independent correlation and confirms both the value
and that the Table 1 units for λ and ε are swapped. Code:
`thermal.validate_gao_epsilon()`.

### 3.2 Insulation thickness scaling, from the real EN 253 catalogue

Log-log fit of `t_ins` against `D_steel` over the 22 catalogue sizes:

```
t_ins = 0.1025 · D_steel^0.391      (R = 0.963)
```

The exponent 0.391 comes from the **standard**, not from any data we are
validating against, so it remains a fair out-of-sample test.

### 3.3 Reconstruction of the Gao case-study geometry

The paper publishes no coordinates. Searching `n` and layout seed to match
**both** published lengths simultaneously (star 3.65×10⁴ m, MST 1.19×10⁴ m):

```
n = 33 users, 2.99 km square site
star  36,500.0 m   (target 36,500, error −0.00 %)
MST   11,900.4 m   (target 11,900, error +0.00 %)
star/MST ratio 3.067  (paper 3.067)
```

The star/MST length ratio is the identifying constraint, because star length
grows like *n* while MST length grows like √*n*.

### 3.4 Physical consistency checks on Table 1

- `ρ = 0.60 kg/m³` ⇒ saturated steam near 1 atm ⇒ `T ≈ 100 °C`, consistent
  with the paper's "only low-pressure steam is considered".
- Back-calculated mean heat loss on the MST: **121 W/m** — a physically normal
  value for an insulated steam main.

---

## 4. ASSUMED — our modelling choices, stated and justified

| # | Assumption | Value | Justification | Tested? |
|---|---|---|---|---|
| 4.1 | Substation nodes obtained by k-means clustering of real census cells | 40 substations + 1 plant | AixDHN has no substations; a DH substation physically serves a block of buildings | node-count sensitivity available |
| 4.2 | District demand split between substations ∝ census-cell count | — | cells are equal-area and are the finest resolution the data supports; no finer allocation exists | — |
| 4.3 | Plant located at the census cell nearest the demand centroid | — | AixDHN gives no plant location | alternative "centroid" option in code |
| 4.4 | Design load from annual energy ÷ full-load hours | 1,800 h/y | German existing residential stock; AixDHN demand is household heat | — |
| 4.5 | Supply / return temperatures | 110 / 50 °C | standard German DH primary design point | 90/45 °C (4GDH) shown in Fig. 7 |
| 4.6 | Pipe pressure class | PN16 | standard DH distribution class | threshold curve in Fig. 7 |
| 4.7 | Pressure-zone station cost | 250,000 EUR | order-of-magnitude for a DH heat-exchanger station | enters only the zone term |
| 4.8 | Gao insulation thickness (not published) | calibrated | three competing models tested against the held-out Star column | **yes — model selection** |
| 4.9 | Gao elbow loss coefficient (not published) | calibrated ζ = 0.598 | falls in the textbook 90° elbow range 0.3–0.9 | — |
| 4.10 | Gao total steam demand (not published) | calibrated 87.5 kg/s | = 315 t/h, realistic for a 33-user industrial park | — |
| 4.11 | Gao user demand spread | lognormal σ = 0.5 | usual description of industrial load distributions | — |
| 4.12 | Steiner trees built by heuristic, not exact GeoSteiner | iterated 1-Steiner | within ~0.5 % of optimal in the literature; transparent and reimplementable | gain vs MST reported |
| 4.13 | Steiner points draw zero load | — | they are physical tee/manifold junctions | — |
| 4.14 | Repair time for a burst | 12 h | typical DH mains repair duration | linear factor in EUD |

---

## 5. Reproducing the data pull

```bash
python fetch_dems.py     # downloads SRTM rasters (~360 API calls, ~8 min)
python run_real.py       # full analysis on both real districts
python make_figures.py   # all figures
```

`data/aixdhn/*.geojson` are downloaded directly from the AixDHN repository;
`data/dem/*.pkl` are cached SRTM rasters. Deleting either causes a re-fetch.
