"""Control panel: isosurface values, opacity, grid resolution, time scale."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QPushButton,
    QSlider, QSpinBox, QVBoxLayout, QWidget,
)


class ControlPanel(QWidget):
    """Side panel emitting signals when visualization parameters change."""

    iso_values_changed = Signal(list)     # list[float]
    opacity_changed = Signal(float)
    rebuild_requested = Signal(int, float)  # grid_res, time_scale
    probe_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # --- Isosurfaces -------------------------------------------------
        iso_box = QGroupBox("Isosurfaces")
        iso_form = QFormLayout(iso_box)
        self._iso_spins: list[QDoubleSpinBox] = []
        for i in range(4):
            spin = QDoubleSpinBox()
            spin.setRange(-1e6, 1e6)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setEnabled(i == 0)
            spin.valueChanged.connect(self._emit_iso_values)
            self._iso_spins.append(spin)
            iso_form.addRow(f"Value {i + 1}", spin)

        self._count = QSpinBox()
        self._count.setRange(1, 4)
        self._count.setValue(1)
        self._count.valueChanged.connect(self._on_count_changed)
        iso_form.addRow("Active count", self._count)
        layout.addWidget(iso_box)

        # --- Appearance --------------------------------------------------
        appear_box = QGroupBox("Appearance")
        appear_form = QFormLayout(appear_box)
        self._opacity = QSlider(Qt.Horizontal)
        self._opacity.setRange(5, 100)
        self._opacity.setValue(60)
        self._opacity.valueChanged.connect(
            lambda v: self.opacity_changed.emit(v / 100.0)
        )
        appear_form.addRow("Opacity", self._opacity)
        layout.addWidget(appear_box)

        # --- Volume ------------------------------------------------------
        vol_box = QGroupBox("Volume")
        vol_form = QFormLayout(vol_box)
        self._grid_res = QSpinBox()
        self._grid_res.setRange(16, 160)
        self._grid_res.setValue(48)
        vol_form.addRow("Grid resolution", self._grid_res)

        self._time_scale = QDoubleSpinBox()
        self._time_scale.setRange(0.01, 100.0)
        self._time_scale.setValue(1.0)
        self._time_scale.setSingleStep(0.1)
        vol_form.addRow("Time scale", self._time_scale)

        rebuild = QPushButton("Rebuild volume")
        rebuild.clicked.connect(
            lambda: self.rebuild_requested.emit(
                self._grid_res.value(), self._time_scale.value()
            )
        )
        vol_form.addRow(rebuild)
        layout.addWidget(vol_box)

        # --- Interaction -------------------------------------------------
        self._probe = QCheckBox("Probe values (click)")
        self._probe.toggled.connect(self.probe_toggled.emit)
        layout.addWidget(self._probe)

        self._status = QLabel("No data loaded.")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        layout.addStretch(1)

    # ---- external updates ----------------------------------------------

    def set_suggested_values(self, values: list[float]) -> None:
        """Populate the spin boxes with suggested iso-values and enable them."""
        self._count.setValue(max(1, min(4, len(values))))
        for i, spin in enumerate(self._iso_spins):
            if i < len(values):
                spin.blockSignals(True)
                spin.setValue(values[i])
                spin.blockSignals(False)
        self._emit_iso_values()

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def current_grid_res(self) -> int:
        return self._grid_res.value()

    def current_time_scale(self) -> float:
        return self._time_scale.value()

    # ---- internal -------------------------------------------------------

    def _on_count_changed(self, n: int) -> None:
        for i, spin in enumerate(self._iso_spins):
            spin.setEnabled(i < n)
        self._emit_iso_values()

    def _emit_iso_values(self) -> None:
        n = self._count.value()
        values = [self._iso_spins[i].value() for i in range(n)]
        self.iso_values_changed.emit(values)
