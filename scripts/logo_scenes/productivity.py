"""Productivity: the top-level Production mark (desk tile, splash, app before a crop is open).

A checklist ticks off, bars rise with a green trend arrow, a gauge settles in the green.
"""

import math

from .common import ACCENT, HIDE, INK, MID, PALE, SHOW

LABEL = "Production"
# Where the scene sits in the disc (wraps SCENE).
SCENE_TRANSFORM = "translate(344 420) scale(1.14) translate(-344 -420)"

STAGE_ORIGIN = "view-box|344px 410px"

# 1. checklist card with three rows
ROW_Y = (330, 405, 480)


def row(i: int) -> str:
    y = ROW_Y[i]
    return f"""<rect x="196" y="{y - 26}" width="52" height="52" rx="12" fill="#ffffff" stroke="{INK}" stroke-width="13"/>
    <path class="line line{i}" d="M290 {y} H490" stroke="{PALE}" stroke-width="26" stroke-linecap="round"/>
    <path class="tick tick{i}" d="M204 {y + 2} L222 {y + 20} L258 {y - 26}" fill="none" stroke="{ACCENT}" stroke-width="22"
          stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>"""


CHECKLIST = f"""<g class="checklist">
    <rect x="160" y="262" width="368" height="288" rx="38" fill="#ffffff" stroke="{INK}" stroke-width="16"/>
    {row(0)}
    {row(1)}
    {row(2)}
  </g>"""

# 2. bar chart and trend arrow
BAR_X = (210, 320, 430)
BAR_H = (90, 150, 205)
BASE_Y = 548


def bar(i: int) -> str:
    fill = ACCENT if i == 2 else INK
    return (f'<rect class="bar bar{i}" x="{BAR_X[i] - 40}" y="{BASE_Y - BAR_H[i]}" width="80" height="{BAR_H[i]}" '
            f'rx="10" fill="{INK}"/>')


BARS = f"""<g class="bars">
    <path class="base" d="M150 {BASE_Y + 8} H500" stroke="{INK}" stroke-width="16" stroke-linecap="round"/>
    {bar(0)}
    {bar(1)}
    {bar(2)}
    <path class="trend" d="M145 425 L240 350 L312 386 L424 282" fill="none" stroke="{ACCENT}" stroke-width="28"
          stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>
    <path class="head" d="M364 278 H434 V338" fill="none" stroke="{ACCENT}" stroke-width="28" stroke-linecap="round" stroke-linejoin="round"/>
  </g>"""

# 3. gauge: a half ring in three zones and a needle
GC = (344, 500)
GR = 180


def arc(a0: float, a1: float) -> str:
    """Arc from angle a0 to a1 (degrees, 180 = left, 0 = right, over the top)."""
    p = lambda a: (GC[0] + GR * math.cos(math.radians(a)), GC[1] - GR * math.sin(math.radians(a)))
    (x0, y0), (x1, y1) = p(a0), p(a1)
    return f"M{x0:.1f} {y0:.1f} A{GR} {GR} 0 0 1 {x1:.1f} {y1:.1f}"


GAUGE = f"""<g class="gauge">
    <path d="{arc(178, 122)}" fill="none" stroke="{PALE}" stroke-width="46"/>
    <path d="{arc(118, 62)}" fill="none" stroke="{MID}" stroke-width="46"/>
    <path class="zone" d="{arc(58, 2)}" fill="none" stroke="{ACCENT}" stroke-width="46"/>
    <g class="needle">
      <path d="M{GC[0]} {GC[1]} V{GC[1] - 140}" stroke="{INK}" stroke-width="22" stroke-linecap="round"/>
    </g>
    <circle cx="{GC[0]}" cy="{GC[1]}" r="34" fill="{INK}"/>
    <circle cx="{GC[0]}" cy="{GC[1]}" r="12" fill="#ffffff"/>
  </g>"""

SCENE = f"""{CHECKLIST}
  {BARS}
  {GAUGE}"""

def _tick(lo, hi):
    return [(0, {"strokeDashoffset": 1}), (lo, {"strokeDashoffset": 1}), (hi, {"strokeDashoffset": 0}),
            (0.30, {"strokeDashoffset": 0}), (0.31, {"strokeDashoffset": 1}), (1, {"strokeDashoffset": 1})]


def _line(lo, hi):
    return [(0, {"stroke": PALE}), (lo, {"stroke": PALE}), (hi, {"stroke": INK}), (0.30, {"stroke": INK}),
            (0.31, {"stroke": PALE}), (1, {"stroke": PALE})]


def _rise(lo, hi):
    return [(0, {"transform": "scaleY(0)"}), (lo, {"transform": "scaleY(0)"}),
            (hi, {"transform": "scaleY(1.07)"}), (hi + 0.025, {"transform": "scaleY(1)"}),
            (0.72, {"transform": "scaleY(1)"}), (0.73, {"transform": "scaleY(0)"}), (1, {"transform": "scaleY(0)"})]


LOOP = [
    # 1. checklist: in at the start, ticks in turn, gone by .36
    (".checklist", STAGE_ORIGIN, [
        (0, {"transform": "scale(.86)", "opacity": 0}),
        (0.04, SHOW), (0.34, SHOW), (0.40, HIDE), (0.94, HIDE), (1, {"transform": "scale(.86)", "opacity": 0}),
    ]),
    (".tick0", None, _tick(0.06, 0.11)),
    (".tick1", None, _tick(0.14, 0.19)),
    (".tick2", None, _tick(0.22, 0.27)),
    (".line0", None, _line(0.09, 0.12)),
    (".line1", None, _line(0.17, 0.20)),
    (".line2", None, _line(0.25, 0.28)),
    # 2. bars rise, the trend arrow shoots up
    (".bars", STAGE_ORIGIN, [
        (0, HIDE), (0.34, HIDE), (0.38, SHOW), (0.70, SHOW), (0.76, HIDE), (1, HIDE),
    ]),
    (".bar0", f"view-box|{BAR_X[0]}px {BASE_Y}px", _rise(0.38, 0.45)),
    (".bar1", f"view-box|{BAR_X[1]}px {BASE_Y}px", _rise(0.44, 0.51)),
    (".bar2", f"view-box|{BAR_X[2]}px {BASE_Y}px", _rise(0.50, 0.57)),
    (".trend", None, [
        (0, {"strokeDashoffset": 1}), (0.55, {"strokeDashoffset": 1}), (0.64, {"strokeDashoffset": 0}),
        (0.72, {"strokeDashoffset": 0}), (0.73, {"strokeDashoffset": 1}), (1, {"strokeDashoffset": 1}),
    ]),
    (".head", "view-box|434px 278px", [
        (0, {"opacity": 0, "transform": "scale(.5)"}), (0.62, {"opacity": 0, "transform": "scale(.5)"}),
        (0.66, {"opacity": 1, "transform": "scale(1.15)"}), (0.69, {"opacity": 1, "transform": "scale(1)"}),
        (0.72, {"opacity": 1, "transform": "scale(1)"}), (0.73, {"opacity": 0, "transform": "scale(.5)"}),
        (1, {"opacity": 0, "transform": "scale(.5)"}),
    ]),
    # 3. gauge: the needle sweeps right, overshoots, settles in the green
    (".gauge", f"view-box|{GC[0]}px {GC[1]}px", [
        (0, HIDE), (0.72, HIDE), (0.78, SHOW), (0.92, SHOW), (0.97, HIDE), (1, HIDE),
    ]),
    (".needle", f"view-box|{GC[0]}px {GC[1]}px", [
        (0, {"transform": "rotate(-84deg)"}), (0.76, {"transform": "rotate(-84deg)"}),
        (0.84, {"transform": "rotate(78deg)"}), (0.88, {"transform": "rotate(56deg)"}),
        (1, {"transform": "rotate(56deg)"}),
    ]),
    (".zone", None, [
        (0, {"strokeWidth": 46}), (0.86, {"strokeWidth": 46}), (0.89, {"strokeWidth": 60}), (0.93, {"strokeWidth": 46}),
        (1, {"strokeWidth": 46}),
    ]),
]

LOOP_MS = 5600
