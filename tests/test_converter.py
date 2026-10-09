#!/usr/bin/env python3
"""Tests für die lokale MarkItDown-Konvertierung (ohne GUI)."""

from __future__ import annotations

import tempfile
import unittest
from unittest import mock
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


class FailingEngine:
    """Ersetzt MarkItDown: scheitert bei Dateien mit „kaputt“ im Namen."""

    def convert_local(self, path: str, **kwargs):
        if "kaputt" in path:
            raise ValueError("Datei beschädigt")
        return type("Result", (), {"markdown": f"Inhalt von {Path(path).name}"})()


class BatchTests(unittest.TestCase):
    def test_one_failure_does_not_stop_the_rest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            files = [folder / "eins.txt", folder / "kaputt.txt", folder / "drei.txt"]
            for f in files:
                f.write_text("x", encoding="utf-8")
            jobs = converter.build_jobs(files)
            with mock.patch.object(converter, "create_markitdown", FailingEngine):
                batch = converter.run_batch(jobs)
            self.assertEqual([p.name for p in batch.written], ["eins.md", "drei.md"])
            self.assertEqual([p.name for p, _ in batch.failures], ["kaputt.txt"])
            self.assertTrue((folder / "drei.md").exists())

    def test_convert_jobs_reports_failures_after_finishing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            files = [folder / "kaputt.txt", folder / "zwei.txt"]
            for f in files:
                f.write_text("x", encoding="utf-8")
            with mock.patch.object(converter, "create_markitdown", FailingEngine):
                with self.assertRaises(converter.ConverterError) as ctx:
                    converter.convert_jobs(converter.build_jobs(files))
            self.assertIn("kaputt.txt", str(ctx.exception))
            self.assertTrue((folder / "zwei.md").exists())


PNG_1PX = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class ImageTests(unittest.TestCase):
    def test_data_uri_images_become_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "Mein Bericht.md"
            markdown = f"Text\n\n![Logo](data:image/png;base64,{PNG_1PX})\n\nmehr"
            result, count = converter.extract_data_uri_images(markdown, target)
            self.assertEqual(count, 1)
            self.assertIn("![Logo](<Mein Bericht_bilder/bild-001.png>)", result)
            self.assertNotIn("base64", result)
            saved = Path(raw) / "Mein Bericht_bilder" / "bild-001.png"
            self.assertEqual(saved.read_bytes()[:4], b"\x89PNG")

    @unittest.skipUnless(converter.pdf_images_available(), "pypdfium2/Pillow fehlen")
    def test_pdf_images_are_saved_once(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            pdf = folder / "fotos.pdf"
            red = Image.new("RGB", (200, 150), (200, 30, 30))
            red.save(pdf, save_all=True, append_images=[red.copy()])  # gleiches Bild auf 2 Seiten
            section, count = converter.extract_pdf_images(pdf, folder / "fotos.md")
            self.assertEqual(count, 1)
            self.assertIn("Seite 1", section)
            self.assertTrue((folder / "fotos_bilder" / "bild-001.png").exists())

    def test_without_images_no_folder_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            pdf = folder / "text.pdf"
            pdf.write_bytes(build_simple_pdf("Nur Text hier, ausreichend viele Zeichen fuer eine Seite"))
            converter.convert_file(pdf, folder / "text.md", extract_images=False)
            self.assertFalse((folder / "text_bilder").exists())


class ScanTests(unittest.TestCase):
    def test_looks_scanned(self) -> None:
        self.assertTrue(converter.looks_scanned("  \n ", 1))
        self.assertTrue(converter.looks_scanned("Seite 1", 3))
        self.assertFalse(converter.looks_scanned("Ein ganz normaler Absatz " * 5, 1))

    def test_scan_without_ocr_gives_warning(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            pdf = folder / "leer.pdf"
            pdf.write_bytes(build_simple_pdf(""))
            report = converter.convert_document(pdf, folder / "leer.md", ocr=False)
            self.assertTrue(any("Scan" in w for w in report.warnings))

    @unittest.skipUnless(converter.ocr_available(), "Texterkennung nur auf dem Mac mit ocrmac")
    def test_scanned_pdf_is_read_with_ocr(self) -> None:
        from PIL import Image, ImageDraw, ImageFont

        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            page = Image.new("RGB", (1240, 1754), "white")
            draw = ImageDraw.Draw(page)
            font = ImageFont.load_default(size=48)
            draw.text((100, 150), "Sehr geehrte Damen und Herren,", fill="black", font=font)
            draw.text((100, 240), "dies ist ein gescannter Testbrief.", fill="black", font=font)
            pdf = folder / "scan.pdf"
            page.save(pdf)
            report = converter.convert_document(pdf, folder / "scan.md")
            text = (folder / "scan.md").read_text(encoding="utf-8")
            self.assertEqual(report.ocr_pages, 1)
            self.assertIn("gescannter Testbrief", text)
            self.assertFalse((folder / "scan_bilder").exists())
class ProfileTests(unittest.TestCase):
    def test_repeating_header_and_footer_are_removed(self) -> None:
        pages = [
            f"Musterverein e.V.\nInhalt {n} ist hier.\nNoch mehr Text {n}.\nSeite {n} von 4"
            for n in range(1, 5)
        ]
        cleaned, removed = converter.remove_repeating_lines(pages)
        self.assertEqual(removed, 8)
        self.assertEqual(cleaned[0], "Inhalt 1 ist hier.\nNoch mehr Text 1.")

    def test_short_documents_keep_everything(self) -> None:
        pages = ["Kopf\nText A", "Kopf\nText B"]
        self.assertEqual(converter.remove_repeating_lines(pages), (pages, 0))

    def test_page_markers(self) -> None:
        self.assertEqual(
            converter.join_pages(["Eins", "", "Drei"], page_markers=True),
            "[Seite 1]\n\nEins\n\n[Seite 2]\n\n[Seite 3]\n\nDrei",
        )
        self.assertEqual(converter.join_pages(["Eins", "", "Drei"], page_markers=False), "Eins\n\nDrei")

    def test_frontmatter_escapes_yaml(self) -> None:
        head = converter.build_frontmatter(
            Path("a.pdf"), 'Titel: mit "Zitat"', pages=2, ocr=False
        )
        self.assertTrue(head.startswith("---\ntitle: \"Titel: mit \\\"Zitat\\\"\"\n"))
        self.assertIn("pages: 2", head)
        self.assertNotIn("ocr", head)

    def test_empty_table_header_gets_first_row(self) -> None:
        table = "|  |  |\n| --- | --- |\n| Posten | Betrag |\n| Porto | 5 € |"
        self.assertEqual(
            converter.fix_empty_table_headers(table),
            "| Posten | Betrag |\n| --- | --- |\n| Porto | 5 € |",
        )

    def test_page_markers_without_ocr(self) -> None:
        # Wenig Text gilt als Scan; ohne Texterkennung (z. B. Windows) braucht es trotzdem Seiten.
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            pdf = folder / "kurz.pdf"
            pdf.write_bytes(build_simple_pdf("Kurzer Text"))
            converter.convert_document(pdf, folder / "kurz.md", ocr=False, page_markers=True)
            text = (folder / "kurz.md").read_text(encoding="utf-8")
            self.assertIn("[Seite 1]", text)
            self.assertIn("Kurzer Text", text)

    def test_profile_options_reach_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            pdf = folder / "bericht.pdf"
            pdf.write_bytes(build_simple_pdf("Ein Absatz mit genug Text fuer eine Seite."))
            converter.convert_document(
                pdf, folder / "bericht.md", **converter.PROFILES["KI & Recherche"]
            )
            text = (folder / "bericht.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\ntitle: "))
            self.assertIn("[Seite 1]", text)
            self.assertNotIn("\f", text)


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
        win_spec = (root / "packaging" / "windows" / "PDF-zu-Markdown.spec").read_text(
            encoding="utf-8"
        )
        self.assertIn("Micky Wenngatz", readme)
        self.assertIn('APP_AUTHOR = "Micky Wenngatz"', app_src)
        self.assertIn("Über…", app_src)
        self.assertIn("NSHumanReadableCopyright", spec)
        self.assertIn("Micky Wenngatz", spec)
        win_readme = (root / "packaging" / "windows" / "LIESMICH.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("version=version_file", win_spec)
        self.assertIn("Micky Wenngatz", win_readme)
        self.assertTrue((root / "packaging" / "icons" / "app_icon.ico").is_file())


if __name__ == "__main__":
    unittest.main()
