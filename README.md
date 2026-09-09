# PDF zu Markdown

Kleine macOS-App, die **PDF** (und optional Word, PowerPoint, Excel) lokal mit [Microsoft MarkItDown](https://github.com/microsoft/markitdown) nach Markdown wandelt. Keine Cloud, kein Azure Document Intelligence.

Zielgruppe: Nutzung auf dem Mac (z. B. macOS Tahoe) — Oberfläche und diese Anleitung sind auf Deutsch.

## Was die App kann

- Eine oder mehrere Dateien auswählen
- Ausgabe automatisch vorschlagen: gleicher Ordner, gleicher Dateiname, Endung `.md`
- Optional eigenen Zielpfad oder Zielordner wählen
- Fortschritt und Fehlermeldungen im Protokoll anzeigen
- Nach Erfolg die Datei im Finder zeigen (macOS)

Einstieg: `app.py` (Oberfläche) oder `converter.py` (Terminal).

## Voraussetzungen

- macOS mit **Python 3.10 oder neuer**
- Tkinter (ist bei der [python.org](https://www.python.org/downloads/)-Installation enthalten)

Falls `import tkinter` fehlschlägt (häufig bei Homebrew-Python):

```bash
brew install python-tk
```

## Einrichtung auf dem Mac

Im Projektordner:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` installiert MarkItDown mit den Extras `[pdf,docx,pptx,xlsx,xls]` plus `customtkinter`.

## Starten

```bash
source .venv/bin/activate
python3 app.py
```

Dateien können zusätzlich als Argumente übergeben werden (nützlich, wenn man später ein `.app`-Icon mit Dateien füttert):

```bash
python3 app.py ~/Desktop/bericht.pdf
```

Ohne Oberfläche, direkt im Terminal:

```bash
python3 converter.py ~/Desktop/bericht.pdf
python3 converter.py *.pdf --out-dir ~/Desktop/markdown
python3 converter.py bericht.pdf -o ~/Desktop/bericht.md
```

## Bedienung

1. **Auswählen…** — eine PDF oder mehrere Dokumente (Batch).
2. Ausgabe: **Neben Quelle** (Standard) oder **Ziel wählen**.
3. **Konvertieren** — Fortschritt erscheint oben, Details im Protokoll.
4. Fertig: `.md` liegt neben der Quelle bzw. im gewählten Ordner.

Gescannte PDFs ohne Textschicht liefern oft wenig oder keinen Text. MarkItDown macht hier **kein OCR**, solange kein extra Plugin eingerichtet ist.

## Tests

```bash
source .venv/bin/activate
python3 -m unittest discover -s tests -v
```

## Später als .app packen (optional)

Nicht nötig zum täglichen Gebrauch. Wenn ein Doppelklick-App-Bundle gewünscht ist:

```bash
source .venv/bin/activate
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "PDF zu Markdown" app.py
```

Das Bundle liegt danach in `dist/`. Beim ersten Start unter **Systemeinstellungen → Datenschutz & Sicherheit** ggf. freigeben.

## Fehler, die oft vorkommen

| Meldung | Was tun |
| --- | --- |
| MarkItDown ist nicht installiert | venv aktivieren, dann `pip install -r requirements.txt` |
| `optional dependency [pdf]` | dieselbe Installation, Anführungszeichen nicht vergessen, falls man MarkItDown manuell setzt: `pip install 'markitdown[pdf,docx,pptx,xlsx,xls]'` |
| Kein Grafikdisplay / TclError | `python3 app.py` in der macOS-Oberfläche starten, nicht per SSH ohne Display |
| Leere Markdown-Datei | PDF prüfen: ist überhaupt Text markierbar, oder nur ein Scan? |
