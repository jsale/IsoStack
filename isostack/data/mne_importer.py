"""Import real EEG/MEG recordings via MNE-Python into an EEGRecording.

One backend covers the binary formats IsoStack cares about — EDF/EDF+ (``.edf``,
``.bdf``), Neuromag/MNE FIFF (``.fif``), BrainVision (``.vhdr`` + its ``.eeg``/
``.vmrk`` siblings), and EEGLAB (``.set``) — because MNE reads them all into a
uniform ``Raw`` object. We keep *every* channel here and let the montage
resolver downstream pick the ones with scalp positions, so a file's non-scalp
channels (EOG/EMG/resp/stim) don't need special-casing at read time.

MNE is an optional dependency; import errors are surfaced with an actionable
message rather than a bare ``ModuleNotFoundError``.
"""

from __future__ import annotations

import os

import numpy as np

from .csv_importer import EEGRecording

# extension -> mne.io reader function name. Point BrainVision at the .vhdr
# header (not the .eeg binary); EEGLAB .set is itself a MATLAB file.
_READERS: dict[str, str] = {
    ".edf": "read_raw_edf",
    ".bdf": "read_raw_bdf",
    ".gdf": "read_raw_gdf",
    ".fif": "read_raw_fif",
    ".vhdr": "read_raw_brainvision",
    ".set": "read_raw_eeglab",
    ".cnt": "read_raw_cnt",
}

# Extensions we accept in the open dialog but must redirect, because the file is
# a companion of another file the reader actually opens.
_REDIRECT = {
    ".eeg": "BrainVision data — open the matching '.vhdr' header file instead.",
    ".vmrk": "BrainVision markers — open the matching '.vhdr' header file instead.",
    ".mat": (
        "Bare '.mat' is ambiguous. If this is an EEGLAB dataset, open its "
        "'.set' file. FieldTrip/custom matrices aren't auto-detectable."
    ),
}

SUPPORTED_EXTENSIONS = tuple(_READERS) + (".eeg", ".vmrk", ".mat")


def can_load(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in _READERS


def load_recording(path: str) -> EEGRecording:
    """Read a binary EEG/MEG file into an EEGRecording via MNE.

    Raises ValueError with a friendly message for unsupported extensions,
    companion files (.eeg/.vmrk), or a missing MNE install.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in _REDIRECT:
        raise ValueError(_REDIRECT[ext])
    reader_name = _READERS.get(ext)
    if reader_name is None:
        raise ValueError(f"Unsupported format {ext!r} for MNE import.")

    try:
        import mne
    except ImportError as exc:  # pragma: no cover - env-dependent
        raise ValueError(
            "Reading this format needs MNE-Python. Install it into the env:\n"
            "    python -m pip install mne"
        ) from exc

    reader = getattr(mne.io, reader_name)
    # preload=True: we need the samples in memory to build the loaf anyway.
    raw = reader(path, preload=True, verbose="ERROR")

    labels = list(raw.ch_names)
    times = np.asarray(raw.times, dtype=float)          # seconds from record start
    values = np.asarray(raw.get_data(), dtype=float).T   # (n_samples, n_channels)
    values = _to_microvolts(values)
    positions = _montage_positions(raw)

    return EEGRecording(times=times, labels=labels, values=values, positions=positions)


def _montage_positions(raw) -> dict[str, tuple[float, float]] | None:
    """Read the file's own electrode montage as 2D scalp positions, or None.

    MNE head coordinates are +X=right, +Y=front(nose), +Z=up, so a top-down
    scalp view is just (x, y). Positions are normalized so the outermost sensor
    lands on the unit disk, matching the app's montage convention (nose=+Y,
    right ear=+X). Returns None if the file carries no usable locations.
    """
    try:
        montage = raw.get_montage()
        if montage is None:
            return None
        ch_pos = (montage.get_positions() or {}).get("ch_pos") or {}
    except Exception:
        return None

    xy: dict[str, tuple[float, float]] = {}
    for label, xyz in ch_pos.items():
        xyz = np.asarray(xyz, dtype=float)
        if xyz.shape != (3,) or not np.all(np.isfinite(xyz[:2])):
            continue
        xy[label] = (float(xyz[0]), float(xyz[1]))
    if len(xy) < 3:
        return None

    radius = max(np.hypot(x, y) for x, y in xy.values())
    if not np.isfinite(radius) or radius <= 0:
        return None
    return {label: (x / radius, y / radius) for label, (x, y) in xy.items()}


def _to_microvolts(values: np.ndarray) -> np.ndarray:
    """Rescale volt-magnitude data to microvolts.

    MNE returns EEG in SI volts (~5e-5 V), which makes iso-values and the
    colorbar read as ~0.000 and contour at invisible magnitudes. If the signal
    is clearly volt-scale (99th-pct |amplitude| < 1e-2), convert to µV so the
    numbers match the app's synthetic/CSV data. Data already in µV is untouched.
    """
    finite = values[np.isfinite(values)]
    if finite.size and np.percentile(np.abs(finite), 99) < 1e-2:
        return values * 1e6
    return values
