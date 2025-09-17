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
from logging.handlers import RotatingFileHandler
import threading
import argparse
import re
from enum import Enum

# Import component modules
try:
    from display_interface import DisplayInterface
    from ai_engine import AIEngine, TargetOS, AttackType as AIAttackType
    from hid_emulation import HIDEmulator
    from wifi_attack import WiFiAttack
    from mitm_attack import MITMAttack
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure all required modules are in the same directory or in the Python path.")
    sys.exit(1)

# Configure logging
LOG_DIR = os.path.join(os.path.expanduser("~"), "natasha", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(os.path.join(LOG_DIR, "natasha.log"), maxBytes=1_000_000, backupCount=5),
        logging.StreamHandler()
    ]
)

class AppState(Enum):
    """Enumeration of application states."""
    STARTUP = "startup"
    MAIN_MENU = "main_menu"
    USB_ATTACK_MENU = "usb_attack_menu"
    WIFI_ATTACK_MENU = "wifi_attack_menu"
    MITM_ATTACK_MENU = "mitm_attack_menu"
    USB_ATTACK_CONFIG = "usb_attack_config"
    WIFI_ATTACK_CONFIG = "wifi_attack_config"
    MITM_ATTACK_CONFIG = "mitm_attack_config"
    USB_ATTACK_RUNNING = "usb_attack_running"
    WIFI_ATTACK_RUNNING = "wifi_attack_running"
    MITM_ATTACK_RUNNING = "mitm_attack_running"
    SYSTEM_STATUS = "system_status"
    SETTINGS = "settings"
    SHUTDOWN = "shutdown"

class NatashaApp:
    """Main application class for Natasha AI Penetration Testing Tool."""
    
    def __init__(self):
        """Initialize the application."""
        self.display = None
        self.ai_engine = None
        self.hid_emulator = None
        self.wifi_attack = None
        self.mitm_attack = None
        
        self.state = AppState.STARTUP
        self.previous_state = None
        self.menu_index = 0
        self.menu_start = 0
        self.menu_items = []
        self.config_params = {}
        self.attack_results = {}
        self.stop_event = threading.Event()
        self.display_lock = threading.RLock()
        self.state_lock = threading.RLock()
        
        # Base directories
        self.base_dir = os.path.join(os.path.expanduser("~"), "natasha")
        self.logs_dir = os.path.join(self.base_dir, "logs")
        self.scripts_dir = os.path.join(self.base_dir, "scripts")
        self.captures_dir = os.path.join(self.base_dir, "captures")
        
        # Button GPIO pins
        self.button_pins = {
            "up": 5,     # GPIO 5 (Pin 29)
            "down": 6,   # GPIO 6 (Pin 31)
            "select": 13, # GPIO 13 (Pin 33)
            "back": 19,  # GPIO 19 (Pin 35)
            "power": 26  # GPIO 26 (Pin 37)
        }
        
        # LED GPIO pins
        self.led_pins = {
            "red": 12,   # GPIO 12 (Pin 32)
            "green": 16  # GPIO 16 (Pin 36)
        }
        
        # Button states
        self.button_states = {pin: False for pin in self.button_pins.keys()}
        self.button_last_press = {pin: 0 for pin in self.button_pins.keys()}
        self.button_debounce_time = 0.2  # seconds
        
        # Initialize components
        self._init_components()
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _init_components(self):
        """Initialize all components."""
        try:
            # Create directories
            os.makedirs(self.logs_dir, exist_ok=True)
            os.makedirs(self.scripts_dir, exist_ok=True)
            os.makedirs(self.captures_dir, exist_ok=True)
            
            # Initialize display
            logging.info("Initializing display...")
            self.display = DisplayInterface()
            
            # Show splash screen
            self.display.draw_splash_screen()
            time.sleep(2)
            
            # Initialize AI engine
            logging.info("Initializing AI engine...")
            self.display.clear()
            self.display.draw_header("Initializing")
            self.display.draw_text(10, 30, "Loading AI engine...", font=self.display.font_normal)
            self.display.update()
            
            self.ai_engine = AIEngine()
            
            # Initialize HID emulator
            logging.info("Initializing HID emulator...")
            self.display.draw_text(10, 50, "Loading HID emulator...", font=self.display.font_normal)
            self.display.update()
            
            try:
                self.hid_emulator = HIDEmulator()
            except FileNotFoundError:
                logging.warning("HID device not found. USB attacks will be disabled.")
                self.hid_emulator = None
            
            # Initialize WiFi attack module
            logging.info("Initializing WiFi attack module...")
            self.display.draw_text(10, 70, "Loading WiFi module...", font=self.display.font_normal)
            self.display.update()
            
            try:
                self.wifi_attack = WiFiAttack()
            except Exception as e:
                logging.warning(f"WiFi attack module initialization failed: {e}")
                self.wifi_attack = None
                
            # Initialize MITM attack module
            logging.info("Initializing MITM attack module...")
            self.display.draw_text(10, 80, "Loading MITM module...", font=self.display.font_normal)
            self.display.update()
            
            try:
                self.mitm_attack = MITMAttack()
            except Exception as e:
                logging.warning(f"MITM attack module initialization failed: {e}")
                self.mitm_attack = None
            
            # Initialize GPIO for buttons and LEDs
            logging.info("Initializing GPIO...")
            self.display.draw_text(10, 90, "Setting up controls...", font=self.display.font_normal)
            self.display.update()
            
            self._init_gpio()
            
            logging.info("All components initialized")
        except Exception as e:
            logging.error(f"Error initializing components: {e}")
            if self.display:
                self.display.clear()
                self.display.draw_header("Error")
                self.display.draw_text(10, 40, "Initialization failed:", font=self.display.font_normal)
                self.display.draw_text(10, 60, str(e), font=self.display.font_normal)
                self.display.update()
                time.sleep(5)
            sys.exit(1)
    
    def _init_gpio(self):
        """Initialize GPIO for buttons and LEDs."""
        try:
            import RPi.GPIO as GPIO
            
            # Set up GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Set up button pins as inputs with pull-up resistors
            for pin in self.button_pins.values():
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Set up LED pins as outputs
            for pin in self.led_pins.values():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
            
            # Set up button event detection
            for button, pin in self.button_pins.items():
                # Rely on software debounce in _button_callback; no hardware bouncetime
                GPIO.add_event_detect(pin, GPIO.FALLING, callback=lambda channel, b=button: self._button_callback(b))
            
            # Blink LEDs to indicate successful initialization
            self._blink_leds()
            
            logging.info("GPIO initialized successfully")
        except ImportError:
            logging.warning("RPi.GPIO module not available. Running in development mode.")
            # In development mode, simulate button presses with keyboard input
            self._setup_keyboard_input()
        except Exception as e:
            logging.error(f"Error initializing GPIO: {e}")
    
    def _setup_keyboard_input(self):
        """Set up keyboard input for development mode."""
        logging.info("Setting up keyboard input for development mode")
        
        def keyboard_input():
            import termios
            import tty
            import sys
            import select
            
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                while not self.stop_event.is_set():
                    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                    if rlist:
                        ch = sys.stdin.read(1)
                        if ch == 'w':  # Up
                            self._button_callback("up")
                        elif ch == 's':  # Down
                            self._button_callback("down")
                        elif ch in ('\r', '\n'):  # Enter/Select
                            self._button_callback("select")
                        elif ch == 'b':  # Back
                            self._button_callback("back")
                        elif ch == 'q':  # Power/Quit
                            self._button_callback("power")
            except Exception as e:
                logging.error(f"Error in keyboard input thread: {e}")
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        
        # Start keyboard input thread
        keyboard_thread = threading.Thread(target=keyboard_input)
        keyboard_thread.daemon = True
        keyboard_thread.start()
    
    def _button_callback(self, button):
        """Handle button press events.
        
        Args:
            button: Button that was pressed
        """
        # Debounce
        current_time = time.time()
        if current_time - self.button_last_press[button] < self.button_debounce_time:
            return
        
        self.button_last_press[button] = current_time
        self.button_states[button] = True
        
        logging.debug(f"Button pressed: {button}")
        
        # Handle button press based on current state
        if button == "power":
            # Power button is special - long press to shutdown
            self._handle_power_button()
        elif self.state == AppState.MAIN_MENU:
            self._handle_main_menu_button(button)
        elif self.state == AppState.USB_ATTACK_MENU:
            self._handle_usb_attack_menu_button(button)
        elif self.state == AppState.WIFI_ATTACK_MENU:
            self._handle_wifi_attack_menu_button(button)
        elif self.state == AppState.MITM_ATTACK_MENU:
            self._handle_mitm_attack_menu_button(button)
        elif self.state == AppState.USB_ATTACK_CONFIG:
            self._handle_usb_attack_config_button(button)
        elif self.state == AppState.WIFI_ATTACK_CONFIG:
            self._handle_wifi_attack_config_button(button)
        elif self.state == AppState.MITM_ATTACK_CONFIG:
            self._handle_mitm_attack_config_button(button)
        elif self.state == AppState.USB_ATTACK_RUNNING:
            self._handle_usb_attack_running_button(button)
        elif self.state == AppState.WIFI_ATTACK_RUNNING:
            self._handle_wifi_attack_running_button(button)
        elif self.state == AppState.MITM_ATTACK_RUNNING:
            self._handle_mitm_attack_running_button(button)
        elif self.state == AppState.SYSTEM_STATUS:
            self._handle_system_status_button(button)
        elif self.state == AppState.SETTINGS:
            self._handle_settings_button(button)
    
    def _handle_power_button(self):
        """Handle power button press."""
        # For now, just go to shutdown state
        self.state = AppState.SHUTDOWN
        self._update_display()
    
    def _handle_main_menu_button(self, button):
        """Handle button press in main menu.
        
        Args:
            button: Button that was pressed
        """
        if button == "up":
            if self.menu_index > 0:
                self.menu_index -= 1
                if self.menu_index < self.menu_start:
                    self.menu_start = self.menu_index
        elif button == "down":
            if self.menu_index < len(self.menu_items) - 1:
                self.menu_index += 1
                if self.menu_index >= self.menu_start + 5:  # 5 items visible at once
                    self.menu_start += 1
        elif button == "select":
            selected_item = self.menu_items[self.menu_index]
            if selected_item == "USB Attacks":
                self.state = AppState.USB_ATTACK_MENU
                self.menu_index = 0
                self.menu_start = 0
            elif selected_item == "WiFi Attacks":
                self.state = AppState.WIFI_ATTACK_MENU
                self.menu_index = 0
                self.menu_start = 0
            elif selected_item == "MITM Attacks":
                self.state = AppState.MITM_ATTACK_MENU
                self.menu_index = 0
                self.menu_start = 0
            elif selected_item == "System Status":
                self.state = AppState.SYSTEM_STATUS
            elif selected_item == "Settings":
                self.state = AppState.SETTINGS
                self.menu_index = 0
                self.menu_start = 0
            elif selected_item == "Shutdown":
                self.state = AppState.SHUTDOWN
        
        self._update_display()
    
    def _handle_usb_attack_menu_button(self, button):
        """Handle button press in USB attack menu.
        
        Args:
            button: Button that was pressed
        """
        if button == "up":
            if self.menu_index > 0:
                self.menu_index -= 1
                if self.menu_index < self.menu_start:
                    self.menu_start = self.menu_index
        elif button == "down":
            if self.menu_index < len(self.menu_items) - 1:
                self.menu_index += 1
                if self.menu_index >= self.menu_start + 5:
                    self.menu_start += 1
        elif button == "select":
            selected_item = self.menu_items[self.menu_index]
            if selected_item == "Back":
                self.state = AppState.MAIN_MENU
                self.menu_index = 0
                self.menu_start = 0
            else:
                # Configure selected USB attack
                self.config_params = {"attack_name": selected_item, "target_os_index": 0}
                self.state = AppState.USB_ATTACK_CONFIG
                self.menu_index = 0
                self.menu_start = 0
        elif button == "back":
            self.state = AppState.MAIN_MENU
            self.menu_index = 0
            self.menu_start = 0
        
        self._update_display()
    
    def _handle_wifi_attack_menu_button(self, button):
        """Handle button press in WiFi attack menu.
        
        Args:
            button: Button that was pressed
        """
        if button == "up":
            if self.menu_index > 0:
                self.menu_index -= 1
                if self.menu_index < self.menu_start:
                    self.menu_start = self.menu_index
        elif button == "down":
            if self.menu_index < len(self.menu_items) - 1:
                self.menu_index += 1
                if self.menu_index >= self.menu_start + 5:
                    self.menu_start += 1
        elif button == "select":
            selected_item = self.menu_items[self.menu_index]
            if selected_item == "Back":
                self.state = AppState.MAIN_MENU
                self.menu_index = 0
                self.menu_start = 0
            else:
                # Configure selected WiFi attack
                self.config_params = {"attack_name": selected_item}
                self.state = AppState.WIFI_ATTACK_CONFIG
                self.menu_index = 0
                self.menu_start = 0
        elif button == "back":
            self.state = AppState.MAIN_MENU
            self.menu_index = 0
            self.menu_start = 0
        
        self._update_display()
    
    def _handle_usb_attack_config_button(self, button):
        """Handle button press in USB attack configuration.
        
        Args:
            button: Button that was pressed
        """
        # Basic parameter navigation for Target OS selection
        if button == "up":
            idx = self.config_params.get("target_os_index", 0)
            self.config_params["target_os_index"] = (idx - 1) % 5
        elif button == "down":
            idx = self.config_params.get("target_os_index", 0)
            self.config_params["target_os_index"] = (idx + 1) % 5
        elif button == "select":
            # Start the attack
            self.state = AppState.USB_ATTACK_RUNNING
            self._start_usb_attack()
        elif button == "back":
            self.state = AppState.USB_ATTACK_MENU
            self.menu_index = 0
            self.menu_start = 0
        
        self._update_display()
    
    def _handle_wifi_attack_config_button(self, button):
        """Handle button press in WiFi attack configuration.
        
        Args:
            button: Button that was pressed
        """
        # This is a simplified implementation
        # In a real implementation, this would handle configuration parameters
        if button == "select":
            # Start the attack
            self.state = AppState.WIFI_ATTACK_RUNNING
            self._start_wifi_attack()
        elif button == "back":
            self.state = AppState.WIFI_ATTACK_MENU
            self.menu_index = 0
            self.menu_start = 0
        
        self._update_display()
    
    def _handle_usb_attack_running_button(self, button):
        """Handle button press while USB attack is running.
        
        Args:
            button: Button that was pressed
        """
        if button == "back" or button == "select":
            # Stop the attack
            self._stop_usb_attack()
            self.state = AppState.USB_ATTACK_MENU
            self.menu_index = 0
            self.menu_start = 0
            self._update_display()
    
    def _handle_wifi_attack_running_button(self, button):
        """Handle button press while WiFi attack is running.
        
        Args:
            button: Button that was pressed
        """
        if button == "back" or button == "select":
            # Stop the attack
            self._stop_wifi_attack()
            self.state = AppState.WIFI_ATTACK_MENU
            self.menu_index = 0
            self.menu_start = 0
            self._update_display()
    
    def _handle_system_status_button(self, button):
        """Handle button press in system status screen.
        
        Args:
            button: Button that was pressed
        """
        if button == "back" or button == "select":
            self.state = AppState.MAIN_MENU
            self.menu_index = 0
            self.menu_start = 0
            self._update_display()
    
    def _handle_settings_button(self, button):
        """Handle button press in settings screen.
        
        Args:
            button: Button that was pressed
        """
        if button == "up":
            if self.menu_index > 0:
                self.menu_index -= 1
                if self.menu_index < self.menu_start:
                    self.menu_start = self.menu_index
        elif button == "down":
            if self.menu_index < len(self.menu_items) - 1:
                self.menu_index += 1
                if self.menu_index >= self.menu_start + 5:
                    self.menu_start += 1
        elif button == "select":
            selected_item = self.menu_items[self.menu_index]
            if selected_item == "Back":
                self.state = AppState.MAIN_MENU
                self.menu_index = 0
                self.menu_start = 0
            else:
                # Handle settings item
                pass
        elif button == "back":
            self.state = AppState.MAIN_MENU
            self.menu_index = 0
            self.menu_start = 0
        
        self._update_display()
    
    def _blink_leds(self):
        """Blink LEDs to indicate successful initialization."""
        try:
            import RPi.GPIO as GPIO
            
            # Blink red LED
            GPIO.output(self.led_pins["red"], GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(self.led_pins["red"], GPIO.LOW)
            
            # Blink green LED
            GPIO.output(self.led_pins["green"], GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(self.led_pins["green"], GPIO.LOW)
        except ImportError:
            logging.debug("RPi.GPIO not available; skipping LED blink in dev mode.")
        except Exception as e:
            logging.warning(f"Blink LEDs failed: {e}")
    
    def _set_led(self, led, state):
        """Set LED state.
        
        Args:
            led: LED to set ("red" or "green")
            state: LED state (True for on, False for off)
        """
        try:
            import RPi.GPIO as GPIO
            GPIO.output(self.led_pins[led], GPIO.HIGH if state else GPIO.LOW)
        except ImportError:
            logging.debug("RPi.GPIO not available; LED control disabled in dev mode.")
        except Exception as e:
            logging.warning(f"LED control failed: {e}")
    
    def _update_display_threadsafe(self):
        """Update the display while holding the display lock (thread-safe)."""
        with self.display_lock:
            self._update_display()

    def _update_display(self):
        """Update the display based on the current state."""
        if self.state == AppState.MAIN_MENU:
            self._show_main_menu()
        elif self.state == AppState.USB_ATTACK_MENU:
            self._show_usb_attack_menu()
        elif self.state == AppState.WIFI_ATTACK_MENU:
            self._show_wifi_attack_menu()
        elif self.state == AppState.MITM_ATTACK_MENU:
            self._show_mitm_attack_menu()
        elif self.state == AppState.USB_ATTACK_CONFIG:
            self._show_usb_attack_config()
        elif self.state == AppState.WIFI_ATTACK_CONFIG:
            self._show_wifi_attack_config()
        elif self.state == AppState.MITM_ATTACK_CONFIG:
            self._show_mitm_attack_config()
        elif self.state == AppState.USB_ATTACK_RUNNING:
            self._show_usb_attack_running()
        elif self.state == AppState.WIFI_ATTACK_RUNNING:
            self._show_wifi_attack_running()
        elif self.state == AppState.MITM_ATTACK_RUNNING:
            self._show_mitm_attack_running()
        elif self.state == AppState.SYSTEM_STATUS:
            self._show_system_status()
        elif self.state == AppState.SETTINGS:
            self._show_settings()
        elif self.state == AppState.SHUTDOWN:
            self._show_shutdown()
    
    def _show_main_menu(self):
        """Show the main menu."""
        self.menu_items = [
            "USB Attacks",
            "WiFi Attacks",
            "MITM Attacks",
            "System Status",
            "Settings",
            "Shutdown"
        ]
        
        self.display.clear()
        self.display.draw_menu("Natasha Main Menu", self.menu_items, 
                             selected_index=self.menu_index, 
                             start_index=self.menu_start)
        self.display.draw_natasha_avatar(200, 30, expression="normal")
        self.display.update()
    
    def _show_usb_attack_menu(self):
        """Show the USB attack menu."""
        self.menu_items = [
            "Credential Harvester",
            "Keylogger",
            "Backdoor",
            "System Information",
            "Custom Script",
            "Back"
        ]
        
        self.display.clear()
        self.display.draw_menu("USB Attacks", self.menu_items, 
                             selected_index=self.menu_index, 
                             start_index=self.menu_start)
        self.display.update()
    
    def _show_wifi_attack_menu(self):
        """Show the WiFi attack menu."""
        self.menu_items = [
            "Network Scanner",
            "Deauthentication",
            "Evil Twin",
            "Captive Portal",
            "Handshake Capture",
            "PMKID Attack",
            "Back"
        ]
        
        self.display.clear()
        self.display.draw_menu("WiFi Attacks", self.menu_items, 
                             selected_index=self.menu_index, 
                             start_index=self.menu_start)
        self.display.update()
    
    def _show_usb_attack_config(self):
        """Show the USB attack configuration screen."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        
        self.display.clear()
        self.display.draw_header(f"Configure: {attack_name}")
        self.display.draw_natasha_avatar(200, 30, expression="thinking")
        
        # Target OS selection (UP/DOWN to change)
        target_os_options = ["Auto-detect", "Windows", "macOS", "Linux", "Android"]
        idx = self.config_params.get("target_os_index", 0)
        selected_os = target_os_options[idx % len(target_os_options)]
        
        self.display.draw_text(10, 30, "Target OS:", font=self.display.font_normal)
        self.display.draw_text(100, 30, selected_os, font=self.display.font_normal)
        
        self.display.draw_text(10, 50, "Options:", font=self.display.font_normal)
        self.display.draw_text(100, 50, "Default", font=self.display.font_normal)
        
        self.display.draw_text(10, 80, "UP/DOWN: change OS", font=self.display.font_small)
        self.display.draw_text(10, 96, "SELECT: start  BACK: return", font=self.display.font_small)
        
        self.display.draw_footer(None, "START", "BACK")
        self.display.update()
    
    def _show_wifi_attack_config(self):
        """Show the WiFi attack configuration screen."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        
        self.display.clear()
        self.display.draw_header(f"Configure: {attack_name}")
        self.display.draw_natasha_avatar(200, 30, expression="thinking")
        
        if attack_name == "Network Scanner":
            self.display.draw_text(10, 30, "Duration:", font=self.display.font_normal)
            self.display.draw_text(100, 30, "30 seconds", font=self.display.font_normal)
        elif attack_name in ["Deauthentication", "Evil Twin", "Captive Portal"]:
            self.display.draw_text(10, 30, "Target:", font=self.display.font_normal)
            self.display.draw_text(100, 30, "All networks", font=self.display.font_normal)
            
            self.display.draw_text(10, 50, "Channel:", font=self.display.font_normal)
            self.display.draw_text(100, 50, "1", font=self.display.font_normal)
        
        self.display.draw_text(10, 80, "Press SELECT to start attack", font=self.display.font_normal)
        self.display.draw_text(10, 100, "Press BACK to return", font=self.display.font_normal)
        
        self.display.draw_footer(None, "START", "BACK")
        self.display.update()
    
    def _show_usb_attack_running(self):
        """Show the USB attack running screen."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        
        self.display.clear()
        self.display.draw_header(f"Running: {attack_name}")
        self.display.draw_natasha_avatar(200, 30, expression="normal")
        
        self.display.draw_text(10, 30, "Status:", font=self.display.font_normal)
        self.display.draw_text(100, 30, "Active", font=self.display.font_normal)
        
        self.display.draw_text(10, 50, "Target OS:", font=self.display.font_normal)
        self.display.draw_text(100, 50, self.attack_results.get("target_os", "Detecting..."), font=self.display.font_normal)
        
        self.display.draw_text(10, 70, "Progress:", font=self.display.font_normal)
        self.display.draw_progress_bar(10, 90, 180, self.attack_results.get("progress", 0))
        
        self.display.draw_footer("STOP", None, None)
        self.display.update()
    
    def _show_wifi_attack_running(self):
        """Show the WiFi attack running screen."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        
        self.display.clear()
        self.display.draw_header(f"Running: {attack_name}")
        self.display.draw_natasha_avatar(200, 30, expression="normal")
        
        self.display.draw_text(10, 30, "Status:", font=self.display.font_normal)
        self.display.draw_text(100, 30, "Active", font=self.display.font_normal)
        
        if attack_name == "Network Scanner":
            self.display.draw_text(10, 50, "Networks found:", font=self.display.font_normal)
            self.display.draw_text(150, 50, str(self.attack_results.get("networks_found", 0)), font=self.display.font_normal)
            
            self.display.draw_text(10, 70, "Clients found:", font=self.display.font_normal)
            self.display.draw_text(150, 70, str(self.attack_results.get("clients_found", 0)), font=self.display.font_normal)
        elif attack_name == "Deauthentication":
            self.display.draw_text(10, 50, "Packets sent:", font=self.display.font_normal)
            self.display.draw_text(150, 50, str(self.attack_results.get("packets_sent", 0)), font=self.display.font_normal)
        elif attack_name in ["Evil Twin", "Captive Portal"]:
            self.display.draw_text(10, 50, "Clients connected:", font=self.display.font_normal)
            self.display.draw_text(150, 50, str(self.attack_results.get("clients_connected", 0)), font=self.display.font_normal)
            
            if attack_name == "Captive Portal":
                self.display.draw_text(10, 70, "Credentials captured:", font=self.display.font_normal)
                self.display.draw_text(150, 70, str(self.attack_results.get("credentials_captured", 0)), font=self.display.font_normal)
        elif attack_name in ["Handshake Capture", "PMKID Attack"]:
            self.display.draw_text(10, 50, "Capture status:", font=self.display.font_normal)
            self.display.draw_text(150, 50, self.attack_results.get("capture_status", "Waiting..."), font=self.display.font_normal)
        
        self.display.draw_footer("STOP", None, None)
        self.display.update()
    
    def _show_mitm_attack_menu(self):
        """Show the MITM attack menu."""
        self.menu_items = [
            "ARP Spoof",
            "DNS Spoof",
            "HTTP Proxy",
            "Back"
        ]
        
        self.display.clear()
        self.display.draw_menu("MITM Attacks", self.menu_items, 
                             selected_index=self.menu_index, 
                             start_index=self.menu_start)
        self.display.update()

    def _handle_mitm_attack_menu_button(self, button):
        """Handle button press in MITM attack menu."""
        if button == "up":
            if self.menu_index > 0:
                self.menu_index -= 1
                if self.menu_index < self.menu_start:
                    self.menu_start = self.menu_index
        elif button == "down":
            if self.menu_index < len(self.menu_items) - 1:
                self.menu_index += 1
                if self.menu_index >= self.menu_start + 5:
                    self.menu_start += 1
        elif button == "select":
            selected_item = self.menu_items[self.menu_index]
            if selected_item == "Back":
                self.state = AppState.MAIN_MENU
                self.menu_index = 0
                self.menu_start = 0
            else:
                # Configure selected MITM attack
                self.config_params = {"attack_name": selected_item}
                self.state = AppState.MITM_ATTACK_CONFIG
                self.menu_index = 0
                self.menu_start = 0
        elif button == "back":
            self.state = AppState.MAIN_MENU
            self.menu_index = 0
            self.menu_start = 0
        
        self._update_display()

    def _show_mitm_attack_config(self):
        """Show the MITM attack configuration screen."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        
        self.display.clear()
        self.display.draw_header(f"Configure: {attack_name}")
        self.display.draw_natasha_avatar(200, 30, expression="thinking")
        
        self.display.draw_text(10, 30, "Target:", font=self.display.font_normal)
        self.display.draw_text(100, 30, "Default", font=self.display.font_normal)
        
        self.display.draw_text(10, 80, "Press SELECT to start attack", font=self.display.font_normal)
        self.display.draw_text(10, 100, "Press BACK to return", font=self.display.font_normal)
        
        self.display.draw_footer(None, "START", "BACK")
        self.display.update()

    def _handle_mitm_attack_config_button(self, button):
        """Handle button press in MITM attack configuration."""
        if button == "select":
            self.state = AppState.MITM_ATTACK_RUNNING
            self._start_mitm_attack()
        elif button == "back":
            self.state = AppState.MITM_ATTACK_MENU
            self.menu_index = 0
            self.menu_start = 0
        
        self._update_display()

    def _show_mitm_attack_running(self):
        """Show the MITM attack running screen."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        
        self.display.clear()
        self.display.draw_header(f"Running: {attack_name}")
        self.display.draw_natasha_avatar(200, 30, expression="normal")
        
        self.display.draw_text(10, 30, "Status:", font=self.display.font_normal)
        self.display.draw_text(100, 30, "Active", font=self.display.font_normal)
        
        self.display.draw_text(10, 50, "Notes:", font=self.display.font_normal)
        self.display.draw_text(100, 50, "Demo mode", font=self.display.font_normal)
        
        self.display.draw_footer("STOP", None, None)
        self.display.update()

    def _handle_mitm_attack_running_button(self, button):
        """Handle button press while MITM attack is running."""
        if button in ("back", "select"):
            self._stop_mitm_attack()
            self.state = AppState.MITM_ATTACK_MENU
            self.menu_index = 0
            self.menu_start = 0
            self._update_display()

    def _start_mitm_attack(self):
        """Start the configured MITM attack (demo stub)."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        logging.info(f"Starting MITM attack: {attack_name}")
        self._set_led("red", True)
        self.attack_results = {}
        t = threading.Thread(target=self._run_mitm_attack, daemon=True)
        t.start()

    def _run_mitm_attack(self):
        """Run the MITM attack in a background thread (demo stub)."""
        try:
            # Demo loop that just updates the screen until stopped
            counter = 0
            while True:
                with self.state_lock:
                    running = self.state == AppState.MITM_ATTACK_RUNNING
                if not running:
                    break
                self.attack_results["counter"] = counter
                self._update_display_threadsafe()
                counter += 1
                time.sleep(1)
        except Exception as e:
            logging.error(f"Error running MITM attack: {e}")
            self.attack_results["error"] = str(e)
            with self.state_lock:
                self.state = AppState.MITM_ATTACK_MENU
                self.menu_index = 0
                self.menu_start = 0
            self._update_display_threadsafe()
        finally:
            self._set_led("red", False)

    def _stop_mitm_attack(self):
        """Stop the running MITM attack (demo stub)."""
        logging.info("Stopping MITM attack")
        if self.mitm_attack and hasattr(self.mitm_attack, "stop_attack"):
            try:
                self.mitm_attack.stop_attack()
            except Exception as e:
                logging.debug(f"MITM stop error: {e}")
        # LED off handled in thread finally
    
    def _show_system_status(self):
        """Show the system status screen."""
        # Get system information
        try:
            import psutil
        except ImportError:
            psutil = None
        
        if psutil:
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
        else:
            cpu_percent = 0
            memory_percent = 0
            disk_percent = 0
        
        battery_level = self._get_battery_level()
        
        uptime = self._get_uptime()
        
        status_items = [
            ("CPU", f"{cpu_percent}%"),
            ("Memory", f"{memory_percent}%"),
            ("Disk", f"{disk_percent}%"),
            ("Battery", f"{battery_level}%"),
            ("Uptime", uptime),
            ("WiFi", "Connected" if self.wifi_attack else "Disabled"),
            ("USB HID", "Ready" if self.hid_emulator else "Disabled")
        ]
        
        self.display.clear()
        self.display.draw_status_screen("System Status", status_items, 
                                      battery_level=battery_level, 
                                      wifi_status=self.wifi_attack is not None)
        self.display.update()
    
    def _show_settings(self):
        """Show the settings screen."""
        self.menu_items = [
            "Display Settings",
            "Network Settings",
            "Power Settings",
            "Update Software",
            "Factory Reset",
            "Back"
        ]
        
        self.display.clear()
        self.display.draw_menu("Settings", self.menu_items, 
                             selected_index=self.menu_index, 
                             start_index=self.menu_start)
        self.display.update()
    
    def _show_shutdown(self):
        """Show the shutdown screen."""
        self.display.clear()
        self.display.draw_header("Shutting Down")
        self.display.draw_natasha_avatar(200, 30, expression="normal")
        self.display.draw_centered_text(50, "Shutting down...", font=self.display.font_normal)
        self.display.draw_centered_text(70, "Please wait", font=self.display.font_normal)
        self.display.update()
        
        # Clean up and shutdown
        self._cleanup()
        
        # In a real implementation, this would shut down the system
        # os.system("sudo shutdown -h now")
        sys.exit(0)
    
    def _get_battery_level(self):
        """Get the battery level.
        
        Returns:
            Battery level as a percentage (0-100)
        """
        # This is a placeholder
        # In a real implementation, this would read the battery level from hardware
        return 85
    
    def _get_uptime(self):
        """Get the system uptime.
        
        Returns:
            Uptime as a string
        """
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
            
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            return f"{int(hours)}h {int(minutes)}m"
        except Exception as e:
            logging.debug(f"Could not read uptime: {e}")
            return "Unknown"
    
    def _start_usb_attack(self):
        """Start the configured USB attack."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        logging.info(f"Starting USB attack: {attack_name}")
        
        # Set red LED to indicate attack is running
        self._set_led("red", True)
        
        # Reset attack results
        self.attack_results = {"progress": 0, "target_os": "Detecting..."}
        
        # Start attack in a separate thread
        attack_thread = threading.Thread(target=self._run_usb_attack)
        attack_thread.daemon = True
        attack_thread.start()
    
    def _run_usb_attack(self):
        """Run the USB attack in a background thread."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        
        try:
            if not self.hid_emulator:
                logging.error("HID emulator not available")
                self.attack_results = {"error": "HID emulator not available"}
                return
            
            # Determine target OS (override or detection)
            idx = self.config_params.get("target_os_index", 0)
            if idx == 0:
                target_os = self.hid_emulator.detect_target_os()
            else:
                idx_map = {1: "windows", 2: "macos", 3: "linux", 4: "android"}
                target_os = idx_map.get(idx, "unknown")
            self.attack_results["target_os"] = target_os
            
            # Map attack name to AI attack type
            attack_type_map = {
                "Credential Harvester": AIAttackType.CREDENTIAL_HARVEST,
                "Keylogger": AIAttackType.KEYLOGGER,
                "Backdoor": AIAttackType.BACKDOOR,
                "System Information": AIAttackType.RECON,
                "Custom Script": AIAttackType.CUSTOM
            }
            
            attack_type = attack_type_map.get(attack_name, AIAttackType.RECON)
            
            # Map target OS string to AI target OS enum
            target_os_map = {
                "windows": TargetOS.WINDOWS,
                "macos": TargetOS.MACOS,
                "linux": TargetOS.LINUX,
                "android": TargetOS.ANDROID,
                "unknown": TargetOS.UNKNOWN
            }
            
            ai_target_os = target_os_map.get(target_os, TargetOS.UNKNOWN)
            
            # Generate script
            self.attack_results["progress"] = 10
            logging.info(f"Generating script for {attack_name} on {target_os}")
            
            params = self.config_params.get("parameters", {})
            script = self.ai_engine.generate_duckyscript(attack_type, ai_target_os, params)
            
            # Save script to file
            script_dir = self.scripts_dir
            os.makedirs(script_dir, exist_ok=True)
            
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", attack_name).strip("_")
            script_file = os.path.join(script_dir, f"{safe_name}_{timestamp}.txt")
            
            with open(script_file, 'w') as f:
                f.write(script)
            
            self.attack_results["script_file"] = script_file
            self.attack_results["progress"] = 30
            
            # Execute script
            logging.info(f"Executing script: {script_file}")
            
            # Split script into lines
            lines = script.split('\n')
            total_lines = len(lines)
            
            for i, line in enumerate(lines):
                with self.state_lock:
                    running = self.state == AppState.USB_ATTACK_RUNNING
                if not running:
                    # Attack was stopped
                    break
                
                line = line.strip()
                if not line or line.startswith("REM"):
                    continue
                
                self.hid_emulator.execute_command(line)
                
                # Update progress
                progress = 30 + int(70 * (i + 1) / total_lines)
                self.attack_results["progress"] = progress
                
                # Update display
                self._update_display_threadsafe()
            
            # Attack completed
            self.attack_results["progress"] = 100
            self.attack_results["status"] = "Completed"
            
            # Wait a bit before returning to menu
            time.sleep(2)
            
            # Return to menu
            with self.state_lock:
                self.state = AppState.USB_ATTACK_MENU
                self.menu_index = 0
                self.menu_start = 0
            self._update_display_threadsafe()
        except Exception as e:
            logging.error(f"Error running USB attack: {e}")
            self.attack_results["error"] = str(e)
            
            # Return to menu
            with self.state_lock:
                self.state = AppState.USB_ATTACK_MENU
                self.menu_index = 0
                self.menu_start = 0
            self._update_display_threadsafe()
        finally:
            # Turn off red LED
            self._set_led("red", False)
    
    def _stop_usb_attack(self):
        """Stop the running USB attack."""
        logging.info("Stopping USB attack")
        # LED state will be turned off by the USB worker thread's finally block
    
    def _start_wifi_attack(self):
        """Start the configured WiFi attack."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        logging.info(f"Starting WiFi attack: {attack_name}")
        
        # Set red LED to indicate attack is running
        self._set_led("red", True)
        
        # Reset attack results
        self.attack_results = {}
        
        # Start attack in a separate thread
        attack_thread = threading.Thread(target=self._run_wifi_attack)
        attack_thread.daemon = True
        attack_thread.start()
    
    def _run_wifi_attack(self):
        """Run the WiFi attack in a background thread."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        
        try:
            if not self.wifi_attack:
                logging.error("WiFi attack module not available")
                self.attack_results = {"error": "WiFi attack module not available"}
                return
            
            if attack_name == "Network Scanner":
                # Run network scan
                def scan_callback(results):
                    self.attack_results["networks_found"] = len(results)
                    self.attack_results["clients_found"] = len(self.wifi_attack.clients)
                    self._update_display_threadsafe()
                
                self.wifi_attack.start_continuous_scan(callback=scan_callback)
                
                # Keep scanning until attack is stopped
                while True:
                    with self.state_lock:
                        running = self.state == AppState.WIFI_ATTACK_RUNNING
                    if not running:
                        break
                    time.sleep(1)
                
                # Stop scanning
                self.wifi_attack.stop_continuous_scan()
            
            elif attack_name == "Deauthentication":
                # Run deauthentication attack
                # For demonstration, just deauthenticate all networks periodically
                packets_sent = 0
                
                while True:
                    with self.state_lock:
                        running = self.state == AppState.WIFI_ATTACK_RUNNING
                    if not running:
                        break
                    # Scan for networks
                    networks = self.wifi_attack.scan_networks(duration=5)
                    
                    for bssid, ap in networks.items():
                        with self.state_lock:
                            running = self.state == AppState.WIFI_ATTACK_RUNNING
                        if not running:
                            break
                        
                        # Deauthenticate network
                        self.wifi_attack.deauth_network(bssid, count=5)
                        packets_sent += 5
                        
                        self.attack_results["packets_sent"] = packets_sent
                        self._update_display_threadsafe()
                    
                    time.sleep(1)
            
            elif attack_name == "Evil Twin":
                # Run evil twin attack
                # For demonstration, create a simple open network
                self.wifi_attack.start_evil_twin("Free-WiFi", channel=1)
                
                # Monitor clients
                while True:
                    with self.state_lock:
                        running = self.state == AppState.WIFI_ATTACK_RUNNING
                    if not running:
                        break
                    # Get attack status
                    status = self.wifi_attack.get_attack_status()
                    
                    # Update results
                    self.attack_results["clients_connected"] = 0  # In a real implementation, this would be the actual count
                    
                    self._update_display_threadsafe()
                    time.sleep(1)
                
                # Stop attack
                self.wifi_attack.stop_attack()
            
            elif attack_name == "Captive Portal":
                # Run captive portal attack
                self.wifi_attack.start_captive_portal("Free-WiFi", channel=1)
                
                # Monitor clients and credentials
                while True:
                    with self.state_lock:
                        running = self.state == AppState.WIFI_ATTACK_RUNNING
                    if not running:
                        break
                    # Get attack status
                    status = self.wifi_attack.get_attack_status()
                    
                    # Update results
                    self.attack_results["clients_connected"] = 0  # In a real implementation, this would be the actual count
                    self.attack_results["credentials_captured"] = 0  # In a real implementation, this would be the actual count
                    
                    self._update_display_threadsafe()
                    time.sleep(1)
                
                # Stop attack
                self.wifi_attack.stop_attack()
            
            elif attack_name == "Handshake Capture":
                # Run handshake capture attack
                # For demonstration, just capture on channel 1
                self.wifi_attack.start_handshake_capture("00:11:22:33:44:55", 1)
                
                # Monitor capture
                while True:
                    with self.state_lock:
                        running = self.state == AppState.WIFI_ATTACK_RUNNING
                    if not running:
                        break
                    # Get attack status
                    status = self.wifi_attack.get_attack_status()
                    
                    # Update results
                    self.attack_results["capture_status"] = "Waiting for handshake..."
                    
                    self._update_display_threadsafe()
                    time.sleep(1)
                
                # Stop attack
                self.wifi_attack.stop_attack()
            
            elif attack_name == "PMKID Attack":
                # Run PMKID attack
                # For demonstration, just capture on channel 1
                self.wifi_attack.start_pmkid_attack("00:11:22:33:44:55", 1)
                
                # Monitor capture
                while True:
                    with self.state_lock:
                        running = self.state == AppState.WIFI_ATTACK_RUNNING
                    if not running:
                        break
                    # Get attack status
                    status = self.wifi_attack.get_attack_status()
                    
                    # Update results
                    self.attack_results["capture_status"] = "Waiting for PMKID..."
                    
                    self._update_display_threadsafe()
                    time.sleep(1)
                
                # Stop attack
                self.wifi_attack.stop_attack()
        
        except Exception as e:
            logging.error(f"Error running WiFi attack: {e}")
            self.attack_results["error"] = str(e)
            
            # Return to menu
            with self.state_lock:
                self.state = AppState.WIFI_ATTACK_MENU
                self.menu_index = 0
                self.menu_start = 0
            self._update_display_threadsafe()
        finally:
            # Turn off red LED
            self._set_led("red", False)
    
    def _stop_wifi_attack(self):
        """Stop the running WiFi attack."""
        logging.info("Stopping WiFi attack")
        
        if self.wifi_attack:
            self.wifi_attack.stop_attack()
            self.wifi_attack.stop_continuous_scan()
        
        # LED state will be turned off by the WiFi worker thread's finally block
    
    def _signal_handler(self, sig, frame):
        """Handle signals (e.g., SIGINT, SIGTERM).
        
        Args:
            sig: Signal number
            frame: Current stack frame
        """
        logging.info(f"Received signal {sig}, shutting down")
        self._cleanup()
        sys.exit(0)
    
    def _cleanup(self):
        """Clean up resources before exiting."""
        logging.info("Cleaning up resources")
        
        # Stop any running attacks
        if self.wifi_attack:
            self.wifi_attack.cleanup()
        if self.hid_emulator and hasattr(self.hid_emulator, "cleanup"):
            try:
                self.hid_emulator.cleanup()
            except Exception as e:
                logging.debug(f"HID cleanup error: {e}")
        
        # Put display to sleep
        if self.display:
            self.display.clear()
            self.display.draw_centered_text(50, "Goodbye!", font=self.display.font_normal)
            self.display.update()
            time.sleep(1)
            self.display.sleep()
        
        # Set stop event
        self.stop_event.set()
        
        # Turn off LEDs
        self._set_led("red", False)
        self._set_led("green", False)
        
        # Clean up GPIO
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
        except ImportError:
            logging.debug("RPi.GPIO not available; skipping GPIO cleanup.")
        except Exception as e:
            logging.warning(f"GPIO cleanup failed: {e}")
    
    def run(self):
        """Run the application main loop."""
        logging.info("Starting Natasha AI Penetration Testing Tool")
        
        # Show main menu
        self.state = AppState.MAIN_MENU
        self._update_display()
        
        # Set green LED to indicate ready
        self._set_led("green", True)
        
        # Main loop
        try:
            while True:
                # Process events
                time.sleep(0.1)
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received, shutting down")
            self._cleanup()
            sys.exit(0)


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Natasha AI Penetration Testing Tool")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Bind external MITM UI handlers if available
    try:
        import mitm_attack_methods as mam
        # Expose AppState enum to the external methods module to avoid NameError
        mam.AppState = AppState
        NatashaApp._show_mitm_attack_menu = mam._show_mitm_attack_menu
        NatashaApp._handle_mitm_attack_menu_button = mam._handle_mitm_attack_menu_button
        NatashaApp._show_mitm_attack_config = mam._show_mitm_attack_config
        NatashaApp._handle_mitm_attack_config_button = mam._handle_mitm_attack_config_button
        NatashaApp._show_mitm_attack_running = mam._show_mitm_attack_running
        NatashaApp._handle_mitm_attack_running_button = mam._handle_mitm_attack_running_button
        NatashaApp._start_mitm_attack = mam._start_mitm_attack
        NatashaApp._stop_mitm_attack = mam._stop_mitm_attack
    except Exception as e:
        logging.debug(f"MITM methods binding skipped: {e}")

    # Create and run the application
    app = NatashaApp()
    app.run()