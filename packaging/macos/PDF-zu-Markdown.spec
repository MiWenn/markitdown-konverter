# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für die macOS-App „PDF zu Markdown“.

Auf macOS erzeugt dieser Spec ein .app-Bundle (onedir, nicht onefile).
Onedir bleibt signierbar und startet schneller als eine einzelne Datei.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parents[1]
ICON_ICNS = ROOT / "packaging" / "icons" / "app_icon.icns"
ICON_PNG = ROOT / "packaging" / "icons" / "app_icon.png"
ENTITLEMENTS = SPEC_DIR / "entitlements.plist"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
APP_NAME = "PDF zu Markdown"
BUNDLE_ID = "de.miwenn.pdf-zu-markdown"

# Nur Pakete mit Daten/Binaries, die PyInstaller sonst oft vergisst.
# pandas/numpy/pdfminer haben eigene Hooks — collect_all würde deren Tests mitschleifen.
COLLECT_PACKAGES = [
    "customtkinter",
    "magika",
    "onnxruntime",
    "markitdown",
    "tkinterdnd2",  # Drag & Drop, bringt tkdnd-Binärdateien mit
    "pypdfium2",  # PDF-Bilder und Seiten für die Texterkennung
    "pypdfium2_raw",
    "ocrmac",  # Texterkennung mit Apple Vision (nur Mac)
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
    "ocrmac",
]


def _try_collect_all(name: str):
    try:
        return collect_all(name)
    except Exception as exc:  # pragma: no cover - Build-Warnung
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
    "objc",
    "Vision",
    "AppKit",
    "CoreFoundation",
    "Foundation",
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

icon_file = str(ICON_ICNS) if ICON_ICNS.is_file() else (str(ICON_PNG) if ICON_PNG.is_file() else None)

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(SPEC_DIR / "hooks")],
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
    argv_emulation=sys.platform == "darwin",
    target_arch=None,
    codesign_identity=None,
    entitlements_file=str(ENTITLEMENTS) if ENTITLEMENTS.is_file() else None,
    icon=icon_file,
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

if sys.platform == "darwin":
    from PyInstaller.building.osx import BUNDLE

    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon_file,
        bundle_identifier=BUNDLE_ID,
        version=VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleGetInfoString": (
                "PDF zu Markdown von Micky Wenngatz — "
                "lokale PDF- und Office-Konvertierung mit Microsoft MarkItDown"
            ),
            "NSHumanReadableCopyright": "© Micky Wenngatz",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "CFBundlePackageType": "APPL",
            "CFBundleIdentifier": BUNDLE_ID,
            "LSMinimumSystemVersion": "11.0",
            "LSApplicationCategoryType": "public.app-category.productivity",
            "LSSupportsOpeningDocumentsInPlace": False,
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "NSPrincipalClass": "NSApplication",
            "NSAppleScriptEnabled": False,
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "PDF-Dokument",
                    "CFBundleTypeRole": "Viewer",
                    "LSHandlerRank": "Alternate",
                    "CFBundleTypeExtensions": ["pdf"],
                    "LSItemContentTypes": ["com.adobe.pdf"],
                },
                {
                    "CFBundleTypeName": "Microsoft Word",
                    "CFBundleTypeRole": "Viewer",
                    "LSHandlerRank": "Alternate",
                    "CFBundleTypeExtensions": ["docx"],
                    "LSItemContentTypes": ["org.openxmlformats.wordprocessingml.document"],
                },
                {
                    "CFBundleTypeName": "Microsoft PowerPoint",
                    "CFBundleTypeRole": "Viewer",
                    "LSHandlerRank": "Alternate",
                    "CFBundleTypeExtensions": ["pptx"],
                    "LSItemContentTypes": ["org.openxmlformats.presentationml.presentation"],
                },
                {
                    "CFBundleTypeName": "Microsoft Excel",
                    "CFBundleTypeRole": "Viewer",
                    "LSHandlerRank": "Alternate",
                    "CFBundleTypeExtensions": ["xlsx", "xls"],
                    "LSItemContentTypes": [
                        "org.openxmlformats.spreadsheetml.sheet",
                        "com.microsoft.excel.xls",
                    ],
                },
                {
                    # Ganze Ordner aufs Dock-Symbol ziehen
                    "CFBundleTypeName": "Ordner",
                    "CFBundleTypeRole": "Viewer",
                    "LSHandlerRank": "None",
                    "LSItemContentTypes": ["public.folder"],
                },
            ],
        },
    )
