"""Draws the app logo and the label symbols (fragile, this way up, seal...) and renders them.

    python tools/make_icons.py

Writes, from the drawings in this file:
  labelapp/ui/resources/app.svg, app.png, app.ico      app / window / installer icon
  labelapp/ui/resources/symbols/<key>.svg               symbol shown in the insert palette
  labelapp/ui/resources/symbols/<key>.png               the same symbol, 600 px black on transparent, used for printing
  docs/logo.svg                                         logo for the README
The PNG/ICO files are committed, so the app and its build do not need to run this script.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "labelapp", "ui", "resources")
SYM = os.path.join(RES, "symbols")

W = "#fff"   # knock-out colour inside a black symbol


def svg(body, size=100):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
            f'{body}</svg>\n')


def pts(points):
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def star(cx, cy, n, r_out, r_in, rot=-90):
    return [polar(cx, cy, r_out if i % 2 == 0 else r_in, rot + i * 180 / n) for i in range(n * 2)]


def no_sign(slash=True):
    """Prohibition ring with a white-haloed slash drawn over whatever came before."""
    s = '<circle cx="50" cy="50" r="44" fill="none" stroke="#000" stroke-width="6"/>'
    if slash:
        s += ('<line x1="19" y1="19" x2="81" y2="81" stroke="#fff" stroke-width="14"/>'
              '<line x1="19" y1="19" x2="81" y2="81" stroke="#000" stroke-width="6"/>')
    return s


def recycle():
    cx, cy, r, out = 50, 52, 30, ""
    for i in range(3):
        a0 = -90 + i * 120 + 18
        a1 = a0 + 74
        x0, y0 = polar(cx, cy, r, a0)
        x1, y1 = polar(cx, cy, r, a1)
        out += (f'<path d="M{x0:.2f} {y0:.2f} A{r} {r} 0 0 1 {x1:.2f} {y1:.2f}" fill="none" stroke="#000" '
                f'stroke-width="10"/>')
        t = math.radians(a1 + 90)                     # clockwise tangent at the arc end
        n = math.radians(a1)                          # outward normal
        tip = (x1 + 16 * math.cos(t), y1 + 16 * math.sin(t))
        out += f'<polygon points="{pts([tip, (x1 + 13 * math.cos(n), y1 + 13 * math.sin(n)), (x1 - 13 * math.cos(n), y1 - 13 * math.sin(n))])}"/>'
    return out


TEXT = 'font-family="Arial, Helvetica, sans-serif" font-weight="700" text-anchor="middle"'

# key -> SVG body on a 100 x 100 canvas, black ink.  Labels and grouping live in LeftPanel.qml.
SYMBOLS = {
    "fragile":
        '<path d="M28 10 H72 L70 38 C68 56 60 64 50 64 C40 64 32 56 30 38 Z"/>'
        '<polyline points="47,10 55,24 45,34 56,46 49,56" fill="none" stroke="#fff" stroke-width="4"/>'
        '<rect x="47" y="63" width="6" height="22"/><rect x="32" y="84" width="36" height="7" rx="2"/>',
    "this_way_up":
        '<polygon points="31,8 14,32 25,32 25,74 37,74 37,32 48,32"/>'
        '<polygon points="69,8 52,32 63,32 63,74 75,74 75,32 86,32"/>'
        '<rect x="12" y="82" width="76" height="8" rx="2"/>',
    "keep_dry":
        '<path d="M12 54 Q12 20 50 18 Q88 20 88 54 Q81 47 75 54 Q69 47 62 54 Q56 47 50 54 Q44 47 38 54 Q31 47 25 54 Q19 47 12 54 Z"/>'
        '<path d="M50 50 V82 Q50 92 41 92 Q34 92 34 85" fill="none" stroke="#000" stroke-width="6" stroke-linecap="round"/>'
        '<g stroke="#000" stroke-width="4" stroke-linecap="round">'
        '<line x1="22" y1="4" x2="19" y2="11"/><line x1="40" y1="2" x2="37" y2="9"/>'
        '<line x1="60" y1="2" x2="57" y2="9"/><line x1="78" y1="4" x2="75" y2="11"/></g>',
    "keep_away_sun":
        '<circle cx="50" cy="50" r="13"/><g stroke="#000" stroke-width="5" stroke-linecap="round">'
        + "".join('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (*polar(50, 50, 20, a), *polar(50, 50, 29, a))
                  for a in range(0, 360, 45)) + '</g>' + no_sign(),
    "do_not_stack":
        '<rect x="20" y="60" width="60" height="32" rx="3"/>'
        '<rect x="30" y="14" width="40" height="32" rx="3" fill="none" stroke="#000" stroke-width="5"/>'
        '<g stroke-linecap="round"><g stroke="#fff" stroke-width="14"><line x1="22" y1="8" x2="78" y2="52"/>'
        '<line x1="78" y1="8" x2="22" y2="52"/></g><g stroke="#000" stroke-width="6"><line x1="22" y1="8" x2="78" y2="52"/>'
        '<line x1="78" y1="8" x2="22" y2="52"/></g></g>',
    "no_knife":
        '<g transform="rotate(-32 50 50)"><path d="M16 52 Q36 40 62 44 L62 56 L16 56 Z"/>'
        '<rect x="62" y="44" width="24" height="12" rx="4"/></g>' + no_sign(),
    "recycle": recycle(),
    "warning":
        '<path d="M50 9 L93 87 H7 Z" stroke="#000" stroke-width="6" stroke-linejoin="round"/>'
        '<rect x="45.5" y="34" width="9" height="30" rx="4" fill="#fff"/><circle cx="50" cy="75" r="5.5" fill="#fff"/>',
    "seal":
        '<polygon points="34,62 22,95 33,89 40,99 50,68"/><polygon points="66,62 78,95 67,89 60,99 50,68"/>'
        f'<polygon points="{pts(star(50, 42, 16, 40, 34))}"/>'
        '<circle cx="50" cy="42" r="27" fill="#fff"/><circle cx="50" cy="42" r="23" fill="none" stroke="#000" stroke-width="3"/>'
        '<polyline points="38,43 47,52 63,34" fill="none" stroke="#000" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>',
    "seal_lock":
        '<path d="M32 46 V32 A18 18 0 0 1 68 32 V46" fill="none" stroke="#000" stroke-width="9"/>'
        '<rect x="20" y="44" width="60" height="48" rx="7"/>'
        '<circle cx="50" cy="63" r="7" fill="#fff"/><rect x="46.5" y="65" width="7" height="15" rx="2" fill="#fff"/>',
    "genuine":
        '<path d="M50 5 L87 18 V46 C87 70 71 86 50 95 C29 86 13 70 13 46 V18 Z"/>'
        '<polyline points="31,50 45,64 70,36" fill="none" stroke="#fff" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>',
    "qc_pass":
        '<circle cx="50" cy="50" r="45" fill="none" stroke="#000" stroke-width="5"/>'
        '<circle cx="50" cy="50" r="37" fill="none" stroke="#000" stroke-width="2"/>'
        f'<text x="50" y="55" font-size="31" {TEXT}>QC</text>'
        f'<text x="50" y="73" font-size="12" {TEXT}>PASSED</text>'
        '<rect x="26" y="25" width="48" height="2.5"/>',
    "tick":
        '<circle cx="50" cy="50" r="45"/>'
        '<polyline points="28,51 44,67 73,36" fill="none" stroke="#fff" stroke-width="11" stroke-linecap="round" stroke-linejoin="round"/>',
    "new_burst":
        f'<polygon points="{pts(star(50, 50, 16, 48, 39))}"/>'
        f'<text x="50" y="59" font-size="25" fill="#fff" {TEXT}>NEW</text>',
    "sale":
        '<path d="M6 50 L30 20 H92 V80 H30 Z" stroke="#000" stroke-width="4" stroke-linejoin="round"/>'
        '<circle cx="27" cy="50" r="6" fill="#fff"/>'
        f'<text x="62" y="63" font-size="36" fill="#fff" {TEXT}>%</text>',
    "scissors":
        '<g fill="none" stroke="#000" stroke-width="6"><circle cx="22" cy="30" r="11"/><circle cx="22" cy="70" r="11"/></g>'
        '<g stroke="#000" stroke-width="8" stroke-linecap="round"><line x1="31" y1="37" x2="88" y2="66"/>'
        '<line x1="31" y1="63" x2="88" y2="34"/></g><circle cx="53" cy="50" r="3" fill="#fff"/>',
}


def logo(size=256):
    """Temly mark: a white hang tag carrying a bold "T" over a barcode, on a blue-violet tile.

    The tag (with its string) says "labels", the T says "Temly"; the T still reads at 16 px in the taskbar.
    """
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="{size}" height="{size}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#2f6bff"/><stop offset="1" stop-color="#7b3ff2"/>
    </linearGradient>
    <linearGradient id="ink" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#1d4ed8"/><stop offset="1" stop-color="#5b2bd0"/>
    </linearGradient>
  </defs>
  <rect x="8" y="8" width="240" height="240" rx="58" fill="url(#bg)"/>
  <g transform="rotate(-12 128 138)">
    <path d="M128 76 C134 40 182 22 214 44" fill="none" stroke="#fff" stroke-opacity=".9" stroke-width="7" stroke-linecap="round"/>
    <path d="M80 92 L106 62 H150 L176 92 V204 Q176 218 162 218 H94 Q80 218 80 204 Z" fill="#fff" stroke="#fff"
          stroke-width="8" stroke-linejoin="round"/>
    <circle cx="128" cy="78" r="9" fill="url(#ink)"/>
    <g fill="url(#ink)">
      <rect x="96" y="102" width="64" height="22" rx="6"/>
      <rect x="117" y="102" width="22" height="72" rx="6"/>
    </g>
    <g fill="url(#ink)" fill-opacity=".8">
      <rect x="98" y="184" width="4" height="20"/><rect x="106" y="184" width="2.5" height="20"/>
      <rect x="112" y="184" width="6" height="20"/><rect x="122" y="184" width="2.5" height="20"/>
      <rect x="128" y="184" width="4" height="20"/><rect x="136" y="184" width="6" height="20"/>
      <rect x="146" y="184" width="2.5" height="20"/><rect x="152" y="184" width="4" height="20"/>
    </g>
  </g>
</svg>
'''


def render(svg_text, png_path, px):
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    r = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    img = QImage(px, px, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p)
    p.end()
    img.save(png_path)


def main():
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)   # needed for the text in qc_pass / new / sale
    os.makedirs(SYM, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    for key, body in SYMBOLS.items():
        text = svg(body)
        with open(os.path.join(SYM, key + ".svg"), "w", encoding="utf-8") as f:
            f.write(text)
        render(text, os.path.join(SYM, key + ".png"), 600)
    for path in (os.path.join(RES, "app.svg"), os.path.join(ROOT, "docs", "logo.svg")):
        with open(path, "w", encoding="utf-8") as f:
            f.write(logo())
    png = os.path.join(RES, "app.png")
    render(logo(), png, 512)
    from PIL import Image
    Image.open(png).save(os.path.join(RES, "app.ico"), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    del app
    print(f"{len(SYMBOLS)} symbols, logo and app.ico written")


if __name__ == "__main__":
    main()
