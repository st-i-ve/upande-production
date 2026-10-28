"""Productivity: the top-level Production mark (desk tile, splash, app before a crop is open).

Flat ink: a checklist ticks off, bars rise on a fine baseline with a trend arrow, a gauge of solid
segments settles in the green. No outlines, no bounces.
"""

import math

from .common import ACCENT, HIDE, INK, MID, PALE, SHOW

LABEL = "Production"
# Where the scene sits in the disc (wraps SCENE).
SCENE_TRANSFORM = "translate(344 420) scale(1.14) translate(-344 -420)"

STAGE_ORIGIN = "view-box|344px 410px"

# 1. checklist: solid rows, square markers that turn green with a white check
ROW_Y = (330, 410, 490)


def row(i: int) -> str:
    y = ROW_Y[i]
    return f"""<rect class="box box{i}" x="190" y="{y - 29}" width="58" height="58" rx="5" fill="{PALE}"/>
    <path class="tick tick{i}" d="M202 {y + 1} L216 {y + 15} L238 {y - 14}" fill="none" stroke="#ffffff" stroke-width="12"
          stroke-linejoin="miter" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>
    <rect class="line line{i}" x="282" y="{y - 12}" width="{(220, 190, 205)[i]}" height="24" rx="3" fill="{PALE}"/>"""


CHECKLIST = f"""<g class="checklist">
    <rect x="190" y="236" width="312" height="14" fill="{INK}"/>
    {row(0)}
    {row(1)}
    {row(2)}
  </g>"""

# 2. bars on a fine baseline, trend line with a solid arrowhead
BAR_X = (210, 320, 430)
BAR_H = (90, 150, 205)
BASE_Y = 548


def bar(i: int) -> str:
    fill = INK if i == 2 else MID
    return (f'<rect class="bar bar{i}" x="{BAR_X[i] - 36}" y="{BASE_Y - BAR_H[i]}" width="72" height="{BAR_H[i]}" '
            f'fill="{fill}"/>')


def _arrow(tip, frm, length=46, half=24):
    dx, dy = tip[0] - frm[0], tip[1] - frm[1]
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    bx, by = tip[0] - ux * length, tip[1] - uy * length
    return (bx, by), f"M{tip[0]} {tip[1]} L{bx - uy * half:.1f} {by + ux * half:.1f} L{bx + uy * half:.1f} {by - ux * half:.1f} Z"


_base, HEAD_D = _arrow((462, 270), (390, 360))
TREND_D = f"M200 412 L316 352 L384 378 L{_base[0]:.1f} {_base[1]:.1f}"

BARS = f"""<g class="bars">
    <rect x="150" y="{BASE_Y}" width="360" height="6" fill="{INK}"/>
    {bar(0)}
    {bar(1)}
    {bar(2)}
    <path class="trend" d="{TREND_D}" fill="none" stroke="{ACCENT}" stroke-width="13"
          stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>
    <path class="head" d="{HEAD_D}" fill="{ACCENT}"/>
  </g>"""

# 3. gauge: solid arc segments and a slim needle
GC = (344, 500)
GR = 180


def arc(a0: float, a1: float) -> str:
    """Arc from angle a0 to a1 (degrees, 180 = left, 0 = right, over the top)."""
    p = lambda a: (GC[0] + GR * math.cos(math.radians(a)), GC[1] - GR * math.sin(math.radians(a)))
    (x0, y0), (x1, y1) = p(a0), p(a1)
    return f"M{x0:.1f} {y0:.1f} A{GR} {GR} 0 0 1 {x1:.1f} {y1:.1f}"


GAUGE = f"""<g class="gauge">
    <path d="{arc(180, 124)}" fill="none" stroke="{PALE}" stroke-width="44"/>
    <path d="{arc(120, 64)}" fill="none" stroke="{MID}" stroke-width="44"/>
    <path class="zone" d="{arc(60, 0)}" fill="none" stroke="{ACCENT}" stroke-width="44"/>
    <g class="needle">
      <path d="M-9 0 L0 -158 L9 0 Z" transform="translate({GC[0]} {GC[1]})" fill="{INK}"/>
    </g>
    <circle cx="{GC[0]}" cy="{GC[1]}" r="22" fill="{INK}"/>
  </g>"""

SCENE = f"""{CHECKLIST}
  {BARS}
  {GAUGE}"""


def _tick(lo, hi):
    return [(0, {"strokeDashoffset": 1}), (lo, {"strokeDashoffset": 1}), (hi, {"strokeDashoffset": 0}),
            (0.30, {"strokeDashoffset": 0}), (0.31, {"strokeDashoffset": 1}), (1, {"strokeDashoffset": 1})]


def _fill(lo, hi, off, on):
    return [(0, {"fill": off}), (lo, {"fill": off}), (hi, {"fill": on}), (0.30, {"fill": on}),
            (0.31, {"fill": off}), (1, {"fill": off})]


def _rise(lo, hi):
    return [(0, {"transform": "scaleY(0)"}), (lo, {"transform": "scaleY(0)"}),
            (hi, {"transform": "scaleY(1)"}),
            (0.72, {"transform": "scaleY(1)"}), (0.73, {"transform": "scaleY(0)"}), (1, {"transform": "scaleY(0)"})]


LOOP = [
    # 1. checklist: in at the start, ticks in turn, gone by .36
    (".checklist", STAGE_ORIGIN, [
        (0, {"transform": "scale(.96)", "opacity": 0}),
        (0.04, SHOW), (0.34, SHOW), (0.40, HIDE), (0.94, HIDE), (1, {"transform": "scale(.86)", "opacity": 0}),
    ]),
    (".tick0", None, _tick(0.06, 0.11)),
    (".tick1", None, _tick(0.14, 0.19)),
    (".tick2", None, _tick(0.22, 0.27)),
    (".box0", None, _fill(0.06, 0.09, PALE, ACCENT)),
    (".box1", None, _fill(0.14, 0.17, PALE, ACCENT)),
    (".box2", None, _fill(0.22, 0.25, PALE, ACCENT)),
    (".line0", None, _fill(0.09, 0.12, PALE, INK)),
    (".line1", None, _fill(0.17, 0.20, PALE, INK)),
    (".line2", None, _fill(0.25, 0.28, PALE, INK)),
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
    (".head", None, [
        (0, {"opacity": 0}), (0.62, {"opacity": 0}), (0.66, {"opacity": 1}),
        (0.72, {"opacity": 1}), (0.73, {"opacity": 0}), (1, {"opacity": 0}),
    ]),
    # 3. gauge: the needle sweeps right and settles in the green
    (".gauge", f"view-box|{GC[0]}px {GC[1]}px", [
        (0, HIDE), (0.72, HIDE), (0.78, SHOW), (0.92, SHOW), (0.97, HIDE), (1, HIDE),
    ]),
    (".needle", f"view-box|{GC[0]}px {GC[1]}px", [
        (0, {"transform": "rotate(-84deg)"}), (0.76, {"transform": "rotate(-84deg)"}),
        (0.88, {"transform": "rotate(56deg)"}), (1, {"transform": "rotate(56deg)"}),
    ]),
]

LOOP_MS = 5600
