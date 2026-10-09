#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Micky Wenngatz
"""Sammelt die Lizenztexte aller Pakete der Build-Umgebung in THIRD-PARTY-NOTICES.txt.

Die meisten Open-Source-Lizenzen (MIT, BSD, Apache) verlangen, dass ihr Text bei
der Weitergabe mitgeliefert wird. Das Skript läuft beim App-Bau; die Datei wird in
die App gepackt und ist dort über „Über… → Lizenzen anzeigen“ erreichbar.
"""

from __future__ import annotations

import re
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "THIRD-PARTY-NOTICES.txt"

# Nur zum Bauen nötig, landen nicht in der App.
BUILD_ONLY = {
    "altgraph",
    "macholib",
    "pefile",
    "pip",
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "pywin32-ctypes",
    "setuptools",
    "wheel",
}

LICENSE_FILE = re.compile(r"(^|/)(licen[cs]e|copying|notice|thirdpartynotices|authors)[^/]*$", re.I)

# Pakete, die keinen Lizenztext mitliefern: Lizenz und Rechteinhaber laut Projektseite.
KNOWN_LICENSES = {
    "markitdown": ("MIT", "Copyright (c) Microsoft Corporation."),
    "magika": ("Apache-2.0", "Copyright Google LLC (Magika Developers)."),
    "flatbuffers": ("Apache-2.0", "Copyright Google Inc."),
    "cobble": ("BSD-2-Clause", "Copyright (c) 2013, Michael Williamson."),
    "pyobjc-core": ("MIT", "Copyright (c) Ronald Oussoren and the PyObjC contributors."),
    "pyobjc-framework-cocoa": ("MIT", "Copyright (c) Ronald Oussoren and the PyObjC contributors."),
    "pyobjc-framework-coreml": ("MIT", "Copyright (c) Ronald Oussoren and the PyObjC contributors."),
    "pyobjc-framework-quartz": ("MIT", "Copyright (c) Ronald Oussoren and the PyObjC contributors."),
    "pyobjc-framework-vision": ("MIT", "Copyright (c) Ronald Oussoren and the PyObjC contributors."),
}

MIT_TEXT = """{holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""

BSD2_TEXT = """{holder}
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."""


def _name(dist: metadata.Distribution) -> str:
    return (dist.metadata["Name"] or "").strip()


def _license_label(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return expression
    classifiers = [
        c.split("::")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    if classifiers:
        return ", ".join(classifiers)
    short = (meta.get("License") or "").strip()
    return short if short and len(short) < 80 else "siehe Lizenztext"


def _license_texts(dist: metadata.Distribution) -> list[tuple[str, str]]:
    texts = []
    for file in dist.files or []:
        path = str(file)
        in_licenses_dir = ".dist-info/licenses/" in path  # PEP 639: alles darin ist Lizenz
        named_like_license = LICENSE_FILE.search(path) and (
            ".dist-info/" in path or path.count("/") <= 1  # dist-info oder Paketwurzel
        )
        if not (in_licenses_dir or named_like_license):
            continue
        try:
            content = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if content.strip():
            texts.append((file.name, content.strip()))
    if not texts:
        short = (dist.metadata.get("License") or "").strip()
        if len(short) >= 80:  # manche Pakete haben den ganzen Text im Feld „License“
            texts.append(("License", short))
    return texts


def _python_license() -> str | None:
    base = Path(sys.base_prefix)
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for candidate in (base / "lib" / version / "LICENSE.txt", base / "LICENSE.txt", base / "LICENSE"):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="replace").strip()
    return None


def _runtime_licenses() -> list[str]:
    """Python-Laufzeit und Tcl/Tk stecken in der App, sind aber keine pip-Pakete."""
    sections = [
        ("Python " + sys.version.split()[0], _python_license()
         or "Python Software Foundation License: https://docs.python.org/3/license.html"),
        ("Tcl/Tk", (ROOT / "packaging" / "licenses" / "tcl-tk.txt").read_text(encoding="utf-8").strip()),
        ("tkdnd (Drag & Drop für Tk, von Georgios Petasis)",
         "BSD-artige Lizenz wie Tcl/Tk: https://github.com/petasis/tkdnd/blob/master/license.terms"),
    ]
    out: list[str] = []
    for title, content in sections:
        out += ["", "-" * 66, title, "-" * 66, "", content]
    return out


def main() -> int:
    dists = {}
    for dist in metadata.distributions():
        name = _name(dist)
        if name and name.lower() not in BUILD_ONLY:
            dists.setdefault(name.lower(), dist)

    own_license = (ROOT / "LICENSE").read_text(encoding="utf-8").strip()
    out = [
        "PDF zu Markdown – Lizenzen",
        "=" * 66,
        "",
        "Teil 1: Diese App",
        "-" * 66,
        "",
        "PDF zu Markdown",
        "Copyright (C) 2026 Micky Wenngatz",
        "",
        "Dieses Programm ist freie Software: Sie können es unter den Bedingungen",
        "der GNU General Public License Version 3, wie von der Free Software",
        "Foundation veröffentlicht, weitergeben und/oder verändern.",
        "Es wird OHNE JEDE GEWÄHRLEISTUNG bereitgestellt. Der Quellcode steht",
        "unter https://github.com/MiWenn/markitdown-konverter.",
        "",
        own_license,
        "",
        "",
        "Teil 2: Enthaltene Open-Source-Bausteine",
        "=" * 66,
        "",
        "Diese App enthält die folgenden Pakete. Ihre Lizenzen erlauben die",
        "Weitergabe; die Lizenztexte stehen unten vollständig.",
        "",
    ]
    out += [
        f"- {_name(d)} {d.version}  ({_license_label(d)})"
        for _, d in sorted(dists.items())
    ]
    out.append("")
    out += [
        "Außerdem enthalten: Python (PSF-Lizenz), Tcl/Tk (BSD-artige Lizenz)",
        "und tkdnd (BSD-artige Lizenz, über tkinterdnd2).",
        "",
    ]
    if "pypdfium2" in dists:
        out += [
            "pypdfium2 enthält PDFium (Google/Foxit, BSD-3-Clause und Apache-2.0)",
            "samt dessen Bestandteilen; deren Texte stehen beim Paket pypdfium2.",
            "",
        ]
    out += _runtime_licenses()

    collected = {key: _license_texts(dist) for key, dist in dists.items()}
    apache_text = next(
        (
            content
            for texts in collected.values()
            for _, content in texts
            if content.lstrip().startswith("Apache License") and "Version 2.0" in content[:200]
        ),
        "Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0",
    )

    missing = []
    for key, dist in sorted(dists.items()):
        texts = collected[key]
        if not texts and key in KNOWN_LICENSES:
            spdx, holder = KNOWN_LICENSES[key]
            template = {"MIT": MIT_TEXT, "BSD-2-Clause": BSD2_TEXT}.get(spdx)
            content = template.format(holder=holder) if template else f"{holder}\n\n{apache_text}"
            texts = [(f"{spdx} (Text ergänzt, Paket liefert keinen mit)", content)]
        if not texts:
            missing.append(_name(dist))
            continue
        for filename, content in texts:
            out += ["", "-" * 66, f"{_name(dist)} {dist.version} – {filename}", "-" * 66, "", content]

    if missing:
        out += [
            "",
            "-" * 66,
            "Ohne beiliegenden Lizenztext (Lizenz laut Paketangaben oben):",
            ", ".join(missing),
        ]

    TARGET.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{TARGET.name}: {len(dists)} Pakete, ohne Lizenztext: {', '.join(missing) or 'keine'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
