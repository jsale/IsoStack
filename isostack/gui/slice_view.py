"""2D scalp-topography panel showing one horizontal cross-section of the loaf.

The loaf volume V(x, y, t) is a stack of 2D scalp maps, so a horizontal slice at
time t *is* a topographic map. This widget renders that slice with matplotlib's
Agg backend (no Qt backend — avoids the PySide6/Qt DLL pitfalls) and blits it
into a QLabel, so it updates live as the cross-section plane is dragged.
"""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import Circle
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_BG = "#1a1d21"          # match the 3D viewer background
_FG = "#c8ccd2"


class SliceView(QWidget):
    """Renders a single time-slice of the volume as a scalp topo map."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vol = None
        self._nt = 0
        self._clim = (0.0, 1.0)        # data range
        self._user_clim = None         # (lo, hi) override, or None
        self._trange = None
        self._cmap = "jet"

        self._fig = Figure(figsize=(2.9, 3.2), dpi=100, facecolor=_BG)
        self._canvas = FigureCanvasAgg(self._fig)
        self._ax = self._fig.add_subplot(111)

        self._label = QLabel("Enable the cross-section to see a scalp map here.")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setMinimumSize(280, 320)
        self._label.setStyleSheet(f"background:{_BG}; color:{_FG};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.addWidget(self._label)

    # ---- data ------------------------------------------------------------

    def set_volume(self, grid, time_range=None, cmap: str | None = None) -> None:
        """Attach the current loaf; reshape its scalars to (nx, ny, nt)."""
        arr = np.asarray(grid.point_data["amplitude"])
        dims = grid.dimensions
        # VTK point ordering is x-fastest -> Fortran reshape recovers (nx, ny, nt)
        self._vol = arr.reshape(dims, order="F")
        self._nt = int(dims[2])
        finite = arr[np.isfinite(arr)]
        self._clim = (float(finite.min()), float(finite.max())) if finite.size else (0.0, 1.0)
        self._trange = time_range
        if cmap:
            self._cmap = cmap

    def set_cmap(self, cmap: str) -> None:
        self._cmap = cmap

    def set_clim(self, lo: float, hi: float) -> None:
        self._user_clim = (float(lo), float(hi))

    def set_clim_auto(self) -> None:
        self._user_clim = None

    def _effective_clim(self):
        return self._user_clim if self._user_clim is not None else self._clim

    @property
    def n_slices(self) -> int:
        return self._nt

    def _time_at(self, k: int) -> float | None:
        if self._trange is None or self._nt <= 1:
            return None
        t0, t1 = self._trange
        return t0 + (k / (self._nt - 1)) * (t1 - t0)

    # ---- render ----------------------------------------------------------

    def show_slice(self, k: int) -> None:
        """Draw the k-th time slice as a scalp topo map."""
        if self._vol is None or self._nt == 0:
            return
        k = int(np.clip(k, 0, self._nt - 1))
        sl = self._vol[:, :, k]                    # (nx, ny)

        ax = self._ax
        ax.clear()
        ax.set_facecolor(_BG)
        # imshow rows=y (vertical), cols=x (horizontal): transpose so +Y is up
        vmin, vmax = self._effective_clim()
        ax.imshow(
            sl.T, origin="lower", extent=(-1, 1, -1, 1), cmap=self._cmap,
            vmin=vmin, vmax=vmax, interpolation="bilinear",
        )
        ax.add_patch(Circle((0, 0), 1.0, fill=False, color=_FG, lw=1.2))
        for x, y, txt, ha, va in (
            (0, 1.06, "Front", "center", "bottom"),
            (0, -1.06, "Back", "center", "top"),
            (1.06, 0, "Right", "left", "center"),
            (-1.06, 0, "Left", "right", "center"),
        ):
            ax.text(x, y, txt, color=_FG, fontsize=8, ha=ha, va=va)

        t = self._time_at(k)
        title = f"t = {t:.3g} s" if t is not None else f"slice {k + 1}/{self._nt}"
        ax.set_title(title, color=_FG, fontsize=10)
        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-1.2, 1.2)
        ax.set_aspect("equal")
        ax.axis("off")
        self._fig.tight_layout(pad=0.3)

        self._canvas.draw()
        buf = np.asarray(self._canvas.buffer_rgba())
        h, w, _ = buf.shape
        img = QImage(buf.tobytes(), w, h, QImage.Format_RGBA8888).copy()
        self._label.setPixmap(QPixmap.fromImage(img))
