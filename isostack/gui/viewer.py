"""Embedded PyVista/VTK render widget and isosurface management."""

from __future__ import annotations

import numpy as np
from pyvistaqt import QtInteractor


class IsoViewer(QtInteractor):
    """VTK render window (as a Qt widget) that shows a volume's isosurfaces."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid = None
        self._iso_actors: list = []
        self.set_background("#1a1d21")
        self._probe_enabled = False
        self._stereo_mode = "off"
        self._cmap = "jet"          # matches the MATLAB heritage of the method
        self._last_values: list[float] = []
        self._add_axes()

    # ---- volume + isosurfaces -------------------------------------------

    def set_volume(self, grid) -> None:
        """Attach a new volume grid and clear any existing isosurfaces."""
        self._grid = grid
        self.clear_isosurfaces()
        self._add_scalp_labels()
        self.reset_camera()

    @property
    def grid(self):
        return self._grid

    def _clim(self):
        """Finite [min, max] of the current volume's amplitude, or None."""
        if self._grid is None:
            return None
        arr = self._grid.point_data["amplitude"]
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            return None
        return [float(finite.min()), float(finite.max())]

    def clear_isosurfaces(self) -> None:
        for actor in self._iso_actors:
            self.remove_actor(actor, render=False)
        self._iso_actors = []
        try:
            self.remove_scalar_bar("Amplitude")
        except Exception:
            pass
        self.render()

    def set_colormap(self, name: str) -> None:
        """Change the colormap and re-render the current isosurfaces."""
        self._cmap = name
        if self._last_values:
            self.show_isosurfaces(self._last_values, self._opacity_of_last())

    def _opacity_of_last(self) -> float:
        if self._iso_actors:
            return self._iso_actors[0].GetProperty().GetOpacity()
        return 0.6

    def show_isosurfaces(self, values: list[float], opacity: float = 0.6) -> None:
        """Contour the volume at the given values as one mesh, colored by amplitude.

        Nested surfaces (low -> high) share a single colormap and colorbar, matching
        the established jet-colored spatiotemporal-isosurface look.
        """
        self.clear_isosurfaces()
        self._last_values = list(values)
        if self._grid is None or not values:
            return
        try:
            surf = self._grid.contour(sorted(values), scalars="amplitude")
        except Exception:
            return
        if surf.n_points == 0:
            return
        actor = self.add_mesh(
            surf, scalars="amplitude", cmap=self._cmap, clim=self._clim(),
            opacity=opacity, smooth_shading=True, name="iso", render=False,
            scalar_bar_args={"title": "Amplitude", "color": "#e6e6e6"},
        )
        self._iso_actors.append(actor)
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

    def _add_scalp_labels(self) -> None:
        """Annotate scalp orientation (Front/Back/Left/Right) at the top cross-section.

        Front = +Y (nose), Right = +X (right ear), matching the montage convention.
        """
        if self._grid is None:
            return
        z_top = self._grid.bounds[5]
        points = [[0.0, 1.05, z_top], [0.0, -1.05, z_top],
                  [1.05, 0.0, z_top], [-1.05, 0.0, z_top]]
        labels = ["Front", "Back", "Right", "Left"]
        try:
            self.remove_actor("scalp_labels", render=False)
        except Exception:
            pass
        self.add_point_labels(
            points, labels, name="scalp_labels", font_size=12,
            text_color="#c8ccd2", shape=None, show_points=False, render=False,
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
