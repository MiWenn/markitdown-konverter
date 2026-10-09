# PDF zu Markdown

**Von Micky Wenngatz.**

Kleine Desktop-App für **macOS** und **Windows 11**, die **PDF** (und Word, PowerPoint, Excel) lokal mit [Microsoft MarkItDown](https://github.com/microsoft/markitdown) nach Markdown wandelt. Keine Cloud, kein Azure Document Intelligence.

Anzeige-Name: **PDF zu Markdown**. Autor: **Micky Wenngatz** ([GitHub](https://github.com/MiWenn/markitdown-konverter)).

---

## Herunterladen und installieren (ohne Terminal)

Die fertigen Apps für **Mac** und **Windows 11** gibt es unter [Releases](https://github.com/MiWenn/markitdown-konverter/releases). Kein Python, kein Terminal nötig.

Beim ersten Öffnen warnen Mac und Windows, weil die App nicht signiert ist. Wie man das einmalig bestätigt, steht Schritt für Schritt in der **[Anleitung](ANLEITUNG.md)**. Die Anleitung liegt auch der Mac-DMG („ZUERST LESEN“) und dem Windows-Ordner („LIESMICH“) bei.

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
3. **Profil** wählen: *Standard* (schlichtes Markdown, auch für Notion), *Notizen & Wissensarchiv* (mit YAML-Metadaten-Kopf für Obsidian, Logseq & Co.) oder *KI & Recherche* (zusätzlich Seitenangaben `[Seite 3]`). Das Profil setzt nur Voreinstellungen; alle Häkchen lassen sich einzeln ändern.
   Weitere Optionen: **Bilder als Dateien speichern**, **Texterkennung für Scans** (Mac), **Kopf- und Fußzeilen entfernen** (PDF).
4. **Konvertieren**: Fortschritt erscheint oben, Details im Protokoll.
5. Fertig: `.md` liegt neben der Quelle bzw. im gewählten Ordner, Bilder im Ordner `…_bilder`.

**Bilder:** In Word und PowerPoint stehen die Bilder an ihrer ursprünglichen Stelle im Text. Bei PDFs lässt sich die Position nicht zuverlässig bestimmen; deshalb sammelt die App sie am Ende unter „Bilder aus dem PDF“, sortiert nach Seite. Sehr kleine Grafiken und Wiederholungen (z. B. ein Logo auf jeder Seite) werden übersprungen.

**Gescannte PDFs:** Enthält ein PDF kaum Text (weniger als 40 Zeichen pro Seite), liest die App es mit der Texterkennung von macOS. Der erkannte Text ist nach Seiten gegliedert und sollte auf Lesefehler geprüft werden. Tabellen und Spalten werden dabei nicht nachgebildet.

**Kopf- und Fußzeilen:** Zeilen, die am oberen oder unteren Seitenrand auf mindestens 60 % der Seiten wiederkehren (Zahlen werden dabei ignoriert, „Seite 3 von 20“ zählt also als gleich), werden bei PDFs ab drei Seiten entfernt.

Im Terminal schalten `--ohne-bilder` und `--ohne-ocr` die beiden Funktionen ab; `--profil "KI & Recherche"` wählt ein Profil.

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

Die Apps sind absichtlich **nicht** signiert. Gatekeeper- und SmartScreen-Hinweise siehe [Anleitung](ANLEITUNG.md).

### Lizenzen

Beim Bauen sammelt `packaging/third_party_notices.py` die Lizenztexte aller mitgelieferten Pakete sowie von Python und Tcl/Tk in `THIRD-PARTY-NOTICES.txt`. Die Datei steckt in der App (**Über… → Lizenzen anzeigen**) und liegt dem Windows-Ordner als `LIZENZEN.txt` bei.

## Fehler, die oft vorkommen

| Meldung | Was tun |
| --- | --- |
| „Windows hat den PC geschützt“ (SmartScreen) | Weitere Informationen → Trotzdem ausführen |
| „wurde nicht geöffnet“ / „Apple konnte nicht überprüfen“ | Fertig → Systemeinstellungen → Datenschutz & Sicherheit → Dennoch öffnen (siehe [Anleitung](ANLEITUNG.md)) |
| „… ist beschädigt“ (Mac) | `xattr -dr com.apple.quarantine "/Applications/PDF zu Markdown.app"` |
| MarkItDown ist nicht installiert (Quellcode) | venv aktivieren, dann `pip install -r requirements.txt` |
| `optional dependency [pdf]` | dieselbe Installation; manuell: `pip install 'markitdown[pdf,docx,pptx,xlsx,xls]'` |
| Kein Grafikdisplay / TclError | `python3 app.py` in der macOS-Oberfläche starten, nicht per SSH ohne Display |
| Hinweis „vermutlich ein Scan“ | Mac: Häkchen bei Texterkennung setzen (Quellcode: `pip install -r requirements.txt`); Windows: nicht verfügbar |
| Ziehen ins Fenster geht nicht | `tkinterdnd2` fehlt: `pip install -r requirements.txt`; „Auswählen…“ funktioniert immer |
