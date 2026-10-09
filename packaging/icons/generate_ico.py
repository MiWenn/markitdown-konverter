#!/usr/bin/env python3
"""Erzeugt app_icon.ico (Windows) aus dem 1024er Master-PNG."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def _here() -> Path:
    return Path(__file__).resolve().parent


def write_ico(master: Image.Image, dest: Path) -> None:
    rgba = master.convert("RGBA")
    # Eine große Quelle; Pillow skaliert die angegebenen ICO-Größen selbst.
    work = rgba.resize((256, 256), Image.Resampling.LANCZOS)
    work.save(
        dest,
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
    )


def main() -> int:
    here = _here()
    master_path = here / "app_icon.png"
    if not master_path.is_file():
        sys.path.insert(0, str(here))
        from generate_app_icon import save_master

        save_master(master_path)

    master = Image.open(master_path)
    if master.size != (1024, 1024):
        master = master.resize((1024, 1024), Image.Resampling.LANCZOS)

    dest = here / "app_icon.ico"
    write_ico(master, dest)
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
