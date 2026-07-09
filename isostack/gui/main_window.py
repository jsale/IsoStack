"""Top-level IsoStack window: menus, viewer, and control panel."""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QDockWidget, QFileDialog, QMainWindow, QMessageBox, QSplitter, QWidget,
)
from PySide6.QtGui import QActionGroup
from PySide6.QtCore import Qt

from ..data import loaders
from ..volume import builder
from ..export import mesh_export
from .controls import ControlPanel
from .slice_view import SliceView
from .viewer import IsoViewer


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IsoStack — Spatiotemporal Isosurfaces")
        self.resize(1200, 800)

        self._recording = None
        self._opacity = 0.6
        self._sweeping = False

        self.viewer = IsoViewer(self)
        self.controls = ControlPanel(self)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.viewer.interactor if hasattr(self.viewer, "interactor") else self.viewer)
        splitter.addWidget(self.controls)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([900, 300])
        self.setCentralWidget(splitter)

        # Docked scalp-map panel for the cross-section (floatable/closable).
        self.slice_view = SliceView(self)
        self._slice_dock = QDockWidget("Scalp map (cross-section)", self)
        self._slice_dock.setWidget(self.slice_view)
        self._slice_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self._slice_dock)
        self._slice_dock.hide()

        self._wire_signals()
        self._build_menus()
        self._load_synthetic()

    # ---- setup ----------------------------------------------------------

    def _wire_signals(self) -> None:
        self.controls.iso_values_changed.connect(self._on_iso_values)
        self.controls.opacity_changed.connect(self._on_opacity)
        self.controls.colormap_changed.connect(self.viewer.set_colormap)
        self.controls.rebuild_requested.connect(self._rebuild_volume)
        self.controls.probe_toggled.connect(self.viewer.enable_probe)
        self.controls.sweep_toggled.connect(self._on_sweep_toggled)
        self.controls.sweep_value_changed.connect(self._on_sweep_value)
        self.controls.section_toggled.connect(self._on_section_toggled)
        self.controls.section_changed.connect(self._on_section_changed)
        self.controls.colormap_changed.connect(self._on_colormap_for_slice)
        self.controls.clim_changed.connect(self._apply_clim)

    def _build_menus(self) -> None:
        m_file = self.menuBar().addMenu("&File")
        m_file.addAction("Open EEG data…", self._open_data)
        m_file.addSeparator()
        m_file.addAction("Save PNG snapshot…", self._save_png)
        m_file.addAction("Export isosurfaces (STL)…", lambda: self._export_mesh("stl"))
        m_file.addAction("Export scene (OBJ)…", self._export_obj)
        m_file.addSeparator()
        m_file.addAction("Load synthetic sample", self._load_synthetic)
        m_file.addSeparator()
        m_file.addAction("Quit", self.close)

        m_view = self.menuBar().addMenu("&View")
        m_view.addAction("Reset camera", self.viewer.reset_camera)
        m_view.addAction("Top (XY)", lambda: self.viewer.view_xy())
        m_view.addAction("Front (XZ)", lambda: self.viewer.view_xz())
        m_view.addAction("Side (YZ)", lambda: self.viewer.view_yz())
        m_view.addSeparator()

        m_stereo = m_view.addMenu("Stereo 3D")
        stereo_group = QActionGroup(self)
        stereo_group.setExclusive(True)
        stereo_labels = [
            ("Off", "off"),
            ("Cross-eye (side-by-side)", "crosseye"),
            ("Anaglyph (red/cyan)", "anaglyph"),
            ("Interlaced", "interlaced"),
            ("Checkerboard", "checkerboard"),
            ("Crystal Eyes (active shutter)", "crystaleyes"),
        ]
        for label, mode in stereo_labels:
            act = m_stereo.addAction(label)
            act.setCheckable(True)
            act.setChecked(mode == "off")
            act.triggered.connect(lambda _checked, m=mode: self._set_stereo(m))
            stereo_group.addAction(act)

    def _set_stereo(self, mode: str) -> None:
        try:
            self.viewer.set_stereo_mode(mode)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Stereo unavailable", str(exc))

    # ---- data -----------------------------------------------------------

    def _open_data(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open EEG/MEG data", "", loaders.OPEN_FILTER
        )
        if not path:
            return
        try:
            self._recording = loaders.load_recording(path)
            self._on_recording_loaded()
            self.controls.set_status(
                f"Loaded {os.path.basename(path)}: "
                f"{self._recording.n_samples} samples × {self._recording.n_channels} channels"
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", str(exc))

    def _load_synthetic(self) -> None:
        from sample_data.generate_sample import make_synthetic_recording

        self._recording = make_synthetic_recording()
        self._on_recording_loaded()
        self.controls.set_status(
            "Synthetic traveling-wave EEG "
            f"({self._recording.n_samples} samples × {self._recording.n_channels} channels)."
        )

    def _on_recording_loaded(self) -> None:
        """Configure the segment window for the new recording, then build."""
        t = self._recording.times
        self.controls.set_time_extent(float(t[0]), float(t[-1]))
        self._rebuild_volume(
            self.controls.current_grid_res(), self.controls.current_time_scale()
        )

    def _rebuild_volume(self, grid_res: int, time_scale: float) -> None:
        if self._recording is None:
            return
        start, end, max_slices = self.controls.current_segment()
        rec = loaders.segment_recording(self._recording, start, end, max_slices)
        try:
            grid = builder.build_volume(rec, grid_res=grid_res, time_scale=time_scale)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Volume build failed", str(exc))
            return
        time_range = (float(rec.times[0]), float(rec.times[-1])) if rec.n_samples else None
        self.viewer.set_volume(grid, time_range=time_range)
        rng = self.viewer.amplitude_range()
        if rng is not None:
            self.controls.set_sweep_range(rng[0], rng[1])
        self.controls.set_suggested_values(builder.suggest_iso_values(grid, n=3))
        # feed the cross-section panel + slider for the new volume
        self.slice_view.set_volume(grid, time_range=time_range, cmap=self.viewer.colormap)
        self.controls.set_section_range(grid.dimensions[2])
        self._apply_clim()           # recolor isosurfaces + slice per the color range
        if self.controls.section_active():
            self.viewer.set_section(self.controls.current_section(), True)
        self.viewer.refresh_axes()   # LAST: after every actor change, so time labels stick
        if self._recording.n_samples:
            self.controls.set_status(
                f"Window {rec.times[0]:.3g}–{rec.times[-1]:.3g} · "
                f"{rec.n_samples} slices (of {self._recording.n_samples}) × "
                f"{self._recording.n_channels} ch"
            )

    # ---- viewer callbacks ----------------------------------------------

    def _on_iso_values(self, values: list) -> None:
        self.viewer.show_isosurfaces(values, opacity=self._opacity)

    def _on_opacity(self, opacity: float) -> None:
        self._opacity = opacity
        # re-emit current values through the viewer
        self._on_iso_values_current()

    def _on_iso_values_current(self) -> None:
        self.controls._emit_iso_values()

    def _on_sweep_toggled(self, active: bool) -> None:
        self._sweeping = active
        if not active:
            # leaving sweep mode: restore the static nested isosurfaces
            self._on_iso_values_current()

    def _on_sweep_value(self, value: float) -> None:
        if self._sweeping:
            # single surface at the swept level; camera/stereo state is untouched
            self.viewer.show_isosurfaces([value], opacity=self._opacity)

    # ---- cross-section --------------------------------------------------

    def _on_section_toggled(self, on: bool) -> None:
        self._slice_dock.setVisible(on)
        if on:
            k = self.controls.current_section()
            self.viewer.set_section(k, True)
            self.slice_view.show_slice(k)
        else:
            self.viewer.set_section(0, False)

    def _on_section_changed(self, k: int) -> None:
        if not self.controls.section_active():
            return
        self.viewer.set_section(k, True)
        self.slice_view.show_slice(k)

    def _on_colormap_for_slice(self, name: str) -> None:
        self.slice_view.set_cmap(name)
        if self.controls.section_active():
            self.slice_view.show_slice(self.controls.current_section())

    def _apply_clim(self) -> None:
        """Apply the color range (auto data range, or the user's min/max clamp)."""
        if self.controls.color_auto():
            rng = self.viewer.amplitude_range()
            if rng is not None:
                self.controls.set_color_range(*rng)   # show data range for reference
            self.viewer.set_clim_auto()
            self.slice_view.set_clim_auto()
        else:
            lo, hi = self.controls.current_color_range()
            self.viewer.set_clim(lo, hi)
            self.slice_view.set_clim(lo, hi)
        if self.controls.section_active():
            self.slice_view.show_slice(self.controls.current_section())

    # ---- export ---------------------------------------------------------

    def _save_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PNG", "isostack.png", "PNG (*.png)"
        )
        if path:
            mesh_export.save_png(self.viewer, path)

    def _export_mesh(self, kind: str) -> None:
        meshes = self.viewer.last_surface_meshes()
        if not meshes:
            QMessageBox.information(self, "Nothing to export", "No isosurfaces are displayed.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export isosurface", f"isosurface.{kind}", f"{kind.upper()} (*.{kind})"
        )
        if not path:
            return
        try:
            import pyvista as pv

            merged = meshes[0]
            for extra in meshes[1:]:
                merged = merged.merge(extra)
            mesh_export.export_mesh(pv.wrap(merged), path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))

    def _export_obj(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export scene OBJ", "scene.obj", "OBJ (*.obj)")
        if path:
            try:
                mesh_export.export_scene_obj(self.viewer, path)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Export failed", str(exc))
