import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Any, Dict, Literal, Union, Tuple
from uuid import UUID, uuid4

import logfire
from dotenv import load_dotenv

from ..data_models import Subtask, Task, ProjectPlan, ModelConfig, TaskStatus, TaskPriority
from ..config_manager import ConfigManager
from .llm_services import AgentDependencies
from .project_manager import ProjectManager
from .task_manager import TaskManager
from .llm_manager import LLMManager
from .planning_manager import PlanningManager

load_dotenv() 
logfire.configure(send_to_logfire='if-token-present')

class DevTaskAIAssistant:
    """
    An AI-driven task management assistant.
    Updated for Phase 1 to take workspace_path and initialize components accordingly.
    """
    
    def __init__(self, workspace_path: str = None):
        """
        Initialize DevTaskAIAssistant with workspace path.
        
        Args:
            workspace_path: Path to the workspace directory. Defaults to current working directory.
        """
        if workspace_path is None:
            workspace_path = os.getcwd()
            
        self.workspace_path = Path(workspace_path).resolve()
        
        # Initialize ConfigManager with workspace path
        self.config_manager = ConfigManager(str(self.workspace_path))
        
        # Initialize managers
        self.project_manager = ProjectManager(str(self.workspace_path), self.config_manager)
        self.llm_manager = LLMManager(self.config_manager)
        self.task_manager = TaskManager(self.project_manager)
        self.planning_manager = PlanningManager(self.llm_manager, self.project_manager)

    def initialize_project(self, project_name: Optional[str] = None) -> None:
        """
        Initialize project structure and configuration.
        
        Args:
            project_name: Optional name for the project
        """
        self.project_manager.initialize_project(project_name)

    def get_model_configurations(self) -> Dict[str, Optional[ModelConfig]]:
        """
        Get all model configurations.
        
        Returns:
            Dict mapping model type to ModelConfig
        """
        return self.llm_manager.get_model_configurations()

    def set_model_configuration(
        self, 
        model_type: Literal["main", "research", "fallback"], 
        model_name: str, 
        provider: Optional[str] = None, 
        api_key_str: Optional[str] = None, 
        base_url_str: Optional[str] = None
    ) -> bool:
        """
        Set model configuration for the specified type.
        
        Args:
            model_type: Type of model to configure
            model_name: Name of the model
            provider: Provider name (optional, inferred from model_name if not provided)
            api_key_str: API key string (optional)
            base_url_str: Base URL string (optional)
            
        Returns:
            True if configuration was set successfully, False otherwise
        """
        return self.llm_manager.set_model_configuration(
            model_type, model_name, provider, api_key_str, base_url_str
        )

    async def plan_project(self, project_goal: str, project_title: Optional[str] = "New Project", num_tasks: Optional[int] = None, use_research: bool = False, deps: Optional[AgentDependencies] = None) -> ProjectPlan:
        """
        Generate a project plan from a simple project goal using the LLMService.
        
        Args:
            project_goal: Description of the overall project goal.
            project_title: Optional title for the project.
            num_tasks: Optional. Desired number of main tasks.
            use_research: Whether to use the research model for planning.
            deps: Optional agent dependencies (not directly used by LLMService, but kept for consistency).
            
        Returns:
            Generated ProjectPlan.
        """
        return await self.planning_manager.plan_project(
            project_goal, project_title, num_tasks, use_research, deps
        )

    async def plan_project_from_prd_file(self, prd_file_path: Union[str, Path], project_title: Optional[str] = "New Project", num_tasks: Optional[int] = None, use_research: bool = False, deps: Optional[AgentDependencies] = None) -> ProjectPlan:
        """
        Generates a project plan by parsing a PRD file using the LLMService.
        Args:
            prd_file_path: Path to the PRD file.
            project_title: Optional title for the project. If not provided, derived from PRD or default.
            num_tasks: Optional. Desired number of main tasks.
            use_research: Whether to use the research model for planning.
            deps: Optional agent dependencies (not directly used by LLMService, but kept for consistency).
            
        Returns:
            Generated ProjectPlan.
        """
        return await self.planning_manager.plan_project_from_prd_file(
            prd_file_path, project_title, num_tasks, use_research, deps
        )

    async def refine_task(self, task_id: UUID, refinement_prompt: str, use_research: bool = False, deps: Optional[AgentDependencies] = None) -> Optional[Task]:
        """
        Refine a specific task using AI assistance.
        
        Args:
            task_id: UUID of the task to refine
            refinement_prompt: Instructions for refining the task
            use_research: Whether to use research model for refinement
            deps: Optional agent dependencies
            
        Returns:
            Refined Task object or None if task not found
        """
        task_to_refine = self.task_manager.get_item_by_id(task_id)
        if task_to_refine is None or not isinstance(task_to_refine, Task):
            logfire.warn(f"Task with ID {task_id} not found in project plan.")
            return None

        refined_task = await self.llm_manager.refine_task(task_to_refine, refinement_prompt, use_research, deps)
        
        if refined_task and self.task_manager.update_task_in_plan(task_id, refined_task):
            return refined_task
        return None

    async def refine_task_or_subtask(self, item_id: UUID, refinement_instruction: str, use_research: bool = False) -> Optional[Union[Task, Subtask]]:
        """
        Refine an individual task or subtask using AI assistance.
        
        Args:
            item_id: UUID of the task or subtask to refine
            refinement_instruction: Instructions for how to refine the item
            use_research: Whether to use the research model for refinement
            
        Returns:
            The updated Task or Subtask object, or None if item not found
        """
        # Find the item and its context using the task manager
        item, parent_list, item_index, parent_task = self.task_manager._find_item_and_context(item_id)
        
        if item is None:
            logfire.warn(f"Item with ID {item_id} not found in project plan.")
            return None
        
        try:
            # Store the original immutable fields
            original_id = item.id
            original_created_at = item.created_at
            
            # Call the LLM manager to refine the item details
            model_type = "research" if use_research else "main"
            updated_item_data = await self.llm_manager.refine_item_details(
                item, refinement_instruction, model_type
            )
            
            # Ensure ID and created_at are preserved (should already be handled by LLM manager)
            updated_item_data.id = original_id
            updated_item_data.created_at = original_created_at
            
            # Update the updated_at timestamp
            from datetime import datetime, timezone
            updated_item_data.updated_at = datetime.now(timezone.utc)
            
            # Replace the item in its parent list
            if parent_list is not None and item_index is not None:
                parent_list[item_index] = updated_item_data
                
                # Save the project plan
                self.project_manager.save_project_plan(self.project_manager.get_current_project_plan())
                
                logfire.info(f"Successfully refined {'task' if isinstance(updated_item_data, Task) else 'subtask'} {item_id}")
                return updated_item_data
            else:
                logfire.error(f"Could not determine parent context for item {item_id}")
                return None
                
        except Exception as e:
            logfire.error(f"Error refining item {item_id}: {e}")
            return None

    def get_current_project_plan(self) -> Optional[ProjectPlan]:
        """
        Get the current project plan.
        
        Returns:
            Current ProjectPlan or None
        """
        return self.project_manager.get_current_project_plan()

    def get_all_tasks(self) -> List[Task]:
        """
        Get all main tasks in the project plan.
        
        Returns:
            A list of all Task objects.
        """
        return self.task_manager.get_all_tasks()

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """
        Get main tasks filtered by their status.
        
        Args:
            status: The TaskStatus to filter by.
            
        Returns:
            A list of Task objects matching the given status.
        """
        return self.task_manager.get_tasks_by_status(status)

    def get_item_by_id(self, item_id: UUID) -> Optional[Union[Task, Subtask]]:
        """
        Get a Task or Subtask by its UUID.
        
        Args:
            item_id: The UUID of the item to retrieve.
            
        Returns:
            The found Task or Subtask object, or None if not found.
        """
        return self.task_manager.get_item_by_id(item_id)

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
        return self.task_manager.update_item_status(item_ids, new_status)

    def get_next_task(self) -> Optional[Task]:
        """
        Identifies the next actionable task based on its status and dependencies.
        A task is actionable if its status is PENDING and all its dependencies are COMPLETED.

        Returns:
            The first actionable Task found, or None if no such task exists.
        """
        return self.task_manager.get_next_task()

    def reload_project_plan(self) -> Optional[ProjectPlan]:
        """
        Reload project plan from storage.
        
        Returns:
            Reloaded ProjectPlan or None
        """
        return self.project_manager.reload_project_plan()

    async def research_query(self, query: str, tools: Optional[List[Any]] = None) -> Any:
        """
        Perform a research query using the research model.
        
        Args:
            query: Research query
            tools: Optional tools to make available
            
        Returns:
            Research results
        """
        return await self.llm_manager.research_query(query, tools)

    async def expand_task_with_subtasks(
        self,
        task_id: UUID,
        num_subtasks: Optional[int] = None,
        prompt_override: Optional[str] = None,
        use_research: bool = False
    ) -> Optional[Task]:
        """
        Expand a specific task by generating new subtasks using AI assistance.
        
        Args:
            task_id: UUID of the task to expand
            num_subtasks: Optional target number of subtasks to generate
            prompt_override: Optional custom prompt for subtask generation
            use_research: Whether to use the research model for expansion
            
        Returns:
            Updated Task object with new subtasks or None if task not found
        """
        # Find the task
        task_to_expand = self.task_manager.get_item_by_id(task_id)
        if task_to_expand is None or not isinstance(task_to_expand, Task):
            logfire.warn(f"Task with ID {task_id} not found in project plan.")
            return None
        
        try:
            # Generate new subtasks
            model_type = "research" if use_research else "main"
            new_subtasks = await self.llm_manager.generate_subtasks_for_task(
                task_description=task_to_expand.description,
                task_title=task_to_expand.title,
                existing_subtasks=task_to_expand.subtasks,
                num_subtasks=num_subtasks,
                context_prompt=prompt_override,
                model_type=model_type
            )
            
            if new_subtasks:
                # Append new subtasks to existing ones
                task_to_expand.subtasks.extend(new_subtasks)
                
                # Update the task's updated_at timestamp
                from datetime import datetime, timezone
                task_to_expand.updated_at = datetime.now(timezone.utc)
                
                # Update the task in the project plan
                if self.task_manager.update_task_in_plan(task_id, task_to_expand):
                    # Save the updated project plan
                    self.project_manager.save_project_plan()
                    logfire.info(f"Successfully expanded task {task_id} with {len(new_subtasks)} new subtasks")
                    return task_to_expand
                else:
                    logfire.error(f"Failed to update task {task_id} in project plan")
                    return None
            else:
                logfire.warn(f"No new subtasks generated for task {task_id}")
                return task_to_expand
                
        except Exception as e:
            logfire.error(f"Error expanding task {task_id}: {e}")
            return None

    async def expand_all_pending_tasks(
        self,
        force_regeneration: bool = False,
        use_research: bool = False,
        num_subtasks_per_task: Optional[int] = None
    ) -> int:
        """
        Expand all pending tasks by generating subtasks for each one.
        
        Args:
            force_regeneration: If True, expand even tasks that already have subtasks
            use_research: Whether to use the research model for expansion
            num_subtasks_per_task: Optional target number of subtasks per task
            
        Returns:
            Number of tasks that were successfully expanded
        """
        all_tasks = self.task_manager.get_all_tasks()
        expanded_count = 0
        
        for task in all_tasks:
            # Only process pending tasks
            if task.status != TaskStatus.PENDING:
                continue
                
            # Skip if task already has subtasks unless force_regeneration is True
            if task.subtasks and not force_regeneration:
                continue
                
            try:
                expanded_task = await self.expand_task_with_subtasks(
                    task_id=task.id,
                    num_subtasks=num_subtasks_per_task,
                    use_research=use_research
                )
                
                if expanded_task:
                    expanded_count += 1
                    logfire.info(f"Expanded task '{task.title}' (ID: {task.id})")
                else:
                    logfire.warn(f"Failed to expand task '{task.title}' (ID: {task.id})")
                    
            except Exception as e:
                logfire.error(f"Error expanding task '{task.title}' (ID: {task.id}): {e}")
                continue
        
        # Save the project plan once at the end for efficiency
        if expanded_count > 0:
            self.project_manager.save_project_plan()
            logfire.info(f"Successfully expanded {expanded_count} pending tasks")
        
        return expanded_count

    def clear_subtasks_for_task(self, task_id: UUID) -> bool:
        """
        Clear all subtasks from a specific task.
        
        Args:
            task_id: UUID of the task whose subtasks to clear
            
        Returns:
            True if subtasks were cleared successfully, False if task not found or not a Task object
        """
        # Find the task
        task = self.task_manager.get_item_by_id(task_id)
        if task is None or not isinstance(task, Task):
            logfire.warn(f"Task with ID {task_id} not found or is not a Task object.")
            return False
        
        # Clear subtasks if any exist
        if task.subtasks:
            task.subtasks.clear()
            
            # Update the task's updated_at timestamp
            from datetime import datetime, timezone
            task.updated_at = datetime.now(timezone.utc)
            
            # Save the updated project plan
            self.project_manager.save_project_plan()
            logfire.info(f"Successfully cleared subtasks for task {task_id}")
            return True
        else:
            logfire.info(f"Task {task_id} has no subtasks to clear")
            return True  # Consider this successful since the goal is achieved

    def clear_subtasks_for_all_tasks(self) -> int:
        """
        Clear subtasks from all tasks that have them.
        
        Returns:
            Number of tasks whose subtasks were cleared
        """
        all_tasks = self.task_manager.get_all_tasks()
        cleared_count = 0
        
        for task in all_tasks:
            if task.subtasks:
                task.subtasks.clear()
                
                # Update the task's updated_at timestamp
                from datetime import datetime, timezone
                task.updated_at = datetime.now(timezone.utc)
                
                cleared_count += 1
                logfire.info(f"Cleared subtasks for task '{task.title}' (ID: {task.id})")
        
        # Save the project plan once at the end for efficiency if any tasks were modified
        if cleared_count > 0:
            self.project_manager.save_project_plan()
            logfire.info(f"Successfully cleared subtasks from {cleared_count} tasks")
        
        return cleared_count

    async def add_new_task(self, description: str, use_research: bool = False, dependencies_str: Optional[List[str]] = None, priority_str: Optional[str] = None) -> Optional[Task]:
        """
        Add a new task to the project plan using AI-driven task generation.
        
        Args:
            description: Description or prompt for the new task
            use_research: Whether to use the research model for task generation
            dependencies_str: Optional list of task ID strings that this task depends on
            priority_str: Optional priority string (low, medium, high, critical)
            
        Returns:
            The newly created Task object if successful, None if failed
        """
        try:
            logfire.info(f"Adding new task using {'research' if use_research else 'main'} model")

            # Handle dependencies if provided (move to before LLM call)
            dependency_uuids = []
            if dependencies_str:
                for dep_str in dependencies_str:
                    try:
                        dependency_uuids.append(UUID(dep_str))
                    except ValueError as e:
                        logfire.error(f"Invalid dependency ID format: '{dep_str}': {e}")
                        return None
            
            # Handle priority if provided (move to before LLM call)
            priority_enum = None
            if priority_str:
                try:
                    priority_enum = TaskPriority(priority_str.upper())
                except ValueError as e:
                    logfire.error(f"Invalid priority: '{priority_str}': {e}")
                    return None
            
            # Get current project plan for context
            current_plan = self.project_manager.get_current_project_plan()
            if current_plan is None:
                logfire.error("No current project plan found. Cannot add task.")
                return None
            
            # Generate project context summary
            project_context_summary = self._generate_project_context_summary(current_plan)
            
            # Generate the new task using LLM
            model_type = "research" if use_research else "main"
            new_task = await self.llm_manager.generate_single_task(
                description, project_context_summary, model_type
            )
            
            # Set dependencies and priority on the new task object
            if dependency_uuids:
                new_task.dependencies = dependency_uuids
            
            if priority_enum:
                new_task.priority = priority_enum
            
            # Add the new task to the project plan
            current_plan.tasks.append(new_task)
            
            # Save the updated project plan
            self.project_manager.save_project_plan(current_plan)
            
            logfire.info(f"Successfully added new task: {new_task.title} (ID: {new_task.id})")
            return new_task
            
        except Exception as e:
            logfire.error(f"Error adding new task: {e}")
            return None
    
    def _generate_project_context_summary(self, project_plan: ProjectPlan) -> str:
        """
        Generate a concise project context summary for the LLM.
        
        Args:
            project_plan: The current project plan
            
        Returns:
            A formatted project context summary string
        """
        context_parts = []
        
        # Basic project info
        context_parts.append(f"Project: {project_plan.project_title}")
        context_parts.append(f"Goal: {project_plan.overall_goal}")
        context_parts.append(f"Total tasks: {len(project_plan.tasks)}")
        
        # Recent/important tasks for context
        if project_plan.tasks:
            # Get a few recent or high-priority tasks
            recent_tasks = project_plan.tasks[-3:]  # Last 3 tasks
            high_priority_tasks = [t for t in project_plan.tasks if t.priority in [TaskPriority.HIGH, TaskPriority.CRITICAL]][:2]
            
            context_tasks = list(set(recent_tasks + high_priority_tasks))[:5]  # Max 5 tasks for context
            
            if context_tasks:
                context_parts.append("\nExisting tasks:")
                for task in context_tasks:
                    for task in context_tasks:
                        context_parts.append(f"- {task.title} (Priority: {task.priority.value}, Status: {task.status.value})")
            
            return "\n".join(context_parts)
    
    def add_task_dependency(self, task_id: UUID, depends_on_id: UUID) -> bool:
        """
        Adds a dependency between two tasks.
        Args:
            task_id: The ID of the task to which the dependency is added.
            depends_on_id: The ID of the task that `task_id` will depend on.
        Returns:
            True if the dependency was successfully added, False otherwise.
        """
        success = self.task_manager.add_task_dependency(task_id, depends_on_id)
        if success:
            self.project_manager.save_project_plan(self.project_manager.get_current_project_plan())
        return success

    def remove_task_dependency(self, task_id: UUID, depends_on_id: UUID) -> bool:
        """
        Removes a dependency from a task.
        Args:
            task_id: The ID of the task from which the dependency is removed.
            depends_on_id: The ID of the dependency to remove.
        Returns:
            True if the dependency was successfully removed, False otherwise.
        """
        success = self.task_manager.remove_task_dependency(task_id, depends_on_id)
        if success:
            self.project_manager.save_project_plan(self.project_manager.get_current_project_plan())
        return success

    def validate_all_dependencies(self) -> Dict[str, List[str]]:
        """
        Validates all dependencies in the current project plan.
        Returns:
            A dictionary of validation errors (e.g., circular, missing IDs).
        """
        return self.task_manager.validate_all_dependencies()

    async def auto_fix_dependencies(self) -> Dict[str, Any]:
        """
        Attempts to automatically fix dependency issues using AI assistance.
        Returns:
            A dictionary summarizing the outcome, including whether fixes were applied
            and any remaining errors.
        """
        logfire.info("Attempting to auto-fix dependencies.")
        current_errors = self.validate_all_dependencies()

        if not current_errors["circular"] and not current_errors["missing_ids"]:
            logfire.info("No dependency errors found. No fixes needed.")
            return {"fixes_applied": False, "remaining_errors": {}}

        logfire.info(f"Identified dependency errors: {current_errors}")

        try:
            current_plan = self.project_manager.get_current_project_plan()
            if current_plan is None:
                logfire.error("No project plan loaded to fix dependencies.")
                return {"fixes_applied": False, "remaining_errors": current_errors}

            # LLM suggests a modified plan
            fixed_plan_suggestion = await self.llm_manager.suggest_dependency_fixes(
                current_plan, current_errors
            )

            # Apply changes from the suggested plan to the current plan
            # CRITICAL FIX: Iterate through the tasks of the *suggested* plan
            # or the deep copy that will be saved.
            changes_applied = False
            
            # Create a mutable copy of the current plan's tasks to modify
            # or directly use the fixed_plan_suggestion's tasks if it's a complete plan
            
            # The suggest_dependency_fixes returns a *new* ProjectPlan with suggested changes.
            # We should replace the current project plan with this new one.
            # However, the prompt implies modifying the existing plan in place.
            # Let's refine the application logic:
            
            # Create a map of tasks from the suggested plan for efficient lookup
            suggested_tasks_map = {task.id: task for task in fixed_plan_suggestion.tasks}
            
            # Iterate through the *current* plan's tasks and update their dependencies
            # based on the suggestions. This ensures other task attributes remain unchanged.
            for current_task in current_plan.tasks:
                suggested_task_for_current = suggested_tasks_map.get(current_task.id)
                if suggested_task_for_current:
                    # Only update if dependencies have actually changed
                    if set(suggested_task_for_current.dependencies) != set(current_task.dependencies):
                        logfire.info(f"Applying suggested dependency changes for task {current_task.id}")
                        current_task.dependencies = suggested_task_for_current.dependencies
                        current_task.updated_at = datetime.now(timezone.utc)
                        changes_applied = True
            
            # Save the modified current_plan
            if changes_applied:
                self.project_manager.save_project_plan(current_plan)
                logfire.info("Project plan saved after applying dependency fixes.")


            # Re-validate after applying fixes
            remaining_errors = self.validate_all_dependencies()

            if changes_applied:
                logfire.info("Dependency fixes applied. Re-validating...")
                if not remaining_errors["circular"] and not remaining_errors["missing_ids"]:
                    logfire.info("All dependency errors resolved.")
                    return {"fixes_applied": True, "remaining_errors": {}}
                else:
                    logfire.warn(f"Some dependency errors remain after auto-fix: {remaining_errors}")
                    return {"fixes_applied": True, "remaining_errors": remaining_errors}
            else:
                logfire.info("LLM suggested no changes or no changes were applicable.")
                return {"fixes_applied": False, "remaining_errors": remaining_errors}

        except Exception as e:
            logfire.error(f"Error during auto-fixing dependencies: {e}", exc_info=True)
            return {"fixes_applied": False, "remaining_errors": current_errors, "error": str(e)}