"""Generate the Production marks' SVGs, one per scene.

    python3 scripts/build_production_logo.py

Same pattern as Upande SCP and Livestock (scripts/build_scp_logo.py). At rest every
mark IS the Upande mark (white disc with its thin rim, the arrow where upande_logo.png
has it on a 689 canvas). On hover the arrow shrinks into the centre and a scene plays; it loops
while the pointer stays and eases back out on leave. Keyframes are written once per
scene and emitted both as CSS (the splash loader, shown through <img>) and as JSON
in <metadata> (production_logo_motion.js on the desk, ProductionMark.tsx in the app).

Scenes live in scripts/logo_scenes/, one module each (see its __init__):

* ``productivity`` - the top-level mark: ``production_logo.svg`` (desk tile, app
  before a crop is chosen) and ``production_logo_loader.svg`` (splash).
* every other module is a crop's own scene, keyed by crop_key:
  ``production_logo_<crop_key>.svg`` and ``production_logo_<crop_key>_loader.svg``.
  The app sidebar and the splash switch to it once that crop is open.

Every desk-tile SVG is also copied to frontend/src/assets for ProductionMark.tsx.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logo_scenes  # noqa: E402

APP = Path(__file__).resolve().parents[1]
ROOT = APP / "upande_production" / "public" / "images"
FRONTEND_ASSETS = APP / "frontend" / "src" / "assets"

# -- artwork (689 x 689, the PNG's own canvas) --------------------------------

ARROW = """<g class="arrow">
    <g transform="translate(169 165)">
      <path fill="#625d59" d="M0 0 H272 V85 H0 Z"/>
      <path fill="#45433f" d="M272 0 H359 V364 H272 Z"/>
      <path fill="#1a1917" d="M246 85 H272 V161 L246 187 Z"/>
      <path fill="#45433f" d="M198 85 H246 V187 L69 364 H0 V283 Z"/>
    </g>
  </g>"""


def body(scene, rest_hidden: bool) -> str:
    hide = ' opacity="0"' if rest_hidden else ""
    return f"""  <clipPath id="production-disc"><circle cx="344.5" cy="344.5" r="336"/></clipPath>
  <!-- the white disc of upande_logo.png, with its thin dark rim -->
  <circle cx="344.5" cy="344.5" r="340" fill="#ffffff" stroke="#1c1b19" stroke-opacity=".3" stroke-width="7"/>
  <g clip-path="url(#production-disc)">
  <g class="scene"{hide}>
  <g transform="{scene.SCENE_TRANSFORM}">
  {scene.SCENE}
  </g>
  </g>
  </g>
  {ARROW}
"""


# -- motion (shared by every scene) -------------------------------------------
# Each entry: selector, transform-origin (view-box px), keyframes [offset, props].
# ENTER runs 0 -> 1 on hover (and back on leave); a scene's LOOP is its story.

ARROW_HOME = "translate(0px, 0px) scale(1)"
ARROW_GONE = "translate(0px, 0px) scale(0)"

ENTER = [
    # The arrow shrinks into the centre of the disc and fades, so the scene has the whole
    # disc; on leave it grows back out of the centre.
    (".arrow", "348.5px 347px", [
        (0, {"transform": ARROW_HOME, "opacity": 1}),
        (0.45, {"transform": ARROW_GONE, "opacity": 0}),
        (1, {"transform": ARROW_GONE, "opacity": 0}),
    ]),
    (".scene", None, [
        (0, {"opacity": 0}),
        (0.2, {"opacity": 1}),
        (1, {"opacity": 1}),
    ]),
]

ENTER_MS = 1500
# Every scene's story plays this much slower than its LOOP_MS on hover: calm, not busy.
PACE = 1.4
EASE = "cubic-bezier(.3,.7,.2,1)"


# -- emit ---------------------------------------------------------------------

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


def loader_css(loop) -> str:
    """One cycle: enter (0–18%), the round (18–82%), back out (82–100%)."""
    # One full pass (arrow in, the scene, arrow back out) in the 4 s the splash is held for.
    cycle_ms = 4000
    a, b = 18.0, 82.0
    lines = ["  <style>"]
    lines += _origin_rules(ENTER + loop)
    keyframes = []
    for i, (sel, _o, frames) in enumerate(ENTER):
        name = f"production-in-{i}"
        steps = {}
        for off, props in frames:
            steps[round(off * a, 2)] = props
            steps[round(100 - off * (100 - b), 2)] = props
        keyframes.append((sel, name, sorted(steps.items())))
    for i, (sel, _o, frames) in enumerate(loop):
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



def motion_json(loop, loop_ms) -> str:
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
        {"enterMs": ENTER_MS, "loopMs": loop_ms, "ease": EASE, "enter": tracks(ENTER), "loop": tracks(loop)},
        separators=(",", ":"),
    )


HEAD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 689 689" width="689" height="689" role="img" aria-label="{label}">'


def check(key: str, tracks) -> None:
    """Browsers reject (and the app used to crash on) keyframes whose offsets go backwards."""
    for sel, _origin, frames in tracks:
        offs = [o for o, _ in frames]
        if any(o < 0 or o > 1 for o in offs) or any(b < a for a, b in zip(offs, offs[1:])):
            raise SystemExit(f"{key}: {sel} offsets out of order: {offs}")


def write(key: str, scene) -> None:
    check(key, ENTER + scene.LOOP)
    stem = "production_logo" if key == "productivity" else f"production_logo_{key}"
    desk = "\n".join([
        HEAD.format(label=scene.LABEL),
        "  <!-- Generated by scripts/build_production_logo.py from logo_scenes — edit there.",
        "       At rest this is the Upande mark; the scene plays on hover. -->",
        f'  <metadata id="production-motion">{motion_json(scene.LOOP, round(scene.LOOP_MS * PACE))}</metadata>',
        body(scene, rest_hidden=True) + "</svg>",
        "",
    ])
    (ROOT / f"{stem}.svg").write_text(desk)
    (FRONTEND_ASSETS / f"{stem}.svg").write_text(desk)
    loader = "\n".join([
        HEAD.format(label=f"Upande {scene.LABEL}"),
        "  <!-- Generated by scripts/build_production_logo.py from logo_scenes — edit there.",
        "       The splash loader: the scene on a loop (in, the story, out). Pure CSS. -->",
        loader_css(scene.LOOP),
        body(scene, rest_hidden=False) + "</svg>",
        "",
    ])
    (ROOT / f"{stem}_loader.svg").write_text(loader)
    print("wrote", stem)


def main(only: list[str] | None = None):
    FRONTEND_ASSETS.mkdir(parents=True, exist_ok=True)
    for mod in pkgutil.iter_modules(logo_scenes.__path__):
        if mod.name == "common":
            continue
        key = mod.name.replace("_", "-")
        if only and key not in only:
            continue
        write(key, importlib.import_module(f"logo_scenes.{mod.name}"))


if __name__ == "__main__":
    main(sys.argv[1:] or None)
