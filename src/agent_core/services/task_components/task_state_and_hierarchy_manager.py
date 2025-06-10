import logging
from typing import List, Dict
from uuid import UUID

from src.data_models import Task, TaskStatus
from src.agent_core.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class TaskStateAndHierarchyManager:
    """
    Manages task state transitions and parent-child relationships within a project plan.
    """

    def __init__(self, project_service: ProjectService):
        """
        Initializes the TaskStateAndHierarchyManager with a ProjectService instance.

        Args:
            project_service: The ProjectService instance to use for accessing the project plan.
        """
        self.project_service = project_service

    async def update_task_status(self, task: Task, new_status: TaskStatus) -> bool:
        """
        Updates the status of a task.

        Args:
            task: The Task object to update.
            new_status: The new TaskStatus to set.

        Returns:
            True if the task status was updated successfully, False otherwise.
        """
        if task.status == new_status:
            logger.info(f"Task {task.id} already has status {new_status.value}. Skipping update.")
            return True

        task.status = new_status
        # task.updated_at = datetime.now(timezone.utc) # updated_at should be handled by TaskService
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logger.warn("Cannot update task status: Project plan not loaded or initialized.")
            return False

        for i, existing_task in enumerate(project_plan.tasks):
            if existing_task.id == task.id:
                project_plan.tasks[i] = task
                await self.project_service.save_project_plan(project_plan)
                logger.info(f"Successfully updated status for task {task.title} (ID: {task.id}) to {new_status.value}")
                return True

        logger.warn(f"Task with ID {task.id} not found for status update.")
        return False

    async def add_child_task(self, parent_task: Task, child_task: Task) -> bool:
        """
        Adds a child task to a parent task.

        Args:
            parent_task: The parent Task object.
            child_task: The child Task object to add.

        Returns:
            True if the child task was added successfully, False otherwise.
        """
        if child_task.id in parent_task.children:
            logger.info(f"Task {child_task.id} is already a child of task {parent_task.id}. Skipping add.")
            return True

        parent_task.children.append(child_task.id)
        child_task.parent = [parent_task.id]

        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logger.warn("Cannot add child task: Project plan not loaded or initialized.")
            return False

        # Update both parent and child tasks in the project plan
        parent_updated = False
        child_updated = False
        for i, existing_task in enumerate(project_plan.tasks):
            if existing_task.id == parent_task.id:
                project_plan.tasks[i] = parent_task
                parent_updated = True
            if existing_task.id == child_task.id:
                project_plan.tasks[i] = child_task
                child_updated = True

        if parent_updated and child_updated:
            await self.project_service.save_project_plan(project_plan)
            logger.info(f"Successfully added child task {child_task.title} (ID: {child_task.id}) to parent task {parent_task.title} (ID: {parent_task.id})")
            return True
        else:
            logger.warn(f"Could not find parent or child task in project plan for adding child relationship.")
            return False

    async def remove_child_task(self, parent_task: Task, child_task: Task) -> bool:
        """
        Removes a child task from a parent task.

        Args:
            parent_task: The parent Task object.
            child_task: The child Task object to remove.

        Returns:
            True if the child task was removed successfully, False otherwise.
        """
        if child_task.id not in parent_task.children:
            logger.info(f"Task {child_task.id} is not a child of task {parent_task.id}. Skipping remove.")
            return True

        parent_task.children.remove(child_task.id)
        child_task.parent = []

        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logger.warn("Cannot remove child task: Project plan not loaded or initialized.")
            return False

        # Update both parent and child tasks in the project plan
        parent_updated = False
        child_updated = False
        for i, existing_task in enumerate(project_plan.tasks):
            if existing_task.id == parent_task.id:
                project_plan.tasks[i] = parent_task
                parent_updated = True
            if existing_task.id == child_task.id:
                project_plan.tasks[i] = child_task
                child_updated = True

        if parent_updated and child_updated:
            await self.project_service.save_project_plan(project_plan)
            logger.info(f"Successfully removed child task {child_task.title} (ID: {child_task.id}) from parent task {parent_task.title} (ID: {parent_task.id})")
            return True
        else:
            logger.warn(f"Could not find parent or child task in project plan for removing child relationship.")
            return False

    async def is_ancestor(self, task: Task, potential_ancestor: Task) -> bool:
        """
        Checks if a task is an ancestor of another task.

        Args:
            task: The Task object to check.
            potential_ancestor: The potential ancestor Task object.

        Returns:
            True if the potential ancestor is an ancestor of the task, False otherwise.
        """
        current_task = task
        while current_task.parent:
            parent_id = current_task.parent[0]
            if parent_id == potential_ancestor.id:
                return True
            project_plan = await self.project_service.get_project_plan()
            if project_plan is None:
                logger.warn("Cannot check ancestor: Project plan not loaded or initialized.")
                return False

            found_parent = False
            for existing_task in project_plan.tasks:
                if existing_task.id == parent_id:
                    current_task = existing_task
                    found_parent = True
                    break
            if not found_parent:
                return False
        return False

    async def detect_cycle(self, task: Task) -> bool:
        """
        Detects if adding the task as a child of itself would create a cycle.

        Args:
            task: The Task object to check.

        Returns:
            True if adding the task as a child of itself would create a cycle, False otherwise.
        """
        return await self.is_ancestor(task, task)