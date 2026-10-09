#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Micky Wenngatz
"""Kleine Desktop-Oberfläche für PDF/Office → Markdown."""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Sequence

import converter

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover - GUI-Start
    print(
        "customtkinter fehlt.\n"
        "Bitte: pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(1)

try:  # Drag & Drop ist optional; ohne tkinterdnd2 bleibt „Auswählen…“
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:  # pragma: no cover - abhängig von der Installation
    DND_FILES = None
    TkinterDnD = None

_DnDBase = TkinterDnD.DnDWrapper if TkinterDnD is not None else object

APP_TITLE = "PDF zu Markdown"
APP_AUTHOR = "Micky Wenngatz"
APP_HOMEPAGE = "https://github.com/MiWenn/markitdown-konverter"
FILE_TYPES = [
    ("Dokumente", "*.pdf *.docx *.pptx *.xlsx *.xls"),
    ("PDF", "*.pdf"),
    ("Word", "*.docx"),
    ("PowerPoint", "*.pptx"),
    ("Excel", "*.xlsx *.xls"),
    ("Alle Dateien", "*.*"),
]


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _read_version() -> str:
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "VERSION")
    candidates.append(Path(__file__).resolve().parent / "VERSION")
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return "2.0.1"


def about_text() -> str:
    return (
        f"{APP_TITLE}\n"
        f"von {APP_AUTHOR}\n"
        f"Version {_read_version()}\n\n"
        "Wandelt PDF, Word, PowerPoint und Excel auf diesem Computer nach Markdown um, "
        "samt Bildern und Texterkennung für gescannte PDFs (Mac).\n\n"
        "Die Umwandlung nutzt Microsoft MarkItDown — nur lokal, ohne Cloud.\n\n"
        f"© 2026 {APP_AUTHOR}. Freie Software unter der GNU General Public "
        "License Version 3 (GPL-3.0); ohne jede Gewährleistung.\n"
        f"Quellcode: {APP_HOMEPAGE}\n\n"
        "Lizenztext und die Lizenzen der enthaltenen Open-Source-Bausteine "
        "siehe „Lizenzen anzeigen“."
    )


def _is_windows() -> bool:
    return sys.platform == "win32"


PROFILE_HINTS = {
    "Standard": "Schlichtes Markdown für jeden Zweck, auch zum Einfügen oder Importieren in Notion.",
    "Notizen & Wissensarchiv": (
        "Mit Metadaten-Kopf (Titel, Quelle, Datum), den Obsidian, Logseq & Co. "
        "als Eigenschaften der Notiz anzeigen."
    ),
    "KI & Recherche": (
        "Mit Metadaten-Kopf und Seitenangaben [Seite 3]: gut zum Zitieren und "
        "für ChatGPT, Claude oder eigene KI-Ablagen."
    ),
}

NOTICES_FILE = "THIRD-PARTY-NOTICES.txt"


def third_party_notices_path() -> Path | None:
    """Lizenztexte der mitgelieferten Open-Source-Bausteine (beim App-Bau erzeugt)."""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / NOTICES_FILE)
    candidates.append(Path(__file__).resolve().parent / NOTICES_FILE)
    return next((path for path in candidates if path.is_file()), None)


def open_with_default_app(path: Path) -> None:
    if _is_macos():
        subprocess.run(["open", "-t", str(path)], check=False)
    elif _is_windows():
        import os

        os.startfile(str(path))  # noqa: S606 - öffnet nur unsere eigene Textdatei
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def reveal_in_finder(path: Path) -> None:
    if _is_macos():
        subprocess.run(["open", "-R", str(path)], check=False)
        return
    if _is_windows():
        subprocess.run(["explorer", f"/select,{path}"], check=False)
        return
    folder = str(path.parent)
    if sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", folder], check=False)


class ConverterApp(ctk.CTk, _DnDBase):
    def __init__(self, initial_files: Sequence[Path] | None = None) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("780x820")
        self.minsize(640, 640)

        self.sources: list[Path] = []
        self._busy = False
        self._events: queue.Queue = queue.Queue()

        self._build()
        self._dnd_enabled = self._enable_drag_and_drop()
        self._refresh_file_list()
        if _is_macos():
            # Dateien, die aufs Dock-Symbol gezogen oder per „Öffnen mit“ geschickt werden
            self.createcommand("::tk::mac::OpenDocument", self._on_open_document)
        self._bind_macos_about()
        self._apply_window_icon()
        self._check_backend()
        if initial_files:
            self._add_files(initial_files)
        self.after(80, self._drain_events)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Dokumente zu Markdown",
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header,
            text="Über…",
            width=80,
            fg_color="transparent",
            border_width=1,
            command=self._show_about,
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))
        ctk.CTkLabel(
            header,
            text=f"von {APP_AUTHOR}",
            font=ctk.CTkFont(size=13),
            anchor="w",
            text_color=("gray25", "gray75"),
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
        ctk.CTkLabel(
            header,
            text="PDF, Word, PowerPoint und Excel lokal mit Microsoft MarkItDown wandeln — ohne Cloud.",
            wraplength=700,
            justify="left",
            text_color=("gray30", "gray70"),
            anchor="w",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        files_box = ctk.CTkFrame(self)
        files_box.grid(row=1, column=0, sticky="nsew", padx=20, pady=8)
        files_box.grid_columnconfigure(0, weight=1)
        files_box.grid_rowconfigure(1, weight=1)

        file_bar = ctk.CTkFrame(files_box, fg_color="transparent")
        file_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        ctk.CTkLabel(file_bar, text="Dateien", font=ctk.CTkFont(weight="bold")).pack(
            side="left"
        )
        ctk.CTkButton(file_bar, text="Auswählen…", width=120, command=self._pick_files).pack(
            side="right", padx=(8, 0)
        )
        ctk.CTkButton(
            file_bar,
            text="Liste leeren",
            width=110,
            fg_color="transparent",
            border_width=1,
            command=self._clear_files,
        ).pack(side="right")

        self.file_box = ctk.CTkTextbox(files_box, height=120, wrap="none")
        self.file_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.file_box.configure(state="disabled")

        out_box = ctk.CTkFrame(self)
        out_box.grid(row=2, column=0, sticky="ew", padx=20, pady=8)
        out_box.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(out_box, text="Ausgabe", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 6)
        )

        self.output_mode = ctk.CTkSegmentedButton(
            out_box,
            values=["Neben Quelle", "Ziel wählen"],
            command=self._on_mode_change,
        )
        self.output_mode.set("Neben Quelle")
        self.output_mode.grid(row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 8))

        self.output_entry = ctk.CTkEntry(
            out_box,
            placeholder_text="Wird automatisch vorgeschlagen",
        )
        self.output_entry.grid(row=2, column=0, columnspan=2, sticky="ew", padx=(12, 8), pady=(0, 8))
        self.output_pick_btn = ctk.CTkButton(
            out_box,
            text="Wählen…",
            width=100,
            command=self._pick_output,
        )
        self.output_pick_btn.grid(row=2, column=2, padx=(0, 12), pady=(0, 8))

        ctk.CTkLabel(out_box, text="Profil").grid(
            row=3, column=0, sticky="w", padx=(12, 8), pady=(4, 2)
        )
        self.profile_menu = ctk.CTkOptionMenu(
            out_box,
            values=list(converter.PROFILES),
            command=self._on_profile_change,
            width=220,
        )
        self.profile_menu.grid(row=3, column=1, columnspan=2, sticky="w", pady=(4, 2))
        self.profile_hint = ctk.CTkLabel(
            out_box,
            text="",
            anchor="w",
            justify="left",
            wraplength=680,
            text_color=("gray30", "gray70"),
        )
        self.profile_hint.grid(row=4, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6))

        options = ctk.CTkFrame(out_box, fg_color="transparent")
        options.grid(row=5, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 12))
        options.grid_columnconfigure((0, 1), weight=1, uniform="optionen")

        def option(text: str, variable, row: int, column: int, state: str = "normal") -> None:
            ctk.CTkCheckBox(options, text=text, variable=variable, state=state).grid(
                row=row, column=column, sticky="w", pady=3, padx=(0, 12)
            )

        self.images_var = ctk.BooleanVar(value=True)
        option("Bilder als Dateien speichern", self.images_var, 0, 0)

        ocr_ok = converter.ocr_available()
        self.ocr_var = ctk.BooleanVar(value=ocr_ok)
        option(
            "Texterkennung für Scans" if ocr_ok else "Texterkennung (nur Mac)",
            self.ocr_var,
            1,
            0,
            "normal" if ocr_ok else "disabled",
        )

        self.reveal_var = ctk.BooleanVar(value=_is_macos() or _is_windows())
        if _is_windows():
            reveal_label = "Im Explorer zeigen"
        elif _is_macos():
            reveal_label = "Im Finder zeigen"
        else:
            reveal_label = "Im Ordner zeigen"
        option(reveal_label, self.reveal_var, 2, 0)

        self.frontmatter_var = ctk.BooleanVar()
        option("Metadaten-Kopf (Titel, Quelle, Datum)", self.frontmatter_var, 0, 1)
        self.page_markers_var = ctk.BooleanVar()
        option("Seitenangaben [Seite 3] (PDF)", self.page_markers_var, 1, 1)
        self.strip_headers_var = ctk.BooleanVar()
        option("Kopf- und Fußzeilen entfernen (PDF)", self.strip_headers_var, 2, 1)

        self.profile_menu.set(converter.DEFAULT_PROFILE)
        self._on_profile_change(converter.DEFAULT_PROFILE)

        action = ctk.CTkFrame(self, fg_color="transparent")
        action.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 8))
        action.grid_columnconfigure(0, weight=1)

        self.convert_btn = ctk.CTkButton(
            action,
            text="Konvertieren",
            height=40,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_convert,
        )
        self.convert_btn.grid(row=0, column=0, sticky="ew")

        self.progress = ctk.CTkProgressBar(action)
        self.progress.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.progress.set(0)

        self.status = ctk.CTkLabel(action, text="Bereit.", anchor="w")
        self.status.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        log_box = ctk.CTkFrame(self)
        log_box.grid(row=4, column=0, sticky="nsew", padx=20, pady=(0, 16))
        log_box.grid_columnconfigure(0, weight=1)
        log_box.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(log_box, text="Protokoll", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 4)
        )
        self.log = ctk.CTkTextbox(log_box, wrap="word")
        self.log.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log.configure(state="disabled")

        self._on_mode_change(self.output_mode.get())

    def _on_profile_change(self, name: str) -> None:
        preset = converter.PROFILES[name]
        self.frontmatter_var.set(preset["frontmatter"])
        self.page_markers_var.set(preset["page_markers"])
        self.strip_headers_var.set(preset["strip_headers"])
        self.profile_hint.configure(text=PROFILE_HINTS.get(name, ""))

    def _bind_macos_about(self) -> None:
        if not _is_macos():
            return
        try:
            self.createcommand("tkAboutDialog", self._show_about)
        except tk.TclError:
            pass

    def _show_about(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title(f"Über {APP_TITLE}")
        window.resizable(False, False)
        window.transient(self)
        ctk.CTkLabel(window, text=about_text(), justify="left", wraplength=420).pack(
            padx=24, pady=(20, 12), anchor="w"
        )
        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.pack(fill="x", padx=24, pady=(0, 20))
        notices = third_party_notices_path()
        ctk.CTkButton(
            buttons,
            text="Lizenzen anzeigen",
            command=lambda: open_with_default_app(notices) if notices else None,
            state="normal" if notices else "disabled",
        ).pack(side="left")
        ctk.CTkButton(buttons, text="Schließen", width=100, command=window.destroy).pack(
            side="right"
        )
        window.after(50, window.grab_set)

    def _apply_window_icon(self) -> None:
        if not _is_windows():
            return
        candidates = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "app_icon.ico")
        candidates.append(Path(__file__).resolve().parent / "packaging" / "icons" / "app_icon.ico")
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).with_name("app_icon.ico"))
        for icon in candidates:
            if icon.is_file():
                try:
                    self.iconbitmap(str(icon))
                except tk.TclError:
                    return
                return

    def _check_backend(self) -> None:
        try:
            converter.check_python_version()
            converter.create_markitdown()
            self._log("MarkItDown ist bereit. Konvertierung läuft lokal auf diesem Gerät.")
        except converter.ConverterError as exc:
            self._set_status("MarkItDown fehlt oder ist unvollständig.")
            self._log(str(exc))
            self.convert_btn.configure(state="disabled")
            messagebox.showerror(APP_TITLE, str(exc))

    def _enable_drag_and_drop(self) -> bool:
        if TkinterDnD is None:
            return False
        try:
            TkinterDnD._require(self)
        except (RuntimeError, tk.TclError):
            return False
        # Drop-Ziele gelten pro Widget, deshalb alle Bereiche des Fensters anmelden.
        pending: list[tk.Misc] = [self]
        while pending:
            widget = pending.pop()
            pending.extend(widget.winfo_children())
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop)
            except (AttributeError, tk.TclError):
                continue
        return True

    def _on_drop(self, event) -> str:
        self._add_files([Path(p) for p in self.tk.splitlist(event.data)])
        return getattr(event, "action", "copy")

    def _on_open_document(self, *paths: str) -> None:
        self._add_files([Path(p) for p in paths])

    def _expand(self, paths: Sequence[Path]) -> tuple[list[Path], list[str]]:
        """Ordner werden durch die unterstützten Dateien darin ersetzt."""
        files: list[Path] = []
        skipped: list[str] = []
        for raw in paths:
            path = Path(raw).expanduser().resolve()
            if path.is_dir():
                inside = sorted(
                    p for p in path.iterdir()
                    if p.is_file() and converter.is_supported(p) and not p.name.startswith(".")
                    and p.suffix.lower() != ".md"
                )
                if not inside:
                    skipped.append(f"{path} (Ordner ohne passende Dateien)")
                files.extend(inside)
            else:
                files.append(path)
        return files, skipped

    def _add_files(self, paths: Sequence[Path]) -> None:
        added = 0
        expanded, skipped = self._expand(paths)
        for path in expanded:
            if not path.is_file():
                skipped.append(f"{path} (keine Datei)")
                continue
            if path in self.sources:
                continue
            self.sources.append(path)
            added += 1
            if path.suffix.lower() not in converter.PRIMARY_EXTENSIONS:
                self._log(
                    f"Hinweis: „{path.name}“ ist kein PDF/Office — MarkItDown versucht es trotzdem."
                )
        if added:
            self._refresh_file_list()
            self._suggest_output()
            self._log(f"{added} Datei(en) übernommen.")
        if skipped:
            self._log("Übersprungen:\n" + "\n".join(skipped))

    def _refresh_file_list(self) -> None:
        self.file_box.configure(state="normal")
        self.file_box.delete("1.0", "end")
        if not self.sources:
            if getattr(self, "_dnd_enabled", False):
                hint = "Dateien oder Ordner hierher ziehen oder „Auswählen…“ klicken."
            elif getattr(sys, "frozen", False):
                hint = "Noch keine Datei. „Auswählen…“ wählen oder Dateien auf das App-Symbol ziehen."
            else:
                hint = "Noch keine Datei. „Auswählen…“ oder Dateien per Kommandozeile übergeben."
            self.file_box.insert("1.0", hint)
        else:
            self.file_box.insert("1.0", "\n".join(str(p) for p in self.sources))
        self.file_box.configure(state="disabled")

    def _pick_files(self) -> None:
        chosen = filedialog.askopenfilenames(
            title="Dateien zum Konvertieren",
            filetypes=FILE_TYPES,
        )
        if chosen:
            self._add_files([Path(p) for p in chosen])

    def _clear_files(self) -> None:
        self.sources.clear()
        self._refresh_file_list()
        self.output_entry.delete(0, "end")
        self._set_status("Liste geleert.")

    def _on_mode_change(self, value: str) -> None:
        custom = value == "Ziel wählen"
        state = "normal" if custom else "disabled"
        self.output_entry.configure(state=state)
        self.output_pick_btn.configure(state=state)
        if custom:
            self._suggest_output()

    def _suggest_output(self) -> None:
        if self.output_mode.get() != "Ziel wählen":
            return
        if not self.sources:
            return
        current = self.output_entry.get().strip()
        if len(self.sources) == 1:
            suggested = str(converter.suggest_output_path(self.sources[0]))
        else:
            suggested = str(self.sources[0].parent)
        if current and current not in {suggested, str(self.sources[0].parent)}:
            return
        self.output_entry.configure(state="normal")
        self.output_entry.delete(0, "end")
        self.output_entry.insert(0, suggested)

    def _pick_output(self) -> None:
        if len(self.sources) <= 1:
            initial = self.sources[0] if self.sources else None
            path = filedialog.asksaveasfilename(
                title="Markdown speichern unter",
                defaultextension=".md",
                filetypes=[("Markdown", "*.md"), ("Alle Dateien", "*.*")],
                initialdir=str(initial.parent) if initial else None,
                initialfile=f"{initial.stem}.md" if initial else "dokument.md",
            )
        else:
            path = filedialog.askdirectory(title="Zielordner für alle Markdown-Dateien")
        if path:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, path)

    def _jobs_from_ui(self) -> list[converter.ConversionJob]:
        if self.output_mode.get() != "Ziel wählen":
            return converter.build_jobs(self.sources)

        raw = self.output_entry.get().strip()
        if not raw:
            raise converter.ConverterError("Bitte einen Zielpfad wählen oder „Neben Quelle“ nutzen.")
        target = Path(raw).expanduser()
        if len(self.sources) == 1 and (target.suffix.lower() == ".md" or not target.is_dir()):
            return converter.build_jobs(self.sources, output_file=target)
        return converter.build_jobs(self.sources, output_dir=target)

    def _start_convert(self) -> None:
        if self._busy:
            return
        if not self.sources:
            messagebox.showinfo(APP_TITLE, "Bitte zuerst eine oder mehrere Dateien auswählen.")
            return

        try:
            jobs = self._jobs_from_ui()
        except converter.ConverterError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return

        existing = [job.target for job in jobs if job.target.exists()]
        if existing:
            preview = "\n".join(str(p) for p in existing[:8])
            extra = "" if len(existing) <= 8 else f"\n… und {len(existing) - 8} weitere"
            ok = messagebox.askyesno(
                APP_TITLE,
                "Diese Markdown-Datei(en) existieren bereits und werden überschrieben:\n\n"
                f"{preview}{extra}\n\nTrotzdem fortfahren?",
            )
            if not ok:
                self._set_status("Abgebrochen.")
                return

        self._busy = True
        self.convert_btn.configure(state="disabled")
        self.progress.set(0)
        self._set_status(f"Starte {len(jobs)} Konvertierung(en)…")
        self._log("—")
        options = {
            "extract_images": self.images_var.get(),
            "ocr": self.ocr_var.get(),
            "frontmatter": self.frontmatter_var.get(),
            "page_markers": self.page_markers_var.get(),
            "strip_headers": self.strip_headers_var.get(),
        }
        worker = threading.Thread(target=self._run_jobs, args=(jobs, options), daemon=True)
        worker.start()

    def _run_jobs(self, jobs: Sequence[converter.ConversionJob], options: dict) -> None:
        def progress(kind: str, index: int, total: int, path: Path) -> None:
            if kind == "start":
                self._events.put(("status", f"Konvertiere {index}/{total}: {path.name}"))
                self._events.put(("log", f"{index}/{total}  {path.name}"))
            elif kind == "failed":
                self._events.put(("log", "    FEHLER, wird übersprungen"))
            if kind in {"done", "failed"}:
                self._events.put(("progress", index / total))

        def on_report(report: converter.ConversionReport) -> None:
            details = []
            if report.ocr_pages:
                details.append(f"{report.ocr_pages} Seite(n) per Texterkennung")
            if report.images:
                details.append(f"{report.images} Bild(er)")
            if report.removed_lines:
                details.append(f"{report.removed_lines} Kopf-/Fußzeile(n) entfernt")
            extra = f"  ({', '.join(details)})" if details else ""
            self._events.put(("log", f"    gespeichert: {report.target}{extra}"))
            for warning in report.warnings:
                self._events.put(("log", f"    Hinweis: {warning}"))

        try:
            batch = converter.run_batch(jobs, progress=progress, on_report=on_report, **options)
            self._events.put(("finished", batch))
        except converter.ConverterError as exc:
            self._events.put(("fail", str(exc)))
        except Exception as exc:  # pragma: no cover - unerwartete Laufzeitfehler
            self._events.put(("fail", f"Unerwarteter Fehler:\n{exc}"))

    def _drain_events(self) -> None:
        while True:
            try:
                kind, payload = self._events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._log(str(payload))
            elif kind == "status":
                self._set_status(str(payload))
            elif kind == "progress":
                self.progress.set(float(payload))
            elif kind == "finished":
                self._on_finished(payload)
            elif kind == "fail":
                self._on_fail(str(payload))
        self.after(80, self._drain_events)

    def _on_finished(self, batch: converter.BatchResult) -> None:
        self._busy = False
        self.convert_btn.configure(state="normal")
        self.progress.set(1)
        written = batch.written
        n = len(written)
        failed = len(batch.failures)
        if failed:
            self._set_status(f"Fertig: {n} geschrieben, {failed} fehlgeschlagen.")
            summary = converter.failure_summary(batch.failures)
            self._log(summary)
        else:
            self._set_status(f"Fertig: {n} Markdown-Datei(en) geschrieben.")
        self._log(f"Fertig. {n} Datei(en) erzeugt.")
        if self.reveal_var.get() and written:
            reveal_in_finder(written[-1])
        if failed:
            messagebox.showwarning(APP_TITLE, summary)

    def _on_fail(self, message: str) -> None:
        self._busy = False
        self.convert_btn.configure(state="normal")
        self._set_status("Fehler bei der Konvertierung.")
        self._log(message)
        messagebox.showerror(APP_TITLE, message)

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")


def _argv_files(argv: Sequence[str]) -> list[Path]:
    files: list[Path] = []
    for arg in argv:
        if arg.startswith("-"):
            continue
        path = Path(arg).expanduser()
        if path.exists():
            files.append(path)
    return files


def main() -> int:
    if getattr(sys, "frozen", False):
        import multiprocessing

        multiprocessing.freeze_support()
    converter.check_python_version()
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    initial = _argv_files(sys.argv[1:])
    try:
        app = ConverterApp(initial_files=initial)
    except tk.TclError as exc:
        if getattr(sys, "frozen", False):
            print("Kein Grafikdisplay gefunden.", file=sys.stderr)
        else:
            print(
                "Kein Grafikdisplay gefunden.\n"
                "Auf dem Mac: python3 app.py\n"
                "Ohne Oberfläche: python3 converter.py datei.pdf",
                file=sys.stderr,
            )
        print(exc, file=sys.stderr)
        return 1
    app.mainloop()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except converter.ConverterError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1)
