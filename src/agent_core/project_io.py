import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

import logfire

from ..data_models import ProjectPlan, Task, TaskStatus
from ..config_manager import ConfigManager


class ProjectIO:
    """
    Handles disk I/O for project_plan.json and other project-related files.
    """
    
    def __init__(self, workspace_path: str, config_manager: ConfigManager):
        """
        Initialize ProjectIO.
        
        Args:
            workspace_path: Path to the workspace directory
            config_manager: ConfigManager instance
        """
        self.workspace_path = Path(workspace_path).resolve()
        self.config_manager = config_manager
        
        self.project_plan_file_path = self.workspace_path / self.config_manager.config.project_plan_file
        self.tasks_dir_path = self.workspace_path / self.config_manager.config.tasks_dir
        
        self._initialize_project_structure()
        
        self._project_plan: Optional[ProjectPlan] = self._load_project_plan()
    
    def _initialize_project_structure(self) -> None:
        """
        Ensures the workspace directory and required subdirectories exist.
        Creates default ProjectPlan if none exists.
        Idempotent: does not overwrite existing data.
        """
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self.tasks_dir_path.mkdir(parents=True, exist_ok=True)
        
        if not self._has_project_plan():
            default_plan = ProjectPlan(
                project_title="New Project",
                overall_goal="No project goal defined yet.",
                tasks=[]
            )
            self._save_project_plan_to_json(default_plan)
    
    def _has_project_plan(self) -> bool:
        """Check if project plan JSON file exists."""
        return self.project_plan_file_path.exists()
    
    def _load_project_plan(self) -> Optional[ProjectPlan]:
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
    
    def _save_project_plan_to_json(self, plan: ProjectPlan) -> None:
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
    
    def initialize_project(self, project_name: Optional[str] = None) -> None:
        """
        Initialize project structure and configuration.
        
        Args:
            project_name: Optional name for the project
        """
        try:
            self.config_manager.config = self.config_manager.load_or_initialize_config()
            self._initialize_project_structure()
            self._project_plan = self._load_project_plan()
            
            if project_name and self._project_plan:
                self._project_plan.project_title = project_name
                self._save_project_plan_to_json(self._project_plan)
                logfire.info(f"Project initialized with name: {project_name}")
            else:
                logfire.info("Project structure initialized successfully")
                
        except Exception as e:
            logfire.error(f"Error initializing project: {e}")
            raise
    
    def get_current_project_plan(self) -> Optional[ProjectPlan]:
        """
        Get the current project plan.
        
        Returns:
            Current ProjectPlan or None
        """
        return self._project_plan
    
    def set_project_plan(self, project_plan: ProjectPlan) -> None:
        """
        Set and save the project plan.
        
        Args:
            project_plan: ProjectPlan to set
        """
        self._project_plan = project_plan
        self._save_project_plan_to_json(self._project_plan)
    
    def reload_project_plan(self) -> Optional[ProjectPlan]:
        """
        Reload project plan from storage.
        
        Returns:
            Reloaded ProjectPlan or None
        """
        self._project_plan = self._load_project_plan()
        return self._project_plan
    
    def save_project_plan(self) -> None:
        """Save the current project plan to storage."""
        if self._project_plan:
            self._save_project_plan_to_json(self._project_plan)