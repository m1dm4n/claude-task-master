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
from .task_components.subtask_service import SubtaskService
from .task_components.dependency_resolver import DependencyResolver
from .task_components.task_query_service import TaskQueryService


logger = logging.getLogger(__name__)


class TaskService:
    """
    Manages all Task and subtask operations, including CRUD, status updates,
    dependencies, and AI-assisted task expansion and fixing.
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
        self.task_crud_manager = TaskCRUDManager()
        self.task_state_and_hierarchy_manager = TaskStateAndHierarchyManager()
        self.subtask_service = SubtaskService(self.llm_service)
        self.dependency_resolver = DependencyResolver(self.llm_service)
        self.task_query_service = TaskQueryService()
        logfire.info("TaskService initialized.")

    async def get_tasks_summary_for_llm(self) -> str:
        """Generates a summary of existing tasks for LLM context."""
        project_plan = await self.project_service.get_project_plan()
        if not project_plan.tasks:
            return "No tasks currently exist in the project plan."

        summary_lines = ["Existing Tasks:"]
        for task in project_plan.tasks:
            summary_lines.append(
                f"- ID: {task.id}, Title: {task.title}, Status: {task.status.value}")
            # if task.subtasks: # subtasks is gone
            #     for subtask in task.subtasks:
            #         summary_lines.append(
            #             f"  - Task ID: {subtask.id}, Title: {subtask.title}, Status: {subtask.status.value}")
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

        all_tasks_map = self._get_all_tasks_map(project_plan)
        return all_tasks_map.get(item_id)

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

            current_plan = await self.project_service.get_project_plan()

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
                current_plan.tasks.append(new_task)
                await self.project_service.save_project_plan(current_plan)

            logfire.info(f"Successfully added new task: {new_task.title} (ID: {new_task.id})")
            # if new_task.subtasks: # subtasks is gone
            #     logfire.info(f"Generated {len(new_task.subtasks)} initial subtasks:")
            #     for i, subtask in enumerate(new_task.subtasks, 1):
            #         logfire.info(f"  {i}. {subtask.title} (ID: {subtask.id})")
            return new_task
        except Exception as e:
            logfire.error(f"Error adding new task: {e}", exc_info=True)
            return None

    async def update_task(self, updated_task: Task) -> bool:
        """Updates an existing task in the project plan."""
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logfire.warn("Cannot update task: Project plan not loaded or initialized.")
            return False
        
        for i, task in enumerate(project_plan.tasks):
            if task.id == updated_task.id:
                project_plan.tasks[i] = updated_task
                await self.project_service.save_project_plan(project_plan)
                logfire.info(f"Successfully updated task: {updated_task.title} (ID: {updated_task.id})")
                return True
            # for j, subtask in enumerate(task.subtasks): # subtasks is gone
            #     if subtask.id == updated_task.id:
            #         task.subtasks[j] = updated_task
            #         await self.project_service.save_project_plan(project_plan)
            #         logfire.info(f"Successfully updated subtask: {updated_task.title} (ID: {updated_task.id})")
            #         return True
        logfire.warn(f"Task or subtask with ID {updated_task.id} not found for update.")
        return False

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
            found_item, parent_list, index, parent_task = await self._find_item_and_context(item_id, project_plan)
            if found_item:
                try:
                    if parent_list is project_plan.tasks:
                        project_plan.tasks[index].status = new_status
                        project_plan.tasks[index].updated_at = datetime.now(timezone.utc)
                    # elif parent_task and parent_list is parent_task.subtasks: # subtasks is gone
                    #     parent_task.subtasks[index].status = new_status
                    #     parent_task.subtasks[index].updated_at = datetime.now(timezone.utc)
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
                await self.project_service.save_project_plan(project_plan)
                logfire.info("Project plan saved after status updates.")
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
                project_plan = await self.project_service.get_project_plan(),
                task=task,
                num_subtasks=num_subtasks,
                prompt_override=prompt_override,
                model_type="research" if use_research else "main"
            )

            if not generated_subtasks_data:
                logfire.warning(f"LLM did not generate subtasks for task '{task.title}'. Returning original task.")
                task.updated_at = datetime.now(timezone.utc)
                await self.project_service.save_project_plan(await self.project_service.get_project_plan())
                return task

            # task.subtasks.extend(generated_subtasks_data) # subtasks is gone
            task.children.extend([subtask.id for subtask in generated_subtasks_data])
            await self.update_task(task)
            task.updated_at = datetime.now(timezone.utc)
            
            await self.project_service.save_project_plan(await self.project_service.get_project_plan())
            logfire.info(f"Successfully expanded task '{task.title}' with {len(generated_subtasks_data)} subtasks.")
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

        for task in project_plan.tasks:
            if task.id == task_id:
                # if task.subtasks: # subtasks is gone
                #     task.subtasks = []
                task.children = []
                await self.project_service.save_project_plan(project_plan)
                logger.info(f"Successfully cleared subtasks for task {task.title}.")
                return True
            else:
                logger.info(f"Task {task.title} has no subtasks to clear.")
                return False
        logger.warning(f"Task with ID {task_id} not found for clearing subtasks.")
        return False

    async def clear_subtasks_for_all_tasks(self) -> int:
        """Clears all subtasks from all tasks in the project plan."""
        logger.info("Clearing subtasks from all tasks...")
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logger.warn("Cannot clear subtasks: Project plan not loaded or initialized.")
            return 0

        count = 0
        for task in project_plan.tasks:
            # if task.subtasks: # subtasks is gone
            #     task.subtasks = []
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

        task_to_move = None
        original_parent_task = None

        for task in project_plan.tasks:
            if task.id == task_id:
                task_to_move = task
                project_plan.tasks.remove(task)
                break
            # for subtask_idx, subtask in enumerate(task.subtasks): # subtasks is gone
            #     if subtask.id == task_id:
            #         task_to_move = task.subtasks.pop(subtask_idx)
            #         original_parent_task = task
            #         break
            if task_to_move:
                break

        if not task_to_move:
            logger.error(f"Task with ID '{task_id}' not found.")
            return False

        if new_parent_id:
            new_parent_task = await self.get_task_by_id(new_parent_id)
            if not new_parent_task:
                logger.error(f"New parent task with ID '{new_parent_id}' not found.")
                if original_parent_task:
                    # original_parent_task.subtasks.append(task_to_move) # subtasks is gone
                    original_parent_task.children.append(task_to_move.id)
                else:
                    project_plan.tasks.append(task_to_move)
                await self.project_service.save_project_plan(project_plan)
                return False

            # task_to_move.parent_id = new_parent_id # parent_id is gone
            task_to_move.parent = [new_parent_id]
            new_parent_task.children.append(task_to_move.id)
            await self.update_task(new_parent_task) # Update the parent task
            logger.info(f"Moved task '{task_to_move.title}' to be a subtask of '{new_parent_task.title}'.")
        else:
            # task_to_move.parent_id = None # parent_id is gone
            task_to_move.parent = []
            project_plan.tasks.append(task_to_move)
            logger.info(f"Moved task '{task_to_move.title}' to be a top-level task.")

        await self.project_service.save_project_plan(project_plan)
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
            # for subtask_idx, subtask in enumerate(task.subtasks): # subtasks is gone
            #     if subtask.id == subtask_id:
            #         found_subtask = task.subtasks.pop(subtask_idx)
            #         parent_task = task
            #         break
            if subtask_id in task.children:
                found_subtask = task.children.remove(subtask_id)
                parent_task = task
                break
            if found_subtask:
                break

        if not found_subtask:
            logger.error(f"Task with ID '{subtask_id}' not found.")
            return False

        await self.project_service.save_project_plan(project_plan)
        logger.info(f"Successfully removed subtask {subtask_id} from task {parent_task.id}.")
        return True

    async def add_dependency(self, task_id: UUID, dependency_ids: List[UUID]) -> bool:
        """Adds dependencies to a task."""
        logger.info(f"Attempting to add dependencies {dependency_ids} to task {task_id}.")
        project_plan = await self.project_service.get_project_plan()
        if not project_plan:
            logger.warn("Cannot add dependency: Project plan not loaded or initialized.")
            return False

        task = (await self._find_item_and_context(task_id, project_plan))[0]
        if not task:
            logger.error(f"Task with ID '{task_id}' not found for adding dependencies.")
            return False

        all_tasks_map = self._get_all_tasks_map(project_plan)
        
        changes_made = False
        for dep_id in dependency_ids:
            dependency = all_tasks_map.get(dep_id)
            if not dependency:
                logger.error(f"Dependency with ID '{dep_id}' not found for task '{task_id}'.")
                return False # Fail if any dependency is not found
            if task.id == dep_id:
                logger.error(f"Task '{task.id}' cannot depend on itself.")
                return False # Fail on self-dependency
            if dep_id in task.dependencies:
                logger.warning(f"Dependency '{dep_id}' already exists for task '{task.id}'. Skipping.")
                continue # Skip if already exists, but don't fail the whole operation

            original_dependencies = list(task.dependencies) # Store original for rollback
            task.dependencies.append(dep_id)

            if await self._is_circular_dependency(task.id, dep_id, all_tasks_map):
                logger.error(f"Adding dependency '{dep_id}' to task '{task.id}' would create a circular dependency. Operation aborted.")
                task.dependencies = original_dependencies # Rollback
                return False # Fail on circular dependency
            changes_made = True # Mark that a change was made

        if changes_made:
            await self.project_service.save_project_plan(project_plan)
            logger.info(f"Successfully added dependencies {dependency_ids} to task {task.id}.")
            return True
        else:
            logger.info(f"No new dependencies were added to task {task.id}.")
            return False # Return False if no actual changes were made

    async def remove_dependency(self, task_id: UUID, dependency_ids: List[UUID]) -> bool:
        """Removes dependencies from a task."""
        logger.info(f"Attempting to remove dependencies {dependency_ids} from task {task_id}.")
        project_plan = await self.project_service.get_project_plan()
        if not project_plan:
            logger.warn("Cannot remove dependency: Project plan not loaded or initialized.")
            return False

        task = (await self._find_item_and_context(task_id, project_plan))[0]
        if not task:
            logger.error(f"Task with ID '{task_id}' not found for removing dependencies.")
            return False
        initial_len = len(task.dependencies)
        task.dependencies = [dep_id for dep_id in task.dependencies if dep_id not in dependency_ids]

        if len(task.dependencies) < initial_len:
            await self.project_service.save_project_plan(project_plan)
            logger.info(f"Successfully removed dependencies from task {task.id}.")
            return True
        else:
            logger.warning(f"Dependency '{dependency_ids}' not found for task '{task_id}'.")
            return False

    async def validate_dependencies(self) -> Dict[str, List[str]]:
        """
        Validates all dependencies in the current project plan.

        Checks for:
        1. Missing IDs: Dependencies that point to non-existent tasks.
        2. Circular Dependencies: Unique elementary cycles in the dependency graph.

        Returns:
            A dictionary where keys are error types ("circular", "missing_ids")
            and values are lists of descriptive error messages.
        """
        errors: Dict[str, List[str]] = {"circular": [], "missing_ids": []}
        project_plan = await self.project_service.get_project_plan()
        if not project_plan:
            logger.warn("Cannot validate dependencies: Project plan not loaded or initialized.")
            return errors
        
        all_tasks_map = self._get_all_tasks_map(project_plan)
        graph: Dict[UUID, List[UUID]] = {task_id: [] for task_id in all_tasks_map.keys()}
        for task_id, task in all_tasks_map.items():
            for dep_id in task.dependencies:
                if dep_id not in all_tasks_map:
                    errors["missing_ids"].append(
                        f"Task '{task.title}' (ID: {task_id}) depends on non-existent task ID: {dep_id}"
                    )
                else:
                    graph[task_id].append(dep_id)

        found_cycles: set[Tuple[UUID, ...]] = set()
        
        for start_node_id in all_tasks_map.keys():
            path_stack: List[UUID] = []
            on_stack: set[UUID] = set()

            async def find_cycles_dfs(current_node_id: UUID):
                path_stack.append(current_node_id)
                on_stack.add(current_node_id)

                for neighbor_id in graph.get(current_node_id, []):
                    if neighbor_id in on_stack:
                        cycle_start_index = path_stack.index(neighbor_id)
                        current_cycle = path_stack[cycle_start_index:]
                        
                        canonical_cycle = self._get_canonical_cycle(current_cycle)
                        if canonical_cycle not in found_cycles:
                            found_cycles.add(canonical_cycle)
                            errors["circular"].append(
                                f"Circular dependency detected: {' -> '.join(str(uid) for uid in current_cycle)} -> {str(current_cycle[0])}"
                            )
                    elif neighbor_id not in on_stack:
                        await find_cycles_dfs(neighbor_id)
                
                on_stack.remove(current_node_id)
                path_stack.pop()
            
            await find_cycles_dfs(start_node_id)

        if errors["circular"] or errors["missing_ids"]:
            logger.warn(f"Dependency validation found errors: {errors}")
        else:
            logger.info("All dependencies validated successfully. No errors found.")
        
        return errors

    async def get_next_actionable_task(self) -> Optional[Task]:
        """
        Identifies the next actionable task based on its status and dependencies.
        A task is actionable if its status is PENDING and all its dependencies are COMPLETED.
        Returns:
            The first actionable Task found, or None if no such task exists.
        """
        project_plan = await self.project_service.get_project_plan()
        if project_plan is None:
            logger.warn("Cannot determine next task: Project plan not loaded or initialized.")
            return None

        all_tasks_map: Dict[UUID, Task] = self._get_all_tasks_map(project_plan)

        for task in project_plan.tasks:
            if task.status == TaskStatus.PENDING:
                all_dependencies_completed = True
                if task.dependencies:
                    for dep_id in task.dependencies:
                        dep_task = all_tasks_map.get(dep_id)
                        if dep_task is None:
                            logger.warn(f"Dependency task {dep_id} for task {task.id} not found. Assuming blocked.")
                            all_dependencies_completed = False
                            break
                        if dep_task.status != TaskStatus.COMPLETED:
                            all_dependencies_completed = False
                            break
                
                if all_dependencies_completed:
                    logger.info(f"Identified next actionable task: {task.title} (ID: {task.id})")
                    return task
        
        logger.info("No actionable pending tasks found.")
        return None

    async def fix_dependencies_ai(self, remove_invalid: bool = False, remove_circular: bool = False) -> List[str]:
        """Fixes dependency issues in the project plan using AI assistance."""
        logfire.info("Attempting to fix dependencies...")
        project_plan = await self.project_service.get_project_plan()
        errors = await self.validate_dependencies()
        is_valid = not bool(errors["circular"] or errors["missing_ids"])
        
        if is_valid:
            logfire.info("No dependency errors found. No fixes needed.")
            return []

        # Filter errors based on flags
        filtered_errors = {}
        if remove_invalid and errors.get("missing_ids"):
            filtered_errors["missing_ids"] = errors["missing_ids"]
        if remove_circular and errors.get("circular"):
            filtered_errors["circular"] = errors["circular"]

        if not filtered_errors:
            logfire.info("No applicable dependency errors to fix based on provided flags.")
            return []

        try:
            updated_plan = await self.dependency_resolver.suggest_dependency_fixes(
                project_plan=project_plan,
                validation_errors=filtered_errors,
                model_type="main" # Or "research" if appropriate
            )
            if updated_plan:
                await self.project_service.save_project_plan(updated_plan)
                logfire.info("Successfully applied suggested dependency fixes.")
                # Re-validate after applying fixes to report remaining issues
                errors = await self.validate_dependencies()
                if errors["circular"] or errors["missing_ids"]:
                    logfire.warning(f"Some dependency errors remain after fixing: {errors}")
                    return [f"Fixed some dependencies. Remaining errors: {errors}"]
                else:
                    return ["All identified dependency errors have been fixed."]
            else:
                logfire.warning("LLM did not provide dependency fix suggestions.")
                return ["LLM did not provide dependency fix suggestions."]
        except Exception as e:
            logfire.error(f"Error fixing dependencies: {e}", exc_info=True)
            return [f"Error fixing dependencies: {e}"]

    async def _find_item_and_context(self, item_id: UUID, project_plan: Optional[ProjectPlan] = None) -> Tuple[Optional[Task], Optional[List[UUID]], Optional[int], Optional[Task]]:
        """
        Internal helper to find a Task (which can be a subtask) by its UUID and return its context.
        """
        if project_plan is None:
            project_plan = await self.project_service.get_project_plan()
        
        if project_plan is None:
            return None, None, None, None

        for i, task in enumerate(project_plan.tasks):
            if task.id == item_id:
                return task, project_plan.tasks, i, None  # Found a top-level task

        # Search within children of each top-level task
        for task in project_plan.tasks:
            if item_id in task.children:
                for j, child_id in enumerate(task.children):
                    if child_id == item_id:
                        child_task = await self.get_task_by_id(item_id)
                        return child_task, task.children, j, task

        return None, None, None, None

    def _get_all_tasks_map(self, project_plan: ProjectPlan) -> Dict[UUID, Task]:
        """Helper to create a flat map of all tasks and subtasks by ID."""
        all_tasks_map: Dict[UUID, Task] = {}
        for task in project_plan.tasks:
            all_tasks_map[task.id] = task
            # for subtask in task.subtasks: # subtasks is gone
            #     all_tasks_map[subtask.id] = subtask
            for child_id in task.children:
                child_task = self.get_task_by_id(child_id)
                if child_task:
                    all_tasks_map[child_id] = child_task
        return all_tasks_map

    async def _is_circular_dependency(self, start_task_id: UUID, new_dependency_id: UUID, tasks_map: Dict[UUID, Task]) -> bool:
        """
        Checks if adding new_dependency_id to start_task_id's dependencies would create a circular dependency.
        This performs a DFS traversal starting from new_dependency_id to see if start_task_id is reachable.
        """
        if start_task_id == new_dependency_id:
            logfire.warn(f"Attempted to add self-dependency: {start_task_id}")
            return True

        visited = set()
        path = set()

        async def dfs(current_task_id: UUID) -> bool:
            visited.add(current_task_id)
            path.add(current_task_id)

            if current_task_id == start_task_id:
                return True

            current_task = tasks_map.get(current_task_id)
            if not current_task:
                return False

            for neighbor_id in current_task.dependencies:
                if neighbor_id not in visited:
                    if await dfs(neighbor_id):
                        return True
                elif neighbor_id in path:
                    logfire.warn(f"Circular dependency detected during traversal: {current_task_id} -> {neighbor_id}")
                    return True
            
            path.remove(current_task_id)
            return False

        return await dfs(new_dependency_id)

    def _get_canonical_cycle(self, cycle_path: List[UUID]) -> Tuple[UUID, ...]:
        """
        Converts a cycle path (list of UUIDs) into a canonical representation.
        """
        if not cycle_path:
            return tuple()

        str_cycle = [str(uid) for uid in cycle_path]
        min_uuid_str = min(str_cycle)

        best_rotated_cycle = None
        for i in range(len(str_cycle)):
            if str_cycle[i] == min_uuid_str:
                rotated_cycle = str_cycle[i:] + str_cycle[:i]
                if best_rotated_cycle is None or rotated_cycle < best_rotated_cycle:
                    best_rotated_cycle = rotated_cycle
        
        return tuple(UUID(s) for s in best_rotated_cycle)