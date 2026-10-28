"""Fruits and vegetables: a centre-pivot circle seen from above, then the harvest in a crate.

The pivot arm sweeps once round, each pizza-slice block greening as it passes; then a cabbage,
a potato and an onion drop into a crate.
"""

import math

from .common import ACCENT, HIDE, INK, MID, PALE, SHOW

LABEL = "Fruits and vegetables"
ORANGE = "#c0662b"
SCENE_TRANSFORM = "translate(344 420) scale(1.2) translate(-344 -420)"
STAGE_ORIGIN = "view-box|344px 420px"

# 1. the pivot circle in six slices
CX, CY, R = 344, 410, 188
N = 6


def pt(a, r=R):
    return CX + r * math.cos(math.radians(a)), CY + r * math.sin(math.radians(a))


def slice_path(i):
    a0, a1 = -90 + 60 * i, -90 + 60 * (i + 1)
    (x0, y0), (x1, y1) = pt(a0), pt(a1)
    return f"M{CX} {CY} L{x0:.1f} {y0:.1f} A{R} {R} 0 0 1 {x1:.1f} {y1:.1f} Z"


SLICES = "\n    ".join(
    f'<path class="slice s{i}" d="{slice_path(i)}" fill="{PALE}" stroke="#ffffff" stroke-width="10" stroke-linejoin="round"/>'
    for i in range(N)
)

FIELD = f"""<g class="field">
    {SLICES}
    <circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="{INK}" stroke-width="18"/>
    <g class="arm">
      <path d="M{CX} {CY} V{CY - R - 4}" stroke="{INK}" stroke-width="20" stroke-linecap="round"/>
      <circle cx="{CX}" cy="{CY - R + 18}" r="15" fill="{ORANGE}" stroke="#ffffff" stroke-width="6"/>
    </g>
    <circle cx="{CX}" cy="{CY}" r="28" fill="{INK}"/>
    <circle cx="{CX}" cy="{CY}" r="10" fill="#ffffff"/>
  </g>"""

# 2. crate and produce
CRATE = f"""<g class="crate">
    <g class="cabbage"><g>
      <circle cx="288" cy="402" r="64" fill="{ACCENT}"/>
      <path d="M288 345 C262 375 262 420 288 458 M288 345 C314 375 314 420 288 458" fill="none" stroke="#ffffff" stroke-opacity=".55" stroke-width="10" stroke-linecap="round"/>
    </g></g>
    <g class="potato"><g>
      <ellipse cx="388" cy="412" rx="54" ry="42" fill="{ORANGE}" transform="rotate(-14 388 412)"/>
      <circle cx="372" cy="402" r="6" fill="#ffffff" fill-opacity=".6"/><circle cx="404" cy="420" r="6" fill="#ffffff" fill-opacity=".6"/>
    </g></g>
    <g class="onion"><g>
      <path d="M446 366 C452 384 480 396 480 424 C480 450 462 462 446 462 C430 462 412 450 412 424 C412 396 440 384 446 366 Z" fill="{MID}"/>
    </g></g>
    <g class="front">
      <path d="M208 440 H480 V548 a16 16 0 0 1 -16 16 H224 a16 16 0 0 1 -16 -16 Z" fill="#ffffff" stroke="{INK}" stroke-width="16" stroke-linejoin="round"/>
      <path d="M208 440 H480" stroke="{ORANGE}" stroke-width="26"/>
      <path d="M222 502 H466" stroke="{INK}" stroke-width="14" stroke-linecap="round"/>
    </g>
  </g>"""

SCENE = f"""{FIELD}
  {CRATE}"""

SWEEP0, SWEEP1 = 0.07, 0.45


def _green(i):
    t = SWEEP0 + (SWEEP1 - SWEEP0) * (i + 1) / N
    return [(0, {"fill": PALE}), (t - 0.03, {"fill": PALE}), (t, {"fill": ACCENT}),
            (0.56, {"fill": ACCENT}), (0.57, {"fill": PALE}), (1, {"fill": PALE})]


def _drop(t0):
    up = {"transform": "translateY(-210px)", "opacity": 0}
    on = {"transform": "translateY(0px)", "opacity": 1}
    return [(0, up), (t0, up), (t0 + 0.01, {"transform": "translateY(-180px)", "opacity": 1}),
            (t0 + 0.07, {"transform": "translateY(8px)", "opacity": 1}),
            (t0 + 0.095, on), (0.95, on), (0.96, up), (1, up)]


LOOP = [
    (".field", STAGE_ORIGIN, [
        (0, HIDE), (0.03, SHOW), (0.50, SHOW), (0.56, HIDE), (1, HIDE),
    ]),
    (".arm", f"view-box|{CX}px {CY}px", [
        (0, {"transform": "rotate(0deg)"}), (SWEEP0, {"transform": "rotate(0deg)"}),
        (SWEEP1, {"transform": "rotate(360deg)"}), (1, {"transform": "rotate(360deg)"}),
    ]),
] + [(f".s{i}", None, _green(i)) for i in range(N)] + [
    (".crate", STAGE_ORIGIN, [
        (0, HIDE), (0.54, HIDE), (0.58, SHOW), (0.88, SHOW), (0.94, HIDE), (1, HIDE),
    ]),
    (".cabbage", None, _drop(0.58)),
    (".potato", None, _drop(0.67)),
    (".onion", None, _drop(0.76)),
]

LOOP_MS = 5800
