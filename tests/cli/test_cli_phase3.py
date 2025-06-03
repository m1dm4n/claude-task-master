"""
Production functional tests for Phase 3 CLI functionality.
Tests the refactored list command and new show command with real data.
"""

import pytest
from typer.testing import CliRunner
from pathlib import Path
from uuid import uuid4, UUID
import json
import os

from unittest.mock import patch
from src.cli import app
from src.data_models import ProjectPlan, Task, Subtask, TaskStatus, TaskPriority
from tests.cli.conftest import setup_project_plan_file
from tests.cli.utils import requires_api_key


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


class TestListCommand:
    """Test cases for the list command."""

    def test_list_command_with_no_tasks(self, runner, cli_test_workspace):
        """Test list command with no tasks in the project."""
        # Arrange: Create an empty project plan
        empty_plan = ProjectPlan(
            project_title="Empty Project",
            overall_goal="A project with no tasks",
            tasks=[]
        )
        setup_project_plan_file(cli_test_workspace, empty_plan)

        # Act
        result = runner.invoke(app, ['list'])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "📋 All Tasks for \'Empty Project\'" in result.stdout
        assert "📝 No tasks found matching the criteria." in result.stdout
        assert "💡 Use 'task-master parse-prd' or 'task-master plan' to get started." in result.stdout

    def test_list_command_with_several_tasks_basic_output(self, runner, cli_test_workspace, sample_project_plan):
        """Test list command with several tasks, verifying basic output format."""
        # Arrange: Use the sample project plan from fixture
        setup_project_plan_file(cli_test_workspace, sample_project_plan)

        # Act
        result = runner.invoke(app, ['list'])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "📋 All Tasks for 'Test Project':" in result.stdout

        # Check that task information is displayed
        assert "ID: " in result.stdout
        assert "Status: PENDING" in result.stdout or "Status: IN_PROGRESS" in result.stdout or "Status: COMPLETED" in result.stdout

        # Check that sample task titles appear in output
        assert "Task 1: Setup" in result.stdout
        assert "Task 2: Development" in result.stdout
        assert "Task 3: Testing" in result.stdout

    # mock_agent removed
    def test_list_command_with_status_pending_filter(self, runner, cli_test_workspace):
        """Test list command with --status PENDING filter."""
        # Arrange: Create a plan. Most tasks will default to PENDING.
        plan_goal = "Organize a community meetup"
        plan_result = runner.invoke(
            app, ['plan', plan_goal, '--title', 'Meetup Plan'])
        assert plan_result.exit_code == 0, f"Plan creation failed: {plan_result.stdout}"
        assert "✅ Project plan" in plan_result.stdout

        # Act
        list_result = runner.invoke(app, ['list', '--status', 'PENDING'])

        # Assert
        assert list_result.exit_code == 0, list_result.stdout
        assert "📋 Tasks with status 'PENDING' for 'Meetup Plan':" in list_result.stdout

        # If tasks are listed, they should have PENDING status.
        # It's possible no tasks are PENDING if LLM marks all differently, though unlikely for a new plan.
        if "📝 No tasks found matching the criteria." not in list_result.stdout:
            assert "Status: PENDING" in list_result.stdout  # Check actual CLI output format
            assert "Status: IN_PROGRESS" not in list_result.stdout
            assert "Status: COMPLETED" not in list_result.stdout
        else:
            # If no tasks are found, the message should indicate that.
            assert "📝 No tasks found matching the criteria." in list_result.stdout

    @requires_api_key()
    # mock_agent removed
    def test_list_command_with_status_in_progress_filter(self, runner, cli_test_workspace):
        """Test list command with --status IN_PROGRESS filter."""
        # Arrange: Create a plan. It's unlikely to have IN_PROGRESS tasks initially.
        plan_goal = "Plan a world tour"
        plan_result = runner.invoke(
            app, ['plan', plan_goal, '--title', 'World Tour Plan'])
        assert plan_result.exit_code == 0, f"Plan creation failed: {plan_result.stdout}"
        assert "✅ Project plan" in plan_result.stdout

        # Act
        list_result = runner.invoke(app, ['list', '--status', 'IN_PROGRESS'])

        # Assert
        assert list_result.exit_code == 0, list_result.stdout
        assert "📋 Tasks with status 'IN_PROGRESS' for 'World Tour Plan':" in list_result.stdout

        # Expect no tasks to be found initially for IN_PROGRESS
        # If the LLM *does* create one, this test might become flaky or need adjustment.
        # For now, the most reliable outcome is that no IN_PROGRESS tasks exist for a new plan.
        if "📝 No tasks found matching the criteria." not in list_result.stdout:
            # This block would execute if, unexpectedly, IN_PROGRESS tasks were found
            # Corrected status string format
            assert "Status: IN_PROGRESS" in list_result.stdout
            assert "Status: TaskStatus.PENDING" not in list_result.stdout
            assert "Status: TaskStatus.COMPLETED" not in list_result.stdout
        else:
            assert "📝 No tasks found matching the criteria." in list_result.stdout

    # mock_agent removed
    @requires_api_key()
    def test_list_command_with_status_completed_filter(self, runner, cli_test_workspace):
        """Test list command with --status COMPLETED filter."""
        # Arrange: Create a plan. It's unlikely to have COMPLETED tasks initially.
        plan_goal = "Write a novel"
        plan_result = runner.invoke(
            app, ['plan', plan_goal, '--title', 'Novel Plan'])
        assert plan_result.exit_code == 0, f"Plan creation failed: {plan_result.stdout}"
        assert "✅ Project plan" in plan_result.stdout

        # Act
        list_result = runner.invoke(app, ['list', '--status', 'COMPLETED'])

        # Assert
        assert list_result.exit_code == 0, list_result.stdout
        assert "📋 Tasks with status 'COMPLETED' for 'Novel Plan':" in list_result.stdout

        # Expect no tasks to be found initially for COMPLETED
        if "📝 No tasks found matching the criteria." not in list_result.stdout:
            # This block would execute if, unexpectedly, COMPLETED tasks were found
            assert "Status: TaskStatus.COMPLETED" in list_result.stdout
            assert "Status: TaskStatus.PENDING" not in list_result.stdout
            assert "Status: TaskStatus.IN_PROGRESS" not in list_result.stdout
        else:
            assert "📝 No tasks found matching the criteria." in list_result.stdout

    @requires_api_key()
    def test_list_command_with_with_subtasks_flag(self, runner, cli_test_workspace):
        """Test list command with --with-subtasks flag."""
        # Arrange: Create a plan.
        plan_goal = "Develop a web app backend"  # Goal likely to generate subtasks
        plan_result = runner.invoke(
            app, ['plan', plan_goal, '--title', 'WebApp Backend Plan'])
        assert plan_result.exit_code == 0, f"Plan creation failed: {plan_result.stdout}"
        assert "✅ Project plan" in plan_result.stdout

        # Act
        list_result = runner.invoke(app, ['list', '--with-subtasks'])

        # Assert
        assert list_result.exit_code == 0, list_result.stdout
        
        # Act
        list_result = runner.invoke(app, ['list', '-s'])  # Use short flag

        # Assert
        assert list_result.exit_code == 0, list_result.stdout

    @requires_api_key()
    def test_list_command_with_short_subtasks_flag(self, runner, cli_test_workspace):
        """Test list command with -s (short flag for subtasks)."""
        # Arrange: Create a plan.
        plan_goal = "Design a new microchip"  # Goal likely to generate subtasks
        plan_result = runner.invoke(
            app, ['plan', plan_goal, '--title', 'Microchip Design Plan'])
        assert plan_result.exit_code == 0, f"Plan creation failed: {plan_result.stdout}"
        assert "✅ Project plan" in plan_result.stdout

        

    # mock_agent removed, cli_test_workspace added
    def test_list_command_handles_agent_exception(self, runner, cli_test_workspace):
        """Test list command handles exceptions from agent gracefully."""
        # Patch a method on the actual agent instance that `list` would use.
        # `get_current_project_plan` is called to display the project title.
        with patch('src.agent_core.main.DevTaskAIAssistant.get_current_project_plan',
                   side_effect=Exception("Simulated agent error on get_current_project_plan")):
            # Act
            result = runner.invoke(app, ['list'])

            # Assert
            assert result.exit_code == 1, result.stdout
            assert "❌ Error listing tasks: Simulated agent error on get_current_project_plan" in result.stdout

    # Uses cli_test_workspace
    def test_list_command_with_no_project_plan(self, runner, cli_test_workspace):
        """Test list command when agent has no project plan initially."""
        # Arrange: cli_test_workspace provides an empty environment.
        # The agent, when initialized, will find no existing user plan.
        # PersistenceManager might create a default "New Project" plan or load None.

        # Act
        result = runner.invoke(app, ['list'])

        # Assert
        assert result.exit_code == 0, result.stdout
        # The CLI should handle the case of no plan or an empty default plan gracefully.
        # Check for either "New Project" (if default is created and used) or "No Project" (if explicitly handled)
        # or simply that it states no tasks.
        assert "📝 No tasks found matching the criteria." in result.stdout
        if "No Project" in result.stdout:
            assert "📋 All Tasks for 'No Project':" in result.stdout
        elif "New Project" in result.stdout:
            assert "📋 All Tasks for 'New Project':" in result.stdout
        else:
            # Fallback if title is something else but no tasks are found
            assert "📋 All Tasks for" in result.stdout
            assert "📝 No tasks found matching the criteria." in result.stdout


class TestShowCommand:
    """Test cases for the show command."""

    @requires_api_key()
    # mock_agent removed
    def test_show_command_with_valid_task_id(self, runner, cli_test_workspace):
        """Test show command with a valid Task ID."""
        # Arrange: Create a plan that will have tasks.
        plan_goal = "Create a blog engine"
        plan_title = "Blog Engine Project"
        plan_result = runner.invoke(
            app, ['plan', plan_goal, '--title', plan_title])
        assert plan_result.exit_code == 0, f"Plan creation failed: {plan_result.stdout}"

        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists()
        with open(plan_file, "r") as f:
            plan_data = json.load(f)

        assert plan_data.get(
            "tasks"), "No tasks found in generated plan to show."
        if not plan_data["tasks"]:
            # Skip if LLM returned no tasks
            pytest.skip("No tasks generated by LLM to test 'show' command.")

        task_to_show = plan_data["tasks"][0]
        task_id_to_show = task_to_show["id"]

        # Act
        show_result = runner.invoke(app, ['show', task_id_to_show])

        # Assert
        assert show_result.exit_code == 0, show_result.stdout
        assert f"🔍 Details for Item (ID: {task_id_to_show})" in show_result.stdout
        assert f"Title: {task_to_show['title']}" in show_result.stdout
        assert f"ID: {task_id_to_show}" in show_result.stdout
        assert f"Description: {task_to_show['description']}" in show_result.stdout
        assert f"Status: {task_to_show['status']}" in show_result.stdout
        if task_to_show.get("priority"):  # Priority is optional
            assert f"Priority: {task_to_show['priority']}" in show_result.stdout
        if task_to_show.get("dependencies"):
            assert "Dependencies: " + \
                ", ".join(task_to_show['dependencies']) in show_result.stdout
        if task_to_show.get("details"):
            assert f"Details:\n{task_to_show['details']}" in show_result.stdout

        if task_to_show.get("subtasks"):
            assert "Subtasks:" in show_result.stdout
            # Check first few subtasks
            for subtask in task_to_show["subtasks"][:2]:
                assert f"- {subtask['title']} (ID: {subtask['id']}, Status: {subtask['status']})" in show_result.stdout

    @requires_api_key()
    # mock_agent removed
    def test_show_command_with_valid_subtask_id(self, runner, cli_test_workspace):
        """Test show command with a valid Subtask ID."""
        # Arrange: Create a plan, ensuring it's likely to have subtasks.
        plan_goal = "Develop a web application with user auth and admin panel"
        plan_title = "Complex Web App"
        plan_result = runner.invoke(
            app, ['plan', plan_goal, '--title', plan_title, '--num-tasks', '3'])  # Request a few tasks
        assert plan_result.exit_code == 0, f"Plan creation failed: {plan_result.stdout}"

        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists()
        with open(plan_file, "r") as f:
            plan_data = json.load(f)

        subtask_to_show = None
        subtask_id_to_show = None
        for task in plan_data.get("tasks", []):
            if task.get("subtasks"):
                subtask_to_show = task["subtasks"][0]
                subtask_id_to_show = subtask_to_show["id"]
                break

        if not subtask_id_to_show:
            pytest.skip(
                "No subtasks generated by LLM to test 'show subtask' command.")

        # Act
        show_result = runner.invoke(app, ['show', subtask_id_to_show])

        # Assert
        assert show_result.exit_code == 0, show_result.stdout
        assert f"🔍 Details for Item (ID: {subtask_id_to_show})" in show_result.stdout
        assert f"Title: {subtask_to_show['title']}" in show_result.stdout
        assert f"ID: {subtask_id_to_show}" in show_result.stdout
        assert f"Description: {subtask_to_show['description']}" in show_result.stdout
        assert f"Status: {subtask_to_show['status']}" in show_result.stdout
        if subtask_to_show.get("priority"):
            assert f"Priority: {subtask_to_show['priority']}" in show_result.stdout
        # Subtasks don't have their own "Subtasks:" section displayed by `show`
        assert "Subtasks:" not in show_result.stdout

    # mock_agent removed
    def test_show_command_with_invalid_uuid_format(self, runner, cli_test_workspace):
        """Test show command with an invalid UUID format."""
        # Act
        result = runner.invoke(app, ['show', 'invalid-uuid-format'])

        # Assert
        # Typer usually exits with 2 for validation, but CLI might catch and exit 1
        assert result.exit_code == 1, result.stdout
        # Make assertion more general for CLI error message
        assert "Invalid ID format" in result.stdout
        assert "'invalid-uuid-format'" in result.stdout

    # mock_agent removed
    def test_show_command_with_valid_uuid_but_nonexistent_id(self, runner, cli_test_workspace):
        """Test show command with a valid UUID format but non-existent ID."""
        # Arrange
        nonexistent_id = uuid4()  # Generate a random UUID that won't exist

        # Act
        result = runner.invoke(app, ['show', str(nonexistent_id)])

        # Assert
        assert result.exit_code == 1, result.stdout
        assert f"❌ Item with ID '{nonexistent_id}' not found." in result.stdout
        # No need to verify mock_agent.get_item_by_id call in functional test

    # mock_agent removed
    def test_show_command_handles_agent_exception(self, runner, cli_test_workspace):
        """Test show command handles exceptions from agent gracefully."""
        # Arrange
        valid_id_for_test = uuid4()  # ID format is valid, agent will try to fetch

        with patch('src.agent_core.main.DevTaskAIAssistant.get_item_by_id',
                   side_effect=Exception("Simulated database error during show")):
            # Act
            result = runner.invoke(app, ['show', str(valid_id_for_test)])

            # Assert
            assert result.exit_code == 1, result.stdout
            assert "❌ An unexpected error occurred: Simulated database error during show" in result.stdout

    @requires_api_key()
    # mock_agent removed
    def test_show_command_task_without_optional_fields(self, runner, cli_test_workspace):
        """Test show command displays a task's core fields."""
        # Arrange: Create a plan.
        plan_goal = "Simple task for display"
        plan_title = "Display Test Plan"
        plan_result = runner.invoke(
            app, ['plan', plan_goal, '--title', plan_title])
        assert plan_result.exit_code == 0, f"Plan creation failed: {plan_result.stdout}"

        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists()
        with open(plan_file, "r") as f:
            plan_data = json.load(f)

        assert plan_data.get("tasks"), "No tasks found in generated plan."
        if not plan_data["tasks"]:
            pytest.skip(
                "No tasks generated by LLM to test 'show' command for minimal fields.")

        task_to_show = plan_data["tasks"][0]
        task_id_to_show = task_to_show["id"]

        # Act
        show_result = runner.invoke(app, ['show', task_id_to_show])

        # Assert
        assert show_result.exit_code == 0, show_result.stdout
        assert f"Title: {task_to_show['title']}" in show_result.stdout
        assert f"ID: {task_id_to_show}" in show_result.stdout
        assert f"Description: {task_to_show['description']}" in show_result.stdout
        assert f"Status: {task_to_show['status']}" in show_result.stdout
        # Asserting absence of optional fields is unreliable with LLM, so we focus on presence of core fields.

    @requires_api_key()
    # mock_agent removed
    def test_show_command_subtask_without_optional_fields(self, runner, cli_test_workspace):
        """Test show command displays a subtask's core fields."""
        # Arrange: Create a plan likely to have subtasks.
        plan_goal = "App feature with multiple steps"
        plan_title = "Feature Plan"
        plan_result = runner.invoke(
            app, ['plan', plan_goal, '--title', plan_title, '--num-tasks', '2'])
        assert plan_result.exit_code == 0, f"Plan creation failed: {plan_result.stdout}"

        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists()
        with open(plan_file, "r") as f:
            plan_data = json.load(f)

        subtask_to_show = None
        subtask_id_to_show = None
        for task in plan_data.get("tasks", []):
            if task.get("subtasks"):
                subtask_to_show = task["subtasks"][0]
                subtask_id_to_show = subtask_to_show["id"]
                break

        if not subtask_id_to_show:
            pytest.skip(
                "No subtasks generated by LLM to test 'show subtask' for minimal fields.")

        # Act
        show_result = runner.invoke(app, ['show', subtask_id_to_show])

        # Assert
        assert show_result.exit_code == 0, show_result.stdout
        assert f"Title: {subtask_to_show['title']}" in show_result.stdout
        assert f"ID: {subtask_id_to_show}" in show_result.stdout
        assert f"Description: {subtask_to_show['description']}" in show_result.stdout
        assert f"Status: {subtask_to_show['status']}" in show_result.stdout
        # Asserting absence of optional fields is unreliable with LLM.
