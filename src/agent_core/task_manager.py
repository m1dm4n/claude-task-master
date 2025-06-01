"""Task operations and status management for the DevTask AI Assistant."""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Union, Tuple
from uuid import UUID

import logfire

from ..data_models import Task, Subtask, TaskStatus, ProjectPlan


class TaskManager:
    """Manages task operations, status updates, and task retrieval."""
    
    def __init__(self, project_manager):
        """
        Initialize TaskManager.
        
        Args:
            project_manager: ProjectManager instance
        """
        self.project_manager = project_manager
    
    def _find_item_and_context(self, item_id: UUID) -> Tuple[Optional[Union[Task, Subtask]], Optional[List[Union[Task, Subtask]]], Optional[int], Optional[Task]]:
        """
        Internal helper to find a Task or Subtask by its UUID and return its context.
        
        Args:
            item_id: The UUID of the Task or Subtask to find.
            
        Returns:
            A tuple: (found_item, parent_list_of_item, index_of_item_in_parent_list, parent_task_object_if_item_is_subtask)
        """
        project_plan = self.project_manager.get_current_project_plan()
        if project_plan is None:
            return None, None, None, None

        for i, task in enumerate(project_plan.tasks):
            if task.id == item_id:
                return task, project_plan.tasks, i, None
            for j, subtask in enumerate(task.subtasks):
                if subtask.id == item_id:
                    return subtask, task.subtasks, j, task
        return None, None, None, None
    
    def get_all_tasks(self) -> List[Task]:
        """
        Get all main tasks in the project plan.
        
        Returns:
            A list of all Task objects.
        """
        project_plan = self.project_manager.get_current_project_plan()
        return project_plan.tasks if project_plan else []
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """
        Get main tasks filtered by their status.
        
        Args:
            status: The TaskStatus to filter by.
            
        Returns:
            A list of Task objects matching the given status.
        """
        project_plan = self.project_manager.get_current_project_plan()
        if project_plan is None:
            return []
        return [task for task in project_plan.tasks if task.status == status]
    
    def get_item_by_id(self, item_id: UUID) -> Optional[Union[Task, Subtask]]:
        """
        Get a Task or Subtask by its UUID.
        
        Args:
            item_id: The UUID of the item to retrieve.
            
        Returns:
            The found Task or Subtask object, or None if not found.
        """
        found_item, _, _, _ = self._find_item_and_context(item_id)
        return found_item
    
    def update_item_status(self, item_ids: List[UUID], new_status: TaskStatus) -> Dict[UUID, bool]:
        """
        Updates the status of specified tasks or subtasks.

        Args:
            item_ids: A list of UUIDs of the tasks or subtasks to update.
            new_status: The new TaskStatus to set for the items.

        Returns:
            A dictionary where keys are the item_id (UUID) and values are booleans
            indicating success (True) or failure (False) of the status update for that item.
        """
        results: Dict[UUID, bool] = {}
        project_plan = self.project_manager.get_current_project_plan()
        if project_plan is None:
            logfire.warn("Cannot update item status: Project plan not loaded or initialized.")
            for item_id in item_ids:
                results[item_id] = False
            return results

        # Track if any item was actually updated to trigger a save
        changes_made = False

        for item_id in item_ids:
            found_item, parent_list, index, parent_task = self._find_item_and_context(item_id)
            if found_item:
                try:
                    # Update the item in its original list to ensure persistence
                    if isinstance(found_item, Task):
                        project_plan.tasks[index].status = new_status
                        project_plan.tasks[index].updated_at = datetime.now(timezone.utc)
                    elif isinstance(found_item, Subtask) and parent_task:
                        # Ensure the subtask is updated in the actual list
                        parent_task.subtasks[index].status = new_status
                        parent_task.subtasks[index].updated_at = datetime.now(timezone.utc)
                    else:
                        # This case should ideally not be reached if _find_item_and_context is correct
                        logfire.error(f"Found item {item_id} but could not determine its type or parent context for update.")
                        results[item_id] = False
                        continue
                        
                    results[item_id] = True
                    changes_made = True
                    logfire.info(f"Successfully updated status for item {item_id} to {new_status.value}")
                except Exception as e:
                    logfire.error(f"Failed to update status for item {item_id}: {e}")
                    results[item_id] = False
            else:
                logfire.warn(f"Item with ID {item_id} not found for status update.")
                results[item_id] = False

        if changes_made:
            try:
                self.project_manager.save_project_plan()
                logfire.info("Project plan saved after status updates.")
            except Exception as e:
                logfire.error(f"Error saving project plan after status updates: {e}")
                # If save fails, all successful updates in this batch are effectively failed
                for item_id, success in results.items():
                    if success:
                        results[item_id] = False # Mark as failed if save failed
        return results
    
    def get_next_task(self) -> Optional[Task]:
        """
        Identifies the next actionable task based on its status and dependencies.
        A task is actionable if its status is PENDING and all its dependencies are COMPLETED.

        Returns:
            The first actionable Task found, or None if no such task exists.
        """
        project_plan = self.project_manager.get_current_project_plan()
        if project_plan is None:
            logfire.warn("Cannot determine next task: Project plan not loaded or initialized.")
            return None

        # Create a dictionary for quick lookup of tasks by their UUID
        task_map: Dict[UUID, Task] = {task.id: task for task in project_plan.tasks}

        for task in project_plan.tasks:
            if task.status == TaskStatus.PENDING:
                # Check dependencies
                all_dependencies_completed = True
                if task.dependencies:
                    for dep_id in task.dependencies:
                        # dep_id is a string from task.dependencies, task_map keys are UUIDs
                        try:
                            # dep_id is already a UUID from Task.dependencies (List[UUID])
                            dep_uuid = dep_id
                            dep_task = task_map.get(dep_uuid)
                        except ValueError:
                            # Handle cases where dep_id might not be a valid UUID string
                            logfire.error(f"Invalid UUID string for dependency ID {dep_id} in task {task.id}. Assuming blocked.")
                            dep_task = None # Ensure it's treated as not found / not completed
                        if dep_task is None:
                            logfire.warn(f"Dependency task {dep_id} for task {task.id} not found. Assuming blocked.")
                            all_dependencies_completed = False
                            break
                        if dep_task.status != TaskStatus.COMPLETED:
                            all_dependencies_completed = False
                            break
                
                if all_dependencies_completed:
                    logfire.info(f"Identified next actionable task: {task.title} (ID: {task.id})")
                    return task
        
        logfire.info("No actionable pending tasks found.")
        return None
    
    def update_task_in_plan(self, task_id: UUID, updated_task: Task) -> bool:
        """
        Update a task in the project plan.
        
        Args:
            task_id: UUID of the task to update
            updated_task: Updated Task object
            
        Returns:
            True if task was updated successfully, False otherwise
        """
        project_plan = self.project_manager.get_current_project_plan()
        if project_plan is None:
            logfire.warn("Cannot update task: Project plan not loaded or initialized.")
            return False
        
        # Update the task in the project plan
        for i, task in enumerate(project_plan.tasks):
            if task.id == task_id:
                project_plan.tasks[i] = updated_task
                try:
                    self.project_manager.save_project_plan()
                    return True
                except Exception as e:
                    logfire.error(f"Error saving project plan after task update: {e}")
                    return False
        
        logfire.warn(f"Task with ID {task_id} not found in project plan.")
        return False