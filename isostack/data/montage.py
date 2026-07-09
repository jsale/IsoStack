"""Electrode-label -> 2D scalp position mapping.

Positions are given in a normalized head disk: the scalp is the unit circle,
nose toward +Y, right ear toward +X, Cz at the origin. These are the standard
projected coordinates for the International 10-20 system (and its 10-10 infills).

Old and new label spellings are both recognized (e.g. T3 == T7, T5 == P7).
Column matching is case-insensitive.
"""

from __future__ import annotations

# label -> (x, y) in the unit head disk (nose = +Y, right ear = +X)
STANDARD_10_20: dict[str, tuple[float, float]] = {
    # Frontopolar
    "Fp1": (-0.31, 0.95), "Fpz": (0.0, 1.0), "Fp2": (0.31, 0.95),
    # Frontal
    "F7": (-0.81, 0.59), "F3": (-0.40, 0.67), "Fz": (0.0, 0.71),
    "F4": (0.40, 0.67), "F8": (0.81, 0.59),
    # Fronto-central / temporal-anterior
    "FC5": (-0.60, 0.34), "FC1": (-0.21, 0.38), "FC2": (0.21, 0.38), "FC6": (0.60, 0.34),
    # Central / temporal
    "T7": (-1.0, 0.0), "C3": (-0.50, 0.0), "Cz": (0.0, 0.0),
    "C4": (0.50, 0.0), "T8": (1.0, 0.0),
    # Centro-parietal
    "CP5": (-0.60, -0.34), "CP1": (-0.21, -0.38), "CP2": (0.21, -0.38), "CP6": (0.60, -0.34),
    # Parietal
    "P7": (-0.81, -0.59), "P3": (-0.40, -0.67), "Pz": (0.0, -0.71),
    "P4": (0.40, -0.67), "P8": (0.81, -0.59),
    # Occipital
    "O1": (-0.31, -0.95), "Oz": (0.0, -1.0), "O2": (0.31, -0.95),
}

# Legacy spellings -> canonical
ALIASES: dict[str, str] = {
    "T3": "T7", "T4": "T8", "T5": "P7", "T6": "P8",
}

# Common reference tags that appear as a suffix on referential montages, e.g.
# "Fp1-REF", "O2-LE", "C3-AVG", "F7-A1". Stripping the reference leaves the
# electrode's own label, which does have a scalp position. (True *bipolar*
# derivations like "Fpz-Cz" are a difference of two sites with no single
# position, so we only strip these known reference tokens, not any hyphenated
# tail.)
_REFERENCE_TOKENS = {
    "ref", "le", "re", "avg", "car", "cz", "ref1", "ref2",
    "a1", "a2", "m1", "m2", "a1a2", "m1m2", "linked", "avr",
}

# Column headers that are never electrodes.
_PREFIXES = ("eeg ", "eeg_", "eeg-")


def normalize_label(label: str) -> str:
    """Reduce a raw column/channel label toward its bare electrode name.

    Handles the two shapes seen in real exports: an ``EEG `` type prefix
    (MNE/EDF, e.g. ``"EEG Fpz"``) and a trailing reference token
    (clinical CSV/EDF, e.g. ``"Fp1-REF"`` -> ``"Fp1"``).
    """
    # trailing '.' padding is how EEGBCI/EDF pad names to fixed width ("C3..")
    key = label.strip().strip(".").strip()
    low = key.lower()
    for pre in _PREFIXES:
        if low.startswith(pre):
            key = key[len(pre):].strip()
            low = key.lower()
            break
    # strip a single trailing reference token after a '-' (or ' ')
    for sep in ("-", " "):
        if sep in key:
            head, _, tail = key.rpartition(sep)
            if head and tail.lower() in _REFERENCE_TOKENS:
                key = head.strip()
                break
    return key.strip().strip(".").strip()


def _canonical(label: str) -> str:
    key = normalize_label(label)
    # direct hit (case-insensitive)
    for name in STANDARD_10_20:
        if name.lower() == key.lower():
            return name
    for old, new in ALIASES.items():
        if old.lower() == key.lower():
            return new
    return key


def position(label: str) -> tuple[float, float] | None:
    """Return the (x, y) scalp position for an electrode label, or None if unknown."""
    canon = _canonical(label)
    return STANDARD_10_20.get(canon)


def resolve_labels(labels: list[str]) -> tuple[list[str], list[tuple[float, float]], list[str]]:
    """Split incoming column labels into (known, positions, unknown).

    Returns the known labels in input order, their (x, y) positions, and any
    labels that could not be matched to the montage.
    """
    known: list[str] = []
    positions: list[tuple[float, float]] = []
    unknown: list[str] = []
    for label in labels:
        pos = position(label)
        if pos is None:
            unknown.append(label)
        else:
            known.append(label)
            positions.append(pos)
    return known, positions, unknown
