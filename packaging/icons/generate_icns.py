#!/usr/bin/env python3
"""Erzeugt icon.iconset und app_icon.icns aus dem 1024er Master-PNG.

Auf macOS wird zusätzlich `iconutil` genutzt (offizielles Apple-Format).
Ohne macOS schreibt Pillow ein .icns, das PyInstaller als Fallback akzeptiert.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ICONSET_SPECS = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]


def _here() -> Path:
    return Path(__file__).resolve().parent


def write_iconset(master: Image.Image, iconset: Path) -> None:
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)
    for name, size in ICONSET_SPECS:
        resized = master.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(iconset / name, format="PNG")


def write_icns_pillow(master: Image.Image, dest: Path) -> None:
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    images = [master.resize((s, s), Image.Resampling.LANCZOS) for s in sizes]
    images[0].save(dest, format="ICNS", append_images=images[1:])


def main() -> int:
    here = _here()
    master_path = here / "app_icon.png"
    if not master_path.is_file():
        sys.path.insert(0, str(here))
        from generate_app_icon import save_master

        save_master(master_path)

    master = Image.open(master_path).convert("RGBA")
    if master.size != (1024, 1024):
        master = master.resize((1024, 1024), Image.Resampling.LANCZOS)

    iconset = here / "icon.iconset"
    icns = here / "app_icon.icns"
    write_iconset(master, iconset)

    if sys.platform == "darwin" and shutil.which("iconutil"):
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(icns)],
            check=True,
        )
    else:
        write_icns_pillow(master.convert("RGB"), icns)
        print("Hinweis: iconutil nicht verfügbar — .icns mit Pillow erzeugt.", file=sys.stderr)

    print(icns)
    print(iconset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
