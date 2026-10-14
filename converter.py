#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Micky Wenngatz
"""Lokale Konvertierung von PDF- und Office-Dateien nach Markdown.

Nutzt Microsoft MarkItDown (convert_local) für die Umwandlung.
Bilder werden in einen Ordner neben der Markdown-Datei gespeichert.
Gescannte PDFs werden mit der eingebauten Texterkennung des Betriebssystems gelesen
(macOS: Apple Vision, Windows 10/11: Windows.Media.Ocr).
Keine Cloud-APIs, kein Azure Document Intelligence.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import datetime
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

import pdf_layout

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".xls",
    ".html",
    ".htm",
    ".epub",
    ".csv",
    ".json",
    ".xml",
    ".txt",
}

PRIMARY_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".xls"}

# Unter dieser Zeichenzahl pro Seite gilt ein PDF als gescannt (nur Bilder, kaum Text).
SCAN_CHARS_PER_PAGE = 40
# Kleinere Bilder (Linien, Aufzählungszeichen, Mini-Logos) werden nicht gespeichert.
MIN_IMAGE_PX = 64
OCR_LANGUAGES = ["de-DE", "en-US"]
OCR_RENDER_SCALE = 3  # 72 dpi × 3 = 216 dpi, guter Kompromiss aus Qualität und Tempo

# Eine Zeile gilt als Kopf-/Fußzeile, wenn sie am Seitenrand auf so vielen Seiten wiederkehrt.
HEADER_MIN_SHARE = 0.6
HEADER_MIN_PAGES = 3
HEADER_EDGE_LINES = 2

# Ab diesem Drehanteil (Sinus des Winkels, ≈ 1°) gilt ein Zeichen als schräg gesetzt.
TILT_TOLERANCE = 0.02

# Word-Formatvorlagen „Titel“/„Untertitel“ sind keine Überschriften im Sinne von Word,
# sollen in Markdown aber welche werden (Mammoth-Style-Map).
DOCX_STYLE_MAP = "p[style-name='Title'] => h1:fresh\np[style-name='Subtitle'] => h2:fresh"

# Ausgabeprofile setzen nur Voreinstellungen; jede Option bleibt einzeln schaltbar.
PROFILES: dict[str, dict[str, bool]] = {
    "Standard": {"frontmatter": False, "page_markers": False, "strip_headers": True},
    "Notizen & Wissensarchiv": {"frontmatter": True, "page_markers": False, "strip_headers": True},
    "KI & Recherche": {"frontmatter": True, "page_markers": True, "strip_headers": True},
}
DEFAULT_PROFILE = "Standard"
GENERATOR = "PDF zu Markdown von Micky Wenngatz"

ProgressCallback = Callable[[str, int, int, Path], None]

_DATA_URI_IMAGE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\(data:image/(?P<subtype>[\w.+-]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)\)"
)
_IMAGE_FILE = re.compile(r"^bild-\d{3}\.\w+$")


class ConverterError(Exception):
    """Fehler, der in der Oberfläche direkt angezeigt werden kann."""


@dataclass(frozen=True)
class ConversionJob:
    source: Path
    target: Path


@dataclass
class ConversionReport:
    """Ergebnis einer einzelnen Konvertierung inklusive Hinweisen."""

    source: Path
    target: Path
    images: int = 0
    ocr_pages: int = 0
    removed_lines: int = 0
    headings: int = 0
    tables: int = 0
    footnotes: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class BatchResult:
    reports: list[ConversionReport] = field(default_factory=list)
    failures: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def written(self) -> list[Path]:
        return [report.target for report in self.reports]


def check_python_version() -> None:
    if sys.version_info < (3, 10):
        raise ConverterError(
            f"Python 3.10 oder neuer wird benötigt (gefunden: {sys.version.split()[0]})."
        )


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def missing_markitdown_message() -> str:
    if _is_frozen():
        return (
            "Microsoft MarkItDown fehlt in dieser App-Version.\n"
            "Bitte die App erneut von GitHub laden (Releases oder Actions → macOS App)."
        )
    return (
        "Microsoft MarkItDown ist nicht installiert oder unvollständig.\n\n"
        "Im Projektordner im Terminal:\n"
        "  python3 -m venv .venv\n"
        "  source .venv/bin/activate\n"
        "  pip install -r requirements.txt"
    )


def create_markitdown():
    """Erzeugt eine lokale MarkItDown-Instanz ohne Plugins und ohne Cloud."""
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise ConverterError(missing_markitdown_message()) from exc

    return MarkItDown(enable_plugins=False)


def ocr_available() -> bool:
    """Texterkennung: Mac mit ocrmac (Apple Vision), Windows mit der eingebauten
    Windows-Texterkennung (winrt); jeweils zusätzlich pypdfium2 für die Seitenbilder."""
    try:
        import pypdfium2  # noqa: F401
    except ImportError:
        return False
    if sys.platform == "darwin":
        try:
            import ocrmac  # noqa: F401
        except ImportError:
            return False
        return True
    if sys.platform == "win32":
        return _windows_ocr_engine() is not None
    return False


def _windows_ocr_engine():
    """Windows-Texterkennung für Deutsch, sonst Englisch, sonst die Sprache des Systems."""
    try:
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine
    except ImportError:
        return None
    for tag in OCR_LANGUAGES:
        try:
            language = Language(tag)
            if OcrEngine.is_language_supported(language):
                engine = OcrEngine.try_create_from_language(language)
                if engine is not None:
                    return engine
        except Exception:
            continue
    try:
        return OcrEngine.try_create_from_user_profile_languages()
    except Exception:
        return None


def _windows_ocr_observations(engine, image) -> list:
    """Erkennt eine Seite mit Windows und liefert Zeilen im Format von Apple Vision:
    (Text, Sicherheit, (x, y, Breite, Höhe)), Werte 0–1, y von unten gemessen."""
    import asyncio

    from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter

    # Größte Bildkante, die Windows annimmt (Eigenschaft der Klasse, nicht der Instanz)
    try:
        limit = int(OcrEngine.max_image_dimension or 0)
    except Exception:
        limit = 0
    if limit and max(image.size) > limit:
        factor = limit / max(image.size)
        image = image.resize((int(image.width * factor), int(image.height * factor)))
    width, height = image.size
    writer = DataWriter()
    writer.write_bytes(bytearray(image.convert("RGBA").tobytes("raw", "BGRA")))
    bitmap = SoftwareBitmap.create_copy_from_buffer(
        writer.detach_buffer(), BitmapPixelFormat.BGRA8, width, height, BitmapAlphaMode.PREMULTIPLIED
    )

    async def recognize():
        return await engine.recognize_async(bitmap)

    result = asyncio.run(recognize())
    observations = []
    for line in result.lines:
        boxes = [word.bounding_rect for word in line.words]
        if not boxes:
            continue
        left = min(box.x for box in boxes)
        top = min(box.y for box in boxes)
        right = max(box.x + box.width for box in boxes)
        bottom = max(box.y + box.height for box in boxes)
        observations.append((
            line.text,
            1.0,
            (left / width, 1 - bottom / height, (right - left) / width, (bottom - top) / height),
        ))
    # Wie Apple Vision von oben nach unten
    observations.sort(key=lambda item: -(item[2][1] + item[2][3]))
    return observations


def pdf_images_available() -> bool:
    try:
        import PIL  # noqa: F401
        import pypdfium2  # noqa: F401
    except ImportError:
        return False
    return True


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def suggest_output_path(source: Path, output_dir: Path | None = None) -> Path:
    folder = output_dir if output_dir is not None else source.parent
    return folder / f"{source.stem}.md"


def image_folder_for(target: Path) -> Path:
    """Bilder zu „bericht.md“ landen in „bericht_bilder/“ daneben."""
    return target.with_name(f"{target.stem}_bilder")


def _unique_target(desired: Path, used: set[Path]) -> Path:
    candidate = desired
    n = 2
    while candidate in used:
        candidate = desired.with_name(f"{desired.stem}-{n}{desired.suffix}")
        n += 1
    used.add(candidate)
    return candidate


def build_jobs(
    sources: Iterable[Path],
    *,
    output_file: Path | None = None,
    output_dir: Path | None = None,
) -> list[ConversionJob]:
    resolved: list[Path] = []
    seen: set[Path] = set()
    for raw in sources:
        path = Path(raw).expanduser().resolve()
        if path in seen:
            continue
        seen.add(path)
        resolved.append(path)

    if not resolved:
        raise ConverterError("Keine Dateien ausgewählt.")

    if output_file is not None:
        if len(resolved) != 1:
            raise ConverterError(
                "Eine einzelne Zieldatei (-o) geht nur bei genau einer Quelldatei."
            )
        target = Path(output_file).expanduser()
        if not target.is_absolute():
            target = Path.cwd() / target
        return [ConversionJob(resolved[0], target)]

    out_dir: Path | None = None
    if output_dir is not None:
        out_dir = Path(output_dir).expanduser()
        if not out_dir.is_absolute():
            out_dir = Path.cwd() / out_dir

    used: set[Path] = set()
    jobs: list[ConversionJob] = []
    for source in resolved:
        desired = suggest_output_path(source, out_dir)
        jobs.append(ConversionJob(source, _unique_target(desired, used)))
    return jobs


def _humanize_error(exc: BaseException, source: Path) -> str:
    name = type(exc).__name__
    message = str(exc).strip() or name

    if name == "MissingDependencyException" or "optional dependency" in message.lower():
        if _is_frozen():
            return (
                f"Für „{source.name}“ fehlen Bestandteile in dieser App.\n"
                "Bitte eine neuere Version der App von GitHub laden."
            )
        return (
            f"Für „{source.name}“ fehlen MarkItDown-Zusatzpakete.\n"
            "Bitte erneut installieren:\n"
            "  pip install -r requirements.txt"
        )
    if name == "UnsupportedFormatException":
        return (
            f"Das Format von „{source.name}“ wird von MarkItDown nicht unterstützt."
        )
    return f"Konvertierung von „{source.name}“ fehlgeschlagen:\n{message}"


_EMPTY_TABLE_HEADER = re.compile(
    r"^(?P<empty>\|(?:\s*\|)+)\n(?P<sep>\|(?:\s*:?-{3,}:?\s*\|)+)\n(?P<first>\|.*\|)$", re.M
)


def fix_empty_table_headers(markdown: str) -> str:
    """Word-Tabellen haben oft keine echte Kopfzeile; MarkItDown setzt dann eine leere.

    Die erste Datenzeile wird zur Kopfzeile, so wie man die Tabelle in Word liest.
    """
    return _EMPTY_TABLE_HEADER.sub(lambda m: f"{m['first']}\n{m['sep']}", markdown)


def _visible_chars(text: str) -> int:
    return len(re.sub(r"\s", "", text))


def _md_link(folder: Path, filename: str) -> str:
    # Spitze Klammern erlauben Leerzeichen im Pfad (CommonMark).
    return f"<{folder.name}/{filename}>"


class _ImageWriter:
    """Speichert Bilder durchnummeriert in den Bilderordner einer Markdown-Datei."""

    def __init__(self, target: Path) -> None:
        self.folder = image_folder_for(target)
        self.count = 0
        self._hashes: set[str] = set()

    def remove_previous(self) -> None:
        """Entfernt Bilder eines früheren Laufs, aber nur die eigenen (bild-001.png …)."""
        if not self.folder.is_dir():
            return
        for old in self.folder.iterdir():
            if old.is_file() and _IMAGE_FILE.match(old.name):
                old.unlink()
        if not any(self.folder.iterdir()):
            self.folder.rmdir()

    def is_duplicate(self, data: bytes) -> bool:
        digest = hashlib.sha1(data).hexdigest()
        if digest in self._hashes:
            return True
        self._hashes.add(digest)
        return False

    def next_name(self, extension: str) -> str:
        self.folder.mkdir(parents=True, exist_ok=True)
        self.count += 1
        return f"bild-{self.count:03d}.{extension}"

    def write_bytes(self, data: bytes, extension: str) -> str:
        name = self.next_name(extension)
        (self.folder / name).write_bytes(data)
        return _md_link(self.folder, name)


def _extension_for(subtype: str) -> str:
    ext = subtype.lower().split("+")[0]
    if ext.startswith("x-"):
        ext = ext[2:]
    return {"jpeg": "jpg", "svg": "svg", "tiff": "tif"}.get(ext, ext) or "bin"


def extract_data_uri_images(
    markdown: str, target: Path, writer: _ImageWriter | None = None
) -> tuple[str, int]:
    """Ersetzt eingebettete Bilder (data:-URIs) durch Dateien im Bilderordner."""
    writer = writer if writer is not None else _ImageWriter(target)
    before = writer.count

    def replace(match: re.Match[str]) -> str:
        try:
            data = base64.b64decode(re.sub(r"\s", "", match["data"]), validate=True)
        except (binascii.Error, ValueError):
            return f"![{match['alt']}](Bild konnte nicht gelesen werden)"
        link = writer.write_bytes(data, _extension_for(match["subtype"]))
        return f"![{match['alt']}]({link})"

    markdown = _DATA_URI_IMAGE.sub(replace, markdown)
    return markdown, writer.count - before


def _pdf_page_count(source: Path) -> int:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return 1
    pdf = pdfium.PdfDocument(str(source))
    try:
        return len(pdf)
    finally:
        pdf.close()


def looks_scanned(markdown: str, page_count: int) -> bool:
    return _visible_chars(markdown) < SCAN_CHARS_PER_PAGE * max(page_count, 1)


def _ocr_page_text(observations: list) -> str:
    """Setzt erkannte Zeilen zu Absätzen zusammen (größere Lücke = neuer Absatz)."""
    paragraphs: list[list[str]] = []
    previous_bottom: float | None = None
    for text, _confidence, (_x, y, _w, h) in observations:
        top = y + h  # Apple Vision misst von unten links
        if previous_bottom is None or previous_bottom - top > h * 0.9:
            paragraphs.append([])
        paragraphs[-1].append(text.strip())
        previous_bottom = y
    return "\n\n".join("\n".join(lines) for lines in paragraphs if lines)


def ocr_pdf(source: Path) -> list[str]:
    """Liest ein gescanntes PDF Seite für Seite mit der Texterkennung des Systems.
    Liefert den Text je Seite."""
    import pypdfium2 as pdfium

    if sys.platform == "win32":
        engine = _windows_ocr_engine()
        if engine is None:
            raise ConverterError("Die Windows-Texterkennung ist auf diesem Computer nicht verfügbar.")

        def recognize(image) -> list:
            return _windows_ocr_observations(engine, image)
    else:
        from ocrmac import ocrmac

        def recognize(image) -> list:
            return ocrmac.OCR(image, language_preference=OCR_LANGUAGES).recognize()

    pdf = pdfium.PdfDocument(str(source))
    pages: list[str] = []
    try:
        for page in pdf:
            image = page.render(scale=OCR_RENDER_SCALE).to_pil()
            pages.append(_ocr_page_text(recognize(image)))
        return pages
    finally:
        pdf.close()


def _is_tilted(matrix: Sequence[float]) -> bool:
    """Schräg oder gedreht gesetztes Zeichen: Die Grundlinie verläuft nicht waagerecht.

    Nur der Drehanteil zählt; kursive Schrift ist geneigt, aber nicht gedreht.
    """
    a, b = matrix[0], matrix[1]
    return abs(b) > TILT_TOLERANCE * max(abs(a), abs(b))


def _tilted_text_blocks(chars: Sequence[dict]) -> list[str]:
    """Setzt schräg/gedreht gesetzten Text wieder zu Zeilen und Absätzen zusammen.

    Die Zeichen werden in das Koordinatensystem ihrer eigenen Grundlinie gedreht;
    dort liegen sie wieder ordentlich nebeneinander wie waagerechter Text.
    """
    groups: dict[int, list[tuple[float, float, float, str]]] = {}
    for char in chars:
        a, b, _c, _d, e, f = char["matrix"]
        angle = math.atan2(b, a)
        cos, sin = math.cos(angle), math.sin(angle)
        # Schriftgröße: steckt je nach PDF in der Matrix oder separat (pdfplumber „size“).
        scale = float(char.get("size") or math.hypot(a, b) or 1.0)
        along = e * cos + f * sin
        across = -e * sin + f * cos
        groups.setdefault(round(math.degrees(angle)), []).append(
            (across, along, scale, char["text"])
        )

    blocks: list[str] = []
    for glyphs in groups.values():
        glyphs.sort(key=lambda g: (-g[0], g[1]))
        lines: list[list[tuple[float, float, float, str]]] = []
        for glyph in glyphs:
            if lines and lines[-1][0][0] - glyph[0] < glyph[2] * 0.5:
                lines[-1].append(glyph)
            else:
                lines.append([glyph])

        # Weit auseinanderliegende Teile einer Zeile sind eigene Texte (z. B. mehrere Plakate).
        segments: list[tuple[float, float, float, float, str]] = []
        for line in lines:
            line.sort(key=lambda g: g[1])
            parts: list[list[tuple[float, float, float, str]]] = [[]]
            for glyph in line:
                if parts[-1] and glyph[1] - parts[-1][-1][1] > glyph[2] * 3:
                    parts.append([])
                parts[-1].append(glyph)
            for part in parts:
                text, last_along = "", None
                for _across, along, scale, char in part:
                    if last_along is not None and along - last_along > scale * 1.2 and not text.endswith(" "):
                        text += " "
                    text += char
                    last_along = along
                text = re.sub(r"\s+", " ", text).strip()
                if text:
                    segments.append((part[0][0], part[0][1], part[-1][1], part[0][2], text))

        # Untereinanderstehende Zeilen, die sich seitlich überlappen, bilden einen Absatz.
        paragraphs: list[list[str]] = []
        tails: list[tuple[float, float, float]] = []
        for across, start, end, scale, text in segments:
            for index, (last_across, last_start, last_end) in enumerate(tails):
                if (
                    0 < last_across - across <= scale * 2
                    and start <= last_end + scale
                    and end >= last_start - scale
                ):
                    paragraphs[index].append(text)
                    tails[index] = (across, start, end)
                    break
            else:
                paragraphs.append([text])
                tails.append((across, start, end))

        for lines_text in paragraphs:
            block = " ".join(lines_text)
            # Trennstriche am Zeilenende: „Aus- nahmen“ → „Ausnahmen“, „Set- Design“ → „Set-Design“
            block = re.sub(r"(?<=\w)- (?=[a-zäöüß])", "", block)
            block = re.sub(r"(?<=\w)- (?=[A-ZÄÖÜ])", "-", block)
            if block not in blocks:
                blocks.append(block)
    return blocks


def _pdfminer_pages_without_tilted(source: Path) -> list[str]:
    """Wie pdfminer.extract_text, aber ohne schräg oder gedreht gesetzte Zeichen."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTChar, LTContainer, LTText, LTTextBox

    pages: list[str] = []
    for layout in extract_pages(str(source)):
        parts: list[str] = []

        def render(item) -> None:
            if isinstance(item, LTChar) and _is_tilted(item.matrix):
                return
            if isinstance(item, LTContainer):
                for child in item:
                    render(child)
            elif isinstance(item, LTText):
                parts.append(item.get_text())
            if isinstance(item, LTTextBox):
                parts.append("\n")

        render(layout)
        lines = [line.strip() for line in "".join(parts).splitlines()]
        pages.append(re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip())
    return pages


_DOT_LEADER = re.compile(r"[ \t]*(?:\.{4,}|…{2,}|(?:\. ){3,}\.)[ \t]*")


def remove_dot_leaders(text: str) -> str:
    """Entfernt Punktreihen aus Inhaltsverzeichnissen („Logo ........ 7“ → „Logo 7“)."""
    lines = []
    for line in text.split("\n"):
        cleaned = _DOT_LEADER.sub(" ", line)
        if cleaned != line:
            cleaned = cleaned.strip()
            if not cleaned:
                continue  # Zeile bestand nur aus Punkten
        lines.append(cleaned)
    return "\n".join(lines)


def _pdf_pages_text(source: Path, *, fix_tilted: bool = False) -> list[str] | None:
    """Text je Seite, auf demselben Weg wie MarkItDown.

    MarkItDown liefert die Seitengrenzen nicht immer mit (bei Tabellen-PDFs und bei
    einseitigen PDFs). Wie MarkItDown: Gibt es keine Formular-/Tabellenseiten, liest
    pdfminer das ganze Dokument (bessere Absätze), sonst pdfplumber Seite für Seite.

    Mit fix_tilted wird schräg oder gedreht gesetzter Text (z. B. in Design-PDFs) aus
    dem Fließtext herausgenommen, weil er dort Buchstabe für Buchstabe zerfällt, und
    am Ende der jeweiligen Seite als lesbare Zeile angehängt.
    """
    try:
        import pdfminer.high_level
        import pdfplumber
        from markitdown.converters import _pdf_converter as md_pdf
    except ImportError:
        return None
    extract_form = getattr(md_pdf, "_extract_form_content_from_words", None)
    merge_numbering = getattr(md_pdf, "_merge_partial_numbering_lines", lambda text: text)

    def upright(obj: dict) -> bool:
        return obj.get("object_type") != "char" or not _is_tilted(obj["matrix"])

    pages: list[str] = []
    tilted: list[list[str]] = []
    has_form_page = False
    with pdfplumber.open(str(source)) as pdf:
        for page in pdf.pages:
            blocks = _tilted_text_blocks(
                [c for c in page.chars if _is_tilted(c["matrix"])]
            ) if fix_tilted else []
            view = page.filter(upright) if blocks else page
            content = extract_form(view) if extract_form is not None else None
            if content is not None:
                has_form_page = True
            else:
                content = view.extract_text() or ""
            pages.append(content)
            tilted.append(blocks)
            page.close()

    if not has_form_page:
        if any(tilted):
            pages = _pdfminer_pages_without_tilted(source)
        else:
            by_page = split_pages(pdfminer.high_level.extract_text(str(source)))
            if by_page is not None:
                pages = by_page
    result = []
    for index, page in enumerate(pages):
        extra = tilted[index] if index < len(tilted) else []
        result.append("\n\n".join([merge_numbering(page).strip(), *extra]).strip())
    return result


def _comparable(text: str) -> int:
    """Buchstaben und Ziffern, ohne Markdown-Zeichen wie # oder |."""
    return len(re.sub(r"[\W_]", "", text))


def structured_pdf(source: Path, reference: str = ""):
    """Seiten mit Überschriften, Tabellen, Spalten und Fußnoten (siehe pdf_layout).

    None, wenn die Analyse nicht klappt oder deutlich weniger Text findet als
    MarkItDown (reference); dann bleibt es beim bisherigen Weg.
    """
    try:
        from markitdown.converters import _pdf_converter as md_pdf
    except ImportError:
        return None
    merge_numbering = getattr(md_pdf, "_merge_partial_numbering_lines", lambda text: text)

    extract_form = getattr(md_pdf, "_extract_form_content_from_words", None)

    def tilted_blocks(page) -> list[str]:
        return _tilted_text_blocks([c for c in page.chars if _is_tilted(c["matrix"])])

    def form_content(page) -> str | None:
        # Schräge Buchstaben würden sonst als Tabellenspalten gedeutet
        upright = page.filter(
            lambda obj: obj.get("object_type") != "char" or not _is_tilted(obj["matrix"])
        )
        return extract_form(upright)

    try:
        layout = pdf_layout.analyze_pdf(
            source,
            skip_char=lambda char: _is_tilted(char.matrix),
            form_content=form_content if extract_form is not None else None,
            page_extra=tilted_blocks,
        )
    except Exception:
        return None
    if layout is None:
        return None
    layout.pages = [merge_numbering(page).strip() for page in layout.pages]
    found = _comparable("\n".join(layout.pages)) + _comparable(
        "\n".join(text for _label, text in layout.footnotes)
    )
    if found < _comparable(reference) * 0.85:
        return None
    return layout


def has_tilted_text(source: Path) -> bool:
    """Prüft, ob ein PDF schräg oder gedreht gesetzten Text enthält."""
    try:
        import pdfplumber
    except ImportError:
        return False
    with pdfplumber.open(str(source)) as pdf:
        for page in pdf.pages:
            found = any(_is_tilted(c["matrix"]) for c in page.chars)
            page.close()
            if found:
                return True
    return False


def split_pages(markdown: str) -> list[str] | None:
    """Teilt MarkItDown-Text an Seitenumbrüchen (\\f von pdfminer)."""
    if "\f" not in markdown:
        return None
    pages = markdown.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()  # pdfminer setzt nach der letzten Seite noch einen Umbruch
    return [page.strip() for page in pages]


def _line_key(line: str) -> str:
    # Seitenzahlen und Datumsangaben sollen nicht verhindern, dass Zeilen als gleich gelten.
    return re.sub(r"\d+", "#", line.strip().lower())


def _edge_indices(lines: list[str]) -> list[int]:
    filled = [i for i, line in enumerate(lines) if line.strip()]
    if len(filled) < 3:
        return []  # zu kurze Seiten: kein verlässlicher Rand
    # Bei kurzen Seiten nur die erste und letzte Zeile prüfen, damit Inhalt sicher bleibt.
    depth = HEADER_EDGE_LINES if len(filled) > 2 * HEADER_EDGE_LINES + 1 else 1
    return sorted(set(filled[:depth] + filled[-depth:]))


def remove_repeating_lines(pages: list[str]) -> tuple[list[str], int]:
    """Entfernt Kopf- und Fußzeilen, die auf den meisten Seiten am Rand wiederkehren."""
    if len(pages) < HEADER_MIN_PAGES:
        return pages, 0
    split = [page.splitlines() for page in pages]
    counts: dict[str, int] = {}
    for lines in split:
        for key in {_line_key(lines[i]) for i in _edge_indices(lines)}:
            if key:
                counts[key] = counts.get(key, 0) + 1
    needed = max(HEADER_MIN_PAGES, math.ceil(len(pages) * HEADER_MIN_SHARE))
    repeated = {key for key, count in counts.items() if count >= needed}
    if not repeated:
        return pages, 0

    removed = 0
    cleaned: list[str] = []
    for lines in split:
        edges = set(_edge_indices(lines))
        keep = []
        for i, line in enumerate(lines):
            if i in edges and _line_key(line) in repeated:
                removed += 1
                continue
            keep.append(line)
        cleaned.append(re.sub(r"\n{3,}", "\n\n", "\n".join(keep)).strip())
    return cleaned, removed


def join_pages(pages: list[str], *, page_markers: bool) -> str:
    if not page_markers:
        return "\n\n".join(page for page in pages if page)
    parts = []
    for number, page in enumerate(pages, start=1):
        parts.append(f"[Seite {number}]\n\n{page}" if page else f"[Seite {number}]")
    return "\n\n".join(parts)


def _docx_title(source: Path) -> str | None:
    """Titel aus den Word-Dokumenteigenschaften (docProps/core.xml)."""
    import zipfile
    from xml.etree import ElementTree

    try:
        with zipfile.ZipFile(source) as archive:
            root = ElementTree.fromstring(archive.read("docProps/core.xml"))
    except (KeyError, OSError, zipfile.BadZipFile, ElementTree.ParseError):
        return None
    element = root.find("{http://purl.org/dc/elements/1.1/}title")
    return element.text if element is not None and element.text else None


def _document_title(source: Path, result, markdown: str) -> str:
    title = getattr(result, "title", None)
    if not title and source.suffix.lower() == ".docx":
        title = _docx_title(source)
    if not title and source.suffix.lower() == ".pdf":
        try:
            import pypdfium2 as pdfium

            pdf = pdfium.PdfDocument(str(source))
            try:
                title = pdf.get_metadata_dict().get("Title")
            finally:
                pdf.close()
        except Exception:
            title = None
    if title:
        # Programme schreiben oft Platzhalter oder Dateinamen in die PDF-Metadaten.
        title = re.sub(r"^Microsoft (Word|PowerPoint|Excel) - ", "", str(title)).strip()
        if title.lower().strip("()") in {"untitled", "unbenannt", "ohne titel", "title", "anonymous"} or re.search(
            r"\.(docx?|pptx?|xlsx?|pdf)$", title, re.I
        ):
            title = None
    if not title:
        heading = re.search(r"^#{1,2}\s+(.+)$", markdown, re.M)
        title = heading.group(1) if heading else None
    return (title or source.stem).strip()


def build_frontmatter(source: Path, title: str, *, pages: int | None, ocr: bool) -> str:
    """YAML-Kopf, den Obsidian als Eigenschaften und KI-Werkzeuge als Metadaten lesen."""
    fields = {
        "title": title,
        "source": source.name,
        "pages": pages,
        "ocr": True if ocr else None,
        "converted": datetime.date.today().isoformat(),
        "generator": GENERATOR,
    }
    # JSON-Strings sind gültiges YAML und maskieren Doppelpunkte, Anführungszeichen usw.
    lines = [
        f"{key}: {json.dumps(value, ensure_ascii=False)}"
        for key, value in fields.items()
        if value is not None
    ]
    return "---\n" + "\n".join(lines) + "\n---\n\n"


def extract_pdf_images(
    source: Path, target: Path, writer: _ImageWriter | None = None
) -> tuple[str, int]:
    """Speichert die Bilder eines PDFs und liefert einen Markdown-Abschnitt dazu."""
    import pypdfium2 as pdfium
    from pypdfium2 import raw as pdfium_raw

    writer = writer if writer is not None else _ImageWriter(target)
    before = writer.count
    sections: list[str] = []
    pdf = pdfium.PdfDocument(str(source))
    try:
        for number, page in enumerate(pdf, start=1):
            links: list[str] = []
            for obj in page.get_objects(filter=(pdfium_raw.FPDF_PAGEOBJ_IMAGE,)):
                width, height = obj.get_px_size()
                if width < MIN_IMAGE_PX or height < MIN_IMAGE_PX:
                    continue
                try:
                    image = obj.get_bitmap(render=False).to_pil()
                except Exception:  # defekte oder exotische Bildformate überspringen
                    continue
                if writer.is_duplicate(image.tobytes()):
                    continue  # z. B. Logo auf jeder Seite nur einmal speichern
                name = writer.next_name("png")
                image.save(writer.folder / name)
                links.append(f"![Seite {number}, Bild {len(links) + 1}]({_md_link(writer.folder, name)})")
            if links:
                sections.append(f"**Seite {number}**\n\n" + "\n\n".join(links))
    finally:
        pdf.close()

    if not sections:
        return "", 0
    return "## Bilder aus dem PDF\n\n" + "\n\n".join(sections), writer.count - before


def convert_document(
    source: Path,
    target: Path,
    *,
    converter=None,
    extract_images: bool = True,
    ocr: bool = True,
    frontmatter: bool = False,
    page_markers: bool = False,
    strip_headers: bool = False,
) -> ConversionReport:
    source = Path(source)
    target = Path(target)

    if not source.exists():
        raise ConverterError(f"Datei nicht gefunden: {source}")
    if not source.is_file():
        raise ConverterError(f"Keine Datei: {source}")

    engine = converter if converter is not None else create_markitdown()
    report = ConversionReport(source, target)
    is_pdf = source.suffix.lower() == ".pdf"

    extra: dict = {"keep_data_uris": True} if extract_images else {}
    if source.suffix.lower() == ".docx":
        extra["style_map"] = DOCX_STYLE_MAP
    try:
        result = engine.convert_local(str(source), **extra)
    except ConverterError:
        raise
    except Exception as exc:
        raise ConverterError(_humanize_error(exc, source)) from exc

    markdown = getattr(result, "markdown", None)
    if markdown is None:
        markdown = getattr(result, "text_content", "")
    markdown = str(markdown or "")
    page_count: int | None = None

    try:
        if is_pdf:
            page_count = _pdf_page_count(source)
            pages = split_pages(markdown)
            if looks_scanned(markdown, page_count):
                if not ocr:
                    report.warnings.append(
                        "Das PDF enthält kaum Text, vermutlich ein Scan. "
                        "Texterkennung ist ausgeschaltet."
                    )
                elif not ocr_available():
                    report.warnings.append(
                        "Das PDF enthält kaum Text, vermutlich ein Scan. "
                        "Texterkennung ist auf diesem Computer nicht verfügbar "
                        "(Mac oder Windows 10/11 nötig)."
                    )
                else:
                    pages = ocr_pdf(source)
                    report.ocr_pages = len(pages)
                    if not page_markers:
                        pages = [page or "*(kein Text erkannt)*" for page in pages]
            footnotes = ""
            layout = None if report.ocr_pages else structured_pdf(source, markdown)
            if layout is not None:
                pages = layout.pages
                report.headings, report.tables = layout.headings, layout.tables
                report.footnotes = len(layout.footnotes)
                footnotes = pdf_layout.footnote_section(layout.footnotes)
            elif not report.ocr_pages and has_tilted_text(source):
                pages = _pdf_pages_text(source, fix_tilted=True) or pages
            elif pages is None and (page_markers or strip_headers):
                pages = _pdf_pages_text(source)

            if pages is not None:
                if strip_headers:
                    pages, report.removed_lines = remove_repeating_lines(pages)
                markdown = join_pages(pages, page_markers=page_markers)
            if footnotes:
                markdown = markdown.rstrip() + "\n\n" + footnotes
            markdown = remove_dot_leaders(markdown)
            if report.ocr_pages:
                markdown = (
                    "*Text per Texterkennung (OCR) aus gescannten Seiten gewonnen. "
                    "Bitte auf Lesefehler prüfen.*\n\n" + markdown
                )
        # Seitenumbruch-Zeichen haben in Markdown nichts verloren.
        markdown = fix_empty_table_headers(markdown.replace("\f", "\n\n"))

        if extract_images:
            writer = _ImageWriter(target)
            writer.remove_previous()
            markdown, _ = extract_data_uri_images(markdown, target, writer)
            # Bei OCR sind die Bilder die Seiten selbst, die braucht es nicht doppelt.
            if is_pdf and not report.ocr_pages and pdf_images_available():
                section, _ = extract_pdf_images(source, target, writer)
                if section:
                    markdown = markdown.rstrip() + "\n\n" + section + "\n"
            report.images = writer.count

        if _visible_chars(markdown) == 0:
            report.warnings.append("Das Ergebnis ist leer, es wurde kein Text gefunden.")
        if frontmatter:
            title = _document_title(source, result, markdown)
            markdown = build_frontmatter(
                source, title, pages=page_count, ocr=bool(report.ocr_pages)
            ) + markdown.lstrip()
    except OSError as exc:
        raise ConverterError(
            f"Bilder zu „{source.name}“ konnten nicht gespeichert werden:\n{exc}"
        ) from exc
    except Exception as exc:
        raise ConverterError(_humanize_error(exc, source)) from exc

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown.rstrip() + "\n", encoding="utf-8")
    except OSError as exc:
        raise ConverterError(
            f"Markdown-Datei konnte nicht geschrieben werden:\n{target}\n{exc}"
        ) from exc

    return report


def convert_file(
    source: Path,
    target: Path,
    *,
    converter=None,
    **options: bool,
) -> Path:
    return convert_document(source, target, converter=converter, **options).target


def run_batch(
    jobs: Sequence[ConversionJob],
    *,
    progress: ProgressCallback | None = None,
    on_report: Callable[[ConversionReport], None] | None = None,
    **options: bool,
) -> BatchResult:
    """Wandelt alle Dateien um. Ein Fehler stoppt nicht die übrigen Dateien."""
    if not jobs:
        raise ConverterError("Keine Dateien ausgewählt.")

    engine = create_markitdown()
    batch = BatchResult()
    total = len(jobs)
    for index, job in enumerate(jobs, start=1):
        if progress is not None:
            progress("start", index, total, job.source)
        try:
            report = convert_document(job.source, job.target, converter=engine, **options)
        except ConverterError as exc:
            batch.failures.append((job.source, str(exc)))
            if progress is not None:
                progress("failed", index, total, job.source)
            continue
        except Exception as exc:  # unerwarteter Fehler: nur diese Datei überspringen
            batch.failures.append((job.source, f"Unerwarteter Fehler:\n{exc}"))
            if progress is not None:
                progress("failed", index, total, job.source)
            continue
        batch.reports.append(report)
        if on_report is not None:
            on_report(report)
        if progress is not None:
            progress("done", index, total, job.target)
    return batch


def failure_summary(failures: Sequence[tuple[Path, str]]) -> str:
    lines = [f"{len(failures)} Datei(en) konnten nicht umgewandelt werden:"]
    for source, message in failures:
        lines.append(f"\n• {source.name}\n  {message.replace(chr(10), chr(10) + '  ')}")
    return "\n".join(lines)


def convert_jobs(
    jobs: Sequence[ConversionJob],
    *,
    progress: ProgressCallback | None = None,
    **options: bool,
) -> list[Path]:
    """Wie run_batch; meldet Fehler aber erst am Ende gesammelt als ConverterError."""
    batch = run_batch(jobs, progress=progress, **options)
    if batch.failures:
        raise ConverterError(failure_summary(batch.failures))
    return batch.written


def _cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PDF und Office-Dokumente lokal mit MarkItDown nach Markdown wandeln.",
    )
    parser.add_argument(
        "quellen",
        nargs="+",
        type=Path,
        help="Eine oder mehrere Quelldateien (PDF, DOCX, PPTX, XLSX, …)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Zieldatei (nur bei genau einer Quelle)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Zielordner für Batch (sonst neben der jeweiligen Quelle)",
    )
    parser.add_argument(
        "--ohne-bilder",
        action="store_true",
        help="Bilder nicht als Dateien speichern",
    )
    parser.add_argument(
        "--ohne-ocr",
        action="store_true",
        help="Keine Texterkennung für gescannte PDFs",
    )
    parser.add_argument(
        "--profil",
        choices=list(PROFILES),
        default=DEFAULT_PROFILE,
        help="Ausgabeprofil (Metadaten-Kopf, Seitenmarkierungen, Kopf-/Fußzeilen)",
    )
    args = parser.parse_args(argv)

    try:
        check_python_version()
        jobs = build_jobs(args.quellen, output_file=args.output, output_dir=args.out_dir)
        batch = run_batch(
            jobs,
            extract_images=not args.ohne_bilder,
            ocr=not args.ohne_ocr,
            **PROFILES[args.profil],
        )
    except ConverterError as exc:
        print(exc, file=sys.stderr)
        return 1

    for report in batch.reports:
        print(report.target)
        for warning in report.warnings:
            print(f"  Hinweis: {warning}", file=sys.stderr)
    if batch.failures:
        print(failure_summary(batch.failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
