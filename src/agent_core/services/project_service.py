import logfire
import json
import os
from pathlib import Path
from typing import Optional, Union, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone

from src.data_models import ProjectPlan, Task, TaskStatus, TaskPriority, AppConfig, ModelConfig
from src.config_manager import ConfigManager
from .llm_service import LLMService
from .config_service import ConfigService


class ProjectService:
    """
    Manages the ProjectPlan lifecycle, including loading, saving, and AI-driven planning.
    Encapsulates ProjectIO and coordinates with LLMService for plan generation.
    """

    def __init__(self, workspace_dir: str, config_service: ConfigService, llm_service: LLMService):
        """
        Initialize ProjectService.

        Args:
            workspace_dir: The root directory of the project workspace.
            config_service: ConfigService instance for accessing configuration.
            llm_service: LLMService instance for AI-driven plan generation.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.config_service = config_service
        self.llm_service = llm_service
        
        self.project_plan_file_path = self.workspace_dir / self.config_service.get_app_config().project_plan_file
        self.tasks_dir_path = self.workspace_dir / self.config_service.get_app_config().tasks_dir
        
        self._project_plan: Optional[ProjectPlan] = None
        logfire.info(f"ProjectService initialized for workspace: {self.workspace_dir}")

    async def _initialize_project_structure(self) -> None:
        """
        Ensures the workspace directory and required subdirectories exist.
        Creates default ProjectPlan if none exists.
        Idempotent: does not overwrite existing data.
        """
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_dir_path.mkdir(parents=True, exist_ok=True)
        
        if not self._has_project_plan():
            default_plan = ProjectPlan(
                project_title="New Project",
                overall_goal="No project goal defined yet.",
                tasks=[]
            )
            await self._save_project_plan_to_json(default_plan)
    
    def _has_project_plan(self) -> bool:
        """Check if project plan JSON file exists."""
        return self.project_plan_file_path.exists()
    
    async def _load_project_plan(self) -> Optional[ProjectPlan]:
        """
        Load existing project plan from JSON file or create a default one.
        
        Returns:
            ProjectPlan object
        """
        if self.project_plan_file_path.exists():
            try:
                with open(self.project_plan_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    plan = ProjectPlan.model_validate(data)
                    logfire.info(f"Loaded existing project plan: {plan.project_title}")
                    return plan
            except (json.JSONDecodeError, Exception) as e:
                logfire.error(f"Error loading project plan from {self.project_plan_file_path}: {e}")
 
        default_plan = ProjectPlan(
            project_title="New Project",
            overall_goal="No project goal defined yet.",
            tasks=[]
        )
        logfire.info("Initialized a new empty project plan.")
        return default_plan
    
    async def _save_project_plan_to_json(self, plan: ProjectPlan) -> None:
        """
        Save project plan to JSON file.
        
        Args:
            plan: ProjectPlan object to save
        """
        try:
            with open(self.project_plan_file_path, 'w', encoding='utf-8') as f:
                f.write(plan.model_dump_json(indent=2, exclude_none=True))
            logfire.info(f"Project plan '{plan.project_title}' (ID: {plan.id}) saved to {self.project_plan_file_path}")
        except Exception as e:
            logfire.error(f"Error saving project plan to {self.project_plan_file_path}: {e}")
            raise

    async def initialize_project_plan(self) -> None:
        """
        Initializes an empty project_plan.json if it doesn't exist.
        Loads the plan into memory.
        """
        await self._initialize_project_structure()
        self._project_plan = await self._load_project_plan()
        logfire.info("Project plan initialized and loaded.")

    async def get_project_plan(self) -> ProjectPlan:
        """
        Loads and returns the current project plan.
        If not already loaded, it will load it from disk.
        """
        if self._project_plan is None:
            self._project_plan = await self._load_project_plan()
        if self._project_plan is None:
            logfire.warn("Project plan not found, creating a default empty plan.")
            default_plan = ProjectPlan(
                project_title="New Project",
                overall_goal="To be defined by the user.",
                tasks=[]
            )
            await self._save_project_plan_to_json(default_plan)
            self._project_plan = default_plan
        return self._project_plan

    async def save_project_plan(self, project_plan: ProjectPlan) -> None:
        """Saves the current project plan to project_plan.json."""
        self._project_plan = project_plan
        await self._save_project_plan_to_json(project_plan)
        logfire.info(f"Project plan '{project_plan.project_title}' saved.")

    async def parse_prd_to_project_plan(self, prd_content: str, project_title: Optional[str] = "New Project", num_tasks: Optional[int] = None, use_research: bool = False) -> Optional[ProjectPlan]:
        """
        Parses a PRD content and generates a project plan using LLMService.
        """
        logfire.info("Parsing PRD content and generating project plan...")
        try:
            project_plan = await self.llm_service.generate_plan(
                text_content=prd_content,
                project_goal=project_title, # Use project_title as initial goal for PRD parsing
                num_tasks=num_tasks,
                model_type="research" if use_research else "main"
            )

            if project_plan:
                if project_title and project_title != "New Project":
                    project_plan.project_title = project_title
                elif not project_plan.project_title:
                    project_plan.project_title = project_title # Fallback to default
                if not project_plan.overall_goal:
                    project_plan.overall_goal = "Project plan generated from PRD."

                await self.save_project_plan(project_plan)
                logfire.info(f"Successfully generated and saved project plan from PRD: {project_plan.project_title}")
                return project_plan
            else:
                logfire.warning("Failed to generate project plan from PRD content.")
                return None
        except Exception as e:
            logfire.error(f"Error parsing PRD to project plan: {e}", exc_info=True)
            raise

    async def plan_project_from_goal(self, project_goal: str, project_title: Optional[str] = "New Project", num_tasks: Optional[int] = None, use_research: bool = False) -> Optional[ProjectPlan]:
        """
        Generates a project plan based on a high-level goal using LLMService.
        """
        logfire.info(f"Planning project based on goal: '{project_goal}'...")
        try:
            project_plan = await self.llm_service.generate_plan(
                project_goal=project_goal,
                num_tasks=num_tasks,
                model_type="research" if use_research else "main"
            )

            if project_plan:
                if project_title and project_title != "New Project":
                    project_plan.project_title = project_title
                elif not project_plan.project_title:
                    project_plan.project_title = project_title
                if not project_plan.overall_goal:
                    project_plan.overall_goal = project_goal

                if not project_plan.tasks:
                    logfire.warn(f"LLM generated an empty task list for goal: '{project_goal}'. Attempting to create a default task.")
                    default_task = Task(
                        id=uuid4(),
                        title=project_plan.project_title if project_plan.project_title != "New Project" else project_goal,
                        description=project_goal,
                        status=TaskStatus.PENDING,
                        priority=TaskPriority.MEDIUM,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                        parent=[],
                        children=[],
                    )
                    project_plan.tasks.append(default_task)
                    logfire.info(f"Added a default task based on the project goal: '{default_task.title}'")

                await self.save_project_plan(project_plan)
                logfire.info(f"Successfully generated and saved project plan: {project_plan.project_title}")
                return project_plan
            else:
                logfire.warning("Failed to generate project plan from high-level goal.")
                return None
        except Exception as e:
            logfire.error(f"Error planning project: {e}", exc_info=True)
            raise 

    async def generate_project_structure_scaffold(self, project_plan: ProjectPlan, use_research: bool = False) -> Optional[Dict[str, Any]]:
        """
        Generates a project structure based on the project plan.
        This method is a placeholder and would typically involve a specific LLM call
        to generate file/directory structures.
        """
        logfire.info("Generating project structure scaffold...")
        # This would involve a specific LLM call to generate file/directory structures.
        # For now, it's a placeholder.
        # Example: return await self.llm_service.generate_project_structure(project_plan, use_research)
        logfire.warning("Project structure generation is not yet fully implemented.")
        return {"message": "Project structure generation not implemented yet."}