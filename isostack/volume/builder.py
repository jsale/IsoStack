"""Build the spatiotemporal volume V(x, y, t) from an EEG recording.

Each time slice's electrode values are interpolated onto a regular 2D grid over
the scalp disk; the slices are stacked along the time axis to form the "loaf".
The result is a PyVista ImageData (uniform grid) with a scalar field ready for
multi-value contouring.
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import griddata

from ..data import montage
from ..data.csv_importer import EEGRecording


def build_volume(
    rec: EEGRecording,
    grid_res: int = 48,
    time_scale: float = 1.0,
    method: str = "cubic",
    mask_outside: bool = True,
):
    """Interpolate and stack an EEGRecording into a PyVista uniform grid.

    Parameters
    ----------
    rec : EEGRecording
    grid_res : int
        Number of samples across the scalp disk in X and Y.
    time_scale : float
        Multiplier applied to the time axis spacing (visual stretch of the loaf).
    method : str
        scipy.interpolate.griddata method: 'cubic', 'linear', or 'nearest'.
    mask_outside : bool
        NaN-out grid points outside the unit scalp disk.

    Returns
    -------
    pyvista.ImageData
        Volume with point scalar 'amplitude' and dimensions (grid_res, grid_res, n_samples).
    """
    import pyvista as pv

    known, positions, unknown = montage.resolve_labels(rec.labels)
    if len(known) < 4:
        raise ValueError(
            f"Need at least 4 recognized electrodes to interpolate; "
            f"got {len(known)} (unknown: {unknown})"
        )

    pts = np.asarray(positions, dtype=float)            # (n_known, 2)
    col_idx = [rec.labels.index(lbl) for lbl in known]
    data = rec.values[:, col_idx]                        # (n_samples, n_known)

    gx = np.linspace(-1.0, 1.0, grid_res)
    gy = np.linspace(-1.0, 1.0, grid_res)
    mesh_x, mesh_y = np.meshgrid(gx, gy)                 # (res, res)
    outside = (mesh_x**2 + mesh_y**2) > 1.0

    n_t = rec.n_samples
    vol = np.empty((grid_res, grid_res, n_t), dtype=np.float32)

    for k in range(n_t):
        slice_vals = griddata(pts, data[k], (mesh_x, mesh_y), method=method, fill_value=np.nan)
        # fall back to nearest where cubic/linear leaves holes inside the disk
        if method != "nearest":
            holes = np.isnan(slice_vals) & ~outside
            if holes.any():
                nn = griddata(pts, data[k], (mesh_x, mesh_y), method="nearest")
                slice_vals[holes] = nn[holes]
        if mask_outside:
            slice_vals[outside] = np.nan
        vol[:, :, k] = slice_vals

    grid = pv.ImageData(dimensions=(grid_res, grid_res, n_t))
    grid.origin = (-1.0, -1.0, 0.0)
    grid.spacing = (2.0 / (grid_res - 1), 2.0 / (grid_res - 1), time_scale)
    # VTK point ordering is x-fastest, then y, then z -> Fortran order flatten
    grid.point_data["amplitude"] = vol.ravel(order="F")
    return grid


def suggest_iso_values(grid, n: int = 3) -> list[float]:
    """Suggest n evenly spaced isosurface values across the volume's data range."""
    import numpy as np

    arr = grid.point_data["amplitude"]
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return []
    lo, hi = np.percentile(finite, [10, 90])
    if n == 1:
        return [float((lo + hi) / 2)]
    return [float(v) for v in np.linspace(lo, hi, n)]
