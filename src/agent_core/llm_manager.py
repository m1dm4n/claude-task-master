"""LLM interactions and model configuration management for the DevTask AI Assistant."""

from datetime import datetime, timezone
from typing import Optional, List, Any, Dict, Literal, Union
from uuid import UUID
from uuid import uuid4
import logfire
import json
from pydantic import SecretStr, AnyHttpUrl
from ..data_models import ProjectPlan, Task, Subtask, ModelConfig
from ..config_manager import ConfigManager
from .llm_services import LLMService, AgentDependencies
from ..agent_prompts import (
    MAIN_AGENT_SYSTEM_PROMPT,
    REFINE_TASK_PROMPT_INSTRUCTION,
    REFINE_TASK_PROMPT,
    RESEARCH_LLM_PROMPT_PREFIX,
    RESEARCH_QUERY_INSTRUCTION,
    EXPAND_TASK_TO_SUBTASKS_PROMPT,
    PLAN_PROJECT_PROMPT_INSTRUCTION,
    PRD_TO_PROJECT_PLAN_PROMPT,
    CREATE_SINGLE_TASK_PROMPT,
    FIX_DEPENDENCIES_PROMPT # New import
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
        self._main_agent.system_prompt = MAIN_AGENT_SYSTEM_PROMPT.format(
            current_date=datetime.now().strftime('%Y-%m-%d'))

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
                model_config_data["api_key"] = SecretStr(api_key_str)

            if base_url_str:

                model_config_data["base_url"] = AnyHttpUrl(base_url_str)

            model_config = ModelConfig(**model_config_data)

            # Set the configuration
            self.config_manager.set_model_config(model_type, model_config)

            # Reload LLM service to pick up new configuration
            self.llm_service.reload_configuration()

            # Re-initialize main agent with new configuration
            self._main_agent = self.llm_service.get_main_agent()
            self._main_agent.system_prompt = MAIN_AGENT_SYSTEM_PROMPT.format(
                current_date=datetime.now().strftime('%Y-%m-%d'))

            logfire.info(
                f"Successfully configured {model_type} model: {model_name}")
            return True

        except Exception as e:
            logfire.error(f"Error setting model configuration: {e}")
            return False

    async def generate_plan_from_text(self, text_content: str = "", project_goal: str = "", num_tasks: Optional[int] = None, model_type: Literal["main", "research"] = "main", **kwargs: Dict[str, Any]) -> ProjectPlan:
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
    
        # Determine which base prompt and user input to use
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
            raise ValueError(
                "Either 'text_content' or 'project_goal' must be provided.")
        
        if num_tasks is not None:
            user_input_content += f"\nFocus on generating around {num_tasks} main tasks."

        # Construct the final prompt for the agent
        full_prompt_for_agent = (
            f"{base_prompt}\n\n"
            f"User Request:\n{user_input_content}\n\n"
        )
        logfire.debug(
            f"Attempting to generate ProjectPlan with prompt (first 500 chars): {full_prompt_for_agent[:500]}")
        try:
            return await self.llm_service.generate_text(
                full_prompt_for_agent,
                model_type=model_type,
                output_type=ProjectPlan,
                **kwargs
            )
        except Exception as e:
            logfire.error(
                f"Failed to generate or validate ProjectPlan: {e}", exc_info=True)
            raise RuntimeError(f"Failed to generate project plan: {e}") from e

    async def refine_task(self, task: Task, refinement_prompt: str, use_research: bool = False, **kwargs: Dict[str, Any]) -> Optional[Task]:
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
        full_system_prompt = self._main_agent.system_prompt + \
            "\n\n" + REFINE_TASK_PROMPT_INSTRUCTION
 
        try:
            if use_research:
                # Use research model via native tools if available
                research_prompt = f"{RESEARCH_LLM_PROMPT_PREFIX}\n\nTask to refine:\n{task.model_dump_json(indent=2)}\n\nRefinement request: {refinement_prompt}"
                research_result = await self.llm_service.generate_text_with_research_tool(research_prompt)
                logfire.debug(f"Research result for task {task.id}: {research_result}")

            return await self.llm_service.generate_text(
                f"Task to refine: {task.model_dump_json(indent=2)}\n\nRefinement request: {refinement_prompt}" +
                f"\n\nAdditional research context: {research_result}" if use_research else "",
                model_type="research" if use_research else "main",
                output_type=Task,
                system_prompt=full_system_prompt,
                **kwargs
            )

        except Exception as e:
            logfire.error(f"Error refining task {task.id}: {e}")
            return None

    async def refine_item_details(self, item_current_details: Union[Task, Subtask], refinement_instruction: str, model_type: Literal["main", "research"] = "main") -> Union[Task, Subtask]:
        """
        Refine the details of a Task or Subtask using AI assistance.
        
        Args:
            item_current_details: The current Task or Subtask object to refine
            refinement_instruction: Instructions for how to refine the item
            model_type: Which model to use for refinement ("main" or "research")
            
        Returns:
            The refined Task or Subtask object with updated details
            
        Raises:
            ValueError: If the LLM response cannot be parsed or is invalid
            RuntimeError: If refinement fails due to service errors
        """
        logfire.info(f"Refining {'task' if isinstance(item_current_details, Task) else 'subtask'} {item_current_details.id} using {model_type} model")
        
        # Store original immutable fields
        original_id = item_current_details.id
        original_created_at = item_current_details.created_at
        item_type = type(item_current_details).__name__
        
        # Prepare the prompt with current item details
        current_item_json = item_current_details.model_dump_json(indent=2)
        
        full_prompt = (
            f"{REFINE_TASK_PROMPT}\n\n"
            f"Current {item_type} Details:\n"
            f"{current_item_json}\n\n"
            f"Refinement Instruction:\n"
            f"{refinement_instruction}\n\n"
            f"Please return the complete refined {item_type} object as valid JSON. "
            f"Remember to preserve the 'id' and 'created_at' fields exactly as they are, "
            f"but update 'updated_at' to the current UTC timestamp."
        )
        
        try:
            # Generate the refined item using the LLM
            response_text = await self.llm_service.generate_text(
                full_prompt,
                model_type=model_type
            )
            
            # Parse the JSON response
            if isinstance(response_text, str):
                # Extract JSON from response if it's wrapped in text
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx:end_idx + 1]
                else:
                    json_str = response_text
            else:
                json_str = str(response_text)
            
            try:
                refined_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                logfire.error(f"Failed to parse JSON response for item refinement: {json_str}")
                raise ValueError(f"LLM returned invalid JSON: {e}") from e
            
            # Ensure immutable fields are preserved
            refined_data['id'] = str(original_id)
            refined_data['created_at'] = original_created_at.isoformat()
            
            # Update the updated_at timestamp
            refined_data['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # Create the refined object of the correct type
            if isinstance(item_current_details, Task):
                # Handle subtasks if present
                if 'subtasks' in refined_data and refined_data['subtasks']:
                    # Ensure subtasks have proper structure
                    for subtask_data in refined_data['subtasks']:
                        if 'id' not in subtask_data or not subtask_data['id']:
                            subtask_data['id'] = str(uuid4())
                        if 'status' not in subtask_data:
                            subtask_data['status'] = 'PENDING'
                        if 'created_at' not in subtask_data:
                            subtask_data['created_at'] = datetime.now(timezone.utc).isoformat()
                        if 'updated_at' not in subtask_data:
                            subtask_data['updated_at'] = datetime.now(timezone.utc).isoformat()
                
                refined_item = Task(**refined_data)
            else:
                refined_item = Subtask(**refined_data)
            
            logfire.info(f"Successfully refined {item_type.lower()} {original_id}")
            return refined_item
            
        except json.JSONDecodeError as e:
            logfire.error(f"JSON parsing error during item refinement: {e}")
            raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e
        except ValueError:
            # Re-raise ValueError (including those from JSON parsing issues) without wrapping
            raise
        except Exception as e:
            logfire.error(f"Error refining {item_type.lower()} {original_id}: {e}")
            raise RuntimeError(f"Item refinement failed: {e}") from e

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

    async def generate_subtasks_for_task(
        self,
        task_description: str,
        task_title: str,
        existing_subtasks: List[Subtask],
        num_subtasks: Optional[int] = None,
        context_prompt: Optional[str] = None,
        model_type: Literal["main", "research"] = "main"
    ) -> List[Subtask]:
        """
        Generate subtasks for a given task using AI assistance.

        Args:
            task_description: Description of the main task
            task_title: Title of the main task
            existing_subtasks: List of existing subtasks (to avoid duplication)
            num_subtasks: Optional target number of subtasks to generate
            context_prompt: Optional additional context for subtask generation
            model_type: Which model to use for generation

        Returns:
            List of generated Subtask objects
        """
        try:
            # Prepare the prompt with task information
            existing_subtasks_info = ""
            if existing_subtasks:
                existing_subtasks_info = f"\n\nExisting subtasks:\n"
                for subtask in existing_subtasks:
                    existing_subtasks_info += f"- {subtask.title}: {subtask.description}\n"

            num_subtasks_instruction = ""
            if num_subtasks:
                num_subtasks_instruction = f"\n\nTarget number of subtasks: {num_subtasks}"

            context_instruction = ""
            if context_prompt:
                context_instruction = f"\n\nAdditional context: {context_prompt}"

            full_prompt = (
                f"{EXPAND_TASK_TO_SUBTASKS_PROMPT}\n\n"
                f"Task to break down:\n"
                f"Title: {task_title}\n"
                f"Description: {task_description}"
                f"{existing_subtasks_info}"
                f"{num_subtasks_instruction}"
                f"{context_instruction}\n\n"
                f"Please generate a JSON array of new subtask objects. "
                f"Each object should conform to the Subtask model with fields: "
                f"id (UUID), title, description, status (always 'PENDING'), priority, "
                f"created_at (current UTC timestamp), updated_at (current UTC timestamp), "
                f"and optional fields: details, testStrategy, dependencies, due_date."
            )

            if model_type == "research":
                # Use research model
                result = await self.llm_service.generate_content_with_native_tools(full_prompt)
                response_text = str(result)
            else:
                # Use main agent
                response = await self._main_agent.run(
                    full_prompt,
                    system_prompt=EXPAND_TASK_TO_SUBTASKS_PROMPT
                )
                response_text = response.output

            # Parse the JSON response

            # Extract JSON from response if it's wrapped in text
            if isinstance(response_text, str):
                # Look for JSON array in the response
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']')
                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx:end_idx + 1]
                else:
                    json_str = response_text
            else:
                json_str = str(response_text)

            try:
                subtasks_data = json.loads(json_str)
            except json.JSONDecodeError:
                logfire.error(
                    f"Failed to parse JSON response for subtask generation: {json_str}")
                return []

            # Convert to Subtask objects
            subtasks = []
            for subtask_data in subtasks_data:
                try:
                    # Always generate fresh UUID
                    subtask_data['id'] = str(uuid4())

                    if 'status' not in subtask_data:
                        subtask_data['status'] = 'PENDING'

                    if 'created_at' not in subtask_data:
                        subtask_data['created_at'] = datetime.now(
                            timezone.utc).isoformat()

                    if 'updated_at' not in subtask_data:
                        subtask_data['updated_at'] = datetime.now(
                            timezone.utc).isoformat()

                    if 'priority' not in subtask_data:
                        subtask_data['priority'] = 'MEDIUM'

                    # Handle due_date conversion if present
                    if 'due_date' in subtask_data and subtask_data['due_date']:
                        due_date_str = subtask_data['due_date']
                        if isinstance(due_date_str, str):
                            try:
                                # Parse datetime string and extract date part
                                parsed_datetime = datetime.fromisoformat(
                                    due_date_str.replace('Z', '+00:00'))
                                subtask_data['due_date'] = parsed_datetime.date()
                            except ValueError:
                                # If parsing fails, remove the due_date field
                                logfire.warning(
                                    f"Failed to parse due_date '{due_date_str}', removing field")
                                subtask_data.pop('due_date', None)

                    # Create Subtask object
                    subtask = Subtask(**subtask_data)
                    subtasks.append(subtask)

                except Exception as e:
                    logfire.error(
                        f"Error creating subtask from data {subtask_data}: {e}")
                    continue

            logfire.info(
                f"Generated {len(subtasks)} subtasks for task '{task_title}'")
            return subtasks

        except Exception as e:
            logfire.error(
                f"Error generating subtasks for task '{task_title}': {e}")
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

        Raises:
            ValueError: If the LLM response cannot be parsed or is invalid
            RuntimeError: If task generation fails due to service errors
        """
        logfire.info(f"Generating single task using {model_type} model")
        
        # Prepare the full prompt with context
        context_section = ""
        if project_context:
            context_section = f"\n\nProject Context:\n{project_context}\n"
        
        full_prompt = (
            f"{CREATE_SINGLE_TASK_PROMPT}\n\n"
            f"Task Description/Prompt:\n{description_prompt}"
            f"{context_section}\n"
            f"Please generate a complete Task object as JSON. Remember to exclude "
            f"id, created_at, and updated_at fields as these will be set by the application."
        )
        
        try:
            # Generate the task using the LLM
            response_text = await self.llm_service.generate_text(
                full_prompt,
                model_type=model_type
            )
            
            # Parse the JSON response
            if isinstance(response_text, str):
                # Extract JSON from response if it's wrapped in text
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx:end_idx + 1]
                else:
                    json_str = response_text
            else:
                json_str = str(response_text)
            
            try:
                task_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                logfire.error(f"Failed to parse JSON response for task generation: {json_str}")
                raise ValueError(f"LLM returned invalid JSON: {e}") from e
            
            # Ensure required fields and defaults
            if 'status' not in task_data:
                task_data['status'] = 'PENDING'
            if 'priority' not in task_data:
                task_data['priority'] = 'MEDIUM'
            if 'dependencies' not in task_data:
                task_data['dependencies'] = []
            if 'subtasks' not in task_data:
                task_data['subtasks'] = []
            
            # Handle subtasks if present
            if task_data['subtasks']:
                for subtask_data in task_data['subtasks']:
                    # Generate unique ID for each subtask
                    if 'id' not in subtask_data or not subtask_data['id']:
                        subtask_data['id'] = str(uuid4())
                    if 'status' not in subtask_data:
                        subtask_data['status'] = 'PENDING'
                    if 'priority' not in subtask_data:
                        subtask_data['priority'] = 'MEDIUM'
                    if 'dependencies' not in subtask_data:
                        subtask_data['dependencies'] = []
                    if 'created_at' not in subtask_data:
                        subtask_data['created_at'] = datetime.now(timezone.utc).isoformat()
                    if 'updated_at' not in subtask_data:
                        subtask_data['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # Set timestamps and ID for the main task

            
            task_data['id'] = str(uuid4())
            task_data['created_at'] = datetime.now(timezone.utc).isoformat()
            task_data['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # Create the Task object
            try:
                task = Task(**task_data)
                logfire.info(f"Successfully generated task: {task.title}")
                return task
            except Exception as e:
                logfire.error(f"Failed to create Task object from data: {task_data}")
                raise ValueError(f"Invalid task data structure: {e}") from e
            
        except json.JSONDecodeError as e:
            logfire.error(f"JSON parsing error during task generation: {e}")
            raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e
        except ValueError:
            # Re-raise ValueError (including those from JSON parsing issues) without wrapping
            raise
        except Exception as e:
            logfire.error(f"Error generating single task: {e}")
            raise RuntimeError(f"Task generation failed: {e}") from e

    async def suggest_dependency_fixes(self, project_plan: ProjectPlan, validation_errors: Dict[str, List[str]], model_type: Literal["main", "research"] = "main") -> ProjectPlan:
        """
        Instructs the LLM to suggest dependency fixes for a given project plan and validation errors.

        Args:
            project_plan: The current ProjectPlan object.
            validation_errors: A dictionary of validation errors.
            model_type: Which model to use for generation ("main" or "research").

        Returns:
            A copy of the ProjectPlan with suggested dependency fixes applied.

        Raises:
            ValueError: If the LLM response cannot be parsed or is invalid.
            RuntimeError: If the dependency fix suggestion fails due to service errors.
        """
        logfire.info(f"Requesting dependency fixes using {model_type} model")

        # Serialize relevant parts of the project_plan for the LLM
        # We only need task IDs and their current dependencies for the LLM to suggest changes.
        # This reduces token usage.
        simplified_plan_for_llm = {
            "tasks": [
                {"id": str(task.id), "dependencies": [str(dep_id) for dep_id in task.dependencies]}
                for task in project_plan.tasks
            ]
        }

        project_plan_json = json.dumps(simplified_plan_for_llm, indent=2)
        validation_errors_json = json.dumps(validation_errors, indent=2)

        full_prompt = (
            f"{FIX_DEPENDENCIES_PROMPT}\n\n"
            f"project_plan_json:\n```json\n{project_plan_json}\n```\n\n"
            f"validation_errors_json:\n```json\n{validation_errors_json}\n```\n\n"
            f"Please return a JSON object with a 'suggested_fixes' array, "
            f"where each object specifies a 'task_id' and its 'new_dependencies'."
        )

        try:
            response_text = await self.llm_service.generate_text(
                full_prompt,
                model_type=model_type
            )

            if isinstance(response_text, str):
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx:end_idx + 1]
                else:
                    json_str = response_text
            else:
                json_str = str(response_text)

            try:
                fix_suggestion = json.loads(json_str)
                suggested_fixes = fix_suggestion.get("suggested_fixes", [])
                if not isinstance(suggested_fixes, list):
                    raise ValueError("LLM response 'suggested_fixes' is not a list.")
            except json.JSONDecodeError as e:
                logfire.error(f"Failed to parse JSON response for dependency fixes: {json_str}")
                raise ValueError(f"LLM returned invalid JSON: {e}") from e
            except ValueError as e:
                logfire.error(f"Invalid structure in LLM dependency fix suggestion: {e}")
                raise

            # Apply suggested fixes to a copy of the project plan
            modified_project_plan = project_plan.model_copy(deep=True) # Create a deep copy
            tasks_map = {task.id: task for task in modified_project_plan.tasks}

            for fix in suggested_fixes:
                task_id_str = fix.get("task_id")
                new_dependencies_str = fix.get("new_dependencies")

                if not task_id_str or not isinstance(new_dependencies_str, list):
                    logfire.warning(f"Skipping malformed fix suggestion: {fix}")
                    continue

                try:
                    task_id = UUID(task_id_str)
                    new_dependencies = [UUID(dep_id) for dep_id in new_dependencies_str]
                except ValueError as e:
                    logfire.warning(f"Skipping fix with invalid UUID format: {fix}. Error: {e}")
                    continue

                if task_id in tasks_map:
                    task_to_modify = tasks_map[task_id]
                    # Validate new dependencies exist in the plan
                    valid_new_dependencies = []
                    for dep_id in new_dependencies:
                        if dep_id in tasks_map:
                            valid_new_dependencies.append(dep_id)
                        else:
                            logfire.warning(f"LLM suggested dependency {dep_id} for task {task_id} which does not exist. Skipping.")

                    task_to_modify.dependencies = valid_new_dependencies
                    task_to_modify.updated_at = datetime.now(timezone.utc)
                    logfire.info(f"Applied dependency fix for task {task_id}: New dependencies {task_to_modify.dependencies}")
                else:
                    logfire.warning(f"LLM suggested fix for non-existent task ID: {task_id_str}. Skipping.")

            return modified_project_plan

        except json.JSONDecodeError as e:
            logfire.error(f"JSON parsing error during dependency fix suggestion: {e}")
            raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e
        except ValueError:
            raise # Re-raise ValueError (including those from JSON parsing issues) without wrapping
        except Exception as e:
            logfire.error(f"Error suggesting dependency fixes: {e}")
            raise RuntimeError(f"Dependency fix suggestion failed: {e}") from e
