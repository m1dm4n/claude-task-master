from __future__ import annotations as _annotations

import asyncio
import os
import json
from functools import lru_cache
from typing import Any, Callable, Dict, Literal, Optional, List, Union
from uuid import UUID  # Import for UUID validation
from dataclasses import dataclass

import logfire

from pydantic import SecretStr
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from ..config_manager import ConfigManager
from ..data_models import ModelConfig, ProjectPlan
from ..agent_prompts import (
    PLAN_PROJECT_PROMPT_INSTRUCTION,
    PRD_TO_PROJECT_PLAN_PROMPT)


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
            retries=1,
            deps_type=AgentDependencies
        )

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
            logfire.warn(
                "Research model configuration not found, falling back to main model for research agent.")
            research_model_config = self.config_manager.get_model_config(
                "main")

        if not research_model_config:
            raise RuntimeError(
                "No research or main model configuration found for research agent.")

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
            retries=1,
            deps_type=AgentDependencies
        )

    async def generate_plan_from_text(self, text_content: str = "", project_goal: str = "", num_tasks: Optional[int] = None, model_type: Literal["main", "research"] = "main") -> ProjectPlan:
        """
        Generates a project plan from text content (e.g., PRD) or a simple project goal.

        Args:
            text_content: The full text content to parse (e.g., PRD, detailed description).
                          If provided, takes precedence over project_goal for prompt selection.
            project_goal: A concise string representing the overall project goal. Used if text_content is empty.
            num_tasks: Optional. The desired number of main tasks in the plan.
            model_type: "main" or "research" to select which model/agent configuration to use.

        Returns:
            ProjectPlan: A structured project plan.
        """
        logfire.info(
            f"Generating project plan from text. Model type: {model_type}")

        current_agent = self.get_main_agent(
        ) if model_type == "main" else self.get_research_agent()

        # Determine which base prompt and user input to use
        if text_content:
            base_prompt = PRD_TO_PROJECT_PLAN_PROMPT
            user_input_content = f"PRD Content:\n{text_content}\n\nProject Goal (for context): {project_goal}"
        elif project_goal:
            base_prompt = PLAN_PROJECT_PROMPT_INSTRUCTION
            user_input_content = f"Project Goal: {project_goal}"
        else:
            raise ValueError(
                "Either 'text_content' or 'project_goal' must be provided.")

        if num_tasks is not None:
            user_input_content += f"\n\nFocus on generating approximately {num_tasks} main tasks."

        # Construct the final prompt for the agent
        full_prompt_for_agent = (
            f"{base_prompt}\n\n"
            f"User Request:\n{user_input_content}\n\n"
        )
        logfire.debug(
            f"Attempting to generate ProjectPlan with prompt (first 500 chars): {full_prompt_for_agent[:500]}")

        try:
            # The agent.run method with output_type=ProjectPlan is critical here.
            # It instructs Pydantic AI to parse the LLM's response into a ProjectPlan
            # object and validate it against the Pydantic schema.
            result = await current_agent.run(full_prompt_for_agent, output_type=ProjectPlan)

            if not result or not result.output:
                logfire.error(
                    "Agent.run returned None or empty result.output for ProjectPlan generation.")
                raise ValueError(
                    "Agent did not return a valid ProjectPlan response.")

            project_plan: ProjectPlan = result.output

            logfire.info(
                "Successfully generated and validated ProjectPlan using pydantic-ai.",
                project_title=project_plan.project_title,
                num_tasks_generated=len(project_plan.tasks)
            )
            return project_plan
        except Exception as e:
            logfire.error(
                f"Failed to generate or validate ProjectPlan: {e}", exc_info=True)
            raise RuntimeError(f"Failed to generate project plan: {e}") from e
