from pathlib import Path
from typing import Optional, Union
from uuid import uuid4
from datetime import datetime, timezone

import logfire

from ..data_models import ProjectPlan, Task, TaskStatus, TaskPriority
from .llm_generator import LLMGenerator
from .project_io import ProjectIO


class PlanBuilder:
    """
    Handles high-level project planning, using LLMGenerator.
    """
    
    def __init__(self, llm_generator: LLMGenerator, project_io: ProjectIO):
        """
        Initialize PlanBuilder.
        
        Args:
            llm_generator: LLMGenerator instance
            project_io: ProjectIO instance
        """
        self.llm_generator = llm_generator
        self.project_io = project_io
    
    async def plan_project(self, project_goal: str, project_title: Optional[str] = "New Project", num_tasks: Optional[int] = None, use_research: bool = False) -> ProjectPlan:
        """
        Generate a project plan from a simple project goal using the LLMGenerator.
        
        Args:
            project_goal: Description of the overall project goal.
            project_title: Optional title for the project.
            num_tasks: Optional. Desired number of main tasks.
            use_research: Whether to use the research model for planning.
            
        Returns:
            Generated ProjectPlan.
        """
        logfire.info(f"Planning project from goal: {project_goal}")
        
        try:
            project_plan = await self.llm_generator.generate_plan_from_text(
                text_content=None,
                project_goal=project_goal,
                num_tasks=num_tasks,
                model_type="research" if use_research else "main"
            )
            
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
                    subtasks=[],
                    dependencies=[]
                )
                project_plan.tasks.append(default_task)
                logfire.info(f"Added a default task based on the project goal: '{default_task.title}'")

            self.project_io.set_project_plan(project_plan)
            logfire.info(f"Successfully generated and saved project plan: {project_plan.project_title}")
            return project_plan
        except Exception as e:
            logfire.error(f"Error generating project plan from goal: {e}")
            raise
        
    async def plan_project_from_prd_file(self, prd_file_path: Union[str, Path], project_title: Optional[str] = "New Project", num_tasks: Optional[int] = None, use_research: bool = False) -> ProjectPlan:
        """
        Generates a project plan by parsing a PRD file using the LLMGenerator.

        Args:
            prd_file_path: Path to the PRD file.
            project_title: Optional title for the project. If not provided, derived from PRD or default.
            num_tasks: Optional. Desired number of main tasks.
            use_research: Whether to use the research model for planning.

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

            derived_project_goal = project_title if project_title != "New Project" else prd_file_path.stem.replace('_', ' ').title()
            
            project_plan = await self.llm_generator.generate_plan_from_text(
                text_content=prd_content,
                project_goal=derived_project_goal,
                num_tasks=num_tasks,
                model_type="research" if use_research else "main"
            )

            if project_title and project_title != "New Project":
                project_plan.project_title = project_title
            elif not project_plan.project_title or project_plan.project_title == "New Project":
                project_plan.project_title = derived_project_goal

            if not project_plan.overall_goal:
                project_plan.overall_goal = derived_project_goal

            self.project_io.set_project_plan(project_plan)
            logfire.info(f"Successfully generated and saved project plan from PRD: {project_plan.project_title}")
            return project_plan
        except Exception as e:
            logfire.error(f"Error generating project plan from PRD file {prd_file_path}: {e}")
            raise