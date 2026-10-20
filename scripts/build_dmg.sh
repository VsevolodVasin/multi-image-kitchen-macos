#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Prefer CLT when Xcode license is not accepted
if [[ -z "${DEVELOPER_DIR:-}" ]] && [[ -d /Library/Developer/CommandLineTools ]]; then
  if ! xcodebuild -license check &>/dev/null; then
    export DEVELOPER_DIR=/Library/Developer/CommandLineTools
  fi
fi

VERSION="${VERSION:-1.0.0}"
ARCH="$(uname -m)"
OUT="$ROOT/dist"
STAGE="$OUT/stage"
VENV="$ROOT/.venv"

[[ -x "$VENV/bin/python" ]] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q -r requirements.txt 'pyinstaller>=6.6'
export PYTHONPATH="$ROOT"

rm -rf "$OUT/MIK" "$OUT/MIK.app" "$STAGE" "$ROOT/build"
mkdir -p "$STAGE" "$OUT"

"$VENV/bin/pyinstaller" --noconfirm --clean \
  --name MIK --windowed \
  --icon "$ROOT/assets/mik.icns" \
  --osx-bundle-identifier com.vsevolodvasin.multi-image-kitchen \
  --add-binary "$ROOT/bin/aml_image_v2_packer:bin" \
  --add-data "$ROOT/assets:assets" \
  --add-data "$ROOT/LICENSE:." \
  --add-data "$ROOT/THIRD_PARTY.md:." \
  --add-data "$ROOT/NOTICE:." \
  --paths "$ROOT" \
  "$ROOT/scripts/run.py"

PLIST="$OUT/MIK.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :NSHumanReadableCopyright Copyright (c) 2026" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Add :NSHumanReadableCopyright string Copyright (c) 2026" "$PLIST"

cp -R "$OUT/MIK.app" "$STAGE/"
cp "$ROOT/LICENSE" "$ROOT/THIRD_PARTY.md" "$ROOT/NOTICE" "$ROOT/README.md" "$STAGE/"
printf 'Multi Image Kitchen %s\nRequires: brew install e2fsprogs\n' "$VERSION" > "$STAGE/Dependencies.txt"

DMG="MIK-${VERSION}-macos-${ARCH}.dmg"
rm -f "$OUT/$DMG"
if command -v create-dmg >/dev/null; then
  create-dmg --volname "MIK $VERSION" --app-drop-link 480 200 "$OUT/$DMG" "$STAGE"
else
  hdiutil create -volname "MIK $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$OUT/$DMG"
fi
echo "OK: $OUT/$DMG"
