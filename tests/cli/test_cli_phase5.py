import pytest
from typer.testing import CliRunner
from uuid import uuid4, UUID
from datetime import datetime, date, timezone # Added date
import json
from pathlib import Path
from typing import Optional, List, Union # Added Union

from src.cli import app
from src.data_models import Task, TaskStatus, TaskPriority, ProjectPlan, Subtask
from tests.cli.utils import requires_api_key

runner = CliRunner()

def format_datetime_for_cli(dt_input: Optional[Union[datetime, date, str]], cli_format: str = '%Y-%m-%d') -> str:
    if dt_input is None:
        return "N/A"

    dt_obj: Optional[Union[datetime, date]] = None

    if isinstance(dt_input, str):
        try:
            # Try parsing as full datetime first (ISO format with Z or offset)
            dt_obj = datetime.fromisoformat(dt_input.replace('Z', '+00:00'))
        except ValueError:
            try:
                # Try parsing as YYYY-MM-DD date string
                dt_obj = datetime.strptime(dt_input, '%Y-%m-%d').date()
            except ValueError:
                # Attempt to parse if it's just a date string that fromisoformat might handle for date part
                try:
                    dt_obj = date.fromisoformat(dt_input)
                except ValueError:
                    return "N/A" # Cannot parse string
    elif isinstance(dt_input, datetime): # Check if already datetime object
        dt_obj = dt_input
    elif isinstance(dt_input, date): # Check if already date object
        dt_obj = dt_input
    else:
        return "N/A" # Unsupported type

    if isinstance(dt_obj, datetime): # If it's a datetime object, format it
        return dt_obj.strftime(cli_format)
    elif isinstance(dt_obj, date): # If it's a date object
        return dt_obj.strftime(cli_format)
    
    return "N/A"


# --- Test Cases for 'task-master next' ---
@requires_api_key()
def test_next_command_with_actionable_task(cli_test_workspace):
    # Arrange: Create a plan. The goal is to have a clearly actionable PENDING task.
    plan_goal = "Setup a simple project: Task A (PENDING) depends on Task B (to be COMPLETED)"
    plan_title = "Next Task Test Plan"
    
    plan_result = runner.invoke(app, ['plan', plan_goal, '--title', plan_title])
    assert plan_result.exit_code == 0, f"Initial plan creation failed: {plan_result.stdout}"

    plan_file_path = cli_test_workspace / "project_plan.json"
    assert plan_file_path.exists(), "Plan file not found after initial plan."

    with open(plan_file_path, 'r') as f:
        initial_plan_data = json.load(f)
    initial_project_plan = ProjectPlan(**initial_plan_data)

    assert len(initial_project_plan.tasks) >= 1, "Plan should have at least one task."

    # Identify Task A (PENDING, to become actionable) and Task B (its dependency)
    # This relies on the LLM creating somewhat predictable tasks based on the goal.
    task_a_id: Optional[UUID] = None
    task_b_id: Optional[UUID] = None
    
    # Heuristic: Find a PENDING task that has a dependency. Mark that dependency COMPLETED.
    # If multiple, pick the first suitable one.
    for task_potential_a in initial_project_plan.tasks:
        if task_potential_a.status == TaskStatus.PENDING and task_potential_a.dependencies:
            # Check if this task's dependencies can be found and set to COMPLETED
            can_setup_dependency = False
            for dep_id_str in task_potential_a.dependencies:
                dep_task = next((t for t in initial_project_plan.tasks if str(t.id) == dep_id_str), None)
                if dep_task: # Found a dependency task
                    task_a_id = task_potential_a.id
                    task_b_id = dep_task.id # This is the dependency to complete
                    can_setup_dependency = True
                    break # Found a pair to work with
            if can_setup_dependency:
                break
    
    actionable_task_model: Optional[Task] = None
    if not (task_a_id and task_b_id):
        # Fallback: Create a simpler plan with just one task, assume it's PENDING and actionable
        plan_result_simple = runner.invoke(app, ['plan', "One single actionable task", '--title', "Simple Actionable Plan"])
        assert plan_result_simple.exit_code == 0, f"Simple plan creation failed: {plan_result_simple.stdout}"
        
        # Reload plan to get the task from the simple plan
        with open(plan_file_path, 'r') as f:
            simple_plan_data = json.load(f)
        simple_project_plan = ProjectPlan(**simple_plan_data)
        
        if simple_project_plan.tasks and simple_project_plan.tasks[0].status == TaskStatus.PENDING and not simple_project_plan.tasks[0].dependencies:
            actionable_task_model = simple_project_plan.tasks[0]
    else:
        # Set Task B to COMPLETED
        set_status_result = runner.invoke(app, ["set-status", "--id", str(task_b_id), "--status", "COMPLETED"])
        assert set_status_result.exit_code == 0, f"Failed to set dependency task {task_b_id} to COMPLETED: {set_status_result.stdout}"
        
        # Reload plan to get updated Task A
        with open(plan_file_path, 'r') as f:
            updated_plan_data = json.load(f)
        updated_project_plan = ProjectPlan(**updated_plan_data)
        actionable_task_model = next((t for t in updated_project_plan.tasks if t.id == task_a_id), None)
        
    if not actionable_task_model or actionable_task_model.status != TaskStatus.PENDING:
         pytest.skip("Could not reliably set up a single actionable PENDING task after all attempts.")

    # Act
    result = runner.invoke(app, ["next"])

    # Assert
    assert result.exit_code == 0, f"CLI 'next' command failed: {result.stdout}"
    assert "🎯 Next actionable task:" in result.stdout
    assert f"ID: {str(actionable_task_model.id)}" in result.stdout
    assert f"Title: {actionable_task_model.title}" in result.stdout
    
    expected_desc = actionable_task_model.description if actionable_task_model.description else "N/A"
    # Handle multi-line descriptions in CLI output by checking for the first line or a significant part.
    # The CLI might truncate or reformat. For simplicity, let's check for presence if not N/A.
    if expected_desc != "N/A":
        assert actionable_task_model.description in result.stdout # Check if the core description is there
    else:
        assert "Description: N/A" in result.stdout

    assert f"Status: {TaskStatus.PENDING.value}" in result.stdout
    
    expected_priority_str = actionable_task_model.priority.value if actionable_task_model.priority else "N/A"
    assert f"Priority: {expected_priority_str}" in result.stdout
    
    if actionable_task_model.dependencies:
        assert f"Dependencies: Yes (Count: {len(actionable_task_model.dependencies)})" in result.stdout
    else:
        assert "Dependencies: No" in result.stdout
    
    # Due date formatting from the model (which might be str or date) to CLI output format
    cli_due_date_str = format_datetime_for_cli(actionable_task_model.due_date)
    assert f"Due Date: {cli_due_date_str}" in result.stdout


@requires_api_key()
def test_next_command_with_actionable_task_no_dependencies_no_due_date(cli_test_workspace):
    # Arrange: Create a plan likely to have a simple PENDING task.
    plan_goal = "A single task, no dependencies, no due date"
    plan_title = "Simple Next Task Plan"
    plan_result = runner.invoke(app, ['plan', plan_goal, '--title', plan_title])
    assert plan_result.exit_code == 0, f"Plan creation failed: {plan_result.stdout}"

    plan_file_path = cli_test_workspace / "project_plan.json"
    assert plan_file_path.exists()
    with open(plan_file_path, 'r') as f:
        plan_data = json.load(f)
    project_plan = ProjectPlan(**plan_data)
    
    assert project_plan.tasks, "No tasks in generated plan."
    
    # Find a PENDING task with no dependencies and no due date, or the first PENDING task.
    # This test is somewhat reliant on the LLM generating such a task from the goal.
    simple_actionable_task = None
    for task in project_plan.tasks:
        if task.status == TaskStatus.PENDING and not task.dependencies and task.due_date is None:
            simple_actionable_task = task
            break
    if not simple_actionable_task and project_plan.tasks[0].status == TaskStatus.PENDING: # Fallback to first PENDING task
        simple_actionable_task = project_plan.tasks[0]


    if not simple_actionable_task:
        pytest.skip("Could not find/set up a simple PENDING task with no dependencies/due_date.")

    # Act
    result = runner.invoke(app, ["next"])

    # Assert
    assert result.exit_code == 0, result.stdout
    assert "🎯 Next actionable task:" in result.stdout
    assert f"ID: {str(simple_actionable_task.id)}" in result.stdout
    assert f"Title: {simple_actionable_task.title}" in result.stdout
    
    expected_desc = simple_actionable_task.description if simple_actionable_task.description else "N/A"
    if expected_desc != "N/A":
         assert simple_actionable_task.description in result.stdout
    else:
        assert "Description: N/A" in result.stdout
        
    assert f"Status: {TaskStatus.PENDING.value}" in result.stdout
    
    expected_priority_str = simple_actionable_task.priority.value if simple_actionable_task.priority else "N/A"
    assert f"Priority: {expected_priority_str}" in result.stdout
        
    assert "Dependencies: No" in result.stdout
    assert "Due Date: N/A" in result.stdout


@requires_api_key()
def test_next_command_no_actionable_task(cli_test_workspace):
    # Arrange: Create a plan, then ensure all tasks are COMPLETED.
    plan_goal = "Plan to test no actionable tasks scenario"
    plan_title = "All Completed Plan"
    plan_result = runner.invoke(app, ['plan', plan_goal, '--title', plan_title])
    assert plan_result.exit_code == 0, f"Plan creation failed: {plan_result.stdout}"

    plan_file_path = cli_test_workspace / "project_plan.json"
    assert plan_file_path.exists()
    with open(plan_file_path, 'r') as f:
        plan_data = json.load(f)
    project_plan = ProjectPlan(**plan_data)

    if project_plan.tasks:
        all_task_ids = [str(t.id) for t in project_plan.tasks]
        if all_task_ids:
            set_status_result = runner.invoke(app, ["set-status", "--id", ",".join(all_task_ids), "--status", "COMPLETED"])
            assert set_status_result.exit_code == 0, f"Failed to set all tasks to COMPLETED: {set_status_result.stdout}"
    # If no tasks were created by the plan, 'next' should also report no actionable tasks.

    # Act
    result = runner.invoke(app, ["next"])

    # Assert
    assert result.exit_code == 0, result.stdout
    assert "🤷 No actionable PENDING tasks found with all dependencies met." in result.stdout


def test_next_command_project_not_initialized(cli_test_workspace):
    # Arrange: Ensure no .taskmasterconfig exists by removing it.
    config_file = cli_test_workspace / ".taskmasterconfig"
    if config_file.exists():
        config_file.unlink() # Remove the config file to simulate uninitialized project
    # Act
    result = runner.invoke(app, ["next"])

    # Assert: Application now creates a default config if one is missing.
    # So, the command should run, print warnings, and then find no actionable tasks.
    assert result.exit_code == 0, f"Expected exit code 0 as app creates default config. Got {result.exit_code}. Output: {result.stdout}"
    assert "Warning: Configuration file" in result.stdout and "not found or empty. Creating default configuration." in result.stdout
    assert "Configuration saved to" in result.stdout
    assert "🤷 No actionable PENDING tasks found with all dependencies met." in result.stdout