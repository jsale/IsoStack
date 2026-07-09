"""Unified entry point: dispatch a file path to the right EEG importer.

CSV/TSV/text go through the hardened pandas reader; everything else
(EDF/FIF/BrainVision/EEGLAB/...) goes through the MNE backend.
"""

from __future__ import annotations

import os

import numpy as np

from . import csv_importer, mne_importer
from .csv_importer import EEGRecording

_CSV_EXTENSIONS = {".csv", ".tsv", ".txt", ".asc", ".dat"}

# Qt file-dialog filter string.
OPEN_FILTER = (
    "EEG/MEG data ("
    "*.csv *.tsv *.txt *.edf *.bdf *.gdf *.fif *.vhdr *.set *.cnt *.eeg *.mat"
    ");;"
    "CSV/text (*.csv *.tsv *.txt *.asc *.dat);;"
    "EDF/BDF (*.edf *.bdf *.gdf);;"
    "Neuromag FIFF (*.fif);;"
    "BrainVision (*.vhdr);;"
    "EEGLAB (*.set);;"
    "All files (*)"
)


def load_recording(path: str) -> EEGRecording:
    """Load any supported EEG/MEG file into an EEGRecording."""
    ext = os.path.splitext(path)[1].lower()
    if ext in _CSV_EXTENSIONS:
        return csv_importer.load_csv(path)
    return mne_importer.load_recording(path)


def segment_recording(
    rec: EEGRecording,
    start: float | None = None,
    end: float | None = None,
    max_slices: int = 200,
) -> EEGRecording:
    """Return a time-windowed, decimated view of a recording.

    Real recordings run to tens of thousands of samples; the loaf builds one
    RBF interpolation per time slice, so a full file is slow and unreadable.
    This selects the ``[start, end]`` window (in the recording's own time
    units) and then evenly strides it down to at most ``max_slices`` slices.
    The full recording is left untouched so the window can be changed and
    re-applied without reloading.
    """
    t = rec.times
    lo = t[0] if start is None else start
    hi = t[-1] if end is None else end
    idx = np.nonzero((t >= lo) & (t <= hi))[0]
    if idx.size == 0:                       # empty/invalid window -> keep all
        idx = np.arange(t.shape[0])
    if max_slices > 0 and idx.size > max_slices:
        stride = int(np.ceil(idx.size / max_slices))
        idx = idx[::stride]
    return EEGRecording(times=t[idx], labels=rec.labels, values=rec.values[idx])
