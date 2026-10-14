#!/usr/bin/env python3
"""Tests für den Seitenaufbau von PDFs (Überschriften, Tabellen, Spalten, Fußnoten)
und für die Texterkennung unter Windows."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import converter
import pdf_layout

BODY = (
    "Der Ortsverein trifft sich jeden zweiten Dienstag im Monat",
    "und bespricht aktuelle Anträge aus Kommune und Land.",
    "Gäste sind jederzeit willkommen, auch ohne Anmeldung.",
)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def text(x: float, y: float, value: str, *, size: float = 10, font: str = "F1", rise: float = 0) -> str:
    rise_op = f" {rise} Ts" if rise else ""
    return f"BT /{font} {size} Tf{rise_op} {x} {y} Td ({_escape(value)}) Tj ET\n"


def end_of(x: float, value: str, size: float = 10) -> float:
    """Wo eine Helvetica-Zeile endet; dort steht ein hochgestelltes Fußnotenzeichen."""
    from pdfminer.fontmetrics import FONT_METRICS

    widths = FONT_METRICS["Helvetica"][1]
    return x + sum(widths.get(ch, 556) for ch in value) * size / 1000


def build_pdf(content: str) -> bytes:
    """Einseitiges PDF mit Helvetica (F1) und Helvetica-Bold (F2), Inhalt als PDF-Operatoren."""
    data = content.encode("cp1252")
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>",
        b"<< /Length " + str(len(data)).encode() + b" >>\nstream\n" + data + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for index, body in enumerate(bodies, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(bodies) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(bodies) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def body_lines(x: float, y: float, lines=BODY, *, repeat: int = 1) -> str:
    out = ""
    for line in list(lines) * repeat:
        out += text(x, y, line)
        y -= 13
    return out


class LayoutTestCase(unittest.TestCase):
    def analyze(self, content: str) -> pdf_layout.PdfLayout:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "test.pdf"
            path.write_bytes(build_pdf(content))
            layout = pdf_layout.analyze_pdf(path)
        self.assertIsNotNone(layout)
        return layout


class HeadingTests(LayoutTestCase):
    def test_large_and_bold_lines_become_headings(self) -> None:
        content = (
            text(72, 770, "Jahresbericht 2026", size=22)
            + text(72, 730, "Einleitung", size=15)
            + body_lines(72, 705, repeat=2)
            + text(72, 600, "Kasse und Finanzen", font="F2")
            + body_lines(72, 580, repeat=2)
        )
        page = self.analyze(content).pages[0]
        self.assertIn("# Jahresbericht 2026", page)
        self.assertIn("## Einleitung", page)
        # Fett in Fließtextgröße: eine Stufe unter der kleinsten Überschrift
        self.assertIn("### Kasse und Finanzen", page)
        self.assertNotIn("# Der Ortsverein", page)

    def test_large_intro_paragraph_is_not_a_heading(self) -> None:
        # Großer Einleitungstext mit weitem Zeilenabstand zerfällt in Einzelzeilen
        content = (
            text(72, 770, "Soziale Politik für Dich. Dafür steht die SPD, dafür stehen", size=14)
            + text(72, 745, "wir. Das ist ein Versprechen an alle, die hier leben.", size=14)
            + body_lines(72, 700, repeat=3)
        )
        page = self.analyze(content).pages[0]
        self.assertNotIn("#", page)
        self.assertIn("Soziale Politik für Dich", page)


class TableTests(LayoutTestCase):
    def test_ruled_table_becomes_markdown_table(self) -> None:
        rows = [("Posten", "2025", "2026"), ("Beiträge", "1.200", "1.450"), ("Spenden", "300", "520")]
        content = "0.5 w\n"
        for i in range(len(rows) + 1):  # waagerechte Linien
            y = 700 - i * 20
            content += f"72 {y} m 372 {y} l S\n"
        for x in (72, 172, 272, 372):  # senkrechte Linien
            content += f"{x} 700 m {x} 640 l S\n"
        for r, row in enumerate(rows):
            for c, cell in enumerate(row):
                content += text(78 + c * 100, 686 - r * 20, cell)
        content += body_lines(72, 600)
        layout = self.analyze(content)
        page = layout.pages[0]
        self.assertEqual(layout.tables, 1)
        self.assertIn("| Posten | 2025 | 2026 |", page)
        self.assertIn("| --- | --- | --- |", page)
        self.assertIn("| Spenden | 300 | 520 |", page)
        # Tabellentext nicht noch einmal als Fließtext
        self.assertEqual(page.count("Beiträge"), 1)

    def test_sparse_grid_like_a_chart_is_not_a_table(self) -> None:
        content = "0.5 w\n"
        for i in range(4):
            y = 700 - i * 20
            content += f"72 {y} m 472 {y} l S\n"
        for x in range(72, 473, 50):
            content += f"{x} 700 m {x} 640 l S\n"
        for r, (col, value) in enumerate([(1, "45,1"), (5, "41,5"), (7, "7,2")]):
            content += text(78 + col * 50, 686 - r * 20, value)
        content += body_lines(72, 600)
        self.assertEqual(self.analyze(content).tables, 0)


class ColumnTests(LayoutTestCase):
    def test_two_columns_are_read_one_after_the_other(self) -> None:
        left = [f"Links Zeile {n} mit etwas Text" for n in range(1, 16)]
        right = [f"Rechts Zeile {n} mit etwas Text" for n in range(1, 16)]
        content = (
            text(72, 780, "Aktivitäten im Überblick", size=16)
            + body_lines(72, 740, left)
            + body_lines(320, 740, right)
        )
        layout = self.analyze(content)
        page = layout.pages[0]
        self.assertEqual(layout.two_column_pages, 1)
        self.assertLess(page.index("Aktivitäten"), page.index("Links Zeile 1 "))
        self.assertLess(page.index("Links Zeile 15"), page.index("Rechts Zeile 1 "))


class FootnoteTests(LayoutTestCase):
    def test_footnotes_move_to_the_end_with_references(self) -> None:
        content = (
            body_lines(72, 760, repeat=2)
            + text(72, 670, "Die Mitgliederzahl ist gestiegen")
            + text(end_of(72, "Die Mitgliederzahl ist gestiegen"), 674, "1", size=6)
            + text(72, 657, "und die Kasse ist ausgeglichen.")
            + text(72, 90, "1", size=6, rise=3)
            + text(78, 90, "Stand 30. September 2026, laut Mitglieder-", size=8)
            + text(78, 80, "verwaltung.", size=8)
        )
        layout = self.analyze(content)
        self.assertIn("gestiegen[^1]", layout.pages[0])
        self.assertNotIn("Stand 30. September", layout.pages[0])
        self.assertEqual(
            layout.footnotes, [("1", "Stand 30. September 2026, laut Mitgliederverwaltung.")]
        )
        self.assertEqual(
            pdf_layout.footnote_section(layout.footnotes),
            "[^1]: Stand 30. September 2026, laut Mitgliederverwaltung.",
        )

    def test_small_print_without_reference_stays_text(self) -> None:
        content = body_lines(72, 760, repeat=3) + text(72, 90, "1 Quelle: eigene Erhebung", size=8)
        layout = self.analyze(content)
        self.assertEqual(layout.footnotes, [])
        self.assertIn("Quelle: eigene Erhebung", layout.pages[0])


class ConvertDocumentTests(unittest.TestCase):
    def test_structure_reaches_markdown_file(self) -> None:
        content = (
            text(72, 770, "Jahresbericht", size=22)
            + body_lines(72, 730, repeat=3)
            + text(72, 600, "Mehr Mitglieder")
            + text(end_of(72, "Mehr Mitglieder"), 604, "1", size=6)
            + text(72, 90, "1", size=6, rise=3)
            + text(78, 90, "Stand September.", size=8)
        )
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "bericht.pdf"
            source.write_bytes(build_pdf(content))
            report = converter.convert_document(source, Path(raw) / "bericht.md", extract_images=False, ocr=False)
            markdown = report.target.read_text(encoding="utf-8")
        self.assertTrue(markdown.startswith("# Jahresbericht"))
        self.assertIn("Mehr Mitglieder[^1]", markdown)
        self.assertTrue(markdown.rstrip().endswith("[^1]: Stand September."))
        self.assertEqual((report.headings, report.footnotes), (1, 1))


@unittest.skipUnless(sys.platform == "win32", "Windows-Texterkennung nur unter Windows")
class WindowsOcrTests(unittest.TestCase):
    def test_reads_rendered_page(self) -> None:
        if not converter.ocr_available():
            self.skipTest("Windows-Texterkennung auf diesem Rechner nicht eingerichtet")
        content = text(72, 700, "Hallo Welt", size=40) + text(72, 600, "Texterkennung 2026", size=40)
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "scan.pdf"
            path.write_bytes(build_pdf(content))
            pages = converter.ocr_pdf(path)
        print(f"\nWindows-Texterkennung erkannte: {pages!r}")
        self.assertEqual(len(pages), 1)
        self.assertIn("Welt", pages[0])
        self.assertIn("2026", pages[0])
        # Zwei weit auseinanderliegende Zeilen: zwei Absätze in der richtigen Reihenfolge
        self.assertLess(pages[0].index("Hallo"), pages[0].index("Texterkennung"))


if __name__ == "__main__":
    unittest.main()
