"""CLI tests for Phase 7: Task Management (Clearing) functionality."""

import pytest
from uuid import uuid4, UUID
from typing import List, Dict, Any

from typer.testing import CliRunner 

from src.cli.main import app
from src.data_models import Task, TaskStatus, TaskPriority, ProjectPlan
from tests.cli.test_utils import run_cli_command, get_task_by_id_from_file, create_task_dict

# Helper to create Task model instances from dictionaries, especially for subtasks

class TestClearSubtasksCommand:
    """Test cases for the clear-subtasks CLI command."""

    @pytest.mark.asyncio
    async def test_clear_subtasks_single_task_success(self, runner: CliRunner, cli_test_workspace, project_plan_factory, real_agent):
        """Test clear-subtasks command for a single task with subtasks."""
        # Setup: Create task with subtasks
        subtask1_id = uuid4()
        subtask2_id = uuid4()
        
        subtask_dicts = [
            create_task_dict(
                title="Task 1",
                description="First subtask to be cleared",
                status=TaskStatus.PENDING,
                priority=TaskPriority.HIGH,
                _id=subtask1_id
            ),
            create_task_dict(
                title="Task 2",
                description="Second subtask to be cleared",
                status=TaskStatus.PENDING,
                priority=TaskPriority.MEDIUM,
                _id=subtask2_id
            )
        ]
        
        parent_task_id = uuid4()
        task_with_subtasks = create_task_dict(
            title="Task with Subtasks",
            description="A task that has subtasks to clear",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
            _id=parent_task_id,
            subtasks=subtask_dicts # Pass Task objects directly
        )

        initial_tasks = [task_with_subtasks]
        
        # Run the command
        result = await run_cli_command(runner, ["clear-subtasks", "--task-id", str(parent_task_id)], cli_test_workspace)
        
        # Assertions
        assert result.exit_code == 0
        assert f"Subtasks cleared for task ID {parent_task_id}" in result.stdout
        assert "✅" in result.stdout
        
        # Verify the subtasks were cleared in the persisted plan
        updated_plan = project_plan_factory.load()
        assert updated_plan is not None
        updated_task = get_task_by_id_from_file(cli_test_workspace, parent_task_id)
        assert updated_task is not None
        assert len(updated_task.subtasks) == 0

    @pytest.mark.asyncio
    async def test_clear_subtasks_single_task_not_found(self, runner: CliRunner, cli_test_workspace, project_plan_factory, real_agent):
        """Test clear-subtasks command when task is not found."""
        # Setup: Create empty project plan
        project_plan_factory.create_with_tasks([])
        
        non_existent_task_id = str(uuid4())
        
        # Run the command
        result = await run_cli_command(runner, ["clear-subtasks", "--task-id", non_existent_task_id], cli_test_workspace)
        
        # Assertions
        assert result.exit_code == 1
        assert "Task not found or no subtasks to clear" in result.stdout
        assert "❌" in result.stdout

    @pytest.mark.asyncio
    async def test_clear_subtasks_single_task_no_subtasks(self, runner: CliRunner, cli_test_workspace, project_plan_factory, real_agent):
        """Test clear-subtasks command on a task that has no subtasks."""
        # Setup: Create task without subtasks
        parent_task_id = uuid4()
        task_without_subtasks_dict = create_task_dict(
            title="Task without Subtasks",
            description="A task with no subtasks",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
            _id=parent_task_id,
            subtasks=[] # No subtasks
        )

        initial_tasks = [task_without_subtasks_dict]
        project_plan_factory.create_with_tasks(initial_tasks)
        
        # Run the command
        result = await run_cli_command(runner, ["clear-subtasks", "--task-id", str(parent_task_id)], cli_test_workspace)
        
        # Assertions
        assert result.exit_code == 0
        assert f"Subtasks cleared for task ID {parent_task_id}" in result.stdout
        assert "✅" in result.stdout
        
        # Verify the task still has no subtasks
        updated_plan = project_plan_factory.load()
        assert updated_plan is not None
        updated_task = get_task_by_id_from_file(cli_test_workspace, parent_task_id)
        assert updated_task is not None
        assert len(updated_task.subtasks) == 0

    @pytest.mark.asyncio
    async def test_clear_subtasks_all_tasks_success(self, runner: CliRunner, cli_test_workspace, project_plan_factory, real_agent):
        """Test clear-subtasks command for all tasks with subtasks."""
        # Setup: Create multiple tasks
        sub1_t1_id = uuid4()
        sub2_t1_id = uuid4()
        task1_subtask_dicts = [
            create_task_dict(title="Task1 Sub1", description="Desc1", status=TaskStatus.PENDING, _id=sub1_t1_id),
            create_task_dict(title="Task1 Sub2", description="Desc2", status=TaskStatus.PENDING, _id=sub2_t1_id)
        ]
        
        sub1_t2_id = uuid4()
        task2_subtask_list = [
            create_task_dict(title="Task2 Sub1", description="Desc3", status=TaskStatus.PENDING, _id=sub1_t2_id)
        ]
        
        task1_id = uuid4()
        task_with_subtasks1 = create_task_dict(
            title="Task 1 with Subtasks",
            description="First task with subtasks",
            status=TaskStatus.PENDING,
            _id=task1_id,
            subtasks=task1_subtask_dicts
        )

        task2_id = uuid4()
        task_with_subtasks2 = create_task_dict(
            title="Task 2 with Subtasks",
            description="Second task with subtasks",
            status=TaskStatus.IN_PROGRESS,
            _id=task2_id,
            subtasks=task2_subtask_list
        )
        
        task3_id = uuid4()
        task_without_subtasks = create_task_dict(
            title="Task without Subtasks",
            description="Task with no subtasks",
            status=TaskStatus.COMPLETED,
            _id=task3_id,
            subtasks=[]
        )

        initial_tasks = [
            task_with_subtasks1,
            task_with_subtasks2,
            task_without_subtasks
        ]
        project_plan_factory.create_with_tasks(initial_tasks)
        
        # Run the command
        result = await run_cli_command(runner, ["clear-subtasks", "--all"], cli_test_workspace)
        
        # Assertions
        assert result.exit_code == 0
        assert "Cleared subtasks from 2 tasks" in result.stdout
        assert "✅" in result.stdout
        
        # Verify the subtasks were cleared in the persisted plan
        updated_plan = project_plan_factory.load()
        assert updated_plan is not None
        for task_model in updated_plan.tasks:
            task_from_file = get_task_by_id_from_file(cli_test_workspace, task_model.id)
            assert task_from_file is not None
            assert len(task_from_file.subtasks) == 0

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_clear_subtasks_all_tasks_no_subtasks_present(self, runner: CliRunner, cli_test_workspace, project_plan_factory, real_agent):
        task1_id = uuid4()
        task1_dict = create_task_dict(
            title="Task 1",
            description="First task without subtasks",
            status=TaskStatus.PENDING,
            _id=task1_id,
            subtasks=[]
        )
        
        task2_id = uuid4()
        task2 = create_task_dict(
            title="Task 2",
            description="Second task without subtasks",
            status=TaskStatus.COMPLETED,
            _id=task2_id,
            subtasks=[]
        )
 
        initial_tasks = [task1_dict, task2]
        project_plan_factory.create_with_tasks(initial_tasks)
        
        result = await run_cli_command(runner, ["clear-subtasks", "--all"], cli_test_workspace)
        
        assert result.exit_code == 0
        assert "No tasks with subtasks found to clear" in result.stdout
        assert "📝" in result.stdout
        
        updated_plan = project_plan_factory.load()
        assert updated_plan is not None
        for task_model in updated_plan.tasks:
            task_from_file = get_task_by_id_from_file(cli_test_workspace, task_model.id)
            assert task_from_file is not None
            assert len(task_from_file.subtasks) == 0
        """Test clear-subtasks command on an empty project."""
        # Setup: Create empty project plan
        project_plan_factory.create_with_tasks([])
        
        # Run the command
        result = await run_cli_command(runner, ["clear-subtasks", "--all"], cli_test_workspace)
        
        # Assertions
        assert result.exit_code == 0
        assert "No tasks with subtasks found to clear" in result.stdout
        assert "📝" in result.stdout

    @pytest.mark.asyncio
    async def test_clear_subtasks_command_missing_args(self, runner: CliRunner, cli_test_workspace, project_plan_factory, real_agent):
        """Test clear-subtasks command when neither --task-id nor --all is provided."""
        # Setup: Create project plan (doesn't matter for this test, but good practice to have one)
        project_plan_factory.create_with_tasks([])
        
        # Run the command without required arguments
        result = await run_cli_command(runner, ["clear-subtasks"], cli_test_workspace)
        
        # Assertions
        assert result.exit_code != 0
        assert "Missing option" in result.stdout or "Please specify either --task-id" in result.stdout

    @pytest.mark.asyncio
    async def test_clear_subtasks_command_invalid_task_id(self, runner: CliRunner, cli_test_workspace, project_plan_factory, real_agent):
        """Test clear-subtasks command with an invalid task ID format."""
        project_plan_factory.create_with_tasks([])
        
        result = await run_cli_command(runner, ["clear-subtasks", "--task-id", "invalid-uuid"], cli_test_workspace)
        
        assert result.exit_code == 1
        assert "Invalid task ID format" in result.stdout
        assert "❌" in result.stdout

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_clear_subtasks_command_both_options_specified(self, runner: CliRunner, cli_test_workspace, project_plan_factory, real_agent):
        sub1_id = uuid4()
        task_subtask_dicts = [
            create_task_dict(title="Sub1", description="Desc1", status=TaskStatus.PENDING, _id=sub1_id)
        ]
        
        task1_id = uuid4()
        task_with_subtasks = create_task_dict(
            title="Task with Subtasks",
            description="A task with subtasks",
            _id=task1_id,
            subtasks=task_subtask_dicts
        )
 
        task2_id = uuid4()
        task_without_subtasks = create_task_dict(
            title="Task without Subtasks",
            description="A task without subtasks",
            _id=task2_id,
            subtasks=[]
        )
        
        initial_tasks = [
            task_with_subtasks,
            task_without_subtasks
        ]
        project_plan_factory.create_with_tasks(initial_tasks)
        
        result = await run_cli_command(runner, ["clear-subtasks", "--task-id", str(task1_id), "--all"], cli_test_workspace)
        
        assert result.exit_code == 0
        assert "Cleared subtasks from 1 tasks" in result.stdout
        assert "✅" in result.stdout
        
        updated_plan = project_plan_factory.load()
        assert updated_plan is not None
        for task_model in updated_plan.tasks:
            task_from_file = get_task_by_id_from_file(cli_test_workspace, task_model.id)
            assert task_from_file is not None
            assert len(task_from_file.subtasks) == 0
        sub1_id = uuid4()
        subtask_dicts = [
            create_task_dict(title="Sub to clear", description="Will be cleared", status=TaskStatus.PENDING, _id=sub1_id)
        ]
        
        original_task_id = uuid4()
        dependency_id = uuid4()
        original_task = create_task_dict(
            title="Important Task",
            description="A very important task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            dependencies=[dependency_id],
            _id=original_task_id,
            subtasks=subtask_dicts
        )
        
        project_plan_factory.create_with_tasks([original_task])
        
        # Run the command
        result = await run_cli_command(runner, ["clear-subtasks", "--task-id", str(original_task_id)], cli_test_workspace)
        
        # Assertions
        assert result.exit_code == 0
        assert f"Subtasks cleared for task ID {original_task_id}" in result.stdout
        
        # Verify only subtasks were cleared, other properties preserved
        updated_plan = project_plan_factory.load()
        assert updated_plan is not None
        updated_task = get_task_by_id_from_file(cli_test_workspace, original_task_id)
        assert updated_task is not None
        
        assert len(updated_task.subtasks) == 0
        assert updated_task.title == original_task.title
        assert updated_task.description == original_task.description
        assert updated_task.status == original_task.status
        assert updated_task.priority == original_task.priority
        assert updated_task.dependencies == original_task.dependencies
        assert updated_task.id == original_task.id
        assert updated_task.updated_at > original_task.updated_at
