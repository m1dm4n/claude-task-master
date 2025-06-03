"""Task operations and status management for the DevTask AI Assistant."""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Union, Tuple
from uuid import UUID

import logfire

from ..data_models import Task, Subtask, TaskStatus, ProjectPlan, ItemType


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

    def _is_circular_dependency(self, start_task_id: UUID, new_dependency_id: UUID, tasks_map: Dict[UUID, Task]) -> bool:
        """
        Checks if adding new_dependency_id to start_task_id's dependencies would create a circular dependency.
        This performs a DFS traversal starting from new_dependency_id to see if start_task_id is reachable.

        Args:
            start_task_id: The ID of the task to which a new dependency is being added.
            new_dependency_id: The ID of the task that start_task_id wants to depend on.
            tasks_map: A dictionary mapping all task UUIDs to their Task objects.

        Returns:
            True if adding the dependency creates a cycle, False otherwise.
        """
        if start_task_id == new_dependency_id:
            logfire.warn(f"Attempted to add self-dependency: {start_task_id}")
            return True # A task cannot depend on itself

        visited = set()
        path = set() # Tracks nodes in current DFS path to detect back-edges (cycles)

        def dfs(current_task_id: UUID) -> bool:
            visited.add(current_task_id)
            path.add(current_task_id)

            # If we reach the task that wants to add the dependency, it's a cycle
            if current_task_id == start_task_id:
                return True

            current_task = tasks_map.get(current_task_id)
            if not current_task:
                return False # Dependency not found, cannot form a cycle through it

            for neighbor_id in current_task.dependencies:
                # Removed the problematic 'if neighbor_id == start_task_id:' check here
                if neighbor_id not in visited:
                    if dfs(neighbor_id):
                        return True
                elif neighbor_id in path: # Back-edge detected
                    logfire.warn(f"Circular dependency detected during traversal: {current_task_id} -> {neighbor_id}")
                    return True
            
            path.remove(current_task_id) # Backtrack
            return False

        # Start DFS from the potential new dependency
        return dfs(new_dependency_id)

    def add_task_dependency(self, task_id: UUID, depends_on_id: UUID) -> bool:
        """
        Adds a dependency to a task.

        Args:
            task_id: The ID of the task to modify.
            depends_on_id: The ID of the task it will depend on.

        Returns:
            True if dependency was added, False otherwise (e.g., not found, circular, already exists).
        """
        project_plan = self.project_manager.get_current_project_plan()
        if not project_plan:
            logfire.warn("Cannot add dependency: Project plan not loaded or initialized.")
            return False

        task = self.get_item_by_id(task_id)
        depends_on_task = self.get_item_by_id(depends_on_id)

        if not isinstance(task, Task):
            logfire.warn(f"Task with ID {task_id} not found or is not a main Task.")
            return False
        if not isinstance(depends_on_task, Task):
            logfire.warn(f"Dependency task with ID {depends_on_id} not found or is not a main Task.")
            return False

        if depends_on_id in task.dependencies:
            logfire.warn(f"Dependency {depends_on_id} already exists for task {task_id}.")
            return False

        tasks_map = {t.id: t for t in project_plan.tasks}
        if self._is_circular_dependency(task_id, depends_on_id, tasks_map):
            logfire.error(f"Adding dependency {depends_on_id} to {task_id} would create a circular dependency.")
            return False

        task.dependencies.append(depends_on_id)
        task.updated_at = datetime.now(timezone.utc)
        self.project_manager.save_project_plan()
        logfire.info(f"Successfully added dependency {depends_on_id} to task {task_id}.")
        return True

    def remove_task_dependency(self, task_id: UUID, depends_on_id: UUID) -> bool:
        """
        Removes a dependency from a task.

        Args:
            task_id: The ID of the task to modify.
            depends_on_id: The ID of the dependency to remove.

        Returns:
            True if dependency was removed, False otherwise.
        """
        project_plan = self.project_manager.get_current_project_plan()
        if not project_plan:
            logfire.warn("Cannot remove dependency: Project plan not loaded or initialized.")
            return False

        task = self.get_item_by_id(task_id)
        if not isinstance(task, Task):
            logfire.warn(f"Task with ID {task_id} not found or is not a main Task.")
            return False

        if depends_on_id in task.dependencies:
            task.dependencies.remove(depends_on_id)
            task.updated_at = datetime.now(timezone.utc)
            self.project_manager.save_project_plan()
            logfire.info(f"Successfully removed dependency {depends_on_id} from task {task_id}.")
            return True
        else:
            logfire.warn(f"Dependency {depends_on_id} not found for task {task_id}.")
            return False

    def _get_canonical_cycle(self, cycle_path: List[UUID]) -> Tuple[UUID, ...]:
        """
        Converts a cycle path (list of UUIDs) into a canonical representation.
        For directed graphs, A->B->C->A is the same cycle as B->C->A->B.
        Canonical form: Find the lexicographically smallest UUID string in the cycle,
        then rotate the cycle list so it starts with this smallest UUID. If there are
        multiple occurrences of the smallest UUID, choose the one that results in the
        lexicographically smallest *sequence* after rotation.
        This ensures unique representation for a given cycle.
        """
        if not cycle_path:
            return tuple()

        # Convert UUIDs to strings for lexicographical comparison and sorting
        str_cycle = [str(uid) for uid in cycle_path]

        # Find the "smallest" UUID string in the cycle
        min_uuid_str = min(str_cycle)

        # Find all occurrences of the smallest UUID string to handle duplicates if any
        # and ensure we pick the one that results in the lexicographically smallest sequence
        best_rotated_cycle = None
        for i in range(len(str_cycle)):
            if str_cycle[i] == min_uuid_str:
                rotated_cycle = str_cycle[i:] + str_cycle[:i]
                if best_rotated_cycle is None or rotated_cycle < best_rotated_cycle:
                    best_rotated_cycle = rotated_cycle
        
        return tuple(UUID(s) for s in best_rotated_cycle)

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
        project_plan = self.project_manager.get_current_project_plan()
        if not project_plan:
            logfire.warn("Cannot validate dependencies: Project plan not loaded or initialized.")
            return errors

        tasks_map: Dict[UUID, Task] = {task.id: task for task in project_plan.tasks}
        
        # Build adjacency list for graph traversal and check for missing IDs
        graph: Dict[UUID, List[UUID]] = {task_id: [] for task_id in tasks_map.keys()}
        for task_id, task in tasks_map.items():
            for dep_id in task.dependencies:
                if dep_id not in tasks_map:
                    errors["missing_ids"].append(
                        f"Task '{task.title}' (ID: {task_id}) depends on non-existent task ID: {dep_id}"
                    )
                else:
                    graph[task_id].append(dep_id)

        found_cycles: set[Tuple[UUID, ...]] = set()
        
        # This implementation attempts to find elementary cycles using a modified DFS.
        # It's a common approach for finding all cycles, but ensuring *only* elementary
        # cycles without a full Johnson's algorithm is complex.
        # The current logic relies on `found_cycles` and `_get_canonical_cycle` to
        # filter out duplicates and rotations, but might still report non-elementary
        # cycles if the DFS path itself is non-elementary.
        
        # A more robust solution for elementary cycles would involve blocking nodes
        # (like in Johnson's or Tarjan's), but given the instruction for a simpler DFS,
        # we proceed with this approach and rely on canonicalization.

        for start_node_id in tasks_map.keys():
            # Reset visited/on_stack for each new DFS start node to find all cycles
            # (not just those reachable from a single source without re-visiting)
            # However, to find elementary cycles, we need to be careful about re-visiting
            # nodes within the *current* path.
            path_stack: List[UUID] = []
            on_stack: set[UUID] = set() # Nodes currently in the recursion stack for the *current* DFS path

            # To avoid re-finding cycles that start with a node already processed
            # as a start_node_id in the outer loop, we can use a global 'visited_outer' set.
            # However, for finding ALL elementary cycles, each node needs to be a potential
            # starting point for a DFS. The `on_stack` is crucial for detecting back-edges.
            
            # The current approach will find all cycles. The `_get_canonical_cycle`
            # and `found_cycles` set will ensure uniqueness of these cycles.
            # The "elementary" part is implicitly handled by the fact that `path_stack`
            # is reset for each new DFS from a `start_node_id`, and `on_stack` ensures
            # that we only consider back-edges to nodes currently in the recursion path.

            def find_cycles_dfs(current_node_id: UUID):
                path_stack.append(current_node_id)
                on_stack.add(current_node_id)

                for neighbor_id in graph.get(current_node_id, []):
                    if neighbor_id in on_stack:
                        # Cycle detected! Reconstruct the cycle from the path_stack
                        cycle_start_index = path_stack.index(neighbor_id)
                        current_cycle = path_stack[cycle_start_index:]
                        
                        canonical_cycle = self._get_canonical_cycle(current_cycle)
                        if canonical_cycle not in found_cycles:
                            found_cycles.add(canonical_cycle)
                            # For display, use the original path order for readability, then canonical for uniqueness check
                            errors["circular"].append(
                                f"Circular dependency detected: {' -> '.join(str(uid) for uid in current_cycle)} -> {str(current_cycle[0])}"
                            )
                    elif neighbor_id not in on_stack:
                        # Only recurse if neighbor is not already on the current path (to avoid infinite loops on cycles)
                        find_cycles_dfs(neighbor_id)
                
                # Backtrack: remove from recursion stack
                on_stack.remove(current_node_id)
                path_stack.pop()

            # Start DFS from the current node
            find_cycles_dfs(start_node_id)

        if errors["circular"] or errors["missing_ids"]:
            logfire.warn(f"Dependency validation found errors: {errors}")
        else:
            logfire.info("All dependencies validated successfully. No errors found.")
        
        return errors