# TOTP Helper

This tool helps automate TOTP entry for login forms.

## What It Does

1. Reads an authenticator QR image (`otpauth://...`) from disk.
2. Stores the TOTP config locally in `~/.com.monuk7735.totp.helper/config.json`.
3. Listens for a global hotkey and types the current OTP into the active input field.

## Prerequisites (macOS)

- Python 3.10+
- Homebrew package for QR decoding:

```bash
brew install zbar
```

- Accessibility permissions for your terminal app:
  - System Settings -> Privacy & Security -> Accessibility
  - Enable Terminal/iTerm/VS Code
  - Also enable the same app in Input Monitoring
  - After enabling permissions, fully quit and reopen the terminal app

## Setup

```bash
pipenv install
```

## 1) Enroll Authenticator from QR Image

Put your authenticator QR image in a known path, then run:

```bash
pipenv run python totp_helper.py enroll --image ~/Downloads/wr.png
```

If successful, it stores the parsed secret in:

`~/.com.monuk7735.totp.helper/config.json`

## 2) Test OTP Generation

```bash
pipenv run python totp_helper.py code
```

## 3) Start Hotkey Listener

Default hotkey is `Command+Control+Shift+V`:

```bash
pipenv run python totp_helper.py listen --hotkey command+control+shift+v --method applescript --press-enter
```

Then:

1. Focus your OTP field.
2. Press the hotkey.
3. Script types your current OTP.

## Optional Flags

- `--copy` copies OTP to clipboard before typing.
- `--method` chooses typing mode: `applescript` (default) or `pyautogui`.
- `--delay 0.5` waits before typing, useful if app focus changes.
- `--press-enter` presses Enter after typing OTP.

## Notes

- Keep `~/.com.monuk7735.totp.helper/config.json` private.
- If your authenticator source rotates to a new QR secret, run `enroll` again.

## Run In Background (No Terminal Window)

Use the included `launchd` helper scripts.

Install and start background listener:

```bash
./scripts/install-totp-helper-launchagent.sh
```

Stop and remove background listener:

```bash
./scripts/uninstall-totp-helper-launchagent.sh
```

Check status:

```bash
launchctl print gui/$(id -u)/"TOTP Helper"
```

View logs:

```bash
tail -f ~/.com.monuk7735.totp.helper/launchagent.out.log ~/.com.monuk7735.totp.helper/launchagent.err.log
```

If you want a different hotkey or method, edit:

- `scripts/totp-helper-runner.sh`

When you run `./scripts/install-totp-helper-launchagent.sh`, it copies the runtime files to:

- `~/.com.monuk7735.totp.helper/runtime/com.monuk7735.totp.helper`
- `~/.com.monuk7735.totp.helper/runtime/totp_helper.py`

So after any script changes, run install again to redeploy runtime files.

## Troubleshooting (macOS)

If logs show "This process is not trusted" and nothing is typed:

1. Add your terminal app (Terminal/iTerm/VS Code) to both Accessibility and Input Monitoring.
2. Restart the terminal app completely.
3. Try applescript typing first:

```bash
pipenv run python totp_helper.py listen --hotkey command+control+shift+v --method applescript --press-enter
```

4. If your target app blocks synthetic typing for secure fields, use:

```bash
pipenv run python totp_helper.py code
```

and type manually.
