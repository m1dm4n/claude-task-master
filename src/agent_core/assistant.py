import json
import shutil
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import ValidationError
from fastmcp import FastMCP

from ..data_models import ProjectPlan, Task, TaskStatus, ToolCode, ToolOutput, Tool, ToolType
from ..config_manager import ConfigManager
from .llm_config import LLMConfigManager
from .llm_provider import LLMProvider
from ..data_models import AgentState
from .llm_generator import LLMGenerator
from .plan_builder import PlanBuilder
from .project_io import ProjectIO
from .task_operations import TaskOperations
from .dependency_logic import DependencyManager


logger = logging.getLogger(__name__)


class DevTaskAIAssistant:
    """
    The main AI assistant for managing development tasks.
    Central orchestrator, delegates to handlers/services, manages ProjectPlan.
    """

    def __init__(self, workspace_dir: str):
        self.logger = logger
        self.workspace_dir = Path(workspace_dir)
        self.project_plan_path = self.workspace_dir / "project_plan.json"
        self.logger.info(f"DevTaskAIAssistant initialized with workspace: {self.workspace_dir}")
        self.logger.info(f"Project plan path: {self.project_plan_path}")

        self.config_manager = ConfigManager(str(self.workspace_dir))
        self.llm_config_manager = LLMConfigManager(self.config_manager)
        self.llm_provider = LLMProvider(self.config_manager)
        self.llm_generator = LLMGenerator(self.llm_provider)
        self.project_io = ProjectIO(str(self.workspace_dir), self.config_manager)
        self.plan_builder = PlanBuilder(self.llm_generator, self.project_io)
        self.dependency_manager = DependencyManager(self.project_io)
        self.task_operations = TaskOperations(self.project_io, self.llm_generator, self.dependency_manager)
        self.mcp_server: Optional[FastMCP] = None

        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        if not self.project_plan_path.exists():
            self._initialize_project_plan()

    def _initialize_project_plan(self):
        """Initializes an empty project_plan.json if it doesn't exist."""
        empty_plan = ProjectPlan(
            project_title="New Project",
            overall_goal="To be defined by the user.",
            tasks=[]
        )
        self.project_io.save_project_plan(empty_plan)
        self.logger.info(f"Initialized new project plan at {self.project_plan_path}")

    def get_current_project_plan(self) -> ProjectPlan:
        """Loads and returns the current project plan."""
        return self.project_io.get_current_project_plan()

    def save_project_plan(self, project_plan: ProjectPlan):
        """Saves the current project plan to project_plan.json."""
        self.project_io.save_project_plan(project_plan)

    def get_tasks_summary(self, project_plan: ProjectPlan) -> str:
        """Generates a summary of existing tasks for LLM context."""
        return self.task_operations.get_tasks_summary(project_plan)

    def get_item_by_id(self, item_id: UUID, project_plan: Optional[ProjectPlan] = None) -> Optional[Task]:
        """Retrieves a task or subtask by its ID."""
        return self.task_operations.get_item_by_id(item_id, project_plan)

    def get_all_tasks(self) -> List[Task]:
        """Returns all top-level tasks."""
        return self.task_operations.get_all_tasks()

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Returns tasks filtered by status."""
        return self.task_operations.get_tasks_by_status(status)

    def update_item_status(self, item_ids: List[UUID], new_status: TaskStatus) -> Dict[UUID, bool]:
        """Updates the status of tasks or subtasks."""
        return self.task_operations.update_item_status(item_ids, new_status)

    def update_task(self, updated_task: Task):
        """Updates an existing task in the project plan."""
        self.task_operations.update_task_in_plan(updated_task.id, updated_task)

    async def refine_task_or_subtask(self, item_id: UUID, refinement_instruction: str, use_research: bool = False) -> Optional[Task]:
        """Refines an existing task or subtask using AI assistance."""
        item = self.get_item_by_id(item_id)
        if not item:
            self.logger.error(f"Item with ID '{item_id}' not found for refinement.")
            return None

        refined_item = await self.llm_generator.refine_item_details(
            item_current_details=item,
            refinement_instruction=refinement_instruction,
            model_type="research" if use_research else "main"
        )
        if refined_item:
            self.update_task(refined_item)
            self.logger.info(f"Successfully refined item: {refined_item.title} (ID: {refined_item.id})")
        else:
            self.logger.warning("LLM did not refine the item.")
        return refined_item

    async def add_new_task(self, description: str, use_research: bool = False,
                           dependencies_str: Optional[List[str]] = None,
                           priority_str: Optional[str] = None,
                           parent_id_str: Optional[str] = None) -> Optional[Task]:
        """Adds a new task to the project plan based on a description, using AI to generate details."""
        try:
            new_task = await self.llm_generator.generate_single_task(
                description_prompt=description,
                project_context=self.get_tasks_summary(self.get_current_project_plan()),
                model_type="research" if use_research else "main"
            )

            if not new_task:
                self.logger.warning("LLM did not generate new task details.")
                return None

            if parent_id_str:
                parent_task = self.get_item_by_id(UUID(parent_id_str))
                if parent_task:
                    new_task.parent_id = UUID(parent_id_str)
                    parent_task.subtasks.append(new_task)
                    self.update_task(parent_task)
                else:
                    self.logger.error(f"Parent task with ID '{parent_id_str}' not found for subtask creation.")
                    raise ValueError(f"Parent task with ID '{parent_id_str}' not found.")
            else:
                current_plan = self.get_current_project_plan()
                current_plan.tasks.append(new_task)
                self.save_project_plan(current_plan)

            self.logger.info(f"Successfully added new task: {new_task.title} (ID: {new_task.id})")
            if new_task.subtasks:
                self.logger.info(f"Generated {len(new_task.subtasks)} initial subtasks:")
                for i, subtask in enumerate(new_task.subtasks, 1):
                    self.logger.info(f"  {i}. {subtask.title} (ID: {subtask.id})")
            return new_task
        except Exception as e:
            self.logger.error(f"Error adding new task: {e}", exc_info=True)
            return None

    async def parse_prd_to_project_plan(self, prd_content: str, use_research: bool = False) -> Optional[ProjectPlan]:
        """Parses a PRD and generates a project plan."""
        self.logger.info("Parsing PRD and generating project plan...")
        try:
            project_plan = await self.plan_builder.parse_prd_to_project_plan(prd_content, use_research)
            if project_plan:
                self.save_project_plan(project_plan)
                self.logger.info(f"Successfully generated and saved project plan: {project_plan.project_title}")
                return project_plan
            else:
                self.logger.warning("Failed to generate project plan from PRD.")
                return None
        except Exception as e:
            self.logger.error(f"Error parsing PRD to project plan: {e}", exc_info=True)
            return None

    async def plan_project(self, project_goal: str, project_title: Optional[str] = "New Project", num_tasks: Optional[int] = None, use_research: bool = False) -> Optional[ProjectPlan]:
        """Generates a project plan based on a high-level goal using AI assistance."""
        self.logger.info(f"Planning project based on goal: '{project_goal}'...")
        try:
            project_plan = await self.plan_builder.plan_project(
                project_goal=project_goal,
                project_title=project_title,
                num_tasks=num_tasks,
                use_research=use_research
            )
            if project_plan:
                self.save_project_plan(project_plan)
                self.logger.info(f"Successfully generated and saved project plan: {project_plan.project_title}")
                return project_plan
            else:
                self.logger.warning("Failed to generate project plan from high-level goal.")
                return None
        except Exception as e:
            self.logger.error(f"Error planning project: {e}", exc_info=True)
            return None

    async def plan_project_from_prd_file(self, prd_file_path: str, project_title: Optional[str] = "New Project", num_tasks: Optional[int] = None, use_research: bool = False) -> Optional[ProjectPlan]:
        """Reads a PRD file and generates a project plan from its content."""
        self.logger.info(f"Planning project from PRD file: {prd_file_path}...")
        try:
            with open(prd_file_path, 'r', encoding='utf-8') as f:
                prd_content = f.read()

            project_plan = await self.plan_builder.plan_project_from_prd_file(
                prd_file_path=prd_file_path,
                project_title=project_title,
                num_tasks=num_tasks,
                use_research=use_research
            )
            if project_plan:
                self.logger.info(f"Successfully generated project plan from PRD file: {prd_file_path}")
                return project_plan
            else:
                self.logger.warning(f"Failed to generate project plan from PRD file: {prd_file_path}.")
                return None
        except FileNotFoundError:
            self.logger.error(f"PRD file not found at: {prd_file_path}")
            return None
        except Exception as e:
            self.logger.error(f"Error reading or processing PRD file {prd_file_path}: {e}", exc_info=True)
            return None

    async def generate_project_structure(self, project_plan: ProjectPlan, use_research: bool = False) -> Optional[Dict[str, Any]]:
        """Generates a project structure based on the project plan."""
        self.logger.info("Generating project structure...")
        try:
            structure = await self.llm_generator.generate_project_structure(project_plan, use_research)
            if structure:
                self.logger.info("Successfully generated project structure.")
                return structure
            else:
                self.logger.warning("Failed to generate project structure.")
                return None
        except Exception as e:
            self.logger.error(f"Error generating project structure: {e}", exc_info=True)
            return None

    async def generate_code_for_task(self, task_id: UUID, use_research: bool = False) -> Optional[str]:
        """Generates code for a specific task."""
        self.logger.info(f"Generating code for task {task_id}...")
        try:
            task = self.get_item_by_id(task_id)
            if not task:
                self.logger.error(f"Task with ID {task_id} not found.")
                return None

            code = await self.llm_generator.generate_code(task, use_research)
            if code:
                self.logger.info(f"Successfully generated code for task {task.title}.")
                return code
            else:
                self.logger.warning(f"Failed to generate code for task {task.title}.")
                return None
        except Exception as e:
            self.logger.error(f"Error generating code for task {task_id}: {e}", exc_info=True)
            return None

    async def expand_task_with_subtasks(self, task_id: UUID, num_subtasks: Optional[int] = None, prompt_override: Optional[str] = None, use_research: bool = False) -> Optional[Task]:
        """Expands a task by generating subtasks."""
        self.logger.info(f"Expanding task {task_id} with subtasks...")
        try:
            task = self.get_item_by_id(task_id)
            if not task:
                self.logger.error(f"Task with ID {task_id} not found.")
                return None

            updated_task = await self.task_operations.expand_task(task, num_subtasks, prompt_override, use_research)
            if updated_task:
                self.save_project_plan(self.get_current_project_plan())
                self.logger.info(f"Successfully expanded task: {updated_task.title}.")
                return updated_task
            else:
                self.logger.warning(f"Failed to expand task: {task.title}.")
                return None
        except Exception as e:
            self.logger.error(f"Error expanding task {task_id}: {e}", exc_info=True)
            return None

    def clear_subtasks_for_task(self, task_id: UUID) -> bool:
        """Clears all subtasks for a given task."""
        return self.task_operations.clear_subtasks_for_task(task_id)

    def clear_subtasks_for_all_tasks(self) -> int:
        """Clears all subtasks from all tasks in the project plan."""
        return self.task_operations.clear_subtasks_for_all_tasks()

    async def expand_all_pending_tasks(self, num_subtasks_per_task: Optional[int] = None, use_research: bool = False) -> int:
        """Expands all pending tasks by generating subtasks."""
        self.logger.info("Expanding all pending tasks...")
        project_plan = self.get_current_project_plan()
        expanded_count = 0

        tasks_to_expand = [task for task in project_plan.tasks if task.status == TaskStatus.PENDING and not task.subtasks]

        for task in tasks_to_expand:
            try:
                updated_task = await self.task_operations.expand_task(task, num_subtasks_per_task, None, use_research)
                if updated_task:
                    for i, p_task in enumerate(project_plan.tasks):
                        if p_task.id == updated_task.id:
                            project_plan.tasks[i] = updated_task
                            break
                    self.logger.info(f"Successfully expanded pending task: {updated_task.title}.")
                    expanded_count += 1
                else:
                    self.logger.warning(f"Failed to expand pending task: {task.title}.")
            except Exception as e:
                self.logger.error(f"Error expanding pending task {task.title}: {e}", exc_info=True)
        self.save_project_plan(project_plan)
        self.logger.info(f"Finished expanding all pending tasks. Expanded {expanded_count} tasks.")
        return expanded_count

    def get_next_task(self) -> Optional[Task]:
        """Retrieves the next pending task based on dependencies and priority."""
        self.logger.info("Attempting to get the next task...")
        next_task = self.dependency_manager.get_next_actionable_task()
        if next_task:
            self.logger.info(f"Next task identified: {next_task.title} (ID: {next_task.id})")
        else:
            self.logger.info("No pending tasks found or all pending tasks have unmet dependencies.")
        return next_task

    def move_task(self, task_id: UUID, new_parent_id: Optional[UUID] = None) -> bool:
        """Moves a task to a new parent or makes it a top-level task."""
        return self.task_operations.move_task(task_id, new_parent_id)

    def remove_subtask(self, subtask_id: UUID) -> bool:
        """Removes a subtask from its parent task."""
        return self.task_operations.remove_subtask(subtask_id)

    def add_dependency(self, task_id: UUID, dependency_ids: List[UUID]) -> bool:
        """Adds dependencies to a task."""
        return self.dependency_manager.add_dependencies(task_id, dependency_ids)

    def remove_dependency(self, task_id: UUID, dependency_ids: List[UUID]) -> bool:
        """Removes dependencies from a task."""
        return self.dependency_manager.remove_dependencies(task_id, dependency_ids)

    def validate_dependencies(self) -> Tuple[bool, Dict[str, List[str]]]:
        """Validates all dependencies in the current project plan."""
        errors = self.dependency_manager.validate_all_dependencies()
        is_valid = not bool(errors["circular"] or errors["missing_ids"])
        return is_valid, errors

    async def fix_dependencies(self, remove_invalid: bool = False, remove_circular: bool = False) -> List[str]:
        """Fixes dependency issues in the project plan using AI assistance."""
        self.logger.info("Attempting to fix dependencies...")
        project_plan = self.get_current_project_plan()
        is_valid, errors = self.validate_dependencies()
        
        if is_valid:
            self.logger.info("No dependency errors found. No fixes needed.")
            return []

        # Filter errors based on flags
        filtered_errors = {}
        if remove_invalid and errors.get("missing_ids"):
            filtered_errors["missing_ids"] = errors["missing_ids"]
        if remove_circular and errors.get("circular"):
            filtered_errors["circular"] = errors["circular"]

        if not filtered_errors:
            self.logger.info("No applicable dependency errors to fix based on provided flags.")
            return []

        try:
            updated_plan = await self.llm_generator.suggest_dependency_fixes(
                project_plan=project_plan,
                validation_errors=filtered_errors,
                model_type="main" # Or "research" if appropriate
            )
            if updated_plan:
                self.save_project_plan(updated_plan)
                self.logger.info("Successfully applied suggested dependency fixes.")
                # Re-validate after applying fixes to report remaining issues
                _, remaining_errors = self.validate_dependencies()
                if remaining_errors["circular"] or remaining_errors["missing_ids"]:
                    self.logger.warning(f"Some dependency errors remain after fixing: {remaining_errors}")
                    return [f"Fixed some dependencies. Remaining errors: {remaining_errors}"]
                else:
                    return ["All identified dependency errors have been fixed."]
            else:
                self.logger.warning("LLM did not provide dependency fix suggestions.")
                return ["LLM did not provide dependency fix suggestions."]
        except Exception as e:
            self.logger.error(f"Error fixing dependencies: {e}", exc_info=True)
            return [f"Error fixing dependencies: {e}"]

    async def close(self):
        """Closes any open resources, like LLM service connections."""
        self.logger.info("Closing DevTaskAIAssistant resources...")
        if self.llm_provider:
            await self.llm_provider.close()
        if self.mcp_server:
            await self.mcp_server.stop()
        self.logger.info("DevTaskAIAssistant resources closed.")

    def get_agent_state(self) -> AgentState:
        """Returns the current state of the agent."""
        return AgentState(
            current_project_plan=self.get_current_project_plan(),
            config=self.config_manager.config
        )

    def register_mcp_tool(self, tool: Tool):
        """Registers a tool with the MCP server."""
        if self.mcp_server:
            # MCP server expects a dict, convert Pydantic model to dict
            tool_dict = tool.model_dump(mode='json')
            self.mcp_server.register_tool(tool_dict)
            self.logger.info(f"Registered MCP tool: {tool.name}")
        else:
            self.logger.warning("MCP server not running. Cannot register tool.")

    def register_mcp_resource(self, uri: str, content: Any, content_type: str):
        """Registers a resource with the MCP server."""
        if self.mcp_server:
            self.mcp_server.register_resource(uri, content, content_type)
            self.logger.info(f"Registered MCP resource: {uri}")
        else:
            self.logger.warning("MCP server not running. Cannot register resource.")

    async def start_mcp_server(self, host: str = "127.0.0.1", port: int = 8000):
        """Starts the FastMCP server."""
        if self.mcp_server:
            self.logger.info("MCP server already running.")
            return

        self.mcp_server = FastMCP(
            server_name="devtask-ai-assistant",
            host=host,
            port=port,
            description="DevTask AI Assistant MCP Server"
        )
        try:
            await self.mcp_server.start()
            self.logger.info(f"MCP server started on {host}:{port}")
        except Exception as e:
            self.logger.error(f"Failed to start MCP server: {e}")
            self.mcp_server = None
            raise

    async def use_mcp_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> ToolOutput:
        """Executes a tool on a registered MCP server."""
        if not self.mcp_server:
            raise RuntimeError("MCP server is not running.")
        try:
            result = await self.mcp_server.use_tool(server_name, tool_name, arguments)
            return ToolOutput(stdout=result.get('stdout'), stderr=result.get('stderr'), exit_code=result.get('exit_code', 0), result=result.get('result'), error=result.get('error'))
        except Exception as e:
            self.logger.error(f"Error using MCP tool '{tool_name}' on server '{server_name}': {e}")
            return ToolOutput(exit_code=1, stderr=str(e), error=str(e))

    async def access_mcp_resource(self, server_name: str, uri: str) -> Any:
        """Accesses a resource on a registered MCP server."""
        if not self.mcp_server:
            raise RuntimeError("MCP server is not running.")
        try:
            return await self.mcp_server.access_resource(server_name, uri)
        except Exception as e:
            self.logger.error(f"Error accessing MCP resource '{uri}' on server '{server_name}': {e}")
            raise