from __future__ import annotations as _annotations

import asyncio
import os
import json
from functools import lru_cache
from typing import Any, Callable, Dict, Literal, Optional, List, Union
from uuid import UUID  # Import for UUID validation
from dataclasses import dataclass

import logfire

from pydantic_ai import tools as pydantic_ai_tools
from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.providers.google import GoogleProvider
from google import genai

from src.agent_prompts import MAIN_AGENT_SYSTEM_PROMPT

from ..config_manager import ConfigManager
from ..data_models import ModelConfig, ProjectPlan


@dataclass
class AgentDependencies:
    pass


logfire.configure(send_to_logfire='if-token-present')


class LLMService:
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize LLMService with a ConfigManager instance.

        Args:
            config_manager: ConfigManager instance for accessing model configurations
        """
        self.config_manager = config_manager
        self._llm_clients: Dict[str, Any] = {}
        self._current_agent_runtime_params: Optional[Dict[str, Any]] = None

    def reload_configuration(self) -> None:
        """
        Reloads configuration and clears internal caches.
        Call this when model configurations change to ensure fresh clients.
        """
        self._llm_clients.clear()
        self.config_manager.config = self.config_manager.load_or_initialize_config()

    def _get_api_key_for_provider(self, provider_name: str, model_config: Optional[ModelConfig]) -> Optional[str]:
        """
        Resolves the API key for a given provider, prioritizing model_config over environment variables.
        """
        if model_config and model_config.api_key:
            return model_config.api_key.get_secret_value()

        key_name = f"{provider_name.upper()}_API_KEY"
        return os.getenv(key_name)

    @lru_cache(maxsize=1)
    def get_main_agent(self) -> Agent:
        """
        Creates and returns the main agent using the main model configuration.

        Returns:
            Agent: Configured pydantic-ai Agent
        """
        main_model_config: ModelConfig = self.config_manager.get_model_config(
            "main")
        if not main_model_config:
            raise RuntimeError("Main model configuration not found")

        provider_name = main_model_config.provider
        if provider_name != 'google':
            raise ValueError(
                f"Unsupported provider: {provider_name}. Only 'google' is supported for main agent.")

        api_key = self._get_api_key_for_provider(
            provider_name, main_model_config)

        # Create GoogleProvider instance, passing the API key (if available)
        # GoogleProvider constructor can take api_key as SecretStr or str
        # If api_key is None, GoogleProvider will rely on GOOGLE_API_KEY env var or ADC
        provider_instance = GoogleProvider(
            api_key=api_key if api_key else None
        )
        logfire.debug(f"Created GoogleProvider for main agent.")

        try:
            llm_model_instance = GoogleModel(
                model_name=main_model_config.model_name,
                provider=provider_instance  # Pass the explicitly created provider
            )
            logfire.debug(
                f"Instantiated GoogleModel '{main_model_config.model_name}' for main agent.")
        except Exception as e:
            logfire.error(
                f"Failed to instantiate Pydantic-AI GoogleModel for main agent '{main_model_config.model_name}': {e}",
                exc_info=True
            )
            raise RuntimeError(
                f"Pydantic-AI GoogleModel instantiation failed for main agent: {e}") from e

        return Agent(
            model=llm_model_instance,
            retries=3,
            system_prompt=MAIN_AGENT_SYSTEM_PROMPT,
            deps_type=AgentDependencies
        )

    @lru_cache(maxsize=1)
    def get_research_agent(self) -> Agent:
        """
        Creates and returns the research agent using the research model configuration.
        Falls back to main model if research model is not configured.

        Returns:
            Agent: Configured pydantic-ai Agent
        """
        research_model_config: Optional[ModelConfig] = self.config_manager.get_model_config(
            "research")
        if not research_model_config:
            raise RuntimeError(
                "Research model configuration not found. Please set up a research model in the configuration to use the research agent.")

        provider_name = research_model_config.provider
        if provider_name != 'google':
            raise ValueError(
                f"Unsupported provider: {provider_name}. Only 'google' is supported for research agent.")

        api_key = self._get_api_key_for_provider(
            provider_name, research_model_config)

        provider_instance = GoogleProvider(
            api_key=api_key if api_key else None
        )
        logfire.debug(f"Created GoogleProvider for research agent.")

        try:
            llm_model_instance = GoogleModel(
                model_name=research_model_config.model_name,
                provider=provider_instance  # Pass the explicitly created provider
            )
            logfire.debug(
                f"Instantiated GoogleModel '{research_model_config.model_name}' for research agent.")
        except Exception as e:
            logfire.error(
                f"Failed to instantiate Pydantic-AI GoogleModel for research agent '{research_model_config.model_name}': {e}",
                exc_info=True
            )
            raise RuntimeError(
                f"Pydantic-AI GoogleModel instantiation failed for research agent: {e}") from e

        return Agent(
            model=llm_model_instance,
            retries=2,
            system_prompt=MAIN_AGENT_SYSTEM_PROMPT,
            deps_type=AgentDependencies,
        )

    async def generate_text(self, prompt: str, model_type: Literal["main", "research"] = "main", **kwargs: Dict[str, Any]) -> str:
        """
        Generates text using the specified model type.

        Args:
            prompt: The input prompt to generate text from.
            model_type: "main" or "research" to select which model/agent configuration to use.

        Returns:
            str: The generated text response.
        """
        output_type = kwargs.pop("output_type", None)
        logfire.info(
            f"Generating text with output type: {output_type.__name__ if output_type else 'String'}")

        current_agent = self.get_main_agent() if model_type == "main" else self.get_research_agent()
        logfire.info("Starting text generation with agent: "
                    f"{current_agent.model.model_name} ({model_type})")

        try:
            result = await current_agent.run(
                prompt,
                output_type=output_type,  # Use the specified output type
                **kwargs
            )

            if not result or not result.output:
                logfire.error(
                    "Agent.run returned None or empty result.output for text generation.")
                raise ValueError("Agent did not return a valid response.")
            # Log first 100 chars
            logfire.debug(f"Generated  output successfully: {result}")

            generated_text = result.output

            return generated_text
        except Exception as e:
            logfire.error(f"Failed to generate text: {e}", exc_info=True)
            raise RuntimeError(f"Text generation failed: {e}") from e

    async def generate_text_with_research_tool(self, prompt: str, tools: List[pydantic_ai_tools.Tool], **kwargs: Dict[str, Any]) -> str:
        """
        Generates text using the specified model type.

        Args:
            prompt: The input prompt to generate text from.
            model_type: "main" or "research" to select which model/agent configuration to use.

        Returns:
            str: The generated text response.
        """
        logfire.info(
            f"Starting research with tools: {prompt[:100]}...")  # Log first 100 chars of prompt

        current_agent = self.get_research_agent()
        for tool in tools:
            if not isinstance(tool, pydantic_ai_tools.Tool):
                logfire.error(
                    f"Invalid tool type: {type(tool)}. Expected pydantic_ai_tools.Tool.")
                raise TypeError(
                    f"Invalid tool type: {type(tool)}. Expected pydantic_ai_tools.Tool.")
            else:
                current_agent._register_tool(tool)
                logfire.debug(f"Registered research tool: {tool}")

        logfire.debug(f"Using agent: {current_agent}")
        try:
            result = await current_agent.run(
                prompt,
                **kwargs
            )

            if not result or not result.output:
                logfire.error(
                    "Agent.run returned None or empty result.output for text generation.")
                raise ValueError("Agent did not return a valid response.")
            # Log first 100 chars
            logfire.debug(f"Generated  output successfully: {result}")

            generated_text = result.output

            return generated_text
        except Exception as e:
            logfire.error(f"Failed to generate text: {e}", exc_info=True)
            raise RuntimeError(f"Text generation failed: {e}") from e
