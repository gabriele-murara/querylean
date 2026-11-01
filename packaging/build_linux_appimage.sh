#!/usr/bin/env bash
# Genera dist/querylean-<versione>-<arch>.AppImage.
# Requisiti: Python con le dipendenze di build (`pip install -e .[build]`),
# curl, file, desktop-file-utils, FUSE oppure APPIMAGE_EXTRACT_AND_RUN=1 per
# eseguire appimagetool. Per la massima compatibilità va eseguito sulla
# distribuzione più vecchia da supportare (Ubuntu 22.04). Le librerie xcb di
# Qt devono essere installate (vedi QT_XCB_PACKAGES in ci.yml).
set -euo pipefail

. "$(dirname "$0")/common.sh"

ARCH="$(uname -m)"
APPIMAGETOOL_VERSION="1.9.0"
APPIMAGETOOL="build/appimagetool-${ARCH}.AppImage"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download"
APPIMAGETOOL_URL+="/${APPIMAGETOOL_VERSION}/appimagetool-${ARCH}.AppImage"
# The AppImage runtime is downloaded here (curl follows GitHub redirects,
# appimagetool's own downloader does not always) and passed explicitly.
RUNTIME="build/runtime-${ARCH}"
RUNTIME_URL="https://github.com/AppImage/type2-runtime/releases/download"
RUNTIME_URL+="/continuous/runtime-${ARCH}"

querylean_pyinstaller

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

mkdir -p build
if [ ! -x "$APPIMAGETOOL" ]; then
    curl -fsSL -o "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
    chmod +x "$APPIMAGETOOL"
fi
if [ ! -s "$RUNTIME" ]; then
    curl -fsSL -o "$RUNTIME" "$RUNTIME_URL"
fi

OUTPUT="dist/querylean-${VERSION}-${ARCH}.AppImage"
ARCH="$ARCH" "$APPIMAGETOOL" --no-appstream --runtime-file "$RUNTIME" \
    "$APPDIR" "$OUTPUT"
echo "Creato $OUTPUT"
