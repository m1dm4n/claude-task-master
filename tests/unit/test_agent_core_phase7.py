"""Unit tests for Phase 7: Subtask Management (Clearing) functionality in agent core."""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4, UUID
from datetime import datetime, timezone

from src.agent_core.main import DevTaskAIAssistant
from src.data_models import Task, Subtask, TaskStatus, TaskPriority


@pytest.fixture
def mock_agent():
    """Create a mock DevTaskAIAssistant for testing."""
    agent = Mock(spec=DevTaskAIAssistant)
    agent.clear_subtasks_for_task = Mock()
    agent.clear_subtasks_for_all_tasks = Mock()
    return agent


@pytest.fixture
def sample_task_with_subtasks():
    """Create a sample task with subtasks for testing."""
    subtasks = [
        Subtask(
            id=uuid4(),
            title="Subtask 1",
            description="First subtask",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH
        ),
        Subtask(
            id=uuid4(),
            title="Subtask 2", 
            description="Second subtask",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM
        )
    ]
    
    return Task(
        id=uuid4(),
        title="Sample Task",
        description="A sample task for testing",
        status=TaskStatus.PENDING,
        priority=TaskPriority.MEDIUM,
        subtasks=subtasks
    )


@pytest.fixture
def sample_task_without_subtasks():
    """Create a sample task without subtasks for testing."""
    return Task(
        id=uuid4(),
        title="Empty Task",
        description="A task without subtasks",
        status=TaskStatus.PENDING,
        priority=TaskPriority.MEDIUM,
        subtasks=[]
    )


class TestClearSubtasksForTask:
    """Test cases for clear_subtasks_for_task method."""

    def test_clear_subtasks_for_task_removes_subtasks_and_updates_plan(self, mocker, sample_task_with_subtasks):
        """Test that clear_subtasks_for_task removes subtasks and updates the plan."""
        # Setup mocks
        mock_task_manager = Mock()
        mock_task_manager.get_item_by_id.return_value = sample_task_with_subtasks
        
        mock_project_manager = Mock()
        mock_project_plan = Mock()
        mock_project_manager.get_current_project_plan.return_value = mock_project_plan
        mock_project_manager.save_project_plan = Mock()
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        agent.project_manager = mock_project_manager
        
        # Verify task has subtasks initially
        assert len(sample_task_with_subtasks.subtasks) == 2
        
        # Test the method
        result = agent.clear_subtasks_for_task(sample_task_with_subtasks.id)
        
        # Assertions
        assert result is True
        assert len(sample_task_with_subtasks.subtasks) == 0
        
        # Verify mocks were called correctly
        mock_task_manager.get_item_by_id.assert_called_once_with(sample_task_with_subtasks.id)
        mock_project_manager.save_project_plan.assert_called_once()

    def test_clear_subtasks_for_task_handles_task_not_found(self, mocker):
        """Test that clear_subtasks_for_task handles task not found scenario."""
        # Setup mocks
        mock_task_manager = Mock()
        mock_task_manager.get_item_by_id.return_value = None
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        
        # Test the method
        result = agent.clear_subtasks_for_task(uuid4())
        
        # Assertions
        assert result is False
        mock_task_manager.get_item_by_id.assert_called_once()

    def test_clear_subtasks_for_task_handles_non_task_item(self, mocker):
        """Test that clear_subtasks_for_task handles when item is not a Task."""
        # Setup mocks - return a Subtask instead of Task
        subtask = Subtask(
            id=uuid4(),
            title="Test Subtask",
            description="A test subtask",
            status=TaskStatus.PENDING
        )
        mock_task_manager = Mock()
        mock_task_manager.get_item_by_id.return_value = subtask
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        
        # Test the method
        result = agent.clear_subtasks_for_task(subtask.id)
        
        # Assertions
        assert result is False
        mock_task_manager.get_item_by_id.assert_called_once()

    def test_clear_subtasks_for_task_handles_no_subtasks_to_clear(self, mocker, sample_task_without_subtasks):
        """Test that clear_subtasks_for_task handles tasks with no subtasks."""
        # Setup mocks
        mock_task_manager = Mock()
        mock_task_manager.get_item_by_id.return_value = sample_task_without_subtasks
        
        mock_project_manager = Mock()
        mock_project_plan = Mock()
        mock_project_manager.get_current_project_plan.return_value = mock_project_plan
        mock_project_manager.save_project_plan = Mock()
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        agent.project_manager = mock_project_manager
        
        # Verify task has no subtasks initially
        assert len(sample_task_without_subtasks.subtasks) == 0
        
        # Test the method
        result = agent.clear_subtasks_for_task(sample_task_without_subtasks.id)
        
        # Assertions
        assert result is True  # Should still return True since goal is achieved
        assert len(sample_task_without_subtasks.subtasks) == 0
        
        # Verify mocks were called correctly
        mock_task_manager.get_item_by_id.assert_called_once_with(sample_task_without_subtasks.id)
        # save_project_plan should not be called since no changes were made
        mock_project_manager.save_project_plan.assert_not_called()


class TestClearSubtasksForAllTasks:
    """Test cases for clear_subtasks_for_all_tasks method."""

    def test_clear_subtasks_for_all_tasks_affects_all_relevant_tasks(self, mocker):
        """Test that clear_subtasks_for_all_tasks affects all relevant tasks."""
        # Create test tasks
        task_with_subtasks1 = Task(
            id=uuid4(),
            title="Task with Subtasks 1",
            description="First task with subtasks",
            status=TaskStatus.PENDING,
            subtasks=[
                Subtask(id=uuid4(), title="Sub 1", description="Desc 1", status=TaskStatus.PENDING),
                Subtask(id=uuid4(), title="Sub 2", description="Desc 2", status=TaskStatus.PENDING)
            ]
        )
        task_with_subtasks2 = Task(
            id=uuid4(),
            title="Task with Subtasks 2",
            description="Second task with subtasks",
            status=TaskStatus.IN_PROGRESS,
            subtasks=[
                Subtask(id=uuid4(), title="Sub 3", description="Desc 3", status=TaskStatus.PENDING)
            ]
        )
        task_without_subtasks = Task(
            id=uuid4(),
            title="Task without Subtasks",
            description="Task with no subtasks",
            status=TaskStatus.COMPLETED,
            subtasks=[]
        )
        
        # Setup mocks
        mock_task_manager = Mock()
        mock_task_manager.get_all_tasks.return_value = [task_with_subtasks1, task_with_subtasks2, task_without_subtasks]
        
        mock_project_manager = Mock()
        mock_project_plan = Mock()
        mock_project_manager.get_current_project_plan.return_value = mock_project_plan
        mock_project_manager.save_project_plan = Mock()
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        agent.project_manager = mock_project_manager
        
        # Verify initial state
        assert len(task_with_subtasks1.subtasks) == 2
        assert len(task_with_subtasks2.subtasks) == 1
        assert len(task_without_subtasks.subtasks) == 0
        
        # Test the method
        result = agent.clear_subtasks_for_all_tasks()
        
        # Assertions
        assert result == 2  # Two tasks had subtasks cleared
        assert len(task_with_subtasks1.subtasks) == 0
        assert len(task_with_subtasks2.subtasks) == 0
        assert len(task_without_subtasks.subtasks) == 0  # Unchanged
        
        # Verify mocks were called correctly
        mock_task_manager.get_all_tasks.assert_called_once()
        mock_project_manager.save_project_plan.assert_called_once()

    def test_clear_subtasks_for_all_tasks_handles_no_tasks_with_subtasks(self, mocker):
        """Test that clear_subtasks_for_all_tasks handles when no tasks have subtasks."""
        # Create test tasks without subtasks
        task1 = Task(
            id=uuid4(),
            title="Task 1",
            description="First task",
            status=TaskStatus.PENDING,
            subtasks=[]
        )
        task2 = Task(
            id=uuid4(),
            title="Task 2",
            description="Second task",
            status=TaskStatus.COMPLETED,
            subtasks=[]
        )
        
        # Setup mocks
        mock_task_manager = Mock()
        mock_task_manager.get_all_tasks.return_value = [task1, task2]
        
        mock_project_manager = Mock()
        mock_project_manager.save_project_plan = Mock()
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        agent.project_manager = mock_project_manager
        
        # Test the method
        result = agent.clear_subtasks_for_all_tasks()
        
        # Assertions
        assert result == 0  # No tasks had subtasks to clear
        
        # Verify mocks were called correctly
        mock_task_manager.get_all_tasks.assert_called_once()
        # save_project_plan should not be called when no tasks are modified
        mock_project_manager.save_project_plan.assert_not_called()

    def test_clear_subtasks_for_all_tasks_handles_empty_task_list(self, mocker):
        """Test that clear_subtasks_for_all_tasks handles when there are no tasks."""
        # Setup mocks
        mock_task_manager = Mock()
        mock_task_manager.get_all_tasks.return_value = []
        
        mock_project_manager = Mock()
        mock_project_manager.save_project_plan = Mock()
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        agent.project_manager = mock_project_manager
        
        # Test the method
        result = agent.clear_subtasks_for_all_tasks()
        
        # Assertions
        assert result == 0
        
        # Verify mocks were called correctly
        mock_task_manager.get_all_tasks.assert_called_once()
        # save_project_plan should not be called when no tasks exist
        mock_project_manager.save_project_plan.assert_not_called()