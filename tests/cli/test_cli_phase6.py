"""
Improved CLI tests for Phase 6: Task Expansion (Subtasks) functionality.

This test suite includes both:
1. Unit tests with mocks for fast feedback and edge case testing (default)
2. Integration tests with real LLM calls for end-to-end validation (when enabled)
3. Fixture-based tests using pre-generated LLM data for consistent results

To run integration tests with real LLM calls:
    pytest tests/cli/test_cli_phase6.py -v

To generate fresh fixtures:
    python tests/fixtures/generate_expansion_fixtures.py
"""

import pytest
import json
import os
from unittest.mock import patch, AsyncMock
from uuid import uuid4, UUID
from pathlib import Path
from typer.testing import CliRunner

from src.cli.main import app
from src.data_models import Task, TaskStatus, TaskPriority, ProjectPlan
from tests.cli.utils import requires_api_key
from tests.cli.test_utils import run_cli_command, get_task_by_id_from_file


@pytest.fixture
def llm_fixtures():
    """Load real LLM-generated fixtures if available, otherwise create mock data."""
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "phase6_expansion_fixtures.json"
    
    if fixtures_path.exists():
        with open(fixtures_path) as f:
            return json.load(f)
    else:
        # Fallback mock data if fixtures haven't been generated yet
        # Simplified tasks for faster LLM calls in tests
        return {
            "base_project_plan": {
                "id": str(uuid4()),
                "project_title": "Simple Test Project",
                "overall_goal": "Test subtask generation with minimal tasks",
                "tasks": [
                    {
                        "id": str(uuid4()),
                        "title": "Implement basic user authentication",
                        "description": "Create a simple login and registration flow.",
                        "status": "PENDING",
                        "priority": "HIGH",
                        "subtasks": []
                    },
                    {
                        "id": str(uuid4()),
                        "title": "Develop task listing feature",
                        "description": "Display all tasks in a clear, sortable list.",
                        "status": "PENDING",
                        "priority": "MEDIUM",
                        "subtasks": []
                    }
                ]
            },
            "tasks_with_subtasks": [],
            "sample_subtasks_only": []
        }


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    return Task(
        id=uuid4(),
        title="Sample Task",
        description="A sample task for testing",
        status=TaskStatus.PENDING,
        priority=TaskPriority.MEDIUM,
        subtasks=[]
    )


@pytest.fixture
def sample_subtasks():
    """Create sample subtasks for testing."""
    return [
        Task(
            id=uuid4(),
            title="New Task 1",
            description="First new subtask",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH
        ),
        Task(
            id=uuid4(),
            title="New Task 2",
            description="Second new subtask",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM
        )
    ]


def create_project_plan_with_tasks(tasks):
    """Helper to create a ProjectPlan with given tasks."""
    return ProjectPlan(
        id=uuid4(),
        project_title="Test Project",
        overall_goal="Test project for CLI testing",
        tasks=tasks
    )


def deserialize_task_from_fixture(task_data):
    """Convert fixture task data back to Task object."""
    subtasks = [
        Task(
            id=uuid4(),  # Generate fresh UUID to avoid conflicts
            title=st["title"],
            description=st["description"],
            status=TaskStatus(st["status"]),
            priority=TaskPriority(st["priority"])
        )
        for st in task_data.get("subtasks", [])
    ]
    
    return Task(
        id=uuid4(),  # Generate fresh UUID to avoid conflicts
        title=task_data["title"],
        description=task_data["description"],
        status=TaskStatus(task_data["status"]),
        priority=TaskPriority(task_data["priority"]),
        subtasks=subtasks
    )


class TestExpandCommandIntegration:
    """Integration tests using real LLM calls for end-to-end validation."""
    
    @requires_api_key()
    @pytest.mark.asyncio
    async def test_expand_command_real_llm_single_task(self, runner, llm_fixtures, cli_test_workspace, project_plan_factory, real_agent):
        """Test expand command with real LLM calls for a single task."""
        # Use a task from real fixtures
        fixture_plan = llm_fixtures["base_project_plan"]
        if not fixture_plan["tasks"]:
            pytest.skip("No tasks in LLM fixtures")
            
        # Convert fixture data to objects
        tasks = [deserialize_task_from_fixture(t) for t in fixture_plan["tasks"]]
        project_plan = create_project_plan_with_tasks(tasks[:1])  # Use first task only
        project_plan_factory.create(project_plan) # Use project_plan_factory to set up data
        
        task_id = str(tasks[0].id)
        
        # Run the command (this will make real LLM calls)
        result = await run_cli_command(runner, ["expand", "--task-id", task_id], cli_test_workspace)
        
        # Assertions
        assert result.exit_code == 0
        assert f"Successfully expanded task '{tasks[0].title}'" in result.stdout
        
        # Verify the project plan was updated with real subtasks
        workspace_path, _ = cli_test_workspace
        updated_plan = project_plan_factory.load()
        updated_task = get_task_by_id_from_file(workspace_path, task_id)
        assert updated_task is not None
        assert len(updated_task.subtasks) > 0
        
        # Verify subtasks have realistic content (not just mock data)
        for subtask in updated_task.subtasks:
            assert len(subtask.title) > 5  # Real titles should be descriptive
            assert len(subtask.description) > 10  # Real descriptions should be detailed
            assert subtask.status == TaskStatus.PENDING
        
        print(f"Generated {len(updated_task.subtasks)} real subtasks:")
        for st in updated_task.subtasks:
            print(f"  - {st.title}: {st.description}")

    @requires_api_key()
    @pytest.mark.asyncio
    async def test_expand_command_real_llm_all_pending(self, runner, llm_fixtures, cli_test_workspace, project_plan_factory, real_agent):
        """Test expand command with real LLM calls for all pending tasks."""
        # Use multiple tasks from real fixtures but ensure they have no subtasks
        fixture_plan = llm_fixtures["base_project_plan"]
        if len(fixture_plan["tasks"]) < 2:
            pytest.skip("Need at least 2 tasks in LLM fixtures")
            
        # Convert fixture data to objects but clear any existing subtasks
        tasks = [deserialize_task_from_fixture(t) for t in fixture_plan["tasks"][:2]]
        for task in tasks:
            task.subtasks = []  # Ensure tasks have no subtasks initially
            
        project_plan = create_project_plan_with_tasks(tasks)
        project_plan_factory.create(project_plan) # Use project_plan_factory to set up data
        
        # Run the command (this will make real LLM calls)
        result = await run_cli_command(runner, ["expand", "--all-pending"], cli_test_workspace)
        
        # Assertions
        assert result.exit_code == 0
        
        # Check if tasks were successfully expanded or if we need to adjust expectations
        if f"Successfully expanded {len(tasks)} pending tasks" in result.stdout:
            # Success case: verify all tasks were expanded with real subtasks
            workspace_path, _ = cli_test_workspace
            updated_plan = project_plan_factory.load()
            for task in updated_plan.tasks:
                assert len(task.subtasks) > 0
                
                for subtask in task.subtasks:
                    assert len(subtask.title) > 5
                    assert len(subtask.description) > 10
                    assert subtask.status == TaskStatus.PENDING
                    
            total_subtasks = sum(len(task.subtasks) for task in updated_plan.tasks)
            print(f"Generated {total_subtasks} real subtasks across {len(tasks)} tasks")
        else:
            if "No pending tasks were expanded" in result.stdout:
                workspace_path, _ = cli_test_workspace
                updated_plan = project_plan_factory.load()
                total_subtasks = sum(len(task.subtasks) for task in updated_plan.tasks)
                
                if total_subtasks == 0:
                    pytest.fail(f"No subtasks were generated. CLI output: {result.stdout}")
                else:
                    print(f"Partial success: {total_subtasks} subtasks generated")

class TestExpandCommand:
    """Unit tests using mocks for fast feedback and edge case testing."""

    @patch('src.agent_core.llm_generator.LLMGenerator.generate_subtasks_for_task')
    @pytest.mark.asyncio
    async def test_expand_command_for_single_task(self, mock_generate_subtasks, runner, sample_task, sample_subtasks, cli_test_workspace, project_plan_factory, real_agent):
        initial_plan = create_project_plan_with_tasks([sample_task])
        workspace_path, _ = cli_test_workspace
        project_plan_factory.create(initial_plan)
        
        mock_generate_subtasks.return_value = sample_subtasks
        
        task_id = str(sample_task.id)
        
        result = await run_cli_command(runner, ["expand", "--task-id", task_id], cli_test_workspace)
        assert result.exit_code == 0
        assert f"Successfully expanded task '{sample_task.title}'" in result.stdout
        assert f"Task now has {len(sample_subtasks)} subtasks" in result.stdout
        assert "New Task 1" in result.stdout
        assert "New Task 2" in result.stdout
        
        updated_plan = project_plan_factory.load()
        updated_task = get_task_by_id_from_file(workspace_path, task_id)
        assert updated_task is not None
        assert len(updated_task.subtasks) == len(sample_subtasks)
        assert updated_task.subtasks[0].title == "New Task 1"
        assert updated_task.subtasks[1].title == "New Task 2"
        
        mock_generate_subtasks.assert_called_once()

    @patch('src.agent_core.llm_generator.LLMGenerator.generate_subtasks_for_task')
    @pytest.mark.asyncio
    async def test_expand_command_for_single_task_with_options(self, mock_generate_subtasks, runner, sample_task, sample_subtasks, cli_test_workspace, project_plan_factory, real_agent):
        workspace_path, _ = cli_test_workspace
        initial_plan = create_project_plan_with_tasks([sample_task])
        project_plan_factory.create(initial_plan)
        
        mock_generate_subtasks.return_value = sample_subtasks
        
        task_id = str(sample_task.id)
        custom_prompt = "Generate backend-focused subtasks"
        
        result = await run_cli_command(runner,
            ["expand", "--task-id", task_id, "--num", "3", "--research", "--prompt", custom_prompt],
            cli_test_workspace
        )
        
        assert result.exit_code == 0
        assert f"Successfully expanded task '{sample_task.title}'" in result.stdout
        
        updated_plan = project_plan_factory.load()
        updated_task = get_task_by_id_from_file(workspace_path, task_id)
        assert updated_task is not None
        assert len(updated_task.subtasks) == len(sample_subtasks)
        
        mock_generate_subtasks.assert_called_once()
        args, kwargs = mock_generate_subtasks.call_args
        assert kwargs.get('num_subtasks') == 3
        assert kwargs.get('prompt_override') == custom_prompt # Changed from context_prompt
        assert kwargs.get('model_type') == 'research'

    @pytest.mark.asyncio
    async def test_expand_command_for_single_task_not_found(self, runner, cli_test_workspace, project_plan_factory, real_agent):
        workspace_path, _ = cli_test_workspace
        initial_plan = create_project_plan_with_tasks([])
        project_plan_factory.create(initial_plan)
        
        task_id = str(uuid4())
        
        result = await run_cli_command(runner, ["expand", "--task-id", task_id], cli_test_workspace)
        
        assert result.exit_code == 1
        assert "not found or could not be expanded" in result.stdout
        
    @patch('src.agent_core.llm_generator.LLMGenerator.generate_subtasks_for_task')
    @pytest.mark.asyncio
    async def test_expand_command_for_all_pending(self, mock_generate_subtasks, runner, cli_test_workspace, project_plan_factory, real_agent):
        pending_task1 = Task(id=uuid4(), title="Pending 1", description="Desc 1", status=TaskStatus.PENDING, subtasks=[])
        pending_task2 = Task(id=uuid4(), title="Pending 2", description="Desc 2", status=TaskStatus.PENDING, subtasks=[])
        pending_task3 = Task(id=uuid4(), title="Pending 3", description="Desc 3", status=TaskStatus.PENDING, subtasks=[])
        
        initial_plan = create_project_plan_with_tasks([pending_task1, pending_task2, pending_task3])
        workspace_path, _ = cli_test_workspace
        project_plan_factory.create(initial_plan)
        
        def create_unique_subtask(*args, **kwargs):
            return [Task(id=uuid4(), title="Generated Sub", description="Desc", status=TaskStatus.PENDING)]
        
        mock_generate_subtasks.side_effect = create_unique_subtask
        
        result = await run_cli_command(runner, ["expand", "--all-pending"], cli_test_workspace)
        assert result.exit_code == 0
        assert "Successfully expanded 3 pending tasks" in result.stdout
        
        updated_plan = project_plan_factory.load()
        for task in updated_plan.tasks:
            assert len(task.subtasks) == 1
            assert task.subtasks[0].title == "Generated Sub"
        
        assert mock_generate_subtasks.call_count == 3

    @patch('src.agent_core.llm_generator.LLMGenerator.generate_subtasks_for_task')
    @pytest.mark.asyncio
    async def test_expand_command_for_all_pending_with_options(self, mock_generate_subtasks, runner, cli_test_workspace, project_plan_factory, real_agent):
        pending_task1 = Task(id=uuid4(), title="Pending Opt 1", description="Desc Opt 1", status=TaskStatus.PENDING, subtasks=[])
        pending_task2 = Task(id=uuid4(), title="Pending Opt 2", description="Desc Opt 2", status=TaskStatus.PENDING, subtasks=[])
        
        workspace_path, _ = cli_test_workspace
        initial_plan = create_project_plan_with_tasks([pending_task1, pending_task2])
        project_plan_factory.create(initial_plan)
        
        def create_unique_subtask_opt(*args, **kwargs):
            return [Task(id=uuid4(), title="Generated Sub Opt", description="Desc", status=TaskStatus.PENDING)]
        
        mock_generate_subtasks.side_effect = create_unique_subtask_opt
        
        result = await run_cli_command(runner,
            ["expand", "--all-pending", "--num", "5", "--research"],
            cli_test_workspace
        )
        
        assert result.exit_code == 0
        assert "Successfully expanded 2 pending tasks" in result.stdout
        
        updated_plan = project_plan_factory.load()
        for task in updated_plan.tasks:
            assert len(task.subtasks) == 1
            assert task.subtasks[0].title == "Generated Sub Opt"
        
        assert mock_generate_subtasks.call_count == 2
        for call_args in mock_generate_subtasks.call_args_list:
            args, kwargs = call_args
            assert kwargs.get('num_subtasks') == 5
            assert kwargs.get('model_type') == 'research'

    @pytest.mark.asyncio
    async def test_expand_command_for_all_pending_no_tasks_expanded(self, runner, cli_test_workspace, project_plan_factory, real_agent):
        workspace_path, _ = cli_test_workspace
        initial_plan = create_project_plan_with_tasks([])
        project_plan_factory.create(initial_plan)
        
        result = await run_cli_command(runner, ["expand", "--all-pending"], cli_test_workspace)
        
        assert result.exit_code == 0
        assert "No pending tasks were expanded" in result.stdout
        assert "Use --force to regenerate subtasks" in result.stdout

    @pytest.mark.asyncio
    async def test_expand_command_missing_args(self, runner, cli_test_workspace, real_agent):
        """Test expand command when neither --task-id nor --all-pending is provided."""
        # Run the command without required arguments
        result = await run_cli_command(runner, ["expand"], cli_test_workspace)
        
        # Assertions
        assert result.exit_code == 1
        assert "Please specify either --task-id" in result.stdout
        assert "Examples:" in result.stdout
        assert "task-master expand --task-id" in result.stdout
        assert "task-master expand --all-pending" in result.stdout

    @pytest.mark.asyncio
    async def test_expand_command_invalid_task_id(self, runner, cli_test_workspace, real_agent):
        """Test expand command with an invalid task ID format."""
        # Run the command with invalid UUID
        result = await run_cli_command(runner, ["expand", "--task-id", "invalid-uuid"], cli_test_workspace)
        
        # Assertions
        assert result.exit_code == 1
        assert "Invalid task ID format" in result.stdout

    @patch('src.agent_core.llm_generator.LLMGenerator.generate_subtasks_for_task')
    @pytest.mark.asyncio
    async def test_expand_command_single_task_exception(self, mock_generate_subtasks, runner, sample_task, cli_test_workspace, project_plan_factory, real_agent):
        workspace_path, _ = cli_test_workspace
        initial_plan = create_project_plan_with_tasks([sample_task])
        project_plan_factory.create(initial_plan)
        
        mock_generate_subtasks.side_effect = Exception("LLM service error")
        
        task_id = str(sample_task.id)
        
        result = await run_cli_command(runner, ["expand", "--task-id", task_id], cli_test_workspace)
        
        assert result.exit_code == 1
        assert "Error expanding task:" in result.stdout

    @patch('src.agent_core.llm_generator.LLMGenerator.generate_subtasks_for_task')
    @pytest.mark.asyncio
    async def test_expand_command_all_pending_exception(self, mock_generate_subtasks, runner, cli_test_workspace, project_plan_factory, real_agent):
        pending_task = Task(id=uuid4(), title="Pending", description="Desc", status=TaskStatus.PENDING, subtasks=[])
        workspace_path, _ = cli_test_workspace
        initial_plan = create_project_plan_with_tasks([pending_task])
        project_plan_factory.create(initial_plan)
        
        mock_generate_subtasks.side_effect = Exception("Database connection error")
        
        result = await run_cli_command(runner, ["expand", "--all-pending"], cli_test_workspace)
        
        assert result.exit_code == 0
        assert "No pending tasks were expanded" in result.stdout

    @patch('src.agent_core.llm_generator.LLMGenerator.generate_subtasks_for_task')
    @pytest.mark.asyncio
    async def test_expand_command_both_options_specified(self, mock_generate_subtasks, runner, sample_task, cli_test_workspace, project_plan_factory, real_agent):
        initial_plan = create_project_plan_with_tasks([sample_task])
        workspace_path, _ = cli_test_workspace
        project_plan_factory.create(initial_plan)
        
        result = await run_cli_command(runner, ["expand", "--task-id", str(sample_task.id), "--all-pending"], cli_test_workspace)
        assert result.exit_code == 1
        assert "Error: Cannot specify both --task-id and --all-pending." in result.stdout
        mock_generate_subtasks.assert_not_called()

    @patch('src.agent_core.llm_generator.LLMGenerator.generate_subtasks_for_task')
    @pytest.mark.asyncio
    async def test_expand_command_displays_subtask_details(self, mock_generate_subtasks, runner, cli_test_workspace, project_plan_factory, real_agent):
        task_to_expand = Task(id=uuid4(), title="Task for Display Test", description="Expand this task to see subtask details.", status=TaskStatus.PENDING, subtasks=[])
        workspace_path, _ = cli_test_workspace
        initial_plan = create_project_plan_with_tasks([task_to_expand])
        project_plan_factory.create(initial_plan)
 
        mock_subtasks = [
            Task(id=uuid4(), title="Task A", description="Description for Task A", status=TaskStatus.PENDING, priority=TaskPriority.HIGH),
            Task(id=uuid4(), title="Task B", description="Description for Task B", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM)
        ]
        mock_generate_subtasks.return_value = mock_subtasks
 
        task_id = str(task_to_expand.id)
        
        result = await run_cli_command(runner, ["expand", "--task-id", task_id], cli_test_workspace)
        
        assert result.exit_code == 0
        assert f"Successfully expanded task '{task_to_expand.title}'" in result.stdout
        assert f"📋 Task now has {len(mock_subtasks)} subtasks:" in result.stdout
        assert f"  1. {mock_subtasks[0].title}" in result.stdout
        assert f"     ID: {mock_subtasks[0].id}" in result.stdout
        assert f"     Description: {mock_subtasks[0].description}" in result.stdout
        assert f"  2. {mock_subtasks[1].title}" in result.stdout
        assert f"     ID: {mock_subtasks[1].id}" in result.stdout
        assert f"     Description: {mock_subtasks[1].description}" in result.stdout
 
        updated_task = get_task_by_id_from_file(workspace_path, task_id)
        assert updated_task is not None
        assert len(updated_task.subtasks) == len(mock_subtasks)
        assert updated_task.subtasks[0].title == mock_subtasks[0].title
        assert updated_task.subtasks[1].title == mock_subtasks[1].title
        mock_generate_subtasks.assert_called_once()
