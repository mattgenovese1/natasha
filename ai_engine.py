#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Natasha AI Penetration Testing Tool
AI Engine for DuckyScript Generation

This module implements the AI engine responsible for generating DuckyScript payloads
based on target OS detection and attack parameters. It uses a lightweight model
to generate effective attack scripts tailored to different environments.
"""

import os
import time
import json
import random
import logging
import threading
from enum import Enum
import numpy as np
from typing import Dict, List, Tuple, Optional, Union, Any

# Optional imports for machine learning components
try:
    import joblib
    from sklearn.feature_extraction.text import CountVectorizer
    ML_AVAILABLE = True
except ImportError:
    logging.warning("Machine learning libraries not available. Some features will be limited.")
    ML_AVAILABLE = False

class TargetOS(Enum):
    """Enumeration of target operating systems."""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    ANDROID = "android"
    UNKNOWN = "unknown"

class AttackType(Enum):
    """Enumeration of attack types."""
    CREDENTIAL_HARVEST = "credential_harvest"
    KEYLOGGER = "keylogger"
    BACKDOOR = "backdoor"
    RECON = "recon"
    EXFILTRATION = "exfiltration"
    NETWORK_CONFIG = "network_config"
    CUSTOM = "custom"

class AIEngine:
    """AI Engine for generating DuckyScript payloads."""
    
    def __init__(self, model_dir: str = "models"):
        """Initialize the AI Engine.
        
        Args:
            model_dir: Directory containing model files
        """
        self.model_dir = model_dir
        self.templates = {}
        self.models = {}
        self.vectorizers = {}
        self.lock = threading.Lock()
        self.os_detection_rules = {}
        
        # Load resources
        self._load_resources()
    
    def _load_resources(self):
        """Load templates, models, and other resources."""
        try:
            # Ensure model directory exists
            os.makedirs(self.model_dir, exist_ok=True)
            
            # Load templates
            template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
            self._load_templates(template_path)
            
            # Load OS detection rules
            self._load_os_detection_rules()
            
            # Load ML models if available
            if ML_AVAILABLE:
                self._load_ml_models()
            
            logging.info("AI Engine resources loaded successfully")
        except Exception as e:
            logging.error(f"Failed to load AI Engine resources: {e}")
    
    def _load_templates(self, template_path: str):
        """Load DuckyScript templates from the template directory.
        
        Args:
            template_path: Path to the templates directory
        """
        try:
            # Load templates for each OS and attack type
            for os_type in TargetOS:
                self.templates[os_type.value] = {}
                
                os_template_dir = os.path.join(template_path, os_type.value)
                if not os.path.exists(os_template_dir):
                    os.makedirs(os_template_dir, exist_ok=True)
                    continue
                
                for attack_type in AttackType:
                    attack_template_file = os.path.join(os_template_dir, f"{attack_type.value}.json")
                    
                    if os.path.exists(attack_template_file):
                        with open(attack_template_file, 'r') as f:
                            self.templates[os_type.value][attack_type.value] = json.load(f)
                    else:
                        # Create empty template structure
                        self.templates[os_type.value][attack_type.value] = {
                            "metadata": {
                                "name": f"{attack_type.value.replace('_', ' ').title()} for {os_type.value.title()}",
                                "description": f"Template for {attack_type.value.replace('_', ' ')} attacks on {os_type.value}",
                                "version": "1.0",
                                "author": "Natasha AI"
                            },
                            "templates": []
                        }
                        
                        # Save empty template for future use
                        with open(attack_template_file, 'w') as f:
                            json.dump(self.templates[os_type.value][attack_type.value], f, indent=2)
            
            # Load fallback templates
            fallback_template_file = os.path.join(template_path, "fallback.json")
            if os.path.exists(fallback_template_file):
                with open(fallback_template_file, 'r') as f:
                    self.templates["fallback"] = json.load(f)
            else:
                self.templates["fallback"] = {
                    "metadata": {
                        "name": "Fallback Templates",
                        "description": "Generic templates for when OS-specific ones are not available",
                        "version": "1.0",
                        "author": "Natasha AI"
                    },
                    "templates": self._generate_fallback_templates()
                }
                
                # Save fallback templates for future use
                with open(fallback_template_file, 'w') as f:
                    json.dump(self.templates["fallback"], f, indent=2)
            
            logging.info(f"Loaded templates for {len(self.templates)} operating systems")
        except Exception as e:
            logging.error(f"Failed to load templates: {e}")
            # Create minimal templates dictionary
            self.templates = {"fallback": {"templates": self._generate_fallback_templates()}}
    
    def _generate_fallback_templates(self) -> List[Dict[str, Any]]:
        """Generate basic fallback templates for common attacks.
        
        Returns:
            List of template dictionaries
        """
        return [
            {
                "name": "Basic Reconnaissance",
                "description": "Gather basic system information",
                "attack_type": "recon",
                "script": [
                    "REM Basic Reconnaissance Script",
                    "REM Generated by Natasha AI",
                    "DELAY 1000",
                    "GUI r",
                    "DELAY 500",
                    "STRING cmd",
                    "ENTER",
                    "DELAY 1000",
                    "STRING whoami & hostname & ipconfig /all",
                    "ENTER"
                ],
                "parameters": {}
            },
            {
                "name": "Simple Exfiltration",
                "description": "Exfiltrate system information to a file",
                "attack_type": "exfiltration",
                "script": [
                    "REM Simple Exfiltration Script",
                    "REM Generated by Natasha AI",
                    "DELAY 1000",
                    "GUI r",
                    "DELAY 500",
                    "STRING cmd",
                    "ENTER",
                    "DELAY 1000",
                    "STRING whoami > %TEMP%\\info.txt & hostname >> %TEMP%\\info.txt & ipconfig /all >> %TEMP%\\info.txt",
                    "ENTER"
                ],
                "parameters": {}
            }
        ]
    
    def _load_os_detection_rules(self):
        """Load rules for OS detection from USB enumeration responses."""
        # These are simplified rules for demonstration
        self.os_detection_rules = {
            TargetOS.WINDOWS: {
                "usb_ids": ["VID_045E&PID_0291", "VID_045E&PID_0750"],  # Microsoft USB IDs
                "descriptors": ["Windows", "Microsoft"],
                "enumeration_speed": (50, 200)  # ms range
            },
            TargetOS.MACOS: {
                "usb_ids": ["VID_05AC&PID_024F", "VID_05AC&PID_0290"],  # Apple USB IDs
                "descriptors": ["Apple", "Mac"],
                "enumeration_speed": (20, 100)  # ms range
            },
            TargetOS.LINUX: {
                "usb_ids": [],  # Various Linux distributions
                "descriptors": ["Linux", "Ubuntu", "Debian", "Fedora"],
                "enumeration_speed": (30, 150)  # ms range
            },
            TargetOS.ANDROID: {
                "usb_ids": ["VID_18D1"],  # Google USB IDs
                "descriptors": ["Android", "Google"],
                "enumeration_speed": (40, 180)  # ms range
            }
        }
    
    def _load_ml_models(self):
        """Load machine learning models for script generation and OS detection."""
        if not ML_AVAILABLE:
            return
        
        try:
            # Check for model files
            model_files = {
                "os_detector": os.path.join(self.model_dir, "os_detector.joblib"),
                "script_generator": os.path.join(self.model_dir, "script_generator.joblib"),
                "vectorizer": os.path.join(self.model_dir, "vectorizer.joblib")
            }
            
            # Load existing models or create placeholders
            for model_name, model_path in model_files.items():
                if os.path.exists(model_path):
                    self.models[model_name] = joblib.load(model_path)
                    logging.info(f"Loaded model: {model_name}")
                else:
                    logging.warning(f"Model file not found: {model_path}")
                    # Create placeholder for missing models
                    if model_name == "vectorizer":
                        self.vectorizers[model_name] = CountVectorizer()
            
            logging.info("Machine learning models loaded")
        except Exception as e:
            logging.error(f"Failed to load ML models: {e}")
    
    def detect_target_os(self, usb_enumeration_data: Dict[str, Any] = None) -> TargetOS:
        """Detect the target operating system based on USB enumeration data.
        
        Args:
            usb_enumeration_data: USB enumeration data (if available)
            
        Returns:
            Detected target OS
        """
        if usb_enumeration_data is None:
            # If no data provided, return UNKNOWN
            return TargetOS.UNKNOWN
        
        # Extract relevant features from USB enumeration data
        usb_id = usb_enumeration_data.get("usb_id", "")
        descriptor = usb_enumeration_data.get("descriptor", "")
        enumeration_speed = usb_enumeration_data.get("enumeration_speed", 0)
        
        # Check against rules for each OS
        for os_type, rules in self.os_detection_rules.items():
            # Check USB ID
            for id_pattern in rules["usb_ids"]:
                if id_pattern in usb_id:
                    return os_type
            
            # Check descriptor strings
            for desc_pattern in rules["descriptors"]:
                if desc_pattern.lower() in descriptor.lower():
                    return os_type
            
            # Check enumeration speed range
            speed_range = rules["enumeration_speed"]
            if speed_range[0] <= enumeration_speed <= speed_range[1]:
                # This is a weak signal, so we'll just consider it a hint
                logging.debug(f"Enumeration speed {enumeration_speed}ms suggests {os_type.value}")
        
        # If no match found, try ML-based detection if available
        if ML_AVAILABLE and "os_detector" in self.models:
            try:
                # Prepare features for ML model
                features = [
                    usb_id,
                    descriptor,
                    str(enumeration_speed)
                ]
                
                # Make prediction
                prediction = self.models["os_detector"].predict([" ".join(features)])
                predicted_os = prediction[0]
                
                # Convert prediction to TargetOS enum
                for os_type in TargetOS:
                    if os_type.value == predicted_os:
                        return os_type
            except Exception as e:
                logging.error(f"ML-based OS detection failed: {e}")
        
        # Default to UNKNOWN if no match found
        return TargetOS.UNKNOWN
    
    def generate_duckyscript(self, 
                           attack_type: AttackType, 
                           target_os: TargetOS = TargetOS.UNKNOWN, 
                           parameters: Dict[str, Any] = None) -> str:
        """Generate a DuckyScript payload for the specified attack type and target OS.
        
        Args:
            attack_type: Type of attack to generate
            target_os: Target operating system
            parameters: Additional parameters for script generation
            
        Returns:
            Generated DuckyScript as a string
        """
        if parameters is None:
            parameters = {}
        
        with self.lock:
            # Select appropriate template
            template = self._select_template(attack_type, target_os, parameters)
            
            if template is None:
                logging.warning(f"No template found for {attack_type.value} on {target_os.value}")
                return self._generate_fallback_script(attack_type, target_os, parameters)
            
            # Generate script from template
            script = self._generate_from_template(template, parameters)
            
            # Add metadata and comments
            script = self._add_metadata(script, attack_type, target_os, parameters)
            
            # Optimize script
            script = self._optimize_script(script)
            
            return script
    
    def _select_template(self, 
                        attack_type: AttackType, 
                        target_os: TargetOS, 
                        parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Select the most appropriate template for the attack.
        
        Args:
            attack_type: Type of attack
            target_os: Target operating system
            parameters: Additional parameters
            
        Returns:
            Selected template dictionary or None if no suitable template found
        """
        # Try to find a specific template for the target OS and attack type
        if target_os.value in self.templates and attack_type.value in self.templates[target_os.value]:
            templates = self.templates[target_os.value][attack_type.value].get("templates", [])
            if templates:
                # Find the best matching template based on parameters
                best_template = self._find_best_template(templates, parameters)
                if best_template:
                    return best_template
        
        # Fall back to generic template for the attack type
        if "fallback" in self.templates:
            fallback_templates = self.templates["fallback"].get("templates", [])
            matching_templates = [t for t in fallback_templates if t.get("attack_type") == attack_type.value]
            
            if matching_templates:
                return self._find_best_template(matching_templates, parameters)
        
        return None
    
    def _find_best_template(self, 
                           templates: List[Dict[str, Any]], 
                           parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Find the best matching template based on parameters.
        
        Args:
            templates: List of template dictionaries
            parameters: Parameters to match against
            
        Returns:
            Best matching template or random template if no good match
        """
        if not templates:
            return None
        
        # If only one template, return it
        if len(templates) == 1:
            return templates[0]
        
        # Score templates based on parameter match
        scored_templates = []
        for template in templates:
            score = 0
            template_params = template.get("parameters", {})
            
            # Score based on parameter match
            for param_name, param_value in parameters.items():
                if param_name in template_params:
                    template_value = template_params[param_name]
                    
                    # Exact match
                    if template_value == param_value:
                        score += 10
                    # Partial match for strings
                    elif isinstance(param_value, str) and isinstance(template_value, str):
                        if param_value.lower() in template_value.lower() or template_value.lower() in param_value.lower():
                            score += 5
                    # Range match for numbers
                    elif isinstance(param_value, (int, float)) and isinstance(template_value, (int, float)):
                        if abs(param_value - template_value) / max(1, abs(template_value)) < 0.2:  # Within 20%
                            score += 5
            
            scored_templates.append((template, score))
        
        # Sort by score (descending)
        scored_templates.sort(key=lambda x: x[1], reverse=True)
        
        # Return the highest scoring template, or a random one if all scores are 0
        if scored_templates[0][1] > 0:
            return scored_templates[0][0]
        else:
            return random.choice(templates)
    
    def _generate_from_template(self, 
                              template: Dict[str, Any], 
                              parameters: Dict[str, Any]) -> str:
        """Generate a DuckyScript from a template.
        
        Args:
            template: Template dictionary
            parameters: Parameters for script generation
            
        Returns:
            Generated DuckyScript as a string
        """
        # Get the base script from the template
        script_lines = template.get("script", [])
        
        # Process each line for parameter substitution
        processed_lines = []
        for line in script_lines:
            # Handle parameter substitution
            for param_name, param_value in parameters.items():
                placeholder = f"{{${param_name}}}"
                if placeholder in line:
                    line = line.replace(placeholder, str(param_value))
            
            processed_lines.append(line)
        
        # Join lines into a single script
        return "\n".join(processed_lines)
    
    def _add_metadata(self, 
                    script: str, 
                    attack_type: AttackType, 
                    target_os: TargetOS, 
                    parameters: Dict[str, Any]) -> str:
        """Add metadata and comments to the script.
        
        Args:
            script: Generated script
            attack_type: Type of attack
            target_os: Target operating system
            parameters: Script parameters
            
        Returns:
            Script with added metadata
        """
        # Create metadata header
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        metadata_lines = [
            "REM ==============================================",
            "REM Natasha AI Penetration Testing Tool",
            f"REM Attack Type: {attack_type.value.replace('_', ' ').title()}",
            f"REM Target OS: {target_os.value.title()}",
            f"REM Generated: {timestamp}",
            "REM =============================================="
        ]
        
        # Add parameter information
        if parameters:
            metadata_lines.append("REM Parameters:")
            for param_name, param_value in parameters.items():
                metadata_lines.append(f"REM   - {param_name}: {param_value}")
            metadata_lines.append("REM ==============================================")
        
        # Add educational note
        metadata_lines.extend([
            "REM NOTE: This script is generated for educational purposes",
            "REM and authorized penetration testing only.",
            "REM ==============================================",
            ""
        ])
        
        # Combine metadata with script
        return "\n".join(metadata_lines) + "\n" + script
    
    def _optimize_script(self, script: str) -> str:
        """Optimize the generated script for better performance.
        
        Args:
            script: Generated script
            
        Returns:
            Optimized script
        """
        lines = script.split("\n")
        optimized_lines = []
        
        # Process lines
        i = 0
        while i < len(lines):
            current_line = lines[i].strip()
            
            # Skip empty lines
            if not current_line:
                i += 1
                continue
            
            # Combine consecutive STRING commands
            if current_line.startswith("STRING ") and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith("STRING "):
                    # Combine the strings
                    current_text = current_line[7:]  # Remove "STRING "
                    next_text = next_line[7:]  # Remove "STRING "
                    combined_line = f"STRING {current_text} {next_text}"
                    lines[i + 1] = combined_line
                    i += 1
                    continue
            
            # Optimize DELAY commands
            if current_line.startswith("DELAY "):
                try:
                    delay_value = int(current_line[6:])
                    # Minimum delay of 20ms
                    if delay_value < 20:
                        optimized_lines.append("DELAY 20")
                    else:
                        optimized_lines.append(current_line)
                except ValueError:
                    optimized_lines.append(current_line)
            else:
                optimized_lines.append(current_line)
            
            i += 1
        
        return "\n".join(optimized_lines)
    
    def _generate_fallback_script(self, 
                                attack_type: AttackType, 
                                target_os: TargetOS, 
                                parameters: Dict[str, Any]) -> str:
        """Generate a fallback script when no suitable template is found.
        
        Args:
            attack_type: Type of attack
            target_os: Target operating system
            parameters: Script parameters
            
        Returns:
            Fallback script as a string
        """
        # Basic script structure
        script_lines = [
            "REM Fallback script generated by Natasha AI",
            f"REM Attack Type: {attack_type.value}",
            f"REM Target OS: {target_os.value}",
            "DELAY 1000"
        ]
        
        # Add OS-specific commands
        if target_os == TargetOS.WINDOWS:
            script_lines.extend([
                "GUI r",
                "DELAY 500",
                "STRING cmd",
                "ENTER",
                "DELAY 1000",
                "STRING echo Natasha AI Penetration Testing Tool",
                "ENTER"
            ])
        elif target_os == TargetOS.MACOS:
            script_lines.extend([
                "GUI SPACE",
                "DELAY 500",
                "STRING terminal",
                "DELAY 500",
                "ENTER",
                "DELAY 1000",
                "STRING echo Natasha AI Penetration Testing Tool",
                "ENTER"
            ])
        elif target_os == TargetOS.LINUX:
            script_lines.extend([
                "ALT F2",
                "DELAY 500",
                "STRING terminal",
                "ENTER",
                "DELAY 1000",
                "STRING echo Natasha AI Penetration Testing Tool",
                "ENTER"
            ])
        else:
            # Generic fallback
            script_lines.extend([
                "REM No OS-specific commands available",
                "REM Using generic commands",
                "GUI r",
                "DELAY 1000",
                "STRING notepad",
                "ENTER",
                "DELAY 1000",
                "STRING Natasha AI Penetration Testing Tool",
                "ENTER"
            ])
        
        # Add attack-specific commands
        if attack_type == AttackType.RECON:
            if target_os == TargetOS.WINDOWS:
                script_lines.extend([
                    "STRING systeminfo",
                    "ENTER"
                ])
            elif target_os == TargetOS.MACOS:
                script_lines.extend([
                    "STRING system_profiler SPHardwareDataType",
                    "ENTER"
                ])
            elif target_os == TargetOS.LINUX:
                script_lines.extend([
                    "STRING uname -a && lsb_release -a",
                    "ENTER"
                ])
        
        return "\n".join(script_lines)
    
    def learn_from_feedback(self, 
                          script: str, 
                          success: bool, 
                          feedback: Dict[str, Any] = None) -> None:
        """Learn from feedback on generated scripts.
        
        Args:
            script: The script that was executed
            success: Whether the script was successful
            feedback: Additional feedback information
        """
        if not ML_AVAILABLE:
            logging.warning("Machine learning libraries not available. Cannot learn from feedback.")
            return
        
        # This is a placeholder for actual learning implementation
        logging.info(f"Learning from feedback: success={success}")
        
        # In a real implementation, this would update the models based on feedback
        pass
    
    def save_models(self) -> None:
        """Save trained models to disk."""
        if not ML_AVAILABLE:
            return
        
        try:
            # Ensure model directory exists
            os.makedirs(self.model_dir, exist_ok=True)
            
            # Save models
            for model_name, model in self.models.items():
                model_path = os.path.join(self.model_dir, f"{model_name}.joblib")
                joblib.dump(model, model_path)
                logging.info(f"Saved model: {model_name}")
            
            # Save vectorizers
            for vec_name, vec in self.vectorizers.items():
                vec_path = os.path.join(self.model_dir, f"{vec_name}.joblib")
                joblib.dump(vec, vec_path)
                logging.info(f"Saved vectorizer: {vec_name}")
        except Exception as e:
            logging.error(f"Failed to save models: {e}")
    
    def generate_custom_script(self, 
                             script_description: str, 
                             target_os: TargetOS = TargetOS.UNKNOWN) -> str:
        """Generate a custom script based on a natural language description.
        
        Args:
            script_description: Natural language description of the desired script
            target_os: Target operating system
            
        Returns:
            Generated DuckyScript as a string
        """
        # This is a placeholder for a more sophisticated implementation
        # In a real implementation, this would use NLP to understand the description
        # and generate an appropriate script
        
        logging.info(f"Generating custom script for: {script_description}")
        
        # Extract key information from description
        keywords = {
            "password": AttackType.CREDENTIAL_HARVEST,
            "credential": AttackType.CREDENTIAL_HARVEST,
            "keylog": AttackType.KEYLOGGER,
            "backdoor": AttackType.BACKDOOR,
            "information": AttackType.RECON,
            "recon": AttackType.RECON,
            "exfil": AttackType.EXFILTRATION,
            "network": AttackType.NETWORK_CONFIG
        }
        
        # Determine attack type based on keywords
        attack_type = AttackType.CUSTOM
        for keyword, att_type in keywords.items():
            if keyword.lower() in script_description.lower():
                attack_type = att_type
                break
        
        # Extract parameters from description
        parameters = {}
        
        # Generate script using the determined attack type
        return self.generate_duckyscript(attack_type, target_os, parameters)


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize the AI Engine
    ai_engine = AIEngine()
    
    # Test OS detection
    test_data = {
        "usb_id": "VID_045E&PID_0291",
        "descriptor": "Microsoft Keyboard",
        "enumeration_speed": 120
    }
    detected_os = ai_engine.detect_target_os(test_data)
    print(f"Detected OS: {detected_os.value}")
    
    # Generate a script for credential harvesting on Windows
    script = ai_engine.generate_duckyscript(
        AttackType.CREDENTIAL_HARVEST,
        TargetOS.WINDOWS,
        {"browser": "chrome", "exfil_method": "file"}
    )
    print("\nGenerated Script:")
    print(script)
    
    # Generate a custom script
    custom_script = ai_engine.generate_custom_script(
        "Extract saved passwords from Chrome and save to a file",
        TargetOS.WINDOWS
    )
    print("\nCustom Script:")
    print(custom_script)