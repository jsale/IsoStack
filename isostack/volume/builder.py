"""Build the spatiotemporal volume V(x, y, t) from an EEG recording.

Each time slice's electrode values are interpolated onto a regular 2D grid over
the scalp disk; the slices are stacked along the time axis to form the "loaf".
The result is a PyVista ImageData (uniform grid) with a scalar field ready for
multi-value contouring.
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import RBFInterpolator

from ..data import montage
from ..data.csv_importer import EEGRecording


def build_volume(
    rec: EEGRecording,
    grid_res: int = 48,
    time_scale: float = 4.0,
    method: str = "thin_plate_spline",
    mask_outside: bool = True,
):
    """Interpolate and stack an EEGRecording into a PyVista uniform grid.

    Parameters
    ----------
    rec : EEGRecording
    grid_res : int
        Number of samples across the scalp disk in X and Y.
    time_scale : float
        Loaf aspect ratio: total time-axis height as a multiple of the scalp
        diameter (e.g. 4.0 => the loaf is 4x as tall as it is wide), independent
        of the number of samples.
    method : str
        RBFInterpolator kernel: 'thin_plate_spline' (default, the usual choice for
        EEG scalp maps), 'multiquadric', 'linear', 'cubic', or 'gaussian'.
    mask_outside : bool
        NaN-out grid points outside the unit scalp disk.

    Returns
    -------
    pyvista.ImageData
        Volume with point scalar 'amplitude' and dimensions (grid_res, grid_res, n_samples).
    """
    import pyvista as pv

    known, positions, unknown = _resolve_positions(rec)
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
    grid_pts = np.column_stack([mesh_x.ravel(), mesh_y.ravel()])
    outside = (mesh_x**2 + mesh_y**2) > 1.0

    n_t = rec.n_samples
    vol = np.empty((grid_res, grid_res, n_t), dtype=np.float32)

    # Radial basis interpolation gives smooth scalp maps and fills the whole disk
    # (it extrapolates past the electrode hull), so no hole-filling pass is needed.
    for k in range(n_t):
        rbf = RBFInterpolator(pts, data[k], kernel=method)
        slice_vals = rbf(grid_pts).reshape(mesh_x.shape)
        if mask_outside:
            slice_vals[outside] = np.nan
        vol[:, :, k] = slice_vals

    # Scalp diameter spans 2.0 in X and Y; set the Z spacing so the total loaf
    # height is (time_scale * 2.0), giving a sample-count-independent aspect ratio.
    z_spacing = (2.0 * time_scale) / max(n_t - 1, 1)
    grid = pv.ImageData(dimensions=(grid_res, grid_res, n_t))
    grid.origin = (-1.0, -1.0, 0.0)
    grid.spacing = (2.0 / (grid_res - 1), 2.0 / (grid_res - 1), z_spacing)
    # VTK point ordering is x-fastest, then y, then z -> Fortran order flatten
    grid.point_data["amplitude"] = vol.ravel(order="F")
    return grid


def _resolve_positions(rec: EEGRecording):
    """Return (labels, 2D positions, unknown) for a recording's electrodes.

    Prefers positions embedded in the file (rec.positions) and falls back to the
    standard-10-20 name lookup for any channel the file didn't place. This is
    what lets non-standard channel names (e.g. EEGLAB 'EEG 000') resolve when the
    file carries its own sensor coordinates.
    """
    labels: list[str] = []
    pts: list[tuple[float, float]] = []
    unknown: list[str] = []
    for label in rec.labels:
        pos = None
        if rec.positions is not None:
            pos = rec.positions.get(label)
        if pos is None:
            pos = montage.position(label)
        if pos is None:
            unknown.append(label)
        else:
            labels.append(label)
            pts.append(pos)
    return labels, pts, unknown


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
