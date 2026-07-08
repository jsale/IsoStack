"""IsoStack — spatiotemporal isosurface visualization for EEG/MEG data."""

__version__ = "0.1.0"


def _ensure_dll_path() -> None:
    """Add the interpreter's ``Library/bin`` to the DLL search path on Windows.

    When ``python.exe`` is launched without the conda env activated (or from a
    frozen build), scipy's BLAS/LAPACK-backed extensions can fail to locate
    OpenBLAS and crash natively on the first linear-algebra call. Registering the
    directory explicitly makes the app work regardless of activation.
    """
    import os
    import sys

    if os.name != "nt":
        return
    dll_dir = os.path.join(sys.prefix, "Library", "bin")
    if os.path.isdir(dll_dir):
        try:
            os.add_dll_directory(dll_dir)
        except (OSError, AttributeError):
            pass
        os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")


_ensure_dll_path()
