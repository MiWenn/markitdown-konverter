#!/usr/bin/env python3
"""Lokale Konvertierung von PDF- und Office-Dateien nach Markdown.

Nutzt Microsoft MarkItDown (convert_local) für die Umwandlung.
Bilder werden in einen Ordner neben der Markdown-Datei gespeichert.
Gescannte PDFs werden mit der Texterkennung von macOS (Apple Vision) gelesen.
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
    """Texterkennung braucht macOS, ocrmac (Apple Vision) und pypdfium2."""
    if sys.platform != "darwin":
        return False
    try:
        import ocrmac  # noqa: F401
        import pypdfium2  # noqa: F401
    except ImportError:
        return False
    return True


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
    """Liest ein gescanntes PDF Seite für Seite mit Apple Vision. Liefert den Text je Seite."""
    import pypdfium2 as pdfium
    from ocrmac import ocrmac

    pdf = pdfium.PdfDocument(str(source))
    pages: list[str] = []
    try:
        for page in pdf:
            image = page.render(scale=OCR_RENDER_SCALE).to_pil()
            observations = ocrmac.OCR(
                image, language_preference=OCR_LANGUAGES
            ).recognize()
            pages.append(_ocr_page_text(observations))
        return pages
    finally:
        pdf.close()


def _pdf_pages_text(source: Path) -> list[str] | None:
    """Text je Seite, auf demselben Weg wie MarkItDown.

    MarkItDown liefert die Seitengrenzen nicht immer mit (bei Tabellen-PDFs und bei
    einseitigen PDFs). Wie MarkItDown: Gibt es keine Formular-/Tabellenseiten, liest
    pdfminer das ganze Dokument (bessere Absätze), sonst pdfplumber Seite für Seite.
    """
    try:
        import pdfminer.high_level
        import pdfplumber
        from markitdown.converters import _pdf_converter as md_pdf
    except ImportError:
        return None
    extract_form = getattr(md_pdf, "_extract_form_content_from_words", None)
    merge_numbering = getattr(md_pdf, "_merge_partial_numbering_lines", lambda text: text)

    pages: list[str] = []
    has_form_page = False
    with pdfplumber.open(str(source)) as pdf:
        for page in pdf.pages:
            content = extract_form(page) if extract_form is not None else None
            if content is not None:
                has_form_page = True
            else:
                content = page.extract_text() or ""
            pages.append(content)
            page.close()

    if not has_form_page:
        by_page = split_pages(pdfminer.high_level.extract_text(str(source)))
        if by_page is not None:
            pages = by_page
    return [merge_numbering(page).strip() for page in pages]


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
                        "Texterkennung ist nur auf dem Mac verfügbar."
                    )
                else:
                    pages = ocr_pdf(source)
                    report.ocr_pages = len(pages)
                    if not page_markers:
                        pages = [page or "*(kein Text erkannt)*" for page in pages]
            elif pages is None and (page_markers or strip_headers):
                pages = _pdf_pages_text(source)

            if pages is not None:
                if strip_headers:
                    pages, report.removed_lines = remove_repeating_lines(pages)
                markdown = join_pages(pages, page_markers=page_markers)
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
