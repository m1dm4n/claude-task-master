from typing import List
from uuid import UUID

from src.data_models import ProjectPlan, Task, TaskStatus


class TaskQueryService:
    def __init__(self):
        pass

    def get_tasks_by_status(self, project_plan: ProjectPlan, status: TaskStatus) -> List[Task]:
        """Retrieves tasks from the project plan by status."""
        # Implementation for getting tasks by status
        pass

    def get_tasks_by_agent_type(self, project_plan: ProjectPlan, agent_type: str) -> List[Task]:
        """Retrieves tasks from the project plan by agent type."""
        # Implementation for getting tasks by agent type
        pass

    def get_all_tasks(self, project_plan: ProjectPlan) -> List[Task]:
        """Retrieves all tasks from the project plan."""
        # Implementation for getting all tasks
        pass