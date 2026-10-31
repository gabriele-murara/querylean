# Shared helpers for the build scripts. Source it, do not execute it:
#   . "$(dirname "$0")/common.sh"
# After sourcing, the current directory is the project root and the variables
# ROOT, PYTHON and VERSION are set.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python}"

# The version is read only from the .version file (never modify it here).
if [ ! -f .version ]; then
    echo "File .version mancante" >&2
    exit 1
fi
VERSION="$(tr -d '[:space:]' < .version)"
if [ -z "$VERSION" ]; then
    echo "File .version vuoto" >&2
    exit 1
fi

# Build the PyInstaller onedir bundle into dist/querylean (dist/QueryLean.app
# on macOS).
querylean_pyinstaller() {
    "$PYTHON" -m PyInstaller --noconfirm --clean \
        --distpath dist --workpath build/pyinstaller \
        packaging/querylean.spec
}
