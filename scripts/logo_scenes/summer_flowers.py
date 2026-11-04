"""Summer flowers (eryngium): a branched blue thistle grows, its heads colour up, it is cut and bunched.

The stem forks into a candelabra of three heads. Each is an egg-shaped cone of tiny florets standing in a
ruff of narrow, spiny bracts, green at first and turning steel blue as it matures, the way sea holly does.
Spiny three-lobed leaves sit low on the stem. Then secateurs cut it and it is bunched with two more in a
kraft sleeve. Solid flat tonal shapes, no outlines.
"""

import math

from ._cut_flowers import (GONE, LOCAL, SHOW, cut_bunch_tracks, ground, pop, seq, shears, sleeve, stage_track)

LABEL = "Summer flowers"
SCENE_TRANSFORM = "translate(344 344) scale(1) translate(-344 -344)"

STEM = "#4f7c93"
YOUNG = {"dome": "#8fae9a", "a": "#86aa78", "b": "#a8c4a0"}
BLUE = {"dome": "#2f568f", "a": "#3b6fb6", "b": "#6b97d1"}
FLORET = "#a9c4e6"
CUT_Y = 500
CANE = 314

# (name, position of the head's base, scale); the stem forks at FORK
FORK = (0, -184)
HEADS = [("h1", (0, -312), 1.3), ("h2", (-112, -236), .98), ("h3", (114, -242), .98)]


def bract(length, fill, cls="", rot=0):
    """A narrow spiny bract standing on 0,0 and pointing up, turned by `rot` degrees."""
    L = length
    pts = [(-5.5, 0), (-3.4, -.3 * L), (-8.5, -.36 * L), (-3, -.56 * L), (-7, -.64 * L), (-1.8, -.84 * L), (0, -L),
           (1.8, -.84 * L), (7, -.64 * L), (3, -.56 * L), (8.5, -.36 * L), (3.4, -.3 * L), (5.5, 0)]
    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z"
    return f'<path class="{cls}" transform="rotate({rot})" d="{d}" fill="{fill}"/>'


def spiny_leaf(x, y, deg, s=1.0, cls=""):
    lobes = "".join(bract(L, STEM if i == 1 else "#5f8fa6", "", a) for i, (L, a) in enumerate(((58, -56), (80, 0), (58, 56))))
    return (f'<g transform="translate({x} {y}) rotate({deg}) scale({s})"><g class="{cls}">'
            f'<path d="M0 0 V16" stroke="{STEM}" stroke-width="6"/><g transform="translate(0 14)">{lobes}</g></g></g>')


def head(s, name, grow=True):
    tone = YOUNG if grow else BLUE
    """An eryngium head, base at 0,0: ruff of spiny bracts, a cone of florets, a short collar."""
    def c(k):
        return f"{k}" if grow else ""
    angles = [-168, -148, -128, -108, -88, -68, -48, -28, -8, 12, 172]
    ruff = "".join(bract(66 - 5 * (i % 3), tone["a"] if i % 2 else tone["b"], c("br-a" if i % 2 else "br-b"), a + 90)
                   for i, a in enumerate(angles))
    dots = ""
    for row, y in enumerate((-10, -22, -34, -46, -57)):
        half = 20 * math.sqrt(max(0.0, 1 - ((y + 33) / 36) ** 2))
        n = max(1, int(half * 2 // 9))
        for k in range(n + 1):
            x = -half + (k + (row % 2) * .5) * (2 * half / max(n, 1))
            if abs(x) <= half:
                dots += f'<circle cx="{x:.1f}" cy="{y}" r="2.5" fill="{FLORET}" fill-opacity=".75"/>'
    dome = (f'<path class="{c("dm")}" d="M-24 -2 C-28 -34 -12 -62 0 -69 C12 -62 28 -34 24 -2 C12 6 -12 6 -24 -2 Z" '
            f'fill="{tone["dome"]}"/>{dots}')
    collar = "".join(bract(36, tone["a"] if i % 2 else tone["b"], c("br-a" if i % 2 else "br-b"), a)
                     for i, a in enumerate((-62, -34, -10, 14, 38, 62)))
    return (f'<g transform="scale({s})"><g class="{c("hd-" + name)}">'
            f'<g class="{c("ru-" + name)}">{ruff}</g>{dome}<g class="{c("ru-" + name)}">{collar}</g></g></g>')


def stem(grow=True):
    cls = (lambda k: k) if grow else (lambda k: "")
    extra = ' pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"' if grow else ""
    main = (f'<path class="{cls("cane")}" d="M0 0 C-4 -70 5 -150 0 {-CANE + 4}" fill="none" stroke="{STEM}" '
            f'stroke-width="9" stroke-linecap="round"{extra}/>')
    branches = "".join(
        f'<path class="{cls("pd-" + n)}" d="M{FORK[0]} {FORK[1]} Q{p[0] * .15:.0f} {p[1] + 38} {p[0]} {p[1]}" fill="none" '
        f'stroke="{STEM}" stroke-width="6" stroke-linecap="round"{extra}/>' for n, p, _ in HEADS[1:])
    fork = (f'<g transform="translate({FORK[0]} {FORK[1]})"><g class="{cls("fk")}">'
            f'{bract(70, "#5f8fa6", "", -50)}{bract(70, "#5f8fa6", "", 50)}</g></g>')
    leaves = spiny_leaf(3, -52, 38, 1.0, cls("lf1")) + spiny_leaf(-3, -104, -38, .9, cls("lf2"))
    heads = "".join(f'<g transform="translate({p[0]} {p[1]})">{head(s, n, grow)}</g>' for n, p, s in HEADS)
    return f"{main}{branches}{leaves}{fork}{heads}"


def side(deg, k, scale):
    return f"""<g transform="translate(344 566) rotate({deg}) scale({scale})"><g class="side{'R' if k > 0 else 'L'}">
      {stem(False)}
    </g></g>"""


SCENE = f"""<g class="stage">
  {ground(CUT_Y, 10, STEM)}
  {side(-23, -1, .72)}
  {side(23, 1, .7)}
  <g transform="translate(344 {CUT_Y})"><g class="main">
    {stem(True)}
  </g></g>
  {sleeve(210, 452, 568, 526)}
  <g transform="translate(322 {CUT_Y})">{shears()}</g>
  </g>"""

LOOP_MS = 6600


def _fill(sel, a, b, lo, hi):
    return (sel, None, seq({"fill": a}, (lo, {"fill": a}), (hi, {"fill": b})))


def _heads():
    out = []
    plan = {"h1": (0.18, 0.22, 0.32), "h2": (0.20, 0.26, 0.36), "h3": (0.22, 0.29, 0.40)}
    for n, (pd, pop_at, open_at) in plan.items():
        if n != "h1":
            out.append((f".pd-{n}", None, seq({"strokeDashoffset": 1}, (pd, {"strokeDashoffset": 1}), (pd + 0.06, {"strokeDashoffset": 0}))))
        out.append(pop(f".hd-{n}", pop_at, pop_at + 0.07))
        # the ruff of bracts spreads out from the cone
        out.append((f".ru-{n}", LOCAL, seq({"transform": "scale(.25)"}, (open_at, {"transform": "scale(.25)"}),
                                           (open_at + 0.14, {"transform": "scale(1)"}))))
    return out


LOOP = [
    stage_track(),
    (".cane", None, seq({"strokeDashoffset": 1}, (0.04, {"strokeDashoffset": 1}), (0.20, {"strokeDashoffset": 0}))),
    pop(".lf1", 0.08, 0.14), pop(".lf2", 0.12, 0.18), pop(".fk", 0.16, 0.22),
] + _heads() + [
    # green to steel blue as the heads mature
    _fill(".dm", YOUNG["dome"], BLUE["dome"], 0.42, 0.56),
    _fill(".br-a", YOUNG["a"], BLUE["a"], 0.42, 0.56),
    _fill(".br-b", YOUNG["b"], BLUE["b"], 0.44, 0.58),
] + cut_bunch_tracks()
