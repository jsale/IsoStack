"""Export helpers: isosurface meshes to STL/OBJ and viewport to PNG."""

from __future__ import annotations


def export_mesh(mesh, path: str) -> None:
    """Write a surface mesh to .stl or .obj (chosen by file extension)."""
    lower = path.lower()
    if lower.endswith(".stl"):
        mesh.extract_surface().triangulate().save(path)
    elif lower.endswith(".obj"):
        # PyVista/VTK OBJ export goes through the render window; for a bare mesh
        # we write via meshio-style save if available, else fall back to STL-like.
        import pyvista as pv

        surf = mesh.extract_surface().triangulate()
        pv.save_meshio(path, surf)
    else:
        raise ValueError(f"Unsupported mesh extension for {path!r}; use .stl or .obj")


def export_scene_obj(plotter, path: str) -> None:
    """Export the full rendered scene (all actors) to OBJ via the render window."""
    plotter.export_obj(path)


def save_png(plotter, path: str, scale: int = 2) -> None:
    """Save a PNG snapshot of the current view."""
    plotter.screenshot(path, scale=scale)
