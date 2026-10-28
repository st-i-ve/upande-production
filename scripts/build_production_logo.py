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

THE SCENE (Production's own): the arrow steps aside to the top right and an
avocado branch slides in with three fruit on it. The harvest round: the fruit
ripen from pale to the avocado green, a ring marks each one that is ready (the
dry-matter check), it is picked and drops into the picking crate, and the crate
fills. Then the crate empties and the branch fruits regrow for the next round.
On the desk the branch eases in on hover, the round loops while the pointer
stays, and on leave it all eases back out to the plain mark.

Keyframes are written once (``ENTER`` and ``LOOP``) and emitted both as CSS for
the loader and as JSON for the desk script and the React mark.
"""

from __future__ import annotations

import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP / "upande_production" / "public" / "images"
FRONTEND_ASSETS = APP / "frontend" / "src" / "assets"

INK = "#45433f"
ACCENT = "#3f7d3a"
RIPE_FROM = "#c6dc9c"

# -- artwork (689 x 689, the PNG's own canvas) --------------------------------

ARROW = """<g class="arrow">
    <g transform="translate(169 165)">
      <path fill="#625d59" d="M0 0 H272 V85 H0 Z"/>
      <path fill="#45433f" d="M272 0 H359 V364 H272 Z"/>
      <path fill="#1a1917" d="M246 85 H272 V161 L246 187 Z"/>
      <path fill="#45433f" d="M198 85 H246 V187 L69 364 H0 V283 Z"/>
    </g>
  </g>"""

# A hanging avocado, drawn with its stalk end at 0,0, about 105 wide and 128 tall.
PEAR = "M0 0 C-12 0 -19 17 -31 43 C-53 85 -44 128 0 128 C44 128 53 85 31 43 C19 17 12 0 0 0 Z"

FRUIT_X = (96, 232, 368)
BRANCH_Y = (178, 182, 172)  # the branch's height where each fruit hangs


def fruit(i: int) -> str:
    x, y = FRUIT_X[i], BRANCH_Y[i] + 8
    return f"""<g transform="translate({x} {y}) scale(1.3)">
      <g class="hang"><g class="pick pick{i}">
        <path d="M0 -10 L0 8" stroke="{INK}" stroke-width="9" stroke-linecap="round"/>
        <path class="body" d="{PEAR}" fill="{RIPE_FROM}" stroke="{INK}" stroke-width="7" stroke-linejoin="round"/>
        <path d="M-20 52 C-30 72 -26 92 -16 104" stroke="#ffffff" stroke-opacity=".55" stroke-width="9" stroke-linecap="round" fill="none"/>
      </g></g>
    </g>"""


# Fruit already in the crate: smaller, tucked behind the crate's front.
CRATE_FRUIT_AT = ((236, 468), (344, 456), (452, 468))


def crate_fruit(i: int) -> str:
    x, y = CRATE_FRUIT_AT[i]
    rot = (-74, 8, 70)[i]
    return f"""<g transform="translate({x} {y}) rotate({rot})">
      <g class="stow stow{i}">
        <path d="{PEAR}" transform="translate(0 -72) scale(1.1)" fill="{ACCENT}" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/>
        <path d="M-20 -26 C-30 -8 -26 12 -16 24" stroke="#ffffff" stroke-opacity=".5" stroke-width="8" stroke-linecap="round" fill="none"/>
      </g>
    </g>"""


BRANCH = f"""<g class="branch">
    <path d="M10 196 C140 156 270 196 424 146" stroke="{INK}" stroke-width="24" stroke-linecap="round" fill="none"/>
    <path d="M168 176 C186 128 232 118 262 128 C246 166 208 184 168 176 Z" fill="#8dba7a" stroke="{ACCENT}" stroke-width="8" stroke-linejoin="round"/>
    <path d="M300 168 C318 116 366 104 398 112 C384 152 342 176 300 168 Z" fill="#8dba7a" stroke="{ACCENT}" stroke-width="8" stroke-linejoin="round"/>
    <path d="M60 192 C60 148 90 126 124 122 C126 160 98 192 60 192 Z" fill="#8dba7a" stroke="{ACCENT}" stroke-width="8" stroke-linejoin="round"/>
  </g>"""

FRUITS = "\n    ".join(fruit(i) for i in range(3))

# The picking crate: back wall, then the stowed fruit, then the slatted front.
CRATE_BACK = f"""<g class="crate">
    <path d="M178 470 L500 470 L488 600 L190 600 Z" fill="#d9d4cb" stroke="{INK}" stroke-width="14" stroke-linejoin="round"/>
  </g>"""
CRATE_FRONT = f"""<g class="crate-front">
    <path d="M168 486 H510 L498 604 H180 Z" fill="#ffffff" stroke="{INK}" stroke-width="16" stroke-linejoin="round"/>
    <path d="M174 530 H504 M177 568 H501" stroke="{INK}" stroke-width="12" stroke-linecap="round"/>
    <path d="M168 470 H510" stroke="{INK}" stroke-width="22" stroke-linecap="round"/>
  </g>"""

RINGS = "\n    ".join(
    f'<circle class="ring ring{i}" cx="{FRUIT_X[i]}" cy="{BRANCH_Y[i] + 100}" r="104" fill="none" stroke="{ACCENT}" stroke-width="20"/>'
    for i in range(3)
)
STOW = "\n  ".join(crate_fruit(i) for i in range(3))


def body(rest_hidden: bool) -> str:
    hide = ' opacity="0"' if rest_hidden else ""
    return f"""  <clipPath id="production-disc"><circle cx="344.5" cy="344.5" r="336"/></clipPath>
  <!-- the white disc of upande_logo.png, with its thin dark rim -->
  <circle cx="344.5" cy="344.5" r="340" fill="#ffffff" stroke="#1c1b19" stroke-opacity=".3" stroke-width="7"/>
  <g clip-path="url(#production-disc)">
  <g class="scene"{hide}>
  {BRANCH}
  {FRUITS}
  <g class="marks">
    {RINGS}
  </g>
  {CRATE_BACK}
  {STOW}
  {CRATE_FRONT}
  </g>
  {ARROW}
  </g>
"""


# -- motion -------------------------------------------------------------------
# Each entry: selector, transform-origin (view-box px), keyframes [offset, props].
# ENTER runs 0 -> 1 on hover (and back on leave). LOOP is the harvest round.

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
        (0.12, {"opacity": 1}),
        (1, {"opacity": 1}),
    ]),
    # the branch slides in from the left edge; the crate rises from below
    (".branch", None, [
        (0, {"transform": "translate(-160px, 0px)"}),
        (0.15, {"transform": "translate(-160px, 0px)"}),
        (0.75, {"transform": "translate(0px, 0px)"}),
        (1, {"transform": "translate(0px, 0px)"}),
    ]),
    (".crate, .crate-front", None, [
        (0, {"transform": "translate(0px, 190px)"}),
        (0.3, {"transform": "translate(0px, 190px)"}),
        (0.9, {"transform": "translate(0px, 0px)"}),
        (1, {"transform": "translate(0px, 0px)"}),
    ]),
    (".hang", "fill-box|50% 0%", [
        (0, {"transform": "scale(0)"}),
        (0.45, {"transform": "scale(0)"}),
        (0.85, {"transform": "scale(1.06)"}),
        (1, {"transform": "scale(1)"}),
    ]),
]

FALL = "translate(0px, 300px) scale(.8)"
HOME = "translate(0px, 0px) scale(1)"
GONE = "translate(0px, 0px) scale(0)"


def _pick(lo, hi):
    """Hang, get picked at ``lo``, drop to the crate by ``hi``, regrow at the end."""
    return [
        (0, {"transform": HOME, "opacity": 1}),
        (lo, {"transform": HOME, "opacity": 1}),
        (lo + 0.03, {"transform": "translate(0px, -8px) scale(1)", "opacity": 1}),
        (hi - 0.02, {"transform": "translate(0px, 230px) scale(.85)", "opacity": 1}),
        (hi, {"transform": FALL, "opacity": 0}),
        (0.93, {"transform": FALL, "opacity": 0}),
        (0.931, {"transform": GONE, "opacity": 0}),
        (0.99, {"transform": HOME, "opacity": 1}),
        (1, {"transform": HOME, "opacity": 1}),
    ]


def _ring(lo, hi):
    return [
        (0, {"transform": "scale(.6)", "opacity": 0}),
        (lo, {"transform": "scale(.6)", "opacity": 0}),
        (lo + 0.03, {"transform": "scale(.8)", "opacity": 1}),
        (hi, {"transform": "scale(1.2)", "opacity": 0}),
        (1, {"transform": "scale(1.2)", "opacity": 0}),
    ]


def _stow(at):
    return [
        (0, {"transform": "scale(0)", "opacity": 0}),
        (at, {"transform": "scale(0)", "opacity": 0}),
        (at + 0.04, {"transform": "scale(1.12)", "opacity": 1}),
        (at + 0.08, {"transform": "scale(1)", "opacity": 1}),
        (0.9, {"transform": "scale(1)", "opacity": 1}),
        (0.97, {"transform": "scale(0)", "opacity": 0}),
        (1, {"transform": "scale(0)", "opacity": 0}),
    ]


def _ripen(lo, hi):
    return [
        (0, {"fill": RIPE_FROM}),
        (lo, {"fill": RIPE_FROM}),
        (hi, {"fill": ACCENT}),
        (0.93, {"fill": ACCENT}),
        (0.95, {"fill": RIPE_FROM}),
        (1, {"fill": RIPE_FROM}),
    ]


# The round: the fruit ripen in turn, each is ringed (the dry-matter check),
# picked and dropped into the crate, which fills up; then it all resets.
LOOP = [
    (".pick0 .body", None, _ripen(0.0, 0.22)),
    (".pick1 .body", None, _ripen(0.12, 0.40)),
    (".pick2 .body", None, _ripen(0.26, 0.56)),
    (".pick0", "fill-box|50% 0%", _pick(0.24, 0.36)),
    (".pick1", "fill-box|50% 0%", _pick(0.42, 0.54)),
    (".pick2", "fill-box|50% 0%", _pick(0.58, 0.70)),
    (".ring0", f"view-box|{FRUIT_X[0]}px {BRANCH_Y[0] + 100}px", _ring(0.18, 0.26)),
    (".ring1", f"view-box|{FRUIT_X[1]}px {BRANCH_Y[1] + 100}px", _ring(0.36, 0.44)),
    (".ring2", f"view-box|{FRUIT_X[2]}px {BRANCH_Y[2] + 100}px", _ring(0.52, 0.60)),
    (".stow0", "fill-box|50% 100%", _stow(0.34)),
    (".stow1", "fill-box|50% 100%", _stow(0.52)),
    (".stow2", "fill-box|50% 100%", _stow(0.68)),
]

ENTER_MS = 1100
LOOP_MS = 3600
EASE = "cubic-bezier(.3,.7,.2,1)"


# ── emit ───────────────────────────────────────────────────────────────────


def _css_props(props: dict) -> str:
    out = []
    for k, v in props.items():
        name = {"strokeDashoffset": "stroke-dashoffset"}.get(k, k)
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
        "       the Production scene on a loop (in, the harvest round, out). Pure CSS. -->",
        loader_css(),
        body(rest_hidden=False) + "</svg>",
        "",
    ])
    (ROOT / "production_logo_loader.svg").write_text(loader)
    print("wrote", ROOT / "production_logo.svg", "and", ROOT / "production_logo_loader.svg")


if __name__ == "__main__":
    main()
