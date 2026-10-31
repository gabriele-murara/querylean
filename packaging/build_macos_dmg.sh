#!/usr/bin/env bash
# Genera dist/querylean-<versione>-<arch>.dmg (non firmato).
# Da eseguire su macOS: l'architettura del pacchetto è quella dell'interprete Python
# utilizzato (arm64 su Apple Silicon, x86_64 su Intel).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python}"
ARCH="$(uname -m)"
VERSION="$("$PYTHON" -c 'import querylean as m; print(m.__version__)')"
APP="dist/QueryLean.app"

"$PYTHON" -m PyInstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller \
    packaging/querylean.spec

# Firma ad-hoc: necessaria su Apple Silicon per avviare binari non firmati.
# Per la distribuzione usare un certificato Developer ID (vedi README).
codesign --force --deep --sign "${CODESIGN_IDENTITY:--}" "$APP"

STAGING="build/dmg"
rm -rf "$STAGING"
mkdir -p "$STAGING"
cp -R "$APP" "$STAGING/"
ln -s /Applications "$STAGING/Applications"

OUTPUT="dist/querylean-${VERSION}-${ARCH}.dmg"
rm -f "$OUTPUT"
hdiutil create -volname "QueryLean" -srcfolder "$STAGING" -ov -format UDZO "$OUTPUT"
echo "Creato $OUTPUT"
