# Baut die Windows-App „PDF zu Markdown“ (Ordner mit .exe + ZIP).
# Muss auf Windows laufen (PyInstaller-Binaries sind plattformspezifisch).
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

if ($env:OS -notlike "*Windows*") {
    Write-Error @"
Dieses Skript erzeugt eine .exe und muss auf Windows laufen.
Ohne eigenen PC: GitHub Actions → Workflow „App bauen“ (windows-latest).
"@
}

$AppName = "PDF zu Markdown"
$Version = (Get-Content -Raw "$Root\VERSION").Trim()
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

function Test-Python {
    & $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
    if ($LASTEXITCODE -ne 0) { throw "Python 3.10+ wird benötigt." }
    & $Python -c "import tkinter"
    if ($LASTEXITCODE -ne 0) { throw "Tkinter fehlt in dieser Python-Installation." }
}

Test-Python

$Venv = if ($env:VENV) { $env:VENV } else { Join-Path $Root ".venv-build" }
$VenvPython = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "==> Virtuelle Umgebung: $Venv"
    & $Python -m venv $Venv
}
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r "$Root\requirements.txt" -r "$Root\requirements-build.txt"
& $VenvPython -c "import tkinter, customtkinter, markitdown; print('tkinter+markitdown ok')"
if ($LASTEXITCODE -ne 0) { throw "Abhängigkeiten unvollständig." }

Write-Host "==> Icon (.ico)"
& $VenvPython "$Root\packaging\icons\generate_app_icon.py"
& $VenvPython "$Root\packaging\icons\generate_ico.py"
if (-not (Test-Path "$Root\packaging\icons\app_icon.ico")) {
    throw "app_icon.ico wurde nicht erzeugt."
}

Write-Host "==> Versionsinfo"
& $VenvPython "$Root\packaging\windows\generate_version_info.py"

Write-Host "==> Tests"
& $VenvPython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Tests fehlgeschlagen." }

Write-Host "==> PyInstaller"
$Dist = Join-Path $Root "dist"
$Build = Join-Path $Root "build"
if (Test-Path $Dist) { Remove-Item -Recurse -Force $Dist }
if (Test-Path $Build) { Remove-Item -Recurse -Force $Build }
& $VenvPython -m PyInstaller --noconfirm --clean "$Root\packaging\windows\PDF-zu-Markdown.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fehlgeschlagen." }

$AppDir = Join-Path $Dist $AppName
$Exe = Join-Path $AppDir "$AppName.exe"
if (-not (Test-Path $Exe)) { throw "EXE nicht gefunden: $Exe" }

Copy-Item "$Root\packaging\windows\LIESMICH.txt" (Join-Path $AppDir "LIESMICH.txt") -Force

$ZipName = "PDF-zu-Markdown-$Version-windows-x64.zip"
$ZipPath = Join-Path $Dist $ZipName
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Compress-Archive -Path $AppDir -DestinationPath $ZipPath -CompressionLevel Optimal

Write-Host ""
Write-Host "Fertig. Version $Version (windows-x64)"
Get-Item $Exe, $ZipPath | Format-Table Name, Length
Write-Host "Ordner: $AppDir"
Write-Host "Lokal:  Start-Process `"$Exe`""
Write-Host "SmartScreen: Weitere Informationen → Trotzdem ausführen."
