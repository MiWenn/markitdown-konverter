#!/bin/bash
# Erstellt „Dokumente zu Markdown.app“, damit der Konverter per Doppelklick startet.
# Voraussetzung: Im Projektordner gibt es die eingerichtete Umgebung .venv
# (siehe README, Abschnitt „Einrichtung auf dem Mac“).
#
# Aufruf:  ./macos/app-erstellen.sh            → legt die App in ~/Applications an
#          ./macos/app-erstellen.sh /Applications

set -euo pipefail

PROJEKT="$(cd "$(dirname "$0")/.." && pwd)"
ZIEL="${1:-$HOME/Applications}"
APP="$ZIEL/Dokumente zu Markdown.app"
PYTHON="$PROJEKT/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "Die Umgebung .venv fehlt. Bitte zuerst die Einrichtung aus der README ausführen." >&2
    exit 1
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/MacOS/start" <<EOF
#!/bin/bash
exec "$PYTHON" "$PROJEKT/app.py" "\$@"
EOF
chmod +x "$APP/Contents/MacOS/start"

"$PYTHON" "$PROJEKT/macos/symbol.py" "$APP/Contents/Resources/symbol.icns"

cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Dokumente zu Markdown</string>
    <key>CFBundleDisplayName</key>
    <string>Dokumente zu Markdown</string>
    <key>CFBundleIdentifier</key>
    <string>de.miwenn.markitdown-konverter</string>
    <key>CFBundleVersion</key>
    <string>2.0</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>start</string>
    <key>CFBundleIconFile</key>
    <string>symbol</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>
            <string>Dokument</string>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
            <key>LSHandlerRank</key>
            <string>Alternate</string>
            <key>LSItemContentTypes</key>
            <array>
                <string>com.adobe.pdf</string>
                <string>org.openxmlformats.wordprocessingml.document</string>
                <string>org.openxmlformats.presentationml.presentation</string>
                <string>org.openxmlformats.spreadsheetml.sheet</string>
                <string>com.microsoft.excel.xls</string>
                <string>public.html</string>
                <string>org.idpf.epub-container</string>
                <string>public.comma-separated-values-text</string>
                <string>public.json</string>
                <string>public.xml</string>
                <string>public.plain-text</string>
                <string>public.folder</string>
            </array>
        </dict>
    </array>
</dict>
</plist>
EOF

# Finder und Dock über die neue App informieren
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP" >/dev/null 2>&1 || true
touch "$APP"

echo "Fertig: $APP"
echo "Tipp: Die App ins Dock ziehen. Dateien lassen sich dann direkt aufs Symbol ziehen."
