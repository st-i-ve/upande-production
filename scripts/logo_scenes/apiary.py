"""Apiary: the bees crop scene, drawn as flat solid silhouettes (no outlines, no faces).

1. A honey bee leaves a Langstroth hive, works a flower and flies back in.
2. Honeycomb cells fill with honey one by one.
3. Two drops fall into a jar that fills.
"""

import math

from .common import HIDE, INK, MID, PALE, SHOW

HONEY = "#c99a1b"
LABEL = "Apiary"
SCENE_TRANSFORM = "translate(344 380) scale(1.1) translate(-344 -380)"
STAGE_ORIGIN = "view-box|344px 380px"

# -- 1. hive, flower, bee -------------------------------------------------------
# Langstroth hive, front view: stacked boxes with hairline gaps, hand-holds and an entrance as
# negative space, a landing board, resting on the ground band.
PETALS = "".join(
    f'<ellipse cx="500" cy="262" rx="13" ry="30" transform="rotate({a} 500 300)" fill="{MID}"/>'
    for a in range(0, 360, 60))
HIVE = f"""<g class="hive">
    <rect x="60" y="494" width="570" height="14" fill="{PALE}"/>
    <rect x="106" y="474" width="250" height="16" fill="{INK}"/>
    <rect x="124" y="414" width="214" height="56" fill="{INK}"/>
    <rect x="124" y="340" width="214" height="70" fill="{HONEY}"/>
    <rect x="124" y="266" width="214" height="70" fill="{INK}"/>
    <rect x="108" y="238" width="246" height="24" fill="{INK}"/>
    <rect x="196" y="452" width="70" height="18" fill="#ffffff"/>
    <rect x="206" y="296" width="50" height="9" fill="#ffffff"/>
    <rect x="206" y="370" width="50" height="9" fill="#ffffff"/>
    <g class="flower">
      <rect x="496" y="300" width="8" height="194" fill="{INK}"/>
      <path d="M500 450 C462 450 446 426 446 404 C486 404 500 426 500 450Z" fill="{MID}"/>
      <path d="M500 400 C538 400 554 380 554 358 C514 358 500 380 500 400Z" fill="{MID}"/>
      {PETALS}
      <circle cx="500" cy="300" r="17" fill="{HONEY}"/>
    </g>
    <clipPath id="apiary-bee"><ellipse cx="-30" cy="4" rx="36" ry="22"/></clipPath>
    <g class="bee">
      <g class="face">
        <g class="wings">
          <ellipse cx="-6" cy="-30" rx="11" ry="28" transform="rotate(-24 -6 -30)" fill="{PALE}" fill-opacity=".85"/>
          <ellipse cx="14" cy="-28" rx="10" ry="24" transform="rotate(12 14 -28)" fill="{PALE}" fill-opacity=".85"/>
        </g>
        <path d="M-12 14 L-20 38 M0 16 L2 40 M12 14 L22 36 M44 -10 L62 -30" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>
        <path d="M-64 4 L-76 4 L-64 10Z" fill="{INK}"/>
        <ellipse cx="-30" cy="4" rx="36" ry="22" fill="{INK}"/>
        <g clip-path="url(#apiary-bee)">
          <rect x="-52" y="-20" width="9" height="48" fill="{HONEY}"/>
          <rect x="-35" y="-20" width="9" height="48" fill="{HONEY}"/>
          <rect x="-18" y="-20" width="9" height="48" fill="{HONEY}"/>
        </g>
        <circle cx="12" cy="0" r="21" fill="{INK}"/>
        <circle cx="38" cy="-2" r="14" fill="{INK}"/>
      </g>
    </g>
  </g>"""

# -- 2. comb ---------------------------------------------------------------------
# Pointy-top hexagons, each a solid cell; the hairline gaps between them are the comb walls.
CR = 60
CA = CR * math.sqrt(3) / 2
CC = (344, 380)
CELLS = [(0, 0), (CA, -1.5 * CR), (2 * CA, 0), (CA, 1.5 * CR), (-CA, 1.5 * CR), (-2 * CA, 0), (-CA, -1.5 * CR)]


def hexpts(cx, cy, r):
    return " ".join(f"{cx + r * math.cos(math.radians(30 + 60 * k)):.1f},{cy + r * math.sin(math.radians(30 + 60 * k)):.1f}"
                    for k in range(6))


def cell(i):
    cx, cy = CC[0] + CELLS[i][0], CC[1] + CELLS[i][1]
    return (f'<polygon points="{hexpts(cx, cy, 55)}" fill="{PALE}"/>'
            f'<polygon class="h{i}" points="{hexpts(cx, cy, 55)}" fill="{HONEY}"/>')


COMB = '<g class="comb">' + "".join(cell(i) for i in range(7)) + "</g>"

# -- 3. jar ------------------------------------------------------------------------
# A solid glass-toned jar with an ink collar; honey rises inside it.
JAR = "M292 292 H396 V306 Q436 320 436 360 V478 Q436 504 410 504 H278 Q252 504 252 478 V360 Q252 320 292 306 Z"
DROP = "M0 -30 C14 -8 20 4 20 16 A20 20 0 0 1 -20 16 C-20 4 -14 -8 0 -30Z"
JARG = f"""<g class="jar">
    <clipPath id="apiary-jar"><path d="{JAR}"/></clipPath>
    <path d="{JAR}" fill="{PALE}"/>
    <g clip-path="url(#apiary-jar)"><rect class="honey" x="240" y="330" width="208" height="180" fill="{HONEY}"/></g>
    <rect x="282" y="276" width="124" height="18" fill="{INK}"/>
    <path class="drop0" d="{DROP}" fill="{HONEY}"/>
    <path class="drop1" d="{DROP}" fill="{HONEY}"/>
  </g>"""

SCENE = f"""{HIVE}
  {COMB}
  {JARG}"""


# -- motion ------------------------------------------------------------------------
def T(x, y, s=1):
    return f"translate({x}px, {y}px) scale({s})"


BEE = [
    (0, {"transform": T(231, 466, .3), "opacity": 0}),
    (0.02, {"transform": T(231, 466, .3), "opacity": 0}),
    (0.05, {"transform": T(238, 436, 1.8), "opacity": 1}),
    (0.10, {"transform": T(300, 352, 1.8)}),
    (0.15, {"transform": T(375, 305, 1.8)}),
    (0.20, {"transform": T(415, 282, 1.8)}),
    (0.23, {"transform": T(424, 290, 1.8)}),
    (0.25, {"transform": T(420, 282, 1.8)}),
    (0.27, {"transform": T(424, 288, 1.8)}),
    (0.285, {"transform": T(425, 288, 1.8)}),
    (0.31, {"transform": T(340, 330, 1.8)}),
    (0.33, {"transform": T(256, 428, 1.8), "opacity": 1}),
    (0.345, {"transform": T(231, 466, .3), "opacity": 0}),
    (1, {"transform": T(231, 466, .3), "opacity": 0}),
]

FLAP = []
for k in range(0, 36):
    FLAP.append((round(0.03 + k * 0.0085, 4), {"transform": "scaleY(1)" if k % 2 == 0 else "scaleY(.45)"}))
FLAP = [(0, {"transform": "scaleY(1)"})] + FLAP + [(0.36, {"transform": "scaleY(1)"}), (1, {"transform": "scaleY(1)"})]


def pop(lo, hi):
    settle = hi + 0.02
    hold = max(0.64, settle + 0.005)  # the last cell settles late: hold after it, never before
    return [(0, {"transform": "scale(0)"}), (lo, {"transform": "scale(0)"}),
            (hi, {"transform": "scale(1)"}), (settle, {"transform": "scale(1)"}),
            (hold, {"transform": "scale(1)"}), (hold + 0.02, {"transform": "scale(0)"}), (1, {"transform": "scale(0)"})]


def drop(t0, t1, y1):
    s = lambda y, sc, op: {"transform": T(344, y, sc), "opacity": op}
    return [(0, s(150, .6, 0)), (t0, s(150, .6, 0)), (t0 + .02, s(165, 1, 1)), (t1, s(y1, 1, 1)),
            (t1 + .015, s(y1 + 14, .6, 0)), (1, s(150, .6, 0))]


LOOP = [
    (".hive", STAGE_ORIGIN, [(0, HIDE), (0.01, SHOW), (0.34, SHOW), (0.38, HIDE), (0.96, HIDE), (1, HIDE)]),
    (".bee", "view-box|0px 0px", BEE),
    (".wings", "fill-box|50% 100%", FLAP),
    (".face", "fill-box|50% 50%", [
        (0, {"transform": "scaleX(1)"}), (0.27, {"transform": "scaleX(1)"}), (0.285, {"transform": "scaleX(-1)"}),
        (0.36, {"transform": "scaleX(-1)"}), (0.37, {"transform": "scaleX(1)"}), (1, {"transform": "scaleX(1)"}),
    ]),
    (".comb", STAGE_ORIGIN, [(0, HIDE), (0.36, HIDE), (0.40, SHOW), (0.64, SHOW), (0.68, HIDE), (1, HIDE)]),
] + [(f".h{i}", "fill-box|50% 50%", pop(0.42 + i * 0.027, 0.46 + i * 0.027)) for i in range(7)] + [
    (".jar", STAGE_ORIGIN, [(0, HIDE), (0.66, HIDE), (0.70, SHOW), (0.93, SHOW), (0.97, HIDE), (1, HIDE)]),
    (".honey", "fill-box|50% 100%", [
        (0, {"transform": "scaleY(0)"}), (0.72, {"transform": "scaleY(0)"}), (0.77, {"transform": "scaleY(.45)"}),
        (0.85, {"transform": "scaleY(.45)"}), (0.90, {"transform": "scaleY(1)"}), (0.97, {"transform": "scaleY(1)"}),
        (0.98, {"transform": "scaleY(0)"}), (1, {"transform": "scaleY(0)"}),
    ]),
    (".drop0", "view-box|0px 0px", drop(0.70, 0.765, 262)),
    (".drop1", "view-box|0px 0px", drop(0.80, 0.865, 262)),
]

LOOP_MS = 5600
