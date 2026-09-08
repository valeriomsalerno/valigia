#!/usr/bin/env python3
"""
scripts/generate_icons.py
==========================
Genera le icone dell'app (favicon, apple-touch-icon, icone PWA) come
semplice illustrazione vettoriale disegnata a codice (una valigetta
stilizzata su sfondo blu notte con dettaglio color ottone), così da
non dipendere da asset esterni. Va rilanciato solo se si vuole
rigenerare/cambiare il logo; le icone già generate sono salvate in
app/static/icons/ e versionate nel progetto.
"""

from pathlib import Path
from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"
OUT_DIR.mkdir(parents=True, exist_ok=True)

NAVY = (15, 28, 48, 255)
BRASS = (201, 154, 74, 255)
IVORY = (246, 242, 233, 255)


def draw_icon(size: int) -> Image.Image:
    scale = 4  # disegniamo a risoluzione maggiore poi ridimensioniamo (antialiasing)
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Sfondo: quadrato arrotondato blu notte
    radius = int(s * 0.22)
    draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=NAVY)

    # Corpo della valigia (rettangolo arrotondato color avorio)
    bw, bh = s * 0.52, s * 0.40
    bx, by = (s - bw) / 2, s * 0.34
    draw.rounded_rectangle(
        [bx, by, bx + bw, by + bh], radius=int(s * 0.05), fill=IVORY
    )

    # Manico (arco color ottone)
    hw, hh = s * 0.20, s * 0.12
    hx, hy = (s - hw) / 2, by - hh + s * 0.02
    draw.rounded_rectangle(
        [hx, hy, hx + hw, hy + hh * 2], radius=int(hw / 2), outline=BRASS, width=int(s * 0.028)
    )

    # Linea centrale della valigia (dettaglio)
    draw.rectangle(
        [bx, by + bh * 0.46, bx + bw, by + bh * 0.46 + s * 0.018], fill=BRASS
    )

    # Due "fibbie" color ottone
    for fx in (bx + bw * 0.24, bx + bw * 0.76):
        r = s * 0.03
        draw.ellipse([fx - r, by + bh * 0.7, fx + r, by + bh * 0.7 + r * 2], fill=BRASS)

    return img.resize((size, size), Image.LANCZOS)


def main():
    sizes = {
        "favicon.png": 64,
        "apple-touch-icon.png": 180,
        "icon-192.png": 192,
        "icon-512.png": 512,
    }
    for filename, size in sizes.items():
        icon = draw_icon(size)
        icon.save(OUT_DIR / filename)
        print(f"Creato {filename} ({size}x{size})")


if __name__ == "__main__":
    main()
