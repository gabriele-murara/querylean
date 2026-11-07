#!/usr/bin/env bash
# Builds dist/querylean-<version>-<arch>.dmg (ad-hoc signed, not notarized).
# Run it on macOS: the package architecture is the one of the Python
# interpreter used (arm64 on Apple Silicon, x86_64 on Intel).
# Requirements: Python with the build dependencies (`pip install -e .[build]`);
# codesign and hdiutil come with macOS.
set -euo pipefail

. "$(dirname "$0")/common.sh"

ARCH="$(uname -m)"
APP="dist/QueryLean.app"

querylean_pyinstaller

# Ad-hoc signature: needed on Apple Silicon to start unsigned binaries.
# To distribute, use a Developer ID certificate (see README) with
# CODESIGN_IDENTITY="Developer ID Application: ...".
codesign --force --deep --sign "${CODESIGN_IDENTITY:--}" "$APP"
codesign --verify --deep --strict "$APP"

STAGING="build/dmg"
rm -rf "$STAGING"
mkdir -p "$STAGING"
cp -R "$APP" "$STAGING/"
ln -s /Applications "$STAGING/Applications"
# License of QueryLean and notices of the bundled third-party components,
# visible next to the application in the disk image.
NOTICES="$(find "$APP" -name THIRD_PARTY_LICENSES.txt -type f | head -n 1)"
if [ -z "$NOTICES" ]; then
    echo "Third-party licenses missing from $APP" >&2
    exit 1
fi
cp LICENSE "$STAGING/LICENSE.txt"
cp "$NOTICES" "$STAGING/THIRD_PARTY_LICENSES.txt"

OUTPUT="dist/querylean-${VERSION}-${ARCH}.dmg"
rm -f "$OUTPUT"
hdiutil create -volname "QueryLean" -srcfolder "$STAGING" -ov -format UDZO \
    "$OUTPUT"
echo "Created $OUTPUT"
