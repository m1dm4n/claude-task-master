from typing import List, Optional, Literal
from uuid import UUID

from src.data_models import ProjectPlan, Task
from src.agent_core.services.llm_service import LLMService


class SubtaskService:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def generate_subtasks(
        self,
        project_plan: ProjectPlan,
        task: Task,
        num_subtasks: Optional[int] = None,
        prompt_override: Optional[str] = None,
        model_type: Literal["main", "research"] = "main"
    ) -> List[Task]:
        """Generates subtasks for a given task using AI assistance."""
        # Implementation for generating subtasks
        pass

    def clear_subtasks(self, project_plan: ProjectPlan, task_id: UUID) -> ProjectPlan:
        """Clears existing subtasks for a given task."""
        # Implementation for clearing subtasks
        pass