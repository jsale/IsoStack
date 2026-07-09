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
    section_toggled = Signal(bool)        # cross-section panel on/off
    section_changed = Signal(int)         # current cross-section slice index
    clim_changed = Signal()               # color range (auto flag or values) changed

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

        # Color range: by default the colormap spans the data min/max; unchecking
        # 'Auto' lets you clamp blue->red to a range of interest (e.g. -100..100)
        # so mid-range detail isn't washed out by outliers.
        self._clim_auto = QCheckBox("Auto color range")
        self._clim_auto.setChecked(True)
        self._clim_auto.toggled.connect(self._on_clim_auto)
        appear_form.addRow(self._clim_auto)

        cr_row = QHBoxLayout()
        self._clim_min = QDoubleSpinBox()
        self._clim_min.setRange(-1e6, 1e6)
        self._clim_min.setDecimals(2)
        self._clim_min.setEnabled(False)
        self._clim_max = QDoubleSpinBox()
        self._clim_max.setRange(-1e6, 1e6)
        self._clim_max.setDecimals(2)
        self._clim_max.setEnabled(False)
        for w in (self._clim_min, self._clim_max):
            w.valueChanged.connect(self._on_clim_edited)
        cr_row.addWidget(QLabel("min"))
        cr_row.addWidget(self._clim_min, 1)
        cr_row.addWidget(QLabel("max"))
        cr_row.addWidget(self._clim_max, 1)
        appear_form.addRow(cr_row)
        layout.addWidget(appear_box)

        # --- Segment -----------------------------------------------------
        # Real recordings run to tens of thousands of samples; pick a time
        # window and cap the slice count so the loaf builds fast and reads well.
        seg_box = QGroupBox("Segment (time window)")
        seg_form = QFormLayout(seg_box)
        self._seg_start = QDoubleSpinBox()
        self._seg_start.setRange(0.0, 1e9)
        self._seg_start.setDecimals(3)
        seg_form.addRow("Start", self._seg_start)

        self._seg_end = QDoubleSpinBox()
        self._seg_end.setRange(0.0, 1e9)
        self._seg_end.setDecimals(3)
        seg_form.addRow("End", self._seg_end)

        self._seg_max = QSpinBox()
        self._seg_max.setRange(20, 4000)
        self._seg_max.setValue(200)
        self._seg_max.setToolTip("Cap on time slices; the window is evenly decimated to this many.")
        seg_form.addRow("Max slices", self._seg_max)
        layout.addWidget(seg_box)

        # Editing the window auto-rebuilds, debounced so dragging a spin box
        # doesn't fire a rebuild per increment. Programmatic set_time_extent()
        # blocks these signals, so loading a file doesn't double-build.
        self._seg_timer = QTimer(self)
        self._seg_timer.setSingleShot(True)
        self._seg_timer.setInterval(400)
        self._seg_timer.timeout.connect(self._emit_rebuild)
        for w in (self._seg_start, self._seg_end, self._seg_max):
            w.valueChanged.connect(lambda *_: self._seg_timer.start())

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

        # --- Cross-section ----------------------------------------------
        # Slide a horizontal plane through the loaf; the 2D scalp map at that
        # time updates live in the docked topograph panel.
        sec_box = QGroupBox("Cross-section (scalp map)")
        sec_layout = QVBoxLayout(sec_box)
        self._section_enable = QCheckBox("Show cross-section")
        self._section_enable.toggled.connect(self._on_section_enable)
        sec_layout.addWidget(self._section_enable)

        self._section_slider = QSlider(Qt.Horizontal)
        self._section_slider.setRange(0, 0)
        self._section_slider.setEnabled(False)
        self._section_slider.valueChanged.connect(self.section_changed.emit)
        sec_layout.addWidget(self._section_slider)
        layout.addWidget(sec_box)

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

    def set_time_extent(self, t0: float, t1: float) -> None:
        """Configure the segment window to span a newly loaded recording."""
        if not (t1 > t0):
            t1 = t0 + 1.0
        for spin in (self._seg_start, self._seg_end):
            spin.blockSignals(True)
            spin.setRange(float(t0), float(t1))
        self._seg_start.setValue(float(t0))
        self._seg_end.setValue(float(t1))
        for spin in (self._seg_start, self._seg_end):
            spin.blockSignals(False)

    def current_segment(self) -> tuple[float, float, int]:
        """Return (start, end, max_slices) for the current time window."""
        return self._seg_start.value(), self._seg_end.value(), self._seg_max.value()

    def _emit_rebuild(self) -> None:
        self.rebuild_requested.emit(self._grid_res.value(), self._time_scale.value())

    # ---- cross-section --------------------------------------------------

    def set_section_range(self, n_slices: int) -> None:
        """Set the cross-section slider to span a volume's time slices."""
        hi = max(0, n_slices - 1)
        cur = self._section_slider.value()
        self._section_slider.blockSignals(True)
        self._section_slider.setRange(0, hi)
        self._section_slider.setValue(min(cur, hi))
        self._section_slider.blockSignals(False)

    def current_section(self) -> int:
        return self._section_slider.value()

    def section_active(self) -> bool:
        return self._section_enable.isChecked()

    def _on_section_enable(self, on: bool) -> None:
        self._section_slider.setEnabled(on)
        self.section_toggled.emit(on)
        if on:
            self.section_changed.emit(self._section_slider.value())

    # ---- color range ----------------------------------------------------

    def color_auto(self) -> bool:
        return self._clim_auto.isChecked()

    def current_color_range(self) -> tuple[float, float]:
        return self._clim_min.value(), self._clim_max.value()

    def set_color_range(self, lo: float, hi: float) -> None:
        """Display a data range in the min/max boxes without emitting changes."""
        for w in (self._clim_min, self._clim_max):
            w.blockSignals(True)
        self._clim_min.setValue(float(lo))
        self._clim_max.setValue(float(hi))
        for w in (self._clim_min, self._clim_max):
            w.blockSignals(False)

    def _on_clim_auto(self, auto: bool) -> None:
        self._clim_min.setEnabled(not auto)
        self._clim_max.setEnabled(not auto)
        self.clim_changed.emit()

    def _on_clim_edited(self, _value: float) -> None:
        if not self._clim_auto.isChecked():
            self.clim_changed.emit()

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
