"""
dem.py - Download and cache a real digital elevation model (DEM) raster over
a district, and sample it along arbitrary pipe routes.

Elevation source: NASA SRTM 30 m (SRTMGL1 v3) via the OpenTopoData API.
The raster is built on a regular EPSG:3035 grid so that sampling a straight
pipe route is a simple bilinear interpolation in projected metres.
"""
from __future__ import annotations
import os
import pickle
from dataclasses import dataclass

import numpy as np

from geo import laea3035_to_wgs84, fetch_elevations


@dataclass
class DEM:
    """Regular EPSG:3035 elevation grid."""

    x0: float
    y0: float
    step: float
    grid: np.ndarray  # (ny, nx) elevation [m a.s.l.], grid[j, i] at (x0+i*step, y0+j*step)

    @property
    def shape(self):
        return self.grid.shape

    def elevation(self, x, y):
        """Bilinear-interpolated elevation [m] at EPSG:3035 (x, y). Vectorised."""
        x = np.atleast_1d(np.asarray(x, dtype=float))
        y = np.atleast_1d(np.asarray(y, dtype=float))
        ny, nx = self.grid.shape
        fi = np.clip((x - self.x0) / self.step, 0, nx - 1.0001)
        fj = np.clip((y - self.y0) / self.step, 0, ny - 1.0001)
        i0, j0 = fi.astype(int), fj.astype(int)
        tx, ty = fi - i0, fj - j0
        g = self.grid
        v = (
            g[j0, i0] * (1 - tx) * (1 - ty)
            + g[j0, i0 + 1] * tx * (1 - ty)
            + g[j0 + 1, i0] * (1 - tx) * ty
            + g[j0 + 1, i0 + 1] * tx * ty
        )
        return v

    def profile(self, p, q, ds: float = 25.0):
        """Elevation profile along the straight line p->q, sampled every `ds` m.

        Returns (s, z) where s is horizontal chainage [m] and z elevation [m].
        A 25 m default matches the paper's own elbow spacing assumption and
        is finer than the 30 m native SRTM posting.
        """
        p = np.asarray(p, float)
        q = np.asarray(q, float)
        L = float(np.hypot(*(q - p)))
        n = max(2, int(np.ceil(L / ds)) + 1)
        t = np.linspace(0.0, 1.0, n)
        pts = p[None, :] + t[:, None] * (q - p)[None, :]
        return t * L, self.elevation(pts[:, 0], pts[:, 1])


def build_dem(cells: np.ndarray, step: float = 100.0, margin: float = 500.0,
              cache: str | None = None, verbose: bool = True) -> DEM:
    """Fetch (or load) a DEM covering the bounding box of `cells`."""
    if cache and os.path.exists(cache):
        with open(cache, "rb") as fh:
            return pickle.load(fh)

    x0 = float(cells[:, 0].min() - margin)
    x1 = float(cells[:, 0].max() + margin)
    y0 = float(cells[:, 1].min() - margin)
    y1 = float(cells[:, 1].max() + margin)
    nx = int(np.ceil((x1 - x0) / step)) + 1
    ny = int(np.ceil((y1 - y0) / step)) + 1

    xs = x0 + step * np.arange(nx)
    ys = y0 + step * np.arange(ny)
    XX, YY = np.meshgrid(xs, ys)
    flat = np.column_stack([XX.ravel(), YY.ravel()])
    if verbose:
        print(f"  DEM grid {nx} x {ny} = {len(flat)} points "
              f"({len(flat)//100 + 1} API calls, ~{len(flat)//100//60 + 1} min)")

    latlon = [laea3035_to_wgs84(px, py) for px, py in flat]
    z = np.asarray(fetch_elevations(latlon), dtype=float).reshape(ny, nx)

    dem = DEM(x0=x0, y0=y0, step=step, grid=z)
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, "wb") as fh:
            pickle.dump(dem, fh)
    return dem
