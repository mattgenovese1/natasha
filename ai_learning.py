#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI Learning Component for Natasha

This module implements the learning functionality for the AI engine,
allowing it to improve DuckyScript generation based on user feedback
and attack outcomes.
"""

import os
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum

class LearningState(Enum):
    """Enumeration of learning states."""
    IDLE = "idle"
    COLLECTING = "collecting"
    PROCESSING = "processing"
    UPDATING = "updating"

class AILearning:
    """AI Learning component for improving script generation."""
    
    def __init__(self, data_dir: str = "learning_data", model_dir: str = "models"):
        """Initialize the AI Learning component.
        
        Args:
            data_dir: Directory for storing learning data
            model_dir: Directory for storing trained models
        """
        self.data_dir = data_dir
        self.model_dir = model_dir
        self.state = LearningState.IDLE
        self.feedback_data: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        self.learning_rate = 0.1  # Default learning rate
        
        # Ensure directories exist
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(model_dir, exist_ok=True)
        
        # Load existing feedback data
        self._load_feedback_data()
        
        logging.info("AI Learning component initialized")
    
    def _load_feedback_data(self):
        """Load existing feedback data from storage."""
        try:
            data_file = os.path.join(self.data_dir, "feedback.json")
            if os.path.exists(data_file):
                with open(data_file, 'r') as f:
                    self.feedback_data = json.load(f)
                logging.info(f"Loaded {len(self.feedback_data)} feedback entries")
            else:
                self.feedback_data = []
                logging.info("No existing feedback data found")
        except Exception as e:
            logging.error(f"Failed to load feedback data: {e}")
            self.feedback_data = []
    
    def _save_feedback_data(self):
        """Save feedback data to storage."""
        try:
            data_file = os.path.join(self.data_dir, "feedback.json")
            tmp_file = data_file + ".tmp"
            
            with open(tmp_file, 'w') as f:
                json.dump(self.feedback_data, f, indent=2)
            
            # Atomic replace
            os.replace(tmp_file, data_file)
            logging.info(f"Feedback data saved: {len(self.feedback_data)} entries")
        except Exception as e:
            logging.error(f"Failed to save feedback data: {e}")
    
    def record_feedback(
        self,
        script: str,
        success: bool,
        attack_type: str,
        target_os: str,
        parameters: Dict[str, Any],
        user_feedback: Optional[Dict[str, Any]] = None,
        execution_time: Optional[float] = None
    ):
        """Record feedback for a generated script.
        
        Args:
            script: The DuckyScript that was executed
            success: Whether the script was successful
            attack_type: Type of attack attempted
            target_os: Target operating system
            parameters: Parameters used for script generation
            user_feedback: Additional user feedback
            execution_time: Time taken to execute the script
        """
        with self.lock:
            feedback_entry = {
                "timestamp": datetime.now().isoformat(),
                "script": script,
                "success": success,
                "attack_type": attack_type,
                "target_os": target_os,
                "parameters": parameters,
                "user_feedback": user_feedback or {},
                "execution_time": execution_time,
                "learning_processed": False
            }
            
            self.feedback_data.append(feedback_entry)
            
            # Save data periodically (every 10 entries)
            if len(self.feedback_data) % 10 == 0:
                self._save_feedback_data()
            
            logging.info(f"Feedback recorded: {attack_type} on {target_os} - Success: {success}")
    
    def process_feedback(self):
        """Process collected feedback to improve script generation."""
        if self.state != LearningState.IDLE:
            logging.warning("Learning component is already processing")
            return
        
        self.state = LearningState.PROCESSING
        logging.info("Starting feedback processing")
        
        try:
            with self.lock:
                # Get unprocessed feedback
                unprocessed = [f for f in self.feedback_data if not f.get("learning_processed")]
                
                if not unprocessed:
                    logging.info("No new feedback to process")
                    self.state = LearningState.IDLE
                    return
                
                # Analyze feedback patterns
                success_patterns = self._analyze_success_patterns(unprocessed)
                failure_patterns = self._analyze_failure_patterns(unprocessed)
                
                # Update models based on patterns
                self._update_models(success_patterns, failure_patterns)
                
                # Mark feedback as processed
                for feedback in unprocessed:
                    feedback["learning_processed"] = True
                
                # Save updated data
                self._save_feedback_data()
                
                logging.info(f"Processed {len(unprocessed)} feedback entries")
                
        except Exception as e:
            logging.error(f"Error processing feedback: {e}")
        finally:
            self.state = LearningState.IDLE
    
    def _analyze_success_patterns(self, feedback_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in successful scripts.
        
        Args:
            feedback_data: List of feedback entries
            
        Returns:
            Dictionary of success patterns
        """
        successful = [f for f in feedback_data if f["success"]]
        
        patterns = {
            "common_commands": {},
            "effective_parameters": {},
            "execution_times": [],
            "os_specific_success": {},
            "attack_type_success": {}
        }
        
        for feedback in successful:
            # Analyze command patterns
            script_lines = feedback["script"].split('\n')
            for line in script_lines:
                line = line.strip()
                if line and not line.startswith('REM'):
                    patterns["common_commands"][line] = patterns["common_commands"].get(line, 0) + 1
            
            # Parameter effectiveness
            for param, value in feedback["parameters"].items():
                key = f"{param}={value}"
                patterns["effective_parameters"][key] = patterns["effective_parameters"].get(key, 0) + 1
            
            # Execution time analysis
            if feedback.get("execution_time"):
                patterns["execution_times"].append(feedback["execution_time"])
            
            # OS-specific success rates
            os_key = feedback["target_os"]
            patterns["os_specific_success"][os_key] = patterns["os_specific_success"].get(os_key, 0) + 1
            
            # Attack type success rates
            attack_key = feedback["attack_type"]
            patterns["attack_type_success"][attack_key] = patterns["attack_type_success"].get(attack_key, 0) + 1
        
        return patterns
    
    def _analyze_failure_patterns(self, feedback_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in failed scripts.
        
        Args:
            feedback_data: List of feedback entries
            
        Returns:
            Dictionary of failure patterns
        """
        failed = [f for f in feedback_data if not f["success"]]
        
        patterns = {
            "common_errors": {},
            "problematic_commands": {},
            "os_specific_failures": {},
            "attack_type_failures": {},
            "user_feedback_themes": {}
        }
        
        for feedback in failed:
            # Analyze error patterns from user feedback
            user_fb = feedback.get("user_feedback", {})
            for key, value in user_fb.items():
                if isinstance(value, str):
                    patterns["user_feedback_themes"][value] = patterns["user_feedback_themes"].get(value, 0) + 1
            
            # Problematic commands
            script_lines = feedback["script"].split('\n')
            for line in script_lines:
                line = line.strip()
                if line and not line.startswith('REM'):
                    patterns["problematic_commands"][line] = patterns["problematic_commands"].get(line, 0) + 1
            
            # OS-specific failure rates
            os_key = feedback["target_os"]
            patterns["os_specific_failures"][os_key] = patterns["os_specific_failures"].get(os_key, 0) + 1
            
            # Attack type failure rates
            attack_key = feedback["attack_type"]
            patterns["attack_type_failures"][attack_key] = patterns["attack_type_failures"].get(attack_key, 0) + 1
        
        return patterns
    
    def _update_models(self, success_patterns: Dict[str, Any], failure_patterns: Dict[str, Any]):
        """Update AI models based on analyzed patterns.
        
        Args:
            success_patterns: Patterns from successful scripts
            failure_patterns: Patterns from failed scripts
        """
        # This is a placeholder for actual model update logic
        # In a real implementation, this would update the AI engine's models
        
        logging.info("Updating models based on feedback analysis")
        
        # Example: Update template selection weights
        self._update_template_weights(success_patterns, failure_patterns)
        
        # Example: Update parameter preferences
        self._update_parameter_preferences(success_patterns, failure_patterns)
        
        # Save updated model state
        self._save_model_state()
    
    def _update_template_weights(self, success_patterns: Dict[str, Any], failure_patterns: Dict[str, Any]):
        """Update template selection weights based on feedback."""
        # This would modify how templates are selected based on success rates
        logging.debug("Updating template selection weights")
    
    def _update_parameter_preferences(self, success_patterns: Dict[str, Any], failure_patterns: Dict[str, Any]):
        """Update parameter preferences based on feedback."""
        # This would modify default parameter values based on effectiveness
        logging.debug("Updating parameter preferences")
    
    def _save_model_state(self):
        """Save the current model state."""
        # This would save the updated model parameters
        logging.debug("Saving model state")
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Get learning statistics.
        
        Returns:
            Dictionary with learning statistics
        """
        with self.lock:
            total_feedback = len(self.feedback_data)
            processed = sum(1 for f in self.feedback_data if f.get("learning_processed"))
            successful = sum(1 for f in self.feedback_data if f.get("success"))
            
            return {
                "total_feedback": total_feedback,
                "processed_feedback": processed,
                "successful_scripts": successful,
                "success_rate": successful / total_feedback if total_feedback > 0 else 0,
                "learning_state": self.state.value,
                "learning_rate": self.learning_rate
            }
    
    def set_learning_rate(self, rate: float):
        """Set the learning rate for model updates.
        
        Args:
            rate: Learning rate between 0.0 and 1.0
        """
        self.learning_rate = max(0.0, min(1.0, rate))
        logging.info(f"Learning rate set to: {self.learning_rate}")
    
    def export_learning_data(self, export_path: str):
        """Export learning data to a file.
        
        Args:
            export_path: Path to export the data to
        """
        try:
            with open(export_path, 'w') as f:
                json.dump(self.feedback_data, f, indent=2)
            logging.info(f"Learning data exported to: {export_path}")
        except Exception as e:
            logging.error(f"Failed to export learning data: {e}")
    
    def import_learning_data(self, import_path: str):
        """Import learning data from a file.
        
        Args:
            import_path: Path to import the data from
        """
        try:
            with open(import_path, 'r') as f:
                imported_data = json.load(f)
            
            with self.lock:
                self.feedback_data.extend(imported_data)
                self._save_feedback_data()
            
            logging.info(f"Imported {len(imported_data)} feedback entries from: {import_path}")
        except Exception as e:
            logging.error(f"Failed to import learning data: {e}")

# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize the learning component
    learning = AILearning()
    
    # Record some example feedback
    learning.record_feedback(
        script="REM Test script\nDELAY 1000\nSTRING echo Hello",
        success=True,
        attack_type="recon",
        target_os="windows",
        parameters={"delay": 1000},
        user_feedback={"comment": "Worked perfectly!"},
        execution_time=2.5
    )
    
    # Get learning statistics
    stats = learning.get_learning_stats()
    print(f"Learning stats: {stats}")
    
    # Process feedback
    learning.process_feedback()
    
    print("AI Learning component test completed")
