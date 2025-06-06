from typing import Any, Dict, Literal, Optional, List
import logfire
from pydantic import ValidationError

from pydantic_ai import tools as pydantic_ai_tools
from src.agent_core.llm_models import ProjectPlanLLMOutput

class LLMGenerationError(Exception):
    """Custom exception for LLM generation failures."""
    pass


class GenerationService:
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager

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

        current_agent = self.agent_manager.get_main_agent() if model_type == "main" else self.agent_manager.get_research_agent()
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
                    "Agent.run returned None or empty result.output for text generation. Prompt: %s", prompt=prompt[:500]
                )
                raise LLMGenerationError("Agent did not return a valid response.")

            logfire.debug(f"Generated output successfully: {str(result.output)[:100]}")
            return result.output

        except ValidationError as ve:
            logfire.error(
                f"Pydantic-AI validation error during text generation: {ve}",
                prompt=prompt[:500],
                validation_errors=ve.errors(),
                exc_info=True
            )
            raise LLMGenerationError(f"Text generation failed due to validation error: {ve}") from ve
        except Exception as e:
            logfire.error(
                f"Failed to generate text: {e}", prompt=prompt, exc_info=True)
            raise LLMGenerationError(f"Text generation failed: {e}") from e

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

        current_agent = self.agent_manager.get_main_agent() if model_type == "main" else self.agent_manager.get_research_agent()
        
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
                    "Agent.run returned None or empty result.output for content generation with native tools. Prompt: %s", prompt=prompt[:500]
                )
                raise ValueError("Agent did not return a valid response.")
            logfire.debug(f"Generated output with native tools successfully: {str(result.output)[:100]}")

        except ValidationError as ve:
            logfire.error(
                f"Pydantic-AI validation error during content generation with native tools: {ve}",
                prompt=prompt[:500],
                validation_errors=ve.errors(),
                exc_info=True
            )
            raise LLMGenerationError(f"Content generation with native tools failed due to validation error: {ve}") from ve
        except Exception as e:
            logfire.error(
                f"Failed to generate content with native tools: {e}", prompt=prompt, exc_info=True)
            raise LLMGenerationError(f"Content generation with native tools failed: {e}") from e