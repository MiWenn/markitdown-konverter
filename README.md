# PDF zu Markdown

Kleine macOS-App, die **PDF** (und Word, PowerPoint, Excel) lokal mit [Microsoft MarkItDown](https://github.com/microsoft/markitdown) nach Markdown wandelt. Keine Cloud, kein Azure Document Intelligence.

Anzeige-Name der gepackten App: **PDF zu Markdown**.

---

## Für den Mac — ohne Terminal (Doppelklick)

Du brauchst **kein** Python und **kein** Terminal. Die fertige App kommt als Scheibe (`.dmg`) von GitHub.

### 1. Richtige Datei wählen

- **Apple-Chip** (M1, M2, M3, M4 — die meisten Macs ab 2020): Datei mit `arm64` im Namen
- **Intel-Mac** (älter): Datei mit `x86_64` im Namen

Unsicher? Apple-Menü  → **Über diesen Mac**. Steht dort **Chip**, nimm `arm64`. Steht **Prozessor**, nimm `x86_64`.

### 2. Herunterladen

**Am einfachsten — Releases** (nach dem ersten Versions-Tag `v…`):

1. Öffne [Releases](https://github.com/MiWenn/markitdown-konverter/releases).
2. Lade `PDF-zu-Markdown-…-macos-arm64.dmg` oder `…-x86_64.dmg`.

**Solange es noch kein Release gibt — Actions:**

1. Öffne [Actions → macOS App](https://github.com/MiWenn/markitdown-konverter/actions/workflows/macos-app.yml).
2. Klicke auf den neuesten **grünen** Lauf.
3. Unten unter **Artifacts** `PDF-zu-Markdown-macos-arm64` oder `…-x86_64` laden (ZIP von GitHub, darin liegt die `.dmg`).
4. Du musst bei GitHub angemeldet sein. Artifacts bleiben etwa 90 Tage.

Der Download ist mehrere hundert Megabyte groß: MarkItDown samt PDF- und Office-Unterstützung ist **offline** in der App enthalten.

### 3. Installieren

1. Doppelklick auf die `.dmg`.
2. Ziehe **PDF zu Markdown** auf den Ordner **Programme** (Applications).
3. Die Scheibe im Finder auswerfen.

### 4. Beim ersten Öffnen (Gatekeeper)

Apple blockiert Programme, die nicht aus dem App Store kommen. Das ist normal und **kein Virenfund**. Die App läuft nur auf deinem Mac und sendet nichts in die Cloud.

**So startest du sie das erste Mal:**

1. Ordner **Programme** öffnen.
2. **Nicht** doppelklicken.
3. Die App **mit der rechten Maustaste** anklicken (oder Control-Taste halten und klicken).
4. **Öffnen** wählen.
5. Im Hinweis erneut **Öffnen** bestätigen.

Ab dann reicht ein normaler Doppelklick.

Falls macOS (z. B. Sequoia oder Tahoe) die App trotzdem sperrt:

1. **Systemeinstellungen** → **Datenschutz & Sicherheit**
2. Nach unten zum Hinweis über die blockierte App scrollen
3. **Trotzdem öffnen** wählen

Die App ist **nicht** mit einem Apple-Entwicklerzertifikat signiert (kein Notarization). Deshalb erscheint die Warnung. Wer später signieren will, braucht ein Apple-Developer-Konto; die Build-Skripte sind darauf vorbereitet (`packaging/macos/entitlements.plist`).

### 5. Nutzen

1. App öffnen.
2. **Auswählen…** — PDF, Word (`.docx`), PowerPoint (`.pptx`) oder Excel (`.xlsx` / `.xls`). Mehrere Dateien gehen.
3. Ausgabe: **Neben Quelle** (Standard) oder **Ziel wählen**.
4. **Konvertieren**.
5. Die `.md`-Datei liegt neben dem Original bzw. im gewählten Ordner. Optional **Im Finder zeigen**.

Dateien lassen sich auch auf das App-Symbol ziehen.

Gescannte PDFs ohne Textschicht liefern oft wenig oder keinen Text. MarkItDown macht hier **kein OCR**.

---

## Was die App kann

- Eine oder mehrere Dateien auswählen
- Ausgabe automatisch vorschlagen: gleicher Ordner, gleicher Dateiname, Endung `.md`
- Optional eigenen Zielpfad oder Zielordner wählen
- Fortschritt und Fehlermeldungen im Protokoll anzeigen
- Nach Erfolg die Datei im Finder zeigen (macOS)

Einstieg aus dem Quellcode: `app.py` (Oberfläche) oder `converter.py` (Terminal).

## Voraussetzungen (nur für den Start aus dem Quellcode)

- macOS mit **Python 3.10 oder neuer**
- Tkinter (ist bei der [python.org](https://www.python.org/downloads/)-Installation enthalten)

Falls `import tkinter` fehlschlägt (häufig bei Homebrew-Python):

```bash
brew install python-tk
```

## Einrichtung auf dem Mac (Entwickler)

Im Projektordner:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` installiert MarkItDown mit den Extras `[pdf,docx,pptx,xlsx,xls]` plus `customtkinter`.

## Starten aus dem Quellcode

```bash
source .venv/bin/activate
python3 app.py
```

Dateien können zusätzlich als Argumente übergeben werden:

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

## Tests

```bash
source .venv/bin/activate
python3 -m unittest discover -s tests -v
```

## macOS-App bauen (.app / .dmg)

PyInstaller kann ein `.app`-Bundle **nur auf einem Mac** erzeugen. Dieses Repository enthält alles dafür; ein Linux-Rechner ersetzt den Mac-Build nicht.

### Ein Befehl auf dem Mac

```bash
./scripts/build_macos.sh
```

Das Skript legt eine Build-venv an, installiert `requirements.txt` plus `requirements-build.txt`, erzeugt das Icon, läuft die Tests und schreibt:

- `dist/PDF zu Markdown.app`
- `dist/PDF-zu-Markdown-<version>-macos-<arch>.dmg` (App + Verknüpfung Programme)
- `dist/PDF-zu-Markdown-<version>-macos-<arch>.zip`

`<arch>` ist `arm64` oder `x86_64`.

### Ohne eigenen Mac: GitHub Actions

Workflow [macOS App](https://github.com/MiWenn/markitdown-konverter/actions/workflows/macos-app.yml):

| Runner | Ergebnis |
| --- | --- |
| `macos-latest` | Apple Silicon (`arm64`) |
| `macos-15-intel` | Intel (`x86_64`; `macos-13` gibt es bei GitHub nicht mehr) |

Auslöser: Push auf `main`, Pull Request, **Run workflow**, oder Tag `v1.0.0` (dann zusätzlich GitHub Release mit den DMGs).

### Icon

Master-Grafik: `packaging/icons/app_icon.png` (1024×1024, vollflächig — macOS maskiert selbst).

Neu erzeugen:

```bash
pip install Pillow
./scripts/generate_icns.sh
```

Quellen: `packaging/icons/generate_app_icon.py`, `generate_icns.py`. Auf dem Mac schreibt `iconutil` das `.icns`, sonst Pillow.

### Spezifikation

- `packaging/macos/PDF-zu-Markdown.spec` — onedir-Bundle, MarkItDown-Extras, customtkinter, Magika/ONNX
- `packaging/macos/entitlements.plist` — für späteres Codesigning (JIT / library validation)
- Anzeige-Name: **PDF zu Markdown**
- Bundle-ID: `de.miwenn.pdf-zu-markdown`

Die App ist absichtlich **nicht** notarisiert. Gatekeeper-Hinweis siehe oben.

## Fehler, die oft vorkommen

| Meldung | Was tun |
| --- | --- |
| „kann nicht geöffnet werden“ / identifizierter Entwickler | Rechtsklick → Öffnen, oder Datenschutz & Sicherheit → Trotzdem öffnen |
| MarkItDown ist nicht installiert (Quellcode) | venv aktivieren, dann `pip install -r requirements.txt` |
| `optional dependency [pdf]` | dieselbe Installation; manuell: `pip install 'markitdown[pdf,docx,pptx,xlsx,xls]'` |
| Kein Grafikdisplay / TclError | `python3 app.py` in der macOS-Oberfläche starten, nicht per SSH ohne Display |
| Leere Markdown-Datei | PDF prüfen: ist überhaupt Text markierbar, oder nur ein Scan? |
