#!/bin/sh
# Installe ExamGen (application de bureau) sur macOS ou Linux, depuis la dernière version publiée.
# Installs the ExamGen desktop app on macOS or Linux from the latest GitHub release.
#
#   curl -fsSL https://raw.githubusercontent.com/JoMeloche/exam_cegep_physique/main/install.sh | sh
#
# macOS : ExamGen.app dans /Applications (ou ~/Applications).
# Linux : ~/.local/bin/examgen, avec une entrée dans le menu des applications.
# Relancer la même commande met l'application à jour. Run it again to update.
# Une version précise / a given version:  ... | EXAMGEN_VERSION=v1.0.0 sh
set -eu

REPO="JoMeloche/exam_cegep_physique"
RAW="https://raw.githubusercontent.com/$REPO/main"
if [ -n "${EXAMGEN_VERSION:-}" ]; then API="https://api.github.com/repos/$REPO/releases/tags/$EXAMGEN_VERSION"
else API="https://api.github.com/repos/$REPO/releases/latest"; fi

say() { printf '%s\n' "$*"; }
die() { printf 'Erreur / Error: %s\n' "$*" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || die "curl est requis / curl is required"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM

# Download URL of the release file whose name matches the pattern (grep -E).
asset_url() {
  curl -fsSL -H "Accept: application/vnd.github+json" "$API" -o "$TMP/release.json" \
    || die "impossible de lire la version sur GitHub / cannot read the release from GitHub ($API)"
  grep -o '"browser_download_url": *"[^"]*"' "$TMP/release.json" | sed 's/.*: *"\([^"]*\)"$/\1/' \
    | grep -E "$1" | head -n 1
}

download() {  # url file
  say "Téléchargement / Downloading $(basename "$1") ..."
  curl -fL --progress-bar "$1" -o "$2" || die "échec du téléchargement / download failed"
}

install_macos() {
  case "$(uname -m)" in
    arm64) arch=arm64 ;;
    x86_64) arch=x86_64 ;;
    *) die "processeur non pris en charge / unsupported CPU: $(uname -m)" ;;
  esac
  url="$(asset_url "macos-$arch\\.dmg$")"
  [ -n "$url" ] || die "aucun .dmg pour $arch dans cette version / no $arch .dmg in this release"
  download "$url" "$TMP/ExamGen.dmg"
  mnt="$TMP/mnt"; mkdir -p "$mnt"
  hdiutil attach -nobrowse -quiet -mountpoint "$mnt" "$TMP/ExamGen.dmg"
  dest=/Applications
  [ -w "$dest" ] || { dest="$HOME/Applications"; mkdir -p "$dest"; }
  pkill -x ExamGen 2>/dev/null || true
  rm -rf "$dest/ExamGen.app"
  cp -R "$mnt/ExamGen.app" "$dest/"
  hdiutil detach -quiet "$mnt" || true
  xattr -dr com.apple.quarantine "$dest/ExamGen.app" 2>/dev/null || true
  say ""
  say "ExamGen est installé dans $dest. / ExamGen is installed in $dest."
  say "Ouvrez-le depuis le Launchpad ou avec : open \"$dest/ExamGen.app\""
}

install_linux() {
  [ "$(uname -m)" = "x86_64" ] || die "seul x86_64 est offert ; utilisez Docker (voir le README) / only x86_64 is available; use Docker"
  url="$(asset_url 'ExamGen-x86_64\.AppImage$')"
  [ -n "$url" ] || die "aucun AppImage dans cette version / no AppImage in this release"
  bin="$HOME/.local/bin"; share="$HOME/.local/share"
  mkdir -p "$bin" "$share/examgen" "$share/applications" "$share/icons/hicolor/256x256/apps"
  download "$url" "$TMP/ExamGen.AppImage"
  chmod +x "$TMP/ExamGen.AppImage"
  mv -f "$TMP/ExamGen.AppImage" "$share/examgen/ExamGen.AppImage"
  # Launcher: without FUSE (libfuse2), the AppImage still runs by extracting itself first.
  cat > "$bin/examgen" <<'EOF'
#!/bin/sh
if ! ldconfig -p 2>/dev/null | grep -q 'libfuse\.so\.2'; then export APPIMAGE_EXTRACT_AND_RUN=1; fi
exec "$HOME/.local/share/examgen/ExamGen.AppImage" "$@"
EOF
  chmod +x "$bin/examgen"
  curl -fsSL "$RAW/app/packaging/linux/examgen.png" -o "$share/icons/hicolor/256x256/apps/examgen.png" 2>/dev/null || true
  cat > "$share/applications/examgen.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ExamGen
Comment=Générateur d'examens / Exam generator
Exec=$bin/examgen
Icon=examgen
Terminal=false
Categories=Education;Office;
EOF
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$share/applications" 2>/dev/null || true
  say ""
  say "ExamGen est installé. Ouvrez-le depuis le menu des applications ou avec : examgen"
  say "ExamGen is installed. Open it from your applications menu or run: examgen"
  case ":$PATH:" in *":$bin:"*) ;; *) say "(Ajoutez $bin à votre PATH pour la commande examgen / add $bin to your PATH.)" ;; esac
}

case "$(uname -s)" in
  Darwin) install_macos ;;
  Linux) install_linux ;;
  *) die "système non pris en charge ; sous Windows, téléchargez ExamGen-Setup.exe / unsupported OS; on Windows, download ExamGen-Setup.exe" ;;
esac
