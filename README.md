# IsoStack

**Spatiotemporal isosurface visualization for EEG / MEG data.**

Traditional isosurfaces use three *spatial* dimensions (atomic orbitals, anatomy).
IsoStack instead devotes one axis to a **spatial parameter** — most commonly time —
so a stack of 2D scalp topographic maps becomes a 3D volume `V(x, y, t)`. Extracting
isosurfaces from that volume (one or several amplitude values at once) reveals
spatiotemporal structure that is very hard to see in a sequence of flat 2D maps.

The method: take a sequence of 2D EEG/MEG topographic maps over time, stack them
"like a loaf of bread," and isosurface the loaf. Pioneered on EEG/MEG sleep data
(work with Dr. David Shannahoff-Khalsa).

## Features (target)

- Import standard 2D CSV EEG (rows = time samples, columns = electrodes)
- Auto-sort/place columns by electrode label using standard montages (10–20 and beyond)
- Build the spatiotemporal volume by interpolating each time slice onto a scalp grid
- Extract **multiple isosurfaces at once**, each with its own color/opacity
- Full labeled axes (scalp X/Y, time Z), mouse orbit / pan / zoom, camera presets
- **Stereographic 3D** viewing: cross-eye side-by-side, anaglyph (red/cyan), interlaced, checkerboard, and active-shutter (Crystal Eyes)
- Mouse **value probing**
- Save **PNG** snapshots
- Export meshes to **.stl** and **.obj**

## Stack

Python 3.12 · PySide6 (Qt6) · PyVista / VTK · NumPy · SciPy · pandas

## Quick start

```bash
conda env create -f environment.yml
conda activate isostack
python main.py
```

On first launch, with no data loaded, IsoStack renders a **synthetic traveling-wave
EEG** volume so you can exercise the viewer immediately.

## Project layout

```
IsoStack/
├── main.py                     # entry point
├── isostack/
│   ├── data/
│   │   ├── montage.py          # electrode label -> 2D scalp position
│   │   └── csv_importer.py     # CSV -> (times, labels, values)
│   ├── volume/
│   │   └── builder.py          # stacked V(x, y, t) volume construction
│   ├── gui/
│   │   ├── main_window.py      # top-level window, menus, layout
│   │   ├── viewer.py           # embedded PyVista/VTK render widget
│   │   └── controls.py         # isosurface / parameter control panel
│   └── export/
│       └── mesh_export.py      # STL / OBJ / PNG export helpers
└── sample_data/
    └── generate_sample.py      # synthetic EEG generator
```

## Status

Early scaffold. See the plan of action in the project notes.
