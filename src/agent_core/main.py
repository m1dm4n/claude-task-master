import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Any, Dict, Literal, Union, Tuple
from uuid import UUID, uuid4

import logfire
from dotenv import load_dotenv

from ..data_models import Subtask, Task, ProjectPlan, ModelConfig, TaskStatus
from ..config_manager import ConfigManager
from .llm_services import AgentDependencies
from .project_manager import ProjectManager
from .task_manager import TaskManager
from .llm_manager import LLMManager
from .planning_manager import PlanningManager

load_dotenv() 
logfire.configure(send_to_logfire='if-token-present')

class DevTaskAIAssistant:
    """
    An AI-driven task management assistant.
    Updated for Phase 1 to take workspace_path and initialize components accordingly.
    """
    
    def __init__(self, workspace_path: str = None):
        """
        Initialize DevTaskAIAssistant with workspace path.
        
        Args:
            workspace_path: Path to the workspace directory. Defaults to current working directory.
        """
        if workspace_path is None:
            workspace_path = os.getcwd()
            
        self.workspace_path = Path(workspace_path).resolve()
        
        # Initialize ConfigManager with workspace path
        self.config_manager = ConfigManager(str(self.workspace_path))
        
        # Initialize managers
        self.project_manager = ProjectManager(str(self.workspace_path), self.config_manager)
        self.llm_manager = LLMManager(self.config_manager)
        self.task_manager = TaskManager(self.project_manager)
        self.planning_manager = PlanningManager(self.llm_manager, self.project_manager)

    def initialize_project(self, project_name: Optional[str] = None) -> None:
        """
        Initialize project structure and configuration.
        
        Args:
            project_name: Optional name for the project
        """
        self.project_manager.initialize_project(project_name)

    def get_model_configurations(self) -> Dict[str, Optional[ModelConfig]]:
        """
        Get all model configurations.
        
        Returns:
            Dict mapping model type to ModelConfig
        """
        return self.llm_manager.get_model_configurations()

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
        return self.llm_manager.set_model_configuration(
            model_type, model_name, provider, api_key_str, base_url_str
        )

    async def plan_project(self, project_goal: str, project_title: Optional[str] = "New Project", num_tasks: Optional[int] = None, use_research: bool = False, deps: Optional[AgentDependencies] = None) -> ProjectPlan:
        """
        Generate a project plan from a simple project goal using the LLMService.
        
        Args:
            project_goal: Description of the overall project goal.
            project_title: Optional title for the project.
            num_tasks: Optional. Desired number of main tasks.
            use_research: Whether to use the research model for planning.
            deps: Optional agent dependencies (not directly used by LLMService, but kept for consistency).
            
        Returns:
            Generated ProjectPlan.
        """
        return await self.planning_manager.plan_project(
            project_goal, project_title, num_tasks, use_research, deps
        )

    async def plan_project_from_prd_file(self, prd_file_path: Union[str, Path], project_title: Optional[str] = "New Project", num_tasks: Optional[int] = None, use_research: bool = False, deps: Optional[AgentDependencies] = None) -> ProjectPlan:
        """
        Generates a project plan by parsing a PRD file using the LLMService.

        Args:
            prd_file_path: Path to the PRD file.
            project_title: Optional title for the project. If not provided, derived from PRD or default.
            num_tasks: Optional. Desired number of main tasks.
            use_research: Whether to use the research model for planning.
            deps: Optional agent dependencies (not directly used by LLMService, but kept for consistency).

        Returns:
            Generated ProjectPlan.
        """
        return await self.planning_manager.plan_project_from_prd_file(
            prd_file_path, project_title, num_tasks, use_research, deps
        )

    async def refine_task(self, task_id: UUID, refinement_prompt: str, use_research: bool = False, deps: Optional[AgentDependencies] = None) -> Optional[Task]:
        """
        Refine a specific task using AI assistance.
        
        Args:
            task_id: UUID of the task to refine
            refinement_prompt: Instructions for refining the task
            use_research: Whether to use research model for refinement
            deps: Optional agent dependencies
            
        Returns:
            Refined Task object or None if task not found
        """
        task_to_refine = self.task_manager.get_item_by_id(task_id)
        if task_to_refine is None or not isinstance(task_to_refine, Task):
            logfire.warn(f"Task with ID {task_id} not found in project plan.")
            return None

        refined_task = await self.llm_manager.refine_task(task_to_refine, refinement_prompt, use_research, deps)
        
        if refined_task and self.task_manager.update_task_in_plan(task_id, refined_task):
            return refined_task
        return None

    def get_current_project_plan(self) -> Optional[ProjectPlan]:
        """
        Get the current project plan.
        
        Returns:
            Current ProjectPlan or None
        """
        return self.project_manager.get_current_project_plan()

    def get_all_tasks(self) -> List[Task]:
        """
        Get all main tasks in the project plan.
        
        Returns:
            A list of all Task objects.
        """
        return self.task_manager.get_all_tasks()

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """
        Get main tasks filtered by their status.
        
        Args:
            status: The TaskStatus to filter by.
            
        Returns:
            A list of Task objects matching the given status.
        """
        return self.task_manager.get_tasks_by_status(status)

    def get_item_by_id(self, item_id: UUID) -> Optional[Union[Task, Subtask]]:
        """
        Get a Task or Subtask by its UUID.
        
        Args:
            item_id: The UUID of the item to retrieve.
            
        Returns:
            The found Task or Subtask object, or None if not found.
        """
        return self.task_manager.get_item_by_id(item_id)

    def update_item_status(self, item_ids: List[UUID], new_status: TaskStatus) -> Dict[UUID, bool]:
        """
        Updates the status of specified tasks or subtasks.

        Args:
            item_ids: A list of UUIDs of the tasks or subtasks to update.
            new_status: The new TaskStatus to set for the items.

        Returns:
            A dictionary where keys are the item_id (UUID) and values are booleans
            indicating success (True) or failure (False) of the status update for that item.
        """
        return self.task_manager.update_item_status(item_ids, new_status)

    def get_next_task(self) -> Optional[Task]:
        """
        Identifies the next actionable task based on its status and dependencies.
        A task is actionable if its status is PENDING and all its dependencies are COMPLETED.

        Returns:
            The first actionable Task found, or None if no such task exists.
        """
        return self.task_manager.get_next_task()

    def reload_project_plan(self) -> Optional[ProjectPlan]:
        """
        Reload project plan from storage.
        
        Returns:
            Reloaded ProjectPlan or None
        """
        return self.project_manager.reload_project_plan()

    async def research_query(self, query: str, tools: Optional[List[Any]] = None) -> Any:
        """
        Perform a research query using the research model.
        
        Args:
            query: Research query
            tools: Optional tools to make available
            
        Returns:
            Research results
        """
        return await self.llm_manager.research_query(query, tools)