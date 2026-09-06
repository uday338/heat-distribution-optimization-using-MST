"""Download the real SRTM DEM rasters for the two study districts (run once)."""
import sys, time
sys.path.insert(0, "src")
from dataset import load_all
from dem import build_dem

STUDY = {"flat": "Bremen_040110000_c1", "hilly": "Stuttgart_081110000_c11"}

if __name__ == "__main__":
    ds = {d.ident: d for d in load_all()}
    for tag, ident in STUDY.items():
        d = ds[ident]
        t = time.time()
        print(f"[{tag}] {ident}  {d.n_cells} cells, extent {d.extent_m/1000:.1f} km")
        dem = build_dem(d.cells, step=100.0, cache=f"data/dem/{ident}.pkl")
        print(f"[{tag}] done in {time.time()-t:.0f}s  relief "
              f"{dem.grid.min():.0f}..{dem.grid.max():.0f} m "
              f"(range {dem.grid.max()-dem.grid.min():.0f} m)")
