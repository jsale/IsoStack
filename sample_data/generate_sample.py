"""Synthetic EEG generator — a traveling wave across the scalp over time.

Produces an EEGRecording on the standard 10-20 montage so IsoStack has something
to visualize before real data is loaded, and can also write a CSV for testing
the importer.
"""

from __future__ import annotations

import numpy as np

from isostack.data import montage
from isostack.data.csv_importer import EEGRecording


def make_synthetic_recording(n_samples: int = 80, seed: int = 0) -> EEGRecording:
    """A plane wave sweeping front-to-back plus a wandering focal blob."""
    rng = np.random.default_rng(seed)
    labels = list(montage.STANDARD_10_20.keys())
    pos = np.array([montage.STANDARD_10_20[l] for l in labels])  # (n_ch, 2)

    t = np.linspace(0.0, 1.0, n_samples)
    values = np.empty((n_samples, len(labels)), dtype=float)

    for k, tk in enumerate(t):
        # traveling plane wave along +Y (front-to-back)
        wave = np.sin(2 * np.pi * (1.5 * pos[:, 1] - 2.0 * tk))
        # a focal blob orbiting the scalp
        cx, cy = 0.6 * np.cos(2 * np.pi * tk), 0.6 * np.sin(2 * np.pi * tk)
        blob = np.exp(-((pos[:, 0] - cx) ** 2 + (pos[:, 1] - cy) ** 2) / 0.15)
        values[k] = wave + 1.5 * blob + 0.05 * rng.standard_normal(len(labels))

    return EEGRecording(times=t, labels=labels, values=values)


def write_csv(path: str, n_samples: int = 80) -> None:
    """Write the synthetic recording to a CSV (time column + one column/electrode)."""
    import pandas as pd

    rec = make_synthetic_recording(n_samples=n_samples)
    df = pd.DataFrame(rec.values, columns=rec.labels)
    df.insert(0, "time", rec.times)
    df.to_csv(path, index=False, encoding="utf-8")


if __name__ == "__main__":
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else "sample_eeg.csv"
    write_csv(out)
    print(f"wrote {out}")
