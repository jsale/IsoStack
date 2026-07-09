# IsoStack — Project Context for Claude

## What this is

IsoStack is a **spatiotemporal isosurface visualizer for EEG/MEG data**, and a
**standalone project — not part of GlyphViz** (though the developer, Jeff, also
builds GlyphViz in a sibling repo). Do not share code between the two.

**The method (Jeff's own, pioneered ~36 years ago, originally on AVS):** a normal
isosurface uses three *spatial* dimensions. IsoStack instead devotes one axis to a
*spatial parameter* — usually **time**. A sequence of 2D scalp topographic maps is
stacked "like a loaf of bread" into a volume `V(x, y, t)`, and isosurfaces are
extracted from that loaf. Viewing **several iso-values at once** (nested surfaces)
reveals spatiotemporal structure that is hard to see in a sequence of flat 2D maps.
Origin: EEG/MEG sleep work with Dr. David Shannahoff-Khalsa.

**Reference look Jeff is matching:** tall vertical loaves (long axis = time,
horizontal cross-section = scalp with Front/Back/Left/Right orientation), surfaces
colored by amplitude through a **jet** colormap with a colorbar, nested low(blue)→
high(red) iso-levels. Advanced target: 7 side-by-side loaves (one per EEG frequency
band) plus a sleep-stage hypnogram (W/R/1–4) aligned to the time axis.

## Tech stack

Python 3.12 · PySide6 (Qt6) · PyVista / VTK · NumPy · SciPy · pandas.

VTK (via PyVista) was chosen deliberately over hand-rolled OpenGL: it provides
marching cubes, mouse probing, labeled axes, camera control, STL/OBJ export, PNG,
and stereo for free. "Build from scratch" means build the *app* from scratch, using
capable libraries — not reimplement marching cubes.

## Running the app

Normal run (activate the env so DLLs resolve):
```
conda activate isostack
python main.py
```

Calling the env's `python.exe` **directly** (unactivated) also works because
`isostack/__init__.py` runs a DLL-path bootstrap — but see gotcha #2 below for why
that bootstrap exists. Never use `conda run -n ... ` (it hangs on Jeff's Windows
setup). The env python is `C:\Users\jsale\anaconda3\envs\isostack\python.exe`.

On launch with no data, the app renders a synthetic traveling-wave EEG loaf so the
viewer is immediately usable. **File → Open EEG CSV…** loads real data (rows = time
samples, columns = electrode labels).

## Verification pattern

Headless: montage → volume → contour → export runs fine without a display. For
anything touching the GUI/GL, verify with a **real-window launch + screenshot**
(a `QApplication` + `MainWindow`, `QTimer.singleShot` to screenshot then quit) —
**do NOT use `QT_QPA_PLATFORM=offscreen`**, which crashes VTK's GL context
(stack overflow). See scratch scripts from the initial build for the pattern.

## Windows environment gotchas (both cost real debugging time — do not relearn)

1. **Never mix pip PySide6 with VTK's conda-forge `qt6-main`.** Two Qt6 builds of
   the same version shadow each other's DLLs → `from PySide6 import QtCore` crashes
   with "procedure could not be found". Keep the whole Qt/VTK/numeric stack on
   **conda-forge** (`environment.yml` enforces this; `pyside6` is a conda dep, not
   pip). The all-pip alternative (see Packaging) is also self-consistent — the
   *mix* is the problem.

2. **Unactivated `python.exe` can't find the env's BLAS DLLs.** When run without the
   env activated, `Library/bin` isn't on the DLL search path, so scipy's
   BLAS-backed extensions (`RBFInterpolator`, `griddata` linear/cubic, `interpnd`)
   crash natively (exit `0xC06D02BF`) on the first linear-algebra call — while numpy
   imports fine (it vendors its own BLAS), which is deceptive. Fixed by
   `_ensure_dll_path()` in `isostack/__init__.py` (adds `sys.prefix/Library/bin` via
   `os.add_dll_directory`); `main.py` imports `isostack` **before** PySide6. This is
   NOT a numpy-version issue (downgrading numpy did not help). It also matters for
   the frozen exe.

## Interpolation

Scalp interpolation uses `scipy.interpolate.RBFInterpolator` (thin-plate spline),
not `griddata` — it is the standard smooth method for EEG topography and fills the
whole scalp disk (no hole-filling pass). Kernel is selectable via `build_volume`'s
`method` arg.

## Stereo 3D (View → Stereo 3D)

Modes: cross-eye, anaglyph (red/cyan), interlaced, checkerboard, Crystal Eyes.
Cross-eye needed two fixes on VTK's `SplitViewportHorizontal`, both in
`isostack/gui/viewer.py`:
- It renders **parallel/wall-eyed**; swap the eyes for cross-eye by negating the
  camera eye angle (`SetEyeAngle(-2.0)`) — this VTK build has **no**
  `SetStereoSwapEyes` on the render window.
- It **squashes each eye ~2× horizontally** (no aspect correction). Fix with
  `camera.SetUseExplicitAspectRatio(True)` + `SetExplicitAspectRatio(0.5 * w/h)`,
  refreshed in a `resizeEvent` override. Only split-viewport modes need this;
  overlay modes (anaglyph etc.) do not.

## Packaging (standalone Windows exe)

Just run **`build.bat`** (repo root). It creates the dedicated all-pip
`isostack_build` conda env on first run, installs the stack, and runs PyInstaller
with the right flags. Build from that all-pip env, never from the conda `isostack`
env (conda-forge PySide6 splits Qt DLLs into `Library/bin`, which PyInstaller's
hooks miss).

Flags that matter (all in `build.bat`):
- `collect_all`: `vtkmodules`, `vtk`, `pyvista`, `pyvistaqt`, **`matplotlib`**
  (pyvista needs it for colormaps — omitting it crashes with "No module named
  'matplotlib'"); hidden-import `sample_data.generate_sample` (function-level import).
- **mne: use `--collect-submodules mne` + `--collect-data mne`, NOT `--collect-all
  mne`.** mne lazy-loads its submodules (via `lazy_loader`), so all of them must be
  bundled — but `--collect-all mne` *also* sweeps binaries and, because the conda
  build env's `Library/bin` lands on PATH during analysis (via `isostack`'s
  `_ensure_dll_path`), drags conda's **ICU DLLs (`icuuc`/`icudt78`) into the
  bundle**, where they clash with PySide6's self-contained Qt →
  "DLL load failed importing QtWidgets: procedure not found". Submodules+data
  avoids the binary sweep. (Sanity check a build: `dist/IsoStack/_internal` must
  have **no** `icu*.dll` at its root.)

Output is a **onedir** bundle (~600 MB) — distribute by zipping the whole folder.
First launch is ~15–20 s (loads DLLs + builds matplotlib's font cache) before the
window appears — don't assume a hang.

To verify a *windowed* frozen exe (no console output): launch it, then check the
process `MainWindowTitle` — the real title is "IsoStack — Spatiotemporal
Isosurfaces"; a startup crash shows a window titled "Unhandled exception in script".

## Collaboration notes

- Address the developer as **Jeff**.
- Jeff has deep domain vision but likes fast, iterative, corrective rounds — ship a
  working result, then react to concrete visuals. Offer ranked recommendations over
  open-ended menus.
- Jeff prefers a selectable **option** over replacing existing behavior outright.
- Ask before committing/pushing unless told otherwise; he sometimes wants to eyeball
  a change on his display first.
- Jeff uses the **Fable** model for GUI-iteration work on this project.

## Repo

Public: https://github.com/jsale/IsoStack

## Backlog (ranked)

1. **Real-data import polish** — column sorting, montage-match reporting, missing-
   electrode handling, against a real EEG CSV's quirks.
2. **Multi-band small-multiples** — the 7-loaves-per-frequency-band layout.
3. **Sleep-stage hypnogram companion** — the aligned W/R/1–4 panel.
4. Volume-probe mode (probe arbitrary interior amplitudes, not just surfaces).
5. Single-file (onefile) exe option + a BUILD.md. (`build.bat` already produces
   the onedir bundle; see Packaging.)
