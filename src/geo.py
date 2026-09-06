"""
geo.py - Coordinate transforms and real terrain acquisition.

EPSG:3035 (ETRS89-extended / LAEA Europe) is the CRS used by the AixDHN
dataset.  `pyproj` is not available in this environment, so the inverse
Lambert Azimuthal Equal-Area projection is implemented directly from
Snyder (1987), "Map Projections - A Working Manual", USGS PP 1395, eqs 3-12,
24-16..24-20.  Verified against known control points in tests/test_geo.py.

Elevations come from the public OpenTopoData API serving NASA SRTM 30 m
(SRTMGL1 v3), the standard open global DEM.
"""
from __future__ import annotations
import json
import math
import time
import urllib.request
from dataclasses import dataclass

# ---------------------------------------------------------------- GRS80 / EPSG:3035
_A = 6378137.0                    # GRS80 semi-major axis [m]
_F = 1.0 / 298.257222101          # GRS80 flattening [-]
_E2 = 2 * _F - _F * _F            # first eccentricity squared [-]
_E = math.sqrt(_E2)
_LAT0 = math.radians(52.0)        # projection origin latitude
_LON0 = math.radians(10.0)        # projection origin longitude
_FE, _FN = 4321000.0, 3210000.0   # false easting / northing [m]


def _q(phi: float) -> float:
    """Snyder eq. 3-12: authalic latitude helper q(phi)."""
    s = math.sin(phi)
    return (1 - _E2) * (
        s / (1 - _E2 * s * s)
        - (1 / (2 * _E)) * math.log((1 - _E * s) / (1 + _E * s))
    )


_QP = _q(math.pi / 2)
_Q0 = _q(_LAT0)
_BETA0 = math.asin(_Q0 / _QP)
_RQ = _A * math.sqrt(_QP / 2)
_D = (_A * math.cos(_LAT0)) / (
    math.sqrt(1 - _E2 * math.sin(_LAT0) ** 2) * _RQ * math.cos(_BETA0)
)


def laea3035_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """EPSG:3035 (x_east, y_north) [m] -> (lat, lon) in degrees."""
    xp = (x - _FE) / _D
    yp = _D * (y - _FN)
    rho = math.hypot(xp, yp)
    if rho < 1e-9:
        return math.degrees(_LAT0), math.degrees(_LON0)
    c = 2 * math.asin(rho / (2 * _RQ))
    sin_c, cos_c = math.sin(c), math.cos(c)
    beta = math.asin(cos_c * math.sin(_BETA0) + (yp * sin_c * math.cos(_BETA0) / rho))
    lon = _LON0 + math.atan2(
        xp * sin_c,
        _D * rho * math.cos(_BETA0) * cos_c - _D * yp * math.sin(_BETA0) * sin_c,
    )
    # authalic -> geodetic latitude, Snyder eq. 3-18 series
    e4, e6 = _E2 * _E2, _E2 * _E2 * _E2  # e^4, e^6
    lat = (
        beta
        + (_E2 / 3 + 31 * e4 / 180 + 517 * e6 / 5040) * math.sin(2 * beta)
        + (23 * e4 / 360 + 251 * e6 / 3780) * math.sin(4 * beta)
        + (761 * e6 / 45360) * math.sin(6 * beta)
    )
    return math.degrees(lat), math.degrees(lon)


# ---------------------------------------------------------------- SRTM elevation
_OPENTOPO = "https://api.opentopodata.org/v1/srtm30m"


def fetch_elevations(latlons, batch: int = 100, pause: float = 1.05, retries: int = 3):
    """Fetch SRTM 30 m elevations [m a.s.l.] for a list of (lat, lon).

    OpenTopoData's free tier allows 100 locations/request and 1 call/s, so
    requests are batched and throttled.  Returns a list of floats.
    """
    out: list[float] = []
    for i in range(0, len(latlons), batch):
        chunk = latlons[i : i + batch]
        q = "|".join(f"{la:.6f},{lo:.6f}" for la, lo in chunk)
        url = f"{_OPENTOPO}?locations={q}"
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    js = json.loads(r.read().decode())
                if js.get("status") != "OK":
                    raise RuntimeError(js.get("error", "unknown"))
                out.extend(
                    (p["elevation"] if p["elevation"] is not None else 0.0)
                    for p in js["results"]
                )
                break
            except Exception as exc:  # noqa: BLE001 - network is best-effort
                if attempt == retries - 1:
                    raise
                time.sleep(2.0 * (attempt + 1))
        time.sleep(pause)
    return out
