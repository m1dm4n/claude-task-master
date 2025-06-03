"""CLI tests for Phase 9: Adding New Tasks (AI-driven)."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime, timezone

from typer.testing import CliRunner
from src.cli.main import app
from src.data_models import Task, TaskStatus, TaskPriority, ProjectPlan
from tests.cli.conftest import setup_project_plan_file, load_project_plan_file # Import helper functions


class TestAddTaskCommand:
    """Test the add-task CLI command."""

    @pytest.fixture
    def runner(self):
        """CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def sample_task(self):
        """Sample task for testing."""
        return Task(
            id=uuid4(),
            title="Implement user authentication",
            description="Create a secure user authentication system with login and registration",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            details="Use JWT tokens for session management and bcrypt for password hashing",
            testStrategy="Unit tests for auth functions, integration tests for auth flow",
            dependencies=[],
            subtasks=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

    @pytest.fixture
    def sample_project_plan(self):
        """Sample project plan for testing."""
        return ProjectPlan(
            id=uuid4(),
            project_title="Test Project",
            overall_goal="Build a web application",
            tasks=[]
        )

    def test_add_task_command_success(self, runner, cli_test_workspace, sample_task, sample_project_plan):
        """Test successful add-task command execution."""
        workspace_path = cli_test_workspace
        
        with patch('src.cli.utils.DevTaskAIAssistant') as mock_agent_class:
            # Mock the agent instance
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            
            # Mock the add_new_task method to return our sample task
            async def mock_add_new_task(*args, **kwargs):
                # Add the task to the sample plan for persistence verification
                sample_project_plan.tasks.append(sample_task)
                return sample_task
            
            mock_agent.add_new_task = mock_add_new_task
            mock_agent.get_current_project_plan.return_value = sample_project_plan
            
            # Run the command
            result = runner.invoke(app, [
                "--workspace", str(workspace_path),
                "add-task",
                "Create user authentication system",
                "--priority", "high"
            ])
            
            # Verify the command succeeded
            assert result.exit_code == 0
            assert "Successfully added new task" in result.stdout
            assert "Implement user authentication" in result.stdout
            assert "Priority: HIGH" in result.stdout
            assert "Status: PENDING" in result.stdout
            
            # Verify the agent was called correctly
            mock_agent_class.assert_called_once_with(str(workspace_path))

    def test_add_task_command_with_dependencies_and_priority(self, runner, cli_test_workspace, sample_task, sample_project_plan):
        """Test add-task command with dependencies and priority options."""
        workspace_path = cli_test_workspace
        
        # Create dependency UUIDs
        dep1_uuid = uuid4()
        dep2_uuid = uuid4()
        
        # Update sample task to include the dependencies
        sample_task.dependencies = [dep1_uuid, dep2_uuid]
        sample_task.priority = TaskPriority.CRITICAL
        
        with patch('src.cli.utils.DevTaskAIAssistant') as mock_agent_class:
            # Mock the agent instance
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            
            # Mock the add_new_task method
            async def mock_add_new_task(*args, **kwargs):
                # Verify the correct parameters were passed
                assert kwargs.get('dependencies_str') == [str(dep1_uuid), str(dep2_uuid)]
                assert kwargs.get('priority_str') == "critical"
                assert kwargs.get('use_research') == True
                return sample_task
            
            mock_agent.add_new_task = mock_add_new_task
            
            # Run the command with dependencies and research flag
            result = runner.invoke(app, [
                "--workspace", str(workspace_path),
                "add-task",
                "Create user dashboard",
                "--dep", str(dep1_uuid),
                "--dep", str(dep2_uuid),
                "--priority", "critical",
                "--research"
            ])
            
            # Verify the command succeeded
            assert result.exit_code == 0
            assert "Successfully added new task" in result.stdout
            assert "Priority: CRITICAL" in result.stdout
            assert f"Dependencies: {dep1_uuid}, {dep2_uuid}" in result.stdout

    def test_add_task_command_with_subtasks(self, runner, cli_test_workspace, sample_project_plan):
        """Test add-task command when the generated task includes subtasks."""
        workspace_path = cli_test_workspace
        
        # Create a task with subtasks
        from src.data_models import Subtask
        subtask1 = Subtask(
            id=uuid4(),
            title="Design API endpoints",
            description="Define authentication API routes",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        subtask2 = Subtask(
            id=uuid4(),
            title="Implement password hashing",
            description="Add bcrypt password hashing",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        task_with_subtasks = Task(
            id=uuid4(),
            title="Implement user authentication",
            description="Create a secure user authentication system",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            details="Implementation details for auth system",
            testStrategy="Testing strategy for auth system",
            subtasks=[subtask1, subtask2],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        with patch('src.cli.utils.DevTaskAIAssistant') as mock_agent_class:
            # Mock the agent instance
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            
            # Mock the add_new_task method
            async def mock_add_new_task(*args, **kwargs):
                return task_with_subtasks
            
            mock_agent.add_new_task = mock_add_new_task
            
            # Run the command
            result = runner.invoke(app, [
                "--workspace", str(workspace_path),
                "add-task",
                "Create comprehensive authentication system"
            ])
            
            # Verify the command succeeded and shows subtasks
            assert result.exit_code == 0
            assert "Successfully added new task" in result.stdout
            assert "Generated 2 initial subtasks:" in result.stdout
            assert "1. Design API endpoints" in result.stdout
            assert "2. Implement password hashing" in result.stdout
            assert "Details: Implementation details for auth system" in result.stdout
            assert "Test Strategy: Testing strategy for auth system" in result.stdout

    def test_add_task_command_llm_failure(self, runner, cli_test_workspace, sample_project_plan):
        """Test add-task command when LLM generation fails."""
        workspace_path = cli_test_workspace
        
        with patch('src.cli.utils.DevTaskAIAssistant') as mock_agent_class:
            # Mock the agent instance
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            
            # Mock the add_new_task method to return None (failure)
            async def mock_add_new_task(*args, **kwargs):
                return None
            
            mock_agent.add_new_task = mock_add_new_task
            
            # Run the command
            result = runner.invoke(app, [
                "--workspace", str(workspace_path),
                "add-task",
                "Create user authentication system"
            ])
            
            # Verify the command failed gracefully
            assert result.exit_code == 1
            assert "Failed to add new task" in result.stdout

    def test_add_task_command_invalid_dependency_id(self, runner, cli_test_workspace):
        """Test add-task command with invalid dependency ID format."""
        workspace_path = cli_test_workspace
        
        # Run the command with invalid dependency ID
        result = runner.invoke(app, [
            "--workspace", str(workspace_path),
            "add-task",
            "Create user authentication system",
            "--dep", "invalid-uuid-format"
        ])
        
        # Verify the command failed with appropriate error
        assert result.exit_code == 1
        assert "Invalid dependency ID format" in result.stdout

    def test_add_task_command_invalid_priority(self, runner, cli_test_workspace):
        """Test add-task command with invalid priority."""
        workspace_path = cli_test_workspace
        
        # Run the command with invalid priority
        result = runner.invoke(app, [
            "--workspace", str(workspace_path),
            "add-task",
            "Create user authentication system",
            "--priority", "invalid_priority"
        ])
        
        # Verify the command failed with appropriate error
        assert result.exit_code == 1
        assert "Invalid priority" in result.stdout
        assert "Valid priorities are:" in result.stdout

    def test_add_task_command_with_research_model(self, runner, cli_test_workspace, sample_task, sample_project_plan):
        """Test add-task command using the research model."""
        workspace_path = cli_test_workspace
        
        with patch('src.cli.utils.DevTaskAIAssistant') as mock_agent_class:
            # Mock the agent instance
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            
            # Mock the add_new_task method
            async def mock_add_new_task(*args, **kwargs):
                # Verify research model is requested
                assert kwargs.get('use_research') == True
                return sample_task
            
            mock_agent.add_new_task = mock_add_new_task
            
            # Run the command with research flag
            result = runner.invoke(app, [
                "--workspace", str(workspace_path),
                "add-task",
                "Research and implement advanced authentication features",
                "--research"
            ])
            
            # Verify the command succeeded
            assert result.exit_code == 0
            assert "Successfully added new task" in result.stdout
            assert "research model" in result.stdout

    def test_add_task_command_help(self, runner):
        """Test add-task command help output."""
        result = runner.invoke(app, ["add-task", "--help"])
        
        assert result.exit_code == 0
        assert "Add a new task to the project using AI-driven task generation" in result.stdout
        assert "--dep" in result.stdout
        assert "--priority" in result.stdout
        assert "--research" in result.stdout

    def test_add_task_command_exception_handling(self, runner, cli_test_workspace):
        """Test add-task command handles unexpected exceptions."""
        workspace_path = cli_test_workspace
        
        with patch('src.cli.utils.DevTaskAIAssistant') as mock_agent_class:
            # Mock the agent to raise an exception
            mock_agent_class.side_effect = Exception("Unexpected error")
            
            # Run the command
            result = runner.invoke(app, [
                "--workspace", str(workspace_path),
                "add-task",
                "Create user authentication system"
            ])
            
            # Verify the command failed gracefully
            assert result.exit_code == 1
            assert "An unexpected error occurred" in result.stdout

    def test_add_task_command_multiple_dependencies(self, runner, cli_test_workspace, sample_task, sample_project_plan):
        """Test add-task command with multiple dependencies using --dep multiple times."""
        workspace_path = cli_test_workspace
        
        # Create multiple dependency UUIDs
        dep1_uuid = uuid4()
        dep2_uuid = uuid4()
        dep3_uuid = uuid4()
        
        sample_task.dependencies = [dep1_uuid, dep2_uuid, dep3_uuid]
        
        with patch('src.cli.utils.DevTaskAIAssistant') as mock_agent_class:
            # Mock the agent instance
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            
            # Mock the add_new_task method
            async def mock_add_new_task(*args, **kwargs):
                # Verify all dependencies were passed
                expected_deps = [str(dep1_uuid), str(dep2_uuid), str(dep3_uuid)]
                assert kwargs.get('dependencies_str') == expected_deps
                return sample_task
            
            mock_agent.add_new_task = mock_add_new_task
            
            # Run the command with multiple --dep flags
            result = runner.invoke(app, [
                "--workspace", str(workspace_path),
                "add-task",
                "Create complex feature depending on multiple tasks",
                "--dep", str(dep1_uuid),
                "--dep", str(dep2_uuid),
                "--dep", str(dep3_uuid)
            ])
            
            # Verify the command succeeded
            assert result.exit_code == 0
            assert "Successfully added new task" in result.stdout
            assert f"Dependencies: {dep1_uuid}, {dep2_uuid}, {dep3_uuid}" in result.stdout