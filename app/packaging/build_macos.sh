#!/bin/bash
# Build the macOS app: ExamGen-<version>-macos-<arch>.dmg (app + bundled TinyTeX + starter question bank).
# Requirements on the build Mac: Python 3.12, Node 20+, curl, internet access. Run from app/:
#   bash packaging/build_macos.sh
# The .app targets the Mac's own architecture (Apple Silicon -> arm64, Intel -> x86_64).
# Optional signing: set MACOS_SIGN_IDENTITY="Developer ID Application: ..." (and, for notarization,
# MACOS_NOTARY_PROFILE=<notarytool keychain profile>). Without it the app is ad-hoc signed.
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
PKG=packaging
BUILD=$PKG/build
DIST=$PKG/dist
ARCH="$(uname -m)"
VERSION="${EXAMGEN_VERSION:-$(python3 -c 'import tomllib;print(tomllib.load(open("backend/pyproject.toml","rb"))["project"]["version"])')}"
export EXAMGEN_VERSION="$VERSION"
mkdir -p "$BUILD"

echo "1/7  Python environment"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install "./backend[desktop]"

echo "2/7  Interface (React)"
(cd frontend && npm ci --no-audit --no-fund && npm run build)
rm -rf backend/examgen/static
cp -R frontend/dist backend/examgen/static

echo "3/7  TinyTeX"
TT="$APP_DIR/$BUILD/TinyTeX"
if [ ! -x "$TT/bin/universal-darwin/pdflatex" ]; then
  # Official TinyTeX installer (picks the macOS build, universal-darwin binaries) into ~/Library/TinyTeX
  export TINYTEX_INSTALLER=TinyTeX-1
  curl -fsSL https://yihui.org/tinytex/install-bin-unix.sh | sh
  rm -rf "$TT"; cp -R "$HOME/Library/TinyTeX" "$TT"
fi
TLBIN="$TT/bin/universal-darwin"
"$TLBIN/tlmgr" option repository ctan
"$TLBIN/tlmgr" install $(cat $PKG/tex-packages.txt) || "$TLBIN/tlmgr" install $(cat $PKG/tex-packages.txt)
"$TLBIN/fmtutil-sys" --byfmt pdflatex >/dev/null
# quick self-test of the bundled TeX with the packages the exams use
mkdir -p "$BUILD/textest"
cat > "$BUILD/textest/t.tex" <<'TEX'
\documentclass{exam}\usepackage[french]{babel}\usepackage{siunitx,xfp,enumitem,tikz,amsmath,lmodern}
\begin{document}Test \SI{9.81}{m/s^2} $\fpeval{2*3}$\end{document}
TEX
(cd "$BUILD/textest" && "$TLBIN/pdflatex" -interaction=nonstopmode -halt-on-error t.tex >/dev/null)
echo "     TinyTeX OK"

echo "4/7  Starter question bank"
sh make_seed.sh

echo "5/7  App icon"
if [ ! -f "$BUILD/ExamGen.icns" ] && command -v qlmanage >/dev/null; then
  rm -rf "$BUILD/icon" "$BUILD/ExamGen.iconset"; mkdir -p "$BUILD/icon" "$BUILD/ExamGen.iconset"
  if qlmanage -t -s 1024 -o "$BUILD/icon" frontend/public/favicon.svg >/dev/null 2>&1; then
    src="$BUILD/icon/favicon.svg.png"
    for s in 16 32 128 256 512; do
      sips -z $s $s "$src" --out "$BUILD/ExamGen.iconset/icon_${s}x${s}.png" >/dev/null
      sips -z $((s*2)) $((s*2)) "$src" --out "$BUILD/ExamGen.iconset/icon_${s}x${s}@2x.png" >/dev/null
    done
    iconutil -c icns "$BUILD/ExamGen.iconset" -o "$BUILD/ExamGen.icns" || true
  fi
fi

echo "6/7  PyInstaller"
.venv/bin/pyinstaller --noconfirm --distpath "$DIST" --workpath "$BUILD/pyi" $PKG/examgen-macos.spec
APP="$DIST/ExamGen.app"
RES="$APP/Contents/Resources"
# TinyTeX and the seed live in Resources; symlinks in Frameworks (= sys._MEIPASS) let the app find them,
# the same layout PyInstaller uses for its own data files.
rm -rf "$RES/tinytex" "$RES/seed"
cp -R "$TT" "$RES/tinytex"
cp -R seed "$RES/seed"
ln -sfn ../Resources/tinytex "$APP/Contents/Frameworks/tinytex"
ln -sfn ../Resources/seed "$APP/Contents/Frameworks/seed"
# drop TeX build leftovers that are not needed at run time
rm -rf "$RES/tinytex/texmf-dist/doc" "$RES/tinytex/texmf-dist/source" 2>/dev/null || true

if [ -n "${MACOS_SIGN_IDENTITY:-}" ]; then
  echo "     signing with $MACOS_SIGN_IDENTITY"
  # sign nested Mach-O first (TeX binaries), then the app with the hardened runtime
  find "$RES/tinytex/bin" -type f -perm -u+x -exec sh -c 'file -b "$1" | grep -q Mach-O' _ {} \; \
       -exec codesign --force --timestamp --options runtime --sign "$MACOS_SIGN_IDENTITY" {} \;
  codesign --force --deep --timestamp --options runtime --sign "$MACOS_SIGN_IDENTITY" "$APP"
else
  codesign --force --deep --sign - "$APP"
fi
codesign --verify --deep --strict "$APP" && echo "     signature OK"

echo "7/7  Disk image"
DMG="$DIST/ExamGen-$VERSION-macos-$ARCH.dmg"
STAGE="$BUILD/dmg"
rm -rf "$STAGE" "$DMG"; mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "ExamGen" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
if [ -n "${MACOS_SIGN_IDENTITY:-}" ]; then
  codesign --force --timestamp --sign "$MACOS_SIGN_IDENTITY" "$DMG"
  if [ -n "${MACOS_NOTARY_PROFILE:-}" ]; then
    xcrun notarytool submit "$DMG" --keychain-profile "$MACOS_NOTARY_PROFILE" --wait
    xcrun stapler staple "$DMG"
  fi
fi
echo "Done: $APP_DIR/$DMG"
