"""Embedded PyVista/VTK render widget and isosurface management."""

from __future__ import annotations

import numpy as np
from pyvistaqt import QtInteractor


class IsoViewer(QtInteractor):
    """VTK render window (as a Qt widget) that shows a volume's isosurfaces."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid = None
        self._time_range = None      # (t_start, t_end) in the recording's units
        self._iso_actors: list = []
        self.set_background("#1a1d21")
        self._probe_enabled = False
        self._stereo_mode = "off"
        self._cmap = "jet"          # matches the MATLAB heritage of the method
        self._user_clim = None      # (lo, hi) override, or None for data range
        self._last_values: list[float] = []
        self._add_axes()

    # ---- volume + isosurfaces -------------------------------------------

    def set_volume(self, grid, time_range=None) -> None:
        """Attach a new volume grid and clear any existing isosurfaces.

        `time_range` is the (start, end) of the built window in the recording's
        own units (seconds for real data); it labels the Time axis so a
        re-windowed loaf reads in real time rather than normalized loaf height.
        """
        self._grid = grid
        self._time_range = time_range
        self.clear_isosurfaces()
        self._add_scalp_labels()
        self.reset_camera()
        # Bounds are refreshed by refresh_axes() *after* the isosurfaces are
        # added — adding a mesh makes VTK's cube-axes actor recompute its tick
        # range from geometry, which would otherwise wipe the real-time labels.

    def refresh_axes(self) -> None:
        """Redraw the labeled bounding box; call after isosurfaces are shown."""
        self._refresh_bounds()

    # ---- cross-section plane --------------------------------------------

    def section_z(self, k: int) -> float:
        """World Z of the k-th time slice (for syncing the 2D panel)."""
        if self._grid is None:
            return 0.0
        return float(self._grid.origin[2] + k * self._grid.spacing[2])

    def set_section(self, k: int, visible: bool = True) -> None:
        """Draw (or hide) a wireframe rectangle at the k-th time slice."""
        try:
            self.remove_actor("section", render=False)
        except Exception:
            pass
        if visible and self._grid is not None:
            import pyvista as pv

            z = self.section_z(k)
            loop = np.array([[-1, -1, z], [1, -1, z], [1, 1, z],
                             [-1, 1, z], [-1, -1, z]], dtype=float)
            self.add_mesh(
                pv.lines_from_points(loop), color="#ff3b6b", line_width=4,
                name="section", render=False, reset_camera=False,
            )
        # adding/removing an actor makes VTK's cube-axes recompute its range from
        # geometry, wiping the real-time Z labels; reassert them.
        self._refresh_bounds()
        self.render()

    @property
    def grid(self):
        return self._grid

    @property
    def colormap(self) -> str:
        return self._cmap

    def _data_clim(self):
        """Finite [min, max] of the current volume's amplitude, or None."""
        if self._grid is None:
            return None
        arr = self._grid.point_data["amplitude"]
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            return None
        return [float(finite.min()), float(finite.max())]

    def _clim(self):
        """Color limits in effect: the user override if set, else the data range."""
        if self._user_clim is not None:
            return [float(self._user_clim[0]), float(self._user_clim[1])]
        return self._data_clim()

    def amplitude_range(self):
        """Public finite [min, max] of the current volume's amplitude, or None."""
        return self._data_clim()

    def set_clim(self, lo: float, hi: float) -> None:
        """Clamp the colormap to [lo, hi] instead of the data range and recolor."""
        self._user_clim = (float(lo), float(hi))
        self._recolor()

    def set_clim_auto(self) -> None:
        """Revert the colormap to spanning the data range and recolor."""
        self._user_clim = None
        self._recolor()

    def _recolor(self) -> None:
        """Rebuild the isosurfaces so the new clim/cmap bakes into the LUT."""
        if self._last_values:
            op = self._opacity_of_last()
            self.clear_isosurfaces()
            self.show_isosurfaces(self._last_values, op)
            # re-adding the mesh makes VTK's cube-axes recompute from geometry;
            # reassert the real-time Z labels.
            self._refresh_bounds()
            self.render()

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
        # colormap is baked into the mapper's LUT at build time, so a full
        # rebuild (not an in-place update) is needed to recolor.
        self._cmap = name
        self._recolor()

    def _opacity_of_last(self) -> float:
        if self._iso_actors:
            return self._iso_actors[0].GetProperty().GetOpacity()
        return 0.6

    def _contour_surface(self, values: list[float]):
        """Contour the volume at `values`, returning a mesh with normals, or None."""
        if self._grid is None or not values:
            return None
        try:
            surf = self._grid.contour(sorted(values), scalars="amplitude")
        except Exception:
            return None
        if surf.n_points == 0:
            return None
        # Point normals keep Phong/smooth shading when we swap the mapper input
        # in place (the mesh from contour has none of its own).
        try:
            surf = surf.compute_normals(
                cell_normals=False, point_normals=True,
                auto_orient_normals=False, inplace=False,
            )
        except Exception:
            pass
        return surf

    def show_isosurfaces(self, values: list[float], opacity: float = 0.6) -> None:
        """Contour the volume at the given values as one mesh, colored by amplitude.

        Nested surfaces (low -> high) share a single colormap and colorbar, matching
        the established jet-colored spatiotemporal-isosurface look.

        When an isosurface actor already exists (e.g. during a sweep) the mesh is
        updated *in place* rather than removed and re-added — this avoids a blank
        intermediate frame that otherwise flickers the surface and colorbar.
        """
        self._last_values = list(values)
        surf = self._contour_surface(values)
        if surf is None:
            self.clear_isosurfaces()
            return
        if self._iso_actors:
            actor = self._iso_actors[0]
            mapper = actor.GetMapper()
            mapper.SetInputData(surf)
            actor.GetProperty().SetOpacity(opacity)
            self.render()
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
        self._refresh_bounds()

    def _refresh_bounds(self) -> None:
        """(Re)draw the labeled bounding box, showing real time on the Z ticks.

        The loaf geometry is normalized (Z spans 0..2*aspect), so we relabel the
        Z tick range to the window's real time via `axes_ranges` while leaving
        the geometry untouched.
        """
        ztitle = "Time"
        axes_ranges = None
        if self._grid is not None:
            b = self._grid.bounds
            if self._time_range is not None:
                t0, t1 = float(self._time_range[0]), float(self._time_range[1])
                if t1 <= t0:                       # degenerate window -> pad
                    t1 = t0 + 1e-6
                ztitle = "Time (s)"
                axes_ranges = [b[0], b[1], b[2], b[3], t0, t1]
        self.show_bounds(
            xtitle="Scalp X", ytitle="Scalp Y", ztitle=ztitle,
            axes_ranges=axes_ranges,
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

    # Split-viewport renders left-eye-left / right-eye-right, which is *parallel*
    # (wall-eyed) free-viewing. Cross-eye viewing needs the two images swapped,
    # which we do by negating the camera eye angle (there is no
    # SetStereoSwapEyes on this VTK render window).
    STEREO_SWAP_EYES = {"crosseye"}
    # Split-viewport modes squeeze each eye into half the window width without
    # correcting the projection aspect, squashing the 3D content ~2x. We fix it
    # with an explicit camera aspect of 0.5 * (width/height), refreshed on resize.
    STEREO_SPLIT_VIEWPORT = {"crosseye"}
    _EYE_ANGLE = 2.0  # VTK default

    def set_stereo_mode(self, mode: str) -> None:
        """Set the stereo render mode (see STEREO_MODES); 'off' disables stereo."""
        if mode not in self.STEREO_MODES:
            raise ValueError(f"Unknown stereo mode {mode!r}")
        self._stereo_mode = mode
        ren_win = self.render_window
        camera = self.renderer.GetActiveCamera()
        swap = mode in self.STEREO_SWAP_EYES
        camera.SetEyeAngle(-self._EYE_ANGLE if swap else self._EYE_ANGLE)
        if mode == "off":
            ren_win.SetStereoRender(False)
        else:
            getattr(ren_win, self.STEREO_MODES[mode])()
            ren_win.SetStereoRender(True)
        self._apply_stereo_aspect()
        self.render()

    def _apply_stereo_aspect(self) -> None:
        """Correct the projection aspect for split-viewport stereo modes."""
        camera = self.renderer.GetActiveCamera()
        if self._stereo_mode in self.STEREO_SPLIT_VIEWPORT:
            w, h = self.render_window.GetSize()
            if h > 0:
                camera.SetExplicitAspectRatio(0.5 * (w / h))
                camera.SetUseExplicitAspectRatio(True)
        else:
            camera.SetUseExplicitAspectRatio(False)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        # window aspect changed -> refresh the split-viewport correction
        self._apply_stereo_aspect()

    @property
    def stereo_mode(self) -> str:
        return self._stereo_mode

    # ---- probing ---------------------------------------------------------

    def enable_probe(self, enabled: bool) -> None:
        """Toggle left-click value probing on the isosurfaces."""
        self._probe_enabled = enabled
        if enabled and self._grid is not None:
            # left_clicking=True makes a plain left-click probe (a drag still
            # orbits the camera); the default trigger is the 'P' key, which is
            # not discoverable.
            self.enable_point_picking(
                callback=self._on_probe,
                left_clicking=True,
                show_message=False,
                show_point=True,
                point_size=14,
                color="#ff3b6b",
                tolerance=0.02,
            )
            self.add_text(
                "Probe ON — left-click a surface",
                position="upper_left", font_size=10, name="probe_hint",
                color="#8a9099",
            )
        else:
            self.disable_picking()
            for name in ("probe_readout", "probe_hint"):
                try:
                    self.remove_actor(name, render=False)
                except Exception:
                    pass
            self.render()

    def _on_probe(self, point, *_) -> None:
        if self._grid is None or point is None:
            return
        idx = self._grid.find_closest_point(point)
        val = self._grid.point_data["amplitude"][idx]
        x, y, t = point
        amp = "outside scalp" if not np.isfinite(val) else f"{val:.4g}"
        self.add_text(
            f"scalp X={x:+.2f}  Y={y:+.2f}   time={t:.2f}\namplitude = {amp}",
            position="lower_left", font_size=12, name="probe_readout",
            color="#e6e6e6",
        )
        self.render()
