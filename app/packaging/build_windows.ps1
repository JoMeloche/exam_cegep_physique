# Build the Windows installer: ExamGen-Setup.exe (app + bundled TinyTeX + starter question bank).
# Requirements on the build PC: Python 3.12, Node 20+, Inno Setup 6 (found on PATH or in its default folder), internet access.
# Run from the app\ folder:   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
# Also run by .github/workflows/build-windows.yml on a GitHub windows runner.
$ErrorActionPreference = "Stop"
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit $LASTEXITCODE)" } }
$App = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $App

Write-Host "1/6  Python environment"
python -m venv .venv; Check "venv"
.\.venv\Scripts\python -m pip install --upgrade pip; Check "pip upgrade"
.\.venv\Scripts\pip install ".\backend[desktop]"; Check "pip install"

Write-Host "2/6  Interface (React)"
Push-Location frontend
npm ci --no-audit --no-fund; Check "npm ci"
npm run build; Check "npm run build"
Pop-Location
Remove-Item -Recurse -Force backend\examgen\static -ErrorAction SilentlyContinue
Copy-Item -Recurse frontend\dist backend\examgen\static

Write-Host "3/6  TinyTeX"
$tt = Join-Path $App "packaging\build\TinyTeX"  # absolute: fmtutil/kpsewhich fail with a relative path
if (-not (Test-Path "$tt\bin\windows\pdflatex.exe")) {
  New-Item -ItemType Directory -Force packaging\build | Out-Null
  # TinyTeX-1 (small bundle) stopped being published after v2026.03; pin that one (it is TeX Live 2025;
  # see the package step below). Override with $env:TINYTEX_URL.
  $url = if ($env:TINYTEX_URL) { $env:TINYTEX_URL } else {
    "https://github.com/rstudio/tinytex-releases/releases/download/v2026.03/TinyTeX-1-v2026.03.zip" }
  Write-Host "    $url"
  Invoke-WebRequest $url -OutFile packaging\build\tinytex.zip
  Expand-Archive packaging\build\tinytex.zip -DestinationPath packaging\build -Force
  if (-not (Test-Path "$tt\bin\windows\pdflatex.exe")) { throw "TinyTeX extracted but $tt\bin\windows\pdflatex.exe is missing" }
}
$tlmgr = "$tt\bin\windows\tlmgr.bat"
$env:PATH = "$tt\bin\windows;$env:PATH"  # fmtutil needs kpsewhich on PATH
# The pinned TinyTeX is TeX Live 2025, and tlmgr refuses to install from a newer year's repository,
# so install packages from the frozen TL2025 archive. Override with $env:TEXLIVE_REPO.
$repos = if ($env:TEXLIVE_REPO) { @($env:TEXLIVE_REPO) } else { @(
  "https://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2025/tlnet-final",
  "https://ftp.tu-chemnitz.de/pub/tug/historic/systems/texlive/2025/tlnet-final") }
# xfp has been part of l3kernel since TeX Live 2024 and is no longer a package of its own.
$pkgs = Get-Content packaging\tex-packages.txt | Where-Object { $_.Trim() -and $_.Trim() -ne "xfp" }
$ok = $false
foreach ($r in $repos) {
  Write-Host "    packages from $r"
  cmd /c "`"$tlmgr`" --repository $r install $pkgs"
  if ($LASTEXITCODE -eq 0) { $ok = $true; break }
}
if (-not $ok) { throw "tlmgr install failed from every repository" }
cmd /c "`"$tt\bin\windows\fmtutil-sys.exe`" --byfmt pdflatex >NUL"; Check "fmtutil"

Write-Host "4/6  Starter question bank"
# Done in PowerShell (same as make_seed.sh) so the build does not need sh.
Remove-Item -Recurse -Force seed -ErrorAction SilentlyContinue
New-Item -ItemType Directory seed | Out-Null
foreach ($d in "questions","figures","exams","templates") { if (Test-Path "..\$d") { Copy-Item -Recurse "..\$d" "seed\$d" } }
if (Test-Path "..\config.yaml") { Copy-Item "..\config.yaml" seed\ }

Write-Host "5/6  PyInstaller"
.\.venv\Scripts\pyinstaller --noconfirm --distpath packaging\dist --workpath packaging\build\pyi packaging\examgen.spec; Check "PyInstaller"
Copy-Item -Recurse -Force $tt packaging\dist\ExamGen\tinytex
Copy-Item -Recurse -Force seed packaging\dist\ExamGen\seed

Write-Host "6/6  Installer"
$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
  $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $iscc) { throw "Inno Setup 6 (ISCC.exe) not found" }
$ver = if ($env:APP_VERSION) { $env:APP_VERSION } else { "1.0.0" }
& $iscc "/DAppVersion=$ver" packaging\installer.iss; Check "Inno Setup"
Write-Host "Done: packaging\Output\ExamGen-Setup.exe"
