"""
SAR-Watch step 1: read two NISAR L2 GCOV files, crop to Mount Rainier,
speckle-filter, convert to dB, and compute the change map.

Usage (local files):
    python sar_process.py BEFORE.h5 AFTER.h5
Usage (stream only the crop, no full download; paste the ASF download links):
    python sar_process.py https://...BEFORE.h5 https://...AFTER.h5
"""
import sys
import h5py
import numpy as np
from pyproj import Transformer
from scipy.ndimage import uniform_filter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Mount Rainier box (lon/lat)
LON_MIN, LON_MAX, LAT_MIN, LAT_MAX = -121.90, -121.60, 46.75, 46.95
GRID = "/science/LSAR/GCOV/grids/frequencyA"


def open_h5(path):
    if path.startswith("http"):
        import earthaccess                      # pip install earthaccess
        earthaccess.login()                     # asks for Earthdata login once
        return h5py.File(earthaccess.open([path])[0], "r")
    return h5py.File(path, "r")


def find_grid(f):
    if GRID in f:
        return f[GRID]
    hits = []
    f.visit(lambda n: hits.append(n) if n.endswith("frequencyA") and "grids" in n else None)
    if not hits:
        sys.exit("Could not find the frequencyA grid. Run: h5ls -r file.h5 | head -50")
    return f[hits[0]]


def get_epsg(g):
    p = g["projection"]
    for key in ("epsg_code", "epsg"):
        if key in p.attrs:
            return int(p.attrs[key])
    return int(p[()])


def crop(path):
    f = open_h5(path)
    g = find_grid(f)
    x, y = g["xCoordinates"][:], g["yCoordinates"][:]
    epsg = get_epsg(g)
    t = Transformer.from_crs(4326, epsg, always_xy=True)
    xs, ys = t.transform([LON_MIN, LON_MAX, LON_MIN, LON_MAX],
                         [LAT_MIN, LAT_MIN, LAT_MAX, LAT_MAX])
    ix = np.where((x >= min(xs)) & (x <= max(xs)))[0]
    iy = np.where((y >= min(ys)) & (y <= max(ys)))[0]
    if ix.size == 0 or iy.size == 0:
        sys.exit(f"Mount Rainier is not inside {path}")
    sx, sy = slice(ix[0], ix[-1] + 1), slice(iy[0], iy[-1] + 1)
    out = {"x": x[sx], "y": y[sy], "epsg": epsg}
    for pol in ("HHHH", "HVHV"):
        if pol in g:
            out[pol] = g[pol][sy, sx].astype(np.float32)
    f.close()
    print(f"  cropped {out['HHHH'].shape} pixels, EPSG {epsg}")
    return out


def to_db(power, win=7):
    power = np.where(np.isfinite(power) & (power > 0), power, np.nan)
    filled = np.nan_to_num(power, nan=0.0)
    smooth = uniform_filter(filled, win)            # boxcar speckle filter
    return 10 * np.log10(np.clip(smooth, 1e-6, None))


def match(a, b, pol):
    """Resample image b onto image a's grid (nearest neighbour)."""
    def idx(src, dst):
        order = np.argsort(src)
        pos = np.clip(np.searchsorted(src[order], dst), 0, len(src) - 1)
        return order[pos]
    return b[pol][np.ix_(idx(b["y"], a["y"]), idx(b["x"], a["x"]))]


def main(before_path, after_path):
    print("Reading BEFORE ..."); a = crop(before_path)
    print("Reading AFTER  ..."); b = crop(after_path)

    res = {"x": a["x"], "y": a["y"], "epsg": a["epsg"]}
    for pol in ("HHHH", "HVHV"):
        if pol in a and pol in b:
            before = to_db(a[pol])
            after = to_db(match(a, b, pol))
            res[f"{pol}_before"], res[f"{pol}_after"] = before, after
            res[f"{pol}_change"] = after - before
    np.savez_compressed("sar_watch_result.npz", **res)

    # Quick-look figures
    ext = [a["x"][0], a["x"][-1], a["y"][-1], a["y"][0]]
    hb, ha, hc = res["HHHH_before"], res["HHHH_after"], res["HHHH_change"]
    fig, ax = plt.subplots(1, 3, figsize=(16, 5))
    for k, (img, title, cmap, lim) in enumerate([
            (hb, "Before (HH, dB)", "gray", (-25, 0)),
            (ha, "After (HH, dB)", "gray", (-25, 0)),
            (hc, "Change (dB): red = brighter, blue = darker", "RdBu_r", (-6, 6))]):
        im = ax[k].imshow(img, cmap=cmap, vmin=lim[0], vmax=lim[1], extent=ext)
        ax[k].set_title(title); ax[k].axis("off"); plt.colorbar(im, ax=ax[k], shrink=0.8)
    plt.tight_layout(); plt.savefig("change_overview.png", dpi=150)

    def norm(d): return np.clip((d + 25) / 25, 0, 1)
    rgb = np.dstack([norm(ha), norm(hb), norm(hb)])   # R=after, G/B=before
    plt.imsave("rgb_composite.png", rgb)
    print("Done: sar_watch_result.npz, change_overview.png, rgb_composite.png")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
