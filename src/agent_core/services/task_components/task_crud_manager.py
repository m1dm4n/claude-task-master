from typing import List, Optional
from uuid import UUID

from src.data_models import ProjectPlan, Task


class TaskCRUDManager:
    def __init__(self):
        pass

    def create_task(self, project_plan: ProjectPlan, task: Task) -> ProjectPlan:
        """Creates a new task in the project plan."""
        # Implementation for creating a task
        pass

    def get_task(self, project_plan: ProjectPlan, task_id: UUID) -> Optional[Task]:
        """Retrieves a task from the project plan by ID."""
        # Implementation for getting a task
        pass

    def update_task(self, project_plan: ProjectPlan, task: Task) -> ProjectPlan:
        """Updates an existing task in the project plan."""
        # Implementation for updating a task
        pass

    def delete_task(self, project_plan: ProjectPlan, task_id: UUID) -> ProjectPlan:
        """Deletes a task from the project plan by ID."""
        # Implementation for deleting a task
        pass