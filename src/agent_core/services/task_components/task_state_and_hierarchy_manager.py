from typing import List
from uuid import UUID

from src.data_models import ProjectPlan, Task, TaskStatus


class TaskStateAndHierarchyManager:
    def __init__(self):
        pass

    def update_task_status(self, project_plan: ProjectPlan, task_id: UUID, new_status: TaskStatus) -> ProjectPlan:
        """Updates the status of a task in the project plan."""
        # Implementation for updating task status
        pass

    def set_task_parent(self, project_plan: ProjectPlan, task_id: UUID, parent_id: UUID) -> ProjectPlan:
        """Sets the parent task for a given task."""
        # Implementation for setting parent task
        pass

    def get_subtasks(self, project_plan: ProjectPlan, task_id: UUID) -> List[Task]:
        """Retrieves the subtasks for a given task."""
        # Implementation for getting subtasks
        pass