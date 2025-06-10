import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple
from uuid import UUID, uuid4

import logfire

from src.data_models import Task, TaskStatus, ProjectPlan, TaskPriority
from .project_service import ProjectService
from .llm_service import LLMService
from .task_components.task_crud_manager import TaskCRUDManager
from .task_components.task_state_and_hierarchy_manager import TaskStateAndHierarchyManager
# from .task_components.subtask_service import SubtaskService # subtask_service is gone
from .task_components.dependency_resolver import DependencyResolver
from .task_components.task_query_service import TaskQueryService


logger = logging.getLogger(__name__)


class TaskService:
    """
    Manages all Task operations, including CRUD, status updates,
    and AI-assisted task expansion and fixing.
    """

    def __init__(self, project_service: ProjectService, llm_service: LLMService):
        """
        Initialize TaskService.

        Args:
            project_service: ProjectService instance for managing the project plan.
            llm_service: LLMService instance for AI-driven task operations.
        """
        self.project_service = project_service
        self.llm_service = llm_service
        self.task_crud_manager = TaskCRUDManager(self.project_service)
        self.task_state_and_hierarchy_manager = TaskStateAndHierarchyManager(self.project_service)
        # self.subtask_service = SubtaskService(self.llm_service) # subtask_service is gone
        self.dependency_resolver = DependencyResolver(self.llm_service)
        self.task_query_service = TaskQueryService()
        logfire.info("TaskService initialized.")

    async def get_tasks_summary_for_llm(self) -> str:
        """Generates a summary of existing tasks for LLM context."""
        project_plan = await self.project_service.get_project_plan()
        if not project_plan or not project_plan.tasks:
            return "No tasks currently exist in the project plan."

        summary_lines = ["Existing Tasks:"]
        for task in project_plan.tasks:
            summary_lines.append(
                f"- ID: {task.id}, Title: {task.title}, Status: {task.status.value}")
        return "\n".join(summary_lines)

    async def get_all_tasks(self) -> List[Task]:
        project_plan = await self.project_service.get_project_plan()
        return self.task_query_service.get_all_tasks(project_plan) if project_plan else []

    async def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        project_plan = await self.project_service.get_project_plan()
        return self.task_query_service.get_tasks_by_status(project_plan, status) if project_plan else []

    async def get_task_by_id(self, item_id: UUID) -> Optional[Task]:
        """Retrieves a task or subtask by its ID."""
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            return None

        # all_tasks_map = self._get_all_tasks_map(project_plan) # replaced by task_query_service
        # return all_tasks_map.get(item_id)
        return self.task_query_service.get_task_by_id(project_plan, item_id)

    async def add_task(self, description: str, use_research: bool = False,
                           dependencies_str: Optional[List[str]] = None,
                           priority_str: Optional[str] = None,
                           parent_id_str: Optional[str] = None) -> Optional[Task]:
        """Adds a new task to the project plan based on a description, using AI to generate details."""
        try:
            # Convert dependencies_str to List[UUID]
            dependencies_uuids: List[UUID] = []
            if dependencies_str:
                for dep_str in dependencies_str:
                    try:
                        dependencies_uuids.append(UUID(dep_str))
                    except ValueError:
                        logfire.error(f"Invalid UUID format for dependency: {dep_str}. Skipping.")
                        return None # Or handle more gracefully, e.g., log and continue

            # Convert priority_str to TaskPriority enum
            priority_enum: Optional[TaskPriority] = None
            if priority_str:
                try:
                    priority_enum = TaskPriority[priority_str.upper()]
                except KeyError:
                    logfire.error(f"Invalid priority string: {priority_str}. Skipping.")
                return None # Or handle more gracefully

            new_task = await self.llm_service.generate_single_task_details(
                description_prompt=description,
                project_context=await self.get_tasks_summary_for_llm(),
                model_type="research" if use_research else "main"
            )

            if not new_task:
                logfire.warning("LLM did not generate new task details.")
                return None
            
            # Apply dependencies and priority from arguments if provided
            if dependencies_uuids:
                new_task.dependencies = dependencies_uuids
            if priority_enum:
                new_task.priority = priority_enum

            # current_plan = await self.project_service.get_project_plan() # handled by task_crud_manager

            if parent_id_str:
                parent_task = await self.get_task_by_id(UUID(parent_id_str))
                if parent_task:
                    new_task.parent = [UUID(parent_id_str)]
                    parent_task.children.append(new_task.id)
                    await self.update_task(parent_task)  # Update the parent task in the plan
                else:
                    logfire.error(f"Parent task with ID '{parent_id_str}' not found for subtask creation.")
                    raise ValueError(f"Parent task with ID '{parent_id_str}' not found.")
            else:
                # current_plan.tasks.append(new_task) # handled by task_crud_manager
                # await self.project_service.save_project_plan(current_plan) # handled by task_crud_manager
                await self.task_crud_manager.create_task(new_task)

            logfire.info(f"Successfully added new task: {new_task.title} (ID: {new_task.id})")
            return new_task
        except Exception as e:
            logfire.error(f"Error adding new task: {e}", exc_info=True)
            return None

    async def update_task(self, updated_task: Task) -> bool:
        """Updates an existing task in the project plan."""
        # project_plan = await self.project_service.get_project_plan() # handled by task_crud_manager
        # if project_plan is None: # handled by task_crud_manager
        #     logfire.warn("Cannot update task: Project plan not loaded or initialized.")
        #     return False

        # for i, task in enumerate(project_plan.tasks): # handled by task_crud_manager
        #     if task.id == updated_task.id: # handled by task_crud_manager
        #         project_plan.tasks[i] = updated_task # handled by task_crud_manager
        #         await self.project_service.save_project_plan(project_plan) # handled by task_crud_manager
        #         logfire.info(f"Successfully updated task: {updated_task.title} (ID: {updated_task.id})")
        #         return True

        # logfire.warn(f"Task or subtask with ID {updated_task.id} not found for update.") # handled by task_crud_manager
        # return False
        return await self.task_crud_manager.update_task(updated_task)

    async def update_task_status(self, item_ids: List[UUID], new_status: TaskStatus) -> Dict[UUID, bool]:
        """Updates the status of specified tasks or subtasks."""
        results: Dict[UUID, bool] = {}
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logfire.warn("Cannot update item status: Project plan not loaded or initialized.")
            for item_id in item_ids:
                results[item_id] = False
            return results

        changes_made = False

        for item_id in item_ids:
            # found_item, parent_list, index, parent_task = await self._find_item_and_context(item_id, project_plan) # replaced by task_query_service
            found_item = self.task_query_service.get_task_by_id(project_plan, item_id)
            if found_item:
                try:
                    # if parent_list is project_plan.tasks: # replaced by task_query_service
                    #     project_plan.tasks[index].status = new_status # replaced by task_query_service
                    #     project_plan.tasks[index].updated_at = datetime.now(timezone.utc) # replaced by task_query_service
                    found_item.status = new_status
                    # await self.task_state_and_hierarchy_manager.update_task_status(found_item, new_status)
                    # elif parent_task and parent_list is parent_task.subtasks:
                    #     parent_task.subtasks[index].status = new_status
                    #     parent_task.subtasks[index].updated_at = datetime.now(timezone.utc)
                    # else:
                    #     logfire.error(f"Found item {item_id} but could not determine its parent context for update.")
                    #     results[item_id] = False
                    #     continue
                    
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
                await self.project_service.save_project_plan(project_plan)
            except Exception as e:
                logfire.error(f"Error saving project plan after status updates: {e}")
                for item_id, success in results.items():
                    if success:
                        results[item_id] = False
        return results

    async def expand_task_with_subtasks(self, task_id: UUID, num_subtasks: Optional[int] = None, prompt_override: Optional[str] = None, use_research: bool = False) -> Optional[Task]:
        """Expands a task by generating subtasks."""
        logfire.info(f"Expanding task {task_id} with subtasks...")
        try:
            task = await self.get_task_by_id(task_id)
            if not task:
                logfire.error(f"Task with ID {task_id} not found.")
                return None

            generated_subtasks_data = await self.llm_service.generate_subtasks(
                description_prompt=task.description,
                project_context=await self.get_tasks_summary_for_llm(),
                num_subtasks=num_subtasks,
                prompt_override=prompt_override,
                model_type="research" if use_research else "main"
            )

            if not generated_subtasks_data:
                logfire.warning(f"LLM did not generate subtasks for task '{task.title}'. Returning original task.")
            # task.updated_at = datetime.now(timezone.utc) # handled by task_state_and_hierarchy_manager
            # await self.project_service.save_project_plan(await self.project_service.get_project_plan()) # handled by task_state_and_hierarchy_manager
            # await self.task_state_and_hierarchy_manager.update_task(task)
            return task
        except Exception as e:
            logfire.error(f"Error expanding task '{task.title}' (ID: {task_id}): {e}", exc_info=True)
            return None

    async def clear_subtasks_for_task(self, task_id: UUID) -> bool:
        """Clears all subtasks for a given task."""
        logger.info(f"Clearing subtasks for task {task_id}...")
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logger.warn("Cannot clear subtasks: Project plan not loaded or initialized.")
            return False

        task = await self.get_task_by_id(task_id)
        if not task:
            logger.warning(f"Task with ID {task_id} not found for clearing subtasks.")
            return False

        task.children = []
        return await self.task_crud_manager.update_task(task)

    async def clear_subtasks_for_all_tasks(self) -> int:
        """Clears all subtasks from all tasks in the project plan."""
        logger.info("Clearing subtasks from all tasks...")
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logger.warn("Cannot clear subtasks: Project plan not loaded or initialized.")
            return 0

        count = 0
        for task in project_plan.tasks:
            task.children = []
            count += 1
        if count > 0:
            await self.project_service.save_project_plan(project_plan)
            logger.info(f"Successfully cleared subtasks from {count} tasks.")
        else:
            logger.info("No tasks with subtasks found to clear.")
        return count

    async def move_task(self, task_id: UUID, new_parent_id: Optional[UUID] = None) -> bool:
        """Moves a task to a new parent or makes it a top-level task."""
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logger.warn("Cannot move task: Project plan not loaded or initialized.")
            return False

        task_to_move = await self.get_task_by_id(task_id)
        if not task_to_move:
            logger.error(f"Task with ID '{task_id}' not found.")
            return False

        original_parent_task = None
        for task in project_plan.tasks:
            if task_to_move.id in task.children:
                original_parent_task = task
                break

        if original_parent_task:
            original_parent_task.children.remove(task_to_move.id)
            await self.update_task(original_parent_task)

        if new_parent_id:
            new_parent_task = await self.get_task_by_id(new_parent_id)
            if not new_parent_task:
                logger.error(f"New parent task with ID '{new_parent_id}' not found.")
                if original_parent_task:
                    original_parent_task.children.append(task_to_move.id)
                    await self.update_task(original_parent_task)
                return False

        task_to_move.parent = [new_parent_id]
        new_parent_task.children.append(task_to_move.id)
        await self.update_task(new_parent_task)
        await self.update_task(task_to_move)
        logger.info(f"Moved task '{task_to_move.title}' to be a subtask of '{new_parent_task.title}'.")
    
        task_to_move.parent = []
        logger.info(f"Moved task '{task_to_move.title}' to be a top-level task.")

        return True

    async def remove_subtask(self, subtask_id: UUID) -> bool:
        """Removes a subtask from its parent task."""
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logger.warn("Cannot remove subtask: Project plan not loaded or initialized.")
            return False

        found_subtask = None
        parent_task = None
        for task in project_plan.tasks:
            if subtask_id in task.children:
                found_subtask = await self.get_task_by_id(subtask_id)
                parent_task = task
                break

        if not found_subtask:
            logger.error(f"Task with ID '{subtask_id}' not found.")
            return False

        parent_task.children.remove(subtask_id)
        await self.update_task(parent_task)
        logger.info(f"Successfully removed subtask {subtask_id} from task {parent_task.id}.")
        return True