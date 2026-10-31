#!/usr/bin/env bash
# Genera dist/querylean-<versione>-<arch>.dmg (firma ad-hoc, non notarizzato).
# Da eseguire su macOS: l'architettura del pacchetto è quella dell'interprete
# Python utilizzato (arm64 su Apple Silicon, x86_64 su Intel).
# Requisiti: Python con le dipendenze di build (`pip install -e .[build]`);
# codesign e hdiutil sono inclusi in macOS.
set -euo pipefail

. "$(dirname "$0")/common.sh"

ARCH="$(uname -m)"
APP="dist/QueryLean.app"

querylean_pyinstaller

# Firma ad-hoc: necessaria su Apple Silicon per avviare binari non firmati.
# Per la distribuzione usare un certificato Developer ID (vedi README) con
# CODESIGN_IDENTITY="Developer ID Application: ...".
codesign --force --deep --sign "${CODESIGN_IDENTITY:--}" "$APP"
codesign --verify --deep --strict "$APP"

STAGING="build/dmg"
rm -rf "$STAGING"
mkdir -p "$STAGING"
cp -R "$APP" "$STAGING/"
ln -s /Applications "$STAGING/Applications"

OUTPUT="dist/querylean-${VERSION}-${ARCH}.dmg"
rm -f "$OUTPUT"
hdiutil create -volname "QueryLean" -srcfolder "$STAGING" -ov -format UDZO \
    "$OUTPUT"
echo "Creato $OUTPUT"
