"""CLI tests for Phase 8: Single Task/Task Refinement commands."""

import pytest
from uuid import uuid4

from src.data_models import TaskStatus, TaskPriority
from tests.cli.test_utils import run_cli_command, get_task_by_id_from_file, assert_task_properties, create_task_dict
from tests.cli.utils import requires_api_key


class TestUpdateTaskCommand:
    """Test the update-task CLI command."""

    @pytest.fixture(autouse=True)
    def setup_method(self, cli_test_workspace):
        """Ensure a clean workspace for each test."""
        # The cli_test_workspace fixture already handles creation and cleanup.
        # We just need to ensure it's available.
        pass

    @requires_api_key()
    @pytest.mark.asyncio
    async def test_update_task_command_success(self, runner, cli_test_workspace, project_plan_factory, real_agent):
        """Test successful task update via CLI."""
        # Arrange
        task_id = uuid4()
        initial_task_title = "Original Task Title"
        initial_task_description = "Original task description."
        initial_task_status = TaskStatus.PENDING
        initial_task_priority = TaskPriority.MEDIUM

        project_plan_factory.create_with_tasks(
            task_list=[
                create_task_dict(
                    title=initial_task_title,
                    description=initial_task_description,
                    status=initial_task_status,
                    priority=initial_task_priority,
                    _id=task_id # Pass id explicitly for testing specific task
                )
            ]
        )

        update_instruction = "Change title to 'Refined Task Title', description to 'This is a refined description with more details.', and priority to HIGH."

        # Act
        result = await run_cli_command(
            runner,
            ["--workspace", str(cli_test_workspace), "update-task", str(task_id), update_instruction],
            (cli_test_workspace, real_agent)
        )

        # Assert
        assert result.exit_code == 0
        assert "Successfully updated task" in result.stdout

        updated_plan = project_plan_factory.load()
        updated_task = get_task_by_id_from_file(cli_test_workspace, task_id)

        assert updated_task is not None
        assert updated_task.id == task_id
        assert updated_task.title != initial_task_title # LLM should change title
        assert updated_task.description != initial_task_description # LLM should change description
        assert updated_task.priority == TaskPriority.HIGH
        assert updated_task.status == initial_task_status # Status not explicitly changed by instruction

        # Check for keywords in description to ensure LLM processed it
        assert "refined description" in updated_task.description
        assert "more details" in updated_task.description

    @requires_api_key()
    @pytest.mark.asyncio
    async def test_update_task_command_task_not_found(self, runner, cli_test_workspace, project_plan_factory, real_agent):
        """Test update-task command when task is not found."""
        # Arrange
        task_id = uuid4()
        project_plan_factory.create_with_tasks(tasks=[]) # Empty plan

        # Act
        result = await run_cli_command(
            runner,
            ["--workspace", str(cli_test_workspace), "update-task", str(task_id), "This task doesn't exist"],
            (cli_test_workspace, real_agent)
        )

        # Assert
        assert result.exit_code == 1
        assert f"Task with ID '{task_id}' not found" in result.stdout

    @requires_api_key()
    @pytest.mark.asyncio
    async def test_update_task_command_invalid_uuid(self, runner, cli_test_workspace, real_agent):
        """Test update-task command with invalid UUID."""
        # Act
        result = await run_cli_command(
            runner,
            ["--workspace", str(cli_test_workspace), "update-task", "invalid-uuid", "Some refinement instruction"],
            (cli_test_workspace, real_agent)
        )

        # Assert
        assert result.exit_code == 1
        assert "Invalid task ID format" in result.stdout

    @requires_api_key()
    @pytest.mark.asyncio
    async def test_update_task_command_item_is_subtask(self, runner, cli_test_workspace, project_plan_factory, real_agent):
        """Test update-task command when the item is actually a subtask."""
        # Arrange
        parent_task_id = uuid4()
        subtask_id = uuid4()
        project_plan_factory.create_with_tasks(
            task_list=[
                create_task_dict(
                    description="Parent task description",
                    title="Parent Task",
                    _id=parent_task_id, # Pass id explicitly
                    subtasks=[
                        create_task_dict(
                            description="Not a task",
                            title="This is a subtask",
                            _id=subtask_id, # Pass id explicitly
                            parent_id=parent_task_id
                        )
                    ]
                )
            ]
        )
        # Act
        result = await run_cli_command(
            runner,
            ["--workspace", str(cli_test_workspace), "update-task", str(subtask_id), "Try to update a subtask as task"],
            (cli_test_workspace, real_agent)
        )

        # Assert
        assert result.exit_code == 1
        assert f"Task with ID '{subtask_id}' not found" in result.stdout # Now it's just "not found"


class TestUpdateSubtaskCommand:
    """Test the update-subtask CLI command."""

    @pytest.fixture(autouse=True)
    def setup_method(self, cli_test_workspace):
        """Ensure a clean workspace for each test."""
        pass

    @requires_api_key()
    @pytest.mark.asyncio
    async def test_update_subtask_command_success(self, runner, cli_test_workspace, project_plan_factory, real_agent):
        """Test successful subtask update via CLI."""
        # Arrange
        parent_task_id = uuid4()
        subtask_id = uuid4()
        initial_subtask_title = "Original Task Title"
        initial_subtask_description = "Original subtask description."
        initial_subtask_status = TaskStatus.PENDING
        initial_subtask_priority = TaskPriority.LOW

        project_plan_factory.create_with_tasks(
            task_list=[
                create_task_dict(
                    title="Parent Task for Task Update",
                    description="Parent task description", # Added description
                    _id=parent_task_id, # Pass id explicitly
                    subtasks=[
                        create_task_dict(
                            title=initial_subtask_title,
                            description=initial_subtask_description,
                            status=initial_subtask_status,
                            priority=initial_subtask_priority,
                            parent_id=parent_task_id,
                            _id=subtask_id # Pass id explicitly
                        )
                    ]
                )
            ]
        )

        update_instruction = "Change title to 'Refined Task Title', description to 'This is a refined subtask description.', and status to COMPLETED."

        # Act
        result = await run_cli_command(
            runner,
            ["--workspace", str(cli_test_workspace), "update-subtask", str(subtask_id), update_instruction],
            cli_test_workspace
        )

        # Assert
        assert result.exit_code == 0
        assert "Successfully updated subtask" in result.stdout

        updated_plan = project_plan_factory.load()
        updated_subtask = get_task_by_id_from_file(cli_test_workspace, subtask_id)

        assert updated_subtask is not None
        assert updated_subtask.id == subtask_id
        assert updated_subtask.title != initial_subtask_title # LLM should change title
        assert updated_subtask.description != initial_subtask_description # LLM should change description
        assert updated_subtask.status == TaskStatus.COMPLETED
        assert updated_subtask.priority == initial_subtask_priority # Priority not explicitly changed by instruction

        # Check for keywords in description to ensure LLM processed it
        assert "refined subtask description" in updated_subtask.description

    @requires_api_key()
    @pytest.mark.asyncio
    async def test_update_subtask_command_subtask_not_found(self, runner, cli_test_workspace, project_plan_factory, real_agent):
        """Test update-subtask command when subtask is not found."""
        # Arrange
        subtask_id = uuid4()
        project_plan_factory.create_with_tasks(tasks=[]) # Empty plan

        # Act
        result = await run_cli_command(
            runner,
            ["--workspace", str(cli_test_workspace), "update-subtask", str(subtask_id), "This subtask doesn't exist"],
            (cli_test_workspace, real_agent)
        )

        # Assert
        assert result.exit_code == 1
        assert f"Task with ID '{subtask_id}' not found" in result.stdout

    @requires_api_key()
    @pytest.mark.asyncio
    async def test_update_subtask_command_invalid_uuid(self, runner, cli_test_workspace, real_agent):
        """Test update-subtask command with invalid UUID."""
        # Act
        result = await run_cli_command(
            runner,
            ["--workspace", str(cli_test_workspace), "update-subtask", "invalid-uuid", "Some refinement instruction"],
            (cli_test_workspace, real_agent)
        )

        # Assert
        assert result.exit_code == 1
        assert "Invalid subtask ID format" in result.stdout

    @requires_api_key()
    @pytest.mark.asyncio
    async def test_update_subtask_command_item_is_task(self, runner, cli_test_workspace, project_plan_factory, real_agent):
        """Test update-subtask command when the item is actually a task."""
        # Arrange
        task_id = uuid4()
        project_plan_factory.create_with_tasks(
            task_list=[
                create_task_dict(
                    title="This is a task",
                    description="Not a subtask",
                    _id=task_id # Pass id explicitly
                )
            ]
        )

        # Act
        result = await run_cli_command(
            runner,
            ["--workspace", str(cli_test_workspace), "update-subtask", str(task_id), "Try to update a task as subtask"],
            cli_test_workspace
        )

        # Assert
        assert result.exit_code == 1
        assert f"Task with ID '{task_id}' not found" in result.stdout # Now it's just "not found"

    @requires_api_key()
    @pytest.mark.asyncio
    async def test_update_subtask_command_with_research_model(self, runner, cli_test_workspace, project_plan_factory, real_agent):
        """Test update-subtask command with research model flag."""
        # Arrange
        parent_task_id = uuid4()
        subtask_id = uuid4()
        initial_subtask_title = "Research Task"
        initial_subtask_description = "Needs research-based refinement"
        initial_subtask_status = TaskStatus.PENDING
        initial_subtask_priority = TaskPriority.MEDIUM

        project_plan_factory.create_with_tasks(
            task_list=[
                create_task_dict(
                    description="Parent task description",
                    title="Parent Task for Research Task",
                    _id=parent_task_id, # Pass id explicitly
                    subtasks=[
                        create_task_dict(
                            description=initial_subtask_description,
                            title=initial_subtask_title,
                            status=initial_subtask_status,
                            priority=initial_subtask_priority,
                            parent_id=parent_task_id,
                            _id=subtask_id # Pass id explicitly
                        )
                    ]
                )
            ]
        ) # Closing parenthesis for create_with_tasks

        update_instruction = "Change title to 'Quantum Computing Research Task' and enhance description with research insights about quantum computing." # Made instruction more explicit

        # Act
        result = await run_cli_command(
            runner,
            ["--workspace", str(cli_test_workspace), "update-subtask", str(subtask_id), update_instruction, "--research"],
            cli_test_workspace
        )

        # Assert
        assert result.exit_code == 0
        assert "Successfully updated subtask" in result.stdout

        updated_plan = project_plan_factory.load()
        updated_subtask = get_task_by_id_from_file(cli_test_workspace, subtask_id)

        assert updated_subtask is not None
        assert updated_subtask.id == subtask_id
        assert updated_subtask.title == "Quantum Computing Research Task" # Assert exact title
        assert updated_subtask.description != initial_subtask_description
        assert "quantum computing" in updated_subtask.description # Verify research impact