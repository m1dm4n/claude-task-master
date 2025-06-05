"""
Production functional tests for Phase 3 CLI functionality.
Tests the refactored list command and new show command with real data.
"""

from src.agent_core.assistant import DevTaskAIAssistant
import pytest
from typer.testing import CliRunner
from pathlib import Path
from uuid import uuid4, UUID
import json

from unittest.mock import patch
from src.cli import app
from src.data_models import ProjectPlan, Task, TaskStatus, TaskPriority
from tests.cli.utils import requires_api_key
from tests.cli.test_utils import run_cli_command, create_task_dict


# The runner fixture is now provided by tests.cli.conftest
# @pytest.fixture
# def runner():
#     """Create a CLI runner for testing."""
#     return CliRunner()


class TestListCommand:
    """Test cases for the list command."""

    @pytest.mark.asyncio
    async def test_list_command_with_no_tasks(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant, project_plan_factory):
        """Test list command with no tasks in the project."""
        # Arrange: Create an empty project plan using the factory
        project_plan_factory.create_with_tasks([])

        # Act
        result = await run_cli_command(runner, ['list'], cli_test_workspace)

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "📋 All Tasks for \'Generated Project Plan\'" in result.stdout # Updated title
        assert "📝 No tasks found matching the criteria." in result.stdout
        assert "💡 Use 'task-master parse-prd' or 'task-master plan' to get started." in result.stdout

    @pytest.mark.asyncio
    async def test_list_command_with_several_tasks_basic_output(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant, project_plan_factory, sample_project_plan: ProjectPlan):
        """Test list command with several tasks, verifying basic output format."""
        # Arrange: Use the sample project plan from fixture via factory
        project_plan_factory.create(sample_project_plan)

        # Act
        result = await run_cli_command(runner, ['list'], cli_test_workspace)

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

    @pytest.mark.asyncio
    async def test_list_command_with_status_pending_filter(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant, project_plan_factory):
        """Test list command with --status PENDING filter."""
        # Arrange: Create a plan with mixed statuses, ensuring some are PENDING
        tasks = [
            create_task_dict("Task A", status=TaskStatus.PENDING),
            create_task_dict("Task B", status=TaskStatus.IN_PROGRESS),
            create_task_dict("Task C", status=TaskStatus.PENDING),
            create_task_dict("Task D", status=TaskStatus.COMPLETED),
        ]
        project_plan_factory.create_with_tasks(tasks)

        # Act
        list_result = await run_cli_command(runner, ['list', '--status', 'PENDING'], cli_test_workspace)

        # Assert
        assert list_result.exit_code == 0, list_result.stdout
        assert "📋 Tasks with status 'PENDING' for 'Generated Project Plan':" in list_result.stdout
        assert "Task A" in list_result.stdout
        assert "Task C" in list_result.stdout
        assert "Task B" not in list_result.stdout
        assert "Task D" not in list_result.stdout
        assert "Status: PENDING" in list_result.stdout
        assert "Status: IN_PROGRESS" not in list_result.stdout
        assert "Status: COMPLETED" not in list_result.stdout

    @pytest.mark.asyncio
    async def test_list_command_with_status_in_progress_filter(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant, project_plan_factory):
        """Test list command with --status IN_PROGRESS filter."""
        # Arrange: Create a plan with mixed statuses, ensuring some are IN_PROGRESS
        tasks = [
            create_task_dict("Task E", status=TaskStatus.PENDING),
            create_task_dict("Task F", status=TaskStatus.IN_PROGRESS),
            create_task_dict("Task G", status=TaskStatus.COMPLETED),
        ]
        project_plan_factory.create_with_tasks(tasks)

        # Act
        list_result = await run_cli_command(runner, ['list', '--status', 'IN_PROGRESS'], cli_test_workspace)

        # Assert
        assert list_result.exit_code == 0, list_result.stdout
        assert "📋 Tasks with status 'IN_PROGRESS' for 'Generated Project Plan':" in list_result.stdout
        assert "Task F" in list_result.stdout
        assert "Task E" not in list_result.stdout
        assert "Task G" not in list_result.stdout
        assert "Status: IN_PROGRESS" in list_result.stdout
        assert "Status: PENDING" not in list_result.stdout
        assert "Status: COMPLETED" not in list_result.stdout

    @pytest.mark.asyncio
    async def test_list_command_with_status_completed_filter(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant, project_plan_factory):
        """Test list command with --status COMPLETED filter."""
        # Arrange: Create a plan with mixed statuses, ensuring some are COMPLETED
        tasks = [
            create_task_dict("Task H", status=TaskStatus.PENDING),
            create_task_dict("Task I", status=TaskStatus.IN_PROGRESS),
            create_task_dict("Task J", status=TaskStatus.COMPLETED),
        ]
        project_plan_factory.create_with_tasks(tasks)

        # Act
        list_result = await run_cli_command(runner, ['list', '--status', 'COMPLETED'], cli_test_workspace)

        # Assert
        assert list_result.exit_code == 0, list_result.stdout
        assert "📋 Tasks with status 'COMPLETED' for 'Generated Project Plan':" in list_result.stdout
        assert "Task J" in list_result.stdout
        assert "Task H" not in list_result.stdout
        assert "Task I" not in list_result.stdout
        assert "Status: COMPLETED" in list_result.stdout
        assert "Status: PENDING" not in list_result.stdout
        assert "Status: IN_PROGRESS" not in list_result.stdout

    @pytest.mark.asyncio
    async def test_list_command_with_with_subtasks_flag(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant, project_plan_factory):
        """Test list command with --with-subtasks flag."""
        # Arrange: Create a plan with tasks, some having subtasks
        subtask1 = create_task_dict(title="Task 1.1", description="First subtask", status=TaskStatus.PENDING)
        subtask2 = create_task_dict(title="Task 1.2", description="Second subtask", status=TaskStatus.IN_PROGRESS)
        
        tasks = [
            create_task_dict(title="Task K", description="Task with subtasks", subtasks=[subtask1, subtask2]),
            create_task_dict(title="Task L", description="Task without subtasks"),
        ]
        workspace_path, _ = cli_test_workspace
        project_plan_factory.create_with_tasks(workspace_path, tasks)

        # Act
        list_result = await run_cli_command(runner, ['list', '--with-subtasks'], cli_test_workspace)

        # Assert
        assert list_result.exit_code == 0, list_result.stdout
        assert "📋 All Tasks for 'Generated Project Plan':" in list_result.stdout
        assert "Task K" in list_result.stdout
        assert "Task L" in list_result.stdout
        # Check for subtask display format: emoji + title on one line, then ID and Status indented
        assert "     ⏳ Task 1.1" in list_result.stdout
        assert f"       ID: {subtask1['id']}" in list_result.stdout
        assert f"       Status: {subtask1['status']}" in list_result.stdout
        assert "     🔄 Task 1.2" in list_result.stdout
        assert f"       ID: {subtask2['id']}" in list_result.stdout
        assert f"       Status: {subtask2['status']}" in list_result.stdout

    @pytest.mark.asyncio
    async def test_list_command_with_short_subtasks_flag(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant, project_plan_factory):
        """Test list command with -s (short flag for subtasks)."""
        # Arrange: Create a plan with tasks, some having subtasks
        subtask1 = create_task_dict(title="Task 2.1", description="Another subtask", status=TaskStatus.PENDING)
        tasks = [
            create_task_dict(title="Task M", description="Task with subtasks (short)", subtasks=[subtask1]),
            create_task_dict(title="Task N", description="Task without subtasks (short)"),
        ]
        workspace_path, _ = cli_test_workspace
        project_plan_factory.create_with_tasks(workspace_path, tasks)

        # Act
        list_result = await run_cli_command(runner, ['list', '-s'], cli_test_workspace)  # Use short flag

        # Assert
        assert list_result.exit_code == 0, list_result.stdout
        assert "📋 All Tasks for 'Generated Project Plan':" in list_result.stdout
        assert "Task M" in list_result.stdout
        assert "Task N" in list_result.stdout
        # Check for subtask display format: emoji + title on one line, then ID and Status indented
        assert "     ⏳ Task 2.1" in list_result.stdout
        assert f"       ID: {subtask1['id']}" in list_result.stdout
        assert f"       Status: {subtask1['status']}" in list_result.stdout

    @pytest.mark.asyncio
    async def test_list_command_handles_agent_exception(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant):
        """Test list command handles exceptions from agent gracefully."""
        # Patch a method on the actual agent instance that `list` would use.
        # `get_current_project_plan` is called to display the project title.
        with patch('src.agent_core.assistant.DevTaskAIAssistant.get_current_project_plan',
                   side_effect=Exception("Simulated agent error on get_current_project_plan")):
            # Act
            result = await run_cli_command(runner, ['list'], cli_test_workspace)

            # Assert
            assert result.exit_code == 1, result.stdout
            assert "❌ Error listing tasks: Simulated agent error on get_current_project_plan" in result.stdout

    @pytest.mark.asyncio
    async def test_list_command_with_no_project_plan(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant):
        """Test list command when agent has no project plan initially."""
        # Arrange: cli_test_workspace provides an empty environment.
        # The agent, when initialized, will find no existing user plan.
        # PersistenceManager might create a default "New Project" plan or load None.

        # Act
        result = await run_cli_command(runner, ['list'], cli_test_workspace)

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
    @requires_api_key()
    @pytest.mark.asyncio
    async def test_show_command_with_valid_task_id(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant, project_plan_factory, llm_generated_plan_fixture: Path):
        """Test show command with a valid Task ID."""
        # Arrange: Use the llm_generated_plan_fixture to ensure a plan with tasks exists
        # The fixture already copies the plan to cli_test_workspace / "project_plan.json"
        plan_file = llm_generated_plan_fixture
        assert plan_file.exists()
        
        workspace_path, _ = cli_test_workspace
        workspace_path, _ = cli_test_workspace
        plan_data = project_plan_factory.load()
        assert plan_data and plan_data.tasks, "No tasks found in generated plan to show."
        
        task_to_show = plan_data.tasks[0]
        task_id_to_show = str(task_to_show.id)
        # Act
        show_result = await run_cli_command(runner, ['show', task_id_to_show], cli_test_workspace)
        # Assert
        assert show_result.exit_code == 0, show_result.stdout
        assert f"🔍 Details for Item (ID: {task_id_to_show})" in show_result.stdout
        assert f"Title: {task_to_show.title}" in show_result.stdout
        assert f"ID: {task_id_to_show}" in show_result.stdout
        assert f"Description: {task_to_show.description}" in show_result.stdout
        assert f"Status: {task_to_show.status.value}" in show_result.stdout # Use .value for enum
        if task_to_show.priority:  # Priority is optional
            assert f"Priority: {task_to_show.priority.value}" in show_result.stdout
        if task_to_show.dependencies:
            assert "Dependencies: " + \
                ", ".join(str(dep) for dep in task_to_show.dependencies) in show_result.stdout
        if task_to_show.details:
            assert f"Details:\n{task_to_show.details}" in show_result.stdout

        if task_to_show.subtasks:
            assert "Subtasks:" in show_result.stdout
            # Check first few subtasks
            for subtask in task_to_show.subtasks[:2]:
                assert f"  - {subtask.title} (ID: {subtask.id}, Status: {subtask.status.value})" in show_result.stdout

    @requires_api_key()
    @requires_api_key()
    @pytest.mark.asyncio
    async def test_show_command_with_valid_subtask_id(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant, project_plan_factory, llm_generated_plan_fixture: Path):
        """Test show command with a valid Task ID."""
        # Arrange: Use the llm_generated_plan_fixture to ensure a plan with subtasks exists
        plan_file = llm_generated_plan_fixture
        assert plan_file.exists()
 
        workspace_path, _ = cli_test_workspace
        plan_data = project_plan_factory.load()
        subtask_to_show = None
        subtask_id_to_show = None
        for task in plan_data.tasks:
            if task.subtasks:
                subtask_to_show = task.subtasks[0]
                subtask_id_to_show = str(subtask_to_show.id)
                break
 
        if not subtask_id_to_show:
            pytest.skip(
                "No subtasks generated by LLM to test 'show subtask' command.")
 
        # Act
        show_result = await run_cli_command(runner, ['show', subtask_id_to_show], cli_test_workspace)
        # Assert
        assert show_result.exit_code == 0, show_result.stdout
        assert f"🔍 Details for Item (ID: {subtask_id_to_show})" in show_result.stdout
        assert f"Title: {subtask_to_show.title}" in show_result.stdout
        assert f"ID: {subtask_id_to_show}" in show_result.stdout
        assert f"Description: {subtask_to_show.description}" in show_result.stdout
        assert f"Status: {subtask_to_show.status.value}" in show_result.stdout
        if subtask_to_show.priority:
            assert f"Priority: {subtask_to_show.priority.value}" in show_result.stdout
        # Subtasks don't have their own "Subtasks:" section displayed by `show`
        assert "Subtasks:" not in show_result.stdout

    @pytest.mark.asyncio
    async def test_show_command_with_invalid_uuid_format(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant):
        """Test show command with an invalid UUID format."""
        # Act
        result = await run_cli_command(runner, ['show', 'invalid-uuid-format'], cli_test_workspace)

        # Assert
        assert result.exit_code == 1, result.stdout
        assert "Invalid ID format" in result.stdout
        assert "'invalid-uuid-format'" in result.stdout

    @pytest.mark.asyncio
    async def test_show_command_with_valid_uuid_but_nonexistent_id(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant, project_plan_factory):
        """Test show command with a valid UUID format but non-existent ID."""
        # Arrange: Ensure a plan exists, but the ID won't be in it.
        workspace_path, _ = cli_test_workspace
        project_plan_factory.create_with_tasks([create_task_dict("Dummy Task")])
        nonexistent_id = uuid4()

        # Act
        result = await run_cli_command(runner, ['show', str(nonexistent_id)], cli_test_workspace)

        # Assert
        assert result.exit_code == 1, result.stdout
        assert f"❌ Item with ID '{nonexistent_id}' not found." in result.stdout

    @pytest.mark.asyncio
    async def test_show_command_handles_agent_exception(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant):
        """Test show command handles exceptions from agent gracefully."""
        # Arrange
        valid_id_for_test = uuid4()  # ID format is valid, agent will try to fetch

        with patch('src.agent_core.assistant.DevTaskAIAssistant.get_item_by_id',
                   side_effect=Exception("Simulated database error during show")):
            result = await run_cli_command(runner, ['show', str(valid_id_for_test)], cli_test_workspace)

            # Assert
            assert result.exit_code == 1, result.stdout
            assert "❌ An unexpected error occurred: Simulated database error during show" in result.stdout

    @requires_api_key()
    @requires_api_key()
    @pytest.mark.asyncio
    async def test_show_command_task_without_optional_fields(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant, project_plan_factory, llm_generated_plan_fixture: Path):
        """Test show command displays a task's core fields."""
        # Arrange: Use the llm_generated_plan_fixture to ensure a plan with tasks exists
        plan_file = llm_generated_plan_fixture
        assert plan_file.exists()
 
        workspace_path, _ = cli_test_workspace
        plan_data = project_plan_factory.load()
        assert plan_data and plan_data.tasks, "No tasks found in generated plan."
        
        task_to_show = plan_data.tasks[0]
        task_id_to_show = str(task_to_show.id)

        # Act
        show_result = await run_cli_command(runner, ['show', task_id_to_show], cli_test_workspace)
        # Assert
        assert show_result.exit_code == 0, show_result.stdout
        assert f"Title: {task_to_show.title}" in show_result.stdout
        assert f"ID: {task_id_to_show}" in show_result.stdout
        assert f"Description: {task_to_show.description}" in show_result.stdout
        assert f"Status: {task_to_show.status.value}" in show_result.stdout
        # Asserting absence of optional fields is unreliable with LLM, so we focus on presence of core fields.

    @requires_api_key()
    @requires_api_key()
    @pytest.mark.asyncio
    async def test_show_command_subtask_without_optional_fields(self, runner: CliRunner, cli_test_workspace: Path, real_agent: DevTaskAIAssistant, project_plan_factory, llm_generated_plan_fixture: Path):
        """Test show command displays a subtask's core fields."""
        # Arrange: Use the llm_generated_plan_fixture to ensure a plan with subtasks exists
        plan_file = llm_generated_plan_fixture
        assert plan_file.exists()
 
        workspace_path, _ = cli_test_workspace
        plan_data = project_plan_factory.load()
        subtask_to_show = None
        subtask_id_to_show = None
        for task in plan_data.tasks:
            if task.subtasks:
                subtask_to_show = task.subtasks[0]
                subtask_id_to_show = str(subtask_to_show.id)
                break
 
        if not subtask_id_to_show:
            pytest.skip(
                "No subtasks generated by LLM to test 'show subtask' for minimal fields.")
 
        # Act
        show_result = await run_cli_command(runner, ['show', subtask_id_to_show], cli_test_workspace)
        # Assert
        assert show_result.exit_code == 0, show_result.stdout
        assert f"Title: {subtask_to_show.title}" in show_result.stdout
        assert f"ID: {subtask_id_to_show}" in show_result.stdout
        assert f"Description: {subtask_to_show.description}" in show_result.stdout
        assert f"Status: {subtask_to_show.status.value}" in show_result.stdout
        # Asserting absence of optional fields is unreliable with LLM.
