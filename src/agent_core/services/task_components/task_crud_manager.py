import logging
from typing import Optional, List
from uuid import UUID

from src.data_models import Task, ProjectPlan
from src.agent_core.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class TaskCRUDManager:
    """
    Manages CRUD operations for tasks within a project plan.
    """

    def __init__(self, project_service: ProjectService):
        """
        Initializes the TaskCRUDManager with a ProjectService instance.

        Args:
            project_service: The ProjectService instance to use for accessing the project plan.
        """
        self.project_service = project_service

    async def create_task(self, task: Task) -> bool:
        """
        Creates a new task in the project plan.

        Args:
            task: The Task object to create.

        Returns:
            True if the task was created successfully, False otherwise.
        """
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logger.warn("Cannot create task: Project plan not loaded or initialized.")
            return False

        project_plan.tasks.append(task)
        await self.project_service.save_project_plan(project_plan)
        logger.info(f"Successfully created task: {task.title} (ID: {task.id})")
        return True

    async def get_task(self, task_id: UUID) -> Optional[Task]:
        """
        Retrieves a task from the project plan by its ID.

        Args:
            task_id: The UUID of the task to retrieve.

        Returns:
            The Task object if found, otherwise None.
        """
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logger.warn("Cannot get task: Project plan not loaded or initialized.")
            return None

        for task in project_plan.tasks:
            if task.id == task_id:
                return task
        logger.warn(f"Task with ID {task_id} not found.")
        return None

    async def update_task(self, task: Task) -> bool:
        """
        Updates an existing task in the project plan.

        Args:
            task: The Task object to update.

        Returns:
            True if the task was updated successfully, False otherwise.
        """
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logger.warn("Cannot update task: Project plan not loaded or initialized.")
            return False

        for i, existing_task in enumerate(project_plan.tasks):
            if existing_task.id == task.id:
                project_plan.tasks[i] = task
                await self.project_service.save_project_plan(project_plan)
                logger.info(f"Successfully updated task: {task.title} (ID: {task.id})")
                return True

        logger.warn(f"Task with ID {task.id} not found for update.")
        return False

    async def delete_task(self, task_id: UUID) -> bool:
        """
        Deletes a task from the project plan.

        Args:
            task_id: The UUID of the task to delete.

        Returns:
            True if the task was deleted successfully, False otherwise.
        """
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logger.warn("Cannot delete task: Project plan not loaded or initialized.")
            return False

        initial_len = len(project_plan.tasks)
        project_plan.tasks = [task for task in project_plan.tasks if task.id != task_id]

        if len(project_plan.tasks) < initial_len:
            await self.project_service.save_project_plan(project_plan)
            logger.info(f"Successfully deleted task with ID: {task_id}")
            return True
        else:
            logger.warn(f"Task with ID {task_id} not found for deletion.")
            return False