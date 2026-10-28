"""Shared palette and helpers for the Production mark's scenes (see build_production_logo.py)."""

INK = "#45433f"
ACCENT = "#3f7d3a"
PALE = "#d6d1c8"
MID = "#a9a49b"

# Stage groups fade/scale in and out with these.
SHOW = {"transform": "scale(1)", "opacity": 1}
HIDE = {"transform": "scale(.86)", "opacity": 0}


def stage(*pts):
    """A stage group: (offset, show?) pairs."""
    return [(o, SHOW if s else HIDE) for o, s in pts]
