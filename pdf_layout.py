# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Micky Wenngatz
"""Seitenaufbau von Text-PDFs: Überschriften, Tabellen mit Linien, Spalten, Fußnoten.

MarkItDown liest PDFs als Fließtext. Hier wird jede Seite aus ihren Textblöcken
(pdfminer) neu zusammengesetzt:

- Überschriften: Blöcke in deutlich größerer Schrift als der Fließtext werden zu
  „#“, „##“, „###“, kurze fette Zeilen in Fließtextgröße eine Stufe darunter.
- Tabellen mit Linien (pdfplumber) werden Markdown-Tabellen; ihr Text taucht
  nicht noch einmal als Fließtext auf.
- Zweispaltige Seiten werden Spalte für Spalte gelesen statt Zeile für Zeile quer.
- Fußnoten unten auf der Seite werden zu „[^1]: …“ am Dokumentende, die hochgestellten
  Ziffern im Text zu „[^1]“.

Ohne pdfplumber/pdfminer liefert analyze_pdf None; dann bleibt es bei MarkItDown.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

# Ab diesem Verhältnis zur Fließtextgröße gilt ein Block als Überschrift.
HEADING_MIN_RATIO = 1.15
HEADING_MAX_CHARS = 150
HEADING_MAX_LINES = 3
HEADING_LEVELS = 3
BOLD_HEADING_MAX_CHARS = 80
# Fußnoten: kleiner als der Fließtext und im unteren Seitenteil.
FOOTNOTE_MAX_RATIO = 0.9
FOOTNOTE_ZONE = 0.35
SUPERSCRIPT_MAX_RATIO = 0.8
# Tabellen: höchstens so viele leere Zellen (sonst eher ein Diagramm) und zerschnittene Wörter.
TABLE_MAX_EMPTY = 0.35
# Echte Tabellen haben feste Spalten: Im Schnitt ist jede Spalte in so vielen Zeilen gefüllt.
# Balkendiagramme verteilen ihre Werte dagegen quer über wechselnde „Spalten“.
TABLE_MIN_COLUMN_FILL = 0.7
TABLE_MAX_CUT_WORDS = 0.03
# Zweispaltig: so viel Anteil des Textes muss sauber links bzw. rechts der Mitte stehen.
COLUMN_MIN_SHARE = 0.25
COLUMN_GUTTER = 0.04
# Kopf-/Fußzeilenbereich: oberer und unterer Seitenrand
EDGE_ZONE = 0.08

_BOLD_FONT = re.compile(r"bold|black|heavy|semibold|demi", re.I)
_FOOTNOTE_START = re.compile(r"^\s*(\d{1,3}|[*†‡])[\s.)]")
_LEAD_MARK = re.compile(r"^\s*(\d{1,3}|[*†‡])[.)]?\s*")


def join_hyphenated(text: str) -> str:
    """Zeilen zu einem Absatz: „kom- men“ → „kommen“, „Set- Design“ → „Set-Design“."""
    text = re.sub(r"(?<=\w)- (?=[a-zäöüß])", "", text)
    return re.sub(r"(?<=\w)- (?=[A-ZÄÖÜ])", "-", text)


@dataclass
class _Line:
    text: str
    size: float
    bold: bool
    # Hochgestellte Ziffernfolgen: (Position im Text, Ziffern)
    marks: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class _Block:
    x0: float
    top: float
    x1: float
    bottom: float
    lines: list[_Line]

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def size(self) -> float:
        counts: Counter[float] = Counter()
        for line in self.lines:
            counts[line.size] += max(len(line.text), 1)
        return counts.most_common(1)[0][0] if counts else 0.0

    @property
    def bold(self) -> bool:
        return all(line.bold for line in self.lines)


@dataclass
class _Page:
    """Zwischenergebnis einer Seite, bevor Überschriften und Fußnoten feststehen."""

    entries: list  # (bbox, _Block oder fertiges Markdown wie eine Tabelle)
    width: float = 0.0
    height: float = 0.0
    form: str | None = None  # ganze Seite als Formular von MarkItDown
    extra: list[str] = field(default_factory=list)  # kommt ans Seitenende


@dataclass
class PdfLayout:
    pages: list[str]
    footnotes: list[tuple[str, str]]  # (Label, Text), Ausgabe am Dokumentende
    tables: int = 0
    headings: int = 0
    two_column_pages: int = 0


def _round_size(value: float) -> float:
    return round(value * 2) / 2


def _char_size(char) -> float:
    return float(getattr(char, "size", 0) or (char.y1 - char.y0))


def _line_from_chars(chars: Sequence) -> _Line:
    """Baut eine Zeile; hochgestellte kleine Ziffern werden als Fußnotenzeichen gemerkt."""
    from pdfminer.layout import LTChar

    sized = [c for c in chars if isinstance(c, LTChar)]
    counts: Counter[float] = Counter(_round_size(_char_size(c)) for c in sized if c.get_text().strip())
    size = counts.most_common(1)[0][0] if counts else 0.0
    baseline = Counter(round(c.y0, 1) for c in sized if _round_size(_char_size(c)) == size)
    base_y = baseline.most_common(1)[0][0] if baseline else 0.0
    letters = [c for c in sized if c.get_text().strip()]
    bold = bool(letters) and all(_BOLD_FONT.search(c.fontname or "") for c in letters)

    text = ""
    marks: list[tuple[int, str]] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            marks.append((len(text), "".join(current)))
            current.clear()

    for char in chars:
        value = char.get_text()
        is_mark = (
            isinstance(char, LTChar)
            and value.isdigit()
            and size
            and _char_size(char) <= size * SUPERSCRIPT_MAX_RATIO
            and char.y0 > base_y + size * 0.2
        )
        if is_mark:
            current.append(value)
            continue
        flush()
        text += value
    flush()
    # Zeichen am Zeilenende (pdfminer) entfernen, Positionen bleiben gültig
    stripped = text.rstrip()
    return _Line(stripped, size, bold, [(min(pos, len(stripped)), digits) for pos, digits in marks])


def _blocks_from_layout(layout, page_top: float, skip: Callable[[object], bool]) -> list[_Block]:
    from pdfminer.layout import LTChar, LTTextBox, LTTextLine

    blocks: list[_Block] = []

    def visit(item) -> None:
        if isinstance(item, LTTextBox):
            lines = []
            for line in item:
                if not isinstance(line, LTTextLine):
                    continue
                chars = [c for c in line if not (isinstance(c, LTChar) and skip(c))]
                built = _line_from_chars(chars)
                if built.text.strip():
                    lines.append(built)
            if lines:
                blocks.append(_Block(item.x0, page_top - item.y1, item.x1, page_top - item.y0, lines))
            return
        if hasattr(item, "__iter__"):
            for child in item:
                visit(child)

    visit(layout)
    return blocks


def _inside(block: _Block, bbox: tuple[float, float, float, float]) -> bool:
    x0, top, x1, bottom = bbox
    cx = (block.x0 + block.x1) / 2
    cy = (block.top + block.bottom) / 2
    return x0 - 1 <= cx <= x1 + 1 and top - 1 <= cy <= bottom + 1


def _cell(text: str | None) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    return value.replace("|", "\\|")


def table_to_markdown(rows: Sequence[Sequence[str | None]]) -> str:
    """Erste Zeile wird Kopfzeile; leere Spalten (verbundene Zellen) fallen weg."""
    width = max(len(row) for row in rows)
    grid = [[_cell(row[i] if i < len(row) else "") for i in range(width)] for row in rows]
    keep = [i for i in range(width) if any(row[i] for row in grid)]
    grid = [[row[i] for i in keep] for row in grid]
    lines = ["| " + " | ".join(grid[0]) + " |", "|" + "|".join(" --- " for _ in keep) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in grid[1:]]
    return "\n".join(lines)


def _cuts_words(page, table) -> bool:
    """Linien, die mitten durch Wörter laufen, gehören zu Grafik, nicht zu einer Tabelle."""
    cells = [cell for cell in table.cells if cell]
    words = page.within_bbox(table.bbox).extract_words()
    if not words or not cells:
        return False
    cut = 0
    for word in words:
        cx = (word["x0"] + word["x1"]) / 2
        cy = (word["top"] + word["bottom"]) / 2
        home = next((c for c in cells if c[0] <= cx <= c[2] and c[1] <= cy <= c[3]), None)
        if home is None or word["x0"] < home[0] - 1 or word["x1"] > home[2] + 1:
            cut += 1
    return cut > max(1, len(words) * TABLE_MAX_CUT_WORDS)


def _ruled_tables(page) -> list[tuple[tuple[float, float, float, float], str]]:
    """Tabellen mit sichtbaren Linien; Rahmen um Textkästen und Diagramme zählen nicht."""
    found = []
    try:
        tables = page.find_tables()
    except Exception:
        return []
    for table in tables:
        try:
            rows = table.extract()
        except Exception:
            continue
        rows = [row for row in rows if any(cell and cell.strip() for cell in row)]
        if len(rows) < 3 or max(len(row) for row in rows) < 2:
            continue
        columns = [
            i for i in range(max(len(row) for row in rows))
            if any(i < len(row) and row[i] and row[i].strip() for row in rows)
        ]
        if len(columns) < 2:
            continue
        def filled(row, i) -> bool:
            return i < len(row) and bool(row[i] and row[i].strip())

        cells = len(rows) * len(columns)
        empty = sum(1 for row in rows for i in columns if not filled(row, i))
        if empty > cells * TABLE_MAX_EMPTY:
            continue
        # Kopfzeile darf Lücken haben (z. B. leere Ecke), deshalb ohne sie rechnen
        body_rows = rows[1:]
        fill = sum(sum(1 for row in body_rows if filled(row, i)) / len(body_rows) for i in columns)
        if fill / len(columns) < TABLE_MIN_COLUMN_FILL:
            continue
        try:
            if _cuts_words(page, table):
                continue
        except Exception:
            continue
        found.append((tuple(table.bbox), table_to_markdown(rows)))
    return found


def _order_blocks(items: list, page_width: float) -> tuple[list, bool]:
    """Lesereihenfolge. Zweispaltig: erst links, dann rechts, getrennt durch breite Blöcke."""
    middle = page_width / 2
    gutter = page_width * COLUMN_GUTTER
    left = right = total = 0.0
    for (x0, _top, x1, _bottom), _item in items:
        width = x1 - x0
        total += width
        if x1 <= middle + gutter:
            left += width
        elif x0 >= middle - gutter:
            right += width
    two_columns = total > 0 and left / total >= COLUMN_MIN_SHARE and right / total >= COLUMN_MIN_SHARE

    by_top = sorted(items, key=lambda entry: (round(entry[0][1]), entry[0][0]))
    if not two_columns:
        return [item for _box, item in by_top], False

    ordered: list = []
    left_col: list = []
    right_col: list = []

    def flush() -> None:
        ordered.extend(item for _box, item in left_col)
        ordered.extend(item for _box, item in right_col)
        left_col.clear()
        right_col.clear()

    for (x0, top, x1, bottom), item in by_top:
        if x1 <= middle + gutter:
            left_col.append(((x0, top, x1, bottom), item))
        elif x0 >= middle - gutter:
            right_col.append(((x0, top, x1, bottom), item))
        else:
            flush()  # Überschrift oder Bild über beide Spalten
            ordered.append(item)
    flush()
    return ordered, True


def _split_footnotes(blocks: list[_Block], body: float, page_height: float) -> tuple[list[_Block], list[tuple[str, str]]]:
    if not body:
        return blocks, []
    zone = page_height * (1 - FOOTNOTE_ZONE)
    candidates = sorted(
        (b for b in blocks if b.top >= zone and b.size and b.size <= body * FOOTNOTE_MAX_RATIO),
        key=lambda b: b.top,
    )
    notes: list[tuple[str, str]] = []
    taken: set[int] = set()
    for block in candidates:
        found: list[tuple[str, str]] = []
        for line in block.lines:
            text = line.text.strip()
            # Fußnotenzeichen am Zeilenanfang ist oft selbst hochgestellt
            if line.marks and line.marks[0][0] == 0:
                text = f"{line.marks[0][1]} {text}"
            match = _FOOTNOTE_START.match(text)
            if match:
                found.append((match.group(1), _LEAD_MARK.sub("", text, count=1).strip()))
            elif found or notes:
                # Fortsetzung der vorigen Fußnote (auch aus dem Block darüber)
                target = found if found else notes
                number, previous = target[-1]
                target[-1] = (number, f"{previous} {text}")
            else:
                found = []
                break
        else:
            if found or notes:
                notes.extend(found)
                taken.add(id(block))
    # Nur echte Fußnoten: Mindestens eine muss im Text darüber hochgestellt erwähnt sein.
    referenced = {
        digits
        for block in blocks
        if id(block) not in taken
        for line in block.lines
        for _pos, digits in line.marks
    }
    if not notes or not any(number in referenced for number, _ in notes):
        return blocks, []
    notes = [(number, join_hyphenated(text)) for number, text in notes]
    return [b for b in blocks if id(b) not in taken], notes


def analyze_pdf(
    source: Path,
    *,
    skip_char: Callable[[object], bool] | None = None,
    form_content: Callable[[object], str | None] | None = None,
    page_extra: Callable[[object], list[str]] | None = None,
) -> PdfLayout | None:
    """Liest alle Seiten eines Text-PDFs mit Aufbau. None, wenn die Bausteine fehlen.

    skip_char lässt einzelne Zeichen aus (z. B. schräg gesetzte), page_extra liefert
    je Seite Absätze, die ans Seitenende kommen (z. B. diese Zeichen, neu sortiert).
    """
    try:
        import pdfplumber
    except ImportError:
        return None

    skip = skip_char or (lambda _char: False)
    raw_pages: list[_Page] = []
    two_column_pages = tables_found = 0
    sizes: Counter[float] = Counter()

    with pdfplumber.open(str(source), laparams={}) as pdf:
        for page in pdf.pages:
            extra = page_extra(page) if page_extra is not None else []
            layout = page.layout
            page_top = layout.y1
            blocks = _blocks_from_layout(layout, page_top, skip)
            tables = _ruled_tables(page)
            items: list = []
            if tables:
                tables_found += len(tables)
                for bbox, markdown in tables:
                    items.append((bbox, markdown))
                blocks = [b for b in blocks if not any(_inside(b, bbox) for bbox, _ in tables)]
            elif form_content is not None:
                # Tabellen ohne Linien (Formulare): MarkItDown kann das schon, also übernehmen.
                try:
                    content = form_content(page)
                except Exception:
                    content = None
                if content is not None:
                    raw_pages.append(_Page([], form=content, extra=extra))
                    page.close()
                    continue
            for block in blocks:
                for line in block.lines:
                    sizes[line.size] += len(line.text)
            items += [((b.x0, b.top, b.x1, b.bottom), b) for b in blocks]
            raw_pages.append(_Page(items, float(page.width), float(page.height), extra=extra))
            page.close()

    body = sizes.most_common(1)[0][0] if sizes else 0.0
    pages: list[list] = []
    page_notes: list[list[tuple[str, str]]] = []
    for page in raw_pages:
        if page.form is not None:
            pages.append([page.form, *page.extra])
            page_notes.append([])
            continue
        blocks = [item for _box, item in page.entries if isinstance(item, _Block)]
        kept, notes = _split_footnotes(blocks, body, page.height)
        kept = _merge_large_lines(_join_edge_rows(kept, page.height), body)
        entries = [(box, item) for box, item in page.entries if not isinstance(item, _Block)]
        entries += [((b.x0, b.top, b.x1, b.bottom), b) for b in kept]
        ordered, two = _order_blocks(entries, page.width)
        two_column_pages += two
        pages.append(ordered + page.extra)
        page_notes.append(notes)

    # Fußnoten-Labels: Nummern, die im Dokument mehrfach vorkommen, bekommen die Seite dazu.
    number_count = Counter(number for notes in page_notes for number, _ in notes)
    labels: list[dict[str, str]] = []
    footnotes: list[tuple[str, str]] = []
    for index, notes in enumerate(page_notes, start=1):
        mapping = {}
        for number, text in notes:
            label = number if number_count[number] == 1 else f"s{index}-{number}"
            mapping[number] = label
            footnotes.append((label, text))
        labels.append(mapping)

    heading_sizes = sorted(
        {
            item.size
            for items in pages
            for item in items
            if isinstance(item, _Block) and _is_heading_candidate(item, body)
        },
        reverse=True,
    )[:HEADING_LEVELS]
    level_of = {size: index + 1 for index, size in enumerate(heading_sizes)}

    headings = 0
    rendered: list[str] = []
    for items, mapping in zip(pages, labels):
        parts: list[str] = []
        for item in items:
            if not isinstance(item, _Block):
                parts.append(item)
                continue
            level = _heading_level(item, body, level_of)
            if level:
                headings += 1
                heading = join_hyphenated(re.sub(r"\s+", " ", _block_text(item, mapping)).strip())
                parts.append("#" * level + " " + heading)
            else:
                parts.append(_block_text(item, mapping))
        rendered.append("\n\n".join(part for part in parts if part.strip()))

    return PdfLayout(rendered, footnotes, tables_found, headings, two_column_pages)


def _reads_like_sentence(text: str) -> bool:
    """Große Schrift ist nicht immer Überschrift: Einleitungstexte enden wie Sätze."""
    flat = re.sub(r"\s+", " ", text).strip()
    if flat.endswith(("-", ",", ";")):
        return True  # Zeile eines längeren Absatzes
    if len(flat) > 60 and flat.endswith((".", "!")):
        return True
    return len(re.findall(r"[.!?] [A-ZÄÖÜ]", flat)) >= 1 and len(flat) > 80


def _is_heading_candidate(block: _Block, body: float) -> bool:
    text = block.text.strip()
    return (
        bool(body)
        and block.size >= body * HEADING_MIN_RATIO
        and len(block.lines) <= HEADING_MAX_LINES
        and len(text) <= HEADING_MAX_CHARS
        and any(ch.isalpha() for ch in text)
        and not _reads_like_sentence(text)
    )


def _join_edge_rows(blocks: list[_Block], page_height: float) -> list[_Block]:
    """Kopf- und Fußzeilen aus mehreren Stücken („Autor   Titel   Seite 3“) werden eine Zeile.

    So erkennt die Kopf-/Fußzeilen-Entfernung sie wieder als wiederkehrende Zeile.
    """
    def at_edge(block: _Block) -> bool:
        return block.bottom <= page_height * EDGE_ZONE or block.top >= page_height * (1 - EDGE_ZONE)

    result: list[_Block] = []
    for block in sorted(blocks, key=lambda b: (round(b.top), b.x0)):
        row = result[-1] if result else None
        if (
            row is not None
            and len(block.lines) == 1
            and len(row.lines) == 1
            and at_edge(block)
            and at_edge(row)
            and abs(row.top - block.top) <= 2
            and block.x0 >= row.x1
        ):
            line = row.lines[0]
            offset = len(line.text) + 1
            line.text = f"{line.text} {block.lines[0].text}"
            line.marks += [(pos + offset, digits) for pos, digits in block.lines[0].marks]
            row.x1 = block.x1
        else:
            result.append(block)
    return result


def _merge_large_lines(blocks: list[_Block], body: float) -> list[_Block]:
    """Absätze in großer Schrift zerfallen bei weitem Zeilenabstand in Einzelzeilen.

    Untereinanderstehende Blöcke gleicher Größe und Einrückung werden wieder vereint,
    damit sie als Absatz erkannt werden und nicht Zeile für Zeile als Überschrift.
    """
    merged: list[_Block] = []
    for block in sorted(blocks, key=lambda b: (b.top, b.x0)):
        previous = next(
            (
                m for m in reversed(merged)
                if body
                and m.size == block.size
                and m.size >= body * HEADING_MIN_RATIO
                and abs(m.x0 - block.x0) <= 2
                and 0 <= block.top - m.bottom <= block.size * 0.9
            ),
            None,
        )
        if previous is not None and not previous.text.rstrip().endswith(":"):
            previous.lines.extend(block.lines)
            previous.bottom = block.bottom
            previous.x1 = max(previous.x1, block.x1)
        else:
            merged.append(block)
    return merged


def _heading_level(block: _Block, body: float, level_of: dict[float, int]) -> int:
    if _is_heading_candidate(block, body):
        return level_of.get(block.size, HEADING_LEVELS)
    text = block.text.strip()
    if (
        block.bold
        and len(block.lines) == 1
        and len(text) <= BOLD_HEADING_MAX_CHARS
        and body
        and abs(block.size - body) <= 0.5
        and not text.endswith((".", ":", ",", ";", "-"))
        and (text[0].isupper() or text[0].isdigit() or text[0] in "„\"»")
        and sum(ch.isalpha() for ch in text) >= 3
    ):
        return len(level_of) + 1  # eine Stufe unter der kleinsten Schriftgrößen-Überschrift
    return 0


def _block_text(block: _Block, labels: dict[str, str]) -> str:
    out = []
    for line in block.lines:
        text = line.text
        for position, digits in sorted(line.marks, reverse=True):
            label = labels.get(digits)
            insert = f"[^{label}]" if label else digits
            text = text[:position] + insert + text[position:]
        out.append(text)
    return "\n".join(out)


def footnote_section(footnotes: Sequence[tuple[str, str]]) -> str:
    return "\n".join(f"[^{label}]: {text}" for label, text in footnotes)
