"""Shared drawing for the cut-flower scenes (standard_roses, spray_roses, summer_flowers).

Not a scene (the build skips modules starting with an underscore). Everything is drawn in the
local frame of a stem: its base at 0,0 and the stem rising to negative y, so a bunch is just the
same stem placed several times. Flat solid shapes in tonal layers (no outlines), the way the
other crop scenes are drawn, but built from real structure: a compound rose leaf with five
serrated-looking leaflets and a pale midrib, thorns on the cane, a rose bloom made of a calyx,
splayed outer petals, a cupped body, wrapping front petals and a tight spiralled centre.
"""

from .common import ACCENT, INK, MID, PALE

LEAF = ACCENT
LEAF_DARK = "#2f6a30"
LEAF_LIGHT = "#6f9a63"
THORN = "#625d59"
KRAFT = "#d6d1c8"
KRAFT_DARK = "#a9a49b"

SHOW = {"transform": "scale(1)", "opacity": 1}
GONE = {"transform": "scale(0)", "opacity": 0}


def leaflet(length, width, fill=LEAF, vein=True):
    """A pointed oval leaflet from 0,0 out along +x, with a pale midrib."""
    l, w = length, width
    body = (f'<path d="M0 0 C{l * .18:.1f} {-w * .62:.1f} {l * .62:.1f} {-w * .62:.1f} {l:.1f} 0 '
            f'C{l * .62:.1f} {w * .62:.1f} {l * .18:.1f} {w * .62:.1f} 0 0 Z" fill="{fill}"/>')
    if vein:
        body += (f'<path d="M{l * .08:.1f} 0 L{l * .9:.1f} 0" stroke="#ffffff" stroke-opacity=".38" '
                 f'stroke-width="{max(1.4, w * .07):.1f}" stroke-linecap="round"/>')
    return body


def rose_leaf(x, y, deg, s=1.0, cls=""):
    """A five-leaflet rose leaf, petiole from x,y out along `deg`."""
    parts = [f'<path d="M0 0 H46" stroke="{LEAF}" stroke-width="3.4" stroke-linecap="round"/>']
    for at, ang, ln, wd, tone in ((.4, -52, 36, 19, LEAF_DARK), (.4, 52, 36, 19, LEAF_DARK),
                                  (.72, -44, 40, 21, LEAF), (.72, 44, 40, 21, LEAF)):
        parts.append(f'<g transform="translate({46 * at:.1f} 0) rotate({ang})">{leaflet(ln, wd, tone)}</g>')
    parts.append(f'<g transform="translate(44 0)">{leaflet(56, 28, LEAF)}</g>')
    return (f'<g transform="translate({x} {y}) rotate({deg}) scale({s})"><g class="{cls}">{"".join(parts)}</g></g>')


def thorn(x, y, side=1, s=1.0):
    """A small hooked prickle on the cane."""
    return (f'<path transform="translate({x} {y}) scale({side * s} {s})" d="M0 0 C7 -2 12 2 15 8 '
            f'C9 6 5 6 0 7 Z" fill="{THORN}"/>')


def petal(length, width, fill, rot=0, ox=0, oy=0):
    """One rounded petal standing on 0,0 and pointing up."""
    l, w = length, width
    return (f'<path transform="translate({ox} {oy}) rotate({rot})" fill="{fill}" '
            f'd="M0 0 C{-w * .72:.1f} {-l * .18:.1f} {-w * .8:.1f} {-l * .74:.1f} {-w * .28:.1f} {-l * .96:.1f} '
            f'Q0 {-l * 1.06:.1f} {w * .28:.1f} {-l * .96:.1f} '
            f'C{w * .8:.1f} {-l * .74:.1f} {w * .72:.1f} {-l * .18:.1f} 0 0 Z"/>')


def shield(cx, top, w, bx, bottom, fill):
    """A cupped petal seen from the side: a rounded lip at `top`, narrowing to its base at bx, bottom."""
    h = bottom - top
    return (f'<path fill="{fill}" d="M{cx - w / 2:.1f} {top + 24:.1f} C{cx - w / 2:.1f} {top - 6:.1f} {cx + w / 2:.1f} {top - 6:.1f} '
            f'{cx + w / 2:.1f} {top + 24:.1f} C{cx + w * .52:.1f} {top + h * .56:.1f} {bx + 9:.1f} {bottom - 8:.1f} {bx:.1f} {bottom} '
            f'C{bx - 9:.1f} {bottom - 8:.1f} {cx - w * .52:.1f} {top + h * .56:.1f} {cx - w / 2:.1f} {top + 24:.1f} Z"/>')


def lip(cx, top, w, op=.4):
    """The pale rolled edge along a petal's rim."""
    return (f'<path d="M{cx - w / 2 + 5:.1f} {top + 22:.1f} C{cx - w / 2 + 6:.1f} {top + 2:.1f} {cx + w / 2 - 6:.1f} {top + 2:.1f} '
            f'{cx + w / 2 - 5:.1f} {top + 22:.1f}" fill="none" stroke="#ffffff" stroke-opacity="{op}" stroke-width="3" stroke-linecap="round"/>')


def rose_bloom(tones, s=1.0, cls="b", calyx=True):
    """A hybrid-tea rose in side view, calyx at 0,0, about 140 wide and 135 tall at s=1.

    tones = (deep, mid, light, bright), darkest to lightest. Layers, back to front: reflexed sepals,
    outer petals rolling their lips outward, an urn-shaped body, three overlapping cupped petals with
    pale rolled rims, and the tight spiral of the centre. Classes <cls>-bud (the whole bloom),
    <cls>-pl / <cls>-pr (outer petals) and <cls>-fl / <cls>-fr (front petals) let a scene open it.
    """
    deep, mid, light, bright = tones
    sepals = ""
    if calyx:
        sepals = (f'<path d="M-4 -8 C-18 -4 -30 6 -38 22 C-26 20 -14 14 -2 4 Z" fill="{LEAF_DARK}"/>'
                  f'<path d="M4 -8 C18 -4 30 6 38 22 C26 20 14 14 2 4 Z" fill="{LEAF_DARK}"/>'
                  f'<path d="M-8 -4 C-16 8 -14 22 -8 32 C-2 20 2 10 5 -4 Z" fill="{LEAF}"/>'
                  f'<path d="M-14 -2 C-14 -16 14 -16 14 -2 C13 8 -13 8 -14 -2 Z" fill="{LEAF}"/>')
    return f"""<g transform="scale({s})"><g class="{cls}-bud">
      {sepals}
      <g class="{cls}-pl"><path d="M-8 -14 C-42 -18 -68 -42 -68 -82 C-62 -94 -48 -94 -42 -84 C-40 -66 -26 -48 -8 -40 Z" fill="{deep}"/></g>
      <g class="{cls}-pr"><path d="M8 -14 C42 -18 68 -42 68 -82 C62 -94 48 -94 42 -84 C40 -66 26 -48 8 -40 Z" fill="{deep}"/></g>
      <path d="M-14 -2 C-44 -10 -62 -40 -60 -84 C-52 -100 -20 -100 0 -98 C20 -100 52 -100 60 -84 C62 -40 44 -10 14 -2 C6 3 -6 3 -14 -2 Z" fill="{mid}"/>
      <g class="{cls}-fl">{shield(-27, -102, 58, -11, -4, light)}{lip(-27, -102, 58)}</g>
      <g class="{cls}-fr">{shield(28, -100, 58, 11, -4, bright)}{lip(28, -100, 58, .5)}</g>
      {shield(0, -114, 44, 0, -8, deep)}{lip(0, -114, 44, .3)}
      {shield(-5, -134, 30, -2, -84, mid)}{lip(-5, -134, 30, .3)}
      {shield(8, -131, 26, 4, -84, light)}{lip(8, -131, 26, .5)}
    </g></g>"""


def bud(tones, s=1.0):
    """A closed rose bud (calyx at 0,0, about 46 wide and 78 tall)."""
    deep, mid, light, _ = tones
    return f"""<g transform="scale({s})">
      <path d="M0 -4 C-18 2 -32 14 -38 34 C-22 30 -10 22 -2 10 Z" fill="{LEAF_DARK}"/>
      <path d="M0 -4 C18 2 32 14 38 34 C22 30 10 22 2 10 Z" fill="{LEAF_DARK}"/>
      <path d="M-13 -4 C-26 -30 -20 -66 0 -82 C20 -66 26 -30 13 -4 C8 4 -8 4 -13 -4 Z" fill="{mid}"/>
      <path d="M0 -82 C-14 -62 -8 -26 -2 -4 C6 -26 10 -60 0 -82 Z" fill="{light}"/>
      <path d="M-13 -4 C-8 -32 -2 -56 0 -82 C-18 -62 -26 -32 -13 -4 Z" fill="{deep}"/>
    </g>"""


def shears():
    """Secateurs at 0,0 with the cutting edges meeting at the origin, handles to the lower right."""
    return f"""<g class="shears">
      <g class="blade-a">
        <path d="M0 0 C14 -18 34 -22 52 -16 L58 -4 C36 -6 16 -2 0 0 Z" fill="{INK}"/>
        <path d="M44 -12 L150 -62 L158 -48 L56 2 Z" fill="{INK}"/>
        <path d="M150 -62 L250 -108 C262 -112 270 -98 258 -92 L158 -48 Z" fill="#c0662b"/>
      </g>
      <g class="blade-b">
        <path d="M0 0 C14 14 34 20 52 14 L58 4 C36 4 16 0 0 0 Z" fill="#625d59"/>
        <path d="M44 10 L150 62 L158 48 L56 -2 Z" fill="#625d59"/>
        <path d="M150 62 L250 108 C262 112 270 98 258 92 L158 48 Z" fill="#a9a49b"/>
      </g>
      <circle cx="34" cy="6" r="7" fill="{PALE}"/>
    </g>"""


def sleeve(width, top, bottom, band_y):
    """A kraft sleeve around the stems of a bunch: flared at the top, wrapped on the diagonal, tied low."""
    cx = 344
    hw, hb = width / 2, width * .12
    bw = hb + (hw - hb) * (bottom - band_y) / (bottom - top) + 7
    return f"""<g class="sleeve">
      <path d="M{cx - hw:.0f} {top} L{cx + hw:.0f} {top - 6} L{cx + hb:.0f} {bottom} H{cx - hb:.0f} Z" fill="{KRAFT_DARK}"/>
      <path d="M{cx - hw + 6:.0f} {top + 8} L{cx + hw * .62:.0f} {top - 20} L{cx + hb:.0f} {bottom} H{cx - hb:.0f} Z" fill="{KRAFT}"/>
      <path d="M{cx + hw * .62:.0f} {top - 20} L{cx - hb * .3:.0f} {bottom}" stroke="#ffffff" stroke-opacity=".55" stroke-width="3"/>
      <rect x="{cx - bw:.0f}" y="{band_y}" width="{2 * bw:.0f}" height="12" rx="4" fill="{INK}"/>
    </g>"""


# -- motion helpers --------------------------------------------------------------
RESET = 0.975
STAGE_ORIGIN = "view-box|344px 344px"
LOCAL = "view-box|0px 0px"


def seq(init, *points, reset=RESET):
    """Keyframes: `init` at 0, the (offset, props) points, then back to `init` out of sight."""
    last = points[-1][1] if points else init
    return [(0, init), *points, (reset, last), (round(reset + .001, 3), init), (1, init)]


def stage_track():
    hide = {"transform": "scale(.86)", "opacity": 0}
    show = {"transform": "scale(1)", "opacity": 1}
    return (".stage", STAGE_ORIGIN, [(0, hide), (0.03, show), (0.92, show), (0.97, hide), (1, hide)])


def pop(sel, lo, hi, origin=LOCAL):
    """Scale a part in from its own origin between offsets lo and hi."""
    return (sel, origin, seq(GONE, (lo, GONE), (hi, SHOW)))


def ground(cut_y, stem_w=11, tone=LEAF):
    """The bed with the stub left standing after the cut."""
    return f"""<g class="ground">
    <path d="M60 546 C160 536 260 548 344 544 C440 540 540 548 628 538 V660 H60 Z" fill="{PALE}"/>
    <path d="M60 546 C160 536 260 548 344 544 C440 540 540 548 628 538" fill="none" stroke="{MID}" stroke-width="4"/>
    <rect x="{344 - stem_w / 2}" y="{cut_y}" width="{stem_w}" height="50" rx="3" fill="{tone}"/>
  </g>"""


def cut_bunch_tracks(lift=26, drop=66):
    """The shared second half of the story: secateurs cut, the stem lifts free, two companions and a
    sleeve join it. Expects .shears/.blade-a/.blade-b, .main, .ground, .sideL/.sideR and .sleeve."""
    away = {"transform": "translate(300px, 30px)", "opacity": 0}
    here = {"transform": "translate(0px, 0px)", "opacity": 1}
    return [
        (".shears", None, seq(away, (0.50, away), (0.58, here), (0.64, here), (0.72, away))),
        (".blade-a", "view-box|34px 6px", seq({"transform": "rotate(-17deg)"}, (0.56, {"transform": "rotate(-17deg)"}),
                                               (0.62, {"transform": "rotate(0deg)"}))),
        (".blade-b", "view-box|34px 6px", seq({"transform": "rotate(17deg)"}, (0.56, {"transform": "rotate(17deg)"}),
                                               (0.62, {"transform": "rotate(0deg)"}))),
        (".main", None, seq({"transform": "translate(0px, 0px)"}, (0.62, {"transform": "translate(0px, 0px)"}),
                            (0.68, {"transform": f"translate(0px, {-lift}px)"}), (0.74, {"transform": f"translate(0px, {-lift}px)"}),
                            (0.82, {"transform": f"translate(0px, {drop}px)"}))),
        (".ground", None, seq({"opacity": 1}, (0.72, {"opacity": 1}), (0.80, {"opacity": 0}))),
        (".sideL", LOCAL, seq(GONE, (0.76, GONE), (0.86, SHOW))),
        (".sideR", LOCAL, seq(GONE, (0.78, GONE), (0.88, SHOW))),
        (".sleeve", None, seq({"transform": "translate(0px, 30px)", "opacity": 0}, (0.86, {"transform": "translate(0px, 30px)", "opacity": 0}),
                              (0.92, {"transform": "translate(0px, 0px)", "opacity": 1}))),
    ]
