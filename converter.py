#!/usr/bin/env python3
"""Lokale Konvertierung von PDF- und Office-Dateien nach Markdown.

Nutzt ausschließlich Microsoft MarkItDown (convert_local).
Keine Cloud-APIs, kein Azure Document Intelligence.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
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

ProgressCallback = Callable[[str, int, int, Path], None]


class ConverterError(Exception):
    """Fehler, der in der Oberfläche direkt angezeigt werden kann."""


@dataclass(frozen=True)
class ConversionJob:
    source: Path
    target: Path


def check_python_version() -> None:
    if sys.version_info < (3, 10):
        raise ConverterError(
            f"Python 3.10 oder neuer wird benötigt (gefunden: {sys.version.split()[0]})."
        )


def missing_markitdown_message() -> str:
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


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def suggest_output_path(source: Path, output_dir: Path | None = None) -> Path:
    folder = output_dir if output_dir is not None else source.parent
    return folder / f"{source.stem}.md"


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
        return (
            f"Für „{source.name}“ fehlen MarkItDown-Zusatzpakete.\n"
            "Bitte erneut installieren:\n"
            "  pip install -r requirements.txt"
        )
    if name == "UnsupportedFormatException":
        return (
            f"Das Format von „{source.name}“ wird von MarkItDown nicht unterstützt."
        )
    if name == "FileConversionException":
        return f"Konvertierung von „{source.name}“ fehlgeschlagen:\n{message}"
    return f"Konvertierung von „{source.name}“ fehlgeschlagen:\n{message}"


def convert_file(
    source: Path,
    target: Path,
    *,
    converter=None,
) -> Path:
    source = Path(source)
    target = Path(target)

    if not source.exists():
        raise ConverterError(f"Datei nicht gefunden: {source}")
    if not source.is_file():
        raise ConverterError(f"Keine Datei: {source}")

    engine = converter if converter is not None else create_markitdown()

    try:
        result = engine.convert_local(str(source))
    except ConverterError:
        raise
    except Exception as exc:
        raise ConverterError(_humanize_error(exc, source)) from exc

    markdown = getattr(result, "markdown", None)
    if markdown is None:
        markdown = getattr(result, "text_content", "")
    if markdown is None:
        markdown = ""

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(markdown), encoding="utf-8")
    except OSError as exc:
        raise ConverterError(
            f"Markdown-Datei konnte nicht geschrieben werden:\n{target}\n{exc}"
        ) from exc

    return target


def convert_jobs(
    jobs: Sequence[ConversionJob],
    *,
    progress: ProgressCallback | None = None,
) -> list[Path]:
    if not jobs:
        raise ConverterError("Keine Dateien ausgewählt.")

    engine = create_markitdown()
    written: list[Path] = []
    total = len(jobs)
    for index, job in enumerate(jobs, start=1):
        if progress is not None:
            progress("start", index, total, job.source)
        written.append(convert_file(job.source, job.target, converter=engine))
        if progress is not None:
            progress("done", index, total, job.target)
    return written


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
    args = parser.parse_args(argv)

    try:
        check_python_version()
        jobs = build_jobs(args.quellen, output_file=args.output, output_dir=args.out_dir)
        paths = convert_jobs(jobs)
    except ConverterError as exc:
        print(exc, file=sys.stderr)
        return 1

    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
