"""Standard roses: one long cane grows, the bloom opens, it is cut, then bunched.

A single hybrid-tea stem rises from the bed: compound leaves unfurl along the cane, the bud opens into
a high-centred rose, secateurs cut it, and it is bunched with two more and wrapped in a kraft sleeve.
Solid flat tonal shapes, no outlines, in the crop's rose accent.
"""

from ._cut_flowers import (LEAF, LOCAL, GONE, SHOW, cut_bunch_tracks, ground, pop, rose_bloom, rose_leaf, seq,
                           shears, sleeve, stage_track, thorn)

LABEL = "Standard roses"
SCENE_TRANSFORM = "translate(344 344) scale(1) translate(-344 -344)"

TONES = ("#7d1f3d", "#a82a52", "#c94468", "#dd6a88")
CANE = 285          # cane length of the stem that is cut
CUT_Y = 500         # where the secateurs bite


def cane(length, jitter=0):
    return (f'<path class="cane" d="M0 0 C{-5 + jitter} {-length * .3:.0f} {6 - jitter} {-length * .7:.0f} 0 {-length}" '
            f'fill="none" stroke="{LEAF}" stroke-width="11" stroke-linecap="round" pathLength="1" '
            f'stroke-dasharray="1" stroke-dashoffset="1"/>')


def stem(length, cls_bloom, grow=True):
    """A stem in its own frame: base at 0,0, bloom at the top."""
    thorns = thorn(4, -length * .22, 1) + thorn(-4, -length * .5, -1, .9) + thorn(4, -length * .78, 1, .8)
    leaves = (rose_leaf(2, -length * .3, -36, 1.0, "lf1") + rose_leaf(-2, -length * .56, -144, .95, "lf2")
              + rose_leaf(2, -length * .78, -38, .8, "lf3"))
    return f"""{thorns}
    {leaves}
    <g transform="translate(0 {-length})"><g class="mb-wrap">{rose_bloom(TONES, 1.0, cls_bloom)}</g></g>"""


def side(deg, length, k):
    """A companion stem in the bunch, fully grown, fanned out by `deg`."""
    cane_static = (f'<path d="M0 0 C{-4 * k} {-length * .3:.0f} {5 * k} {-length * .7:.0f} 0 {-length}" fill="none" '
                   f'stroke="{LEAF}" stroke-width="10" stroke-linecap="round"/>')
    leaves = rose_leaf(2, -length * .34, -34 if k > 0 else -146, .9) + rose_leaf(-2, -length * .6, -146 if k > 0 else -34, .8)
    return f"""<g transform="translate(344 566) rotate({deg})"><g class="side{'R' if k > 0 else 'L'}">
      {cane_static}
      {leaves}
      <g transform="translate(0 {-length})">{rose_bloom(TONES, .9, 's' + ('R' if k > 0 else 'L'))}</g>
    </g></g>"""


SCENE = f"""<g class="stage">
  {ground(CUT_Y)}
  {side(-21, 272, -1)}
  {side(21, 268, 1)}
  <g transform="translate(344 {CUT_Y})"><g class="main">
    {cane(CANE)}
    {stem(CANE, "mb")}
  </g></g>
  {sleeve(210, 452, 568, 526)}
  <g transform="translate(322 {CUT_Y})">{shears()}</g>
  </g>"""

LOOP_MS = 6400


def _open(sel, origin, frm, to, lo, hi, prop="rotate"):
    a = f"{prop}({frm}deg)" if prop == "rotate" else f"{prop}({frm})"
    b = f"{prop}({to}deg)" if prop == "rotate" else f"{prop}({to})"
    return (sel, origin, seq({"transform": a}, (lo, {"transform": a}), (hi, {"transform": b})))


LOOP = [
    stage_track(),
    (".cane", None, seq({"strokeDashoffset": 1}, (0.04, {"strokeDashoffset": 1}), (0.24, {"strokeDashoffset": 0}))),
    pop(".lf1", 0.09, 0.15), pop(".lf2", 0.14, 0.20), pop(".lf3", 0.19, 0.25),
    pop(".mb-wrap", 0.23, 0.30),
    _open(".mb-bud", "view-box|0px -8px", ".6", "1", 0.28, 0.44, "scale"),
    _open(".mb-pl", "view-box|-8px -30px", 44, 0, 0.30, 0.46),
    _open(".mb-pr", "view-box|8px -30px", -44, 0, 0.30, 0.46),
    _open(".mb-fl", "view-box|0px -4px", ".82", "1", 0.32, 0.46, "scale"),
    _open(".mb-fr", "view-box|0px -4px", ".82", "1", 0.34, 0.48, "scale"),
] + cut_bunch_tracks()
