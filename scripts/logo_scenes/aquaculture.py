"""Aquaculture: a tilapia pond.

Feed pellets drop through the waterline, the tilapia rises and takes them and grows, oxygen bubbles
rise, and a net lifts the grown fish out of the water.
"""

from .common import INK, MID, PALE

AQUA = "#2b6f9e"

LABEL = "Aquaculture"
SCENE_TRANSFORM = "translate(344 380) scale(1.0) translate(-344 -380)"

SURF = 300
# wave: 10 periods of 100 units, drifting one period per loop
_wave = "M-100 %d Q-75 %d -50 %d" % (SURF, SURF - 16, SURF) + "".join(
    " T%d %d" % (x, SURF) for x in range(0, 900, 50))

POND = f"""<g class="pond">
    <g class="wave">
      <path d="{_wave} V760 H-100 Z" fill="{AQUA}" fill-opacity=".2"/>
      <path d="{_wave}" fill="none" stroke="{AQUA}" stroke-width="14" stroke-linecap="round"/>
    </g>
  </g>"""

PELLET_X = (318, 356, 394)
PELLETS = "\n  ".join(
    f'<circle class="pel pel{i}" cx="{x}" cy="{150 + (i % 2) * 22}" r="18" fill="{INK}"/>'
    for i, x in enumerate(PELLET_X))

BUBBLES = "\n  ".join(
    f'<circle class="bub bub{i}" cx="{x}" cy="600" r="{r}" fill="#ffffff" stroke="{AQUA}" stroke-width="9"/>'
    for i, (x, r) in enumerate(((190, 20), (510, 24), (150, 14), (545, 15))))

NET = f"""<g class="net">
    <path d="M-140 0 Q-140 130 0 130 Q140 130 140 0 Z" fill="#ffffff" fill-opacity=".75" stroke="{INK}" stroke-width="12" stroke-linejoin="round"/>
    <path d="M-70 8 Q-62 100 -22 126 M70 8 Q62 100 22 126 M-134 50 Q0 78 134 50" fill="none" stroke="{MID}" stroke-width="6" stroke-linecap="round"/>
    <path d="M-148 0 H148" stroke="{INK}" stroke-width="16" stroke-linecap="round"/>
    <path d="M-148 0 L-330 -150" stroke="{INK}" stroke-width="16" stroke-linecap="round"/>
  </g>"""

FISH = f"""<g class="fish">
    <g class="tail"><path d="M52 0 L116 -46 Q98 0 116 46 Z" fill="{INK}" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/></g>
    <path d="M-62 -42 L-44 -82 L-28 -48 L-8 -86 L14 -44 L34 -60 L40 -22 Z" fill="{INK}" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/>
    <ellipse cx="-20" cy="0" rx="86" ry="54" fill="{INK}"/>
    <path d="M-30 30 L-8 62 L18 30 Z" fill="{INK}" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/>
    <path d="M-52 -30 Q-68 0 -52 30" fill="none" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>
    <circle cx="-76" cy="-12" r="10" fill="#ffffff"/>
    <circle cx="-79" cy="-12" r="4.5" fill="{INK}"/>
  </g>"""

SCENE = f"""{POND}
  {PELLETS}
  {BUBBLES}
  {NET}
  {FISH}"""

V = "view-box|0px 0px"


def tr(x, y, s=1):
    return {"transform": f"translate({x}px, {y}px) scale({s})"}


def tro(x, y, s, o):
    return {"transform": f"translate({x}px, {y}px) scale({s})", "opacity": o}


def _pel(i):
    t0 = 0.06 + i * 0.035
    return (f".pel{i}", V, [
        (0, tro(0, -40, 1, 0)), (t0, tro(0, -40, 1, 0)), (t0 + 0.02, tro(0, -30, 1, 1)),
        (t0 + 0.08, tro(0, 150, 1, 1)), (t0 + 0.14, tro(0, 215, 1, 0)), (1, tro(0, 215, 1, 0)),
    ])


def _bub(i, t0):
    dx = (-12, 14, 10, -10)[i]
    return (f".bub{i}", V, [
        (0, tro(0, 0, 1, 0)), (t0, tro(0, 0, 1, 0)), (t0 + 0.03, tro(0, -20, 1, 1)),
        (t0 + 0.14, tro(dx, -230, 1, 1)), (t0 + 0.17, tro(dx, -250, 1, 0)), (1, tro(dx, -250, 1, 0)),
    ])


def _wag():
    fr = [(0, {"transform": "rotate(0deg)"})]
    n = 0
    t = 0.04
    while t < 0.92:
        n += 1
        fr.append((round(t, 3), {"transform": f"rotate({-14 if n % 2 else 14}deg)"}))
        t += 0.06
    fr.append((1, {"transform": "rotate(0deg)"}))
    return fr


LOOP = [
    (".wave", None, [(0, {"transform": "translateX(0px)"}), (0.25, {"transform": "translateX(-25px)"}),
                     (0.5, {"transform": "translateX(-50px)"}), (0.75, {"transform": "translateX(-75px)"}),
                     (1, {"transform": "translateX(-100px)"})]),
    _pel(0), _pel(1), _pel(2),
    (".fish", V, [
        (0, tro(520, 560, .9, 0)), (0.04, tro(500, 550, .9, 1)),
        (0.17, tro(410, 430, .9, 1)), (0.22, tro(402, 418, 1.0, 1)), (0.25, tro(406, 426, .88, 1)),
        (0.28, tro(402, 420, 1.0, 1)), (0.33, tro(400, 420, 1.2, 1)), (0.36, tro(400, 420, 1.1, 1)),
        (0.46, tro(300, 490, 1.1, 1)), (0.55, tro(390, 510, 1.12, 1)),
        (0.60, tro(360, 460, 1.5, 1)), (0.64, tro(352, 450, 1.32, 1)),
        (0.70, tro(344, 450, 1.35, 1)), (0.76, tro(344, 450, 1.35, 1)),
        (0.92, tro(300, 278, 1.35, 1)), (0.95, tro(300, 278, 1.35, 0)), (1, tro(520, 560, .9, 0)),
    ]),
    (".tail", "fill-box|0% 50%", _wag()),
    _bub(0, 0.40), _bub(1, 0.45), _bub(2, 0.50), _bub(3, 0.55),
    (".net", V, [
        (0, tro(344, 780, 1.3, 0)), (0.62, tro(344, 780, 1.3, 0)), (0.65, tro(344, 720, 1.3, 1)),
        (0.74, tro(344, 425, 1.3, 1)), (0.76, tro(344, 425, 1.3, 1)), (0.92, tro(300, 253, 1.3, 1)),
        (0.95, tro(300, 253, 1.3, 0)), (1, tro(344, 780, 1.3, 0)),
    ]),
]

LOOP_MS = 5600
