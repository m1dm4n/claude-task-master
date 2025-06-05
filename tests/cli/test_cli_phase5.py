import pytest
from uuid import uuid4, UUID
from datetime import datetime, date, timezone
import json
from pathlib import Path
from typing import Optional, List, Union

from src.cli import app
from src.data_models import Task, TaskStatus, TaskPriority, ProjectPlan
from tests.cli.test_utils import run_cli_command, create_task_dict

# The format_datetime_for_cli helper is no longer needed as we control the plan content directly
# and assert against the expected CLI output format.

# --- Test Cases for 'task-master next' ---

@pytest.mark.asyncio
async def test_next_command_with_actionable_task(runner, cli_test_workspace, project_plan_factory, real_agent):
    # Arrange: Create a plan with a PENDING task whose dependency is COMPLETED.
    # Task B is a dependency for Task A.
    task_b_id = uuid4()
    task_a_id = uuid4()

    tasks_data = [
        create_task_dict(
            description="This task must be completed before Task A.",
            title="Task B: Complete prerequisite",
            status=TaskStatus.COMPLETED,
            _id=task_b_id
        ),
        create_task_dict(
            description="This task should be identified as the next actionable task.",
            title="Task A: Main actionable task",
            status=TaskStatus.PENDING,
            dependencies=[task_b_id],
            priority=TaskPriority.HIGH,
            _id=task_a_id
        ),
        create_task_dict(
            description="This task has an uncompleted dependency.",
            title="Task C: Blocked task",
            status=TaskStatus.PENDING,
            dependencies=[uuid4()] # A non-existent/uncompleted dependency
        ),
    ]
    project_plan_factory.create_with_tasks(tasks=tasks_data)
    # Act
    result = await run_cli_command(runner, ["next"], cli_test_workspace)

    # Assert
    assert result.exit_code == 0, f"CLI 'next' command failed: {result.stdout}"
    assert "🎯 Next actionable task:" in result.stdout
    assert f"ID: {str(task_a_id)}" in result.stdout
    assert "Title: Task A: Main actionable task" in result.stdout
    assert "Description: This task should be identified as the next actionable task." in result.stdout
    assert f"Status: {TaskStatus.PENDING.value}" in result.stdout
    assert f"Priority: {TaskPriority.HIGH.value}" in result.stdout
    assert f"Dependencies: {str(task_b_id)}" in result.stdout
    assert "Due Date: N/A" in result.stdout


@pytest.mark.asyncio
async def test_next_command_with_actionable_task_no_dependencies_no_due_date(runner, cli_test_workspace, project_plan_factory, real_agent):
    # Arrange: Create a plan with a single PENDING task, no dependencies, no due date.
    task_id = uuid4()
    tasks_data = [
        create_task_dict(
            title="Simple Actionable Task",
            description="This task has no dependencies and no due date.",
            status=TaskStatus.PENDING,
            _id=task_id
        ),
        create_task_dict(
            title="Completed Task",
            description="A completed task.",
            status=TaskStatus.COMPLETED
        ),
    ]
    project_plan_factory.create_with_tasks(tasks=tasks_data)
    # Act
    result = await run_cli_command(runner, ["next"], cli_test_workspace)

    # Assert
    assert result.exit_code == 0, result.stdout
    assert "🎯 Next actionable task:" in result.stdout
    assert f"ID: {str(task_id)}" in result.stdout
    assert "Title: Simple Actionable Task" in result.stdout
    assert "Description: This task has no dependencies and no due date." in result.stdout
    assert f"Status: {TaskStatus.PENDING.value}" in result.stdout
    assert f"Priority: {TaskPriority.MEDIUM.value}" in result.stdout # Corrected assertion
    assert "Dependencies: No" in result.stdout
    assert "Due Date: N/A" in result.stdout


@pytest.mark.asyncio
async def test_next_command_no_actionable_task_all_completed(runner, cli_test_workspace, project_plan_factory, real_agent):
    # Arrange: Create a plan where all tasks are COMPLETED.
    tasks_data = [
        create_task_dict(title="Task 1", description="Description 1", status=TaskStatus.COMPLETED),
        create_task_dict(title="Task 2", description="Description 2", status=TaskStatus.COMPLETED)
    ]
    project_plan_factory.create_with_tasks(tasks=tasks_data)

    # Act
    result = await run_cli_command(runner, ["next"], cli_test_workspace)

    # Assert
    assert result.exit_code == 0, result.stdout
    assert "🤷 No actionable PENDING tasks found with all dependencies met." in result.stdout


@pytest.mark.asyncio
async def test_next_command_no_actionable_task_all_blocked(runner, cli_test_workspace, project_plan_factory, real_agent):
    # Arrange: Create a plan where all tasks are PENDING but blocked by uncompleted dependencies.
    task_a_id = uuid4()
    task_b_id = uuid4()
    tasks_data = [
        create_task_dict(
            title="Task A (Blocked by B)",
            description="This task is blocked by Task B.",
            status=TaskStatus.PENDING,
            dependencies=[task_b_id],
            _id=task_a_id
        ),
        create_task_dict(
            title="Task B (Blocked by A)",
            description="This task is blocked by Task A.",
            status=TaskStatus.PENDING,
            dependencies=[task_a_id], # Task B now depends on Task A (circular dependency)
            _id=task_b_id
        ),
    ]
    project_plan_factory.create_with_tasks(tasks=tasks_data)

    # Act
    result = await run_cli_command(runner, ["next"], cli_test_workspace)

    # Assert
    assert result.exit_code == 0, result.stdout
    assert "🤷 No actionable PENDING tasks found with all dependencies met." in result.stdout


@pytest.mark.asyncio
async def test_next_command_empty_plan(runner, cli_test_workspace, project_plan_factory, real_agent):
    # Arrange: Create an empty plan.
    project_plan_factory.create_with_tasks(tasks=[])

    # Act
    result = await run_cli_command(runner, ["next"], cli_test_workspace)

    # Assert
    assert result.exit_code == 0, result.stdout
    assert "🤷 No actionable PENDING tasks found with all dependencies met." in result.stdout


@pytest.mark.asyncio
async def test_next_command_project_not_initialized(runner, cli_test_workspace, real_agent):
    # Arrange: Ensure no .taskmasterconfig exists by removing it.
    # The cli_test_workspace fixture ensures a clean slate, but we explicitly remove config.
    config_file = cli_test_workspace[0] / ".taskmasterconfig"
    if config_file.exists():
        config_file.unlink() # Remove the config file to simulate uninitialized project
    
    # Also ensure no project_plan.json exists
    plan_file = cli_test_workspace[0] / "project_plan.json"
    if plan_file.exists():
        plan_file.unlink()

    # Act
    result = await run_cli_command(runner, ["next"], cli_test_workspace)

    # Assert: Application now creates a default config if one is missing.
    # So, the command should run, print warnings, and then find no actionable tasks.
    assert result.exit_code == 0, f"Expected exit code 0 as app creates default config. Got {result.exit_code}. Output: {result.stdout}"
    assert "Warning: Configuration file" in result.stdout and "not found or empty. Creating default configuration." in result.stdout
    assert "Configuration saved to" in result.stdout
    assert "🤷 No actionable PENDING tasks found with all dependencies met." in result.stdout