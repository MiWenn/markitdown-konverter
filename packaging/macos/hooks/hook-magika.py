# hook-magika.py — Magika braucht ONNX-Modelle als Paketdaten.
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

datas = collect_data_files("magika")
binaries = collect_dynamic_libs("magika")
hiddenimports = collect_submodules("magika")
try:
    datas += copy_metadata("magika")
except Exception:
    pass
