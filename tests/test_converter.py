#!/usr/bin/env python3
"""Tests für die lokale MarkItDown-Konvertierung (ohne GUI)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import converter


def build_simple_pdf(text: str) -> bytes:
    """Minimal gültiges PDF mit einer Textzeile (pdfminer-lesbar)."""
    safe = (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )
    content = f"BT /F1 24 Tf 72 720 Td ({safe}) Tj ET\n"
    bodies = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content.encode('latin-1'))} >>\nstream\n{content}endstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = [0]
    for index, body in enumerate(bodies, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref_pos = len(out)
    out += f"xref\n0 {len(bodies) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(bodies) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")
    return out


class JobPlanningTests(unittest.TestCase):
    def test_suggest_same_folder_markdown(self) -> None:
        source = Path("/tmp/bericht.pdf")
        self.assertEqual(converter.suggest_output_path(source), Path("/tmp/bericht.md"))

    def test_build_jobs_batch_next_to_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            a = folder / "a.pdf"
            b = folder / "b.pdf"
            a.write_bytes(b"%PDF")
            b.write_bytes(b"%PDF")
            jobs = converter.build_jobs([a, b])
            self.assertEqual([j.target.name for j in jobs], ["a.md", "b.md"])
            # macOS: /var ist ein Symlink auf /private/var; build_jobs() nutzt resolve()
            self.assertEqual(jobs[0].target.parent, folder.resolve())

    def test_build_jobs_output_dir_avoids_name_clash(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            one = root / "one"
            two = root / "two"
            one.mkdir()
            two.mkdir()
            (one / "report.pdf").write_bytes(b"%PDF")
            (two / "report.pdf").write_bytes(b"%PDF")
            out = root / "md"
            jobs = converter.build_jobs(
                [one / "report.pdf", two / "report.pdf"],
                output_dir=out,
            )
            names = [j.target.name for j in jobs]
            self.assertEqual(names, ["report.md", "report-2.md"])

    def test_single_output_file_rejected_for_batch(self) -> None:
        with self.assertRaises(converter.ConverterError):
            converter.build_jobs(
                [Path("a.pdf"), Path("b.pdf")],
                output_file=Path("out.md"),
            )


class ConvertTests(unittest.TestCase):
    def test_convert_sample_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            pdf = folder / "probe.pdf"
            pdf.write_bytes(build_simple_pdf("Hallo MarkItDown Probe"))
            target = folder / "probe.md"
            written = converter.convert_file(pdf, target)
            self.assertTrue(written.exists())
            text = written.read_text(encoding="utf-8")
            self.assertIn("Hallo MarkItDown Probe", text)

    def test_batch_writes_two_markdown_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            first = folder / "eins.pdf"
            second = folder / "zwei.pdf"
            first.write_bytes(build_simple_pdf("Dokument Eins"))
            second.write_bytes(build_simple_pdf("Dokument Zwei"))
            jobs = converter.build_jobs([first, second])
            paths = converter.convert_jobs(jobs)
            self.assertEqual(len(paths), 2)
            self.assertIn("Dokument Eins", paths[0].read_text(encoding="utf-8"))
            self.assertIn("Dokument Zwei", paths[1].read_text(encoding="utf-8"))

    def test_missing_file_has_german_error(self) -> None:
        with self.assertRaises(converter.ConverterError) as ctx:
            converter.convert_file(Path("/tmp/gibt-es-nicht-12345.pdf"), Path("/tmp/x.md"))
        self.assertIn("nicht gefunden", str(ctx.exception).lower())


class FrozenMessageTests(unittest.TestCase):
    def test_dev_message_mentions_pip(self) -> None:
        self.assertIn("pip install", converter.missing_markitdown_message())

    def test_frozen_message_points_to_github(self) -> None:
        import sys
        from unittest.mock import patch

        with patch.object(sys, "frozen", True, create=True):
            msg = converter.missing_markitdown_message()
        self.assertNotIn("pip install", msg)
        self.assertIn("GitHub", msg)


class BrandingTests(unittest.TestCase):
    def test_readme_and_app_name_the_author(self) -> None:
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        app_src = (root / "app.py").read_text(encoding="utf-8")
        spec = (root / "packaging" / "macos" / "PDF-zu-Markdown.spec").read_text(
            encoding="utf-8"
        )
        self.assertIn("Micky Wenngatz", readme)
        self.assertIn('APP_AUTHOR = "Micky Wenngatz"', app_src)
        self.assertIn("Über…", app_src)
        self.assertIn("NSHumanReadableCopyright", spec)
        self.assertIn("Micky Wenngatz", spec)


if __name__ == "__main__":
    unittest.main()
