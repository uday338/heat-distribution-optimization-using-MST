"""
make_figures.py - Generate every presentation figure from the saved results.

Run after run_real.py. Writes PNGs to results/figures/.
"""
from __future__ import annotations

import json
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, "src")

import matplotlib.pyplot as plt

import netsci as ns
from costs import euro_tac
from plots import (
    C,
    COST_COLOR,
    GRID,
    INK,
    INK2,
    INK3,
    SERIES,
    TOPO_COLOR,
    apply_style,
    despine,
    dn_widths,
    draw_network,
    label_bars,
    legend_swatches,
    scalebar,
)

FIG = "results/figures"
apply_style()
ORDER = ["Star", "MST-2D", "MST-terrain", "ESMT", "RSMT", "MST-terrain+R"]


def load(tag):
    with open(f"results/tables/{tag}_results.json") as fh:
        res = json.load(fh)
    with open(f"results/{tag}_topologies.pkl", "rb") as fh:
        raw = pickle.load(fh)
    return res, raw


def save(fig, name):
    path = f"{FIG}/{name}.png"
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", path)


# =====================================================================
def fig_networks(flat, hilly):
    """The two real networks on their real terrain, three topologies each."""
    (rf, df), (rh, dh) = flat, hilly
    fig, axes = plt.subplots(2, 3, figsize=(13.2, 8.4))
    for row, (res, raw, name) in enumerate(
        [(rf, df, "Bremen - North German Plain"),
         (rh, dh, "Stuttgart - Neckar basin")]
    ):
        dem = raw["dem"]
        xy = raw["xy"]
        rel = res["relief"]
        for col, topo in enumerate(["Star", "MST-terrain", "MST-terrain+R"]):
            ax = axes[row, col]
            if topo == "MST-terrain+R":
                edges = raw["aug_edges"]
                nxy, ndem_, nM = xy, raw["demand"], raw["M"]
            else:
                edges, nxy, ndem_, nM = raw["topo"][topo]
            c = euro_tac(len(nxy), edges, nM, ndem_,
                         np.zeros(len(nxy)))
            w = dn_widths(c.detail["per_edge"], edges)
            base = raw["topo"]["MST-terrain"][0]
            cols = [TOPO_COLOR[topo] if topo != "MST-terrain+R"
                    else (C["violet"] if e not in base and e[::-1] not in base
                          else C["orange"])
                    for e in edges]
            draw_network(ax, nxy, edges, dem=dem, edge_width=w,
                         edge_color=cols, title="")
            r = res["results"][topo]
            ax.set_title(f"{topo}", color=INK, pad=4)
            ax.text(0.02, 0.98,
                    f"{r['length_3d_km']:.1f} km   "
                    f"{r['specific_cost']:.1f} EUR/MWh\n"
                    f"N-1 served {100*r['n1_served']:.0f}%   "
                    f"{r['n_zones']} pressure zone(s)",
                    transform=ax.transAxes, va="top", ha="left", fontsize=7.6,
                    color=INK, bbox=dict(fc="white", ec=GRID, alpha=0.85,
                                         boxstyle="round,pad=0.35"))
            if col == 0:
                ax.text(-0.03, 0.5, name, transform=ax.transAxes,
                        rotation=90, va="center", ha="right",
                        fontsize=10, fontweight="bold", color=INK)
                ax.text(0.02, 0.02,
                        f"relief {rel['relief_m']:.0f} m",
                        transform=ax.transAxes, fontsize=7.5, color=INK2)
            scalebar(ax, xy, 2000)
    fig.suptitle("Real district-heating networks on real SRTM terrain\n"
                 "pipe thickness proportional to nominal diameter; "
                 "violet = redundant pipes added by the reliability model",
                 fontsize=11.5, color=INK, y=1.015)
    save(fig, "fig1_networks")


def fig_costs(flat, hilly):
    """Cost breakdown per topology, both districts, specific cost."""
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.9))
    parts = ["capital", "pumping", "heat_loss", "zones"]
    plabels = ["Pipe capital", "Pumping (friction)", "Heat loss to ground",
               "Pressure-zone stations"]
    for ax, (res, _), title in zip(
        axes, [flat, hilly],
        ["Bremen (flat, 8 m relief)", "Stuttgart (hilly, 282 m relief)"]
    ):
        names = [n for n in ORDER if n in res["results"]]
        x = np.arange(len(names))
        bottom = np.zeros(len(names))
        deliv = np.array([res["results"][n]["delivered_MWh"] for n in names])
        for p, lab, col in zip(parts, plabels,
                               [COST_COLOR[k] for k in parts]):
            v = np.array([res["results"][n][p] for n in names]) / deliv
            ax.bar(x, v, bottom=bottom, color=col, width=0.66,
                   edgecolor="#fcfcfb", linewidth=2.0, label=lab)
            bottom += v
        label_bars(ax, x, bottom, fmt="{:.1f}")
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=18, ha="right")
        ax.set_ylabel("specific cost  [EUR / MWh delivered]")
        ax.set_title(title, color=INK)
        despine(ax)
        ax.grid(axis="x", visible=False)
    axes[0].legend(loc="upper right", ncols=1)
    fig.suptitle("Total annual cost by topology - real demand, real terrain, "
                 "cited cost data", fontsize=11.5, color=INK, y=1.02)
    fig.tight_layout()
    save(fig, "fig2_cost_breakdown")


def fig_terrain(hilly):
    """Why terrain weighting changes the optimal tree."""
    res, raw = hilly
    dem, xy = raw["dem"], raw["xy"]
    e2d = raw["topo"]["MST-2D"][0]
    et = raw["topo"]["MST-terrain"][0]
    s2, st_ = {tuple(sorted(e)) for e in e2d}, {tuple(sorted(e)) for e in et}
    only2, onlyt = s2 - st_, st_ - s2

    fig = plt.figure(figsize=(12.8, 5.0))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 1, 1], wspace=0.28)

    ax = fig.add_subplot(gs[0, 0])
    draw_network(ax, xy, list(s2 | st_), dem=dem,
                 edge_color=[C["blue"] if tuple(sorted(e)) in st_ and tuple(sorted(e)) in s2
                             else (C["orange"] if tuple(sorted(e)) in onlyt else C["magenta"])
                             for e in (s2 | st_)],
                 edge_width=[1.6 if tuple(sorted(e)) in s2 and tuple(sorted(e)) in st_ else 2.8
                             for e in (s2 | st_)])
    ax.set_title("Stuttgart: where the two trees differ", color=INK)
    legend_swatches(ax, ["shared by both", "only Euclidean MST",
                         "only terrain MST"],
                    [C["blue"], C["magenta"], C["orange"]],
                    loc="lower right", fontsize=7.4)
    scalebar(ax, xy, 2000)

    # elevation profile of one rerouted pair
    ax2 = fig.add_subplot(gs[0, 1])
    if only2 and onlyt:
        # show the dropped edge with the most punishing elevation profile
        u, v = max(only2, key=lambda e: np.ptp(dem.profile(xy[e[0]], xy[e[1]])[1]))
        s, z = dem.profile(xy[u], xy[v])
        ax2.plot(s / 1000, z, color=C["magenta"], label=f"dropped edge {u}-{v}")
        u2, v2 = list(onlyt)[0]
        s2b, z2 = dem.profile(xy[u2], xy[v2])
        ax2.plot(s2b / 1000, z2, color=C["orange"], label=f"chosen edge {u2}-{v2}")
        ax2.set_xlabel("chainage along route  [km]")
        ax2.set_ylabel("elevation  [m a.s.l.]")
        ax2.set_title("Route elevation profiles", color=INK)
        ax2.legend(loc="best", fontsize=7.4)
        despine(ax2)

    ax3 = fig.add_subplot(gs[0, 2])
    names = ["MST-2D", "MST-terrain"]
    L = [res["results"][n]["length_3d_km"] for n in names]
    T = [res["results"][n]["specific_cost"] for n in names]
    x = np.arange(2)
    ax3.bar(x - 0.19, L, width=0.34, color=C["aqua"], label="3D length [km]",
            edgecolor="#fcfcfb", linewidth=2)
    ax3.bar(x + 0.19, T, width=0.34, color=C["violet"],
            label="specific cost [EUR/MWh]", edgecolor="#fcfcfb", linewidth=2)
    for xi, (l, t) in enumerate(zip(L, T)):
        ax3.text(xi - 0.19, l, f"{l:.2f}", ha="center", va="bottom", fontsize=7.5)
        ax3.text(xi + 0.19, t, f"{t:.2f}", ha="center", va="bottom", fontsize=7.5)
    ax3.set_xticks(x)
    ax3.set_xticklabels(names)
    ax3.set_title(f"Terrain weighting saves "
                  f"{100*(T[0]-T[1])/T[0]:.1f} % of TAC", color=INK)
    ax3.legend(loc="upper center", fontsize=7.4)
    despine(ax3)
    ax3.grid(axis="x", visible=False)
    fig.suptitle("A longer tree can be the cheaper tree: terrain-weighted "
                 "routing on real topography", fontsize=11.5, color=INK, y=1.03)
    save(fig, "fig3_terrain_effect")


def fig_reliability(flat, hilly):
    """The reliability-cost trade-off and what redundancy buys."""
    fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.5))
    for (res, _), lab, col in [(flat, "Bremen (flat)", C["blue"]),
                               (hilly, "Stuttgart (hilly)", C["orange"])]:
        aug = res["tradeoff"]          # true N-1-sized re-costing
        prem = [a["cost_premium_pct"] for a in aug]
        eud = [a["eud_reduction_pct"] for a in aug]
        n1 = [100 * a["n1_served_fraction"] for a in aug]
        axes[0].plot(prem, eud, "-o", color=col, label=lab, ms=6,
                     markeredgecolor="white", markeredgewidth=1.2)
        axes[1].plot(prem, n1, "-o", color=col, label=lab, ms=6,
                     markeredgecolor="white", markeredgewidth=1.2)
        for a in aug[1:]:
            axes[0].annotate(f"+{a['k']}", (a["cost_premium_pct"],
                                            a["eud_reduction_pct"]),
                             textcoords="offset points", xytext=(6, -9),
                             fontsize=7, color=INK2)
    axes[0].set_xlabel("total annual cost premium  [%]  (N-1 sized)")
    axes[0].set_ylabel("reduction in expected unserved demand  [%]")
    axes[0].set_title("Reliability bought per euro spent", color=INK)
    axes[1].set_xlabel("total annual cost premium  [%]  (N-1 sized)")
    axes[1].set_ylabel("demand served after worst single failure  [%]")
    axes[1].set_title("N-1 security", color=INK)
    for a in axes[:2]:
        a.legend(loc="lower right")
        despine(a)

    # percolation
    ax = axes[2]
    res, raw = hilly
    xy, dem_, M = raw["xy"], raw["demand"], raw["M"]
    et = raw["topo"]["MST-terrain"][0]
    n = len(xy)
    for edges, lab, col, ls in [(et, "MST-terrain", C["orange"], "-"),
                                (raw["aug_edges"], "MST-terrain+R", C["violet"], "-")]:
        f, s = ns.percolation(n, list(edges), dem_, mode="random", trials=40)
        ax.plot(100 * f, 100 * s, ls, color=col, label=f"{lab}, random")
        f2, s2 = ns.percolation(n, list(edges), dem_, mode="targeted")
        ax.plot(100 * f2, 100 * s2, "--", color=col, alpha=0.75,
                label=f"{lab}, targeted")
    ax.set_xlabel("pipes removed  [%]")
    ax.set_ylabel("demand still connected  [%]")
    ax.set_title("Percolation robustness", color=INK)
    ax.set_xlim(0, 25)
    ax.legend(loc="upper right", fontsize=7.2)
    despine(ax)
    fig.suptitle("Every tree edge is a bridge - what it costs to fix that",
                 fontsize=11.5, color=INK, y=1.03)
    fig.tight_layout()
    save(fig, "fig4_reliability")


def fig_algorithms():
    with open("results/tables/benchmark.json") as fh:
        b = json.load(fh)
    rows = b["rows"]
    n = np.array([r["n"] for r in rows], float)
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.4))
    ax = axes[0]
    for key, lab, col in [("kruskal_s", "Kruskal (union-find)", C["blue"]),
                          ("prim_s", "Prim (binary heap)", C["orange"]),
                          ("prim_dense_s", "Prim (dense array)", C["aqua"])]:
        t = np.array([r[key] for r in rows], float) * 1000
        ax.loglog(n, t, "-o", color=col, label=lab, ms=5.5,
                  markeredgecolor="white", markeredgewidth=1.1)
        ax.annotate(lab, (n[-1], t[-1]), textcoords="offset points",
                    xytext=(-4, 8), fontsize=7.4, color=col, ha="right")
    ax.set_xlabel("nodes V  (complete graph, E = V(V-1)/2)")
    ax.set_ylabel("runtime  [ms]")
    ax.set_title("MST algorithm scaling", color=INK)
    sc = b["scaling"]
    ax.text(0.03, 0.97,
            f"fitted t ~ V^a\n Kruskal a={sc['kruskal']:.2f}\n"
            f" Prim-heap a={sc['prim']:.2f}\n Prim-dense a={sc['prim_dense']:.2f}",
            transform=ax.transAxes, va="top", fontsize=7.6, color=INK2)
    despine(ax)

    ax = axes[1]
    frac = np.array([100 * r["kruskal_examined"] / r["n_edges"] for r in rows])
    ax.semilogx(n, frac, "-o", color=C["blue"], ms=5.5,
                markeredgecolor="white", markeredgewidth=1.1)
    for xi, yi in zip(n, frac):
        ax.annotate(f"{yi:.1f}%", (xi, yi), textcoords="offset points",
                    xytext=(0, 8), fontsize=7, ha="center", color=INK2)
    ax.set_xlabel("nodes V")
    ax.set_ylabel("edges Kruskal actually examines  [%]")
    ax.set_title("Why Kruskal beats heap-Prim here: early termination",
                 color=INK)
    despine(ax)
    fig.suptitle("Kruskal vs Prim on dense graphs - the dense array variant "
                 "wins decisively", fontsize=11.5, color=INK, y=1.03)
    fig.tight_layout()
    save(fig, "fig5_algorithms")


def fig_netsci(hilly):
    res, raw = hilly
    xy, dem_, M = raw["xy"], raw["demand"], raw["M"]
    n = len(xy)
    et = raw["topo"]["MST-terrain"][0]
    star = raw["topo"]["Star"][0]
    aug = raw["aug_edges"]

    fig, axes = plt.subplots(1, 4, figsize=(15.2, 4.0))

    # degree distribution vs random-tree null
    ax = axes[0]
    for edges, lab, col in [(star, "Star", C["magenta"]),
                            (et, "MST-terrain", C["orange"]),
                            (aug, "MST-terrain+R", C["violet"])]:
        d = np.zeros(n, int)
        for u, v in edges:
            d[u] += 1
            d[v] += 1
        vals, cnt = np.unique(d, return_counts=True)
        ax.plot(vals, cnt / n, "-o", color=col, label=lab, ms=5,
                markeredgecolor="white", markeredgewidth=1.0)
    nm = ns.null_model_comparison(n, list(et), trials=120)
    ax.set_xlabel("degree k")
    ax.set_ylabel("P(k)")
    ax.set_title("Degree distribution", color=INK)
    ax.legend(fontsize=7.2)
    ax.text(0.97, 0.62,
            f"degree variance vs\nrandom labelled tree:\n"
            f"{nm['degree_var_ratio_vs_random_tree']:.2f}x",
            transform=ax.transAxes, ha="right", fontsize=7.2, color=INK2)
    despine(ax)

    # betweenness map
    ax = axes[1]
    import networkx as nx
    g = nx.Graph()
    g.add_nodes_from(range(n))
    for u, v in et:
        g.add_edge(u, v, length=float(M["L3d"][u, v]))
    eb = nx.edge_betweenness_centrality(g, weight="length")
    vals = np.array([eb[e] if e in eb else eb[e[::-1]] for e in et])
    draw_network(ax, xy, et, dem=None, show_dem=False,
                 edge_color=[plt.cm.YlOrRd(0.25 + 0.75 * v / vals.max())
                             for v in vals],
                 edge_width=[1.0 + 4.5 * v / vals.max() for v in vals])
    ax.set_title("Edge betweenness\n(critical pipes)", color=INK)

    # algebraic connectivity
    ax = axes[2]
    labs, l2, brg = [], [], []
    for edges, lab in [(star, "Star"), (raw["topo"]["MST-2D"][0], "MST-2D"),
                       (et, "MST-terr"), (aug, "MST-terr+R")]:
        labs.append(lab)
        l2.append(ns.algebraic_connectivity(n, list(edges), M["L3d"]))
        brg.append(ns.connectivity_report(n, list(edges))["n_bridges"])
    x = np.arange(len(labs))
    ax.bar(x, np.array(l2) * 1e5, color=C["blue"], width=0.6,
           edgecolor="#fcfcfb", linewidth=2)
    for xi, v in zip(x, np.array(l2) * 1e5):
        ax.text(xi, v, f"{v:.2f}", ha="center", va="bottom", fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labs, rotation=18, ha="right")
    ax.set_ylabel(r"algebraic connectivity $\lambda_2$  [$\times 10^{-5}$]")
    ax.set_title("Spectral robustness", color=INK)
    despine(ax)
    ax.grid(axis="x", visible=False)

    # bridges
    ax = axes[3]
    ax.bar(x, brg, color=C["red"], width=0.6, edgecolor="#fcfcfb", linewidth=2)
    for xi, v in zip(x, brg):
        ax.text(xi, v, str(v), ha="center", va="bottom", fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labs, rotation=18, ha="right")
    ax.set_ylabel("number of bridges")
    ax.set_title("Single points of failure", color=INK)
    despine(ax)
    ax.grid(axis="x", visible=False)

    fig.suptitle("Graph-theoretic characterisation of the real Stuttgart "
                 "network", fontsize=11.5, color=INK, y=1.04)
    fig.tight_layout()
    save(fig, "fig6_network_science")


def fig_transport():
    """Transport phenomena: momentum, heat, mass."""
    import hydraulics as hyd
    import thermal as th
    from masstransfer import O2_SCENARIOS, corrosion_rate
    from params import DN_CATALOGUE, WATER

    fig, axes = plt.subplots(1, 4, figsize=(15.4, 4.0))

    # Moody: friction factor vs Re
    ax = axes[0]
    Re = np.logspace(3, 7, 300)
    for D, col in [(0.05, C["blue"]), (0.2, C["orange"]), (0.6, C["aqua"])]:
        f = [hyd.friction_factor(r, D) for r in Re]
        ax.loglog(Re, f, color=col, label=f"D = {D*1000:.0f} mm")
    ax.axvline(2300, color=INK3, lw=1, ls=":")
    ax.text(2400, 0.06, "laminar |  turbulent", fontsize=7, color=INK2)
    ax.axhline(0.015, color=C["red"], lw=1.4, ls="--")
    ax.text(1.2e3, 0.0158, "Gao et al. assume $\\sigma$ = 0.015 (constant)",
            fontsize=7.2, color=C["red"])
    ax.set_xlabel("Reynolds number")
    ax.set_ylabel("Darcy friction factor f")
    ax.set_title("Momentum: Colebrook-White\nvs a constant friction factor",
                 color=INK)
    ax.legend(fontsize=7.2)
    despine(ax)

    # heat loss vs DN
    ax = axes[1]
    dn = [c[0] for c in DN_CATALOGUE]
    q = [th.heat_loss_buried(th.BuriedPipe(c[1], c[2], c[3]), 110, 50)
         for c in DN_CATALOGUE]
    qs = [th.heat_loss_buried(th.BuriedPipe(c[1], c[2], c[3]), 90, 45)
          for c in DN_CATALOGUE]
    ax.plot(dn, q, "-o", color=C["orange"], ms=4, label="110 / 50 degC")
    ax.plot(dn, qs, "-o", color=C["aqua"], ms=4, label="90 / 45 degC (4GDH)")
    ax.set_xscale("log")
    ax.set_xlabel("nominal diameter DN")
    ax.set_ylabel("heat loss  [W per trench metre]")
    ax.set_title("Heat: buried twin-pipe loss\n(EN 253, soil shape factor)",
                 color=INK)
    ax.legend(fontsize=7.2)
    despine(ax)

    # corrosion vs DN and O2
    ax = axes[2]
    for name, col in [("well_deaerated", C["aqua"]),
                      ("poor_deaeration", C["orange"]),
                      ("air_saturated", C["red"])]:
        c = O2_SCENARIOS[name]
        y = [corrosion_rate(2.0, cc[1], c).years_to_perforate
             for cc in DN_CATALOGUE]
        ax.plot(dn, y, "-o", color=col, ms=4,
                label=f"{name.replace('_',' ')} ({c*1e6:.0f} ppb)")
    ax.axhspan(0, 30, color=C["red"], alpha=0.07)
    ax.text(25, 14, "below DH design life", fontsize=7, color=C["red"])
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("nominal diameter DN")
    ax.set_ylabel("years to wall perforation")
    ax.set_title("Mass: O$_2$-limited corrosion\n(Linton-Sherwood)", color=INK)
    ax.legend(fontsize=6.8, loc="lower right")
    despine(ax)

    # static pressure vs relief
    ax = axes[3]
    relief = np.linspace(0, 350, 300)
    p = (WATER.p_sat_supply + 0.5e5 + WATER.rho * 9.80665 * relief) / 1e5
    ax.plot(relief, p, color=C["blue"], lw=2.4)
    ax.axhline(16, color=C["red"], lw=1.6, ls="--")
    ax.text(5, 16.4, "PN16 pipe pressure class", fontsize=7.4, color=C["red"])
    ax.axvline(8, color=C["aqua"], lw=1.4)
    ax.text(12, 3, "Bremen\n8 m", fontsize=7.4, color=C["aqua"])
    ax.axvline(282, color=C["orange"], lw=1.4)
    ax.text(232, 3, "Stuttgart\n282 m", fontsize=7.4, color=C["orange"])
    crit = (16e5 - WATER.p_sat_supply - 0.5e5) / (WATER.rho * 9.80665)
    ax.axvline(crit, color=INK3, lw=1, ls=":")
    ax.text(crit + 4, 21, f"single-zone limit\n{crit:.0f} m", fontsize=7.2,
            color=INK2)
    ax.set_xlabel("network relief  [m]")
    ax.set_ylabel("static pressure at the low point  [bar]")
    ax.set_title("Why hills force pressure zones", color=INK)
    despine(ax)

    fig.suptitle("Transport phenomena upgrades over the reference model: "
                 "momentum, heat and mass",
                 fontsize=11.5, color=INK, y=1.04)
    fig.tight_layout()
    save(fig, "fig7_transport_phenomena")


def fig_zones(hilly):
    """Spectral bisection choosing the pressure zones."""
    from params import EURO, WATER

    res, raw = hilly
    xy, dem = raw["xy"], raw["dem"]
    et = raw["topo"]["MST-terrain"][0]
    n = len(xy)
    z = np.asarray(dem.elevation(xy[:, 0], xy[:, 1]), float)
    labels, nz, cut = ns.spectral_pressure_zones(
        n, list(et), z, WATER.rho, 9.80665, EURO.PN_rating,
        WATER.p_sat_supply + EURO.p_cavitation_margin)

    fig, axes = plt.subplots(1, 3, figsize=(12.6, 4.4))
    ax = axes[0]
    draw_network(ax, xy, et, dem=dem, edge_width=[1.6] * len(et),
                 edge_color=[INK2] * len(et))
    for zi in range(nz):
        m = labels == zi
        ax.scatter(xy[m, 0], xy[m, 1], s=42, color=SERIES[zi % 8],
                   edgecolors="white", linewidths=1.0, zorder=7,
                   label=f"zone {zi+1}")
    ax.legend(fontsize=7.2, loc="lower right")
    ax.set_title(f"Spectral bisection -> {nz} pressure zones\n"
                 f"({cut} pipes cross a zone boundary)", color=INK)
    scalebar(ax, xy, 2000)

    ax = axes[1]
    fv = ns.fiedler_vector(n, list(et), None)
    order = np.argsort(fv)
    ax.plot(np.arange(n), fv[order], "-o", color=C["blue"], ms=4,
            markeredgecolor="white", markeredgewidth=1.0)
    ax.axhline(np.median(fv), color=C["red"], ls="--", lw=1.4)
    ax.text(1, np.median(fv), " median = bisection cut", fontsize=7.2,
            color=C["red"], va="bottom")
    ax.set_xlabel("nodes, sorted by Fiedler component")
    ax.set_ylabel("Fiedler vector $v_2$")
    ax.set_title("The Fiedler vector splits the graph", color=INK)
    despine(ax)

    ax = axes[2]
    for zi in range(nz):
        m = labels == zi
        ax.scatter(np.full(m.sum(), zi), z[m], s=28, color=SERIES[zi % 8],
                   edgecolors="white", linewidths=0.8)
        if m.sum():
            ax.plot([zi - 0.28, zi + 0.28], [z[m].min()] * 2, color=INK2, lw=1)
            ax.plot([zi - 0.28, zi + 0.28], [z[m].max()] * 2, color=INK2, lw=1)
            ax.text(zi, z[m].max() + 4, f"{z[m].max()-z[m].min():.0f} m",
                    ha="center", fontsize=7.4, color=INK)
    usable = (EURO.PN_rating - WATER.p_sat_supply - EURO.p_cavitation_margin)
    ax.text(0.02, 0.02,
            f"max relief one zone can hold:\n"
            f"{usable/(WATER.rho*9.80665):.0f} m",
            transform=ax.transAxes, fontsize=7.4, color=INK2)
    ax.set_xticks(range(nz))
    ax.set_xticklabels([f"zone {i+1}" for i in range(nz)])
    ax.set_ylabel("node elevation  [m a.s.l.]")
    ax.set_title("Relief within each zone", color=INK)
    despine(ax)
    ax.grid(axis="x", visible=False)

    fig.suptitle("Spectral bisection as a hydraulic design tool: "
                 "partitioning a hilly network into feasible pressure zones",
                 fontsize=11.5, color=INK, y=1.03)
    fig.tight_layout()
    save(fig, "fig8_pressure_zones")


def fig_gao():
    with open("results/tables/insulation_model_selection.json") as fh:
        ms = json.load(fh)
    from params import GAO_TABLE2

    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.4))
    keys = ["pipe_1e7", "pressure_1e7", "heat_1e7", "total_1e7"]
    klab = ["pipe\ncapital", "pressure\ndrop", "heat\nloss", "TOTAL"]

    ax = axes[0]
    x = np.arange(len(keys))
    pap = [GAO_TABLE2[k]["MST"] for k in keys]
    our = [ms["en_scaling"]["mst"][k] for k in keys]
    ax.bar(x - 0.2, pap, 0.38, color=C["blue"], label="Gao et al. Table 2",
           edgecolor="#fcfcfb", linewidth=2)
    ax.bar(x + 0.2, our, 0.38, color=C["orange"], label="our implementation",
           edgecolor="#fcfcfb", linewidth=2)
    for xi, (a, b) in enumerate(zip(pap, our)):
        ax.text(xi - 0.2, a, f"{a:.3f}", ha="center", va="bottom", fontsize=7)
        ax.text(xi + 0.2, b, f"{b:.3f}", ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(klab)
    ax.set_ylabel(r"cost  [$\times 10^7$ CNY/y]")
    ax.set_title("MST column - calibrated (3 parameters)", color=INK)
    ax.legend(fontsize=7.4)
    despine(ax)
    ax.grid(axis="x", visible=False)

    ax = axes[1]
    w = 0.26
    for i, (mode, col) in enumerate([("constant", C["blue"]),
                                     ("en_scaling", C["orange"]),
                                     ("proportional", C["aqua"])]):
        err = [ms[mode]["err"][k] for k in keys]
        ax.bar(x + (i - 1) * w, err, w, color=col,
               label=mode.replace("_", " "), edgecolor="#fcfcfb", linewidth=1.6)
    ax.axhline(0, color=INK2, lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels(klab)
    ax.set_ylabel("error vs published Star column  [%]")
    ax.set_title("Star column - HELD OUT, never calibrated", color=INK)
    ax.legend(fontsize=7.2, title="insulation model", title_fontsize=7.2)
    despine(ax)
    ax.grid(axis="x", visible=False)
    fig.suptitle("Reproducing Gao et al. (2020): the MST column fits, "
                 "the held-out Star column does not",
                 fontsize=11.5, color=INK, y=1.03)
    fig.tight_layout()
    save(fig, "fig9_gao_reproduction")


if __name__ == "__main__":
    os.makedirs(FIG, exist_ok=True)
    flat = load("flat")
    hilly = load("hilly")
    print("building figures ...")
    fig_networks(flat, hilly)
    fig_costs(flat, hilly)
    fig_terrain(hilly)
    fig_reliability(flat, hilly)
    fig_algorithms()
    fig_netsci(hilly)
    fig_transport()
    fig_zones(hilly)
    fig_gao()
    print("done.")
