#!/usr/bin/env python3
"""Erzeugt das App-Icon als vollflächiges 1024×1024-PNG.

macOS legt die Squircle-Maske selbst an — die Grafik muss das Quadrat
ausfüllen (keine vorgerundeten Ecken, kein weißer Rand).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
TEAL = (46, 196, 182)
BLUE = (25, 110, 196)
PAPER = (255, 254, 251)
LINE = (186, 196, 208)
HASH = (22, 92, 176)
FOLD = (232, 238, 244)
FOLD_EDGE = (210, 218, 228)
SHADOW = (12, 40, 70, 70)


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def _gradient(size: int) -> Image.Image:
    """Diagonales Türkis→Blau, klein gerendert und hochskaliert."""
    small = 256
    img = Image.new("RGB", (small, small))
    pix = img.load()
    denom = 2 * (small - 1)
    for y in range(small):
        for x in range(small):
            t = (x + y) / denom
            # leichter vertikaler Verlauf zusätzlich
            t = 0.85 * t + 0.15 * (y / (small - 1))
            pix[x, y] = _lerp(TEAL, BLUE, t)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _draw_hash(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: tuple[int, int, int]) -> None:
    """Geometrisches Markdown-„#“ ohne Schriftart."""
    thickness = max(8, int(size * 0.16))
    spread = int(size * 0.28)
    height = int(size * 0.78)
    width = int(size * 0.78)
    skew = int(size * 0.08)

    def bar(points: list[tuple[float, float]]) -> None:
        draw.polygon([(int(x), int(y)) for x, y in points], fill=color)

    # zwei vertikale Balken, leicht geschert
    for dx in (-spread, spread):
        x0 = cx + dx - thickness / 2
        bar(
            [
                (x0 + skew, cy - height / 2),
                (x0 + thickness + skew, cy - height / 2),
                (x0 + thickness - skew, cy + height / 2),
                (x0 - skew, cy + height / 2),
            ]
        )

    # zwei waagerechte Balken
    for dy in (-int(size * 0.14), int(size * 0.18)):
        y0 = cy + dy - thickness / 2
        bar(
            [
                (cx - width / 2, y0),
                (cx + width / 2, y0),
                (cx + width / 2, y0 + thickness),
                (cx - width / 2, y0 + thickness),
            ]
        )


def render_icon(size: int = SIZE) -> Image.Image:
    base = _gradient(size).convert("RGBA")

    # weiches Licht oben links
    light = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    light_draw = ImageDraw.Draw(light)
    light_draw.ellipse(
        (-size * 0.35, -size * 0.45, size * 0.85, size * 0.55),
        fill=(255, 255, 255, 38),
    )
    light = light.filter(ImageFilter.GaussianBlur(radius=size * 0.08))
    base = Image.alpha_composite(base, light)

    # Dokument-Geometrie
    doc_w = int(size * 0.52)
    doc_h = int(size * 0.64)
    left = (size - doc_w) // 2
    top = int(size * 0.16)
    right = left + doc_w
    bottom = top + doc_h
    radius = int(size * 0.045)
    fold = int(doc_w * 0.22)

    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    offset = int(size * 0.018)
    sdraw.rounded_rectangle(
        (left + offset, top + offset * 2, right + offset, bottom + offset * 2),
        radius=radius,
        fill=SHADOW,
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=int(size * 0.03)))
    base = Image.alpha_composite(base, shadow)

    doc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(doc)
    d.rounded_rectangle((left, top, right, bottom), radius=radius, fill=PAPER)

    # Eselsohr oben rechts
    d.polygon(
        [(right - fold, top), (right, top + fold), (right - fold, top + fold)],
        fill=FOLD,
    )
    # kleine Kante unter dem Falz
    d.line([(right - fold, top), (right - fold, top + fold), (right, top + fold)], fill=FOLD_EDGE, width=max(2, size // 256))

    # Textzeilen links
    line_left = left + int(doc_w * 0.12)
    line_right_full = left + int(doc_w * 0.48)
    line_top = top + int(doc_h * 0.28)
    gap = int(doc_h * 0.09)
    thicknesses = [
        (line_right_full, max(6, size // 64)),
        (int(line_left + (line_right_full - line_left) * 0.82), max(6, size // 64)),
        (int(line_left + (line_right_full - line_left) * 0.94), max(6, size // 64)),
        (int(line_left + (line_right_full - line_left) * 0.62), max(6, size // 64)),
    ]
    for i, (x1, thick) in enumerate(thicknesses):
        y = line_top + i * gap
        d.rounded_rectangle((line_left, y, x1, y + thick), radius=thick // 2, fill=LINE)

    _draw_hash(
        d,
        cx=left + int(doc_w * 0.72),
        cy=top + int(doc_h * 0.58),
        size=int(doc_w * 0.34),
        color=HASH,
    )

    base = Image.alpha_composite(base, doc)
    return base.convert("RGB")


def save_master(path: Path, size: int = SIZE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    render_icon(size).save(path, format="PNG", optimize=True)
    return path


def main() -> int:
    here = Path(__file__).resolve().parent
    out = here / "app_icon.png"
    save_master(out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
