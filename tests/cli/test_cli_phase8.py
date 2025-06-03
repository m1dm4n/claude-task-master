"""CLI tests for Phase 8: Single Task/Subtask Refinement commands."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from typer.testing import CliRunner

from src.cli.main import app
from src.data_models import Task, Subtask, TaskStatus, TaskPriority, ProjectPlan


class TestUpdateTaskCommand:
    """Test the update-task CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def cli_test_workspace(self, tmp_path):
        """Create a temporary workspace for CLI testing."""
        workspace = tmp_path / "test_workspace"
        workspace.mkdir()
        
        # Create a basic project plan
        project_plan = ProjectPlan(
            project_title="Test Project",
            overall_goal="Test project for CLI testing",
            tasks=[]
        )
        
        # Write project plan file
        project_plan_file = workspace / "project_plan.json"
        with open(project_plan_file, 'w') as f:
            f.write(project_plan.model_dump_json(indent=2))
        
        return str(workspace)

    def test_update_task_command_success(self, runner, cli_test_workspace, mocker):
        """Test successful task update via CLI."""
        # Arrange
        task_id = uuid4()
        original_task = Task(
            id=task_id,
            title="Original Task",
            description="Original description",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM
        )
        
        updated_task = Task(
            id=task_id,
            title="Updated Task",
            description="Updated description with refinements",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            details="Added implementation details",
            created_at=original_task.created_at,
            updated_at=datetime.now(timezone.utc)
        )
        
        # Mock the agent and its methods
        mock_agent = MagicMock()
        mock_agent.get_item_by_id.return_value = original_task
        mock_agent.refine_task_or_subtask = AsyncMock(return_value=updated_task)
        
        # Mock the get_agent function
        mocker.patch('src.cli.tasks.get_agent', return_value=mock_agent)
        
        # Act
        result = runner.invoke(app, [
            "--workspace", cli_test_workspace,
            "update-task",
            str(task_id),
            "Change priority to HIGH and add implementation details",
            "--research"
        ])
        
        # Assert
        assert result.exit_code == 0
        assert "Successfully updated task 'Updated Task'" in result.stdout
        assert "Updated Task Details:" in result.stdout
        assert "Title: Updated Task" in result.stdout
        assert "Priority: HIGH" in result.stdout
        assert "Status: IN_PROGRESS" in result.stdout
        assert "Details: Added implementation details" in result.stdout
        
        # Verify the agent methods were called correctly
        mock_agent.get_item_by_id.assert_called_once_with(task_id)
        mock_agent.refine_task_or_subtask.assert_called_once_with(
            task_id, "Change priority to HIGH and add implementation details", use_research=True
        )

    def test_update_task_command_task_not_found(self, runner, cli_test_workspace, mocker):
        """Test update-task command when task is not found."""
        # Arrange
        task_id = uuid4()
        
        # Mock the agent to return None for the task
        mock_agent = MagicMock()
        mock_agent.get_item_by_id.return_value = None
        
        mocker.patch('src.cli.tasks.get_agent', return_value=mock_agent)
        
        # Act
        result = runner.invoke(app, [
            "--workspace", cli_test_workspace,
            "update-task",
            str(task_id),
            "This task doesn't exist"
        ])
        
        # Assert
        assert result.exit_code == 1
        assert f"Task with ID '{task_id}' not found" in result.stdout

    def test_update_task_command_invalid_uuid(self, runner, cli_test_workspace):
        """Test update-task command with invalid UUID."""
        # Act
        result = runner.invoke(app, [
            "--workspace", cli_test_workspace,
            "update-task",
            "invalid-uuid",
            "Some refinement instruction"
        ])
        
        # Assert
        assert result.exit_code == 1
        assert "Invalid task ID format" in result.stdout

    def test_update_task_command_item_is_subtask(self, runner, cli_test_workspace, mocker):
        """Test update-task command when the item is actually a subtask."""
        # Arrange
        subtask_id = uuid4()
        subtask = Subtask(
            id=subtask_id,
            title="This is a subtask",
            description="Not a task",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM
        )
        
        # Mock the agent to return a subtask instead of a task
        mock_agent = MagicMock()
        mock_agent.get_item_by_id.return_value = subtask
        
        mocker.patch('src.cli.tasks.get_agent', return_value=mock_agent)
        
        # Act
        result = runner.invoke(app, [
            "--workspace", cli_test_workspace,
            "update-task",
            str(subtask_id),
            "Try to update a subtask as task"
        ])
        
        # Assert
        assert result.exit_code == 1
        assert "is not a task. Use 'update-subtask' for subtasks" in result.stdout

    def test_update_task_command_refinement_fails(self, runner, cli_test_workspace, mocker):
        """Test update-task command when refinement fails."""
        # Arrange
        task_id = uuid4()
        original_task = Task(
            id=task_id,
            title="Original Task",
            description="Original description",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM
        )
        
        # Mock the agent
        mock_agent = MagicMock()
        mock_agent.get_item_by_id.return_value = original_task
        mock_agent.refine_task_or_subtask = AsyncMock(return_value=None)  # Refinement fails
        
        mocker.patch('src.cli.tasks.get_agent', return_value=mock_agent)
        
        # Act
        result = runner.invoke(app, [
            "--workspace", cli_test_workspace,
            "update-task",
            str(task_id),
            "This refinement will fail"
        ])
        
        # Assert
        assert result.exit_code == 1
        assert "Failed to update task" in result.stdout


class TestUpdateSubtaskCommand:
    """Test the update-subtask CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def cli_test_workspace(self, tmp_path):
        """Create a temporary workspace for CLI testing."""
        workspace = tmp_path / "test_workspace"
        workspace.mkdir()
        
        # Create a basic project plan
        project_plan = ProjectPlan(
            project_title="Test Project",
            overall_goal="Test project for CLI testing",
            tasks=[]
        )
        
        # Write project plan file
        project_plan_file = workspace / "project_plan.json"
        with open(project_plan_file, 'w') as f:
            f.write(project_plan.model_dump_json(indent=2))
        
        return str(workspace)

    def test_update_subtask_command_success(self, runner, cli_test_workspace, mocker):
        """Test successful subtask update via CLI."""
        # Arrange
        subtask_id = uuid4()
        original_subtask = Subtask(
            id=subtask_id,
            title="Original Subtask",
            description="Original subtask description",
            status=TaskStatus.PENDING,
            priority=TaskPriority.LOW
        )
        
        updated_subtask = Subtask(
            id=subtask_id,
            title="Updated Subtask",
            description="Updated subtask description",
            status=TaskStatus.COMPLETED,
            priority=TaskPriority.MEDIUM,
            testStrategy="Added test strategy",
            created_at=original_subtask.created_at,
            updated_at=datetime.now(timezone.utc)
        )
        
        # Mock the agent and its methods
        mock_agent = MagicMock()
        mock_agent.get_item_by_id.return_value = original_subtask
        mock_agent.refine_task_or_subtask = AsyncMock(return_value=updated_subtask)
        
        # Mock the get_agent function
        mocker.patch('src.cli.tasks.get_agent', return_value=mock_agent)
        
        # Act
        result = runner.invoke(app, [
            "--workspace", cli_test_workspace,
            "update-subtask",
            str(subtask_id),
            "Mark as completed and add test strategy"
        ])
        
        # Assert
        assert result.exit_code == 0
        assert "Successfully updated subtask 'Updated Subtask'" in result.stdout
        assert "Updated Subtask Details:" in result.stdout
        assert "Title: Updated Subtask" in result.stdout
        assert "Priority: MEDIUM" in result.stdout
        assert "Status: COMPLETED" in result.stdout
        assert "Test Strategy: Added test strategy" in result.stdout
        
        # Verify the agent methods were called correctly
        mock_agent.get_item_by_id.assert_called_once_with(subtask_id)
        mock_agent.refine_task_or_subtask.assert_called_once_with(
            subtask_id, "Mark as completed and add test strategy", use_research=False
        )

    def test_update_subtask_command_subtask_not_found(self, runner, cli_test_workspace, mocker):
        """Test update-subtask command when subtask is not found."""
        # Arrange
        subtask_id = uuid4()
        
        # Mock the agent to return None for the subtask
        mock_agent = MagicMock()
        mock_agent.get_item_by_id.return_value = None
        
        mocker.patch('src.cli.tasks.get_agent', return_value=mock_agent)
        
        # Act
        result = runner.invoke(app, [
            "--workspace", cli_test_workspace,
            "update-subtask",
            str(subtask_id),
            "This subtask doesn't exist"
        ])
        
        # Assert
        assert result.exit_code == 1
        assert f"Subtask with ID '{subtask_id}' not found" in result.stdout

    def test_update_subtask_command_invalid_uuid(self, runner, cli_test_workspace):
        """Test update-subtask command with invalid UUID."""
        # Act
        result = runner.invoke(app, [
            "--workspace", cli_test_workspace,
            "update-subtask",
            "invalid-uuid",
            "Some refinement instruction"
        ])
        
        # Assert
        assert result.exit_code == 1
        assert "Invalid subtask ID format" in result.stdout

    def test_update_subtask_command_item_is_task(self, runner, cli_test_workspace, mocker):
        """Test update-subtask command when the item is actually a task."""
        # Arrange
        task_id = uuid4()
        task = Task(
            id=task_id,
            title="This is a task",
            description="Not a subtask",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM
        )
        
        # Mock the agent to return a task instead of a subtask
        mock_agent = MagicMock()
        mock_agent.get_item_by_id.return_value = task
        
        mocker.patch('src.cli.tasks.get_agent', return_value=mock_agent)
        
        # Act
        result = runner.invoke(app, [
            "--workspace", cli_test_workspace,
            "update-subtask",
            str(task_id),
            "Try to update a task as subtask"
        ])
        
        # Assert
        assert result.exit_code == 1
        assert "is not a subtask. Use 'update-task' for tasks" in result.stdout

    def test_update_subtask_command_with_research_model(self, runner, cli_test_workspace, mocker):
        """Test update-subtask command with research model flag."""
        # Arrange
        subtask_id = uuid4()
        original_subtask = Subtask(
            id=subtask_id,
            title="Research Subtask",
            description="Needs research-based refinement",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM
        )
        
        updated_subtask = Subtask(
            id=subtask_id,
            title="Research-Enhanced Subtask",
            description="Enhanced with research insights",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            created_at=original_subtask.created_at,
            updated_at=datetime.now(timezone.utc)
        )
        
        # Mock the agent
        mock_agent = MagicMock()
        mock_agent.get_item_by_id.return_value = original_subtask
        mock_agent.refine_task_or_subtask = AsyncMock(return_value=updated_subtask)
        
        mocker.patch('src.cli.tasks.get_agent', return_value=mock_agent)
        
        # Act
        result = runner.invoke(app, [
            "--workspace", cli_test_workspace,
            "update-subtask",
            str(subtask_id),
            "Enhance with research insights",
            "--research"
        ])
        
        # Assert
        assert result.exit_code == 0
        assert "Successfully updated subtask 'Research-Enhanced Subtask'" in result.stdout
        
        # Verify research flag was passed correctly
        mock_agent.refine_task_or_subtask.assert_called_once_with(
            subtask_id, "Enhance with research insights", use_research=True
        )