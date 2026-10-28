"""Generate the Production mark's SVGs from one description.

    python3 scripts/build_production_logo.py

Same pattern as Upande SCP and Livestock (scripts/build_scp_logo.py):

* ``public/images/production_logo.svg`` - the desk tile. At rest it IS the Upande
  mark (white disc with its thin rim, the arrow at the same place and size as
  upande_logo.png on a 689 canvas). The scene is in the file but hidden;
  ``public/js/production_logo_motion.js`` inlines the file and plays it on hover,
  reading the keyframes from the ``<metadata>`` below.
* ``public/images/production_logo_loader.svg`` - the splash loader: the same scene
  as a pure-CSS loop (the splash shows it through ``<img>``, where scripts never run).
* ``frontend/src/assets/production_logo.svg`` - a copy of the desk tile, imported
  raw by ``ProductionMark.tsx`` for the app sidebar.

THE SCENE: Production is about output, whatever the crop, so the mark is about
productivity and no crop. The arrow steps aside to the top right and, in the
mono ink of the other marks with one green accent, a short story plays in the
middle of the disc:

  1. a checklist: three tasks tick off, one after another (the plan is done);
  2. it gives way to a bar chart: three bars rise, then a green trend arrow
     shoots up over them (echoing the Upande arrow);
  3. that gives way to a gauge: the needle sweeps across, overshoots and settles
     in the green zone (output on target).

Then it eases out and the loop starts again. On the desk it eases in on hover, the
round loops while the pointer stays, and on leave everything eases back out to the
plain mark. Keyframes are written once (``ENTER`` and ``LOOP``) and emitted both as
CSS for the loader and as JSON for the desk script and the React mark.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP / "upande_production" / "public" / "images"
FRONTEND_ASSETS = APP / "frontend" / "src" / "assets"

INK = "#45433f"
ACCENT = "#3f7d3a"
PALE = "#d6d1c8"
MID = "#a9a49b"

# -- artwork (689 x 689, the PNG's own canvas) --------------------------------

ARROW = """<g class="arrow">
    <g transform="translate(169 165)">
      <path fill="#625d59" d="M0 0 H272 V85 H0 Z"/>
      <path fill="#45433f" d="M272 0 H359 V364 H272 Z"/>
      <path fill="#1a1917" d="M246 85 H272 V161 L246 187 Z"/>
      <path fill="#45433f" d="M198 85 H246 V187 L69 364 H0 V283 Z"/>
    </g>
  </g>"""

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


def body(rest_hidden: bool) -> str:
    hide = ' opacity="0"' if rest_hidden else ""
    return f"""  <clipPath id="production-disc"><circle cx="344.5" cy="344.5" r="336"/></clipPath>
  <!-- the white disc of upande_logo.png, with its thin dark rim -->
  <circle cx="344.5" cy="344.5" r="340" fill="#ffffff" stroke="#1c1b19" stroke-opacity=".3" stroke-width="7"/>
  <g clip-path="url(#production-disc)">
  <g class="scene"{hide}>
  <g transform="translate(344 420) scale(1.14) translate(-344 -420)">
  {CHECKLIST}
  {BARS}
  {GAUGE}
  </g>
  </g>
  </g>
  {ARROW}
"""


# -- motion -------------------------------------------------------------------
# Each entry: selector, transform-origin (view-box px), keyframes [offset, props].
# ENTER runs 0 -> 1 on hover (and back on leave). LOOP is the productivity story.

ARROW_HOME = "translate(0px, 0px) scale(1)"
ARROW_ASIDE = "translate(186px, -190px) scale(.3)"

ENTER = [
    (".arrow", "348.5px 347px", [
        (0, {"transform": ARROW_HOME}),
        (0.55, {"transform": ARROW_ASIDE}),
        (1, {"transform": ARROW_ASIDE}),
    ]),
    (".scene", None, [
        (0, {"opacity": 0}),
        (0.2, {"opacity": 1}),
        (1, {"opacity": 1}),
    ]),
]

SHOW = {"transform": "scale(1)", "opacity": 1}
HIDE = {"transform": "scale(.86)", "opacity": 0}


def _stage(*pts):
    """A stage group: (offset, 'show'|'hide') pairs, starting from the first."""
    return [(o, SHOW if s else HIDE) for o, s in pts]


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

ENTER_MS = 1000
LOOP_MS = 5600
EASE = "cubic-bezier(.3,.7,.2,1)"


# ── emit ───────────────────────────────────────────────────────────────────


def _css_props(props: dict) -> str:
    out = []
    for k, v in props.items():
        name = {"strokeDashoffset": "stroke-dashoffset", "strokeWidth": "stroke-width"}.get(k, k)
        out.append(f"{name}: {v}")
    return "; ".join(out)


def _origin(origin: str) -> tuple[str, str]:
    """"fill-box|50% 100%" → (box, origin); a bare origin is in view-box px."""
    box, _, at = origin.rpartition("|")
    return (box or "view-box", at)


def _origin_rules(tracks) -> list[str]:
    rules = []
    for sel, origin, _ in tracks:
        if origin:
            box, at = _origin(origin)
            rules.append(f"    {sel} {{ transform-box: {box}; transform-origin: {at}; }}")
    return rules


def loader_css() -> str:
    """One cycle: enter (0–18%), the round (18–82%), back out (82–100%)."""
    cycle_ms = 4600
    a, b = 18.0, 82.0
    lines = ["  <style>"]
    lines += _origin_rules(ENTER + LOOP)
    keyframes = []
    for i, (sel, _o, frames) in enumerate(ENTER):
        name = f"production-in-{i}"
        steps = {}
        for off, props in frames:
            steps[round(off * a, 2)] = props
            steps[round(100 - off * (100 - b), 2)] = props
        keyframes.append((sel, name, sorted(steps.items())))
    for i, (sel, _o, frames) in enumerate(LOOP):
        name = f"production-round-{i}"
        first = frames[0][1]
        steps = {0.0: first}
        for off, props in frames:
            steps[round(a + off * (b - a), 2)] = props
        steps[100.0] = first
        keyframes.append((sel, name, sorted(steps.items())))
    for sel, name, _ in keyframes:
        lines.append(f"    {sel} {{ animation: {name} {cycle_ms}ms {EASE} infinite both; }}")
    for _sel, name, steps in keyframes:
        lines.append(f"    @keyframes {name} {{")
        for pct, props in steps:
            lines.append(f"      {pct:g}% {{ {_css_props(props)}; }}")
        lines.append("    }")
    lines.append("    @media (prefers-reduced-motion: reduce) {")
    lines.append("      .arrow, .scene, .scene * { animation: none !important; }")
    lines.append("      .scene { opacity: 0; }")
    lines.append("    }")
    lines.append("  </style>")
    return "\n".join(lines)


def motion_json() -> str:
    def tracks(t):
        return [
            {
                "sel": sel,
                "box": _origin(origin)[0] if origin else None,
                "origin": _origin(origin)[1] if origin else None,
                "frames": [dict(offset=o, **p) for o, p in frames],
            }
            for sel, origin, frames in t
        ]

    return json.dumps(
        {"enterMs": ENTER_MS, "loopMs": LOOP_MS, "ease": EASE, "enter": tracks(ENTER), "loop": tracks(LOOP)},
        separators=(",", ":"),
    )


HEAD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 689 689" width="689" height="689" role="img" aria-label="{label}">'


def main():
    desk = "\n".join([
        HEAD.format(label="Production"),
        "  <!-- Generated by scripts/build_production_logo.py — edit there. At rest this is",
        "       the Upande mark; production_logo_motion.js plays the scene on hover. -->",
        f'  <metadata id="production-motion">{motion_json()}</metadata>',
        body(rest_hidden=True) + "</svg>",
        "",
    ])
    (ROOT / "production_logo.svg").write_text(desk)
    FRONTEND_ASSETS.mkdir(parents=True, exist_ok=True)
    (FRONTEND_ASSETS / "production_logo.svg").write_text(desk)

    loader = "\n".join([
        HEAD.format(label="Upande Production"),
        "  <!-- Generated by scripts/build_production_logo.py — edit there. The splash loader:",
        "       the Production scene on a loop (in, the story, out). Pure CSS. -->",
        loader_css(),
        body(rest_hidden=False) + "</svg>",
        "",
    ])
    (ROOT / "production_logo_loader.svg").write_text(loader)
    print("wrote", ROOT / "production_logo.svg", "and", ROOT / "production_logo_loader.svg")


if __name__ == "__main__":
    main()
