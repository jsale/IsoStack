"""Import 2D EEG CSV files into (times, labels, values).

Expected layout: rows are time samples, columns are electrodes. An optional
leading time/index column (named 'time', 't', 'sample', or 'index',
case-insensitive) is detected and used for the time axis; otherwise a simple
integer sample index is generated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

_TIME_COLS = {"time", "t", "sample", "samples", "index", "timestamp", "times"}

# Non-electrode columns that clinical/BCI exports interleave with the signal:
# event/trigger channels, annotation strings, and status flags. Dropped before
# the numeric cast so a stray "1:18:48 PM" timestamp can't poison the whole load.
_NON_ELECTRODE_COLS = {
    "event", "events", "annotation", "annotations", "status",
    "trigger", "triggers", "marker", "markers", "stim", "stimulus",
}


@dataclass
class EEGRecording:
    times: np.ndarray          # shape (n_samples,)
    labels: list[str]          # length n_channels
    values: np.ndarray         # shape (n_samples, n_channels)
    # Optional per-electrode 2D scalp positions read from the file's own montage
    # (label -> (x, y) in the unit head disk). When present these override the
    # standard-10-20 name lookup, so files with non-standard channel names but
    # embedded sensor coordinates (typical EEGLAB .set / FIFF) still resolve.
    positions: dict[str, tuple[float, float]] | None = None

    @property
    def n_samples(self) -> int:
        return self.values.shape[0]

    @property
    def n_channels(self) -> int:
        return self.values.shape[1]


def load_csv(path: str) -> EEGRecording:
    """Load an EEG CSV into an EEGRecording.

    Robust to real-world exports: the delimiter is sniffed (comma, semicolon,
    tab, whitespace), an empty trailing column from a dangling delimiter is
    dropped, event/annotation/timestamp columns are removed, and each remaining
    column is coerced to numeric — any column that still won't parse (e.g. a
    wall-clock timestamp) is dropped rather than crashing the whole load.
    """
    # sep=None + python engine sniffs the delimiter (handles ';' clinical exports)
    df = pd.read_csv(path, sep=None, engine="python", skipinitialspace=True)
    df.columns = [str(c).strip() for c in df.columns]

    # A dangling trailing delimiter yields an empty 'Unnamed: N' column.
    df = df.drop(columns=[c for c in df.columns if c == "" or c.startswith("Unnamed:")])

    # Pull out an explicit time column before dropping other non-signal columns.
    time_col = next((c for c in df.columns if c.lower() in _TIME_COLS), None)
    if time_col is not None:
        times = pd.to_numeric(df[time_col], errors="coerce").to_numpy(dtype=float)
        df = df.drop(columns=[time_col])
    else:
        times = np.arange(len(df), dtype=float)

    # Drop known non-electrode columns (event/trigger/annotation/status/...).
    df = df.drop(columns=[c for c in df.columns if c.lower() in _NON_ELECTRODE_COLS])

    # Coerce every remaining column to numeric; drop any that are entirely
    # non-numeric (e.g. a trailing "1:18:48 PM" timestamp with no header).
    numeric = df.apply(pd.to_numeric, errors="coerce")
    numeric = numeric.dropna(axis=1, how="all")
    if numeric.shape[1] == 0:
        raise ValueError(
            "No numeric electrode columns found after parsing "
            f"{path!r}. Detected columns: {list(df.columns)}"
        )

    labels = [str(c).strip() for c in numeric.columns]
    values = numeric.to_numpy(dtype=float)
    return EEGRecording(times=times, labels=labels, values=values)
