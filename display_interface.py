#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Natasha AI Penetration Testing Tool
E-Paper Display Interface Module

This module handles the interface with the Waveshare 2.13-inch e-paper display,
providing functions for rendering the UI, displaying text and graphics, and
managing screen updates efficiently.

Enhancements:
- Graceful mock mode when hardware driver is unavailable (development-friendly)
- Configurable partial/full refresh policy
- Font loading with fallbacks
- Thread-safe drawing and hardware refresh with minimal retries
- Text wrapping helper and optional clipping
- Image fitting/scaling options
- Explicit close() to release hardware resources
"""

import os
import time
import logging
import threading
from typing import Optional, Tuple, List

from PIL import Image, ImageDraw, ImageFont

# Try to import the Waveshare e-paper library
try:
    from waveshare_epd import epd2in13_V4 as epd_driver
    EPD_AVAILABLE = True
except ImportError:
    logging.warning(
        "Waveshare e-paper library not found. Running in mock display mode."
    )
    EPD_AVAILABLE = False

# Try to import character animation controller
try:
    from characters.character_animation import AnimationController, CharacterState
    ANIMATION_AVAILABLE = True
except ImportError:
    logging.warning(
        "Character animation controller not found. Running without animation support."
    )
    ANIMATION_AVAILABLE = False


class _MockEPD:
    """Mock EPD driver for development environments without hardware."""

    class _EPD:
        def __init__(self):
            self._last = None

        def init(self):
            logging.info("[MOCK EPD] init() called")

        def Clear(self, color):
            logging.info(f"[MOCK EPD] Clear({color}) called")

        def getbuffer(self, image):
            return image

        def display(self, buffer):
            logging.info("[MOCK EPD] display() full refresh")
            self._last = buffer

        def displayPartial(self, buffer):
            logging.info("[MOCK EPD] displayPartial()")
            self._last = buffer

        def sleep(self):
            logging.info("[MOCK EPD] sleep() called")

        def Dev_exit(self):
            logging.info("[MOCK EPD] Dev_exit() called")

    @staticmethod
    def EPD():
        return _MockEPD._EPD()


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

    def __init__(
        self,
        max_partial_before_full: int = 5,
        full_refresh_interval_sec: int = 300,
        mock_mode: Optional[bool] = None,
        font_dir: Optional[str] = None,
    ):
        """Initialize the display interface.

        Args:
            max_partial_before_full: number of partial refreshes before forcing a full refresh
            full_refresh_interval_sec: time in seconds to force a full refresh
            mock_mode: force mock mode if True; auto if None
            font_dir: directory containing TTF fonts; defaults to ./fonts next to this file
        """
        self._mock_mode = (not EPD_AVAILABLE) if mock_mode is None else bool(mock_mode)
        self.max_partial_before_full = max_partial_before_full
        self.full_refresh_interval_sec = full_refresh_interval_sec

        self.epd = None
        self.image: Optional[Image.Image] = None
        self.draw: Optional[ImageDraw.ImageDraw] = None
        self.font_small: Optional[ImageFont.ImageFont] = None
        self.font_normal: Optional[ImageFont.ImageFont] = None
        self.font_large: Optional[ImageFont.ImageFont] = None
        self.lock = threading.RLock()
        self.last_full_refresh = 0.0
        self.refresh_count = 0

        # Resolve font directory
        self._font_dir = (
            font_dir
            if font_dir
            else os.path.join(os.path.dirname(os.path.realpath(__file__)), "fonts")
        )

        # Initialize character animation controller if available
        if ANIMATION_AVAILABLE:
            self.animation_controller = AnimationController()
        else:
            self.animation_controller = None

        # Initialize the display
        self._init_display()

    def _init_display(self):
        """Initialize the e-paper display and load resources."""
        try:
            # Initialize driver
            if self._mock_mode:
                self.epd = _MockEPD.EPD()
            else:
                self.epd = epd_driver.EPD()

            # Try init with a small retry loop (helps transient failures)
            for attempt in range(2):
                try:
                    self.epd.init()
                    break
                except Exception as e:
                    if attempt == 1:
                        raise
                    logging.warning(f"EPD init retry due to: {e}")
                    time.sleep(0.2)

            # Clear the display with a white background
            self.epd.Clear(0xFF)

            # Create a new image with white background
            self.image = Image.new("1", (self.WIDTH, self.HEIGHT), 255)
            self.draw = ImageDraw.Draw(self.image)

            # Load fonts with fallbacks
            self._load_fonts()

            logging.info(
                "E-paper display initialized successfully" + (" (mock)" if self._mock_mode else "")
            )
        except Exception as e:
            logging.error(f"Failed to initialize e-paper display: {e}")
            # Fallback to mock if hardware init fails unexpectedly
            if not self._mock_mode:
                logging.warning("Falling back to mock display mode due to init failure.")
                self._mock_mode = True
                self._init_display()
            else:
                raise

    def _load_fonts(self):
        """Load TTF fonts with safe fallbacks to default PIL font."""
        def _try_load(size: int) -> ImageFont.ImageFont:
            try:
                return ImageFont.truetype(os.path.join(self._font_dir, "DejaVuSansMono.ttf"), size)
            except Exception:
                logging.warning(
                    f"TTF font not found/failed to load at size {size}; using default bitmap font."
                )
                return ImageFont.load_default()

        self.font_small = _try_load(8)
        self.font_normal = _try_load(12)
        self.font_large = _try_load(16)

    def clear(self, refresh: bool = True):
        """Clear the display with a white background."""
        with self.lock:
            self.image = Image.new("1", (self.WIDTH, self.HEIGHT), 255)
            self.draw = ImageDraw.Draw(self.image)
            if refresh:
                self._refresh(self.FULL_REFRESH)

    def _refresh(self, refresh_type: int = PARTIAL_REFRESH):
        """Refresh the display with the current image.

        Args:
            refresh_type: Type of refresh to perform (FULL_REFRESH or PARTIAL_REFRESH)
        """
        try:
            current_time = time.time()

            # Force a full refresh per policy
            if (
                refresh_type == self.PARTIAL_REFRESH
                and (
                    self.refresh_count >= self.max_partial_before_full
                    or current_time - self.last_full_refresh > self.full_refresh_interval_sec
                )
            ):
                refresh_type = self.FULL_REFRESH

            # Perform refresh with minimal retry for stability
            for attempt in range(2):
                try:
                    if refresh_type == self.FULL_REFRESH:
                        self.epd.display(self.epd.getbuffer(self.image))
                        self.last_full_refresh = current_time
                        self.refresh_count = 0
                    else:
                        self.epd.displayPartial(self.epd.getbuffer(self.image))
                        self.refresh_count += 1
                    break
                except Exception as e:
                    if attempt == 0:
                        logging.warning(f"EPD refresh error, attempting re-init: {e}")
                        try:
                            self.epd.init()
                        except Exception as e2:
                            logging.error(f"EPD re-init failed: {e2}")
                            raise
                    else:
                        raise
        except Exception as e:
            logging.error(f"Failed to refresh display: {e}")

    
    def draw_wrapped_text(
        self,
        x: int,
        y: int,
        text: str,
        font: Optional[ImageFont.ImageFont] = None,
        fill: int = 0,
        max_width: Optional[int] = None,
        line_spacing: int = 2,
    ) -> int:
        """Draw word-wrapped text within max_width. Returns bottom y of the drawn block.

        Args:
            x, y: top-left position
            text: text to draw
            font: font to use (defaults to normal)
            fill: color
            max_width: maximum width for wrapping; if None, no wrapping
            line_spacing: spacing between lines in pixels
        """
        if font is None:
            font = self.font_normal
        if not max_width:
            with self.lock:
                self.draw.text((x, y), text, font=font, fill=fill)
            return y + font.size

        words = text.split()
        lines: List[str] = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if self.draw.textlength(test, font=font) <= max_width or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)

        with self.lock:
            yy = y
            for line in lines:
                self.draw.text((x, yy), line, font=font, fill=fill)
                yy += font.size + line_spacing
        return yy

    def draw_centered_text(self, y: int, text: str, font: Optional[ImageFont.ImageFont] = None, fill: int = 0):
        """Draw horizontally centered text on the display."""
        if font is None:
            font = self.font_normal

        with self.lock:
            text_width = self.draw.textlength(text, font=font)
            x = (self.WIDTH - text_width) // 2
            self.draw.text((x, y), text, font=font, fill=fill)

    def draw_text(self, x: int, y: int, text: str, font: Optional[ImageFont.ImageFont] = None, fill: int = 0, max_width: Optional[int] = None, ellipsis: bool = False):
        """Draw text with optional width constraint and ellipsis.

        Args:
            x, y: top-left position
            text: text to draw
            font: PIL font to use (defaults to normal)
            fill: color (0=black, 255=white)
            max_width: if provided, constrain to this width
            ellipsis: if True, show '...' when truncated
        """
        if font is None:
            font = self.font_normal
        with self.lock:
            if not max_width:
                self.draw.text((x, y), text, font=font, fill=fill)
                return
            # Fits as-is
            if self.draw.textlength(text, font=font) <= max_width:
                self.draw.text((x, y), text, font=font, fill=fill)
                return
            if ellipsis:
                ell = "..."
                ell_w = self.draw.textlength(ell, font=font)
                if ell_w >= max_width:
                    return
                lo, hi = 0, len(text)
                best = 0
                while lo <= hi:
                    mid = (lo + hi) // 2
                    if self.draw.textlength(text[:mid], font=font) + ell_w <= max_width:
                        best = mid
                        lo = mid + 1
                    else:
                        hi = mid - 1
                clipped = text[:best] + ell
                self.draw.text((x, y), clipped, font=font, fill=fill)
            else:
                lo, hi = 0, len(text)
                best = 0
                while lo <= hi:
                    mid = (lo + hi) // 2
                    if self.draw.textlength(text[:mid], font=font) <= max_width:
                        best = mid
                        lo = mid + 1
                    else:
                        hi = mid - 1
                if best > 0:
                    self.draw.text((x, y), text[:best], font=font, fill=fill)

    def draw_rectangle(self, x0: int, y0: int, x1: int, y1: int, outline: int = 0, fill: Optional[int] = None):
        """Draw a rectangle on the display."""
        with self.lock:
            self.draw.rectangle((x0, y0, x1, y1), outline=outline, fill=fill)

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, fill: int = 0, width: int = 1):
        """Draw a line on the display."""
        with self.lock:
            self.draw.line((x0, y0, x1, y1), fill=fill, width=width)

    def draw_image(
        self,
        x: int,
        y: int,
        image_path: str,
        fit: bool = False,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
    ) -> None:
        """Draw an image on the display.

        Args:
            x, y: Top-left corner coordinates
            image_path: Path to the image file
            fit: If True, scale image to fit within (max_width, max_height) or remaining screen
            max_width, max_height: Optional fit bounds; defaults to screen bounds from (x, y)
        """
        try:
            img = Image.open(image_path).convert("1")
            if fit:
                avail_w = (max_width if max_width is not None else (self.WIDTH - x))
                avail_h = (max_height if max_height is not None else (self.HEIGHT - y))
                if avail_w > 0 and avail_h > 0:
                    img.thumbnail((avail_w, avail_h))
            with self.lock:
                self.image.paste(img, (x, y))
        except Exception as e:
            logging.error(f"Failed to draw image {image_path}: {e}")

    def update(self, refresh_type: int = PARTIAL_REFRESH):
        """Update the display with the current image."""
        with self.lock:
            self._refresh(refresh_type)

    def draw_header(self, title: str, battery_level: Optional[int] = None, wifi_status: Optional[bool] = None):
        """Draw the header bar with title and status icons."""
        with self.lock:
            # Draw header background
            self.draw_rectangle(0, 0, self.WIDTH - 1, self.HEADER_HEIGHT, outline=0, fill=0)

            # Draw title
            self.draw_text(3, 2, title, font=self.font_small, fill=255, max_width=self.WIDTH - 60, ellipsis=True)

            # Draw battery indicator if provided
            if battery_level is not None:
                # Battery outline
                self.draw_rectangle(self.WIDTH - 19, 2, self.WIDTH - 3, 12, outline=255, fill=None)
                # Battery level
                level_width = max(0, min(14, int((battery_level / 100) * 14)))
                if level_width > 0:
                    self.draw_rectangle(self.WIDTH - 18, 3, self.WIDTH - 18 + level_width, 11, outline=None, fill=255)

            # Draw WiFi indicator if provided
            if wifi_status is not None:
                if wifi_status:
                    # Connected WiFi icon
                    for i in range(3):
                        self.draw_rectangle(self.WIDTH - 30 - i * 3, 9 - i * 3, self.WIDTH - 24 + i * 3, 12, outline=255, fill=None)
                else:
                    # Disconnected WiFi icon
                    self.draw_line(self.WIDTH - 30, 3, self.WIDTH - 24, 12, fill=255)
                    self.draw_line(self.WIDTH - 24, 3, self.WIDTH - 30, 12, fill=255)

    def draw_footer(self, left_text: Optional[str] = None, center_text: Optional[str] = None, right_text: Optional[str] = None):
        """Draw the footer bar with button labels."""
        with self.lock:
            # Draw footer line
            self.draw_line(0, self.HEIGHT - self.FOOTER_HEIGHT, self.WIDTH, self.HEIGHT - self.FOOTER_HEIGHT, fill=0)

            # Draw button labels
            if left_text:
                self.draw_text(3, self.HEIGHT - self.FOOTER_HEIGHT + 2, left_text, font=self.font_small)

            if center_text:
                self.draw_centered_text(self.HEIGHT - self.FOOTER_HEIGHT + 2, center_text, font=self.font_small)

            if right_text:
                text_width = self.draw.textlength(right_text, font=self.font_small)
                self.draw_text(self.WIDTH - text_width - 3, self.HEIGHT - self.FOOTER_HEIGHT + 2, right_text, font=self.font_small)

    def draw_menu(
        self,
        title: str,
        items: List[str],
        selected_index: int = 0,
        start_index: int = 0,
        max_items: int = 5,
        footer_labels: Tuple[Optional[str], Optional[str], Optional[str]] = ("↑", "SELECT", "↓"),
    ) -> None:
        """Draw a menu with selectable items."""
        with self.lock:
            # Draw header
            self.draw_header(title)

            # Calculate visible items
            visible_items = items[start_index : start_index + max_items]

            # Draw menu items
            for i, item in enumerate(visible_items):
                y = self.HEADER_HEIGHT + 5 + i * 18

                # Highlight selected item
                if start_index + i == selected_index:
                    self.draw_rectangle(0, y - 2, self.WIDTH, y + 16, outline=None, fill=0)
                    self.draw_text(5, y, item, font=self.font_normal, fill=255, max_width=self.WIDTH - 10, ellipsis=True)
                else:
                    self.draw_text(5, y, item, font=self.font_normal, max_width=self.WIDTH - 10, ellipsis=True)

            # Draw scrollbar if needed
            if len(items) > max_items:
                track_h = self.HEIGHT - self.HEADER_HEIGHT - self.FOOTER_HEIGHT
                scrollbar_height = (max_items / len(items)) * track_h
                denom = max(1, (len(items) - max_items))
                scrollbar_pos = (start_index / denom) * (track_h - scrollbar_height)

                self.draw_rectangle(
                    self.WIDTH - 5,
                    self.HEADER_HEIGHT + int(scrollbar_pos),
                    self.WIDTH - 2,
                    self.HEADER_HEIGHT + int(scrollbar_pos + scrollbar_height),
                    outline=None,
                    fill=0,
                )

            # Draw footer with navigation hints
            self.draw_footer(*footer_labels)

    def draw_natasha_avatar(self, x: int, y: int, expression: str = "normal"):
        """Draw Natasha's avatar with the specified expression."""
        with self.lock:
            # Draw avatar background
            self.draw_rectangle(x, y, x + self.AVATAR_SIZE, y + self.AVATAR_SIZE, outline=0, fill=None)

            # Basic face outline
            self.draw_rectangle(x + 5, y + 5, x + self.AVATAR_SIZE - 5, y + self.AVATAR_SIZE - 5, outline=0, fill=None)

            # Draw eyes
            if expression == "normal":
                self.draw_rectangle(x + 10, y + 15, x + 15, y + 20, outline=0, fill=0)
                self.draw_rectangle(x + 25, y + 15, x + 30, y + 20, outline=0, fill=0)
            elif expression == "thinking":
                self.draw_rectangle(x + 10, y + 17, x + 15, y + 22, outline=0, fill=0)
                self.draw_rectangle(x + 25, y + 13, x + 30, y + 18, outline=0, fill=0)
            elif expression == "success":
                self.draw_line(x + 10, y + 15, x + 15, y + 20, fill=0)
                self.draw_line(x + 10, y + 20, x + 15, y + 15, fill=0)
                self.draw_line(x + 25, y + 15, x + 30, y + 20, fill=0)
                self.draw_line(x + 25, y + 20, x + 30, y + 15, fill=0)
            elif expression == "warning":
                self.draw_rectangle(x + 10, y + 15, x + 15, y + 20, outline=0, fill=0)
                self.draw_rectangle(x + 25, y + 15, x + 30, y + 20, outline=0, fill=0)
                self.draw_line(x + 5, y + 10, x + 15, y + 5, fill=0)
                self.draw_line(x + 25, y + 5, x + 35, y + 10, fill=0)

            # Draw mouth
            if expression == "normal":
                self.draw_line(x + 15, y + 30, x + 25, y + 30, fill=0)
            elif expression == "thinking":
                self.draw_line(x + 15, y + 30, x + 20, y + 32, fill=0)
                self.draw_line(x + 20, y + 32, x + 25, y + 30, fill=0)
            elif expression == "success":
                self.draw_line(x + 15, y + 28, x + 20, y + 32, fill=0)
                self.draw_line(x + 20, y + 32, x + 25, y + 28, fill=0)
            elif expression == "warning":
                self.draw_line(x + 15, y + 32, x + 20, y + 28, fill=0)
                self.draw_line(x + 20, y + 28, x + 25, y + 32, fill=0)

            # Draw hair (simple for e-paper display)
            self.draw_line(x + 5, y + 5, x + 5, y + 15, fill=0)
            self.draw_line(x + 35, y + 5, x + 35, y + 15, fill=0)
            self.draw_line(x + 10, y + 3, x + 30, y + 3, fill=0)

    def draw_progress_bar(self, x: int, y: int, width: int, progress: int, max_value: int = 100):
        """Draw a progress bar."""
        with self.lock:
            # Draw outline
            self.draw_rectangle(x, y, x + width, y + 10, outline=0, fill=None)

            # Draw progress
            progress = max(0, min(max_value, progress))
            inner_w = max(0, width - 2)
            progress_width = int((progress / max_value) * inner_w)
            if progress_width > 0:
                self.draw_rectangle(x + 1, y + 1, x + 1 + progress_width, y + 9, outline=None, fill=0)

            # Draw percentage text
            percentage = f"{int(progress / max_value * 100)}%"
            text_width = self.draw.textlength(percentage, font=self.font_small)
            text_x = x + (width - text_width) // 2
            self.draw_text(
                text_x,
                y + 1,
                percentage,
                font=self.font_small,
                fill=255 if progress_width > text_width else 0,
            )

    def draw_status_screen(
        self,
        title: str,
        status_items: List[Tuple[str, str]],
        battery_level: Optional[int] = None,
        wifi_status: Optional[bool] = None,
    ) -> None:
        """Draw a status screen with multiple information items."""
        with self.lock:
            # Draw header
            self.draw_header(title, battery_level, wifi_status)

            # Draw status items
            for i, (label, value) in enumerate(status_items):
                y = self.HEADER_HEIGHT + 5 + i * 16

                # Draw label
                self.draw_text(5, y, f"{label}:", font=self.font_normal)

                # Draw value (truncate if too long)
                label_w = self.draw.textlength(f"{label}:", font=self.font_normal)
                max_value_width = self.WIDTH - 10 - label_w
                self.draw_text(
                    10 + int(label_w),
                    y,
                    value,
                    font=self.font_normal,
                    max_width=int(max_value_width),
                    ellipsis=True,
                )

            # Draw footer
            self.draw_footer(None, "BACK", None)

    def draw_splash_screen(self):
        """Draw the Natasha splash screen."""
        with self.lock:
            # Clear the display
            self.image = Image.new("1", (self.WIDTH, self.HEIGHT), 255)
            self.draw = ImageDraw.Draw(self.image)

            # Draw title and texts
            self.draw_centered_text(20, "NATASHA", font=self.font_large)
            self.draw_centered_text(40, "AI Penetration Testing Tool", font=self.font_normal)
            self.draw_centered_text(70, "v1.0", font=self.font_small)
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
            for attempt in range(2):
                try:
                    self.epd.init()
                    break
                except Exception as e:
                    if attempt == 1:
                        raise
                    logging.warning(f"EPD wake retry due to: {e}")
                    time.sleep(0.2)
            logging.info("E-paper display woken from sleep")
        except Exception as e:
            logging.error(f"Failed to wake display: {e}")

    def close(self):
        """Release hardware resources, safe to call multiple times."""
        try:
            if self.epd is not None:
                try:
                    self.epd.sleep()
                except Exception:
                    pass
                try:
                    # Not all drivers provide Dev_exit
                    if hasattr(self.epd, "Dev_exit"):
                        self.epd.Dev_exit()
                except Exception:
                    pass
        finally:
            self.epd = None

    def __del__(self):
        """Best-effort cleanup when the object is destroyed."""
        try:
            self.close()
        except Exception:
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
        "Settings",
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
        ("IP Address", "192.168.1.100"),
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
    display.close()
