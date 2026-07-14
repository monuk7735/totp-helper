#!/usr/bin/env bash
set -euo pipefail

LABEL="TOTP Helper"
IDENTIFIER="com.monuk7735.totp.helper"
PLIST_PATH="$HOME/Library/LaunchAgents/${IDENTIFIER}.plist"

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl disable "gui/$(id -u)/${LABEL}" 2>/dev/null || true
rm -f "$PLIST_PATH"

echo "Uninstalled: ${LABEL}"
