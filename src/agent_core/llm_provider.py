from __future__ import annotations as _annotations

import asyncio
import os
import json
from functools import lru_cache
from typing import Any, Callable, Dict, Literal, Optional, List, Union
from uuid import UUID
from dataclasses import dataclass

import logfire

from pydantic_ai import tools as pydantic_ai_tools
from pydantic_ai import Agent
from pydantic import ValidationError
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


class LLMProvider:
    """
    Direct LLM SDK interaction, manages Agent instances, API calls.
    """
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize LLMProvider with a ConfigManager instance.

        Args:
            config_manager: ConfigManager instance for accessing model configurations
        """
        self.config_manager = config_manager
        self._llm_clients: Dict[str, Any] = {}
        self._current_agent_runtime_params: Optional[Dict[str, Any]] = None
        self._agents: Dict[str, Agent] = {}

    def reload_configuration(self) -> None:
        """
        Reloads configuration and clears internal caches.
        Call this when model configurations change to ensure fresh clients.
        """
        self._llm_clients.clear()
        self.config_manager.config = self.config_manager.load_or_initialize_config()
        self._agents.clear()
        self.get_main_agent.cache_clear()
        self.get_research_agent.cache_clear()

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
        if "main" in self._agents:
            return self._agents["main"]

        main_model_config: ModelConfig = self.config_manager.get_model_config("main")
        if not main_model_config:
            raise RuntimeError("Main model configuration not found")

        provider_name = main_model_config.provider
        if provider_name != 'google':
            raise ValueError(f"Unsupported provider: {provider_name}. Only 'google' is supported for main agent.")

        api_key = self._get_api_key_for_provider(provider_name, main_model_config)

        provider_instance = GoogleProvider(api_key=api_key if api_key else None)
        self._llm_clients["main_provider"] = provider_instance
        logfire.debug(f"Created GoogleProvider for main agent.")

        try:
            llm_model_instance = GoogleModel(
                model_name=main_model_config.model_name,
                provider=provider_instance
            )
            logfire.debug(f"Instantiated GoogleModel '{main_model_config.model_name}' for main agent.")
        except Exception as e:
            logfire.error(
                f"Failed to instantiate Pydantic-AI GoogleModel for main agent '{main_model_config.model_name}': {e}",
                exc_info=True
            )
            raise RuntimeError(f"Pydantic-AI GoogleModel instantiation failed for main agent: {e}") from e

        agent = Agent(
            model=llm_model_instance,
            retries=3,
            system_prompt=MAIN_AGENT_SYSTEM_PROMPT,
            deps_type=AgentDependencies
        )
        self._agents["main"] = agent
        return agent

    @lru_cache(maxsize=1)
    def get_research_agent(self) -> Agent:
        """
        Creates and returns the research agent using the research model configuration.
        Falls back to main model if research model is not configured.

        Returns:
            Agent: Configured pydantic-ai Agent
        """
        if "research" in self._agents:
            return self._agents["research"]

        research_model_config: Optional[ModelConfig] = self.config_manager.get_model_config("research")
        if not research_model_config:
            raise RuntimeError(
                "Research model configuration not found. Please set up a research model in the configuration to use the research agent.")

        provider_name = research_model_config.provider
        if provider_name != 'google':
            raise ValueError(f"Unsupported provider: {provider_name}. Only 'google' is supported for research agent.")

        api_key = self._get_api_key_for_provider(provider_name, research_model_config)

        provider_instance = GoogleProvider(api_key=api_key if api_key else None)
        self._llm_clients["research_provider"] = provider_instance
        logfire.debug(f"Created GoogleProvider for research agent.")

        try:
            llm_model_instance = GoogleModel(
                model_name=research_model_config.model_name,
                provider=provider_instance
            )
            logfire.debug(f"Instantiated GoogleModel '{research_model_config.model_name}' for research agent.")
        except Exception as e:
            logfire.error(
                f"Failed to instantiate Pydantic-AI GoogleModel for research agent '{research_model_config.model_name}': {e}",
                exc_info=True
            )
            raise RuntimeError(f"Pydantic-AI GoogleModel instantiation failed for research agent: {e}") from e

        agent = Agent(
            model=llm_model_instance,
            retries=2,
            system_prompt=MAIN_AGENT_SYSTEM_PROMPT,
            deps_type=AgentDependencies,
        )
        self._agents["research"] = agent
        return agent

    async def generate_text(self, prompt: str, model_type: Literal["main", "research"] = "main", output_type: Optional[Any] = None, **kwargs: Dict[str, Any]) -> Any:
        """
        Generates text using the specified model type.

        Args:
            prompt: The input prompt to generate text from.
            model_type: "main" or "research" to select which model/agent configuration to use.
            output_type: The Pydantic model to parse the output into.

        Returns:
            Any: The generated object response (Pydantic model instance or string).
        """
        logfire.info(
            f"Generating text with output type: {output_type.__name__ if output_type else 'String'}"
        )

        current_agent = self.get_main_agent() if model_type == "main" else self.get_research_agent()
        logfire.info("Starting text generation with agent: "
                     f"{current_agent.model.model_name} ({model_type})")

        try:
            result = await current_agent.run(
                prompt,
                output_type=output_type,
                **kwargs
            )

            if not result or not result.output:
                logfire.error(
                    "Agent.run returned None or empty result.output for text generation. Prompt: %s", prompt[:500]
                )
                raise ValueError("Agent did not return a valid response.")
            logfire.debug(f"Generated output successfully: {str(result.output)[:100]}")

            return result.output
        except ValidationError as ve:
            logfire.error(
                f"Pydantic-AI validation error during text generation: {ve}",
                prompt=prompt[:500],
                validation_errors=ve.errors(),
                exc_info=True
            )
            raise RuntimeError(f"Text generation failed due to validation error: {ve}") from ve
        except Exception as e:
            logfire.error(
                f"Failed to generate text: {e}", prompt=prompt, exc_info=True)
            raise RuntimeError(f"Text generation failed: {e}") from e

    async def generate_content_with_native_tools(self, prompt: str, tools: Optional[List[Any]] = None, model_type: Literal["main", "research"] = "research", **kwargs: Dict[str, Any]) -> Any:
        """
        Generates content using the specified model type with native tools.

        Args:
            prompt: The input prompt to generate content from.
            tools: List of native tools to make available to the LLM.
            model_type: "main" or "research" to select which model/agent configuration to use.

        Returns:
            Any: The generated content response.
        """
        logfire.info(f"Starting content generation with native tools using {model_type} model.")

        current_agent = self.get_main_agent() if model_type == "main" else self.get_research_agent()
        
        # Register tools with the agent
        if tools:
            for tool in tools:
                if not isinstance(tool, pydantic_ai_tools.Tool):
                    logfire.warning(f"Skipping invalid tool type: {type(tool)}. Expected pydantic_ai_tools.Tool.")
                    continue
                current_agent._register_tool(tool)
                logfire.debug(f"Registered native tool: {tool.name}")

        try:
            result = await current_agent.run(
                prompt,
                **kwargs
            )

            if not result or not result.output:
                logfire.error(
                    "Agent.run returned None or empty result.output for content generation with native tools. Prompt: %s", prompt[:500]
                )
                raise ValueError("Agent did not return a valid response.")
            logfire.debug(f"Generated output with native tools successfully: {str(result.output)[:100]}")

            return result.output
        except ValidationError as ve:
            logfire.error(
                f"Pydantic-AI validation error during content generation with native tools: {ve}",
                prompt=prompt[:500],
                validation_errors=ve.errors(),
                exc_info=True
            )
            raise RuntimeError(f"Content generation with native tools failed due to validation error: {ve}") from ve
        except Exception as e:
            logfire.error(
                f"Failed to generate content with native tools: {e}", prompt=prompt[:500], exc_info=True)
            raise RuntimeError(f"Content generation with native tools failed: {e}") from e

    async def close(self):
        """
        Asynchronously closes all initialized Pydantic-AI Agent instances and their underlying providers.
        """
        logfire.info("Closing LLMProvider agents and providers...")
        for agent_name, agent_instance in list(self._agents.items()):
            try:
                if hasattr(agent_instance, 'aclose'):
                    await agent_instance.aclose()
                    logfire.debug(f"Closed agent '{agent_name}'")
                elif hasattr(agent_instance.model, 'aclose'):
                    await agent_instance.model.aclose()
                    logfire.debug(f"Closed model for agent '{agent_name}'")
                else:
                    logfire.debug(f"No explicit aclose method for agent '{agent_name}' or its model.")
            except Exception as e:
                logfire.error(f"Error closing agent '{agent_name}': {e}", exc_info=True)
            finally:
                del self._agents[agent_name]

        for provider_name, provider_instance in list(self._llm_clients.items()):
            try:
                if hasattr(provider_instance, 'aclose'):
                    await provider_instance.aclose()
                    logfire.debug(f"Closed provider '{provider_name}'")
                else:
                    logfire.debug(f"No explicit aclose method for provider '{provider_name}'.")
            except Exception as e:
                logfire.error(f"Error closing provider '{provider_name}': {e}", exc_info=True)
            finally:
                del self._llm_clients[provider_name]

        logfire.info("All LLMProvider agents and providers closed.")