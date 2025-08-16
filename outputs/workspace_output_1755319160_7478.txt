#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Natasha AI Penetration Testing Tool
Main Application

This is the main entry point for the Natasha AI Penetration Testing Tool.
It integrates all components and provides the user interface.
"""

import os
import sys
import time
import signal
import logging
import threading
import argparse
import json
from typing import Dict, List, Tuple, Optional, Union, Any
from enum import Enum

# Import component modules
try:
    from display_interface import DisplayInterface
    from ai_engine import AIEngine, TargetOS, AttackType as AIAttackType
    from hid_emulation import HIDEmulator
    from wifi_attack import WiFiAttack, AttackType as WiFiAttackType
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure all required modules are in the same directory or in the Python path.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.expanduser("~"), "natasha", "logs", "natasha.log")),
        logging.StreamHandler()
    ]
)

class AppState(Enum):
    """Enumeration of application states."""
    STARTUP = "startup"
    MAIN_MENU = "main_menu"
    USB_ATTACK_MENU = "usb_attack_menu"
    WIFI_ATTACK_MENU = "wifi_attack_menu"
    USB_ATTACK_CONFIG = "usb_attack_config"
