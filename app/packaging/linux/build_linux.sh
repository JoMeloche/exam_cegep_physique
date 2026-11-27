#!/usr/bin/env bash
# Build the Linux desktop app: ExamGen-x86_64.AppImage and examgen_<version>_amd64.deb
# (app + bundled TinyTeX + starter question bank), both self-contained.
#
# Requirements on the build machine: Python 3.11+, Node 20+, perl, curl, internet access
# (yihui.org for TinyTeX, CTAN for LaTeX packages, GitHub releases for appimagetool).
# Run from anywhere:   bash app/packaging/linux/build_linux.sh
#
# Optional environment:
#   PYTHON=python3.12          Python used for the build venv
#   TINYTEX_DIR=/path/.TinyTeX Use an existing TinyTeX instead of downloading one
#   SKIP_TLMGR=1               Don't install tex-packages.txt with tlmgr (TINYTEX_DIR already has them)
#   SKIP_DEB=1 / SKIP_APPIMAGE=1
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$(cd "$HERE/../.." && pwd)"
OUT="$HERE/dist"
WORK="$HERE/build"
PYTHON="${PYTHON:-python3}"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$APP/backend/pyproject.toml" | head -1)"
mkdir -p "$OUT" "$WORK"
cd "$APP"

echo "1/7  Python environment"
"$PYTHON" -m venv "$WORK/venv"
"$WORK/venv/bin/python" -m pip install --quiet --upgrade pip
"$WORK/venv/bin/pip" install --quiet "$APP/backend[desktop]" "pywebview[qt]>=5" PyQt6 PyQt6-WebEngine

echo "2/7  Interface (React)"
(cd frontend && npm ci --no-audit --no-fund && npm run build)
rm -rf backend/examgen/static
cp -r frontend/dist backend/examgen/static

echo "3/7  TinyTeX"
if [ -n "${TINYTEX_DIR:-}" ]; then
  TT="$TINYTEX_DIR"
else
  # Official TinyTeX installer (installs ~/.TinyTeX, current TeX Live, so tlmgr matches CTAN).
  TT="$HOME/.TinyTeX"
  if [ ! -x "$TT/bin/x86_64-linux/pdflatex" ]; then
    curl -fsSL https://yihui.org/tinytex/install-bin-unix.sh | TINYTEX_INSTALLER=TinyTeX-1 sh
  fi
fi
TT="$(cd "$TT" && pwd)"
TEXBIN="$TT/bin/x86_64-linux"
if [ -z "${SKIP_TLMGR:-}" ]; then
  "$TEXBIN/tlmgr" option repository ctan
  # One at a time: some names in the list (xfp, l3backend) were merged into l3kernel in
  # recent TeX Live, and a single unknown name must not stop the others.
  for pkg in $(cat "$APP/packaging/tex-packages.txt"); do
    "$TEXBIN/tlmgr" install "$pkg" >/dev/null 2>&1 || echo "  tlmgr: $pkg skipped (already present or not in repository)"
  done
  "$TEXBIN/fmtutil-sys" --byfmt pdflatex >/dev/null
fi
# Gate: the app's LaTeX preamble must compile with this TinyTeX.
TEST="$WORK/textest"; rm -rf "$TEST"; mkdir -p "$TEST"
sed 's/<<[a-z_]*>>/1/g' "$APP/backend/examgen/templates/preamble.tex" > "$TEST/t.tex"
printf '%s\n' '\begin{document}' '\begin{questions}\question[5] Test \SI{3.5}{\metre\per\second} $\vec v$ é\end{questions}' '\end{document}' >> "$TEST/t.tex"
(cd "$TEST" && "$TEXBIN/pdflatex" -interaction=nonstopmode -halt-on-error t.tex >/dev/null) \
  || { tail -30 "$TEST/t.log"; echo "TinyTeX cannot compile the app preamble"; exit 1; }
"$TEXBIN/pdflatex" --version | head -1

echo "4/7  Starter question bank"
sh make_seed.sh

echo "5/7  PyInstaller"
rm -rf "$WORK/ExamGen"
"$WORK/venv/bin/pyinstaller" --noconfirm --log-level WARN --distpath "$WORK" --workpath "$WORK/pyi" \
  "$HERE/examgen-linux.spec"
BUNDLE="$WORK/ExamGen"
cp -a "$TT" "$BUNDLE/tinytex"
rm -rf "$BUNDLE/tinytex/texmf-var/web2c/tlmgr.log" "$BUNDLE/tinytex/tlpkg/backups"
cp -a seed "$BUNDLE/seed"


if [ -z "${SKIP_APPIMAGE:-}" ]; then
  echo "6/7  AppImage"
  AD="$WORK/AppDir"
  rm -rf "$AD"
  mkdir -p "$AD/usr/lib" "$AD/usr/share/applications" "$AD/usr/share/icons/hicolor/256x256/apps"
  cp -a "$BUNDLE" "$AD/usr/lib/examgen"
  cp "$HERE/AppRun" "$AD/AppRun"; chmod +x "$AD/AppRun"
  cp "$HERE/examgen.desktop" "$AD/examgen.desktop"
  cp "$HERE/examgen.desktop" "$AD/usr/share/applications/"
  cp "$HERE/examgen.png" "$AD/examgen.png"
  cp "$HERE/examgen.png" "$AD/usr/share/icons/hicolor/256x256/apps/"
  ln -sf examgen.png "$AD/.DirIcon"
  TOOL="$WORK/appimagetool"
  [ -x "$TOOL" ] || { curl -fsSL -o "$TOOL" "$APPIMAGETOOL_URL"; chmod +x "$TOOL"; }
  # --appimage-extract-and-run: works without FUSE (containers, CI runners)
  ARCH=x86_64 "$TOOL" --appimage-extract-and-run --no-appstream "$AD" "$OUT/ExamGen-x86_64.AppImage"
fi

if [ -z "${SKIP_DEB:-}" ]; then
  echo "7/7  .deb package"
  DD="$WORK/deb"
  rm -rf "$DD"
  mkdir -p "$DD/DEBIAN" "$DD/opt" "$DD/usr/bin" "$DD/usr/share/applications" "$DD/usr/share/icons/hicolor/256x256/apps"
  cp -a "$BUNDLE" "$DD/opt/examgen"
  ln -s /opt/examgen/ExamGen "$DD/usr/bin/examgen"
  cp "$HERE/examgen.desktop" "$DD/usr/share/applications/"
  cp "$HERE/examgen.png" "$DD/usr/share/icons/hicolor/256x256/apps/"
  cat > "$DD/DEBIAN/control" <<CTRL
Package: examgen
Version: $VERSION
Section: education
Priority: optional
Architecture: amd64
Maintainer: ExamGen <noreply@example.com>
Installed-Size: $(du -sk "$DD" | cut -f1)
Depends: libc6 (>= 2.35), libgl1, libegl1, libxkbcommon0, libxkbcommon-x11-0, libfontconfig1, libdbus-1-3, libnss3, libxcomposite1, libxdamage1, libxrandr2, libxtst6, libasound2 | libasound2t64
Description: Exam generator (question bank, versioned exams, LaTeX PDFs)
 Desktop app to manage a LaTeX question bank and generate versioned exams
 with solutions. Bundles TinyTeX, so no separate LaTeX install is needed.
CTRL
  dpkg-deb --root-owner-group --build "$DD" "$OUT/examgen_${VERSION}_amd64.deb"
fi

echo "Done:"
ls -lh "$OUT"
