"""
terrain.py - Terrain-aware pipe route costing.

Gao et al. weight every candidate pipe by straight-line Euclidean distance.
That is only correct on flat ground. On real terrain three things change:

  1. The pipe is longer than the map distance: a route climbing dz over a
     horizontal run dx has true length sqrt(dx^2 + dz^2).
  2. Trenching on a slope costs more per metre - benching, anchor blocks,
     reduced plant productivity, and rock rather than soil excavation.
  3. Some ground is simply not trenchable, so a route crossing it is
     infeasible however short it looks on a map.

This module turns a real DEM into an edge-weight matrix capturing all three,
so the same Kruskal/Prim machinery can be run on a cost that means something
physically. Everything is computed by sampling the real SRTM profile along
each candidate route.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dem import DEM
from params import TerrainParams


@dataclass
class RouteMetrics:
    """Everything we know about one candidate pipe route."""

    L2d: float          # horizontal (map) length [m]
    L3d: float          # true slope length [m]
    cost_weight: float  # terrain-weighted construction length [m-equivalent]
    dz: float           # net elevation change end-to-end [m]
    climb: float        # total uphill climb along the route [m]
    max_slope: float    # steepest local gradient [-]
    mean_slope: float   # length-weighted mean gradient [-]
    feasible: bool      # False if any segment exceeds max trenchable slope


class TerrainCost:
    """Compute route metrics on a real DEM."""

    def __init__(self, dem: DEM, params: TerrainParams | None = None,
                 ds: float = 25.0):
        self.dem = dem
        self.p = params or TerrainParams()
        self.ds = ds

    # ---------------------------------------------------------------- core
    def slope_factor(self, s: np.ndarray) -> np.ndarray:
        """Trenching cost multiplier f(s) = 1 + a1 s + a2 s^2, plus rock.

        s is the ground gradient tan(theta). The quadratic is fitted to
        published pipeline terrain cost classes (flat 1.0, rolling ~1.6 at
        15 deg, mountainous ~3.0 at 30 deg). Above `rock_slope` the ground is
        assumed to require rock excavation, adding a further factor.
        """
        s = np.abs(s)
        f = 1.0 + self.p.a1 * s + self.p.a2 * s * s
        f = np.where(s > self.p.rock_slope, f * self.p.rock_factor, f)
        return f

    def route(self, p, q) -> RouteMetrics:
        """Metrics for a straight route between two EPSG:3035 points."""
        s, z = self.dem.profile(p, q, ds=self.ds)
        if len(s) < 2:
            return RouteMetrics(0, 0, 0, 0, 0, 0, 0, True)
        dh = np.diff(s)                       # horizontal step lengths
        dv = np.diff(z)                       # vertical steps
        seg3d = np.hypot(dh, dv)
        with np.errstate(divide="ignore", invalid="ignore"):
            grad = np.where(dh > 0, np.abs(dv) / dh, 0.0)

        L2d = float(s[-1])
        L3d = float(seg3d.sum())
        w = float((seg3d * self.slope_factor(grad)).sum())
        climb = float(np.clip(dv, 0, None).sum())
        mean_slope = float((grad * seg3d).sum() / max(seg3d.sum(), 1e-9))
        return RouteMetrics(
            L2d=L2d,
            L3d=L3d,
            cost_weight=w,
            dz=float(z[-1] - z[0]),
            climb=climb,
            max_slope=float(grad.max()),
            mean_slope=mean_slope,
            feasible=bool(grad.max() <= self.p.max_slope),
        )

    # ---------------------------------------------------------------- matrices
    def matrices(self, xy: np.ndarray, verbose: bool = False) -> dict:
        """All pairwise route metrics for a node set.

        Returns a dict of (n, n) symmetric matrices:
            L2d, L3d, W (terrain cost weight), climb, max_slope, feasible
        Infeasible routes get an infinite cost weight so the MST avoids them
        while remaining a well-defined problem.
        """
        n = len(xy)
        L2d = np.zeros((n, n))
        L3d = np.zeros((n, n))
        W = np.zeros((n, n))
        climb = np.zeros((n, n))
        mslope = np.zeros((n, n))
        feas = np.ones((n, n), dtype=bool)
        for i in range(n):
            for j in range(i + 1, n):
                r = self.route(xy[i], xy[j])
                L2d[i, j] = L2d[j, i] = r.L2d
                L3d[i, j] = L3d[j, i] = r.L3d
                climb[i, j] = climb[j, i] = r.climb
                mslope[i, j] = mslope[j, i] = r.max_slope
                feas[i, j] = feas[j, i] = r.feasible
                W[i, j] = W[j, i] = r.cost_weight if r.feasible else np.inf
            if verbose and i % 10 == 0:
                print(f"    routes {i}/{n}")
        np.fill_diagonal(W, 0.0)
        return {
            "L2d": L2d, "L3d": L3d, "W": W,
            "climb": climb, "max_slope": mslope, "feasible": feas,
        }


def node_elevations(dem: DEM, xy: np.ndarray) -> np.ndarray:
    """Elevation [m a.s.l.] at each node."""
    return np.asarray(dem.elevation(xy[:, 0], xy[:, 1]), dtype=float)


def relief_stats(z: np.ndarray) -> dict:
    z = np.asarray(z, float)
    return {
        "z_min": float(z.min()),
        "z_max": float(z.max()),
        "relief_m": float(z.max() - z.min()),
        "z_std": float(z.std()),
    }
