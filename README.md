# PDF zu Markdown

**Von Micky Wenngatz.**

Kleine Desktop-App für **macOS** und **Windows 11**, die **PDF** (und Word, PowerPoint, Excel) lokal mit [Microsoft MarkItDown](https://github.com/microsoft/markitdown) nach Markdown wandelt. Keine Cloud, kein Azure Document Intelligence.

Anzeige-Name: **PDF zu Markdown**. Autor: **Micky Wenngatz** ([GitHub](https://github.com/MiWenn/markitdown-konverter)).

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

1. Öffne [Actions → App bauen](https://github.com/MiWenn/markitdown-konverter/actions/workflows/macos-app.yml).
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
2. Dateien oder Ordner **ins Fenster ziehen** oder **Auswählen…** klicken: PDF, Word (`.docx`), PowerPoint (`.pptx`) oder Excel (`.xlsx` / `.xls`). Mehrere Dateien gehen.
3. Ausgabe: **Neben Quelle** (Standard) oder **Ziel wählen**.
4. **Konvertieren**.
5. Die `.md`-Datei liegt neben dem Original bzw. im gewählten Ordner. Optional **Im Finder zeigen**.

Dateien lassen sich auch auf das App-Symbol ziehen.

Bilder landen im Ordner `…_bilder` neben der Markdown-Datei. Gescannte PDFs liest die App mit der Texterkennung von macOS.

---

## Für Windows 11 — ohne Terminal (Doppelklick)

Du brauchst **kein** Python und **kein** Terminal. Die fertige App kommt als ZIP von GitHub (64-Bit, übliche PCs).

### 1. Herunterladen

**Am einfachsten — Releases** (nach dem ersten Versions-Tag `v…`):

1. Öffne [Releases](https://github.com/MiWenn/markitdown-konverter/releases).
2. Lade `PDF-zu-Markdown-…-windows-x64.zip`.

**Solange es noch kein Release gibt — Actions:**

1. Öffne [Actions → App bauen](https://github.com/MiWenn/markitdown-konverter/actions/workflows/macos-app.yml).
2. Klicke auf den neuesten **grünen** Lauf.
3. Unten unter **Artifacts** `PDF-zu-Markdown-windows-x64` laden.
4. Du musst bei GitHub angemeldet sein. Artifacts bleiben etwa 90 Tage.

Der Download ist groß: MarkItDown samt PDF- und Office-Unterstützung ist **offline** enthalten.

### 2. Starten

1. Das heruntergeladene ZIP mit der rechten Maustaste → **Alle extrahieren…** (nicht die .exe aus dem ZIP heraus starten).
2. Ordner z. B. auf den Desktop legen.
3. **PDF zu Markdown.exe** doppelklicken.

### 3. Beim ersten Öffnen (SmartScreen)

Windows warnt bei Programmen ohne Microsoft-Signatur. Das ist normal und **kein Virenfund**. Die App läuft nur auf deinem PC und sendet nichts in die Cloud.

**Wenn „Windows hat den PC geschützt“ erscheint:**

1. **Weitere Informationen** anklicken.
2. **Trotzdem ausführen** wählen.

Falls die Datei von einem Freund kommt und Windows sie weiter blockiert: Rechtsklick auf die `.exe` → **Eigenschaften** → unten **Zulassen** / **Unblock** → **OK**, dann erneut starten.

### 4. Nutzen

Wie auf dem Mac: Dateien ins Fenster ziehen oder **Auswählen…** → **Konvertieren**. Optional **Im Explorer zeigen**.

Unterschied zum Mac: Die **Texterkennung für gescannte PDFs** gibt es unter Windows nicht (sie nutzt eine Mac-Funktion). Bei Scans erscheint ein Hinweis im Protokoll.

---

## Was die App kann

- Eine oder mehrere Dateien auswählen oder **ins Fenster ziehen** (auch ganze Ordner)
- Start per **Doppelklick** als fertige App für Mac und Windows; auf dem Mac auch Dateien aufs Dock-Symbol ziehen
- Ausgabe automatisch vorschlagen: gleicher Ordner, gleicher Dateiname, Endung `.md`
- Optional eigenen Zielpfad oder Zielordner wählen
- **Bilder** aus Word, PowerPoint und PDF als Dateien speichern (Ordner `…_bilder` neben der `.md`)
- **Gescannte PDFs** mit der Texterkennung von macOS (Apple Vision) lesen, ebenfalls lokal (nur Mac)
- Scheitert eine Datei, laufen die übrigen weiter; am Ende gibt es eine Zusammenfassung
- Fortschritt, Hinweise und Fehlermeldungen im Protokoll anzeigen
- Nach Erfolg die Datei im Finder (macOS) oder Explorer (Windows) zeigen

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
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

(`python3.13` statt `python3`, weil das bei macOS mitgelieferte `python3` zu alt ist.)

`requirements.txt` installiert MarkItDown mit den Extras `[pdf,docx,pptx,xlsx,xls]`, die Oberfläche `customtkinter`, `tkinterdnd2` für Drag & Drop, `pypdfium2` und `pillow` für PDF-Bilder sowie `ocrmac` für die Texterkennung.

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

Workflow [App bauen](https://github.com/MiWenn/markitdown-konverter/actions/workflows/macos-app.yml):

| Runner | Ergebnis |
| --- | --- |
| `macos-latest` | Apple Silicon (`arm64`) |
| `macos-15-intel` | Intel (`x86_64`; `macos-13` gibt es bei GitHub nicht mehr) |
| `windows-latest` | Windows 64-Bit (`.exe` im ZIP `PDF-zu-Markdown-windows-x64`) |

Auslöser: Push auf `main`, Pull Request, **Run workflow**, oder Tag `v1.0.0` (dann zusätzlich GitHub Release).

### Windows-App bauen (.exe)

Auf einem Windows-11-PC:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

Ergebnis: `dist/PDF zu Markdown/PDF zu Markdown.exe` und `dist/PDF-zu-Markdown-<version>-windows-x64.zip`.

Ohne eigenen Windows-PC den Workflow oben nutzen (Job **Build (windows-x64)**).

### Icon

Master-Grafik: `packaging/icons/app_icon.png` (1024×1024, vollflächig — macOS maskiert selbst).

Neu erzeugen:

```bash
pip install Pillow
./scripts/generate_icns.sh
```

Quellen: `packaging/icons/generate_app_icon.py`, `generate_icns.py`, `generate_ico.py`. Auf dem Mac schreibt `iconutil` das `.icns`, sonst Pillow. Windows nutzt `app_icon.ico`.

### Spezifikation

- `packaging/macos/PDF-zu-Markdown.spec` — macOS-onedir-Bundle
- `packaging/windows/PDF-zu-Markdown.spec` — Windows-onedir (customtkinter + MarkItDown)
- `packaging/macos/entitlements.plist` — für späteres Mac-Codesigning
- Anzeige-Name: **PDF zu Markdown**
- Bundle-ID: `de.miwenn.pdf-zu-markdown`

Die Apps sind absichtlich **nicht** signiert. Gatekeeper- und SmartScreen-Hinweise siehe oben.

## Fehler, die oft vorkommen

| Meldung | Was tun |
| --- | --- |
| „Windows hat den PC geschützt“ (SmartScreen) | Weitere Informationen → Trotzdem ausführen |
| „kann nicht geöffnet werden“ / identifizierter Entwickler | Rechtsklick → Öffnen, oder Datenschutz & Sicherheit → Trotzdem öffnen |
| MarkItDown ist nicht installiert (Quellcode) | venv aktivieren, dann `pip install -r requirements.txt` |
| `optional dependency [pdf]` | dieselbe Installation; manuell: `pip install 'markitdown[pdf,docx,pptx,xlsx,xls]'` |
| Kein Grafikdisplay / TclError | `python3 app.py` in der macOS-Oberfläche starten, nicht per SSH ohne Display |
| Hinweis „vermutlich ein Scan“ | Mac: Häkchen bei Texterkennung setzen (Quellcode: `pip install -r requirements.txt`); Windows: nicht verfügbar |
| Ziehen ins Fenster geht nicht | `tkinterdnd2` fehlt: `pip install -r requirements.txt`; „Auswählen…“ funktioniert immer |
