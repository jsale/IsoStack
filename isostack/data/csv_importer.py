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

_TIME_COLS = {"time", "t", "sample", "samples", "index", "timestamp"}


@dataclass
class EEGRecording:
    times: np.ndarray          # shape (n_samples,)
    labels: list[str]          # length n_channels
    values: np.ndarray         # shape (n_samples, n_channels)

    @property
    def n_samples(self) -> int:
        return self.values.shape[0]

    @property
    def n_channels(self) -> int:
        return self.values.shape[1]


def load_csv(path: str) -> EEGRecording:
    """Load an EEG CSV into an EEGRecording."""
    df = pd.read_csv(path)

    time_col = next((c for c in df.columns if str(c).strip().lower() in _TIME_COLS), None)
    if time_col is not None:
        times = df[time_col].to_numpy(dtype=float)
        df = df.drop(columns=[time_col])
    else:
        times = np.arange(len(df), dtype=float)

    labels = [str(c).strip() for c in df.columns]
    values = df.to_numpy(dtype=float)
    return EEGRecording(times=times, labels=labels, values=values)
