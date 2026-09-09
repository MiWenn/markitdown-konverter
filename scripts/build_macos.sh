#!/usr/bin/env bash
# Baut die macOS-App „PDF zu Markdown“ (.app + .dmg).
# Muss auf einem Mac laufen (PyInstaller erzeugt Bundles nur unter Darwin).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP_NAME="PDF zu Markdown"
ARCH="$(uname -m)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
DIST="$ROOT/dist"
BUILD="$ROOT/build"
SPEC="$ROOT/packaging/macos/PDF-zu-Markdown.spec"

die() { echo "Fehler: $*" >&2; exit 1; }

if [[ "$(uname -s)" != "Darwin" ]]; then
  cat >&2 <<EOF
Dieses Skript erzeugt eine echte .app und muss auf macOS laufen.
Auf diesem Rechner ($(uname -s)) ist kein Mac-Bundle möglich.

Ohne eigenen Mac: GitHub Actions → Workflow „macOS App“ starten
(oder einen Versions-Tag v* pushen). Die .dmg erscheint als Artifact/Release.
EOF
  exit 1
fi

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null || die "python3 nicht gefunden"

"$PYTHON" - <<'PY' || die "Python 3.10+ wird benötigt"
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY

"$PYTHON" - <<'PY' || die "Tkinter fehlt. python.org-Installer nutzen oder: brew install python-tk"
import tkinter
PY

VENV="${VENV:-$ROOT/.venv-build}"
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "==> Virtuelle Umgebung: $VENV"
  "$PYTHON" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "==> Abhängigkeiten"
python -m pip install --upgrade pip
python -m pip install -r "$ROOT/requirements.txt" -r "$ROOT/requirements-build.txt"

echo "==> Icon (.icns)"
python "$ROOT/packaging/icons/generate_app_icon.py"
python "$ROOT/packaging/icons/generate_icns.py"
[[ -f "$ROOT/packaging/icons/app_icon.icns" ]] || die "app_icon.icns wurde nicht erzeugt"

echo "==> Tests"
python -m unittest discover -s tests -v

echo "==> PyInstaller"
rm -rf "$DIST" "$BUILD"
pyinstaller --noconfirm --clean "$SPEC"

APP="$DIST/${APP_NAME}.app"
[[ -d "$APP" ]] || die "Bundle nicht gefunden: $APP"
[[ -x "$APP/Contents/MacOS/${APP_NAME}" ]] || die "Ausführbare Datei fehlt im Bundle"

# Finder-Infos und Resource Forks erhalten
ZIP_NAME="PDF-zu-Markdown-${VERSION}-macos-${ARCH}.zip"
DMG_NAME="PDF-zu-Markdown-${VERSION}-macos-${ARCH}.dmg"

echo "==> ZIP ($ZIP_NAME)"
ditto -c -k --keepParent "$APP" "$DIST/$ZIP_NAME"

echo "==> DMG ($DMG_NAME)"
STAGE="$DIST/dmg-root"
rm -rf "$STAGE"
mkdir -p "$STAGE"
ditto "$APP" "$STAGE/${APP_NAME}.app"
ln -s /Applications "$STAGE/Applications"
# UDZO = komprimiertes lesbares Image, Doppelklick im Finder
hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$DIST/$DMG_NAME"
rm -rf "$STAGE"

# Größe ausgeben
echo
echo "Fertig. Version $VERSION ($ARCH)"
ls -lh "$DIST/$DMG_NAME" "$DIST/$ZIP_NAME"
echo "App: $APP"
echo
echo "Lokal testen:  open \"$APP\""
echo "Erste Freigabe: Rechtsklick → Öffnen (Gatekeeper)."
