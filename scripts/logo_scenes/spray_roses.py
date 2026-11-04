"""Spray roses: one cane carries a spray of heads that open one after another, then it is cut and bunched.

A branched stem: buds form on the side peduncles, three of them open into small rosettes while two stay
closed, as on a real spray; then secateurs cut the cane and it is bunched with two more in a kraft sleeve.
Solid flat tonal shapes, no outlines, in the crop's lighter pink accent.
"""

from ._cut_flowers import (LEAF, LOCAL, GONE, SHOW, bud, cut_bunch_tracks, ground, pop, rose_bloom, rose_leaf, seq,
                           shears, sleeve, stage_track, thorn)

LABEL = "Spray roses"
SCENE_TRANSFORM = "translate(344 344) scale(1) translate(-344 -344)"

TONES = ("#a8456b", "#c9577e", "#df7d9b", "#ee9fb6")
CUT_Y = 500
CANE = 338

# (name, peduncle start on the cane, head position, state, scale)
HEADS = [
    ("h1", (0, -338), (0, -338), "open", .56),
    ("h2", (-2, -206), (-66, -284), "open", .46),
    ("h3", (2, -228), (68, -298), "open", .46),
    ("h4", (-1, -250), (-32, -300), "bud", .8),
    ("h5", (1, -176), (38, -258), "bud", .72),
]


def peduncle(name, a, b, grow):
    (ax, ay), (bx, by) = a, b
    cx = (ax + bx) / 2 + (6 if bx < ax else -6)
    cy = min(ay, by) + 22
    d = f"M{ax} {ay} Q{cx:.0f} {cy:.0f} {bx} {by}"
    cls = f' class="pd-{name}"' if grow else ""
    extra = f' pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"' if grow else ""
    return f'<path{cls} d="{d}" fill="none" stroke="{LEAF}" stroke-width="5.5" stroke-linecap="round"{extra}/>'


def head(name, pos, state, s, grow):
    x, y = pos
    c = (lambda k: f"{k}-{name}") if grow else (lambda k: "")
    if state == "bud":
        return f'<g transform="translate({x} {y})"><g class="{c("bd")}">{bud(TONES, s)}</g></g>'
    # open heads: a bud that opens into the rosette
    return (f'<g transform="translate({x} {y})">'
            f'<g class="{c("bd")}">{bud(TONES, .8)}</g>'
            f'<g class="{c("op")}">{rose_bloom(TONES, s, "x" + name)}</g></g>')


def spray(grow=True, length=CANE):
    cane_cls = ' class="cane"' if grow else ""
    extra = ' pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"' if grow else ""
    main = (f'<path{cane_cls} d="M0 0 C-5 {-length * .3:.0f} 6 {-length * .7:.0f} 0 {-length}" fill="none" stroke="{LEAF}" '
            f'stroke-width="9" stroke-linecap="round"{extra}/>')
    ped = "".join(peduncle(n, a, b, grow) for n, a, b, st, s in HEADS[1:])
    cl = (lambda n: n) if grow else (lambda n: "")
    leaves = (thorn(4, -60, 1, .9) + thorn(-4, -120, -1, .8)
              + rose_leaf(2, -78, -36, .95, cl("lf1")) + rose_leaf(-2, -142, -144, .9, cl("lf2"))
              + rose_leaf(2, -190, -40, .72, cl("lf3")))
    heads = "".join(head(n, p, st, s, grow) for n, a, p, st, s in HEADS[::-1])
    return f"{main}{ped}{leaves}{heads}"


def side(deg, k, scale):
    return f"""<g transform="translate(344 566) rotate({deg}) scale({scale})"><g class="side{'R' if k > 0 else 'L'}">
      {spray(False)}
    </g></g>"""


SCENE = f"""<g class="stage">
  {ground(CUT_Y, 10)}
  {side(-25, -1, .84)}
  {side(25, 1, .8)}
  <g transform="translate(344 {CUT_Y})"><g class="main">
    {spray(True)}
  </g></g>
  {sleeve(210, 452, 568, 526)}
  <g transform="translate(322 {CUT_Y})">{shears()}</g>
  </g>"""

LOOP_MS = 6800


def _head_tracks():
    out = []
    # (peduncle grows, bud pops, opens)
    plan = {"h1": (0.18, 0.24, 0.40), "h2": (0.20, 0.27, 0.44), "h3": (0.23, 0.30, 0.48),
            "h4": (0.25, 0.33, None), "h5": (0.22, 0.31, None)}
    for n, (pd, pp, op) in plan.items():
        if n != "h1":
            out.append((f".pd-{n}", None, seq({"strokeDashoffset": 1}, (pd, {"strokeDashoffset": 1}), (pd + 0.06, {"strokeDashoffset": 0}))))
        if op is None:
            out.append(pop(f".bd-{n}", pp, pp + 0.06))
            continue
        # the bud pops in, then fades into the opening rosette
        out.append((f".bd-{n}", LOCAL, seq(GONE, (pp, GONE), (pp + 0.06, SHOW), (op, SHOW),
                                           (op + 0.05, {"transform": "scale(.7)", "opacity": 0}))))
        out.append((f".op-{n}", LOCAL, seq({"transform": "scale(.3)", "opacity": 0}, (op, {"transform": "scale(.3)", "opacity": 0}),
                                           (op + 0.03, {"transform": "scale(.45)", "opacity": 1}),
                                           (op + 0.12, SHOW))))
    return out


LOOP = [
    stage_track(),
    (".cane", None, seq({"strokeDashoffset": 1}, (0.04, {"strokeDashoffset": 1}), (0.22, {"strokeDashoffset": 0}))),
    pop(".lf1", 0.08, 0.14), pop(".lf2", 0.12, 0.18), pop(".lf3", 0.16, 0.22),
] + _head_tracks() + cut_bunch_tracks()
