#!/usr/bin/env python3
"""Zeichnet das Programmsymbol (.icns) für „Dokumente zu Markdown.app“."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 1024


def draw() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = 100
    draw.rounded_rectangle(
        (margin, margin, SIZE - margin, SIZE - margin),
        radius=180,
        fill=(31, 106, 165),
    )
    font = ImageFont.load_default(size=330)
    draw.text((SIZE / 2 - 90, SIZE / 2 - 40), "M", font=font, fill="white", anchor="mm")
    # Pfeil nach unten (das Markdown-Zeichen „M↓“), gezeichnet statt als Schriftzeichen
    ax, top, bottom = SIZE / 2 + 150, SIZE / 2 - 160, SIZE / 2 + 80
    draw.rectangle((ax - 28, top, ax + 28, bottom - 60), fill="white")
    draw.polygon([(ax - 95, bottom - 90), (ax + 95, bottom - 90), (ax, bottom + 20)], fill="white")
    small = ImageFont.load_default(size=110)
    draw.text((SIZE / 2, SIZE - 250), ".md", font=small, fill=(200, 225, 245), anchor="mm")
    return image


def main() -> int:
    if len(sys.argv) != 2:
        print("Aufruf: symbol.py ZIEL.icns", file=sys.stderr)
        return 1
    draw().save(Path(sys.argv[1]), format="ICNS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
