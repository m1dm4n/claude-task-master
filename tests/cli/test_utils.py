import json
import re # Added for extract_task_id_from_stdout
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timezone

import io
import inspect
import sys
import click
import typer.main
from typer.testing import CliRunner, Result as TyperResult

from src.cli.main import app
from src.data_models import ProjectPlan, Task, TaskStatus, TaskPriority # Removed Task
from src.agent_core.assistant import DevTaskAIAssistant

async def run_cli_command(runner: CliRunner, command_args: List[str], cli_test_workspace_tuple: Tuple[Path, DevTaskAIAssistant]) -> TyperResult:
    """
    Helper to run CLI commands with the test runner, supporting both sync and async commands.
    Sets the workspace and passes the agent instance.
    """
    workspace_path, agent_instance = cli_test_workspace_tuple
    original_cwd = os.getcwd()

    # Change to the workspace directory for the command execution
    os.chdir(workspace_path)

    try:
        # Use runner.invoke directly. pytest-asyncio and Typer's runner handle async.
        result = runner.invoke(app, command_args, catch_exceptions=False, obj={"agent": agent_instance})
        return result
    finally:
        # Always change back to the original directory
        os.chdir(original_cwd)

def get_task_by_id_from_file(workspace_path: Path, task_id: UUID) -> Optional[Task]:
    """
    Loads the project plan from the given workspace and retrieves a task by its ID.
    """
    project_plan_file = workspace_path / "project_plan.json"
    if not project_plan_file.exists():
        return None
    
    with open(project_plan_file, 'r') as f:
        data = json.load(f)
        project_plan = ProjectPlan.model_validate(data)
    
    for task in project_plan.tasks:
        if task.id == task_id:
            return task
        for subtask in task.subtasks:
            if subtask.id == task_id:
                return subtask # subtask is now a Task object, no conversion needed
    return None

def assert_task_properties(workspace_path: Path, task_id: UUID, **kwargs):
    """
    Loads a task by ID from the project plan and asserts its properties.
    """
    task = get_task_by_id_from_file(workspace_path, task_id)
    assert task is not None, f"Task with ID {task_id} not found in project plan."

    for prop, expected_value in kwargs.items():
        actual_value = getattr(task, prop)
        if prop == "dependencies":
            actual_deps_str = [str(dep) for dep in actual_value]
            expected_deps_str = [str(dep) for dep in expected_value]
            assert set(actual_deps_str) == set(expected_deps_str), f"Expected {prop} to be {expected_value}, but got {actual_value}"
        else:
            assert actual_value == expected_value, f"Expected {prop} to be {expected_value}, but got {actual_value}"

def create_task_dict(
    description: str,
    title: Optional[str] = None, # Make title optional, derive from description if not provided
    status: TaskStatus = TaskStatus.PENDING,
    priority: TaskPriority = TaskPriority.MEDIUM,
    details: Optional[str] = None,
    testStrategy: Optional[str] = None,
    dependencies: Optional[List[UUID]] = None,
    subtasks: Optional[List[Task]] = None, # Subtasks should also be Task objects
    parent_id: Optional[UUID] = None,
    _id: Optional[UUID] = None # Internal parameter to allow specifying ID for tests
) -> Task:
    """
    Helper to create a Task object for testing.
    """
    if title is None:
        title = description.splitlines()[0][:100] # Use first line of description as title

    return Task(
        id=_id if _id else uuid4(),
        title=title,
        description=description,
        status=status,
        priority=priority,
        details=details,
        testStrategy=testStrategy,
        dependencies=dependencies if dependencies else [],
        subtasks=subtasks if subtasks else [],
        parent_id=parent_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

def extract_task_id_from_stdout(stdout: str) -> Optional[UUID]:
    """
    Extracts a task ID (UUID) from CLI stdout.
    Assumes the ID is typically found after "ID: " or similar, and is a valid UUID.
    """
    # Regex to find a UUID pattern (8-4-4-4-12 hex characters)
    match = re.search(r'ID: ([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})', stdout)
    if match:
        try:
            return UUID(match.group(1))
        except ValueError:
            return None
    return None

def create_test_project_with_tasks(workspace_path: Path, tasks: List[Task]):
    """Helper to create a project plan with specific Task objects."""
    
    project_plan_file = workspace_path / "project_plan.json"
    project_plan = ProjectPlan(
        project_title="CLI Test Project",
        overall_goal="Test project for dependency CLI commands",
        tasks=tasks
    )
    with open(project_plan_file, 'w') as f:
        f.write(project_plan.model_dump_json(indent=2, exclude_none=True))
    return project_plan
