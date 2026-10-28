"""Apiary: the bees crop scene.

1. A bee leaves the hive, loops to a flower and flies back in.
2. Honeycomb cells fill with honey one by one.
3. Two drops fall into a jar that fills.
"""

import math

from .common import HIDE, INK, MID, PALE, SHOW

HONEY = "#c99a1b"
LABEL = "Apiary"
SCENE_TRANSFORM = "translate(344 430) scale(1.2) translate(-344 -430)"
STAGE_ORIGIN = "view-box|344px 410px"

# -- 1. hive, flower, bee -------------------------------------------------------
HIVE = f"""<g class="hive">
    <path d="M120 548 H380" stroke="{INK}" stroke-width="16" stroke-linecap="round"/>
    <rect x="155" y="440" width="190" height="90" rx="10" fill="#ffffff" stroke="{INK}" stroke-width="16"/>
    <rect x="155" y="355" width="190" height="85" rx="10" fill="{HONEY}" stroke="{INK}" stroke-width="16"/>
    <path d="M122 355 L148 305 H352 L378 355 Z" fill="{INK}" stroke="{INK}" stroke-width="16" stroke-linejoin="round"/>
    <rect x="215" y="496" width="70" height="26" rx="8" fill="{INK}"/>
    <g class="flower">
      <path d="M492 548 V420" stroke="{INK}" stroke-width="16" stroke-linecap="round"/>
      <path d="M492 500 C455 500 440 475 440 455 C478 455 492 475 492 500Z" fill="{PALE}" stroke="{INK}" stroke-width="10" stroke-linejoin="round"/>
      {"".join(f'<circle cx="{492 + 40 * math.cos(math.radians(a)):.1f}" cy="{400 + 40 * math.sin(math.radians(a)):.1f}" r="27" fill="#ffffff" stroke="{INK}" stroke-width="12"/>' for a in range(-90, 270, 72))}
      <circle cx="492" cy="400" r="30" fill="{HONEY}" stroke="{INK}" stroke-width="12"/>
    </g>
    <clipPath id="apiary-bee"><ellipse cx="0" cy="0" rx="42" ry="30"/></clipPath>
    <g class="bee">
      <g class="face">
        <g class="wings">
          <ellipse cx="-10" cy="-38" rx="20" ry="34" transform="rotate(-18 -10 -38)" fill="#ffffff" stroke="{INK}" stroke-width="10"/>
          <ellipse cx="14" cy="-38" rx="18" ry="30" transform="rotate(14 14 -38)" fill="#ffffff" stroke="{INK}" stroke-width="10"/>
        </g>
        <path d="M-40 0 L-62 -6 L-62 6 Z" fill="{INK}" stroke="{INK}" stroke-width="6" stroke-linejoin="round"/>
        <ellipse cx="0" cy="0" rx="42" ry="30" fill="{HONEY}"/>
        <g clip-path="url(#apiary-bee)">
          <rect x="-24" y="-34" width="14" height="68" fill="{INK}"/>
          <rect x="4" y="-34" width="14" height="68" fill="{INK}"/>
        </g>
        <ellipse cx="0" cy="0" rx="42" ry="30" fill="none" stroke="{INK}" stroke-width="10"/>
        <circle cx="48" cy="-2" r="19" fill="{INK}"/>
        <circle cx="54" cy="-8" r="5" fill="#ffffff"/>
      </g>
    </g>
  </g>"""

# -- 2. comb ---------------------------------------------------------------------
CR = 60
CA = CR * math.sqrt(3) / 2
CC = (344, 420)
CELLS = [(0, 0), (CA, -1.5 * CR), (2 * CA, 0), (CA, 1.5 * CR), (-CA, 1.5 * CR), (-2 * CA, 0), (-CA, -1.5 * CR)]


def hexpts(cx, cy, r):
    return " ".join(f"{cx + r * math.cos(math.radians(30 + 60 * k)):.1f},{cy + r * math.sin(math.radians(30 + 60 * k)):.1f}"
                    for k in range(6))


def cell(i):
    cx, cy = CC[0] + CELLS[i][0], CC[1] + CELLS[i][1]
    return (f'<polygon points="{hexpts(cx, cy, 52)}" fill="#ffffff" stroke="{INK}" stroke-width="14" stroke-linejoin="round"/>'
            f'<polygon class="h{i}" points="{hexpts(cx, cy, 36)}" fill="{HONEY}" stroke="{HONEY}" stroke-width="8" '
            f'stroke-linejoin="round"/>')


COMB = '<g class="comb">' + "".join(cell(i) for i in range(7)) + "</g>"

# -- 3. jar ------------------------------------------------------------------------
JAR = "M286 340 H402 V372 Q434 384 434 420 V516 Q434 550 400 550 H288 Q254 550 254 516 V420 Q254 384 286 372 Z"
DROP = "M0 -36 C18 -8 26 6 26 20 A26 26 0 0 1 -26 20 C-26 6 -18 -8 0 -36Z"
JARG = f"""<g class="jar">
    <clipPath id="apiary-jar"><path d="{JAR}"/></clipPath>
    <path d="{JAR}" fill="#ffffff"/>
    <g clip-path="url(#apiary-jar)"><rect class="honey" x="240" y="400" width="208" height="160" fill="{HONEY}"/></g>
    <path d="{JAR}" fill="none" stroke="{INK}" stroke-width="16" stroke-linejoin="round"/>
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
    (0, {"transform": T(250, 512, .3), "opacity": 0}),
    (0.02, {"transform": T(250, 512, .3), "opacity": 0}),
    (0.05, {"transform": T(256, 480, 1.4), "opacity": 1}),
    (0.10, {"transform": T(290, 370, 1.4)}),
    (0.15, {"transform": T(385, 345, 1.4)}),
    (0.20, {"transform": T(485, 340, 1.4)}),
    (0.23, {"transform": T(492, 350, 1.4)}),
    (0.25, {"transform": T(488, 340, 1.4)}),
    (0.27, {"transform": T(496, 348, 1.4)}),
    (0.285, {"transform": T(425, 345, 1.4)}),
    (0.31, {"transform": T(330, 330, 1.4)}),
    (0.33, {"transform": T(262, 478, 1.4), "opacity": 1}),
    (0.345, {"transform": T(250, 512, .3), "opacity": 0}),
    (1, {"transform": T(250, 512, .3), "opacity": 0}),
]

FLAP = []
for k in range(0, 36):
    FLAP.append((round(0.03 + k * 0.0085, 4), {"transform": "scaleY(1)" if k % 2 == 0 else "scaleY(.3)"}))
FLAP = [(0, {"transform": "scaleY(1)"})] + FLAP + [(0.36, {"transform": "scaleY(1)"}), (1, {"transform": "scaleY(1)"})]


def pop(lo, hi):
    settle = hi + 0.02
    hold = max(0.64, settle + 0.005)  # the last cell settles late: hold after it, never before
    return [(0, {"transform": "scale(0)"}), (lo, {"transform": "scale(0)"}),
            (hi, {"transform": "scale(1.12)"}), (settle, {"transform": "scale(1)"}),
            (hold, {"transform": "scale(1)"}), (hold + 0.02, {"transform": "scale(0)"}), (1, {"transform": "scale(0)"})]


def drop(t0, t1, y1):
    s = lambda y, sc, op: {"transform": T(344, y, sc), "opacity": op}
    return [(0, s(190, .3, 0)), (t0, s(190, .3, 0)), (t0 + .02, s(200, 1, 1)), (t1, s(y1, 1, 1)),
            (t1 + .015, s(y1 + 14, .4, 0)), (1, s(190, .3, 0))]


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
    (".drop0", "view-box|0px 0px", drop(0.70, 0.765, 472)),
    (".drop1", "view-box|0px 0px", drop(0.80, 0.865, 440)),
]

LOOP_MS = 5600
