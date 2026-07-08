"""Embedded PyVista/VTK render widget and isosurface management."""

from __future__ import annotations

import numpy as np
from pyvistaqt import QtInteractor

# A small default colormap of distinct colors for stacked isosurfaces.
_ISO_COLORS = [
    "#4C9BE6", "#E67E4C", "#5FBF6A", "#C05FD0", "#E6C84C", "#E65C7A",
]


class IsoViewer(QtInteractor):
    """VTK render window (as a Qt widget) that shows a volume's isosurfaces."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid = None
        self._iso_actors: list = []
        self.set_background("#1a1d21")
        self._probe_enabled = False
        self._stereo_mode = "off"
        self._add_axes()

    # ---- volume + isosurfaces -------------------------------------------

    def set_volume(self, grid) -> None:
        """Attach a new volume grid and clear any existing isosurfaces."""
        self._grid = grid
        self.clear_isosurfaces()

    @property
    def grid(self):
        return self._grid

    def clear_isosurfaces(self) -> None:
        for actor in self._iso_actors:
            self.remove_actor(actor, render=False)
        self._iso_actors = []
        self.render()

    def show_isosurfaces(self, values: list[float], opacity: float = 0.6) -> None:
        """Contour the current volume at the given values, one colored surface each."""
        self.clear_isosurfaces()
        if self._grid is None or not values:
            return
        for i, val in enumerate(values):
            try:
                surf = self._grid.contour([val], scalars="amplitude")
            except Exception:
                continue
            if surf.n_points == 0:
                continue
            color = _ISO_COLORS[i % len(_ISO_COLORS)]
            actor = self.add_mesh(
                surf, color=color, opacity=opacity, smooth_shading=True,
                name=f"iso_{i}", render=False,
            )
            self._iso_actors.append(actor)
        self.reset_camera()
        self.render()

    def last_surface_meshes(self):
        """Return the currently displayed isosurface meshes (for export)."""
        meshes = []
        for actor in self._iso_actors:
            mapper = actor.GetMapper()
            if mapper is not None:
                meshes.append(mapper.GetInput())
        return meshes

    # ---- decoration ------------------------------------------------------

    def _add_axes(self) -> None:
        self.add_axes(
            xlabel="Scalp X", ylabel="Scalp Y", zlabel="Time",
            line_width=2,
        )
        self.show_bounds(
            xtitle="Scalp X", ytitle="Scalp Y", ztitle="Time",
            grid="back", location="outer", color="#8a9099",
        )

    # ---- stereo 3D -------------------------------------------------------

    # Human-readable mode -> VTK render-window stereo setter name.
    STEREO_MODES = {
        "off": None,
        "anaglyph": "SetStereoTypeToAnaglyph",           # red/cyan glasses
        "crosseye": "SetStereoTypeToSplitViewportHorizontal",  # side-by-side, free-view
        "interlaced": "SetStereoTypeToInterlaced",       # line-interlaced 3D displays
        "checkerboard": "SetStereoTypeToCheckerboard",   # some 3D TVs
        "crystaleyes": "SetStereoTypeToCrystalEyes",     # active-shutter / quad-buffer
    }

    def set_stereo_mode(self, mode: str) -> None:
        """Set the stereo render mode (see STEREO_MODES); 'off' disables stereo."""
        if mode not in self.STEREO_MODES:
            raise ValueError(f"Unknown stereo mode {mode!r}")
        self._stereo_mode = mode
        ren_win = self.render_window
        if mode == "off":
            ren_win.SetStereoRender(False)
        else:
            getattr(ren_win, self.STEREO_MODES[mode])()
            ren_win.SetStereoRender(True)
        self.render()

    @property
    def stereo_mode(self) -> str:
        return self._stereo_mode

    # ---- probing ---------------------------------------------------------

    def enable_probe(self, enabled: bool) -> None:
        """Toggle mouse-click value probing on the volume."""
        self._probe_enabled = enabled
        if enabled and self._grid is not None:
            self.enable_point_picking(
                callback=self._on_probe, show_message=False,
                use_picker=True, show_point=True,
            )
        else:
            self.disable_picking()

    def _on_probe(self, point) -> None:
        if self._grid is None or point is None:
            return
        idx = self._grid.find_closest_point(point)
        val = self._grid.point_data["amplitude"][idx]
        x, y, t = point
        self.add_text(
            f"({x:.2f}, {y:.2f}, t={t:.1f})  amplitude = {val:.3g}",
            position="lower_left", font_size=10, name="probe_readout",
            color="#e6e6e6",
        )
