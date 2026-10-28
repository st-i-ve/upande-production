"""Avocado: the harvest round.

Three Hass fruit hang from a leafy branch as solid silhouettes and darken as they ripen. A green check
badge marks each one that passes the dry-matter test, it is picked and drops into a field crate. Then one
is shown in section (skin, flesh, stone), the fruit are cleared and the branch fruits regrow.
Flat solid shapes, no outlines, no highlights; ink tones plus the crop accent for meaning.
"""

from .common import ACCENT, INK, MID

LABEL = "Avocado"
SCENE_TRANSFORM = "translate(0 0)"

UNRIPE = "#86aa78"
RIPE = INK
FLESH = "#cfe0c4"
STONE = "#625d59"
PANEL = "#e6e2da"

# A hanging Hass avocado, stalk end at 0,0, about 92 wide and 128 tall.
PEAR = "M0 0 C-13 0 -21 15 -33 40 C-60 86 -46 128 0 128 C46 128 60 86 33 40 C21 15 13 0 0 0 Z"
S = 1.25

FRUIT_X = (196, 344, 492)
FRUIT_Y = (206, 200, 192)      # top of each fruit (stalk joins here)
CRATE_X = (236, 344, 452)      # where each lands
CRATE_ROT = (-9, 3, 9)
DROP = (148, 158, 146)         # how far it falls

CHECK = f"""<g class="chk chk{{i}}">
          <circle cx="0" cy="0" r="26" fill="{ACCENT}"/>
          <path d="M-11 0 L-3 9 L12 -9" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
        </g>"""


def fruit(i: int) -> str:
    return f"""<g transform="translate({FRUIT_X[i]} {FRUIT_Y[i]})">
      <g class="pick pick{i}">
        <rect x="-4" y="-26" width="8" height="30" fill="{INK}"/>
        <g transform="scale({S})">
          <path class="body body{i}" d="{PEAR}" fill="{UNRIPE}"/>
        </g>
        <g transform="translate(0 74)">
        {CHECK.format(i=i)}
        </g>
      </g>
    </g>"""


def leaf(x, y, rot, s=1.0):
    return (f'<path transform="translate({x} {y}) rotate({rot}) scale({s})" fill="{ACCENT}" '
            f'd="M0 0 C22 -32 78 -38 124 0 C78 38 22 32 0 0 Z"/>')


BRANCH = f"""<g class="branch">
    <path d="M24 206 C150 172 250 186 344 174 C440 162 540 170 668 148" fill="none" stroke="{INK}" stroke-width="16" stroke-linecap="round"/>
    {leaf(92, 192, -38)}
    {leaf(276, 180, -62, .95)}
    {leaf(414, 170, -120, .95)}
    {leaf(580, 162, -146)}
    {leaf(150, 190, 28, .8)}
    {leaf(545, 164, 150, .8)}
  </g>"""

FRUITS = "\n    ".join(fruit(i) for i in range(3))


# the crate is symmetric about x=344
def slat_sym(y0, y1):
    k = 16 / 128
    a, b = 176 + (y0 - 470) * k, 176 + (y1 - 470) * k
    return f"M{a:.1f} {y0} H{688 - a:.1f} L{688 - b:.1f} {y1} H{b:.1f} Z"


CRATE = f"""<g class="crate-front">
    <path d="{slat_sym(486, 600)}" fill="{PANEL}"/>
    <path d="{slat_sym(490, 524)}" fill="{MID}"/>
    <path d="{slat_sym(534, 566)}" fill="{MID}"/>
    <path d="{slat_sym(576, 600)}" fill="{MID}"/>
    <rect x="164" y="462" width="360" height="24" rx="5" fill="{INK}"/>
  </g>"""

# The fruit in section: skin, flesh, stone.
HALF = f"""<g class="half" transform="translate(344 194) scale(1.12)">
    <g class="halfin">
      <path d="{PEAR}" transform="translate(0 -64) translate(0 64)" fill="{INK}"/>
      <path d="{PEAR}" transform="translate(0 88) scale(.86) translate(0 -88)" fill="{FLESH}"/>
      <circle cx="0" cy="88" r="24" fill="{STONE}"/>
    </g>
  </g>"""

SCENE = f"""{BRANCH}
  {FRUITS}
  {CRATE}
  {HALF}"""

HOME = "translate(0px, 0px) rotate(0deg)"


def _pick(i, lo, hi):
    end = f"translate({CRATE_X[i] - FRUIT_X[i]}px, {DROP[i]}px) rotate({CRATE_ROT[i]}deg)"
    return [
        (0, {"transform": HOME, "opacity": 1}),
        (lo, {"transform": HOME, "opacity": 1}),
        (hi, {"transform": end, "opacity": 1}),
        (0.90, {"transform": end, "opacity": 1}),
        (0.95, {"transform": end, "opacity": 0}),
        (0.951, {"transform": HOME, "opacity": 0}),
        (1, {"transform": HOME, "opacity": 1}),
    ]


def _chk(lo):
    return [
        (0, {"transform": "scale(0)", "opacity": 0}),
        (lo, {"transform": "scale(0)", "opacity": 0}),
        (lo + 0.04, {"transform": "scale(1)", "opacity": 1}),
        (1, {"transform": "scale(1)", "opacity": 1}),
    ]


def _ripen(lo, hi):
    return [
        (0, {"fill": UNRIPE}), (lo, {"fill": UNRIPE}), (hi, {"fill": RIPE}),
        (0.95, {"fill": RIPE}), (0.951, {"fill": UNRIPE}), (1, {"fill": UNRIPE}),
    ]


def _chk_full(lo):
    fr = _chk(lo)
    # hide again with the fruit, ready for the next round
    return fr[:-1] + [(0.95, {"transform": "scale(1)", "opacity": 1}),
                      (0.951, {"transform": "scale(0)", "opacity": 0}), (1, {"transform": "scale(0)", "opacity": 0})]


LOOP = [
    (".body0", None, _ripen(0.02, 0.16)),
    (".body1", None, _ripen(0.08, 0.24)),
    (".body2", None, _ripen(0.14, 0.32)),
    (".chk0", "fill-box|50% 50%", _chk_full(0.17)),
    (".chk1", "fill-box|50% 50%", _chk_full(0.25)),
    (".chk2", "fill-box|50% 50%", _chk_full(0.33)),
    (".pick0", "fill-box|50% 50%", _pick(0, 0.23, 0.33)),
    (".pick1", "fill-box|50% 50%", _pick(1, 0.38, 0.48)),
    (".pick2", "fill-box|50% 50%", _pick(2, 0.50, 0.60)),
    (".halfin", "view-box|344px 360px", [
        (0, {"transform": "translate(0px, 12px)", "opacity": 0}), (0.64, {"transform": "translate(0px, 12px)", "opacity": 0}),
        (0.72, {"transform": "translate(0px, 0px)", "opacity": 1}), (0.86, {"transform": "translate(0px, 0px)", "opacity": 1}),
        (0.92, {"transform": "translate(0px, 0px)", "opacity": 0}), (1, {"transform": "translate(0px, 12px)", "opacity": 0}),
    ]),
]

LOOP_MS = 5600
