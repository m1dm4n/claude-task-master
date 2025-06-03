"""Project planning and PRD parsing for the DevTask AI Assistant."""

from pathlib import Path
from typing import Optional, Union

import logfire

from ..data_models import ProjectPlan
from .llm_services import AgentDependencies


class PlanningManager:
    """Manages project planning and PRD parsing functionality."""
    
    def __init__(self, llm_manager, project_manager):
        """
        Initialize PlanningManager.
        
        Args:
            llm_manager: LLMManager instance
            project_manager: ProjectManager instance
        """
        self.llm_manager = llm_manager
        self.project_manager = project_manager
    
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
        logfire.info(f"Planning project from goal: {project_goal}")
        
        try:
            project_plan = await self.llm_manager.generate_plan_from_text(
                text_content=None, # No PRD content, just the goal
                project_goal=project_goal,
                num_tasks=num_tasks,
                model_type="research" if use_research else "main"
            )
            
            # Ensure project title and overall goal are set from input if not by LLM
            # If a custom project_title is provided (and not the default placeholder), use it.
            # Otherwise, use what the LLM provided, or fall back to the original project_title if LLM provided nothing.
            if project_title and project_title != "New Project":
                project_plan.project_title = project_title
            elif not project_plan.project_title: # If LLM gave no title, use input (which might be "New Project")
                project_plan.project_title = project_title
            # If LLM gave a title, and input was "New Project", we keep LLM's title.
            if not project_plan.overall_goal:
                project_plan.overall_goal = project_goal

            self.project_manager.set_project_plan(project_plan)
            logfire.info(f"Successfully generated and saved project plan: {project_plan.project_title}")
            return project_plan
        except Exception as e:
            logfire.error(f"Error generating project plan from goal: {e}")
            raise

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
        prd_file_path = Path(prd_file_path)
        if not prd_file_path.is_file():
            raise FileNotFoundError(f"PRD file not found at: {prd_file_path}")

        logfire.info(f"Planning project from PRD file: {prd_file_path}")

        try:
            with open(prd_file_path, 'r', encoding='utf-8') as f:
                prd_content = f.read()

            # Attempt to derive a project goal/title from the PRD content or filename
            # For simplicity, we can initially use the filename as a goal, or let LLM derive it.
            # In a real scenario, you might have a more sophisticated prompt to extract title/goal
            # or even use a dedicated LLM call just for that.
            derived_project_goal = project_title if project_title != "New Project" else prd_file_path.stem.replace('_', ' ').title()
            
            project_plan = await self.llm_manager.generate_plan_from_text(
                text_content=prd_content,
                project_goal=derived_project_goal,
                num_tasks=num_tasks,
                model_type="research" if use_research else "main"
            )

            # Update project title from input if provided, otherwise use LLM's title or derived
            if project_title and project_title != "New Project":
                project_plan.project_title = project_title
            elif not project_plan.project_title or project_plan.project_title == "New Project":
                project_plan.project_title = derived_project_goal # Fallback to derived from filename

            # Ensure overall goal is set if not by LLM
            if not project_plan.overall_goal:
                project_plan.overall_goal = derived_project_goal

            self.project_manager.set_project_plan(project_plan)
            logfire.info(f"Successfully generated and saved project plan from PRD: {project_plan.project_title}")
            return project_plan
        except Exception as e:
            logfire.error(f"Error generating project plan from PRD file {prd_file_path}: {e}")
            raise