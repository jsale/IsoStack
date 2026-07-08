"""Top-level IsoStack window: menus, viewer, and control panel."""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QFileDialog, QMainWindow, QMessageBox, QSplitter, QWidget,
)
from PySide6.QtGui import QActionGroup
from PySide6.QtCore import Qt

from ..data import csv_importer
from ..volume import builder
from ..export import mesh_export
from .controls import ControlPanel
from .viewer import IsoViewer


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IsoStack — Spatiotemporal Isosurfaces")
        self.resize(1200, 800)

        self._recording = None
        self._opacity = 0.6

        self.viewer = IsoViewer(self)
        self.controls = ControlPanel(self)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.viewer.interactor if hasattr(self.viewer, "interactor") else self.viewer)
        splitter.addWidget(self.controls)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([900, 300])
        self.setCentralWidget(splitter)

        self._wire_signals()
        self._build_menus()
        self._load_synthetic()

    # ---- setup ----------------------------------------------------------

    def _wire_signals(self) -> None:
        self.controls.iso_values_changed.connect(self._on_iso_values)
        self.controls.opacity_changed.connect(self._on_opacity)
        self.controls.rebuild_requested.connect(self._rebuild_volume)
        self.controls.probe_toggled.connect(self.viewer.enable_probe)

    def _build_menus(self) -> None:
        m_file = self.menuBar().addMenu("&File")
        m_file.addAction("Open EEG CSV…", self._open_csv)
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

    def _open_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open EEG CSV", "", "CSV files (*.csv);;All files (*)"
        )
        if not path:
            return
        try:
            self._recording = csv_importer.load_csv(path)
            self._rebuild_volume(
                self.controls.current_grid_res(), self.controls.current_time_scale()
            )
            self.controls.set_status(
                f"Loaded {os.path.basename(path)}: "
                f"{self._recording.n_samples} samples × {self._recording.n_channels} channels"
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", str(exc))

    def _load_synthetic(self) -> None:
        from sample_data.generate_sample import make_synthetic_recording

        self._recording = make_synthetic_recording()
        self._rebuild_volume(
            self.controls.current_grid_res(), self.controls.current_time_scale()
        )
        self.controls.set_status(
            "Synthetic traveling-wave EEG "
            f"({self._recording.n_samples} samples × {self._recording.n_channels} channels)."
        )

    def _rebuild_volume(self, grid_res: int, time_scale: float) -> None:
        if self._recording is None:
            return
        try:
            grid = builder.build_volume(
                self._recording, grid_res=grid_res, time_scale=time_scale
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Volume build failed", str(exc))
            return
        self.viewer.set_volume(grid)
        self.controls.set_suggested_values(builder.suggest_iso_values(grid, n=3))

    # ---- viewer callbacks ----------------------------------------------

    def _on_iso_values(self, values: list) -> None:
        self.viewer.show_isosurfaces(values, opacity=self._opacity)

    def _on_opacity(self, opacity: float) -> None:
        self._opacity = opacity
        # re-emit current values through the viewer
        self._on_iso_values_current()

    def _on_iso_values_current(self) -> None:
        self.controls._emit_iso_values()

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
