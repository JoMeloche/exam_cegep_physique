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
$tt = "packaging\build\TinyTeX"
if (-not (Test-Path "$tt\bin\windows\pdflatex.exe")) {
  New-Item -ItemType Directory -Force packaging\build | Out-Null
  $hdr = @{}
  if ($env:GITHUB_TOKEN) { $hdr["Authorization"] = "Bearer $env:GITHUB_TOKEN" }  # avoids API rate limits on CI
  $rel = Invoke-RestMethod "https://api.github.com/repos/rstudio/tinytex-releases/releases/latest" -Headers $hdr
  # Windows bundle: older releases name it TinyTeX-1-v<date>.zip, newer ones TinyTeX-1-windows-v<date>.zip/.exe
  $win = $rel.assets | Where-Object { $_.name -match '^TinyTeX-1-' -and $_.name -match '\.(zip|exe)$' -and $_.name -notmatch 'linux|darwin|mac' }
  $asset = ($win | Where-Object { $_.name -match '\.zip$' } | Select-Object -First 1)
  if (-not $asset) { $asset = $win | Select-Object -First 1 }
  if (-not $asset) { throw "No Windows TinyTeX-1 asset in release $($rel.tag_name): $(($rel.assets.name) -join ', ')" }
  Write-Host "    $($asset.name)"
  if ($asset.name -match '\.zip$') {
    Invoke-WebRequest $asset.browser_download_url -OutFile packaging\build\tinytex.zip
    Expand-Archive packaging\build\tinytex.zip -DestinationPath packaging\build -Force
  } else {  # 7-Zip self-extracting archive
    Invoke-WebRequest $asset.browser_download_url -OutFile packaging\build\tinytex.exe
    & packaging\build\tinytex.exe -y "-opackaging\build"; Check "TinyTeX extract"
  }
  if (-not (Test-Path "$tt\bin\windows\pdflatex.exe")) { throw "TinyTeX extracted but $tt\bin\windows\pdflatex.exe is missing" }
}
$tlmgr = "$tt\bin\windows\tlmgr.bat"
& $tlmgr option repository ctan; Check "tlmgr option"
& $tlmgr install (Get-Content packaging\tex-packages.txt | Where-Object { $_.Trim() }); Check "tlmgr install"
& "$tt\bin\windows\fmtutil-sys.exe" --byfmt pdflatex | Out-Null

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
$ver = if ($env:APP_VERSION) { $env:APP_VERSION } else { "0.1.0" }
& $iscc "/DAppVersion=$ver" packaging\installer.iss; Check "Inno Setup"
Write-Host "Done: packaging\Output\ExamGen-Setup.exe"
