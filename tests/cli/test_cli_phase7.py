"""CLI tests for Phase 7: Subtask Management (Clearing) functionality."""

import pytest
import json
from uuid import uuid4, UUID
from pathlib import Path
from typer.testing import CliRunner

from src.cli.main import app
from src.data_models import Task, Subtask, TaskStatus, TaskPriority, ProjectPlan


@pytest.fixture
def runner():
    """Create a CliRunner for testing."""
    return CliRunner()


def create_project_plan_with_tasks(tasks):
    """Helper to create a ProjectPlan with given tasks."""
    return ProjectPlan(
        id=uuid4(),
        project_title="Test Project",
        overall_goal="Test project for CLI testing",
        tasks=tasks
    )


def setup_test_data(cli_test_workspace, project_plan):
    """Setup test data by saving the project plan directly to JSON file."""
    from src.data_models import ProjectPlan
    import json
    from pathlib import Path
    
    # Save project plan directly to JSON file
    project_plan_file = Path(cli_test_workspace) / "project_plan.json"
    with open(project_plan_file, 'w', encoding='utf-8') as f:
        f.write(project_plan.model_dump_json(indent=2, exclude_none=True))
    
    return None  # No agent needed anymore


def load_updated_project_plan(cli_test_workspace):
    """Load the updated project plan directly from JSON file."""
    from src.data_models import ProjectPlan
    import json
    from pathlib import Path
    
    # Load project plan directly from JSON file
    project_plan_file = Path(cli_test_workspace) / "project_plan.json"
    if project_plan_file.exists():
        with open(project_plan_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return ProjectPlan.model_validate(data)
    return None


class TestClearSubtasksCommand:
    """Test cases for the clear-subtasks CLI command."""

    def test_clear_subtasks_single_task_success(self, runner, cli_test_workspace):
        """Test clear-subtasks command for a single task with subtasks."""
        # Setup: Create task with subtasks
        subtasks = [
            Subtask(
                id=uuid4(),
                title="Subtask 1",
                description="First subtask to be cleared",
                status=TaskStatus.PENDING,
                priority=TaskPriority.HIGH
            ),
            Subtask(
                id=uuid4(),
                title="Subtask 2",
                description="Second subtask to be cleared",
                status=TaskStatus.PENDING,
                priority=TaskPriority.MEDIUM
            )
        ]
        
        task_with_subtasks = Task(
            id=uuid4(),
            title="Task with Subtasks",
            description="A task that has subtasks to clear",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
            subtasks=subtasks
        )
        
        initial_plan = create_project_plan_with_tasks([task_with_subtasks])
        setup_test_data(cli_test_workspace, initial_plan)
        
        task_id = str(task_with_subtasks.id)
        
        # Run the command
        result = runner.invoke(app, ["clear-subtasks", "--task-id", task_id])
        
        # Assertions
        assert result.exit_code == 0
        assert f"Subtasks cleared for task ID {task_with_subtasks.id}" in result.stdout
        assert "✅" in result.stdout
        
        # Verify the subtasks were cleared in the persisted plan
        updated_plan = load_updated_project_plan(cli_test_workspace)
        updated_task = updated_plan.tasks[0]
        assert len(updated_task.subtasks) == 0

    def test_clear_subtasks_single_task_not_found(self, runner, cli_test_workspace):
        """Test clear-subtasks command when task is not found."""
        # Setup: Create empty project plan
        initial_plan = create_project_plan_with_tasks([])
        setup_test_data(cli_test_workspace, initial_plan)
        
        task_id = str(uuid4())
        
        # Run the command
        result = runner.invoke(app, ["clear-subtasks", "--task-id", task_id])
        
        # Assertions
        assert result.exit_code == 1
        assert "Task not found or no subtasks to clear" in result.stdout
        assert "❌" in result.stdout

    def test_clear_subtasks_single_task_no_subtasks(self, runner, cli_test_workspace):
        """Test clear-subtasks command on a task that has no subtasks."""
        # Setup: Create task without subtasks
        task_without_subtasks = Task(
            id=uuid4(),
            title="Task without Subtasks",
            description="A task with no subtasks",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
            subtasks=[]
        )
        
        initial_plan = create_project_plan_with_tasks([task_without_subtasks])
        setup_test_data(cli_test_workspace, initial_plan)
        
        task_id = str(task_without_subtasks.id)
        
        # Run the command
        result = runner.invoke(app, ["clear-subtasks", "--task-id", task_id])
        
        # Assertions
        assert result.exit_code == 0
        assert f"Subtasks cleared for task ID {task_without_subtasks.id}" in result.stdout
        assert "✅" in result.stdout
        
        # Verify the task still has no subtasks
        updated_plan = load_updated_project_plan(cli_test_workspace)
        updated_task = updated_plan.tasks[0]
        assert len(updated_task.subtasks) == 0

    def test_clear_subtasks_all_tasks_success(self, runner, cli_test_workspace):
        """Test clear-subtasks command for all tasks with subtasks."""
        # Setup: Create multiple tasks with subtasks
        task1_subtasks = [
            Subtask(id=uuid4(), title="Task1 Sub1", description="Desc1", status=TaskStatus.PENDING),
            Subtask(id=uuid4(), title="Task1 Sub2", description="Desc2", status=TaskStatus.PENDING)
        ]
        
        task2_subtasks = [
            Subtask(id=uuid4(), title="Task2 Sub1", description="Desc3", status=TaskStatus.PENDING)
        ]
        
        task_with_subtasks1 = Task(
            id=uuid4(),
            title="Task 1 with Subtasks",
            description="First task with subtasks",
            status=TaskStatus.PENDING,
            subtasks=task1_subtasks
        )
        
        task_with_subtasks2 = Task(
            id=uuid4(),
            title="Task 2 with Subtasks", 
            description="Second task with subtasks",
            status=TaskStatus.IN_PROGRESS,
            subtasks=task2_subtasks
        )
        
        task_without_subtasks = Task(
            id=uuid4(),
            title="Task without Subtasks",
            description="Task with no subtasks",
            status=TaskStatus.COMPLETED,
            subtasks=[]
        )
        
        initial_plan = create_project_plan_with_tasks([task_with_subtasks1, task_with_subtasks2, task_without_subtasks])
        setup_test_data(cli_test_workspace, initial_plan)
        
        # Run the command
        result = runner.invoke(app, ["clear-subtasks", "--all"])
        
        # Assertions
        assert result.exit_code == 0
        assert "Cleared subtasks from 2 tasks" in result.stdout
        assert "✅" in result.stdout
        
        # Verify the subtasks were cleared in the persisted plan
        updated_plan = load_updated_project_plan(cli_test_workspace)
        for task in updated_plan.tasks:
            assert len(task.subtasks) == 0

    def test_clear_subtasks_all_tasks_no_subtasks_present(self, runner, cli_test_workspace):
        """Test clear-subtasks command when no tasks have subtasks."""
        # Setup: Create tasks without subtasks
        task1 = Task(
            id=uuid4(),
            title="Task 1",
            description="First task without subtasks",
            status=TaskStatus.PENDING,
            subtasks=[]
        )
        
        task2 = Task(
            id=uuid4(),
            title="Task 2",
            description="Second task without subtasks",
            status=TaskStatus.COMPLETED,
            subtasks=[]
        )
        
        initial_plan = create_project_plan_with_tasks([task1, task2])
        setup_test_data(cli_test_workspace, initial_plan)
        
        # Run the command
        result = runner.invoke(app, ["clear-subtasks", "--all"])
        
        # Assertions
        assert result.exit_code == 0
        assert "No tasks with subtasks found to clear" in result.stdout
        assert "📝" in result.stdout

    def test_clear_subtasks_all_tasks_empty_project(self, runner, cli_test_workspace):
        """Test clear-subtasks command on an empty project."""
        # Setup: Create empty project plan
        initial_plan = create_project_plan_with_tasks([])
        setup_test_data(cli_test_workspace, initial_plan)
        
        # Run the command
        result = runner.invoke(app, ["clear-subtasks", "--all"])
        
        # Assertions
        assert result.exit_code == 0
        assert "No tasks with subtasks found to clear" in result.stdout
        assert "📝" in result.stdout

    def test_clear_subtasks_command_missing_args(self, runner, cli_test_workspace):
        """Test clear-subtasks command when neither --task-id nor --all is provided."""
        # Setup: Create project plan (doesn't matter for this test)
        initial_plan = create_project_plan_with_tasks([])
        setup_test_data(cli_test_workspace, initial_plan)
        
        # Run the command without required arguments
        result = runner.invoke(app, ["clear-subtasks"])
        
        # Assertions
        assert result.exit_code == 1
        assert "Please specify either --task-id" in result.stdout
        assert "Examples:" in result.stdout
        assert "task-master clear-subtasks --task-id" in result.stdout
        assert "task-master clear-subtasks --all" in result.stdout

    def test_clear_subtasks_command_invalid_task_id(self, runner, cli_test_workspace):
        """Test clear-subtasks command with an invalid task ID format."""
        # Setup: Create project plan (doesn't matter for this test)
        initial_plan = create_project_plan_with_tasks([])
        setup_test_data(cli_test_workspace, initial_plan)
        
        # Run the command with invalid UUID
        result = runner.invoke(app, ["clear-subtasks", "--task-id", "invalid-uuid"])
        
        # Assertions
        assert result.exit_code == 1
        assert "Invalid task ID format" in result.stdout
        assert "❌" in result.stdout

    def test_clear_subtasks_command_both_options_specified(self, runner, cli_test_workspace):
        """Test clear-subtasks command behavior when both --task-id and --all are specified."""
        # Setup: Create tasks with subtasks
        task_subtasks = [
            Subtask(id=uuid4(), title="Sub1", description="Desc1", status=TaskStatus.PENDING),
            Subtask(id=uuid4(), title="Sub2", description="Desc2", status=TaskStatus.PENDING)
        ]
        
        task_with_subtasks = Task(
            id=uuid4(),
            title="Task with Subtasks",
            description="A task with subtasks",
            status=TaskStatus.PENDING,
            subtasks=task_subtasks
        )
        
        task_without_subtasks = Task(
            id=uuid4(),
            title="Task without Subtasks",
            description="A task without subtasks",
            status=TaskStatus.PENDING,
            subtasks=[]
        )
        
        initial_plan = create_project_plan_with_tasks([task_with_subtasks, task_without_subtasks])
        setup_test_data(cli_test_workspace, initial_plan)
        
        task_id = str(task_with_subtasks.id)
        
        # Run the command with both options (--all should take precedence based on CLI logic)
        result = runner.invoke(app, ["clear-subtasks", "--task-id", task_id, "--all"])
        
        # Assertions
        assert result.exit_code == 0
        assert "Cleared subtasks from 1 tasks" in result.stdout  # Only 1 task had subtasks
        assert "✅" in result.stdout
        
        # Verify all tasks have no subtasks
        updated_plan = load_updated_project_plan(cli_test_workspace)
        for task in updated_plan.tasks:
            assert len(task.subtasks) == 0

    def test_clear_subtasks_command_preserves_task_properties(self, runner, cli_test_workspace):
        """Test that clear-subtasks command only clears subtasks and preserves other task properties."""
        # Setup: Create task with subtasks and specific properties
        subtasks = [
            Subtask(id=uuid4(), title="Sub to clear", description="Will be cleared", status=TaskStatus.PENDING)
        ]
        
        original_task = Task(
            id=uuid4(),
            title="Important Task",
            description="A very important task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            subtasks=subtasks,
            dependencies=[uuid4()]  # Add a dependency
        )
        
        initial_plan = create_project_plan_with_tasks([original_task])
        setup_test_data(cli_test_workspace, initial_plan)
        
        task_id = str(original_task.id)
        
        # Run the command
        result = runner.invoke(app, ["clear-subtasks", "--task-id", task_id])
        
        # Assertions
        assert result.exit_code == 0
        assert "Subtasks cleared" in result.stdout
        
        # Verify only subtasks were cleared, other properties preserved
        updated_plan = load_updated_project_plan(cli_test_workspace)
        updated_task = updated_plan.tasks[0]
        
        assert len(updated_task.subtasks) == 0  # Subtasks cleared
        assert updated_task.title == original_task.title  # Title preserved
        assert updated_task.description == original_task.description  # Description preserved
        assert updated_task.status == original_task.status  # Status preserved
        assert updated_task.priority == original_task.priority  # Priority preserved
        assert updated_task.dependencies == original_task.dependencies  # Dependencies preserved
        assert updated_task.id == original_task.id  # ID preserved