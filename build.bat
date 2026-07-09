@echo off
REM ============================================================================
REM  build.bat - Build a standalone Windows executable of IsoStack.
REM
REM  Per CLAUDE.md: build from a DEDICATED all-pip conda env (isostack_build),
REM  never from the conda-forge "isostack" env - conda-forge PySide6 splits Qt
REM  DLLs into Library\bin, which PyInstaller's hooks miss. This script creates
REM  that env on first run, then packages main.py into dist\IsoStack\.
REM
REM  Usage:   build.bat
REM  Output:  dist\IsoStack\IsoStack.exe  (onedir bundle, ~600 MB)
REM  Distribute by zipping the whole dist\IsoStack folder.
REM
REM  Overrides (optional): set CONDA_ROOT or BUILD_ENV before calling, e.g.
REM      set CONDA_ROOT=C:\Users\me\miniconda3
REM ============================================================================
setlocal enabledelayedexpansion

REM Run from the repo root (this script's directory), whatever the caller's cwd.
cd /d "%~dp0"

if "%CONDA_ROOT%"=="" set "CONDA_ROOT=%USERPROFILE%\anaconda3"
if "%BUILD_ENV%"=="" set "BUILD_ENV=isostack_build"

set "CONDA_EXE=%CONDA_ROOT%\Scripts\conda.exe"
set "BUILD_PY=%CONDA_ROOT%\envs\%BUILD_ENV%\python.exe"

if not exist "%CONDA_EXE%" (
    echo [ERROR] conda not found at "%CONDA_EXE%".
    echo         Set CONDA_ROOT to your Anaconda/Miniconda install, e.g.:
    echo             set CONDA_ROOT=C:\Users\%USERNAME%\miniconda3
    exit /b 1
)

REM --- 1. Create the dedicated build env if it doesn't exist yet --------------
if not exist "%BUILD_PY%" (
    echo [1/4] Creating build env "%BUILD_ENV%" ^(python 3.12^)...
    call "%CONDA_EXE%" create -n "%BUILD_ENV%" python=3.12 -y
    if errorlevel 1 (
        echo [ERROR] Failed to create the build env.
        exit /b 1
    )
) else (
    echo [1/4] Build env "%BUILD_ENV%" already exists - reusing it.
)

REM --- 2. Install the all-pip dependency stack -------------------------------
echo [2/4] Installing build dependencies via pip...
"%BUILD_PY%" -m pip install --upgrade pip
"%BUILD_PY%" -m pip install numpy scipy pandas vtk pyvista pyvistaqt PySide6 mne pooch matplotlib pyinstaller
if errorlevel 1 (
    echo [ERROR] Dependency install failed.
    exit /b 1
)

REM --- 3. Clean previous build artifacts -------------------------------------
echo [3/4] Cleaning previous build/dist...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

REM --- 4. Package with PyInstaller -------------------------------------------
REM  collect-all: pull every submodule + data file for libraries that load
REM  things dynamically (VTK/pyvista) or ship data (matplotlib fonts).
REM  mne: use collect-SUBMODULES (+ its data), NOT collect-all. mne lazy-loads
REM  most of itself via lazy_loader, so all its submodules must be bundled; but
REM  --collect-all mne ALSO sweeps binaries and drags conda's Library\bin ICU
REM  DLLs (icuuc/icudt) into the bundle, which clash with PySide6's Qt and cause
REM  "DLL load failed importing QtWidgets: procedure not found". Submodules+data
REM  gets mne working without that clash.
REM  hidden-import: sample_data.generate_sample is imported inside a function,
REM  so static analysis misses it.
echo [4/4] Running PyInstaller...
"%BUILD_PY%" -m PyInstaller --noconfirm --windowed --name IsoStack ^
    --collect-all vtkmodules ^
    --collect-all vtk ^
    --collect-all pyvista ^
    --collect-all pyvistaqt ^
    --collect-all matplotlib ^
    --collect-submodules mne ^
    --collect-data mne ^
    --collect-submodules pooch ^
    --hidden-import lazy_loader ^
    --hidden-import sample_data.generate_sample ^
    main.py
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    exit /b 1
)

echo.
echo ============================================================================
echo  Build complete:  dist\IsoStack\IsoStack.exe
echo  First launch takes ~5 s (loads DLLs + builds matplotlib's font cache).
echo  To distribute, zip the entire  dist\IsoStack  folder.
echo ============================================================================
endlocal
