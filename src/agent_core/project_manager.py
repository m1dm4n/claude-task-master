"""Project data management and persistence for the DevTask AI Assistant."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

import logfire

from ..data_models import ProjectPlan, Task, Subtask, TaskStatus
from ..config_manager import ConfigManager
from ..persistence_manager import PersistenceManager


class ProjectManager:
    """Manages project data, initialization, and persistence."""
    
    def __init__(self, workspace_path: str, config_manager: ConfigManager):
        """
        Initialize ProjectManager.
        
        Args:
            workspace_path: Path to the workspace directory
            config_manager: ConfigManager instance
        """
        self.workspace_path = Path(workspace_path).resolve()
        self.config_manager = config_manager
        
        # Initialize PersistenceManager with workspace path and app config
        self.persistence_manager = PersistenceManager(str(self.workspace_path), self.config_manager.config)
        
        # Ensure project structure (including DB and .tasks dir) is initialized
        self.persistence_manager.initialize_project_structure()
        
        # Load existing project plan (or default if none after initialization)
        self._project_plan: Optional[ProjectPlan] = self._load_project_plan()
    
    def _load_project_plan(self) -> Optional[ProjectPlan]:
        """
        Load existing project plan or create a default one.
        
        Returns:
            ProjectPlan object
        """
        loaded_plan = self.persistence_manager.load_project_plan()
        if loaded_plan:
            logfire.info(f"Loaded existing project plan: {loaded_plan.project_title}")
            return loaded_plan

        # Create default project plan if none exists
        default_plan = ProjectPlan(
            project_title="New Project",
            overall_goal="No project goal defined yet.",
            tasks=[]
        )
        logfire.info("Initialized a new empty project plan.")
        return default_plan
    
    def initialize_project(self, project_name: Optional[str] = None) -> None:
        """
        Initialize project structure and configuration.
        
        Args:
            project_name: Optional name for the project
        """
        try:
            # Ensure configuration is loaded/initialized
            self.config_manager.config = self.config_manager.load_or_initialize_config()
            
            # Initialize project structure (creates directories and database)
            self.persistence_manager.initialize_project_structure()
            
            # Reload project plan after initialization
            self._project_plan = self._load_project_plan()
            
            # Update project name if provided
            if project_name and self._project_plan:
                self._project_plan.project_title = project_name
                self.persistence_manager.save_project_plan(self._project_plan)
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
        self.persistence_manager.save_project_plan(self._project_plan)
    
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
            self.persistence_manager.save_project_plan(self._project_plan)