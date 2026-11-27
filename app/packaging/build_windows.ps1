# Build the Windows installer: ExamGen-Setup.exe (app + bundled TinyTeX + starter question bank).
# Requirements on the build PC: Python 3.12, Node 20+, Inno Setup 6 (iscc on PATH), internet access.
# Run from the app\ folder:   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
$ErrorActionPreference = "Stop"
$App = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $App

Write-Host "1/6  Python environment"
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install ".\backend[desktop]"

Write-Host "2/6  Interface (React)"
Push-Location frontend
npm ci --no-audit --no-fund
npm run build
Pop-Location
Remove-Item -Recurse -Force backend\examgen\static -ErrorAction SilentlyContinue
Copy-Item -Recurse frontend\dist backend\examgen\static

Write-Host "3/6  TinyTeX"
$tt = "packaging\build\TinyTeX"
if (-not (Test-Path "$tt\bin\windows\pdflatex.exe")) {
  New-Item -ItemType Directory -Force packaging\build | Out-Null
  $rel = Invoke-RestMethod "https://api.github.com/repos/rstudio/tinytex-releases/releases/latest"
  $asset = $rel.assets | Where-Object { $_.name -match '^TinyTeX-1-v.*\.zip$' } | Select-Object -First 1
  Invoke-WebRequest $asset.browser_download_url -OutFile packaging\build\tinytex.zip
  Expand-Archive packaging\build\tinytex.zip -DestinationPath packaging\build -Force
}
$tlmgr = "$tt\bin\windows\tlmgr.bat"
& $tlmgr option repository ctan
& $tlmgr install (Get-Content packaging\tex-packages.txt)
& "$tt\bin\windows\fmtutil-sys.exe" --byfmt pdflatex | Out-Null

Write-Host "4/6  Starter question bank"
& sh make_seed.sh 2>$null
if ($LASTEXITCODE -ne 0) {  # no sh on Windows: do it in PowerShell
  Remove-Item -Recurse -Force seed -ErrorAction SilentlyContinue
  New-Item -ItemType Directory seed | Out-Null
  foreach ($d in "questions","figures","exams","templates") { if (Test-Path "..\$d") { Copy-Item -Recurse "..\$d" "seed\$d" } }
  if (Test-Path "..\config.yaml") { Copy-Item "..\config.yaml" seed\ }
}

Write-Host "5/6  PyInstaller"
.\.venv\Scripts\pyinstaller --noconfirm --distpath packaging\dist --workpath packaging\build\pyi packaging\examgen.spec
Copy-Item -Recurse -Force $tt packaging\dist\ExamGen\tinytex
Copy-Item -Recurse -Force seed packaging\dist\ExamGen\seed

Write-Host "6/6  Installer"
iscc packaging\installer.iss
Write-Host "Done: packaging\Output\ExamGen-Setup.exe"
