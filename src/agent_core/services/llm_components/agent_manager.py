import os
from functools import lru_cache
import logfire
from typing import Any, Dict, Literal, Optional
from dataclasses import dataclass

from pydantic_ai import Agent
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.models.google import GoogleModel

from src.data_models import ModelConfig
from src.agent_prompts import MAIN_AGENT_SYSTEM_PROMPT


@dataclass
class AgentDependencies:
	pass


logfire.configure(send_to_logfire='if-token-present')


class AgentManager:
    def __init__(self, config_service):
        self.config_service = config_service
        self._llm_clients: Dict[str, Any] = {}
        self._agents: Dict[str, Agent] = {}

    def reload_configuration(self) -> None:
        """
        Reloads configuration and clears internal caches.
        Call this when model configurations change to ensure fresh clients.
        """
        self._llm_clients.clear()
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

        main_model_config: ModelConfig = self.config_service.get_model_config("main")
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
            deps_type=AgentDependencies,
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

        research_model_config: Optional[ModelConfig] = self.config_service.get_model_config("research")
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

    async def close(self):
        """
        Asynchronously closes all initialized Pydantic-AI Agent instances and their underlying providers.
        """
        logfire.info("Closing LLMService agents and providers...")
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
        logfire.info("All LLMService agents and providers closed.")