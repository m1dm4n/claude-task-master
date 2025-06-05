import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple
from uuid import UUID, uuid4

import logfire

from ..data_models import Task, TaskStatus, ProjectPlan, TaskPriority
from .llm_generator import LLMGenerator
from .project_io import ProjectIO
from .dependency_logic import DependencyManager


logger = logging.getLogger(__name__)


class TaskOperations:
    """
    Handles core task manipulations, orchestrates LLM calls for tasks.
    """
    
    def __init__(self, project_io: ProjectIO, llm_generator: LLMGenerator, dependency_manager: DependencyManager):
        """
        Initialize TaskOperations.
        
        Args:
            project_io: ProjectIO instance
            llm_generator: LLMGenerator instance
            dependency_manager: DependencyManager instance
        """
        self.project_io = project_io
        self.llm_generator = llm_generator
        self.dependency_manager = dependency_manager
    
    def _find_item_and_context(self, item_id: UUID, project_plan: Optional[ProjectPlan] = None) -> Tuple[Optional[Task], Optional[List[Task]], Optional[int], Optional[Task]]:
        """
        Internal helper to find a Task (which can be a subtask) by its UUID and return its context.
        
        Args:
            item_id: The UUID of the Task to find.
            project_plan: Optional ProjectPlan to search within. If None, loads current plan.
            
        Returns:
            A tuple: (found_item, parent_list_of_item, index_of_item_in_parent_list, parent_task_object_if_item_is_subtask)
        """
        if project_plan is None:
            project_plan = self.project_io.get_current_project_plan()
        
        if project_plan is None:
            return None, None, None, None

        for i, task in enumerate(project_plan.tasks):
            if task.id == item_id:
                return task, project_plan.tasks, i, None
            for j, subtask in enumerate(task.subtasks):
                if subtask.id == item_id:
                    return subtask, task.subtasks, j, task
        return None, None, None, None
    
    def get_tasks_summary(self, project_plan: ProjectPlan) -> str:
        """Generates a summary of existing tasks for LLM context."""
        if not project_plan.tasks:
            return "No tasks currently exist in the project plan."

        summary_lines = ["Existing Tasks:"]
        for task in project_plan.tasks:
            summary_lines.append(
                f"- ID: {task.id}, Title: {task.title}, Status: {task.status.value}")
            if task.subtasks:
                for subtask in task.subtasks:
                    summary_lines.append(
                        f"  - Task ID: {subtask.id}, Title: {subtask.title}, Status: {subtask.status.value}")
        return "\n".join(summary_lines)

    def get_all_tasks(self) -> List[Task]:
        """
        Get all main tasks in the project plan.
        
        Returns:
            A list of all Task objects.
        """
        project_plan = self.project_io.get_current_project_plan()
        return project_plan.tasks if project_plan else []
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """
        Get main tasks filtered by their status.
        
        Args:
            status: The TaskStatus to filter by.
            
        Returns:
            A list of Task objects matching the given status.
        """
        project_plan = self.project_io.get_current_project_plan()
        if project_plan is None:
            return []
        return [task for task in project_plan.tasks if task.status == status]
    
    def get_item_by_id(self, item_id: UUID, project_plan: Optional[ProjectPlan] = None) -> Optional[Task]:
        """
        Get a Task (which can be a subtask) by its UUID.
        
        Args:
            item_id: The UUID of the item to retrieve.
            project_plan: Optional ProjectPlan to search within. If None, loads current plan.
            
        Returns:
            The found Task object, or None if not found.
        """
        found_item, _, _, _ = self._find_item_and_context(item_id, project_plan)
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
        project_plan = self.project_io.get_current_project_plan()
        if project_plan is None:
            logfire.warn("Cannot update item status: Project plan not loaded or initialized.")
            for item_id in item_ids:
                results[item_id] = False
            return results

        changes_made = False

        for item_id in item_ids:
            found_item, parent_list, index, parent_task = self._find_item_and_context(item_id, project_plan)
            if found_item:
                try:
                    if parent_list is project_plan.tasks:
                        project_plan.tasks[index].status = new_status
                        project_plan.tasks[index].updated_at = datetime.now(timezone.utc)
                    elif parent_task and parent_list is parent_task.subtasks:
                        parent_task.subtasks[index].status = new_status
                        parent_task.subtasks[index].updated_at = datetime.now(timezone.utc)
                    else:
                        logfire.error(f"Found item {item_id} but could not determine its parent context for update.")
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
                self.project_io.save_project_plan(project_plan)
                logfire.info("Project plan saved after status updates.")
            except Exception as e:
                logfire.error(f"Error saving project plan after status updates: {e}")
                for item_id, success in results.items():
                    if success:
                        results[item_id] = False
        return results
    
    def update_task_in_plan(self, task_id: UUID, updated_task: Task) -> bool:
        """
        Update a task (or subtask) in the project plan.
        
        Args:
            task_id: UUID of the task to update
            updated_task: Updated Task object
            
        Returns:
            True if task was updated successfully, False otherwise
        """
        project_plan = self.project_io.get_current_project_plan()
        if project_plan is None:
            logfire.warn("Cannot update task: Project plan not loaded or initialized.")
            return False
        
        for i, task in enumerate(project_plan.tasks):
            if task.id == task_id:
                project_plan.tasks[i] = updated_task
                try:
                    self.project_io.save_project_plan(project_plan)
                    return True
                except Exception as e:
                    logfire.error(f"Error saving project plan after task update: {e}")
                    return False
            for j, subtask in enumerate(task.subtasks):
                if subtask.id == task_id:
                    task.subtasks[j] = updated_task
                    try:
                        self.project_io.save_project_plan(project_plan)
                        return True
                    except Exception as e:
                        logfire.error(f"Error saving project plan after subtask update: {e}")
                        return False
        logfire.warn(f"Task or subtask with ID {task_id} not found in project plan.")
        return False

    async def expand_task(self, task: Task, num_subtasks: Optional[int], prompt_override: Optional[str], use_research: bool) -> Optional[Task]:
        """
        Expands a given task by generating subtasks using the LLM.
        
        Args:
            task: The Task object to expand.
            num_subtasks: Optional. The desired number of subtasks to generate.
            prompt_override: Optional. A specific prompt to use for subtask generation.
            use_research: Whether to use the research model for generation.
            
        Returns:
            The updated Task object with new subtasks, or None if expansion fails.
        """
        logfire.info(f"Expanding task '{task.title}' (ID: {task.id})...")
        
        try:
            generated_subtasks_data = await self.llm_generator.generate_subtasks_for_task(
                task_description=task.description,
                task_title=task.title,
                existing_subtasks=task.subtasks,
                num_subtasks=num_subtasks,
                prompt_override=prompt_override,
                model_type="research" if use_research else "main"
            )

            if not generated_subtasks_data:
                logfire.warning(f"LLM did not generate subtasks for task '{task.title}'. Returning original task.")
                task.updated_at = datetime.now(timezone.utc)
                self.project_io.save_project_plan()
                return task

            new_subtasks = []
            for subtask_data in generated_subtasks_data:
                try:
                    subtask = subtask_data
                    subtask.parent_id = task.id
                    new_subtasks.append(subtask)
                except Exception as e:
                    logfire.error(f"Failed to validate generated subtask data: {subtask_data}. Error: {e}")
                    continue
            
            if not new_subtasks:
                logfire.warning(f"No valid subtasks were generated for task '{task.title}'.")
                return None

            task.subtasks.extend(new_subtasks)
            task.updated_at = datetime.now(timezone.utc)
            
            self.project_io.save_project_plan()
            logfire.info(f"Successfully expanded task '{task.title}' with {len(new_subtasks)} subtasks.")
            return task
        except Exception as e:
            logfire.error(f"Error expanding task '{task.title}' (ID: {task.id}): {e}", exc_info=True)
            return None

    def clear_subtasks_for_task(self, task_id: UUID) -> bool:
        """Clears all subtasks for a given task."""
        logger.info(f"Clearing subtasks for task {task_id}...")
        project_plan = self.project_io.get_current_project_plan()
        if project_plan is None:
            logger.warning("Cannot clear subtasks: Project plan not loaded or initialized.")
            return False

        for task in project_plan.tasks:
            if task.id == task_id:
                if task.subtasks:
                    task.subtasks = []
                    self.project_io.save_project_plan(project_plan)
                    logger.info(f"Successfully cleared subtasks for task {task.title}.")
                    return True
                else:
                    logger.info(f"Task {task.title} has no subtasks to clear.")
                    return False
        logger.warning(f"Task with ID {task_id} not found for clearing subtasks.")
        return False

    def clear_subtasks_for_all_tasks(self) -> int:
        """Clears all subtasks from all tasks in the project plan."""
        logger.info("Clearing subtasks from all tasks...")
        project_plan = self.project_io.get_current_project_plan()
        if project_plan is None:
            logger.warning("Cannot clear subtasks: Project plan not loaded or initialized.")
            return 0

        count = 0
        for task in project_plan.tasks:
            if task.subtasks:
                task.subtasks = []
                count += 1
        if count > 0:
            self.project_io.save_project_plan(project_plan)
            logger.info(f"Successfully cleared subtasks from {count} tasks.")
        else:
            logger.info("No tasks with subtasks found to clear.")
        return count

    def move_task(self, task_id: UUID, new_parent_id: Optional[UUID] = None) -> bool:
        """Moves a task to a new parent or makes it a top-level task."""
        project_plan = self.project_io.get_current_project_plan()
        if project_plan is None:
            logger.warn("Cannot move task: Project plan not loaded or initialized.")
            return False

        task_to_move = None
        original_parent_task = None

        for task in project_plan.tasks:
            if task.id == task_id:
                task_to_move = task
                project_plan.tasks.remove(task)
                break
            for subtask_idx, subtask in enumerate(task.subtasks):
                if subtask.id == task_id:
                    task_to_move = task.subtasks.pop(subtask_idx)
                    original_parent_task = task
                    break
            if task_to_move:
                break

        if not task_to_move:
            logger.error(f"Task with ID '{task_id}' not found.")
            return False

        if new_parent_id:
            new_parent_task = self.get_item_by_id(new_parent_id, project_plan)
            if not new_parent_task:
                logger.error(f"New parent task with ID '{new_parent_id}' not found.")
                if original_parent_task:
                    original_parent_task.subtasks.append(task_to_move)
                else:
                    project_plan.tasks.append(task_to_move)
                self.project_io.save_project_plan(project_plan)
                return False

            task_to_move.parent_id = new_parent_id
            new_parent_task.subtasks.append(task_to_move)
            self.update_task_in_plan(new_parent_task.id, new_parent_task) # Update the parent task
            logger.info(f"Moved task '{task_to_move.title}' to be a subtask of '{new_parent_task.title}'.")
        else:
            task_to_move.parent_id = None
            project_plan.tasks.append(task_to_move)
            logger.info(f"Moved task '{task_to_move.title}' to be a top-level task.")

        self.project_io.save_project_plan(project_plan)
        return True

    def remove_subtask(self, subtask_id: UUID) -> bool:
        """Removes a subtask from its parent task."""
        project_plan = self.project_io.get_current_project_plan()
        if project_plan is None:
            logger.warn("Cannot remove subtask: Project plan not loaded or initialized.")
            return False

        found_subtask = None
        parent_task = None
        for task in project_plan.tasks:
            for subtask_idx, subtask in enumerate(task.subtasks):
                if subtask.id == subtask_id:
                    found_subtask = task.subtasks.pop(subtask_idx)
                    parent_task = task
                    break
            if found_subtask:
                break

        if not found_subtask:
            logger.error(f"Task with ID '{subtask_id}' not found.")
            return False

        self.project_io.save_project_plan(project_plan)
        logger.info(f"Successfully removed subtask {subtask_id} from task {parent_task.id}.")
        return True