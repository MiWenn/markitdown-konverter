# hook-markitdown.py — Converter und Metadaten vollständig einsammeln.
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata

hiddenimports = collect_submodules("markitdown")
datas = collect_data_files("markitdown")
try:
    datas += copy_metadata("markitdown")
except Exception:
    pass

hiddenimports += [
    "pdfminer",
    "pdfminer.high_level",
    "pdfminer.layout",
    "pdfplumber",
    "mammoth",
    "pptx",
    "openpyxl",
    "xlrd",
    "pandas",
    "lxml",
    "lxml.etree",
    "bs4",
    "markdownify",
    "charset_normalizer",
    "defusedxml",
]
