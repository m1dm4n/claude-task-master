import json
import os
from pathlib import Path
from typing import Optional, Dict, Literal

from .data_models import AppConfig, ModelConfig, SecretStr, AnyHttpUrl # Import SecretStr, AnyHttpUrl


class ConfigManager:
    """
    Manages loading and accessing configuration for the DevTask AI Assistant.
    No longer a singleton - initialized with workspace_path.
    """
    
    def __init__(self, workspace_path: str, config_filename: str = ".taskmasterconfig"):
        """
        Initialize ConfigManager with workspace path and config filename.
        
        Args:
            workspace_path: Path to the workspace directory
            config_filename: Name of the config file (default: .taskmasterconfig)
        """
        # Removed debug print
        self.workspace_path = Path(workspace_path).resolve()
        self.config_filename = config_filename
        self.config_file_path = self.workspace_path / config_filename
        
        # Load or initialize configuration
        self.config = self.load_or_initialize_config()
    
    def load_or_initialize_config(self) -> AppConfig:
        """
        Loads configuration from file or creates default configuration.
        
        Returns:
            AppConfig: Loaded or default configuration
        """
        config_data: Dict = {}
        
        if self.config_file_path.exists():
            try:
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                print(f"Configuration loaded from {self.config_file_path}")
            except Exception as e:
                print(f"Error reading configuration file {self.config_file_path}: {e}")
                config_data = {}
        
        if not config_data:
            print(f"Warning: Configuration file '{self.config_file_path}' not found or empty. Creating default configuration.")
            # Create default configuration
            default_config = self._create_default_config()
            self.config = default_config
            self.save_config()
            return default_config
        
        try:
            config = AppConfig.model_validate(config_data)
            return config
        except Exception as e:
            print(f"Error validating configuration from '{self.config_file_path}': {e}")
            print("Creating fallback configuration.")
            fallback_config = self._create_default_config()
            self.config = fallback_config
            self.save_config()
            return fallback_config
    
    def _create_default_config(self) -> AppConfig:
        """
        Creates a default AppConfig with sensible defaults.
        
        Returns:
            AppConfig: Default configuration
        """
        # Create default model configurations
        default_main_model = ModelConfig(
            model_name="gemini-2.0-flash",
            provider="google"
        )
        
        default_research_model = ModelConfig(
            model_name="gemini-2.5-flash-preview-05-20",
            provider="google"
        )
        
        default_fallback_model = ModelConfig(
            model_name="gemini-2.0-flash",
            provider="google"
        )
        
        return AppConfig(
            main_model=default_main_model,
            research_model=default_research_model,
            fallback_model=default_fallback_model
        )
    
    def save_config(self) -> None:
        """
        Saves the current configuration to the config file.
        """
        try:
            # Ensure workspace directory exists
            self.workspace_path.mkdir(parents=True, exist_ok=True)
            
            # Convert to dict and save as JSON
            # Use a custom encoder for Pydantic types that json.dump doesn't handle natively
            def json_encoder(obj):
                if isinstance(obj, SecretStr):
                    return obj.get_secret_value()
                if isinstance(obj, AnyHttpUrl):
                    return str(obj)
                raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

            config_dict = self.config.model_dump() # model_dump() handles SecretStr and AnyHttpUrl for JSON-like output
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, default=json_encoder) # Pass custom encoder
            print(f"Configuration saved to {self.config_file_path}")
        except Exception as e:
            print(f"Error saving configuration to {self.config_file_path}: {e}")
            raise
    
    def get_model_config(self, model_type: Literal["main", "research", "fallback"]) -> Optional[ModelConfig]:
        """
        Get model configuration for the specified type.
        
        Args:
            model_type: Type of model configuration to retrieve
            
        Returns:
            ModelConfig or None if not found
        """
        if model_type == "main":
            return self.config.main_model
        elif model_type == "research":
            return self.config.research_model
        elif model_type == "fallback":
            return self.config.fallback_model
        else:
            return None
    
    def set_model_config(self, model_type: Literal["main", "research", "fallback"], config: ModelConfig) -> None:
        """
        Set model configuration for the specified type.
        
        Args:
            model_type: Type of model configuration to set
            config: ModelConfig to set
        """
        if model_type == "main":
            self.config.main_model = config
        elif model_type == "research":
            self.config.research_model = config
        elif model_type == "fallback":
            self.config.fallback_model = config
        else:
            raise ValueError(f"Invalid model type: {model_type}")
        
        # Save configuration after updating
        self.save_config()
    
    def get_all_model_configs(self) -> Dict[str, Optional[ModelConfig]]:
        """
        Get all model configurations.
        
        Returns:
            Dict mapping model type to ModelConfig
        """
        return {
            "main": self.config.main_model,
            "research": self.config.research_model,
            "fallback": self.config.fallback_model
        }


# Example usage for testing
if __name__ == "__main__":
    import tempfile
    import shutil
    
    # Create temporary workspace for testing
    test_workspace = tempfile.mkdtemp()
    print(f"Testing with workspace: {test_workspace}")
    
    try:
        # Test ConfigManager initialization
        config_manager = ConfigManager(test_workspace)
        print("ConfigManager initialized successfully")
        
        # Test getting model configurations
        configs = config_manager.get_all_model_configs()
        print(f"All model configs: {configs}")
        
        # Test setting a model configuration
        new_main_config = ModelConfig(
            model_name="gpt-4",
            provider="openai"
        )
        config_manager.set_model_config("main", new_main_config)
        print("Updated main model configuration")
        
        # Verify the change
        updated_config = config_manager.get_model_config("main")
        print(f"Updated main config: {updated_config}")
        
    finally:
        # Clean up test workspace
        shutil.rmtree(test_workspace)
        print("Test workspace cleaned up")