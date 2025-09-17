#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Character Animation Controller for Natasha AI

This module handles the animation and expression management for the Natasha character.
It supports multiple animation states and frame-by-frame animation for e-paper displays.
"""

import os
import time
import threading
import logging
from enum import Enum
from typing import Dict, List, Optional
from PIL import Image

class CharacterState(Enum):
    """Enumeration of character states/expressions."""
    IDLE = "idle"
    THINKING = "thinking"
    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"
    PROCESSING = "processing"

class AnimationController:
    """Controller for managing character animations and expressions."""
    
    def __init__(self, character_dir: str = "characters/natasha"):
        """Initialize the animation controller.
        
        Args:
            character_dir: Directory containing character animation frames
        """
        self.character_dir = character_dir
        self.current_state = CharacterState.IDLE
        self.current_frame = 0
        self.animation_speed = 0.5  # seconds per frame
        self.last_frame_time = 0
        self.is_animating = False
        self.animation_thread = None
        self.stop_animation = False
        
        # Load animation frames
        self.frames: Dict[CharacterState, List[Image.Image]] = {}
        self._load_animation_frames()
        
        logging.info("Character Animation Controller initialized")
    
    def _load_animation_frames(self):
        """Load animation frames from the character directory."""
        try:
            for state in CharacterState:
                state_dir = os.path.join(self.character_dir, state.value)
                if os.path.exists(state_dir):
                    frames = []
                    # Look for PNG files in the state directory
                    for file_name in sorted(os.listdir(state_dir)):
                        if file_name.endswith('.png'):
                            file_path = os.path.join(state_dir, file_name)
                            try:
                                img = Image.open(file_path)
                                # Convert to 1-bit for e-paper compatibility
                                if img.mode != '1':
                                    img = img.convert('1')
                                frames.append(img)
                                logging.debug(f"Loaded frame: {file_path}")
                            except Exception as e:
                                logging.error(f"Failed to load frame {file_path}: {e}")
                    
                    if frames:
                        self.frames[state] = frames
                        logging.info(f"Loaded {len(frames)} frames for state: {state.value}")
                    else:
                        logging.warning(f"No frames found for state: {state.value}")
                        # Create a placeholder frame
                        placeholder = Image.new('1', (122, 250), 1)  # White background
                        self.frames[state] = [placeholder]
                else:
                    logging.warning(f"Directory not found for state: {state.value}")
                    # Create a placeholder frame
                    placeholder = Image.new('1', (122, 250), 1)  # White background
                    self.frames[state] = [placeholder]
                    
        except Exception as e:
            logging.error(f"Failed to load animation frames: {e}")
            # Create placeholder frames for all states
            for state in CharacterState:
                placeholder = Image.new('1', (122, 250), 1)
                self.frames[state] = [placeholder]
    
    def set_state(self, new_state: CharacterState):
        """Set the character's current state.
        
        Args:
            new_state: The new state to transition to
        """
        if new_state != self.current_state:
            self.current_state = new_state
            self.current_frame = 0
            logging.info(f"Character state changed to: {new_state.value}")
    
    def get_current_frame(self) -> Optional[Image.Image]:
        """Get the current animation frame.
        
        Returns:
            Current frame as PIL Image, or None if no frames available
        """
        frames = self.frames.get(self.current_state)
        if frames and frames:
            return frames[self.current_frame % len(frames)]
        return None
    
    def update_frame(self):
        """Update to the next animation frame if enough time has passed."""
        current_time = time.time()
        if current_time - self.last_frame_time >= self.animation_speed:
            frames = self.frames.get(self.current_state)
            if frames and len(frames) > 1:
                self.current_frame = (self.current_frame + 1) % len(frames)
            self.last_frame_time = current_time
    
    def start_animation_loop(self):
        """Start the animation loop in a separate thread."""
        if self.is_animating:
            return
            
        self.stop_animation = False
        self.is_animating = True
        
        def animation_loop():
            while not self.stop_animation:
                self.update_frame()
                time.sleep(0.1)  # Check for updates every 100ms
        
        self.animation_thread = threading.Thread(target=animation_loop, daemon=True)
        self.animation_thread.start()
        logging.info("Animation loop started")
    
    def stop_animation_loop(self):
        """Stop the animation loop."""
        self.stop_animation = True
        self.is_animating = False
        if self.animation_thread:
            self.animation_thread.join(timeout=1.0)
        logging.info("Animation loop stopped")
    
    def set_animation_speed(self, speed: float):
        """Set the animation speed in seconds per frame.
        
        Args:
            speed: Time in seconds between frame updates
        """
        self.animation_speed = max(0.1, speed)  # Minimum 0.1 seconds
        logging.info(f"Animation speed set to: {speed}s per frame")
    
    def get_state_info(self) -> Dict:
        """Get information about the current state and animation.
        
        Returns:
            Dictionary with state information
        """
        frames = self.frames.get(self.current_state, [])
        return {
            "state": self.current_state.value,
            "current_frame": self.current_frame,
            "total_frames": len(frames),
            "is_animating": self.is_animating,
            "animation_speed": self.animation_speed
        }
    
    def trigger_success_animation(self):
        """Trigger a success animation sequence."""
        self.set_state(CharacterState.SUCCESS)
        # Success animations might have special handling
        logging.info("Success animation triggered")
    
    def trigger_failure_animation(self):
        """Trigger a failure animation sequence."""
        self.set_state(CharacterState.FAILURE)
        logging.info("Failure animation triggered")
    
    def trigger_thinking_animation(self):
        """Trigger a thinking/processing animation."""
        self.set_state(CharacterState.THINKING)
        logging.info("Thinking animation triggered")
    
    def trigger_warning_animation(self):
        """Trigger a warning animation."""
        self.set_state(CharacterState.WARNING)
        logging.info("Warning animation triggered")

# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize the animation controller
    anim_controller = AnimationController()
    
    # Test state changes
    print("Testing character animation controller...")
    print(f"Initial state: {anim_controller.current_state.value}")
    
    # Test state transitions
    anim_controller.set_state(CharacterState.THINKING)
    print(f"Current state: {anim_controller.current_state.value}")
    
    # Get current frame
    frame = anim_controller.get_current_frame()
    if frame:
        print(f"Frame size: {frame.size}")
    
    # Test animation info
    info = anim_controller.get_state_info()
    print(f"State info: {info}")
