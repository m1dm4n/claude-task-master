from typing import Optional, List, Any
import logfire

from src.agent_prompts import RESEARCH_LLM_PROMPT_PREFIX, RESEARCH_QUERY_INSTRUCTION


class ResearchLLM:
    def __init__(self, agent_manager, generation_service):
        self.agent_manager = agent_manager
        self.generation_service = generation_service

    async def research_query(self, task_title: str, query: str, tools: Optional[List[Any]] = None) -> Any:
        """
        Perform a research query using the research model.

        Args:
            query: Research query
            tools: Optional tools to make available

        Returns:
            Research results
        """
        research_prompt = f"{RESEARCH_LLM_PROMPT_PREFIX}\n\n{RESEARCH_QUERY_INSTRUCTION}\n\n".format(
            query=query,
            task_title=task_title
        )

        try:
            result = await self.generation_service.generate_content_with_native_tools(research_prompt, tools)
            return result
        except Exception as e:
            logfire.error(f"Error performing research query: {e}")
            raise