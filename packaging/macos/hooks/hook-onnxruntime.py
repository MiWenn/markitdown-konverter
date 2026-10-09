# hook-onnxruntime.py — Magika lädt ONNX Runtime dynamisch.
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas, binaries, hiddenimports = collect_all("onnxruntime")
try:
    datas += copy_metadata("onnxruntime")
except Exception:
    pass
