#!/usr/bin/env python3
"""Kleine macOS-taugliche Oberfläche für PDF/Office → Markdown."""

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


def reveal_in_finder(path: Path) -> None:
    if _is_macos():
        subprocess.run(["open", "-R", str(path)], check=False)
        return
    folder = str(path.parent)
    if sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", folder], check=False)


class ConverterApp(ctk.CTk, _DnDBase):
    def __init__(self, initial_files: Sequence[Path] | None = None) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("760x780")
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
        ctk.CTkLabel(
            header,
            text="PDF, Word, PowerPoint und Excel lokal mit Microsoft MarkItDown wandeln — ohne Cloud.",
            wraplength=700,
            justify="left",
            text_color=("gray30", "gray70"),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

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

        self.images_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            out_box,
            text="Bilder als Dateien speichern (Ordner „…_bilder“ neben der Markdown-Datei)",
            variable=self.images_var,
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6))

        ocr_ok = converter.ocr_available()
        self.ocr_var = ctk.BooleanVar(value=ocr_ok)
        ctk.CTkCheckBox(
            out_box,
            text=(
                "Texterkennung (OCR) für gescannte PDFs"
                if ocr_ok
                else "Texterkennung (OCR) für gescannte PDFs – nicht verfügbar"
            ),
            variable=self.ocr_var,
            state="normal" if ocr_ok else "disabled",
        ).grid(row=4, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6))

        self.reveal_var = ctk.BooleanVar(value=_is_macos())
        ctk.CTkCheckBox(
            out_box,
            text="Im Finder zeigen (macOS)",
            variable=self.reveal_var,
        ).grid(row=5, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 12))

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

    def _check_backend(self) -> None:
        try:
            converter.check_python_version()
            converter.create_markitdown()
            self._log("MarkItDown ist bereit. Konvertierung läuft lokal auf diesem Mac.")
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
            hint = (
                "Dateien oder Ordner hierher ziehen oder „Auswählen…“ klicken."
                if getattr(self, "_dnd_enabled", False)
                else "Noch keine Datei. „Auswählen…“ klicken."
            )
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
        options = {"extract_images": self.images_var.get(), "ocr": self.ocr_var.get()}
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
    converter.check_python_version()
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    initial = _argv_files(sys.argv[1:])
    try:
        app = ConverterApp(initial_files=initial)
    except tk.TclError as exc:
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
