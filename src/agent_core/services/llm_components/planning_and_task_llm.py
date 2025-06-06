from typing import Optional, Literal, List, Dict
from uuid import uuid4
from datetime import datetime, timezone
import logfire

from src.data_models import ProjectPlan, Task, TaskStatus, TaskPriority
from src.agent_prompts import (
    PRD_TO_PROJECT_PLAN_PROMPT,
    REFINE_TASK_PROMPT,
    EXPAND_TASK_TO_SUBTASKS_PROMPT,
    PLAN_PROJECT_PROMPT_INSTRUCTION,
    CREATE_SINGLE_TASK_PROMPT
)


class PlanningAndTaskLLM:
    def __init__(self, agent_manager, generation_service):
        self.agent_manager = agent_manager
        self.generation_service = generation_service

    async def generate_plan(self, text_content: Optional[str] = "", project_goal: Optional[str] = "", num_tasks: Optional[int] = None, model_type: Literal["main", "research"] = "main") -> ProjectPlan:
        """
        Generates a project plan from text content (e.g., PRD) or a simple project goal.

        Args:
            text_content: The full text content to parse (e.g., PRD, detailed description).
                              If provided, takes precedence over project_goal for prompt selection.
            project_goal: A concise string representing the overall project goal. Used if text_content is empty.
            num_tasks: Optional. The desired number of main tasks in the plan.
            model_type: Which model to use for generation

        Returns:
            ProjectPlan: A structured project plan.
        """
        logfire.info(
            f"Generating project plan from text. Model type: {'research' if model_type == 'research' else 'main'}"
        )

        if text_content and project_goal:
            base_prompt = PRD_TO_PROJECT_PLAN_PROMPT
            user_input_content = f"PRD Content:\n{text_content}\n\nProject Goal: {project_goal}"
        elif text_content:
            base_prompt = PRD_TO_PROJECT_PLAN_PROMPT
            user_input_content = f"PRD Content:\n{text_content}.\n\nProject Goal: Fully satisfy the requirements outlined in the PRD."
        elif project_goal:
            base_prompt = PLAN_PROJECT_PROMPT_INSTRUCTION
            user_input_content = f"Project Goal: {project_goal}."
        else:
            raise ValueError("Either 'text_content' or 'project_goal' must be provided.")

        if num_tasks is not None:
            user_input_content += f"\nFocus on generating around {num_tasks} main tasks."

        full_prompt_for_agent = (
            f"{base_prompt}\n\n"
            f"User Request:\n{user_input_content}\n\n"
        )
        logfire.debug(
            f"Attempting to generate ProjectPlan with prompt (first 500 chars): {full_prompt_for_agent[:500]}")
        try:
            project_plan: ProjectPlan = await self.generation_service.generate_text(
                full_prompt_for_agent,
                model_type=model_type,
                output_type=ProjectPlan,
            )

            if num_tasks is not None and len(project_plan.tasks) > num_tasks:
                logfire.info(f"Generated {len(project_plan.tasks)} tasks, truncating to {num_tasks}.")
                project_plan.tasks = project_plan.tasks[:num_tasks]

            return project_plan
        except Exception as e:
            logfire.error(
                f"Failed to generate or validate ProjectPlan: {e}", exc_info=True)
            raise RuntimeError(f"Failed to generate project plan: {e}") from e

    async def refine_item(self, item_current_details: Task, refinement_instruction: str, model_type: Literal["main", "research"] = "main") -> Task:
        """
        Refine the details of a Task using AI assistance.

        Args:
            item_current_details: The current Task object to refine
            refinement_instruction: Instructions for how to refine the item
            model_type: Which model to use for refinement

        Returns:
            The refined Task object with updated details
        """
        original_id = item_current_details.id
        original_created_at = item_current_details.created_at
        item_type = type(item_current_details).__name__

        current_item_json = item_current_details.model_dump_json(indent=2)
        try:
            refined_task = await self.generation_service.generate_text(
                (
                    f"{REFINE_TASK_PROMPT}\n\n"
                    f"Current {item_type} Details:\n"
                    f"{current_item_json}\n\n"
                    f"Refinement Instruction:\n"
                    f"{refinement_instruction}\n\n"
                    f"Please return the complete refined {item_type} object as valid JSON. "
                    f"Remember to preserve the 'id' and 'created_at' fields exactly as they are, "
                ),
                model_type=model_type,
                output_type=Task,
            )
            refined_task.id = original_id
            refined_task.created_at = original_created_at
            refined_task.updated_at = datetime.now(timezone.utc)
            return refined_task

        except Exception as e:
            logfire.error(f"Error refining {item_type.lower()} {original_id}: {e}")
            raise RuntimeError(f"Item refinement failed: {e}") from e

    async def generate_subtasks(
        self,
        task_description: str,
        task_title: str,
        existing_subtasks: List[Task],
        num_subtasks: Optional[int] = None,
        prompt_override: Optional[str] = None,
        model_type: Literal["main", "research"] = "main"
    ) -> List[Task]:
        """
        Generate subtasks for a given task using AI assistance.

        Args:
            task_description: Description of the main task
            task_title: Title of the main task
            existing_subtasks: List of existing subtasks (to avoid duplication)
            num_subtasks: Optional target number of subtasks to generate
            prompt_override: Optional additional context for subtask generation
            model_type: Which model to use for generation

        Returns:
            List of generated Task objects (representing subtasks)
        """
        try:
            existing_subtasks_info = ""
            if existing_subtasks:
                existing_subtasks_info = f"\n\nExisting subtasks:\n"
                for subtask in existing_subtasks:
                    existing_subtasks_info += f"- {subtask.title}: {subtask.description}\n"

            num_subtasks_instruction = ""
            if num_subtasks:
                num_subtasks_instruction = f"\n\nTarget number of subtasks: {num_subtasks}"
            prompt_override_instruction = ""
            if prompt_override:
                prompt_override_instruction = f"\n\nPrompt override: {prompt_override}"

            full_prompt = (
                f"{EXPAND_TASK_TO_SUBTASKS_PROMPT}\n\n"
                f"Task to break down:\n"
                f"Title: {task_title}\n"
                f"Description: {task_description}"
                f"{existing_subtasks_info}"
                f"{num_subtasks_instruction}"
                f"{prompt_override_instruction}\n\n"
                f"Each object should conform to the Task model with fields: "
                f"id (UUID), title, description, status (always 'PENDING'), priority, "
                f"created_at (current UTC timestamp), updated_at (current UTC timestamp), " # TODO: Remove this instruction, this is handled by the adapter
                f"and optional fields: details, testStrategy, dependencies, due_date, parent_id." # TODO: Remove this instruction, this is handled by the adapter
            )

            new_subtasks = await self.generation_service.generate_text(
                full_prompt,
                model_type=model_type,
                output_type=List[Task]
            )

            logfire.info(f"Generated {len(new_subtasks)} subtasks for task '{task_title}'")
            return new_subtasks
        except Exception as e:
            logfire.error(f"Error generating subtasks for task '{task_title}': {e}")
            return []
        except Exception as e:
            logfire.error(f"Error generating subtasks for task '{task_title}': {e}")
            return []
        except Exception as e:
            logfire.error(f"Error generating subtasks: {e}", exc_info=True)
            return []

    async def generate_single_task_details(self, description_prompt: str, project_context: Optional[str] = None, model_type: Literal["main", "research"] = "main") -> Task:
        """
        Generate a single task from a user description using AI assistance.

        Args:
            description_prompt: User's description/prompt for the new task
            project_context: Optional project context summary for better task generation
            model_type: Which model to use for generation

        Returns:
            Task object with all necessary details populated
        """
        logfire.info(f"Generating single task using {model_type} model")

        full_prompt = (
            f"{CREATE_SINGLE_TASK_PROMPT}\n\n"
            f"Task Description/Prompt:\n{description_prompt}\n"
            f"Project Context:\n{project_context}\n"
        )

        try:
            new_task: Task = await self.generation_service.generate_text(
                full_prompt,
                model_type=model_type,
                output_type=Task,
            )
            new_task.created_at = datetime.now(timezone.utc)
            new_task.updated_at = datetime.now(timezone.utc)
            new_task.id = str(uuid4())

            logfire.info(f"Successfully generated single task: {new_task.title}")
            return new_task

        except Exception as e:
            logfire.error(f"Error generating single task: {e}", exc_info=True)
            raise RuntimeError(f"Task generation failed: {e}") from e