"""
dataset.py - Load the AixDHN real district-heating dataset and reduce a
chosen district to a tractable node set for network optimisation.

Source
------
RWTH Aachen EBC, "AixDHN: District Heating Networks Dataset from Clustered
Census Data", https://github.com/RWTH-EBC/AixDHN  (MIT licence).

What the dataset actually contains (verified, not assumed): polygons of
*presumed* DH network extents per German municipality, the annual private-
household DH demand of each [MWh/y], and `DH_cells` - the list of 100 m
census-grid cell coordinates (EPSG:3035) that make up the network area.

It contains NO pipes, no per-node demand and no diameters.  We therefore
build the node set ourselves by clustering the real census cells into
substation groups, which is exactly how a DH network is laid out in
practice (one substation serves a block of buildings).
"""
from __future__ import annotations
import json
import glob
import os
from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import KMeans

CELL_M = 100.0  # census grid resolution [m]


@dataclass
class District:
    """One real AixDHN district-heating area."""

    ident: str
    name: str
    state: str
    area_km2: float
    dh_demand_MWh: float          # annual household DH demand [MWh/y]
    households: int
    cells: np.ndarray             # (n_cells, 2) EPSG:3035 [m]

    @property
    def n_cells(self) -> int:
        return len(self.cells)

    @property
    def extent_m(self) -> float:
        """Largest side of the bounding box [m]."""
        return float(max(np.ptp(self.cells[:, 0]), np.ptp(self.cells[:, 1])))


def load_state(path: str) -> list[District]:
    """Load every district in one AixDHN state GeoJSON."""
    with open(path, encoding="utf-8") as fh:
        gj = json.load(fh)
    out = []
    for feat in gj["features"]:
        p = feat["properties"]
        raw = p["DH_cells"]
        cells = json.loads(raw) if isinstance(raw, str) else raw
        out.append(
            District(
                ident=p["ID"],
                name=p["GEN"],
                state=p["LAN"],
                area_km2=float(p["area"]),
                dh_demand_MWh=float(p["DH_demand"]),
                households=int(p["DH_supplied_households"] or 0),
                cells=np.asarray(cells, dtype=float),
            )
        )
    return out


def load_all(data_dir: str = "data/aixdhn") -> list[District]:
    ds = []
    for f in sorted(glob.glob(os.path.join(data_dir, "heatgrids_*.geojson"))):
        ds.extend(load_state(f))
    return ds


# ------------------------------------------------------------------ node reduction
@dataclass
class NodeSet:
    """Substation nodes derived from a real district, plus the energy hub.

    Node 0 is always the energy hub (the plant); nodes 1..n are consumer
    substations.  `demand_kW` is the design (peak) thermal load.
    """

    district: District
    xy: np.ndarray                 # (n+1, 2) EPSG:3035 [m], row 0 = hub
    demand_kW: np.ndarray          # (n+1,)  [kW], entry 0 = -sum (supply)
    cell_counts: np.ndarray        # (n+1,)  census cells behind each node
    z: np.ndarray | None = None    # (n+1,) elevation [m a.s.l.], filled later
    latlon: np.ndarray | None = None

    @property
    def n_users(self) -> int:
        return len(self.xy) - 1


def build_nodes(
    district: District,
    n_users: int = 40,
    full_load_hours: float = 2000.0,
    hub: str = "medoid",
    seed: int = 42,
) -> NodeSet:
    """Cluster real census cells into `n_users` substations.

    Demand allocation: the dataset gives one aggregate annual demand for the
    whole district, so it is split between substations in proportion to the
    number of census cells each one serves (cells are equal-area and are the
    finest resolution the data supports).  Annual energy is converted to a
    design thermal load with an annual full-load-hours factor, the standard
    DH sizing convention (Frederiksen & Werner, *District Heating and
    Cooling*, 2013): P_design = E_annual / t_full_load.

    hub : "medoid"   -> plant at the census cell closest to the demand centroid
          "centroid" -> plant at the geometric centroid
    """
    km = KMeans(n_clusters=n_users, n_init=10, random_state=seed).fit(district.cells)
    centres = km.cluster_centers_
    counts = np.bincount(km.labels_, minlength=n_users).astype(float)

    share = counts / counts.sum()
    energy_MWh = district.dh_demand_MWh * share
    load_kW = energy_MWh * 1000.0 / full_load_hours

    if hub == "medoid":
        c = district.cells.mean(axis=0)
        hub_xy = district.cells[np.argmin(((district.cells - c) ** 2).sum(1))]
    else:
        hub_xy = district.cells.mean(axis=0)

    xy = np.vstack([hub_xy, centres])
    dem = np.concatenate([[-load_kW.sum()], load_kW])
    cnt = np.concatenate([[0.0], counts])
    return NodeSet(district=district, xy=xy, demand_kW=dem, cell_counts=cnt)
