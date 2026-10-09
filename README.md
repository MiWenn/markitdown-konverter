# PDF zu Markdown

Kleine macOS-App, die **PDF** (und optional Word, PowerPoint, Excel) lokal mit [Microsoft MarkItDown](https://github.com/microsoft/markitdown) nach Markdown wandelt. Keine Cloud, kein Azure Document Intelligence.

Zielgruppe: Nutzung auf dem Mac (z. B. macOS Tahoe) — Oberfläche und diese Anleitung sind auf Deutsch.

## Was die App kann

- Eine oder mehrere Dateien auswählen oder **ins Fenster ziehen** (auch ganze Ordner)
- Start per **Doppelklick** als Mac-App; Dateien lassen sich auch aufs Dock-Symbol ziehen
- Ausgabe automatisch vorschlagen: gleicher Ordner, gleicher Dateiname, Endung `.md`
- Optional eigenen Zielpfad oder Zielordner wählen
- **Bilder** aus Word, PowerPoint und PDF als Dateien speichern (Ordner `…_bilder` neben der `.md`)
- **Gescannte PDFs** mit der Texterkennung von macOS (Apple Vision) lesen, ebenfalls lokal
- Scheitert eine Datei, laufen die übrigen weiter; am Ende gibt es eine Zusammenfassung
- Fortschritt, Hinweise und Fehlermeldungen im Protokoll anzeigen
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
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

(`python3.13` statt `python3`, weil das bei macOS mitgelieferte `python3` zu alt ist.)

`requirements.txt` installiert MarkItDown mit den Extras `[pdf,docx,pptx,xlsx,xls]`, die Oberfläche `customtkinter`, `tkinterdnd2` für Drag & Drop, `pypdfium2` und `pillow` für PDF-Bilder sowie `ocrmac` für die Texterkennung.

### Als Mac-App mit Symbol einrichten

```bash
./macos/app-erstellen.sh
```

Legt **Dokumente zu Markdown.app** in `~/Applications` an. Von dort ins Dock ziehen. Die App startet den Konverter aus diesem Projektordner, der Ordner darf also danach nicht verschoben werden (sonst das Skript erneut ausführen).

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

1. Dateien oder Ordner **ins Fenster ziehen** oder **Auswählen…** klicken.
2. Ausgabe: **Neben Quelle** (Standard) oder **Ziel wählen**.
3. Optionen: **Bilder als Dateien speichern** und **Texterkennung (OCR)** sind standardmäßig an.
4. **Konvertieren**: Fortschritt erscheint oben, Details im Protokoll.
5. Fertig: `.md` liegt neben der Quelle bzw. im gewählten Ordner, Bilder im Ordner `…_bilder`.

**Bilder:** In Word und PowerPoint stehen die Bilder an ihrer ursprünglichen Stelle im Text. Bei PDFs lässt sich die Position nicht zuverlässig bestimmen; deshalb sammelt die App sie am Ende unter „Bilder aus dem PDF“, sortiert nach Seite. Sehr kleine Grafiken und Wiederholungen (z. B. ein Logo auf jeder Seite) werden übersprungen.

**Gescannte PDFs:** Enthält ein PDF kaum Text (weniger als 40 Zeichen pro Seite), liest die App es mit der Texterkennung von macOS. Der erkannte Text ist nach Seiten gegliedert und sollte auf Lesefehler geprüft werden. Tabellen und Spalten werden dabei nicht nachgebildet.

Im Terminal schalten `--ohne-bilder` und `--ohne-ocr` die beiden Funktionen ab.

## Tests

```bash
source .venv/bin/activate
python3 -m unittest discover -s tests -v
```

## Fehler, die oft vorkommen

| Meldung | Was tun |
| --- | --- |
| MarkItDown ist nicht installiert | venv aktivieren, dann `pip install -r requirements.txt` |
| `optional dependency [pdf]` | dieselbe Installation, Anführungszeichen nicht vergessen, falls man MarkItDown manuell setzt: `pip install 'markitdown[pdf,docx,pptx,xlsx,xls]'` |
| Kein Grafikdisplay / TclError | `python3 app.py` in der macOS-Oberfläche starten, nicht per SSH ohne Display |
| Hinweis „vermutlich ein Scan“ | Texterkennung einschalten bzw. `pip install -r requirements.txt` ausführen |
| Ziehen ins Fenster geht nicht | `tkinterdnd2` fehlt: `pip install -r requirements.txt`; „Auswählen…“ funktioniert immer |
| App startet nicht per Doppelklick | Projektordner verschoben? `./macos/app-erstellen.sh` erneut ausführen |
