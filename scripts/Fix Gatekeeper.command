#!/bin/bash
cd "$(dirname "$0")" || exit 1
APP="MIK.app"
XATTR=/usr/bin/xattr

if [[ ! -d "$APP" ]]; then
  osascript -e 'display dialog "MIK.app not found next to this script." buttons {"OK"} default button 1 with icon stop'
  exit 1
fi

"$XATTR" -cr "$APP" 2>/dev/null || {
  find "$APP" \( -type f -o -type d \) -exec "$XATTR" -d com.apple.quarantine {} \; 2>/dev/null || true
  "$XATTR" -c "$APP" 2>/dev/null || true
}

osascript -e 'display dialog "Gatekeeper quarantine removed from MIK.app.\nDrag it to Applications and open." buttons {"OK"} default button 1 with icon note'
