# Speaker script — 5 minute prelim

Strictly 5 minutes, ~4 of them on results (slides 3–6).
Timings are cumulative in the top-right of each slide.

## 1. Title  —  0:15

We asked whether the minimum spanning tree — the standard answer for pipe-network layout — survives contact with real terrain. It does not, in three separate ways. Those three are the results.

## 2. Setup  —  0:45

Nodes are substations, edges are candidate trenches, and any valid layout is a spanning tree — there are 10^62 of them, so you need an algorithm, and that is why MST is the standard tool. Everything here is real: two German networks from the AixDHN census dataset, 859 GWh/y of real household demand, and NASA SRTM elevation sampled every 25 m along every candidate route. Bremen is flat at 63 m of relief; Stuttgart is 282 m. That contrast is our controlled experiment — same method, same code, two terrains.

## 3. Terrain  —  0:55

First result. We replaced straight-line distance with terrain-weighted construction cost — true slope length times a trenching multiplier that rises with gradient, sampled on the real DEM. In Stuttgart that changes which tree is optimal and saves 3 % of total annual cost, for a tree that is LONGER in metres. And in flat Bremen it returns the identical tree — the control behaving exactly as it must. So minimum length equals minimum cost only on flat ground.

## 4. Feasibility  —  0:55

Second result, and this is the one I would emphasise. The binding constraint from terrain is NOT pumping cost — in a closed supply/return loop the static head cancels, because the return leg gives it back, so pumping is friction only. What does not cancel is the pressure the pipe must physically hold. 282 m of relief is 26.3 bar against a PN16 pipe class rated for 16. One zone can hold 151 m of relief. So Stuttgart needs two pressure zones; Bremen needs one. And where you split them is a balanced minimum-cut problem, because every pipe crossing a zone boundary needs a heat-exchanger station — so we use spectral bisection of the graph Laplacian.

## 5. Reliability  —  1:00

Third result. Structurally, every edge of a tree is a bridge — so any single pipe failure strands everything downstream. A natural question is whether a Steiner tree fixes that. It does not: a Steiner tree is still a tree. In fact the rectilinear Steiner tree is the cheapest topology we found, at 20.87 EUR per MWh, but it has 59 bridges against the MST's 40, because Steiner points concentrate flow into shared trunks. Steiner solves cost; only cycles solve faults. So we price the cycles: one redundant pipe costs 4.3 % and removes 57 % of expected unserved demand, taking N−1 survival from zero to 68 %. And notice the star is the most reliable topology of all — that is the whole trade-off in one line.

## 6. Algorithms  —  0:50

Fourth. All three MST variants written from scratch and verified to return identical tree weight. Our own earlier slides predicted that a dense graph favours Prim — the measurement says it favours the DENSE ARRAY Prim, 212 times faster than the heap version, while heap Prim is actually the worst choice. Kruskal beats it by terminating early, examining only 0.7 % of the edge list. On the reproduction: we matched the paper's MST column exactly, but found Table 2 is not internally self-consistent — a 3× contradiction — and its reported Steiner ratio sits below a proved geometric bound.

## 7. Close  —  0:20

To close: terrain belongs in the edge weight, pressure class belongs in the constraints, and reliability belongs in the objective. On flat ground the MST is the right answer; on real terrain it is neither minimum-cost nor necessarily buildable, and it is never robust. Happy to take questions.


**Total: 5:00**
