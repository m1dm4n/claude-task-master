import json
import shutil
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import ValidationError
from fastmcp import FastMCP

from ..data_models import ProjectPlan, Task, TaskStatus, ToolCode, ToolOutput, Tool, ToolType, TaskPriority
from ..data_models import AgentState
from ..utils.async_utils import run_async_tasks_sync

# Import new services
from .services.config_service import ConfigService
from .services.llm_service import LLMService
from .services.project_service import ProjectService
from .services.task_service import TaskService
from .mcp_handler import MCPHandler


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
        self.logger.info(
            f"DevTaskAIAssistant initialized with workspace: {self.workspace_dir}")
        # Initialize new services
        self.config_service = ConfigService(str(self.workspace_dir))
        self.llm_service = LLMService(self.config_service)
        self.project_service = ProjectService(
            str(self.workspace_dir), self.config_service, self.llm_service)
        self.task_service = TaskService(self.project_service, self.llm_service)
        self.mcp_handler = MCPHandler()

        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        """Initializes the project plan."""
        try:
            run_async_tasks_sync(
                self.project_service.initialize_project_plan())
        except Exception as e:
            self.logger.error(
                f"Error initializing project plan: {e}", exc_info=True)

    async def get_current_project_plan(self) -> ProjectPlan:
        """Loads and returns the current project plan."""
        return await self.project_service.get_project_plan()

    async def save_project_plan(self, project_plan: ProjectPlan):
        """Saves the current project plan to project_plan.json."""
        await self.project_service.save_project_plan(project_plan)

    async def get_tasks_summary(self, project_plan: ProjectPlan) -> str:
        """Generates a summary of existing tasks for LLM context."""
        return await self.task_service.get_tasks_summary_for_llm()

    async def get_item_by_id(self, item_id: UUID, project_plan: Optional[ProjectPlan] = None) -> Optional[Task]:
        """Retrieves a task or subtask by its ID."""
        return await self.task_service.get_task_by_id(item_id)

    async def get_all_tasks(self) -> List[Task]:
        """Returns all top-level tasks."""
        return await self.task_service.get_all_tasks()

    async def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Returns tasks filtered by status."""
        return await self.task_service.get_tasks_by_status(status)

    async def update_item_status(self, item_ids: List[UUID], new_status: TaskStatus) -> Dict[UUID, bool]:
        """Updates the status of tasks or subtasks."""
        return await self.task_service.update_task_status(item_ids, new_status)

    async def update_task(self, updated_task: Task):
        """Updates an existing task in the project plan."""
        await self.task_service.update_task(updated_task)

    async def refine_task_or_subtask(self, item_id: UUID, refinement_instruction: str, use_research: bool = False) -> Optional[Task]:
        """Refines an existing task or subtask using AI assistance."""
        item = await self.task_service.get_task_by_id(item_id)
        if not item:
            self.logger.error(
                f"Item with ID '{item_id}' not found for refinement.")
            return None

        refined_item = await self.llm_service.refine_item(
            item_current_details=item,
            refinement_instruction=refinement_instruction,
            model_type="research" if use_research else "main"
        )
        if refined_item:
            await self.task_service.update_task(refined_item)
            self.logger.info(
                f"Successfully refined item: {refined_item.title} (ID: {refined_item.id})")
        else:
            self.logger.warning("LLM did not refine the item.")
        return refined_item

    async def add_new_task(self, description: str, use_research: bool = False,
                           dependencies_str: Optional[List[str]] = None,
                           priority_str: Optional[str] = None,
                           parent_id_str: Optional[str] = None) -> Optional[Task]:
        """Adds a new task to the project plan based on a description, using AI to generate details."""
        return await self.task_service.add_task(description, use_research, dependencies_str, priority_str, parent_id_str)

    async def parse_prd_to_project_plan(self, prd_content: str, use_research: bool = False) -> Optional[ProjectPlan]:
        """Parses a PRD and generates a project plan."""
        self.logger.info("Parsing PRD and generating project plan...")
        try:
            project_plan = await self.project_service.parse_prd_to_project_plan(prd_content, use_research=use_research)
            if project_plan:
                self.logger.info(
                    f"Successfully generated and saved project plan: {project_plan.project_title}")
                return project_plan
            else:
                self.logger.warning(
                    "Failed to generate project plan from PRD.")
                return None
        except Exception as e:
            self.logger.error(
                f"Error parsing PRD to project plan: {e}", exc_info=True)
            return None

    async def plan_project(self, project_goal: str, project_title: Optional[str] = "New Project", num_tasks: Optional[int] = None, use_research: bool = False) -> Optional[ProjectPlan]:
        """Generates a project plan based on a high-level goal using AI assistance."""
        self.logger.info(
            f"Planning project based on goal: '{project_goal}'...")
        try:
            project_plan = await self.project_service.plan_project_from_goal(
                project_goal=project_goal,
                project_title=project_title,
                num_tasks=num_tasks,
                use_research=use_research
            )
            if project_plan:
                self.logger.info(
                    f"Successfully generated and saved project plan: {project_plan.project_title}")
                return project_plan
            else:
                self.logger.warning(
                    "Failed to generate project plan from high-level goal.")
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

            project_plan = await self.project_service.parse_prd_to_project_plan(
                prd_content=prd_content,
                project_title=project_title,
                num_tasks=num_tasks,
                use_research=use_research
            )
            if project_plan:
                self.logger.info(
                    f"Successfully generated project plan from PRD file: {prd_file_path}")
                return project_plan
            else:
                self.logger.warning(
                    f"Failed to generate project plan from PRD file: {prd_file_path}.")
                return None
        except FileNotFoundError:
            self.logger.error(f"PRD file not found at: {prd_file_path}")
            return None
        except Exception as e:
            self.logger.error(
                f"Error reading or processing PRD file {prd_file_path}: {e}", exc_info=True)
            return None

    async def generate_project_structure(self, project_plan: ProjectPlan, use_research: bool = False) -> Optional[Dict[str, Any]]:
        """Generates a project structure based on the project plan."""
        return await self.project_service.generate_project_structure_scaffold(project_plan, use_research)

    async def generate_code_for_task(self, task: Task, use_research: bool = False) -> Optional[str]:
        """Generates code for a specific task."""
        self.logger.info(
            f"Generating code for task '{task.title}' (ID: {task.id})...")
        try:
            task = await self.task_service.get_task_by_id(task.id)
            if not task:
                self.logger.error(f"Task with ID {task.id} not found.")
                return None

            code = await self.llm_service.generate_code_for_task(task, use_research)
            if code:
                self.logger.info(
                    f"Successfully generated code for task {task.title}.")
                return code
            else:
                self.logger.warning(
                    f"Failed to generate code for task {task.title}.")
                return None
        except Exception as e:
            self.logger.error(
                f"Error generating code for task {task.id}: {e}", exc_info=True)
            return None

    async def expand_task_with_subtasks(self, task_id: UUID, num_subtasks: Optional[int] = None, prompt_override: Optional[str] = None, use_research: bool = False) -> Optional[Task]:
        """Expands a task by generating subtasks."""
        return await self.task_service.expand_task_with_subtasks(task_id, num_subtasks, prompt_override, use_research)

    async def clear_subtasks_for_task(self, task_id: UUID) -> bool:
        """Clears all subtasks for a given task."""
        return await self.task_service.clear_subtasks_for_task(task_id)

    async def clear_subtasks_for_all_tasks(self) -> int:
        """Clears all subtasks from all tasks in the project plan."""
        return await self.task_service.clear_subtasks_for_all_tasks()

    async def expand_all_pending_tasks(self, num_subtasks_per_task: Optional[int] = None, use_research: bool = False) -> int:
        """Expands all pending tasks by generating subtasks."""
        self.logger.info("Expanding all pending tasks...")
        project_plan = await self.project_service.get_project_plan()
        expanded_count = 0

        tasks_to_expand = [task for task in project_plan.tasks if task.status ==
                           TaskStatus.PENDING and not task.subtasks]

        for task in tasks_to_expand:
            try:
                updated_task = await self.task_service.expand_task_with_subtasks(task.id, num_subtasks_per_task, None, use_research)
                if updated_task:
                    # The task_service.expand_task_with_subtasks already saves the plan,
                    # but we need to update the in-memory project_plan for this loop.
                    for i, p_task in enumerate(project_plan.tasks):
                        if p_task.id == updated_task.id:
                            project_plan.tasks[i] = updated_task
                            break
                    self.logger.info(
                        f"Successfully expanded pending task: {updated_task.title}.")
                    expanded_count += 1
                else:
                    self.logger.warning(
                        f"Failed to expand pending task: {task.title}.")
            except Exception as e:
                self.logger.error(
                    f"Error expanding pending task {task.title}: {e}", exc_info=True)
        # No need to save here, as task_service.expand_task_with_subtasks already saves.
        self.logger.info(
            f"Finished expanding all pending tasks. Expanded {expanded_count} tasks.")
        return expanded_count

    async def get_next_task(self) -> Optional[Task]:
        """Retrieves the next pending task based on dependencies and priority."""
        self.logger.info("Attempting to get the next task...")
        next_task = await self.task_service.get_next_actionable_task()
        if next_task:
            self.logger.info(
                f"Next task identified: {next_task.title} (ID: {next_task.id})")
        else:
            self.logger.info(
                "No pending tasks found or all pending tasks have unmet dependencies.")
        return next_task

    async def move_task(self, task_id: UUID, new_parent_id: Optional[UUID] = None) -> bool:
        """Moves a task to a new parent or makes it a top-level task."""
        return await self.task_service.move_task(task_id, new_parent_id)

    async def remove_subtask(self, subtask_id: UUID) -> bool:
        """Removes a subtask from its parent task."""
        return await self.task_service.remove_subtask(subtask_id)

    async def add_dependency(self, task_id: UUID, dependency_ids: List[UUID]) -> bool:
        """Adds dependencies to a task."""
        return await self.task_service.add_dependency(task_id, dependency_ids)

    async def remove_dependency(self, task_id: UUID, dependency_ids: List[UUID]) -> bool:
        """Removes dependencies from a task."""
        return await self.task_service.remove_dependency(task_id, dependency_ids)

    async def validate_dependencies(self) -> Tuple[bool, Dict[str, List[str]]]:
        """Validates all dependencies in the current project plan."""
        return await self.task_service.validate_dependencies()

    async def fix_dependencies(self, remove_invalid: bool = False, remove_circular: bool = False) -> List[str]:
        """Fixes dependency issues in the project plan using AI assistance."""
        return await self.task_service.fix_dependencies_ai(remove_invalid, remove_circular)

    async def close(self):
        """Closes any open resources, like LLM service connections."""
        self.logger.info("Closing DevTaskAIAssistant resources...")
        await self.llm_service.close()
        await self.mcp_handler.stop_mcp_server()
        self.logger.info("DevTaskAIAssistant resources closed.")

    def get_agent_state(self) -> AgentState:
        """Returns the current state of the agent."""
        # This needs to be updated to reflect the new service structure
        # For now, returning a placeholder or simplified state
        current_plan = self.project_service._project_plan  # Access internal loaded plan
        if current_plan is None:
            # If plan isn't loaded yet, try to load it synchronously for state reporting
            # This is a potential blocking call, consider async if this is frequently called
            from ..utils.async_utils import run_async_tasks_sync
            current_plan = run_async_tasks_sync(
                self.project_service.get_project_plan())

        return AgentState(
            current_project_plan=current_plan,
            config=self.config_service.get_app_config()
        )

    def register_mcp_tool(self, tool: Tool):
        """Registers a tool with the MCP server."""
        self.mcp_handler.register_mcp_tool(tool)

    def register_mcp_resource(self, uri: str, content: Any, content_type: str):
        """Registers a resource with the MCP server."""
        self.mcp_handler.register_mcp_resource(uri, content, content_type)

    async def start_mcp_server(self, host: str = "127.0.0.1", port: int = 8000):
        """Starts the FastMCP server."""
        await self.mcp_handler.start_mcp_server(host, port)

    async def use_mcp_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> ToolOutput:
        """Executes a tool on a registered MCP server."""
        return await self.mcp_handler.use_mcp_tool(server_name, tool_name, arguments)

    async def access_mcp_resource(self, server_name: str, uri: str) -> Any:
        """Accesses a resource on a registered MCP server."""
        return await self.mcp_handler.access_mcp_resource(server_name, uri)
