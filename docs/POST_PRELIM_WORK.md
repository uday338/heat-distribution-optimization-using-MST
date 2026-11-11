# Work done after the prelim presentation (9 Sep 2026)

All of this reuses the prelim code in `src/` and the same two districts
(AixDHN Bremen and Stuttgart, NASA SRTM 30 m). No new raw data was added.
`run_real.py` must be run first, because the new scripts read the cached
topologies it writes to `results/*.pkl`.

The prelim numbers reproduce exactly: Stuttgart, 40 substations, seed 42,
map MST 23.09 and terrain MST 22.39 EUR/MWh.

## 1. Robustness: 120 networks (`run_final.py B`)

Same two districts, clustered into 20, 40, 60, 80, 120 and 160 substations,
with 10 k-means seeds each: 6 × 10 × 2 = 120 networks.

- Stuttgart, 40 substations: terrain saving ranges from -6.3% to +13.3%
  depending only on the seed.
- Median over the 50 Stuttgart networks with 40 or more substations: +1.2%,
  negative in 15 of them. Bremen: zero in 33 of 50.
- Of the prelim's 3.04% saving, 2.68 points were pumping and 0.41 trenching.

## 2. Seasonal load (`run_final.py E`)

Sochinsky load-duration curve (1,800 full-load hours, 10% summer base load,
supply 110 → 80 °C), integrated over 40 load levels pipe by pipe.

- Stuttgart terrain MST: pump energy 5,399 → 631 MWh/yr, heat loss
  15,141 → 12,357 MWh/yr, cost 22.39 → 18.07 EUR/MWh.
- Terrain saving falls to 0.9% (0.85 to 0.91% for 5 to 20% summer load).
- The load curve is assumed, not measured.

## 3. Flow-aware edge-swap search (`run_final_F.py`, `run_final_G.py scale`)

Start from the MST; add a non-tree edge among each node's 8 nearest
neighbours, remove the cycle edge that gives the lowest total cost, keep it if
the cost falls; repeat until no swap helps. Costed with the seasonal model.

| Substations | Stuttgart gain | Bremen gain | Clusterings |
|---|---|---|---|
| 40 | 5.8% | 6.7% | 10 |
| 80 | 8.6% | 9.5% | 5 |
| 160 | 7.8% | 7.9% | 2 |

Stuttgart seed 42: 18.07 → 16.48 EUR/MWh, 32.9 → 33.9 km, pump head
14.2 → 8.6 bar. Starting from the map MST or the terrain MST ends within
0.09 EUR/MWh.

## 4. Which graph property decides cost (`run_final_G.py design`)

30 trees per city (3 tree types × 10 clusterings).

- Correlation of cost with total length: -0.46 (Stuttgart), -0.30 (Bremen).
- With demand-weighted distance to the plant: +0.98 and +0.97.
- R² of a linear fit: 0.21 with length alone, 0.97 with length plus weighted
  distance (Stuttgart).

## 5. Pressure zones and the relief sweep (`run_final.py B, D`, `run_final_G.py relief`)

- Real terrain: Stuttgart needs 2 PN16 zones in 60 of 60 networks, Bremen 1.
  PN10 gives 3 zones and PN25 gives 1; cost changes by 0.5%.
- Stuttgart's elevations scaled about their mean by 0 to 1.5 (10 clusterings
  each), as a substitute for the planned third district. Zones switch from 1
  to 2 where the relief along built routes crosses 151 m. Mean terrain
  saving: 0% flat, 2.6% real, 4.7% at 1.5×.

## 6. Redundancy: brute force and ILP (`run_final.py C`, `run_final_G.py ilp`)

A new pipe on a tree protects exactly the tree edges on its cycle, so the
choice is a weighted maximum-coverage problem.

- Brute force over all 780 candidates, 303,810 pairs and 78.8 million triples
  per city: greedy is on the optimum in 5 of 6 cases.
- ILP (scipy `milp`, HiGHS) for 1 to 8 pipes at the greedy's budget: greedy is
  never more than 1.5 points below the optimum. The ILP equals the brute
  force for 1 to 3 pipes.
- Edge-swap tree + 1 loop: Stuttgart 18.45 EUR/MWh, 67% served after the
  worst failure; MST + 1 loop: 19.39, 68% (means over 10 clusterings).

## 7. Sensitivity (`run_final.py D`)

Electricity ±50%, heat price ±50%, discount 2 to 6% and a 90/45 °C regime
change the terrain saving between 1.9 and 4.0% but never the cost ranking of
the topologies.

## Limitations

- Load curve from a formula, no hourly demand data.
- Edge swap is a local search with no optimality bound.
- Still two districts; the relief sweep scales one city's terrain.
- The 160-substation edge-swap figures use only 2 clusterings per city.
- Total pump head is not checked against the pipe pressure rating.
