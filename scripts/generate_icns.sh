#!/usr/bin/env bash
# Icon-Quellen erzeugen (PNG-Master, iconset, .icns).
# Läuft auf Linux und macOS (macOS nutzt iconutil, sonst Pillow).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

"$PYTHON" - <<'PY' || { echo "Pillow fehlt: pip install Pillow" >&2; exit 1; }
import PIL
PY

"$PYTHON" "$ROOT/packaging/icons/generate_app_icon.py"
"$PYTHON" "$ROOT/packaging/icons/generate_icns.py"
