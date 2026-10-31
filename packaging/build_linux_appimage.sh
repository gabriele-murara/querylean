#!/usr/bin/env bash
# Genera dist/querylean-<versione>-x86_64.AppImage.
# Requisiti: Python con le dipendenze di build (`pip install -e .[build]`),
# curl, file, FUSE oppure APPIMAGE_EXTRACT_AND_RUN=1 per eseguire
# appimagetool.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python}"
ARCH="$(uname -m)"
# The version is read only from the .version file.
VERSION="$(tr -d '[:space:]' < .version)"
if [ -z "$VERSION" ]; then
    echo "File .version mancante o vuoto" >&2
    exit 1
fi
APPIMAGETOOL_VERSION="1.9.0"
APPIMAGETOOL="build/appimagetool-${ARCH}.AppImage"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download"
APPIMAGETOOL_URL+="/${APPIMAGETOOL_VERSION}/appimagetool-${ARCH}.AppImage"

"$PYTHON" -m PyInstaller --noconfirm --clean \
    --distpath dist --workpath build/pyinstaller \
    packaging/querylean.spec

APPDIR="build/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/scalable/apps"
cp -a dist/querylean "$APPDIR/usr/lib/querylean"
cp packaging/AppRun "$APPDIR/AppRun"
cp packaging/querylean.desktop "$APPDIR/"
cp packaging/querylean.desktop "$APPDIR/usr/share/applications/"
cp packaging/querylean.svg "$APPDIR/"
cp packaging/querylean.svg "$APPDIR/usr/share/icons/hicolor/scalable/apps/"

if [ ! -x "$APPIMAGETOOL" ]; then
    mkdir -p build
    curl -fsSL -o "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
    chmod +x "$APPIMAGETOOL"
fi

OUTPUT="dist/querylean-${VERSION}-${ARCH}.AppImage"
ARCH="$ARCH" "$APPIMAGETOOL" --no-appstream "$APPDIR" "$OUTPUT"
echo "Creato $OUTPUT"
