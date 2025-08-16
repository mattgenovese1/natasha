#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Natasha AI Penetration Testing Tool
E-Paper Display Interface Module

This module handles the interface with the Waveshare 2.13-inch e-paper display,
providing functions for rendering the UI, displaying text and graphics, and
managing screen updates efficiently.
"""

import os
import time
import logging
from PIL import Image, ImageDraw, ImageFont
import threading

# Import the Waveshare e-paper library
# Note: This requires the Waveshare library to be installed
try:
    from waveshare_epd import epd2in13_V4 as epd_driver
except ImportError:
    logging.error("Waveshare e-paper library not found. Install it from: "
                 "https://github.com/waveshare/e-Paper")
    raise

class DisplayInterface:
    """Interface for the Waveshare 2.13-inch e-paper display."""
    
    # Display dimensions
    WIDTH = 250
    HEIGHT = 122
    
    # UI element dimensions
    HEADER_HEIGHT = 15
    FOOTER_HEIGHT = 12
    AVATAR_SIZE = 40
    
    # Refresh types
    FULL_REFRESH = 0
    PARTIAL_REFRESH = 1
    
    def __init__(self):
        """Initialize the display interface."""
        self.epd = None
        self.image = None
        self.draw = None
        self.font_small = None
        self.font_normal = None
        self.font_large = None
        self.lock = threading.Lock()
        self.last_full_refresh = 0
        self.refresh_count = 0
        
        # Initialize the display
        self._init_display()
        
    def _init_display(self):
        """Initialize the e-paper display and load resources."""
        try:
            # Initialize the e-paper driver
            self.epd = epd_driver.EPD()
            self.epd.init()
            
            # Clear the display with a white background
            self.epd.Clear(0xFF)
            
            # Create a new image with white background
            self.image = Image.new('1', (self.WIDTH, self.HEIGHT), 255)
            self.draw = ImageDraw.Draw(self.image)
            
            # Load fonts
            font_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'fonts')
            self.font_small = ImageFont.truetype(os.path.join(font_dir, 'DejaVuSansMono.ttf'), 8)
            self.font_normal = ImageFont.truetype(os.path.join(font_dir, 'DejaVuSansMono.ttf'), 12)
            self.font_large = ImageFont.truetype(os.path.join(font_dir, 'DejaVuSansMono.ttf'), 16)
            
            logging.info("E-paper display initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize e-paper display: {e}")
            raise
    
    def clear(self, refresh=True):
        """Clear the display with a white background."""
        with self.lock:
            self.image = Image.new('1', (self.WIDTH, self.HEIGHT), 255)
            self.draw = ImageDraw.Draw(self.image)
            if refresh:
                self._refresh(self.FULL_REFRESH)
    
    def _refresh(self, refresh_type=PARTIAL_REFRESH):
        """Refresh the display with the current image.
        
        Args:
            refresh_type: Type of refresh to perform (FULL_REFRESH or PARTIAL_REFRESH)
        """
        try:
            current_time = time.time()
            
            # Force a full refresh every 5 partial refreshes or if it's been more than 5 minutes
            if (refresh_type == self.PARTIAL_REFRESH and 
                (self.refresh_count >= 5 or current_time - self.last_full_refresh > 300)):
                refresh_type = self.FULL_REFRESH
            
            if refresh_type == self.FULL_REFRESH:
                self.epd.display(self.epd.getbuffer(self.image))
                self.last_full_refresh = current_time
                self.refresh_count = 0
            else:
                self.epd.displayPartial(self.epd.getbuffer(self.image))
                self.refresh_count += 1
                
        except Exception as e:
            logging.error(f"Failed to refresh display: {e}")
    
    def draw_text(self, x, y, text, font=None, fill=0):
        """Draw text on the display.
        
        Args:
            x: X coordinate
            y: Y coordinate
            text: Text to display
            font: Font to use (defaults to normal font)
            fill: Color (0 for black, 255 for white)
        """
        if font is None:
            font = self.font_normal
        
        with self.lock:
            self.draw.text((x, y), text, font=font, fill=fill)
    
    def draw_centered_text(self, y, text, font=None, fill=0):
        """Draw horizontally centered text on the display.
        
        Args:
            y: Y coordinate
            text: Text to display
            font: Font to use (defaults to normal font)
            fill: Color (0 for black, 255 for white)
        """
        if font is None:
            font = self.font_normal
        
        with self.lock:
            text_width = self.draw.textlength(text, font=font)
            x = (self.WIDTH - text_width) // 2
            self.draw.text((x, y), text, font=font, fill=fill)
    
    def draw_rectangle(self, x0, y0, x1, y1, outline=0, fill=None):
        """Draw a rectangle on the display.
        
        Args:
            x0, y0: Top-left corner coordinates
            x1, y1: Bottom-right corner coordinates
            outline: Outline color (0 for black, 255 for white)
            fill: Fill color (0 for black, 255 for white, None for transparent)
        """
        with self.lock:
            self.draw.rectangle((x0, y0, x1, y1), outline=outline, fill=fill)
    
    def draw_line(self, x0, y0, x1, y1, fill=0, width=1):
        """Draw a line on the display.
        
        Args:
            x0, y0: Start point coordinates
            x1, y1: End point coordinates
            fill: Line color (0 for black, 255 for white)
            width: Line width in pixels
        """
        with self.lock:
            self.draw.line((x0, y0, x1, y1), fill=fill, width=width)
    
    def draw_image(self, x, y, image_path):
        """Draw an image on the display.
        
        Args:
            x, y: Top-left corner coordinates
            image_path: Path to the image file
        """
        try:
            with self.lock:
                img = Image.open(image_path).convert('1')
                self.image.paste(img, (x, y))
        except Exception as e:
            logging.error(f"Failed to draw image {image_path}: {e}")
    
    def update(self, refresh_type=PARTIAL_REFRESH):
        """Update the display with the current image.
        
        Args:
            refresh_type: Type of refresh to perform (FULL_REFRESH or PARTIAL_REFRESH)
        """
        with self.lock:
            self._refresh(refresh_type)
    
    def draw_header(self, title, battery_level=None, wifi_status=None):
        """Draw the header bar with title and status icons.
        
        Args:
            title: Title text to display
            battery_level: Battery level (0-100) or None to hide
            wifi_status: WiFi status (True/False) or None to hide
        """
        with self.lock:
            # Draw header background
            self.draw_rectangle(0, 0, self.WIDTH-1, self.HEADER_HEIGHT, outline=0, fill=0)
            
            # Draw title
            self.draw_text(3, 2, title, font=self.font_small, fill=255)
            
            # Draw battery indicator if provided
            if battery_level is not None:
                # Battery outline
                self.draw_rectangle(self.WIDTH-19, 2, self.WIDTH-3, 12, outline=255, fill=None)
                # Battery level
                level_width = int((battery_level / 100) * 14)
                if level_width > 0:
                    self.draw_rectangle(self.WIDTH-18, 3, self.WIDTH-18+level_width, 11, outline=None, fill=255)
            
            # Draw WiFi indicator if provided
            if wifi_status is not None:
                if wifi_status:
                    # Connected WiFi icon
                    for i in range(3):
                        self.draw_rectangle(self.WIDTH-30-i*3, 9-i*3, self.WIDTH-24+i*3, 12, outline=255, fill=None)
                else:
                    # Disconnected WiFi icon
                    self.draw_line(self.WIDTH-30, 3, self.WIDTH-24, 12, fill=255)
                    self.draw_line(self.WIDTH-24, 3, self.WIDTH-30, 12, fill=255)
    
    def draw_footer(self, left_text=None, center_text=None, right_text=None):
        """Draw the footer bar with button labels.
        
        Args:
            left_text: Text for left button
            center_text: Text for center button
            right_text: Text for right button
        """
        with self.lock:
            # Draw footer line
            self.draw_line(0, self.HEIGHT-self.FOOTER_HEIGHT, self.WIDTH, self.HEIGHT-self.FOOTER_HEIGHT, fill=0)
            
            # Draw button labels
            if left_text:
                self.draw_text(3, self.HEIGHT-self.FOOTER_HEIGHT+2, left_text, font=self.font_small)
            
            if center_text:
                self.draw_centered_text(self.HEIGHT-self.FOOTER_HEIGHT+2, center_text, font=self.font_small)
            
            if right_text:
                text_width = self.draw.textlength(right_text, font=self.font_small)
                self.draw_text(self.WIDTH-text_width-3, self.HEIGHT-self.FOOTER_HEIGHT+2, right_text, font=self.font_small)
    
    def draw_menu(self, title, items, selected_index=0, start_index=0, max_items=5):
        """Draw a menu with selectable items.
        
        Args:
            title: Menu title
            items: List of menu items
            selected_index: Index of the selected item
            start_index: Index of the first visible item
            max_items: Maximum number of visible items
        """
        with self.lock:
            # Draw header
            self.draw_header(title)
            
            # Calculate visible items
            visible_items = items[start_index:start_index+max_items]
            
            # Draw menu items
            for i, item in enumerate(visible_items):
                y = self.HEADER_HEIGHT + 5 + i * 18
                
                # Highlight selected item
                if start_index + i == selected_index:
                    self.draw_rectangle(0, y-2, self.WIDTH, y+16, outline=None, fill=0)
                    self.draw_text(5, y, item, font=self.font_normal, fill=255)
                else:
                    self.draw_text(5, y, item, font=self.font_normal)
            
            # Draw scrollbar if needed
            if len(items) > max_items:
                scrollbar_height = (max_items / len(items)) * (self.HEIGHT - self.HEADER_HEIGHT - self.FOOTER_HEIGHT)
                scrollbar_pos = ((start_index / (len(items) - max_items)) * 
                                (self.HEIGHT - self.HEADER_HEIGHT - self.FOOTER_HEIGHT - scrollbar_height))
                
                self.draw_rectangle(self.WIDTH-5, 
                                   self.HEADER_HEIGHT + scrollbar_pos,
                                   self.WIDTH-2, 
                                   self.HEADER_HEIGHT + scrollbar_pos + scrollbar_height,
                                   outline=None, fill=0)
            
            # Draw footer with navigation hints
            self.draw_footer("↑", "SELECT", "↓")
    
    def draw_natasha_avatar(self, x, y, expression="normal"):
        """Draw Natasha's avatar with the specified expression.
        
        Args:
            x, y: Top-left corner coordinates
            expression: Avatar expression ("normal", "thinking", "success", "warning")
        """
        with self.lock:
            # Draw avatar background
            self.draw_rectangle(x, y, x+self.AVATAR_SIZE, y+self.AVATAR_SIZE, outline=0, fill=None)
            
            # Basic face outline
            self.draw_rectangle(x+5, y+5, x+self.AVATAR_SIZE-5, y+self.AVATAR_SIZE-5, outline=0, fill=None)
            
            # Draw eyes
            if expression == "normal":
                # Normal eyes
                self.draw_rectangle(x+10, y+15, x+15, y+20, outline=0, fill=0)
                self.draw_rectangle(x+25, y+15, x+30, y+20, outline=0, fill=0)
            elif expression == "thinking":
                # Thinking eyes (one raised eyebrow)
                self.draw_rectangle(x+10, y+17, x+15, y+22, outline=0, fill=0)
                self.draw_rectangle(x+25, y+13, x+30, y+18, outline=0, fill=0)
            elif expression == "success":
                # Happy eyes
                self.draw_line(x+10, y+15, x+15, y+20, fill=0)
                self.draw_line(x+10, y+20, x+15, y+15, fill=0)
                self.draw_line(x+25, y+15, x+30, y+20, fill=0)
                self.draw_line(x+25, y+20, x+30, y+15, fill=0)
            elif expression == "warning":
                # Warning eyes
                self.draw_rectangle(x+10, y+15, x+15, y+20, outline=0, fill=0)
                self.draw_rectangle(x+25, y+15, x+30, y+20, outline=0, fill=0)
                self.draw_line(x+5, y+10, x+15, y+5, fill=0)
                self.draw_line(x+25, y+5, x+35, y+10, fill=0)
            
            # Draw mouth
            if expression == "normal":
                self.draw_line(x+15, y+30, x+25, y+30, fill=0)
            elif expression == "thinking":
                self.draw_line(x+15, y+30, x+20, y+32, fill=0)
                self.draw_line(x+20, y+32, x+25, y+30, fill=0)
            elif expression == "success":
                self.draw_line(x+15, y+28, x+20, y+32, fill=0)
                self.draw_line(x+20, y+32, x+25, y+28, fill=0)
            elif expression == "warning":
                self.draw_line(x+15, y+32, x+20, y+28, fill=0)
                self.draw_line(x+20, y+28, x+25, y+32, fill=0)
            
            # Draw hair (simple for e-paper display)
            self.draw_line(x+5, y+5, x+5, y+15, fill=0)
            self.draw_line(x+35, y+5, x+35, y+15, fill=0)
            self.draw_line(x+10, y+3, x+30, y+3, fill=0)
    
    def draw_progress_bar(self, x, y, width, progress, max_value=100):
        """Draw a progress bar.
        
        Args:
            x, y: Top-left corner coordinates
            width: Width of the progress bar
            progress: Current progress value
            max_value: Maximum progress value
        """
        with self.lock:
            # Draw outline
            self.draw_rectangle(x, y, x+width, y+10, outline=0, fill=None)
            
            # Draw progress
            progress_width = int((progress / max_value) * (width - 2))
            if progress_width > 0:
                self.draw_rectangle(x+1, y+1, x+1+progress_width, y+9, outline=None, fill=0)
            
            # Draw percentage text
            percentage = f"{int(progress / max_value * 100)}%"
            text_width = self.draw.textlength(percentage, font=self.font_small)
            text_x = x + (width - text_width) // 2
            self.draw_text(text_x, y+1, percentage, font=self.font_small, fill=255 if progress_width > text_width else 0)
    
    def draw_status_screen(self, title, status_items, battery_level=None, wifi_status=None):
        """Draw a status screen with multiple information items.
        
        Args:
            title: Screen title
            status_items: List of (label, value) tuples
            battery_level: Battery level (0-100) or None to hide
            wifi_status: WiFi status (True/False) or None to hide
        """
        with self.lock:
            # Draw header
            self.draw_header(title, battery_level, wifi_status)
            
            # Draw status items
            for i, (label, value) in enumerate(status_items):
                y = self.HEADER_HEIGHT + 5 + i * 16
                
                # Draw label
                self.draw_text(5, y, f"{label}:", font=self.font_normal)
                
                # Draw value (truncate if too long)
                max_value_width = self.WIDTH - 10 - self.draw.textlength(f"{label}:", font=self.font_normal)
                value_text = value
                while self.draw.textlength(value_text + "...", font=self.font_normal) > max_value_width and len(value_text) > 0:
                    value_text = value_text[:-1]
                
                if value_text != value:
                    value_text += "..."
                
                self.draw_text(10 + self.draw.textlength(f"{label}:", font=self.font_normal), y, value_text, font=self.font_normal)
            
            # Draw footer
            self.draw_footer(None, "BACK", None)
    
    def draw_splash_screen(self):
        """Draw the Natasha splash screen."""
        with self.lock:
            # Clear the display
            self.image = Image.new('1', (self.WIDTH, self.HEIGHT), 255)
            self.draw = ImageDraw.Draw(self.image)
            
            # Draw title
            self.draw_centered_text(20, "NATASHA", font=self.font_large)
            self.draw_centered_text(40, "AI Penetration Testing Tool", font=self.font_normal)
            
            # Draw version
            self.draw_centered_text(70, "v1.0", font=self.font_small)
            
            # Draw footer text
            self.draw_centered_text(100, "© 2025 NinjaTech AI", font=self.font_small)
            
            # Update the display with a full refresh
            self._refresh(self.FULL_REFRESH)
    
    def sleep(self):
        """Put the display to sleep to save power."""
        try:
            self.epd.sleep()
            logging.info("E-paper display put to sleep")
        except Exception as e:
            logging.error(f"Failed to put display to sleep: {e}")
    
    def wake(self):
        """Wake the display from sleep."""
        try:
            self.epd.init()
            logging.info("E-paper display woken from sleep")
        except Exception as e:
            logging.error(f"Failed to wake display: {e}")
    
    def __del__(self):
        """Clean up resources when the object is destroyed."""
        if hasattr(self, 'epd') and self.epd is not None:
            try:
                self.epd.sleep()
                logging.info("E-paper display put to sleep during cleanup")
            except:
                pass


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize the display
    display = DisplayInterface()
    
    # Show splash screen
    display.draw_splash_screen()
    time.sleep(2)
    
    # Show a menu
    menu_items = [
        "USB Attacks",
        "WiFi Attacks",
        "System Information",
        "Credential Harvesting",
        "Backdoor Generator",
        "Settings"
    ]
    display.clear()
    display.draw_menu("Natasha Main Menu", menu_items, selected_index=0)
    display.update()
    time.sleep(2)
    
    # Show a status screen
    status_items = [
        ("Battery", "85%"),
        ("WiFi", "Connected"),
        ("USB", "HID Mode"),
        ("Storage", "28.2 GB Free"),
        ("Uptime", "2h 15m"),
        ("IP Address", "192.168.1.100")
    ]
    display.clear()
    display.draw_status_screen("System Status", status_items, battery_level=85, wifi_status=True)
    display.update()
    time.sleep(2)
    
    # Show an attack screen with Natasha avatar
    display.clear()
    display.draw_header("USB Attack")
    display.draw_natasha_avatar(200, 30, expression="thinking")
    display.draw_text(10, 30, "Target: Windows 10", font=display.font_normal)
    display.draw_text(10, 50, "Attack: Credential Harvest", font=display.font_normal)
    display.draw_text(10, 70, "Status: Running", font=display.font_normal)
    display.draw_progress_bar(10, 90, 180, 60)
    display.draw_footer("ABORT", None, None)
    display.update()
    time.sleep(2)
    
    # Clean up
    display.clear()
    display.draw_centered_text(50, "Shutting down...", font=display.font_normal)
    display.update()
    time.sleep(1)
    display.sleep()