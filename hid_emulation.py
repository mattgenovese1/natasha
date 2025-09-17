#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Natasha AI Penetration Testing Tool
HID Emulation Module

This module implements the USB HID (Human Interface Device) emulation functionality,
allowing the Raspberry Pi Zero 2 W to act as a keyboard device for executing
DuckyScript payloads on target systems.

Improvements:
- Persistent HID device handle with guarded writes and retries
- Configurable inter-report delay and default per-character delay
- Extended DuckyScript support: DEFAULTDELAY/DEFAULT_DELAY, DEFAULTCHARDELAY, REPEAT, hyphenated combos (e.g., ALT-F4), KEYDOWN/KEYUP
- Safe key mapping for single-letter tokens in combos (avoid unintended Shift)
- Optional external keymap override from ~/.natasha/keymap.json
- Non-intrusive OS detection (no keystrokes)
- Additional debug logging for parsing and actions
"""

import os
import time
import json
import random
import logging
import threading
from typing import Dict, List, Optional, Union, Tuple
from enum import Enum


class KeyCode(Enum):
    """USB HID keyboard scan codes for common keys."""
    # Modifier keys
    MOD_NONE = 0x00
    MOD_LCTRL = 0x01
    MOD_LSHIFT = 0x02
    MOD_LALT = 0x04
    MOD_LMETA = 0x08  # Left Windows/Command key
    MOD_RCTRL = 0x10
    MOD_RSHIFT = 0x20
    MOD_RALT = 0x40
    MOD_RMETA = 0x80  # Right Windows/Command key

    # Standard keys
    KEY_NONE = 0x00
    KEY_A = 0x04
    KEY_B = 0x05
    KEY_C = 0x06
    KEY_D = 0x07
    KEY_E = 0x08
    KEY_F = 0x09
    KEY_G = 0x0A
    KEY_H = 0x0B
    KEY_I = 0x0C
    KEY_J = 0x0D
    KEY_K = 0x0E
    KEY_L = 0x0F
    KEY_M = 0x10
    KEY_N = 0x11
    KEY_O = 0x12
    KEY_P = 0x13
    KEY_Q = 0x14
    KEY_R = 0x15
    KEY_S = 0x16
    KEY_T = 0x17
    KEY_U = 0x18
    KEY_V = 0x19
    KEY_W = 0x1A
    KEY_X = 0x1B
    KEY_Y = 0x1C
    KEY_Z = 0x1D
    KEY_1 = 0x1E
    KEY_2 = 0x1F
    KEY_3 = 0x20
    KEY_4 = 0x21
    KEY_5 = 0x22
    KEY_6 = 0x23
    KEY_7 = 0x24
    KEY_8 = 0x25
    KEY_9 = 0x26
    KEY_0 = 0x27
    KEY_ENTER = 0x28
    KEY_ESC = 0x29
    KEY_BACKSPACE = 0x2A
    KEY_TAB = 0x2B
    KEY_SPACE = 0x2C
    KEY_MINUS = 0x2D
    KEY_EQUAL = 0x2E
    KEY_LEFTBRACE = 0x2F
    KEY_RIGHTBRACE = 0x30
    KEY_BACKSLASH = 0x31
    KEY_SEMICOLON = 0x33
    KEY_APOSTROPHE = 0x34
    KEY_GRAVE = 0x35
    KEY_COMMA = 0x36
    KEY_DOT = 0x37
    KEY_SLASH = 0x38
    KEY_CAPSLOCK = 0x39
    KEY_F1 = 0x3A
    KEY_F2 = 0x3B
    KEY_F3 = 0x3C
    KEY_F4 = 0x3D
    KEY_F5 = 0x3E
    KEY_F6 = 0x3F
    KEY_F7 = 0x40
    KEY_F8 = 0x41
    KEY_F9 = 0x42
    KEY_F10 = 0x43
    KEY_F11 = 0x44
    KEY_F12 = 0x45
    KEY_SYSRQ = 0x46
    KEY_SCROLLLOCK = 0x47
    KEY_PAUSE = 0x48
    KEY_INSERT = 0x49
    KEY_HOME = 0x4A
    KEY_PAGEUP = 0x4B
    KEY_DELETE = 0x4C
    KEY_END = 0x4D
    KEY_PAGEDOWN = 0x4E
    KEY_RIGHT = 0x4F
    KEY_LEFT = 0x50
    KEY_DOWN = 0x51
    KEY_UP = 0x52
    KEY_NUMLOCK = 0x53
    KEY_KPSLASH = 0x54
    KEY_KPASTERISK = 0x55
    KEY_KPMINUS = 0x56
    KEY_KPPLUS = 0x57
    KEY_KPENTER = 0x58
    KEY_KP1 = 0x59
    KEY_KP2 = 0x5A
    KEY_KP3 = 0x5B
    KEY_KP4 = 0x5C
    KEY_KP5 = 0x5D
    KEY_KP6 = 0x5E
    KEY_KP7 = 0x5F
    KEY_KP8 = 0x60
    KEY_KP9 = 0x61
    KEY_KP0 = 0x62
    KEY_KPDOT = 0x63
    KEY_COMPOSE = 0x65
    KEY_POWER = 0x66
    KEY_KPEQUAL = 0x67
    KEY_F13 = 0x68
    KEY_F14 = 0x69
    KEY_F15 = 0x6A
    KEY_F16 = 0x6B
    KEY_F17 = 0x6C
    KEY_F18 = 0x6D
    KEY_F19 = 0x6E
    KEY_F20 = 0x6F
    KEY_F21 = 0x70
    KEY_F22 = 0x71
    KEY_F23 = 0x72
    KEY_F24 = 0x73


class HIDEmulator:
    """USB HID Emulator for keyboard emulation."""

    # HID report structure: [modifier, reserved, Key1, Key2, Key3, Key4, Key5, Key6]
    REPORT_LENGTH = 8

    def __init__(
        self,
        hid_device_path: str = "/dev/hidg0",
        inter_report_delay: float = 0.015,
        default_char_delay: float = 0.015,
        keymap_path: Optional[str] = None,
    ):
        """Initialize the HID Emulator.

        Args:
            hid_device_path: Path to the USB HID gadget device
            inter_report_delay: Sleep (s) after each HID report to improve reliability
            default_char_delay: Default delay (s) between characters when typing strings
            keymap_path: Optional path to JSON keymap overrides
        """
        self.hid_device_path = hid_device_path
        self.device: Optional[object] = None
        self.lock = threading.RLock()
        self.key_state = bytearray(self.REPORT_LENGTH)
        self.inter_report_delay = max(0.0, inter_report_delay)
        self.default_char_delay = max(0.0, default_char_delay)
        self.default_command_delay_ms = 0  # set via DEFAULTDELAY/DEFAULT_DELAY
        self.last_executable_command: Optional[str] = None

        self.char_to_key = self._build_char_map(keymap_path)
        self.duckyscript_commands = self._build_duckyscript_commands()

        # Check and open HID device
        self._check_and_open_hid_device()

    # ----------------------- Device management -----------------------
    def _check_and_open_hid_device(self) -> None:
        """Ensure HID device exists and open a persistent handle."""
        if not os.path.exists(self.hid_device_path):
            logging.error(f"HID device not found: {self.hid_device_path}")
            logging.info("USB HID gadget may not be configured. Run setup_usb_hid.sh first.")
            raise FileNotFoundError(f"HID device not found: {self.hid_device_path}")
        self._open_device()

    def _open_device(self) -> None:
        """Open the HID device and store the handle."""
        try:
            # buffering=0 may not be supported on all systems; rely on flush
            self.device = open(self.hid_device_path, 'wb')
            logging.info(f"HID device ready: {self.hid_device_path}")
        except Exception as e:
            logging.error(f"Failed to access HID device: {e}")
            self.device = None
            raise

    def _reopen_device(self) -> None:
        """Attempt to reopen the HID device after an error."""
        try:
            if self.device:
                try:
                    self.device.close()
                except Exception:
                    pass
            self.device = None
            time.sleep(0.05)
            self._open_device()
        except Exception as e:
            logging.error(f"Failed to reopen HID device: {e}")
            raise

    # ----------------------- Key mapping -----------------------
    def _build_char_map(self, keymap_path: Optional[str]) -> Dict[str, Tuple[int, int]]:
        """Build a mapping from characters to (modifier, keycode) pairs.

        Returns:
            Dictionary mapping characters to (modifier, keycode) pairs
        """
        char_map: Dict[str, Tuple[int, int]] = {}

        # Lowercase letters
        for c in "abcdefghijklmnopqrstuvwxyz":
            keycode = getattr(KeyCode, f"KEY_{c.upper()}").value
            char_map[c] = (KeyCode.MOD_NONE.value, keycode)

        # Uppercase letters (shifted)
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            keycode = getattr(KeyCode, f"KEY_{c}").value
            char_map[c] = (KeyCode.MOD_LSHIFT.value, keycode)

        # Numbers
        for c in "1234567890":
            keycode = getattr(KeyCode, f"KEY_{c}").value
            char_map[c] = (KeyCode.MOD_NONE.value, keycode)

        # Special characters (unshifted)
        char_map[' '] = (KeyCode.MOD_NONE.value, KeyCode.KEY_SPACE.value)
        char_map['-'] = (KeyCode.MOD_NONE.value, KeyCode.KEY_MINUS.value)
        char_map['='] = (KeyCode.MOD_NONE.value, KeyCode.KEY_EQUAL.value)
        char_map['['] = (KeyCode.MOD_NONE.value, KeyCode.KEY_LEFTBRACE.value)
        char_map[']'] = (KeyCode.MOD_NONE.value, KeyCode.KEY_RIGHTBRACE.value)
        char_map['\\'] = (KeyCode.MOD_NONE.value, KeyCode.KEY_BACKSLASH.value)
        char_map[';'] = (KeyCode.MOD_NONE.value, KeyCode.KEY_SEMICOLON.value)
        char_map["'"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_APOSTROPHE.value)
        char_map['`'] = (KeyCode.MOD_NONE.value, KeyCode.KEY_GRAVE.value)
        char_map[','] = (KeyCode.MOD_NONE.value, KeyCode.KEY_COMMA.value)
        char_map['.'] = (KeyCode.MOD_NONE.value, KeyCode.KEY_DOT.value)
        char_map['/'] = (KeyCode.MOD_NONE.value, KeyCode.KEY_SLASH.value)

        # Special characters (shifted)
        char_map['!'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_1.value)
        char_map['@'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_2.value)
        char_map['#'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_3.value)
        char_map['$'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_4.value)
        char_map['%'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_5.value)
        char_map['^'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_6.value)
        char_map['&'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_7.value)
        char_map['*'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_8.value)
        char_map['('] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_9.value)
        char_map[')'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_0.value)
        char_map['_'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_MINUS.value)
        char_map['+'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_EQUAL.value)
        char_map['{'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_LEFTBRACE.value)
        char_map['}'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_RIGHTBRACE.value)
        char_map['|'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_BACKSLASH.value)
        char_map[':'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_SEMICOLON.value)
        char_map['"'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_APOSTROPHE.value)
        char_map['~'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_GRAVE.value)
        char_map['<'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_COMMA.value)
        char_map['>'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_DOT.value)
        char_map['?'] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_SLASH.value)

        # Optional external keymap overrides
        try:
            override_path = keymap_path or os.path.join(os.path.expanduser("~"), "natasha", "keymap.json")
            if os.path.exists(override_path):
                with open(override_path, 'r') as f:
                    data = json.load(f)
                # Expected format: {"char": {"modifier": int, "keycode": int}}
                for ch, mk in data.items():
                    if isinstance(mk, dict) and "modifier" in mk and "keycode" in mk:
                        char_map[ch] = (int(mk["modifier"]), int(mk["keycode"]))
                logging.info(f"Loaded keymap overrides from {override_path}")
        except Exception as e:
            logging.warning(f"Failed to load keymap overrides: {e}")

        return char_map

    def _build_duckyscript_commands(self) -> Dict[str, Tuple[int, int]]:
        """Build a mapping from DuckyScript commands to (modifier, keycode) pairs."""
        commands: Dict[str, Tuple[int, int]] = {}
        # Modifiers
        commands["CTRL"] = (KeyCode.MOD_LCTRL.value, KeyCode.KEY_NONE.value)
        commands["CONTROL"] = (KeyCode.MOD_LCTRL.value, KeyCode.KEY_NONE.value)
        commands["SHIFT"] = (KeyCode.MOD_LSHIFT.value, KeyCode.KEY_NONE.value)
        commands["ALT"] = (KeyCode.MOD_LALT.value, KeyCode.KEY_NONE.value)
        commands["GUI"] = (KeyCode.MOD_LMETA.value, KeyCode.KEY_NONE.value)
        commands["WINDOWS"] = (KeyCode.MOD_LMETA.value, KeyCode.KEY_NONE.value)
        # Special keys
        commands["ENTER"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_ENTER.value)
        commands["ESCAPE"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_ESC.value)
        commands["ESC"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_ESC.value)
        commands["BACKSPACE"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_BACKSPACE.value)
        commands["TAB"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_TAB.value)
        commands["SPACE"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_SPACE.value)
        commands["CAPSLOCK"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_CAPSLOCK.value)
        commands["PRINTSCREEN"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_SYSRQ.value)
        commands["SCROLLLOCK"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_SCROLLLOCK.value)
        commands["PAUSE"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_PAUSE.value)
        commands["BREAK"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_PAUSE.value)
        commands["INSERT"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_INSERT.value)
        commands["HOME"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_HOME.value)
        commands["PAGEUP"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_PAGEUP.value)
        commands["DELETE"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_DELETE.value)
        commands["DEL"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_DELETE.value)
        commands["END"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_END.value)
        commands["PAGEDOWN"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_PAGEDOWN.value)
        commands["RIGHT"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_RIGHT.value)
        commands["RIGHTARROW"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_RIGHT.value)
        commands["LEFT"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_LEFT.value)
        commands["LEFTARROW"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_LEFT.value)
        commands["DOWN"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_DOWN.value)
        commands["DOWNARROW"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_DOWN.value)
        commands["UP"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_UP.value)
        commands["UPARROW"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_UP.value)
        commands["NUMLOCK"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_NUMLOCK.value)
        commands["MENU"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_COMPOSE.value)
        commands["APP"] = (KeyCode.MOD_NONE.value, KeyCode.KEY_COMPOSE.value)
        # Function keys
        for i in range(1, 25):
            commands[f"F{i}"] = (KeyCode.MOD_NONE.value, getattr(KeyCode, f"KEY_F{i}").value)
        return commands

    # ----------------------- Low-level send -----------------------
    def _send_report(self, report: bytearray) -> None:
        """Send a HID report with retries.

        Args:
            report: HID report to send
        """
        if not self.device:
            self._reopen_device()
        last_exc: Optional[Exception] = None
        for attempt in range(2):
            try:
                assert self.device is not None
                self.device.write(report)
                self.device.flush()
                if self.inter_report_delay > 0:
                    time.sleep(self.inter_report_delay)
                return
            except Exception as e:
                logging.warning(f"HID write failed (attempt {attempt+1}): {e}")
                last_exc = e
                try:
                    self._reopen_device()
                except Exception as e2:
                    last_exc = e2
                    break
        logging.error(f"Failed to send HID report after retries: {last_exc}")
        raise last_exc  # type: ignore

    def _reset_report(self) -> None:
        """Reset the HID report to all zeros (no keys pressed)."""
        self.key_state = bytearray(self.REPORT_LENGTH)
        self._send_report(self.key_state)

    # ----------------------- High-level actions -----------------------
    def press_key(self, modifier: int, key: int) -> None:
        """Press a key with the specified modifier, then release."""
        with self.lock:
            self.key_state[0] = modifier
            self.key_state[2] = key
            self._send_report(self.key_state)
            self._reset_report()

    def press_keys(self, keys: List[Tuple[int, int]]) -> None:
        """Press multiple keys simultaneously (up to 6), then release."""
        with self.lock:
            self.key_state = bytearray(self.REPORT_LENGTH)
            modifier = 0
            for mod, _ in keys:
                modifier |= mod
            self.key_state[0] = modifier
            for i, (_, key) in enumerate(keys[:6]):
                self.key_state[2 + i] = key
            self._send_report(self.key_state)
            self._reset_report()

    def hold_key(self, modifier: int, key: int) -> None:
        """Hold a key down without releasing it."""
        with self.lock:
            self.key_state[0] = modifier
            self.key_state[2] = key
            self._send_report(self.key_state)

    def release_key(self) -> None:
        """Release all held keys."""
        with self.lock:
            self._reset_report()

    def type_character(self, char: str) -> None:
        """Type a single character using char map."""
        if char in self.char_to_key:
            modifier, key = self.char_to_key[char]
            self.press_key(modifier, key)
        else:
            logging.warning(f"Character not in keymap: {char}")

    def type_string(self, string: str, delay: Optional[float] = None) -> None:
        """Type a string of characters, with delay between chars."""
        per_char_delay = self.default_char_delay if delay is None else max(0.0, delay)
        for char in string:
            self.type_character(char)
            if per_char_delay > 0:
                time.sleep(per_char_delay)

    # ----------------------- DuckyScript parsing -----------------------
    def _parse_combo_tokens(self, tokens: List[str]) -> List[Tuple[int, int]]:
        """Parse tokens for a single combo into a list of (modifier,key) tuples.
        This respects that single-letter tokens should not implicitly apply SHIFT.
        """
        keys: List[Tuple[int, int]] = []
        modifier = KeyCode.MOD_NONE.value

        for token in tokens:
            part = token.upper()
            # Modifiers accumulate
            if part in ("CTRL", "CONTROL", "SHIFT", "ALT", "GUI", "WINDOWS"):
                if part in ("CTRL", "CONTROL"):
                    modifier |= KeyCode.MOD_LCTRL.value
                elif part == "SHIFT":
                    modifier |= KeyCode.MOD_LSHIFT.value
                elif part == "ALT":
                    modifier |= KeyCode.MOD_LALT.value
                elif part in ("GUI", "WINDOWS"):
                    modifier |= KeyCode.MOD_LMETA.value
                continue

            # Known special key
            if part in self.duckyscript_commands:
                cmd_mod, cmd_key = self.duckyscript_commands[part]
                keys.append((modifier | cmd_mod, cmd_key))
                modifier = KeyCode.MOD_NONE.value
                continue

            # Single-letter key token: use lowercase mapping to avoid implicit shift
            if len(part) == 1 and part.isalpha():
                lower = part.lower()
                if lower in self.char_to_key:
                    char_mod, char_key = self.char_to_key[lower]
                    keys.append((modifier | char_mod, char_key))
                    modifier = KeyCode.MOD_NONE.value
                    continue

            # Digit or symbol present in char map as-is
            if token in self.char_to_key:
                char_mod, char_key = self.char_to_key[token]
                keys.append((modifier | char_mod, char_key))
                modifier = KeyCode.MOD_NONE.value
                continue

            logging.debug(f"Unrecognized token in combo: {token}")

        return keys

    def execute_command(self, command: str) -> None:
        """Execute a single DuckyScript command line."""
        raw = command.rstrip("\n")
        line = raw.strip()
        if not line:
            return

        logging.debug(f"Executing DuckyScript line: {line}")

        parts = line.split()
        head = parts[0].upper()

        # Comments
        if head == "REM":
            return

        # Timing controls
        if head in ("DELAY",):
            if len(parts) > 1:
                try:
                    delay_ms = int(parts[1])
                    time.sleep(max(0, delay_ms) / 1000.0)
                except ValueError:
                    logging.warning(f"Invalid DELAY value: {parts[1]}")
            return
        if head in ("DEFAULTDELAY", "DEFAULT_DELAY"):
            if len(parts) > 1:
                try:
                    self.default_command_delay_ms = max(0, int(parts[1]))
                except ValueError:
                    logging.warning(f"Invalid DEFAULTDELAY value: {parts[1]}")
            return
        if head in ("DEFAULTCHARDELAY", "DEFAULT_CHAR_DELAY"):
            if len(parts) > 1:
                try:
                    self.default_char_delay = max(0.0, int(parts[1]) / 1000.0)
                except ValueError:
                    logging.warning(f"Invalid DEFAULTCHARDELAY value: {parts[1]}")
            return

        # STRING variants
        if head == "STRING":
            text = raw[7:] if len(raw) >= 7 else ""
            self.type_string(text)
            self.last_executable_command = line
            return
        if head == "STRINGLN":
            text = raw[9:] if len(raw) >= 9 else ""
            self.type_string(text)
            self.press_key(KeyCode.MOD_NONE.value, KeyCode.KEY_ENTER.value)
            self.last_executable_command = line
            return

        # REPEAT last executable command
        if head == "REPEAT":
            count = 1
            if len(parts) > 1:
                try:
                    count = max(1, int(parts[1]))
                except ValueError:
                    logging.warning(f"Invalid REPEAT count: {parts[1]}")
            if self.last_executable_command:
                for _ in range(count):
                    self.execute_command(self.last_executable_command)
                    if self.default_command_delay_ms > 0:
                        time.sleep(self.default_command_delay_ms / 1000.0)
            else:
                logging.debug("REPEAT with no prior executable command")
            return

        # KEYDOWN/KEYUP support
        if head in ("KEYDOWN", "KEYUP"):
            if head == "KEYUP":
                self.release_key()
                return
            # KEYDOWN <combo>
            tokens = [p for p in parts[1:]]
            # Support hyphenated token as a single combo chunk
            expanded: List[str] = []
            for t in tokens:
                expanded.extend(t.split('-'))
            keys = self._parse_combo_tokens(expanded)
            if keys:
                # Only support a single primary key with modifiers for hold
                mod = 0
                primary_key = None
                for m, k in keys:
                    mod |= m
                    if k != KeyCode.KEY_NONE.value and primary_key is None:
                        primary_key = k
                if primary_key is not None:
                    self.hold_key(mod, primary_key)
            self.last_executable_command = line
            return

        # Key combos (including hyphenated)
        tokens: List[str] = []
        for p in parts:
            tokens.extend(p.split('-'))
        keys = self._parse_combo_tokens(tokens)
        if keys:
            self.press_keys(keys)
            self.last_executable_command = line
        else:
            logging.debug(f"No actionable keys for line: {line}")

    def execute_script(self, script: str, jitter: bool = False, jitter_max: int = 20) -> None:
        """Execute a DuckyScript (multi-line)."""
        lines = script.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            self.execute_command(line)
            # Default per-line delay if configured
            if self.default_command_delay_ms > 0:
                time.sleep(self.default_command_delay_ms / 1000.0)
            # Add jitter if enabled
            if jitter:
                jitter_delay = random.randint(0, max(0, jitter_max)) / 1000.0
                time.sleep(jitter_delay)

    # ----------------------- OS detection -----------------------
    def detect_target_os(self) -> str:
        """Attempt to detect the target OS based on USB enumeration behavior.
        Non-intrusive placeholder (no keystrokes)."""
        logging.info("Attempting to detect target OS (non-intrusive placeholder)...")
        # In a real implementation, analyze USB enumeration/timing/identifiers
        return "unknown"


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # Initialize the HID Emulator
        emulator = HIDEmulator()

        # Test typing a string
        emulator.type_string("Hello, World!", delay=0.02)

        # Test pressing Enter
        emulator.press_key(KeyCode.MOD_NONE.value, KeyCode.KEY_ENTER.value)

        # Test executing DuckyScript commands
        emulator.execute_command("GUI r")
        emulator.execute_command("DELAY 500")
        emulator.execute_command("STRING notepad")
        emulator.execute_command("ENTER")
        emulator.execute_command("DELAY 800")
        emulator.execute_command("STRING This is a test from Natasha AI")
        emulator.execute_command("ENTER")
        emulator.execute_command("DEFAULTDELAY 200")
        emulator.execute_command("ALT-F4")

        logging.info("HID Emulator test completed successfully")
    except Exception as e:
        logging.error(f"HID Emulator test failed: {e}")
