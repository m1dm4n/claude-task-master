import logging
from typing import Optional, List, Dict
from uuid import UUID

from src.data_models import Task, TaskStatus, ProjectPlan

logger = logging.getLogger(__name__)


class TaskQueryService:
    """
    Provides methods for querying tasks based on various criteria.
    """

    def get_all_tasks(self, project_plan: ProjectPlan) -> List[Task]:
        """
        Retrieves all tasks from the project plan.

        Args:
            project_plan: The ProjectPlan object to retrieve tasks from.

        Returns:
            A list of all Task objects in the project plan.
        """
        if project_plan is None:
            logger.warn("Cannot get all tasks: Project plan not loaded or initialized.")
            return []
        return project_plan.tasks

    def get_tasks_by_status(self, project_plan: ProjectPlan, status: TaskStatus) -> List[Task]:
        """
        Retrieves tasks from the project plan by their status.

        Args:
            project_plan: The ProjectPlan object to retrieve tasks from.
            status: The TaskStatus to filter by.

        Returns:
            A list of Task objects with the specified status.
        """
        if project_plan is None:
            logger.warn("Cannot get tasks by status: Project plan not loaded or initialized.")
            return []
        return [task for task in project_plan.tasks if task.status == status]

    def get_task_by_id(self, project_plan: ProjectPlan, task_id: UUID) -> Optional[Task]:
        """
        Retrieves a task from the project plan by its ID.

        Args:
            project_plan: The ProjectPlan object to retrieve tasks from.
            task_id: The UUID of the task to retrieve.

        Returns:
            The Task object if found, otherwise None.
        """
        if project_plan is None:
            logger.warn("Cannot get task by ID: Project plan not loaded or initialized.")
            return None
        for task in project_plan.tasks:
            if task.id == task_id:
                return task
        logger.warn(f"Task with ID {task_id} not found.")
        return None

    def get_tasks_with_dependency(self, project_plan: ProjectPlan, dependency_id: UUID) -> List[Task]:
        """
        Retrieves tasks that have a specific dependency.

        Args:
            project_plan: The ProjectPlan object to retrieve tasks from.
            dependency_id: The UUID of the dependency to search for.

        Returns:
            A list of Task objects that have the specified dependency.
        """
        if project_plan is None:
            logger.warn("Cannot get tasks with dependency: Project plan not loaded or initialized.")
            return []
        return [task for task in project_plan.tasks if dependency_id in task.dependencies]

    def get_child_tasks(self, project_plan: ProjectPlan, parent_task_id: UUID) -> List[Task]:
        """
        Retrieves the child tasks for a given parent task.

        Args:
            project_plan: The ProjectPlan object to retrieve tasks from.
            parent_task_id: The UUID of the parent task.

        Returns:
            A list of Task objects that are children of the specified parent task.
        """
        if project_plan is None:
            logger.warn("Cannot get child tasks: Project plan not loaded or initialized.")
            return []
        return [task for task in project_plan.tasks if parent_task_id in task.parent]

    def get_parent_tasks(self, project_plan: ProjectPlan, child_task_id: UUID) -> List[Task]:
        """
        Retrieves the parent tasks for a given child task.

        Args:
            project_plan: The ProjectPlan object to retrieve tasks from.
            child_task_id: The UUID of the child task.

        Returns:
            A list of Task objects that are parents of the specified child task.
        """
        if project_plan is None:
            logger.warn("Cannot get parent tasks: Project plan not loaded or initialized.")
            return []
        return [task for task in project_plan.tasks if child_task_id in task.children]

    def _get_all_tasks_map(self, project_plan: ProjectPlan) -> Dict[UUID, Task]:
        """Helper to create a flat map of all tasks and subtasks by ID."""
        all_tasks_map: Dict[UUID, Task] = {}
        for task in project_plan.tasks:
            all_tasks_map[task.id] = task
            # for subtask in task.subtasks: # subtasks is gone
            #     all_tasks_map[subtask.id] = subtask
            for child_id in task.children:
                child_task = self.get_task_by_id(project_plan, child_id)
                if child_task:
                    all_tasks_map[child_id] = child_task
        return all_tasks_map