"""Fruits and vegetables: a centre-pivot field seen from above, then the harvest in a crate.

The pivot arm sweeps once round, each plot greening as it passes; then a cabbage, a potato and an
onion settle into a slatted field crate. Solid flat silhouettes, no outlines.
"""

import math

from .common import ACCENT, HIDE, INK, MID, PALE, SHOW

LABEL = "Fruits and vegetables"
ORANGE = "#c0662b"
ONION = "#7a756c"
SCENE_TRANSFORM = "translate(344 344) scale(1.2) translate(-344 -344)"
STAGE_ORIGIN = "view-box|344px 344px"

# 1. the pivot field seen from above: six plots, a fine arm, a soft spray wedge
CX, CY, R, HUB = 344, 344, 232, 24
N = 6
GAP = 2.2  # degrees of bare track between plots
FIELD_TONES = [PALE, "#e3dfd7"] * 3


def pt(a, r):
    return CX + r * math.cos(math.radians(a)), CY + r * math.sin(math.radians(a))


def slice_path(i):
    a0, a1 = -90 + 60 * i + GAP / 2, -90 + 60 * (i + 1) - GAP / 2
    (x0, y0), (x1, y1) = pt(a0, HUB), pt(a0, R)
    (x2, y2), (x3, y3) = pt(a1, R), pt(a1, HUB)
    return (f"M{x0:.1f} {y0:.1f} L{x1:.1f} {y1:.1f} A{R} {R} 0 0 1 {x2:.1f} {y2:.1f} "
            f"L{x3:.1f} {y3:.1f} A{HUB} {HUB} 0 0 0 {x0:.1f} {y0:.1f} Z")


SLICES = "\n    ".join(
    f'<path class="slice s{i}" d="{slice_path(i)}" fill="{FIELD_TONES[i]}"/>' for i in range(N)
)

_wx, _wy = pt(-90 - 26, R + 2)
FIELD = f"""<g class="field">
    {SLICES}
    <g class="arm">
      <path d="M{CX} {CY} L{_wx:.1f} {_wy:.1f} A{R + 2} {R + 2} 0 0 1 {CX} {CY - R - 2} Z" fill="{MID}" fill-opacity=".38"/>
      <path d="M{CX} {CY} V{CY - R - 6}" stroke="{INK}" stroke-width="7"/>
      <path d="M{CX - 5} {CY - R * .5:.0f} h10 v-14 h-10 Z M{CX - 5} {CY - R * .82:.0f} h10 v-14 h-10 Z" fill="{INK}"/>
      <rect x="{CX - 9}" y="{CY - R - 10}" width="18" height="20" rx="3" fill="{ORANGE}"/>
    </g>
    <circle cx="{CX}" cy="{CY}" r="17" fill="{INK}"/>
  </g>"""

# 2. the harvest: solid silhouettes settling into a slatted field crate
CRATE = f"""<g transform="translate(0 -102)"><g class="crate">
    <g class="cabbage"><g>
      <circle cx="262" cy="392" r="76" fill="{ACCENT}"/>
      <path d="M262 470 V338 M262 452 C226 430 218 392 232 352 M262 452 C298 430 306 392 292 352 M262 418 C238 408 230 392 232 378 M262 418 C286 408 294 392 292 378" fill="none" stroke="#ffffff" stroke-width="5.5" stroke-linecap="round"/>
    </g></g>
    <g class="potato"><g>
      <path d="M338 404 C340 372 378 356 410 366 C446 378 462 408 446 436 C430 462 380 466 354 450 C340 440 337 420 338 404 Z" fill="{ORANGE}"/>
    </g></g>
    <g class="onion"><g>
      <path d="M484 318 C486 340 490 350 506 366 C524 384 534 404 526 424 C518 442 500 450 484 450 C468 450 450 442 442 424 C434 404 444 384 462 366 C478 350 482 340 484 318 Z" fill="{ONION}"/>
      <path d="M484 434 v22 M476 434 l-8 20 M492 434 l8 20" stroke="{ONION}" stroke-width="4" stroke-linecap="round"/>
      <path d="M484 330 C470 372 462 408 468 440 M484 330 C498 372 506 408 500 440" fill="none" stroke="#ffffff" stroke-opacity=".7" stroke-width="3.5" stroke-linecap="round"/>
    </g></g>
    <g class="front">
      <path d="M170 448 H558 V570 a10 10 0 0 1 -10 10 H180 a10 10 0 0 1 -10 -10 Z" fill="{INK}"/>
      <path d="M170 448 H558 V470 H170 Z" fill="{ORANGE}"/>
      <path d="M170 488 H558 M170 520 H558 M170 552 H558" stroke="#ffffff" stroke-width="7"/>
      <path d="M214 470 V580 M514 470 V580" stroke="#ffffff" stroke-width="7"/>
    </g>
  </g></g>"""

SCENE = f"""{FIELD}
  {CRATE}"""

SWEEP0, SWEEP1 = 0.07, 0.45


def _green(i):
    PALE = FIELD_TONES[i]
    t = SWEEP0 + (SWEEP1 - SWEEP0) * (i + 1) / N
    return [(0, {"fill": PALE}), (t - 0.03, {"fill": PALE}), (t, {"fill": ACCENT}),
            (0.56, {"fill": ACCENT}), (0.57, {"fill": PALE}), (1, {"fill": PALE})]


def _drop(t0):
    up = {"transform": "translateY(-200px)", "opacity": 0}
    on = {"transform": "translateY(0px)", "opacity": 1}
    return [(0, up), (t0, up), (t0 + 0.015, {"transform": "translateY(-170px)", "opacity": 1}),
            (t0 + 0.085, on), (0.95, on), (0.96, up), (1, up)]


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
