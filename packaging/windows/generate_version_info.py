#!/usr/bin/env python3
"""Schreibt PyInstaller-Versionsinfos für die Windows-.exe (Autor Micky Wenngatz)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
OUT = Path(__file__).resolve().parent / "file_version_info.txt"


def _tuple(version: str) -> tuple[int, int, int, int]:
    parts = [int(p) for p in version.split(".") if p.isdigit()]
    parts = (parts + [0, 0, 0, 0])[:4]
    return parts[0], parts[1], parts[2], parts[3]


def main() -> int:
    fv = _tuple(VERSION)
    OUT.write_text(
        f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={fv!r},
    prodvers={fv!r},
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040704B0',
        [StringStruct('CompanyName', 'Micky Wenngatz'),
        StringStruct('FileDescription', 'PDF zu Markdown'),
        StringStruct('FileVersion', '{VERSION}'),
        StringStruct('InternalName', 'PDF-zu-Markdown'),
        StringStruct('LegalCopyright', '© Micky Wenngatz'),
        StringStruct('OriginalFilename', 'PDF zu Markdown.exe'),
        StringStruct('ProductName', 'PDF zu Markdown'),
        StringStruct('ProductVersion', '{VERSION}')])
      ]),
    VarFileInfo([VarStruct('Translation', [1031, 1200])])
  ]
)
""",
        encoding="utf-8",
    )
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
