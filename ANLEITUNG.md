# PDF zu Markdown – Anleitung

**Von Micky Wenngatz.** Die App wandelt PDF-, Word-, PowerPoint- und Excel-Dateien in Markdown um. Alles passiert auf deinem eigenen Computer, nichts wird hochgeladen.

Du brauchst nichts weiter zu installieren: kein Python, kein Terminal.

---

## Vorab: Warum warnt mein Computer?

Beim ersten Öffnen zeigt dein Mac oder Windows-PC eine Warnung. **Das ist normal und kein Virenfund.**

Apple und Microsoft lassen Programme nur dann ohne Warnung starten, wenn die Entwicklerin sich dort kostenpflichtig registriert und die App „signiert“ hat. Diese App ist ein kostenloses Geschenk und deshalb nicht signiert. Die Warnung bedeutet nur: „Wir kennen die Herkunft nicht.“ Sie sagt nichts darüber, ob die App gefährlich ist.

Du musst die Warnung **einmal** bestätigen. Danach startet die App ganz normal.

> Lade die App nur über den Link herunter, den du von mir bekommen hast. Dann weißt du, woher sie stammt.

---

## Mac

### 1. Die richtige Datei wählen

Es gibt zwei Mac-Dateien. Welche du brauchst, hängt vom Prozessor ab:

- Klicke oben links auf das Apple-Menü  → **Über diesen Mac**.
- Steht dort **Chip** (zum Beispiel „Apple M2“): Nimm die Datei mit **`arm64`** im Namen.
- Steht dort **Prozessor** (zum Beispiel „Intel Core i5“): Nimm die Datei mit **`x86_64`** im Namen.

Fast alle Macs ab Ende 2020 haben einen Apple-Chip.

### 2. Installieren

1. Doppelklicke die heruntergeladene Datei `PDF-zu-Markdown-….dmg`.
2. Es öffnet sich ein Fenster. Ziehe **PDF zu Markdown** auf den Ordner **Programme**.
3. Schließe das Fenster. Wirf im Finder in der Seitenleiste die Scheibe „PDF zu Markdown“ aus (Klick auf ⏏).

### 3. Das erste Öffnen (nur einmal nötig)

1. Öffne den Ordner **Programme** und doppelklicke **PDF zu Markdown**.
2. Es erscheint die Meldung **„‚PDF zu Markdown‘ wurde nicht geöffnet“** (oder ähnlich: „Apple konnte nicht überprüfen …“).
   Klicke auf **Fertig**. **Nicht** auf „In den Papierkorb legen“.
3. Öffne **Systemeinstellungen** (Apple-Menü  → Systemeinstellungen).
4. Klicke links auf **Datenschutz & Sicherheit**.
5. Scrolle rechts ganz nach unten bis zum Abschnitt **Sicherheit**. Dort steht: „‚PDF zu Markdown‘ wurde blockiert, um deinen Mac zu schützen.“
6. Klicke daneben auf **Dennoch öffnen**.
7. Bestätige mit deinem Passwort oder Touch ID.
8. Es kommt noch einmal eine Rückfrage. Klicke wieder auf **Dennoch öffnen**.

Fertig. Ab jetzt startet die App mit einem normalen Doppelklick.

**Tipp:** Ziehe die App aus dem Programme-Ordner ins Dock. Dann kannst du Dateien direkt auf das Symbol ziehen.

> **Ältere Macs (macOS 14 Sonoma oder älter):** Hier geht es schneller. Klicke die App im Programme-Ordner mit der **rechten Maustaste** an (oder mit gedrückter ctrl-Taste) → **Öffnen** → noch einmal **Öffnen**.

### Falls der Mac sagt: „… ist beschädigt und kann nicht geöffnet werden“

Die App ist nicht beschädigt. macOS zeigt diese Meldung manchmal statt der normalen Warnung. So geht es trotzdem:

1. Öffne das Programm **Terminal**: Drücke cmd + Leertaste, tippe „Terminal“ und drücke Enter.
2. Kopiere diese Zeile hinein und drücke Enter:
   ```
   xattr -dr com.apple.quarantine "/Applications/PDF zu Markdown.app"
   ```
3. Schließe das Terminal und öffne die App normal.

Der Befehl entfernt nur den Vermerk „aus dem Internet geladen“ von dieser einen App.

---

## Windows 11

### 1. Herunterladen und entpacken

1. Lade die Datei `PDF-zu-Markdown-…-windows-x64.zip` herunter.
2. Klicke sie mit der **rechten Maustaste** an → **Alle extrahieren…** → **Extrahieren**.
   Wichtig: Starte die App **nicht** direkt aus der ZIP-Datei heraus, sonst fehlen ihr Bestandteile.
3. Lege den entpackten Ordner an einen festen Platz, zum Beispiel in **Dokumente**.

### 2. Das erste Öffnen (nur einmal nötig)

1. Öffne den Ordner und doppelklicke **PDF zu Markdown.exe**.
2. Es erscheint ein blaues Fenster: **„Der Computer wurde durch Windows geschützt“**.
3. Klicke auf den kleinen Link **Weitere Informationen**.
4. Klicke auf **Trotzdem ausführen**.

Fertig. Ab jetzt startet die App normal.

**Tipp:** Klicke die `.exe` mit der rechten Maustaste an → **An Start anheften** oder **An Taskleiste anheften**.

### Falls Windows die App ganz blockiert, ohne „Trotzdem ausführen“

Dann ist auf deinem PC wahrscheinlich die **intelligente App-Steuerung** (Smart App Control) eingeschaltet. Sie lässt unsignierte Programme grundsätzlich nicht zu, eine Ausnahme für einzelne Apps gibt es nicht. Du kannst sie unter **Einstellungen → Datenschutz und Sicherheit → Windows-Sicherheit → App- und Browsersteuerung** ausschalten. Das gilt dann aber für den ganzen PC und lässt sich je nach Windows-Version nicht ohne Weiteres wieder einschalten. Überlege dir das gut. Im Zweifel nutze die App lieber nicht.

### Falls die Datei von jemand anderem kommt

Windows blockiert manchmal Dateien aus E-Mails oder Cloud-Ordnern. Dann: Rechtsklick auf **PDF zu Markdown.exe** → **Eigenschaften** → unten bei „Sicherheit“ ein Häkchen bei **Zulassen** → **OK**.

---

## So benutzt du die App

1. **Dateien hineinziehen:** Ziehe PDF-, Word-, PowerPoint- oder Excel-Dateien ins Fenster. Ganze Ordner gehen auch. Alternativ: **Auswählen…**
2. **Profil wählen:**
   - **Standard:** schlichtes Markdown für jeden Zweck, auch für Notion.
   - **Notizen & Wissensarchiv:** mit einem Kopfbereich (Titel, Quelle, Datum), den Obsidian, Logseq und ähnliche Programme als Eigenschaften anzeigen.
   - **KI & Recherche:** zusätzlich mit Seitenangaben wie `[Seite 3]`. Praktisch zum Zitieren und für ChatGPT, Claude & Co.
3. **Ausgabe:** Standardmäßig landet die Markdown-Datei neben dem Original. Mit **Ziel wählen** bestimmst du einen anderen Ordner.
4. **Konvertieren** klicken.

Danach findest du neben dem Original:

```
bericht.pdf
bericht.md            ← der Text als Markdown
bericht_bilder/       ← die Bilder aus dem Dokument
    bild-001.png
    bild-002.jpg
```

### Gut zu wissen

- **Gescannte PDFs** (nur Bilder, kein markierbarer Text) liest die App auf dem Mac mit der Texterkennung von macOS. Unter Windows gibt es diese Funktion nicht. Dann erscheint ein Hinweis.
- **Bilder in PDFs** stehen gesammelt am Ende der Markdown-Datei, nach Seiten sortiert. Bei Word und PowerPoint stehen sie an der richtigen Stelle im Text.
- **Kopf- und Fußzeilen**, die sich auf jeder Seite wiederholen (z. B. „Seite 3 von 20“), entfernt die App bei PDFs automatisch. Abschalten kannst du das mit dem entsprechenden Häkchen.
- **Mehrspaltige PDFs, komplizierte Tabellen und Fußnoten** kommen nicht immer in perfekter Reihenfolge heraus. Schau bei wichtigen Dokumenten kurz drüber.

---

## Datenschutz

Die App arbeitet vollständig offline. Deine Dokumente verlassen deinen Computer nicht.

## Lizenzen

Die App ist ein kostenloses Geschenk von Micky Wenngatz. Sie baut auf Open-Source-Software auf, vor allem auf **Microsoft MarkItDown**. Die Lizenzen aller enthaltenen Bausteine findest du in der App unter **Über… → Lizenzen anzeigen**.
