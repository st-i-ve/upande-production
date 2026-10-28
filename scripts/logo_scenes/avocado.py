"""Avocado: the harvest round.

Three Hass-style fruit ripen on the branch (pale green to dark, pebbled skin), a ring marks each ripe one
(the dry-matter check), it is picked and drops into the crate. Then one is cut open on the spot, flesh and
pit showing, the crate empties and the fruit regrow.
"""

from .common import ACCENT, INK, PALE

LABEL = "Avocado"
SCENE_TRANSFORM = "translate(0 0)"

RIPE_FROM = "#c9dea0"
RIPE_TO = "#3a6e36"
DARK = "#264d23"
LEAF = "#8dba7a"

# A hanging avocado, stalk end at 0,0, about 105 wide and 128 tall.
PEAR = "M0 0 C-12 0 -19 17 -31 43 C-53 85 -44 128 0 128 C44 128 53 85 31 43 C19 17 12 0 0 0 Z"
# Pebbles on the skin (x, y, r) in PEAR space.
PEBBLES = ((-14, 60, 4.2), (10, 52, 3.8), (22, 84, 4.4), (-27, 88, 4.2), (-4, 82, 4.6), (8, 108, 4),
           (-18, 110, 3.8), (-2, 36, 3.4), (30, 66, 3.6), (-32, 68, 3.4))


def pebbles(fill, op):
    return "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" fill-opacity="{op}"/>' for x, y, r in PEBBLES)


FRUIT_X = (130, 256, 384)
BRANCH_Y = (166, 170, 160)
S = 1.2


def fruit(i: int) -> str:
    x, y = FRUIT_X[i], BRANCH_Y[i] + 6
    return f"""<g transform="translate({x} {y}) scale({S})">
      <g class="pick pick{i}">
        <path d="M0 -8 L0 10" stroke="{INK}" stroke-width="9" stroke-linecap="round"/>
        <path class="body" d="{PEAR}" fill="{RIPE_FROM}" stroke="{INK}" stroke-width="7" stroke-linejoin="round"/>
        <g class="peb">{pebbles(DARK, .55)}</g>
        <path d="M-22 52 C-31 72 -27 92 -17 104" stroke="#ffffff" stroke-opacity=".45" stroke-width="8" stroke-linecap="round" fill="none"/>
      </g>
    </g>"""


CRATE_FRUIT_AT = ((246, 462), (344, 440), (442, 462))


def crate_fruit(i: int) -> str:
    x, y = CRATE_FRUIT_AT[i]
    rot = (-78, 0, 78)[i]
    return f"""<g transform="translate({x} {y}) rotate({rot})">
      <g class="stow stow{i}">
        <g transform="translate(0 -64) scale(1.0)">
          <path d="{PEAR}" fill="{RIPE_TO}" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/>
          {pebbles(DARK, .6)}
        </g>
      </g>
    </g>"""


BRANCH = f"""<g class="branch">
    <path d="M10 188 C140 150 270 190 440 140" stroke="{INK}" stroke-width="24" stroke-linecap="round" fill="none"/>
    <path d="M176 170 C194 122 240 112 270 122 C254 160 216 178 176 170 Z" fill="{LEAF}" stroke="{ACCENT}" stroke-width="8" stroke-linejoin="round"/>
    <path d="M310 164 C328 112 376 100 408 108 C394 148 352 172 310 164 Z" fill="{LEAF}" stroke="{ACCENT}" stroke-width="8" stroke-linejoin="round"/>
    <path d="M64 184 C64 140 94 118 128 114 C130 152 102 184 64 184 Z" fill="{LEAF}" stroke="{ACCENT}" stroke-width="8" stroke-linejoin="round"/>
  </g>"""

FRUITS = "\n    ".join(fruit(i) for i in range(3))
RINGS = "\n    ".join(
    f'<circle class="ring ring{i}" cx="{FRUIT_X[i]}" cy="{BRANCH_Y[i] + 104}" r="104" fill="none" stroke="{ACCENT}" stroke-width="20"/>'
    for i in range(3)
)
STOW = "\n  ".join(crate_fruit(i) for i in range(3))

CRATE_BACK = f"""<g class="crate">
    <path d="M178 470 L500 470 L488 600 L190 600 Z" fill="#d9d4cb" stroke="{INK}" stroke-width="14" stroke-linejoin="round"/>
  </g>"""
CRATE_FRONT = f"""<g class="crate-front">
    <path d="M168 486 H510 L498 604 H180 Z" fill="#ffffff" stroke="{INK}" stroke-width="16" stroke-linejoin="round"/>
    <path d="M174 530 H504 M177 568 H501" stroke="{INK}" stroke-width="12" stroke-linecap="round"/>
    <path d="M168 470 H510" stroke="{INK}" stroke-width="22" stroke-linecap="round"/>
  </g>"""

# The halved fruit: skin rim, pale flesh, the pit.
HALF = f"""<g class="half" transform="translate(300 214) scale(1.5)">
    <g class="halfin">
      <path d="{PEAR}" fill="{RIPE_TO}" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/>
      <path d="{PEAR}" transform="translate(0 84) scale(.8) translate(0 -84)" fill="#e6efb9"/>
      <circle cx="0" cy="88" r="25" fill="{INK}"/>
      <path d="M-11 80 C-8 74 -3 72 1 72" stroke="#ffffff" stroke-opacity=".5" stroke-width="5" stroke-linecap="round" fill="none"/>
    </g>
  </g>"""

SCENE = f"""{BRANCH}
  {FRUITS}
  <g class="marks">
    {RINGS}
  </g>
  {CRATE_BACK}
  {STOW}
  {CRATE_FRONT}
  {HALF}"""

HOME = "translate(0px, 0px) scale(1)"
FALL = "translate(0px, 300px) scale(.8)"
GONE = "translate(0px, 0px) scale(0)"


def _pick(lo, hi):
    return [
        (0, {"transform": HOME, "opacity": 1}),
        (lo, {"transform": HOME, "opacity": 1}),
        (lo + 0.03, {"transform": "translate(0px, -8px) scale(1)", "opacity": 1}),
        (hi - 0.02, {"transform": "translate(0px, 240px) scale(.85)", "opacity": 1}),
        (hi, {"transform": FALL, "opacity": 0}),
        (0.92, {"transform": FALL, "opacity": 0}),
        (0.921, {"transform": GONE, "opacity": 0}),
        (0.99, {"transform": HOME, "opacity": 1}),
        (1, {"transform": HOME, "opacity": 1}),
    ]


def _ring(lo, hi):
    return [
        (0, {"transform": "scale(.6)", "opacity": 0}),
        (lo, {"transform": "scale(.6)", "opacity": 0}),
        (lo + 0.03, {"transform": "scale(.85)", "opacity": 1}),
        (hi, {"transform": "scale(1.2)", "opacity": 0}),
        (1, {"transform": "scale(1.2)", "opacity": 0}),
    ]


def _stow(at):
    return [
        (0, {"transform": "scale(0)", "opacity": 0}),
        (at, {"transform": "scale(0)", "opacity": 0}),
        (at + 0.03, {"transform": "scale(1.12)", "opacity": 1}),
        (at + 0.06, {"transform": "scale(1)", "opacity": 1}),
        (0.88, {"transform": "scale(1)", "opacity": 1}),
        (0.95, {"transform": "scale(0)", "opacity": 0}),
        (1, {"transform": "scale(0)", "opacity": 0}),
    ]


def _ripen(lo, hi):
    return [
        (0, {"fill": RIPE_FROM}), (lo, {"fill": RIPE_FROM}), (hi, {"fill": RIPE_TO}),
        (0.92, {"fill": RIPE_TO}), (0.93, {"fill": RIPE_FROM}), (1, {"fill": RIPE_FROM}),
    ]


LOOP = [
    (".pick0 .body", None, _ripen(0.0, 0.16)),
    (".pick1 .body", None, _ripen(0.08, 0.28)),
    (".pick2 .body", None, _ripen(0.18, 0.40)),
    (".pick0", "fill-box|50% 0%", _pick(0.18, 0.28)),
    (".pick1", "fill-box|50% 0%", _pick(0.32, 0.42)),
    (".pick2", "fill-box|50% 0%", _pick(0.46, 0.56)),
    (".ring0", f"view-box|{FRUIT_X[0]}px {BRANCH_Y[0] + 104}px", _ring(0.13, 0.20)),
    (".ring1", f"view-box|{FRUIT_X[1]}px {BRANCH_Y[1] + 104}px", _ring(0.27, 0.34)),
    (".ring2", f"view-box|{FRUIT_X[2]}px {BRANCH_Y[2] + 104}px", _ring(0.41, 0.48)),
    (".stow0", "fill-box|50% 100%", _stow(0.27)),
    (".stow1", "fill-box|50% 100%", _stow(0.41)),
    (".stow2", "fill-box|50% 100%", _stow(0.55)),
    # one is cut open: flesh and pit
    (".halfin", "view-box|300px 340px", [
        (0, {"transform": "scale(0) rotate(-12deg)", "opacity": 0}), (0.60, {"transform": "scale(0) rotate(-12deg)", "opacity": 0}),
        (0.67, {"transform": "scale(1.1) rotate(0deg)", "opacity": 1}), (0.70, {"transform": "scale(1) rotate(0deg)", "opacity": 1}),
        (0.84, {"transform": "scale(1) rotate(0deg)", "opacity": 1}), (0.90, {"transform": "scale(0) rotate(8deg)", "opacity": 0}),
        (1, {"transform": "scale(0) rotate(8deg)", "opacity": 0}),
    ]),
]

LOOP_MS = 5600
