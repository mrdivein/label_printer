"""Gallery of the bundled symbols for the README:  python tools/make_symbol_sheet.py  ->  docs/symbols.png"""
import os
import re

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYM = os.path.join(ROOT, "labelapp", "ui", "resources", "symbols")
QML = os.path.join(ROOT, "labelapp", "ui", "qml", "panels", "LeftPanel.qml")


def font(size, bold=False):
    for name in (("segoeuib.ttf" if bold else "segoeui.ttf"), "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main():
    items = re.findall(r'\{ k: "([a-z_]+)", t: "([^"]+)" \}', open(QML, encoding="utf-8").read())
    cols, cw, ch, gap, pad = 8, 150, 150, 14, 20
    rows = (len(items) + cols - 1) // cols
    W, H = pad * 2 + cols * cw + (cols - 1) * gap, pad * 2 + rows * ch + (rows - 1) * gap
    sheet = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))     # 2x for sharp text, scaled down at the end
    d = ImageDraw.Draw(sheet)
    f = font(30)
    for i, (key, label) in enumerate(items):
        x = (pad + (i % cols) * (cw + gap)) * 2
        y = (pad + (i // cols) * (ch + gap)) * 2
        d.rounded_rectangle((x, y, x + cw * 2, y + ch * 2), radius=28, fill="#ffffff", outline="#d9dee8", width=3)
        icon = Image.open(os.path.join(SYM, key + ".png")).convert("RGBA").resize((150, 150), Image.Resampling.LANCZOS)
        sheet.alpha_composite(icon, (x + (cw * 2 - 150) // 2, y + 36))
        tw = d.textlength(label, font=f)
        d.text((x + (cw * 2 - tw) / 2, y + 214), label, font=f, fill="#3a4354")
    sheet = sheet.resize((W, H), Image.Resampling.LANCZOS)
    sheet.save(os.path.join(ROOT, "docs", "symbols.png"), optimize=True)
    print(f"docs/symbols.png: {len(items)} symbols")


if __name__ == "__main__":
    main()
