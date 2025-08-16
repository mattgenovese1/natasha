#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Natasha AI Penetration Testing Tool
HID Emulation Module

This module implements the USB HID (Human Interface Device) emulation functionality,
allowing the Raspberry Pi Zero 2 W to act as a keyboard device for executing
DuckyScript payloads on target systems.
"""

import os
import time
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
    
    def __init__(self, hid_device_path: str = "/dev/hidg0"):
        """Initialize the HID Emulator.
        
        Args:
            hid_device_path: Path to the USB HID gadget device
        """
        self.hid_device_path = hid_device_path
        self.device = None
        self.lock = threading.Lock()
        self.key_state = bytearray(self.REPORT_LENGTH)
        self.char_to_key = self._build_char_map()
        self.duckyscript_commands = self._build_duckyscript_commands()
        
        # Check if HID device exists
        self._check_hid_device()
    
    def _check_hid_device(self) -> None:
        """Check if the HID device exists and is accessible."""
        if not os.path.exists(self.hid_device_path):
            logging.error(f"HID device not found: {self.hid_device_path}")
            logging.info("USB HID gadget may not be configured. Run setup_usb_hid.sh first.")
            raise FileNotFoundError(f"HID device not found: {self.hid_device_path}")
        
        try:
            # Test opening the device
            with open(self.hid_device_path, 'wb') as f:
                pass
            logging.info(f"HID device ready: {self.hid_device_path}")
        except Exception as e:
            logging.error(f"Failed to access HID device: {e}")
            raise
    
    def _build_char_map(self) -> Dict[str, Tuple[int, int]]:
        """Build a mapping from characters to (modifier, keycode) pairs.
        
        Returns:
            Dictionary mapping characters to (modifier, keycode) pairs
        """
        char_map = {}
        
        # Lowercase letters
        for c in "abcdefghijklmnopqrstuvwxyz":
            keycode = getattr(KeyCode, f"KEY_{c.upper()}").value
            char_map[c] = (KeyCode.MOD_NONE.value, keycode)
        
        # Uppercase letters
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            keycode = getattr(KeyCode, f"KEY_{c}").value
            char_map[c] = (KeyCode.MOD_LSHIFT.value, keycode)
        
        # Numbers
        for i, c in enumerate("1234567890"):
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
        
        return char_map
    
    def _build_duckyscript_commands(self) -> Dict[str, Tuple[int, int]]:
        """Build a mapping from DuckyScript commands to (modifier, keycode) pairs.
        
        Returns:
            Dictionary mapping DuckyScript commands to (modifier, keycode) pairs
        """
        commands = {}
        
        # Modifier keys
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
    
    def _send_report(self, report: bytearray) -> None:
        """Send a HID report to the device.
        
        Args:
            report: HID report to send
        """
        try:
            with open(self.hid_device_path, 'wb') as device:
                device.write(report)
                device.flush()
        except Exception as e:
            logging.error(f"Failed to send HID report: {e}")
            raise
    
    def _reset_report(self) -> None:
        """Reset the HID report to all zeros (no keys pressed)."""
        self.key_state = bytearray(self.REPORT_LENGTH)
        self._send_report(self.key_state)
    
    def press_key(self, modifier: int, key: int) -> None:
        """Press a key with the specified modifier.
        
        Args:
            modifier: Modifier key code
            key: Key code
        """
        with self.lock:
            # Set modifier
            self.key_state[0] = modifier
            # Set key
            self.key_state[2] = key
            # Send report
            self._send_report(self.key_state)
            # Reset report (release all keys)
            self._reset_report()
    
    def press_keys(self, keys: List[Tuple[int, int]]) -> None:
        """Press multiple keys simultaneously.
        
        Args:
            keys: List of (modifier, key) tuples
        """
        with self.lock:
            # Reset report
            self.key_state = bytearray(self.REPORT_LENGTH)
            
            # Set modifiers (combine all modifiers)
            modifier = 0
            for mod, _ in keys:
                modifier |= mod
            self.key_state[0] = modifier
            
            # Set keys (up to 6 keys)
            for i, (_, key) in enumerate(keys[:6]):
                self.key_state[2 + i] = key
            
            # Send report
            self._send_report(self.key_state)
            
            # Reset report (release all keys)
            self._reset_report()
    
    def type_character(self, char: str) -> None:
        """Type a single character.
        
        Args:
            char: Character to type
        """
        if char in self.char_to_key:
            modifier, key = self.char_to_key[char]
            self.press_key(modifier, key)
        else:
            logging.warning(f"Character not in keymap: {char}")
    
    def type_string(self, string: str, delay: float = 0.0) -> None:
        """Type a string of characters.
        
        Args:
            string: String to type
            delay: Delay between keystrokes in seconds
        """
        for char in string:
            self.type_character(char)
            if delay > 0:
                time.sleep(delay)
    
    def execute_command(self, command: str) -> None:
        """Execute a DuckyScript command.
        
        Args:
            command: DuckyScript command to execute
        """
        # Split command into parts
        parts = command.strip().split()
        
        if not parts:
            return
        
        # Handle special commands
        if parts[0] == "REM":
            # Comment, do nothing
            return
        elif parts[0] == "DELAY":
            # Delay in milliseconds
            if len(parts) > 1:
                try:
                    delay_ms = int(parts[1])
                    time.sleep(delay_ms / 1000.0)
                except ValueError:
                    logging.warning(f"Invalid DELAY value: {parts[1]}")
            return
        elif parts[0] == "STRING":
            # Type a string
            if len(parts) > 1:
                string = command[7:]  # Remove "STRING "
                self.type_string(string)
            return
        elif parts[0] == "STRINGLN":
            # Type a string followed by Enter
            if len(parts) > 1:
                string = command[9:]  # Remove "STRINGLN "
                self.type_string(string)
                self.press_key(KeyCode.MOD_NONE.value, KeyCode.KEY_ENTER.value)
            else:
                self.press_key(KeyCode.MOD_NONE.value, KeyCode.KEY_ENTER.value)
            return
        
        # Handle key combinations
        keys = []
        modifier = KeyCode.MOD_NONE.value
        
        for part in parts:
            part = part.upper()
            
            # Check if it's a modifier key
            if part in ["CTRL", "CONTROL", "SHIFT", "ALT", "GUI", "WINDOWS"]:
                if part in ["CTRL", "CONTROL"]:
                    modifier |= KeyCode.MOD_LCTRL.value
                elif part == "SHIFT":
                    modifier |= KeyCode.MOD_LSHIFT.value
                elif part == "ALT":
                    modifier |= KeyCode.MOD_LALT.value
                elif part in ["GUI", "WINDOWS"]:
                    modifier |= KeyCode.MOD_LMETA.value
            
            # Check if it's a special key
            elif part in self.duckyscript_commands:
                cmd_mod, cmd_key = self.duckyscript_commands[part]
                keys.append((modifier | cmd_mod, cmd_key))
                modifier = KeyCode.MOD_NONE.value  # Reset modifier after each key
            
            # Check if it's a single character
            elif len(part) == 1 and part in self.char_to_key:
                char_mod, char_key = self.char_to_key[part]
                keys.append((modifier | char_mod, char_key))
                modifier = KeyCode.MOD_NONE.value  # Reset modifier after each key
        
        # Press all keys
        if keys:
            self.press_keys(keys)
    
    def execute_script(self, script: str, jitter: bool = False, jitter_max: int = 20) -> None:
        """Execute a DuckyScript.
        
        Args:
            script: DuckyScript to execute
            jitter: Whether to add random delays between commands
            jitter_max: Maximum jitter delay in milliseconds
        """
        lines = script.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            self.execute_command(line)
            
            # Add jitter if enabled
            if jitter:
                jitter_delay = random.randint(0, jitter_max) / 1000.0
                time.sleep(jitter_delay)
    
    def hold_key(self, modifier: int, key: int) -> None:
        """Hold a key down without releasing it.
        
        Args:
            modifier: Modifier key code
            key: Key code
        """
        with self.lock:
            # Set modifier
            self.key_state[0] = modifier
            # Set key
            self.key_state[2] = key
            # Send report
            self._send_report(self.key_state)
    
    def release_key(self) -> None:
        """Release all held keys."""
        with self.lock:
            self._reset_report()
    
    def detect_target_os(self) -> str:
        """Attempt to detect the target OS based on USB enumeration behavior.
        
        Returns:
            Detected OS name or "unknown"
        """
        # This is a placeholder for actual OS detection logic
        # In a real implementation, this would analyze USB enumeration patterns
        
        logging.info("Attempting to detect target OS...")
        
        # Press a key that triggers different behaviors on different OSes
        self.press_key(KeyCode.MOD_LMETA.value, KeyCode.KEY_SPACE.value)
        
        # In a real implementation, we would analyze the response
        # For now, just return unknown
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
        emulator.type_string("Hello, World!")
        
        # Test pressing Enter
        emulator.press_key(KeyCode.MOD_NONE.value, KeyCode.KEY_ENTER.value)
        
        # Test executing a DuckyScript command
        emulator.execute_command("GUI r")
        time.sleep(0.5)
        emulator.execute_command("STRING notepad")
        emulator.execute_command("ENTER")
        time.sleep(1)
        emulator.execute_command("STRING This is a test from Natasha AI")
        emulator.execute_command("ENTER")
        
        logging.info("HID Emulator test completed successfully")
    except Exception as e:
        logging.error(f"HID Emulator test failed: {e}")