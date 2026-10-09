# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für Windows „PDF zu Markdown“ (onedir, kein Konsolenfenster).

Onedir ist für customtkinter + ONNX/Magika zuverlässiger als onefile.
Hooks liegen bei den macOS-Dateien (plattformneutral).
"""

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parents[1]
ICON_ICO = ROOT / "packaging" / "icons" / "app_icon.ico"
VERSION_FILE = SPEC_DIR / "file_version_info.txt"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
APP_NAME = "PDF zu Markdown"
HOOKS = ROOT / "packaging" / "macos" / "hooks"

COLLECT_PACKAGES = [
    "customtkinter",
    "magika",
    "onnxruntime",
    "markitdown",
    "tkinterdnd2",  # Drag & Drop, bringt tkdnd-Binärdateien mit
    "pypdfium2",  # PDF-Bilder und Seiten für die Texterkennung
    "pypdfium2_raw",
]

METADATA_DISTS = [
    "markitdown",
    "customtkinter",
    "magika",
    "onnxruntime",
    "pdfminer.six",
    "pdfplumber",
    "mammoth",
    "python-pptx",
    "openpyxl",
    "xlrd",
    "pandas",
    "pypdfium2",
    "pillow",
]


def _try_collect_all(name: str):
    try:
        return collect_all(name)
    except Exception as exc:  # pragma: no cover
        print(f"WARN: collect_all({name!r}) übersprungen: {exc}")
        return [], [], []


datas = []
binaries = []
hiddenimports = [
    "converter",
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.ttk",
    "customtkinter",
    "multiprocessing",
    "PIL.Image",
]

for package in COLLECT_PACKAGES:
    pkg_datas, pkg_binaries, pkg_hidden = _try_collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

for dist in METADATA_DISTS:
    try:
        datas += copy_metadata(dist)
    except Exception as exc:  # pragma: no cover
        print(f"WARN: copy_metadata({dist!r}) übersprungen: {exc}")

datas.append((str(ROOT / "VERSION"), "."))
if ICON_ICO.is_file():
    datas.append((str(ICON_ICO), "."))

icon_file = str(ICON_ICO) if ICON_ICO.is_file() else None
version_file = str(VERSION_FILE) if VERSION_FILE.is_file() else None

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(HOOKS)],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "azure",
        "azure.ai",
        "azure.identity",
        "IPython",
        "matplotlib",
        "pytest",
        "tkinter.test",
        "numpy.tests",
        "pandas.tests",
        "onnxruntime.quantization",
        "onnxruntime.datasets",
        "onnxruntime.tools",
        "youtube_transcript_api",
        "speech_recognition",
        "pydub",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
    version=version_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
