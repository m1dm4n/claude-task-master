"""LLM interactions and model configuration management for the DevTask AI Assistant."""

from datetime import datetime
from typing import Optional, List, Any, Dict, Literal, Union
from uuid import UUID

import logfire
from pydantic_ai import Agent

from ..data_models import Task, ModelConfig
from ..config_manager import ConfigManager
from .llm_services import LLMService, AgentDependencies
from ..agent_prompts import (
    MAIN_AGENT_SYSTEM_PROMPT,
    REFINE_TASK_PROMPT_INSTRUCTION,
    RESEARCH_LLM_PROMPT_PREFIX,
    RESEARCH_QUERY_INSTRUCTION
)


class LLMManager:
    """Manages LLM interactions and model configurations."""
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize LLMManager.
        
        Args:
            config_manager: ConfigManager instance
        """
        self.config_manager = config_manager
        
        # Initialize LLM service with config manager
        self.llm_service = LLMService(self.config_manager)
        
        # Initialize main agent
        self._main_agent = self.llm_service.get_main_agent()
        self._main_agent.system_prompt = MAIN_AGENT_SYSTEM_PROMPT.format(current_date=datetime.now().strftime('%Y-%m-%d'))
    
    def get_model_configurations(self) -> Dict[str, Optional[ModelConfig]]:
        """
        Get all model configurations.
        
        Returns:
            Dict mapping model type to ModelConfig
        """
        return self.config_manager.get_all_model_configs()
    
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
            model_type: Type of model to configure
            model_name: Name of the model
            provider: Provider name (optional, inferred from model_name if not provided)
            api_key_str: API key string (optional)
            base_url_str: Base URL string (optional)
            
        Returns:
            True if configuration was set successfully, False otherwise
        """
        try:
            # Create ModelConfig object
            model_config_data = {"model_name": model_name}
            
            if provider:
                model_config_data["provider"] = provider
            else:
                # Try to infer provider from model name
                if "gpt" in model_name.lower() or "openai" in model_name.lower():
                    model_config_data["provider"] = "openai"
                elif "claude" in model_name.lower() or "anthropic" in model_name.lower():
                    model_config_data["provider"] = "anthropic"
                elif "gemini" in model_name.lower() or "google" in model_name.lower():
                    model_config_data["provider"] = "google"
                else:
                    model_config_data["provider"] = "unknown"
            
            if api_key_str:
                from pydantic import SecretStr
                model_config_data["api_key"] = SecretStr(api_key_str)
                
            if base_url_str:
                from pydantic import AnyHttpUrl
                model_config_data["base_url"] = AnyHttpUrl(base_url_str)
            
            model_config = ModelConfig(**model_config_data)
            
            # Set the configuration
            self.config_manager.set_model_config(model_type, model_config)
            
            # Reload LLM service to pick up new configuration
            self.llm_service.reload_configuration()
            
            # Re-initialize main agent with new configuration
            self._main_agent = self.llm_service.get_main_agent()
            self._main_agent.system_prompt = MAIN_AGENT_SYSTEM_PROMPT.format(current_date=datetime.now().strftime('%Y-%m-%d'))
            
            logfire.info(f"Successfully configured {model_type} model: {model_name}")
            return True
            
        except Exception as e:
            logfire.error(f"Error setting model configuration: {e}")
            return False
    
    async def refine_task(self, task: Task, refinement_prompt: str, use_research: bool = False, deps: Optional[AgentDependencies] = None) -> Optional[Task]:
        """
        Refine a specific task using AI assistance.
        
        Args:
            task: Task object to refine
            refinement_prompt: Instructions for refining the task
            use_research: Whether to use research model for refinement
            deps: Optional agent dependencies
            
        Returns:
            Refined Task object or None if refinement failed
        """
        full_system_prompt = self._main_agent.system_prompt + "\n\n" + REFINE_TASK_PROMPT_INSTRUCTION

        try:
            if use_research:
                # Use research model via native tools if available
                research_prompt = f"{RESEARCH_LLM_PROMPT_PREFIX}\n\nTask to refine:\n{task.model_dump_json(indent=2)}\n\nRefinement request: {refinement_prompt}"
                research_result = await self.llm_service.generate_content_with_native_tools(research_prompt)
                
                # Use research result to inform the main agent
                response = await self._main_agent.run(
                    f"Task to refine: {task.model_dump_json(indent=2)}\n\nRefinement request: {refinement_prompt}\n\nAdditional research context: {research_result}",
                    output_type=Task,
                    system_prompt=full_system_prompt,
                    deps=deps
                )
            else:
                response = await self._main_agent.run(
                    f"Task to refine: {task.model_dump_json(indent=2)}\n\nRefinement request: {refinement_prompt}",
                    output_type=Task,
                    system_prompt=full_system_prompt,
                    deps=deps
                )

            return response.output

        except Exception as e:
            logfire.error(f"Error refining task {task.id}: {e}")
            return None
    
    async def research_query(self, query: str, tools: Optional[List[Any]] = None) -> Any:
        """
        Perform a research query using the research model.
        
        Args:
            query: Research query
            tools: Optional tools to make available
            
        Returns:
            Research results
        """
        research_prompt = f"{RESEARCH_LLM_PROMPT_PREFIX}\n\n{RESEARCH_QUERY_INSTRUCTION}\n\nQuery: {query}"
        
        try:
            result = await self.llm_service.generate_content_with_native_tools(research_prompt, tools)
            return result
        except Exception as e:
            logfire.error(f"Error performing research query: {e}")
            raise