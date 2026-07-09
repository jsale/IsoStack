"""Control panel: isosurface values, opacity, grid resolution, time scale."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

# Slider is integer-based; this is how many discrete steps span the
# low->high amplitude range (finer = smoother sweep).
_SWEEP_STEPS = 1000


class ControlPanel(QWidget):
    """Side panel emitting signals when visualization parameters change."""

    iso_values_changed = Signal(list)     # list[float]
    opacity_changed = Signal(float)
    colormap_changed = Signal(str)
    rebuild_requested = Signal(int, float)  # grid_res, time_scale
    probe_toggled = Signal(bool)
    sweep_toggled = Signal(bool)          # sweep mode on/off
    sweep_value_changed = Signal(float)   # current swept iso-value

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

        # --- Sweep -------------------------------------------------------
        # Animate a single isosurface from low -> high amplitude, revealing the
        # nested spatiotemporal structure one level at a time. Works in stereo.
        sweep_box = QGroupBox("Sweep isosurface")
        sweep_layout = QVBoxLayout(sweep_box)

        self._sweep_enable = QCheckBox("Enable sweep")
        self._sweep_enable.toggled.connect(self._on_sweep_enable)
        sweep_layout.addWidget(self._sweep_enable)

        # slider + synced value text box on one row
        sv_row = QHBoxLayout()
        self._sweep_slider = QSlider(Qt.Horizontal)
        self._sweep_slider.setRange(0, _SWEEP_STEPS)
        self._sweep_slider.setValue(0)
        self._sweep_slider.setEnabled(False)
        self._sweep_slider.valueChanged.connect(self._on_sweep_slider)
        sv_row.addWidget(self._sweep_slider, 1)

        self._sweep_value = QDoubleSpinBox()
        self._sweep_value.setRange(-1e6, 1e6)
        self._sweep_value.setDecimals(3)
        self._sweep_value.setSingleStep(0.01)
        self._sweep_value.setEnabled(False)
        self._sweep_value.valueChanged.connect(self._on_sweep_spin)
        sv_row.addWidget(self._sweep_value)
        sweep_layout.addLayout(sv_row)

        # play/pause + loop
        pl_row = QHBoxLayout()
        self._sweep_play = QPushButton("▶ Play")
        self._sweep_play.setCheckable(True)
        self._sweep_play.setEnabled(False)
        self._sweep_play.toggled.connect(self._on_sweep_play)
        pl_row.addWidget(self._sweep_play)

        self._sweep_loop = QCheckBox("Loop")
        self._sweep_loop.setChecked(True)
        pl_row.addWidget(self._sweep_loop)
        sweep_layout.addLayout(pl_row)

        dur_form = QFormLayout()
        self._sweep_secs = QDoubleSpinBox()
        self._sweep_secs.setRange(0.5, 60.0)
        self._sweep_secs.setValue(6.0)
        self._sweep_secs.setSingleStep(0.5)
        self._sweep_secs.setSuffix(" s")
        dur_form.addRow("Sweep time", self._sweep_secs)
        sweep_layout.addLayout(dur_form)

        layout.addWidget(sweep_box)

        # animation timer (drives the slider forward while playing)
        self._sweep_lo = 0.0
        self._sweep_hi = 1.0
        self._sweep_timer = QTimer(self)
        self._sweep_timer.setInterval(33)  # ~30 fps
        self._sweep_timer.timeout.connect(self._on_sweep_tick)

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

        self._cmap = QComboBox()
        # jet first to match the method's MATLAB heritage; perceptual options after
        self._cmap.addItems(["jet", "turbo", "viridis", "plasma", "coolwarm", "RdBu_r"])
        self._cmap.currentTextChanged.connect(self.colormap_changed.emit)
        appear_form.addRow("Colormap", self._cmap)
        layout.addWidget(appear_box)

        # --- Volume ------------------------------------------------------
        vol_box = QGroupBox("Volume")
        vol_form = QFormLayout(vol_box)
        self._grid_res = QSpinBox()
        self._grid_res.setRange(16, 160)
        self._grid_res.setValue(48)
        vol_form.addRow("Grid resolution", self._grid_res)

        self._time_scale = QDoubleSpinBox()
        self._time_scale.setRange(0.1, 50.0)
        self._time_scale.setValue(4.0)
        self._time_scale.setSingleStep(0.5)
        vol_form.addRow("Loaf aspect (H/W)", self._time_scale)

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

    def set_sweep_range(self, lo: float, hi: float) -> None:
        """Set the amplitude range the sweep slider spans (from the new volume)."""
        if not (hi > lo):
            hi = lo + 1.0
        self._sweep_lo, self._sweep_hi = float(lo), float(hi)
        self._sweep_value.blockSignals(True)
        self._sweep_value.setRange(self._sweep_lo, self._sweep_hi)
        step = (self._sweep_hi - self._sweep_lo) / 100.0
        self._sweep_value.setSingleStep(step if step > 0 else 0.01)
        self._sweep_value.setValue(self._sweep_lo)
        self._sweep_value.blockSignals(False)
        self._sweep_slider.blockSignals(True)
        self._sweep_slider.setValue(0)
        self._sweep_slider.blockSignals(False)

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

    # ---- sweep ----------------------------------------------------------

    def _slider_to_value(self, s: int) -> float:
        frac = s / _SWEEP_STEPS
        return self._sweep_lo + frac * (self._sweep_hi - self._sweep_lo)

    def _value_to_slider(self, v: float) -> int:
        span = self._sweep_hi - self._sweep_lo
        if span <= 0:
            return 0
        frac = (v - self._sweep_lo) / span
        return int(round(max(0.0, min(1.0, frac)) * _SWEEP_STEPS))

    def _on_sweep_enable(self, on: bool) -> None:
        self._sweep_slider.setEnabled(on)
        self._sweep_value.setEnabled(on)
        self._sweep_play.setEnabled(on)
        # disable the static nested-value controls while sweeping (mutually exclusive)
        self._count.setEnabled(not on)
        for i, spin in enumerate(self._iso_spins):
            spin.setEnabled(not on and i < self._count.value())
        if not on:
            self._sweep_play.setChecked(False)  # stops the timer via _on_sweep_play
        self.sweep_toggled.emit(on)
        if on:
            self.sweep_value_changed.emit(self._slider_to_value(self._sweep_slider.value()))

    def _on_sweep_slider(self, s: int) -> None:
        value = self._slider_to_value(s)
        self._sweep_value.blockSignals(True)
        self._sweep_value.setValue(value)
        self._sweep_value.blockSignals(False)
        self.sweep_value_changed.emit(value)

    def _on_sweep_spin(self, value: float) -> None:
        self._sweep_slider.blockSignals(True)
        self._sweep_slider.setValue(self._value_to_slider(value))
        self._sweep_slider.blockSignals(False)
        self.sweep_value_changed.emit(value)

    def _on_sweep_play(self, playing: bool) -> None:
        self._sweep_play.setText("❚❚ Pause" if playing else "▶ Play")
        if playing:
            # if parked at the very top, restart from the bottom
            if self._sweep_slider.value() >= _SWEEP_STEPS:
                self._sweep_slider.setValue(0)
            self._sweep_timer.start()
        else:
            self._sweep_timer.stop()

    def _on_sweep_tick(self) -> None:
        # advance so a full low->high sweep takes the configured number of seconds
        per_tick = _SWEEP_STEPS * (self._sweep_timer.interval() / 1000.0) / self._sweep_secs.value()
        nxt = self._sweep_slider.value() + max(1, int(round(per_tick)))
        if nxt >= _SWEEP_STEPS:
            if self._sweep_loop.isChecked():
                nxt = nxt - _SWEEP_STEPS
            else:
                nxt = _SWEEP_STEPS
                self._sweep_play.setChecked(False)  # stops at the top
        self._sweep_slider.setValue(nxt)
