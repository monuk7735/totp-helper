#!/usr/bin/env python3
"""
TOTP Helper utility.

What it does:
1. Enrolls an authenticator secret from a QR image (otpauth URI).
2. Generates the current OTP on demand.
3. Listens for a global keyboard shortcut and types OTP into the active window.

macOS notes:
- Global hotkeys and keyboard typing require Accessibility/Input Monitoring permissions
  for your terminal app (Terminal, iTerm, VS Code, etc.).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

import pyautogui
import pyotp
from pynput import keyboard


CONFIG_DIR = pathlib.Path.home() / ".com.monuk7735.totp.helper"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _decode_qr_from_image(image_path: pathlib.Path) -> str:
    """Decode QR content with macOS's built-in `zbarimg` if available."""
    import subprocess

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    command = ["zbarimg", "--quiet", "--raw", str(image_path)]
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "zbarimg is not installed. Install with: brew install zbar"
        ) from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or "Unable to decode QR image."
        raise RuntimeError(message) from exc

    payload = result.stdout.strip()
    if not payload:
        raise RuntimeError("QR image decoded to empty content.")
    return payload


def _extract_secret_from_otpauth(otpauth_uri: str) -> dict:
    parsed = urlparse(otpauth_uri)
    if parsed.scheme != "otpauth":
        raise ValueError("QR content is not an otpauth URI.")

    if parsed.netloc.lower() != "totp":
        raise ValueError("Only TOTP otpauth URIs are supported.")

    label = unquote(parsed.path.lstrip("/"))
    query = parse_qs(parsed.query)

    secret_values = query.get("secret")
    if not secret_values:
        raise ValueError("otpauth URI does not include a secret parameter.")

    secret = secret_values[0].strip().replace(" ", "")
    if not re.fullmatch(r"[A-Z2-7]+=*", secret, re.IGNORECASE):
        raise ValueError("Invalid TOTP secret format in otpauth URI.")

    issuer = query.get("issuer", [""])[0]
    digits = int(query.get("digits", ["6"])[0])
    interval = int(query.get("period", ["30"])[0])
    algorithm = query.get("algorithm", ["SHA1"])[0].upper()

    if digits not in (6, 7, 8):
        raise ValueError("Unsupported OTP digits in otpauth URI.")
    if interval <= 0:
        raise ValueError("Invalid OTP period in otpauth URI.")
    if algorithm not in ("SHA1", "SHA256", "SHA512"):
        raise ValueError("Unsupported algorithm in otpauth URI.")

    return {
        "label": label,
        "issuer": issuer,
        "secret": secret,
        "digits": digits,
        "interval": interval,
        "algorithm": algorithm,
    }


def _save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Config not found at {CONFIG_FILE}. Run enroll first."
        )
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def _build_totp(config: dict) -> pyotp.TOTP:
    digest = {
        "SHA1": "sha1",
        "SHA256": "sha256",
        "SHA512": "sha512",
    }[config["algorithm"]]

    # pyotp accepts digest function from hashlib by name lookup.
    import hashlib

    digest_fn = getattr(hashlib, digest)
    return pyotp.TOTP(
        s=config["secret"],
        digits=config["digits"],
        digest=digest_fn,
        interval=config["interval"],
    )


def command_enroll(args: argparse.Namespace) -> int:
    image_path = pathlib.Path(args.image).expanduser().resolve()

    qr_payload = _decode_qr_from_image(image_path)
    config = _extract_secret_from_otpauth(qr_payload)
    _save_config(config)

    print("Enrolled authenticator successfully.")
    print(f"Stored config: {CONFIG_FILE}")
    if config["issuer"] or config["label"]:
        print(f"Account: {config['issuer']} {config['label']}")
    return 0


def command_code(_: argparse.Namespace) -> int:
    config = _load_config()
    totp = _build_totp(config)
    print(totp.now())
    return 0


@dataclass
class HotkeyState:
    pressed: set
    pending_trigger: bool
    lock: threading.Lock


def _normalize_key_name(raw: str) -> str:
    value = raw.strip().lower()
    aliases = {
        "cmd": "command",
        "control": "ctrl",
        "option": "alt",
        "return": "enter",
    }
    return aliases.get(value, value)


def _key_to_name(key: keyboard.Key | keyboard.KeyCode) -> Optional[str]:
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
        return None

    mapping = {
        keyboard.Key.ctrl: "ctrl",
        keyboard.Key.ctrl_l: "ctrl",
        keyboard.Key.ctrl_r: "ctrl",
        keyboard.Key.cmd: "command",
        keyboard.Key.cmd_l: "command",
        keyboard.Key.cmd_r: "command",
        keyboard.Key.alt: "alt",
        keyboard.Key.alt_l: "alt",
        keyboard.Key.alt_r: "alt",
        keyboard.Key.shift: "shift",
        keyboard.Key.shift_l: "shift",
        keyboard.Key.shift_r: "shift",
        keyboard.Key.enter: "enter",
        keyboard.Key.space: "space",
        keyboard.Key.tab: "tab",
        keyboard.Key.esc: "esc",
    }
    return mapping.get(key)


def _parse_hotkey_combo(combo: str) -> set[str]:
    parts = [segment for segment in combo.split("+") if segment.strip()]
    if not parts:
        raise ValueError("Hotkey cannot be empty.")

    normalized = {_normalize_key_name(part) for part in parts}
    return normalized


def _copy_to_clipboard(text: str) -> None:
    subprocess.run(["pbcopy"], input=text, text=True, check=True)


def _type_via_applescript(text: str) -> None:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    script = f'tell application "System Events" to keystroke "{escaped}"'
    subprocess.run(["osascript", "-e", script], check=True)


def _inject_otp(otp: str, method: str, press_enter: bool) -> None:
    if method == "pyautogui":
        pyautogui.write(otp, interval=0.02)
    elif method == "applescript":
        _type_via_applescript(otp)
    else:
        raise ValueError(f"Unsupported typing method: {method}")

    if press_enter:
        if method == "pyautogui":
            pyautogui.press("enter")
        else:
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to key code 36',
                ],
                check=True,
            )


def command_listen(args: argparse.Namespace) -> int:
    config = _load_config()
    totp = _build_totp(config)

    hotkey = _parse_hotkey_combo(args.hotkey)
    state = HotkeyState(pressed=set(), pending_trigger=False, lock=threading.Lock())
    modifier_keys = {"command", "shift", "ctrl", "alt"}

    print("Listening for hotkey. Press Ctrl+C to stop.")
    print(f"Hotkey: {args.hotkey}")
    print(f"Method: {args.method}")

    def trigger_type_otp() -> None:
        otp = totp.now()
        try:
            if args.copy:
                _copy_to_clipboard(otp)
            if args.delay > 0:
                time.sleep(args.delay)
            _inject_otp(otp, method=args.method, press_enter=args.press_enter)
            print("OTP injected.")
        except Exception as exc:
            print(f"OTP injection failed: {exc}")

    def on_press(key: keyboard.Key | keyboard.KeyCode) -> None:
        name = _key_to_name(key)
        if not name:
            return
        with state.lock:
            state.pressed.add(name)
            if hotkey.issubset(state.pressed):
                # Trigger on release so modifier keys are not held during typing.
                state.pending_trigger = True

    def on_release(key: keyboard.Key | keyboard.KeyCode) -> None:
        name = _key_to_name(key)
        if not name:
            return
        should_trigger = False
        with state.lock:
            state.pressed.discard(name)
            if state.pending_trigger and not (state.pressed & modifier_keys):
                state.pending_trigger = False
                should_trigger = True

        if should_trigger:
            trigger_type_otp()

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TOTP Helper")
    sub = parser.add_subparsers(dest="command", required=True)

    enroll = sub.add_parser("enroll", help="Enroll TOTP from QR image")
    enroll.add_argument(
        "--image",
        required=True,
        help="Path to QR image (e.g. ~/Downloads/wr.png)",
    )
    enroll.set_defaults(func=command_enroll)

    code = sub.add_parser("code", help="Print current OTP")
    code.set_defaults(func=command_code)

    listen = sub.add_parser("listen", help="Listen for hotkey and type OTP")
    listen.add_argument(
        "--hotkey",
        default="command+control+shift+v",
        help=(
            "Global shortcut to trigger OTP typing "
            "(default: command+control+shift+v)"
        ),
    )
    listen.add_argument(
        "--copy",
        action="store_true",
        help="Also copy OTP to clipboard before typing",
    )
    listen.add_argument(
        "--method",
        choices=["pyautogui", "applescript"],
        default="applescript",
        help=(
            "OTP typing method: applescript (default) or pyautogui"
        ),
    )
    listen.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds to wait after hotkey before injecting OTP",
    )
    listen.add_argument(
        "--press-enter",
        action="store_true",
        help="Press Enter after typing the OTP",
    )
    listen.set_defaults(func=command_listen)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("Stopped.")
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
