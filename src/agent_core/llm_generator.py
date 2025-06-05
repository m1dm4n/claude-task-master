import json
import logfire
from datetime import datetime, timezone
from typing import Optional, List, Any, Dict, Literal, Union
from uuid import UUID, uuid4

from pydantic_ai import tools as pydantic_ai_tools

from ..data_models import ProjectPlan, Task, TaskStatus, TaskPriority, TaskLLMOutput, SubtaskLLMInput, DependencyFixesLLMOutput
from ..agent_prompts import (
    REFINE_TASK_PROMPT,
    RESEARCH_LLM_PROMPT_PREFIX,
    RESEARCH_QUERY_INSTRUCTION,
    EXPAND_TASK_TO_SUBTASKS_PROMPT,
    PLAN_PROJECT_PROMPT_INSTRUCTION,
    PRD_TO_PROJECT_PLAN_PROMPT,
    CREATE_SINGLE_TASK_PROMPT,
    FIX_DEPENDENCIES_PROMPT
)
from .llm_provider import LLMProvider


class LLMGenerator:
    """
    Handles prompt construction and orchestrates LLM generation tasks.
    Calls LLMProvider for direct LLM interaction.
    """

    def __init__(self, llm_provider: LLMProvider):
        """
        Initialize LLMGenerator.

        Args:
            llm_provider: LLMProvider instance for LLM interactions.
        """
        self.llm_provider = llm_provider

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
            return await self.llm_provider.generate_text(
                full_prompt_for_agent,
                model_type=model_type,
                output_type=ProjectPlan,
            )
        except Exception as e:
            logfire.error(
                f"Failed to generate or validate ProjectPlan: {e}", exc_info=True)
            raise RuntimeError(f"Failed to generate project plan: {e}") from e

    async def refine_item_details(self, item_current_details: Task, refinement_instruction: str, model_type: Literal["main", "research"] = "main") -> Optional[Task]:
        """
        Refine the details of a Task or Task using AI assistance.

        Args:
            item_current_details: The current Task object to refine
            refinement_instruction: Instructions for how to refine the item
            model_type: Which model to use for refinement ("main" or "research")

        Returns:
            The refined Task object with updated details
        """
        original_id = item_current_details.id
        original_created_at = item_current_details.created_at
        item_type = type(item_current_details).__name__

        current_item_json = item_current_details.model_dump_json(indent=2)
        try:
            refined_data = await self.llm_provider.generate_text(
                (
                    f"{REFINE_TASK_PROMPT}\n\n"
                    f"Current {item_type} Details:\n"
                    f"{current_item_json}\n\n"
                    f"Refinement Instruction:\n"
                    f"{refinement_instruction}\n\n"
                    f"Please return the complete refined {item_type} object as valid JSON. "
                    f"Remember to preserve the 'id' and 'created_at' fields exactly as they are, "
                    f"but update 'updated_at' to the current UTC timestamp."
                ),
                model_type=model_type,
                output_type=Task,
            )

            refined_task_dict = refined_data.model_dump()
            refined_task_dict['id'] = original_id
            refined_task_dict['created_at'] = original_created_at
            refined_task_dict['updated_at'] = datetime.now(timezone.utc)

            if 'subtasks' in refined_task_dict and refined_task_dict['subtasks']:
                processed_subtasks = []
                for subtask_data in refined_task_dict['subtasks']:
                    if isinstance(subtask_data, Task):
                        subtask_data = subtask_data.model_dump()

                    if 'id' not in subtask_data or not subtask_data['id']:
                        subtask_data['id'] = uuid4()
                    else:
                        subtask_data['id'] = UUID(str(subtask_data['id']))

                    if 'status' not in subtask_data:
                        subtask_data['status'] = TaskStatus.PENDING
                    if 'created_at' not in subtask_data:
                        subtask_data['created_at'] = datetime.now(timezone.utc)
                    if 'updated_at' not in subtask_data:
                        subtask_data['updated_at'] = datetime.now(timezone.utc)
                    if 'priority' not in subtask_data:
                        subtask_data['priority'] = TaskPriority.MEDIUM
                    
                    processed_subtasks.append(Task(**subtask_data))

                refined_task_dict['subtasks'] = processed_subtasks

            final_refined_task = Task(**refined_task_dict)

            logfire.info(f"Successfully refined {item_type.lower()} {original_id}")
            return final_refined_task
        except Exception as e:
            logfire.error(f"Error refining {item_type.lower()} {original_id}: {e}")
            raise RuntimeError(f"Item refinement failed: {e}") from e

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
            result = await self.llm_provider.generate_content_with_native_tools(research_prompt, tools)
            return result
        except Exception as e:
            logfire.error(f"Error performing research query: {e}")
            raise

    async def generate_subtasks_for_task(
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
                f"Please generate a JSON array of new task objects. "
                f"Each object should conform to the Task model with fields: "
                f"id (UUID), title, description, status (always 'PENDING'), priority, "
                f"created_at (current UTC timestamp), updated_at (current UTC timestamp), "
                f"and optional fields: details, testStrategy, dependencies, due_date, parent_id."
            )

            generated_tasks_data = await self.llm_provider.generate_text(
                full_prompt,
                model_type=model_type,
                output_type=List[Task] # Expect a list of Task objects directly
            )

            new_subtasks = []
            for subtask_data in generated_tasks_data:
                try:
                    # Ensure new UUID for subtasks generated by LLM
                    subtask_data.id = uuid4()
                    subtask_data.status = TaskStatus.PENDING
                    subtask_data.created_at = datetime.now(timezone.utc)
                    subtask_data.updated_at = datetime.now(timezone.utc)
                    if not subtask_data.priority:
                        subtask_data.priority = TaskPriority.MEDIUM
                    
                    new_subtasks.append(subtask_data)
                except Exception as e:
                    logfire.error(f"Error processing generated subtask data: {subtask_data}. Error: {e}. Skipping this subtask.")
                    continue
            
            logfire.info(f"Generated {len(new_subtasks)} subtasks for task '{task_title}'")
            return new_subtasks

        except Exception as e:
            logfire.error(f"Error generating subtasks for task '{task_title}': {e}")
            return []

    async def generate_single_task(self, description_prompt: str, project_context: Optional[str] = None, model_type: Literal["main", "research"] = "main") -> Task:
        """
        Generate a single task from a user description using AI assistance.

        Args:
            description_prompt: User's description/prompt for the new task
            project_context: Optional project context summary for better task generation
            model_type: Which model to use for generation ("main" or "research")

        Returns:
            Task object with all necessary details populated
        """
        logfire.info(f"Generating single task using {model_type} model")

        context_section = ""
        if project_context:
            context_section = f"\n\nProject Context:\n{project_context}\n"

        full_prompt = (
            f"{CREATE_SINGLE_TASK_PROMPT}\n\n"
            f"Task Description/Prompt:\n{description_prompt}"
            f"{context_section}\n"
        )

        try:
            llm_output = await self.llm_provider.generate_text(
                full_prompt,
                model_type=model_type,
                output_type=TaskLLMOutput,
            )

            new_task = Task(
                id=uuid4(),
                title=llm_output.title,
                description=llm_output.description,
                status=llm_output.status if llm_output.status else TaskStatus.PENDING,
                priority=llm_output.priority if llm_output.priority else TaskPriority.MEDIUM,
                dependencies=llm_output.dependencies if llm_output.dependencies else [],
                details=llm_output.details,
                testStrategy=llm_output.testStrategy,
                due_date=llm_output.due_date,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            if llm_output.initial_subtasks:
                for subtask_input in llm_output.initial_subtasks:
                    try:
                        subtask_data = Task(
                            id=uuid4(),
                            title=subtask_input.title,
                            description=subtask_input.description,
                            parent_id=new_task.id,
                            status=TaskStatus.PENDING,
                            priority=subtask_input.priority if subtask_input.priority else TaskPriority.MEDIUM,
                            dependencies=subtask_input.dependencies if subtask_input.dependencies else [],
                            details=subtask_input.details,
                            testStrategy=subtask_input.testStrategy,
                            due_date=subtask_input.due_date,
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc)
                        )
                        new_task.subtasks.append(subtask_data)
                    except Exception as e:
                        logfire.error(f"Error processing initial subtask from LLM: {subtask_input}. Error: {e}. Skipping this subtask.")
                        continue

            logfire.info(f"Successfully generated single task: {new_task.title}")
            return new_task

        except Exception as e:
            logfire.error(f"Error generating single task: {e}", exc_info=True)
            raise RuntimeError(f"Task generation failed: {e}") from e

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
            llm_response: DependencyFixesLLMOutput = await self.llm_provider.generate_text(
                full_prompt,
                model_type=model_type,
                output_type=DependencyFixesLLMOutput
            )
            
            logfire.info(f"Raw LLM response for dependency fixes: {llm_response.model_dump_json(indent=2)}")

            if llm_response and llm_response.suggested_fixes:
                logfire.info(f"Successfully received {len(llm_response.suggested_fixes)} dependency fix suggestions from LLM.")
                
                updated_plan = project_plan.model_copy(deep=True)
                
                allowed_to_fix_missing_ids = bool(validation_errors.get("missing_ids"))
                allowed_to_fix_circular = bool(validation_errors.get("circular"))

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
                        logfire.warning(f"Skipping LLM suggested fix for task {fix.task_id} as it does not correspond to an allowed or reported error type based on input flags.")
                        continue

                    found_task = False
                    for task in updated_plan.tasks:
                        if task.id == fix.task_id:
                            task.dependencies = fix.new_dependencies
                            task.updated_at = datetime.now(timezone.utc)
                            found_task = True
                            logfire.info(f"Applied fix for task {task.id}: new dependencies {task.dependencies}")
                            break
                        for subtask in task.subtasks:
                            if subtask.id == fix.task_id:
                                subtask.dependencies = fix.new_dependencies
                                subtask.updated_at = datetime.now(timezone.utc)
                                found_task = True
                                logfire.info(f"Applied fix for subtask {subtask.id}: new dependencies {subtask.dependencies}")
                                break
                    if not found_task:
                        logfire.warning(f"Task/subtask with ID {fix.task_id} not found in plan for applying fix.")
                
                return updated_plan
            else:
                logfire.warning("LLM did not provide dependency fix suggestions or returned an empty list.")
                return project_plan
        except Exception as e:
            logfire.error(f"Error suggesting dependency fixes: {e}", exc_info=True)
            raise RuntimeError(f"Dependency fix suggestion failed: {e}") from e

    async def generate_code(self, task: Task, use_research: bool = False) -> Optional[str]:
        """
        Generates code for a specific task using AI assistance.
        This is a placeholder and needs actual implementation for code generation.
        """
        logfire.info(f"Generating code for task '{task.title}' (ID: {task.id})...")
        # Placeholder for actual code generation logic
        # This would involve more complex prompts, potentially multiple LLM calls,
        # and integration with other tools (e.g., file system access, external APIs).
        
        # Example: A very simple prompt for code generation
        code_prompt = (
            f"Generate Python code to implement the following task:\n\n"
            f"Task Title: {task.title}\n"
            f"Task Description: {task.description}\n"
            f"Details: {task.details if task.details else 'No specific details provided.'}\n"
            f"Test Strategy: {task.testStrategy if task.testStrategy else 'No specific test strategy provided.'}\n\n"
            f"Provide only the code, no explanations or additional text."
        )

        try:
            generated_code = await self.llm_provider.generate_text(
                code_prompt,
                model_type="research" if use_research else "main",
                output_type=str # Expect raw string output for code
            )
            logfire.info(f"Successfully generated code for task {task.id}.")
            return generated_code
        except Exception as e:
            logfire.error(f"Error generating code for task {task.id}: {e}", exc_info=True)
            return None