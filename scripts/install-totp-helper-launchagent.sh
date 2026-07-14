#!/usr/bin/env bash
set -euo pipefail

LABEL="TOTP Helper"
IDENTIFIER="com.monuk7735.totp.helper"
PLIST_PATH="$HOME/Library/LaunchAgents/${IDENTIFIER}.plist"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE_DIR="$HOME/.${IDENTIFIER}"
RUNTIME_DIR="${BASE_DIR}/runtime"
RUNNER_PATH="${RUNTIME_DIR}/${IDENTIFIER}"
APP_PATH="${RUNTIME_DIR}/totp_helper.py"
VENV_PATH="$(cd "${PROJECT_DIR}" && pipenv --venv)"
PYTHON_PATH="${VENV_PATH}/bin/python"
LOG_DIR="${BASE_DIR}"
STDOUT_LOG="${LOG_DIR}/launchagent.out.log"
STDERR_LOG="${LOG_DIR}/launchagent.err.log"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$LOG_DIR"
mkdir -p "$RUNTIME_DIR"

cp -f "${PROJECT_DIR}/totp_helper.py" "$APP_PATH"

cat > "$RUNNER_PATH" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "${PYTHON_PATH}" "${APP_PATH}" listen --hotkey command+control+shift+v --method applescript --press-enter
EOF

chmod +x "$RUNNER_PATH"
xattr -d com.apple.provenance "$RUNNER_PATH" 2>/dev/null || true
xattr -d com.apple.macl "$RUNNER_PATH" 2>/dev/null || true

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>${RUNNER_PATH}</string>
  </array>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>${STDOUT_LOG}</string>

  <key>StandardErrorPath</key>
  <string>${STDERR_LOG}</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl enable "gui/$(id -u)/${LABEL}"
launchctl kickstart -k "gui/$(id -u)/${LABEL}"

echo "Installed and started: ${LABEL}"
echo "Plist: ${PLIST_PATH}"
echo "Runner: ${RUNNER_PATH}"
echo "Stdout log: ${STDOUT_LOG}"
echo "Stderr log: ${STDERR_LOG}"
