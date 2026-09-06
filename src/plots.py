"""
plots.py - Shared figure styling and drawing primitives.

Palette: validated categorical set (adjacent-pair CVD dE 9.1, normal-vision
22.9 on the light surface). Contrast for the aqua/yellow slots is below 3:1,
so every chart that uses them carries visible direct labels, which is the
required relief.
"""
from __future__ import annotations

import matplotlib as mpl
import numpy as np

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

# --- validated categorical palette (light mode) -------------------------
C = {
    "blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a",
    "yellow": "#eda100", "magenta": "#e87ba4", "green": "#008300",
    "violet": "#4a3aa7", "red": "#e34948",
}
SERIES = [C["blue"], C["orange"], C["aqua"], C["yellow"],
          C["magenta"], C["green"], C["violet"], C["red"]]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
INK3 = "#8a8880"
GRID = "#e3e2dd"

TOPO_COLOR = {
    "Star": C["magenta"], "MST-2D": C["blue"], "MST-terrain": C["orange"],
    "ESMT": C["aqua"], "RSMT": C["yellow"], "MST-terrain+R": C["violet"],
}
COST_COLOR = {
    "capital": C["blue"], "pumping": C["orange"],
    "heat_loss": C["aqua"], "zones": C["yellow"],
}


def apply_style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 10.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 9,
        "axes.labelcolor": INK2,
        "axes.edgecolor": GRID,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.7,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.frameon": False,
        "legend.fontsize": 8,
        "text.color": INK,
        "lines.linewidth": 2.0,
        "lines.solid_capstyle": "round",
    })


def despine(ax, keep=("left", "bottom")):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(s in keep)


def hillshade(z, dx=100.0, azdeg=315.0, altdeg=45.0):
    """Simple analytical hillshade for a DEM background."""
    gy, gx = np.gradient(z, dx, dx)
    slope = np.pi / 2 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az = np.radians(360.0 - azdeg + 90.0)
    alt = np.radians(altdeg)
    sh = (np.sin(alt) * np.sin(slope)
          + np.cos(alt) * np.cos(slope) * np.cos(az - aspect))
    return np.clip(sh, 0, 1)


def draw_network(ax, xy, edges, dem=None, node_size=None, edge_width=None,
                 edge_color=None, hub=0, title="", show_dem=True,
                 cmap="terrain", steiner_from=None):
    """Draw a pipe network over its real terrain."""
    if dem is not None and show_dem:
        ny, nx_ = dem.grid.shape
        ext = [dem.x0, dem.x0 + dem.step * (nx_ - 1),
               dem.y0, dem.y0 + dem.step * (ny - 1)]
        ax.imshow(dem.grid, extent=ext, origin="lower", cmap=cmap,
                  alpha=0.55, interpolation="bilinear", zorder=0)
        ax.imshow(hillshade(dem.grid, dem.step), extent=ext, origin="lower",
                  cmap="gray", alpha=0.28, interpolation="bilinear", zorder=1)

    ew = edge_width if edge_width is not None else [1.8] * len(edges)
    ec = edge_color if edge_color is not None else [C["blue"]] * len(edges)
    for (u, v), w, c in zip(edges, ew, ec):
        ax.plot([xy[u, 0], xy[v, 0]], [xy[u, 1], xy[v, 1]],
                color=c, lw=w, solid_capstyle="round", zorder=3)

    ns = node_size if node_size is not None else np.full(len(xy), 14.0)
    if steiner_from is not None and steiner_from < len(xy):
        ax.scatter(xy[steiner_from:, 0], xy[steiner_from:, 1], s=10,
                   marker="s", c="none", edgecolors=INK, linewidths=0.8,
                   zorder=4, label="Steiner point")
        term = slice(0, steiner_from)
    else:
        term = slice(0, len(xy))
    ax.scatter(xy[term][1:, 0], xy[term][1:, 1], s=ns[term][1:],
               c="white", edgecolors=INK2, linewidths=0.7, zorder=5)
    ax.scatter([xy[hub, 0]], [xy[hub, 1]], s=140, marker="*",
               c=C["red"], edgecolors="white", linewidths=1.0, zorder=6)

    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    despine(ax, keep=())
    if title:
        ax.set_title(title, color=INK, pad=6)


def scalebar(ax, xy, length_m=1000, label=None):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x0 + 0.06 * (x1 - x0)
    y = y0 + 0.07 * (y1 - y0)
    ax.plot([x, x + length_m], [y, y], color=INK, lw=2.5, solid_capstyle="butt",
            zorder=8)
    ax.text(x + length_m / 2, y + 0.018 * (y1 - y0),
            label or f"{length_m/1000:g} km", ha="center", va="bottom",
            fontsize=7.5, color=INK)


def dn_widths(per_edge, edges, lo=0.9, hi=5.0):
    """Line width proportional to nominal diameter, like the paper's Fig 1."""
    dn = np.array([per_edge[e]["dn"] for e in edges], dtype=float)
    if dn.max() == dn.min():
        return np.full(len(edges), (lo + hi) / 2)
    t = (dn - dn.min()) / (dn.max() - dn.min())
    return lo + (hi - lo) * np.sqrt(t)


def legend_swatches(ax, labels, colors, loc="upper left", **kw):
    handles = [Line2D([0], [0], color=c, lw=3, solid_capstyle="round")
               for c in colors]
    ax.legend(handles, labels, loc=loc, **kw)


def label_bars(ax, xs, ys, fmt="{:.1f}", dy=0.01, fontsize=7.5, color=INK):
    span = ax.get_ylim()[1] - ax.get_ylim()[0]
    for x, y in zip(xs, ys):
        ax.text(x, y + dy * span, fmt.format(y), ha="center", va="bottom",
                fontsize=fontsize, color=color)
