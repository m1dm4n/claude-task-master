from __future__ import annotations as _annotations

import json
import logfire
from typing import Any, Callable, Dict, Literal, Optional, List, Union
from datetime import datetime, timezone


from src.agent_prompts import (
    FIX_DEPENDENCIES_PROMPT
)
from src.data_models import ProjectPlan, Task, DependencyFixesLLMOutput
from .config_service import ConfigService

from .llm_components.agent_manager import AgentManager
from .llm_components.generation_service import GenerationService
from .llm_components.planning_and_task_llm import PlanningAndTaskLLM
from .llm_components.research_llm import ResearchLLM
from .llm_components.code_generation_llm import CodeGenerationLLM


class LLMService:
    """
    Encapsulates all LLM interaction logic, including text generation,
    task refinement, subtask generation, and dependency fixing.
    Manages LLMProvider and LLMGenerator internally.
    """

    def __init__(self, config_service: ConfigService):
        """
        Initialize LLMService.

        Args:
                config_service: ConfigService instance for accessing LLM configurations.
        """
        self.config_service = config_service
        self.agent_manager = AgentManager(self.config_service)
        self.generation_service = GenerationService(self.agent_manager)
        self.planning_and_task_llm = PlanningAndTaskLLM(
            self.agent_manager, self.generation_service)
        self.research_llm = ResearchLLM(
            self.agent_manager, self.generation_service)
        self.code_generation_llm = CodeGenerationLLM(
            self.agent_manager, self.generation_service)

    def reload_configuration(self) -> None:
        self.agent_manager.reload_configuration()

    async def generate_text(self, prompt: str, model_type: Literal["main", "research"] = "main", output_type: Optional[Any] = None, **kwargs: Dict[str, Any]) -> Any:
        return await self.generation_service.generate_text(prompt, model_type, output_type, **kwargs)

    async def generate_content_with_native_tools(self, prompt: str, tools: Optional[List[Any]] = None, model_type: Literal["main", "research"] = "research", **kwargs: Dict[str, Any]) -> Any:
        return await self.generation_service.generate_content_with_native_tools(prompt, tools, model_type, **kwargs)

    async def generate_plan(self, text_content: Optional[str] = "", project_goal: Optional[str] = "", num_tasks: Optional[int] = None, model_type: Literal["main", "research"] = "main") -> ProjectPlan:
        return await self.planning_and_task_llm.generate_plan(text_content, project_goal, num_tasks, model_type)

    async def refine_item(self, item_current_details: Task, refinement_instruction: str, model_type: Literal["main", "research"] = "main") -> Task:
        return await self.planning_and_task_llm.refine_item(item_current_details, refinement_instruction, model_type)

    async def research_query(self, task_title: str, query: str, tools: Optional[List[Any]] = None) -> Any:
        return await self.research_llm.research_query(task_title, query, tools)

    async def generate_subtasks(
            self,
            task_description: str,
            task_title: str,
            existing_subtasks: List[Task],
            num_subtasks: Optional[int] = None,
            prompt_override: Optional[str] = None,
            model_type: Literal["main", "research"] = "main"
    ) -> List[Task]:
        return await self.planning_and_task_llm.generate_subtasks(task_description, task_title, existing_subtasks, num_subtasks, prompt_override, model_type)

    async def generate_single_task_details(self, description_prompt: str, project_context: Optional[str] = None, model_type: Literal["main", "research"] = "main") -> Task:
        return await self.planning_and_task_llm.generate_single_task_details(description_prompt, project_context, model_type)

    async def generate_code_for_task(self, task: Task, use_research: bool = False) -> Optional[str]:
        """
        Generates code for a specific task using AI assistance.
        This is a placeholder and needs actual implementation for code generation.
        """
        return await self.code_generation_llm.generate_code_for_task(task, use_research)

    async def suggest_dependency_fixes(self, project_plan: ProjectPlan, validation_errors: Dict[str, List[str]], model_type: Literal["main", "research"] = "main") -> Optional[ProjectPlan]:
        """
        Suggests fixes for dependency issues in the project plan using AI assistance.
        """
        logfire.info(f"Suggesting dependency fixes using {model_type} model")

        current_plan_json = project_plan.model_dump_json(indent=2)
        errors_json = json.dumps(validation_errors, indent=2)

        full_prompt = (
            f"{FIX_DEPENDENCIES_PROMPT}\n\n"
            f"Current Project Plan:\n{current_plan_json}\n\n"
            f"Dependency Validation Errors:\n{errors_json}\n\n"
            f"Please return a JSON object conforming to `DependencyFixesLLMOutput` with suggested fixes. "
            f"Focus on resolving the reported errors by modifying dependencies or task structures."
        )

        try:
            llm_response: DependencyFixesLLMOutput = await self.generation_service.generate_text(
                full_prompt,
                model_type=model_type,
                output_type=DependencyFixesLLMOutput
            )

            logfire.info(
                f"Raw LLM response for dependency fixes: {llm_response.model_dump_json(indent=2)}")

            if llm_response and llm_response.suggested_fixes:
                logfire.info(
                    f"Successfully received {len(llm_response.suggested_fixes)} dependency fix suggestions from LLM.")

                updated_plan = project_plan.model_copy(deep=True)

                allowed_to_fix_missing_ids = bool(
                    validation_errors.get("missing_ids"))
                allowed_to_fix_circular = bool(
                    validation_errors.get("circular"))

                for fix in llm_response.suggested_fixes:
                    is_missing_id_fix = False
                    is_circular_fix = False

                    if allowed_to_fix_missing_ids:
                        for error_msg in validation_errors.get("missing_ids", []):
                            if str(fix.task_id) in error_msg:
                                is_missing_id_fix = True
                                break

                    if allowed_to_fix_circular:
                        for error_msg in validation_errors.get("circular", []):
                            if str(fix.task_id) in error_msg:
                                is_circular_fix = True
                                break

                    if (is_missing_id_fix and allowed_to_fix_missing_ids) or \
                       (is_circular_fix and allowed_to_fix_circular):
                        pass
                    else:
                        logfire.warning(
                            f"Skipping LLM suggested fix for task {fix.task_id} as it does not correspond to an allowed or reported error type based on input flags.")
                        continue

                    found_task = False
                    for task in updated_plan.tasks:
                        if task.id == fix.task_id:
                            task.dependencies = fix.new_dependencies
                            task.updated_at = datetime.now(timezone.utc)
                            found_task = True
                            logfire.info(
                                f"Applied fix for task {task.id}: new dependencies {task.dependencies}")
                            break
                        for subtask in task.subtasks:
                            if subtask.id == fix.task_id:
                                subtask.dependencies = fix.new_dependencies
                                subtask.updated_at = datetime.now(timezone.utc)
                                found_task = True
                                logfire.info(
                                    f"Applied fix for subtask {subtask.id}: new dependencies {subtask.dependencies}")
                                break
                    if not found_task:
                        logfire.warning(
                            f"Task/subtask with ID {fix.task_id} not found in plan for applying fix.")

                return updated_plan
            else:
                logfire.warning(
                    "LLM did not provide dependency fix suggestions or returned an empty list.")
                return project_plan
        except Exception as e:
            logfire.error(
                f"Error suggesting dependency fixes: {e}", exc_info=True)
            raise RuntimeError(f"Dependency fix suggestion failed: {e}") from e

    async def close(self):
        """
        Asynchronously closes all initialized Pydantic-AI Agent instances and their underlying providers.
        """
        logfire.info("Closing LLMService agents and providers...")
        await self.agent_manager.close()
        logfire.info("All LLMService agents and providers closed.")
