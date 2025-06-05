import logging
from typing import Optional, List, Dict, Tuple
from uuid import UUID

import logfire

from ..data_models import Task, TaskStatus, ProjectPlan
from .project_io import ProjectIO


logger = logging.getLogger(__name__)


class DependencyManager:
    """
    Manages dependency graph logic, including validation and next task retrieval.
    """

    def __init__(self, project_io: ProjectIO):
        """
        Initialize DependencyManager.

        Args:
            project_io: ProjectIO instance
        """
        self.project_io = project_io

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

    def _get_all_tasks_map(self, project_plan: ProjectPlan) -> Dict[UUID, Task]:
        """Helper to create a flat map of all tasks and subtasks by ID."""
        all_tasks_map: Dict[UUID, Task] = {}
        for task in project_plan.tasks:
            all_tasks_map[task.id] = task
            for subtask in task.subtasks:
                all_tasks_map[subtask.id] = subtask
        return all_tasks_map

    def _is_circular_dependency(self, start_task_id: UUID, new_dependency_id: UUID, tasks_map: Dict[UUID, Task]) -> bool:
        """
        Checks if adding new_dependency_id to start_task_id's dependencies would create a circular dependency.
        This performs a DFS traversal starting from new_dependency_id to see if start_task_id is reachable.
        """
        if start_task_id == new_dependency_id:
            logfire.warn(f"Attempted to add self-dependency: {start_task_id}")
            return True

        visited = set()
        path = set()

        def dfs(current_task_id: UUID) -> bool:
            visited.add(current_task_id)
            path.add(current_task_id)

            if current_task_id == start_task_id:
                return True

            current_task = tasks_map.get(current_task_id)
            if not current_task:
                return False

            for neighbor_id in current_task.dependencies:
                if neighbor_id not in visited:
                    if dfs(neighbor_id):
                        return True
                elif neighbor_id in path:
                    logfire.warn(f"Circular dependency detected during traversal: {current_task_id} -> {neighbor_id}")
                    return True
            
            path.remove(current_task_id)
            return False

        return dfs(new_dependency_id)

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

    def add_dependencies(self, task_id: UUID, dependency_ids: List[UUID]) -> bool:
        """Adds dependencies to a task."""
        logger.info(f"Attempting to add dependencies {dependency_ids} to task {task_id}.")
        project_plan = self.project_io.get_current_project_plan()
        if not project_plan:
            logger.warn("Cannot add dependency: Project plan not loaded or initialized.")
            return False

        task = self._find_item_and_context(task_id, project_plan)[0]
        if not task:
            logger.error(f"Task with ID '{task_id}' not found for adding dependencies.")
            return False

        all_tasks_map = self._get_all_tasks_map(project_plan)

        for dep_id in dependency_ids:
            dependency = all_tasks_map.get(dep_id)
            if not dependency:
                logger.error(f"Dependency with ID '{dep_id}' not found for task '{task_id}'.")
                return False
            if task.id == dep_id:
                logger.error(f"Task '{task.id}' cannot depend on itself.")
                return False
            if dep_id in task.dependencies:
                logger.warning(f"Dependency '{dep_id}' already exists for task '{task.id}'.")
                continue

            original_dependencies = list(task.dependencies)
            task.dependencies.append(dep_id)

            if self._is_circular_dependency(task.id, dep_id, all_tasks_map):
                logger.error(f"Adding dependency '{dep_id}' to task '{task.id}' would create a circular dependency. Operation aborted.")
                task.dependencies = original_dependencies
                return False

        self.project_io.save_project_plan(project_plan)
        logger.info(f"Successfully added dependencies {dependency_ids} to task {task.id}.")
        return True

    def remove_dependencies(self, task_id: UUID, dependency_ids: List[UUID]) -> bool:
        """Removes dependencies from a task."""
        logger.info(f"Attempting to remove dependencies {dependency_ids} from task {task_id}.")
        project_plan = self.project_io.get_current_project_plan()
        if not project_plan:
            logger.warn("Cannot remove dependency: Project plan not loaded or initialized.")
            return False

        task = self._find_item_and_context(task_id, project_plan)[0]
        if not task:
            logger.error(f"Task with ID '{task_id}' not found for removing dependencies.")
            return False

        initial_len = len(task.dependencies)
        task.dependencies = [dep_id for dep_id in task.dependencies if dep_id not in dependency_ids]

        if len(task.dependencies) < initial_len:
            self.project_io.save_project_plan(project_plan)
            logger.info(f"Successfully removed dependencies from task {task.id}.")
            return True
        else:
            logger.warning(f"Dependency '{dependency_ids}' not found for task '{task_id}'.")
            return False

    def validate_all_dependencies(self) -> Dict[str, List[str]]:
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
        project_plan = self.project_io.get_current_project_plan()
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

            def find_cycles_dfs(current_node_id: UUID):
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
                        find_cycles_dfs(neighbor_id)
                
                on_stack.remove(current_node_id)
                path_stack.pop()

            find_cycles_dfs(start_node_id)

        if errors["circular"] or errors["missing_ids"]:
            logger.warn(f"Dependency validation found errors: {errors}")
        else:
            logger.info("All dependencies validated successfully. No errors found.")
        
        return errors

    def get_next_actionable_task(self) -> Optional[Task]:
        """
        Identifies the next actionable task based on its status and dependencies.
        A task is actionable if its status is PENDING and all its dependencies are COMPLETED.
        Returns:
            The first actionable Task found, or None if no such task exists.
        """
        project_plan = self.project_io.get_current_project_plan()
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