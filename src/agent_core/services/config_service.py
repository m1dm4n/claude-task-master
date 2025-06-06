import logfire
from pydantic import SecretStr, AnyHttpUrl
from typing import Optional, Dict, Literal

from ...config_manager import ConfigManager
from ...data_models import ModelConfig, AppConfig


class ConfigService:
    """
    Manages application and LLM model configurations.
    Encapsulates ConfigManager and LLMConfigManager.
    """

    def __init__(self, workspace_dir: str):
        """
        Initialize ConfigService.

        Args:
            workspace_dir: The root directory of the project workspace.
        """
        self.config_manager = ConfigManager(workspace_dir)
        logfire.info(f"ConfigService initialized for workspace: {workspace_dir}")

    def get_app_config(self) -> AppConfig:
        """
        Get the overall application configuration.

        Returns:
            AppConfig: The current application configuration.
        """
        return self.config_manager.config

    def get_model_config(self, model_type: Literal["main", "research", "fallback"]) -> Optional[ModelConfig]:
        """
        Get configuration for a specific LLM model type.

        Args:
            model_type: Type of model to retrieve configuration for.

        Returns:
            Optional[ModelConfig]: The model configuration if found, else None.
        """
        return self.config_manager.get_model_config(model_type)

    def set_model_configuration(
        self,
        model_type: Literal["main", "research", "fallback"],
        model_name: str,
        provider: Optional[str] = None,
        api_key_str: Optional[str] = None,
        base_url_str: Optional[str] = None
    ) -> bool:
        """
        Set model configuration for the specified type.

        Args:
            model_type: Type of model to configure.
            model_name: Name of the model.
            provider: Provider name (optional, inferred from model_name if not provided).
            api_key_str: API key string (optional).
            base_url_str: Base URL string (optional).

        Returns:
            True if configuration was set successfully, False otherwise.
        """
        try:
            model_config_data = {"model_name": model_name}

            if provider:
                model_config_data["provider"] = provider
            else:
                if "gpt" in model_name.lower() or "openai" in model_name.lower():
                    model_config_data["provider"] = "openai"
                elif "claude" in model_name.lower() or "anthropic" in model_name.lower():
                    model_config_data["provider"] = "anthropic"
                elif "gemini" in model_name.lower() or "google" in model_name.lower():
                    model_config_data["provider"] = "google"
                else:
                    model_config_data["provider"] = "unknown"

            if api_key_str:
                model_config_data["api_key"] = SecretStr(api_key_str)

            if base_url_str:
                model_config_data["base_url"] = AnyHttpUrl(base_url_str)

            model_config = ModelConfig(**model_config_data)

            self.config_manager.set_model_config(model_type, model_config)

            logfire.info(f"Successfully configured {model_type} model: {model_name}")
            return True

        except Exception as e:
            logfire.error(f"Error setting model configuration: {e}")
            return False

    def get_all_model_configurations(self) -> Dict[str, Optional[ModelConfig]]:
        """
        Get all model configurations.

        Returns:
            Dict mapping model type to ModelConfig.
        """
        return self.config_manager.get_all_model_configs()

    def reload_config(self):
        """Reloads the application configuration."""
        self.config_manager.reload_config()
        logfire.info("Application configuration reloaded.")