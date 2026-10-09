# hook-customtkinter.py
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas, binaries, hiddenimports = collect_all("customtkinter")
try:
    datas += copy_metadata("customtkinter")
except Exception:
    pass
