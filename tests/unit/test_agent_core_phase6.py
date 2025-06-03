"""Unit tests for Phase 6: Task Expansion (Subtasks) functionality in agent core."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4, UUID
from datetime import datetime, timezone

from src.agent_core.main import DevTaskAIAssistant
from src.data_models import Task, Subtask, TaskStatus, TaskPriority


@pytest.fixture
def mock_agent():
    """Create a mock DevTaskAIAssistant for testing."""
    agent = Mock(spec=DevTaskAIAssistant)
    agent.expand_task_with_subtasks = AsyncMock()
    agent.expand_all_pending_tasks = AsyncMock()
    return agent


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


class TestExpandTaskWithSubtasks:
    """Test cases for expand_task_with_subtasks method."""

    @pytest.mark.asyncio
    async def test_expand_task_with_subtasks_adds_subtasks_and_updates_plan(self, mocker, sample_task, sample_subtasks):
        """Test that expand_task_with_subtasks adds subtasks and updates the plan."""
        # Setup mocks
        mock_task_manager = Mock()
        mock_task_manager.get_item_by_id.return_value = sample_task
        mock_task_manager.update_task_in_plan.return_value = True
        
        mock_llm_manager = Mock()
        mock_llm_manager.generate_subtasks_for_task = AsyncMock(return_value=sample_subtasks)
        
        mock_project_manager = Mock()
        mock_project_manager.get_current_project_plan.return_value = Mock()
        mock_project_manager.save_project_plan = Mock()
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        agent.llm_manager = mock_llm_manager
        agent.project_manager = mock_project_manager
        
        # Test the method
        result = await agent.expand_task_with_subtasks(sample_task.id, num_subtasks=2)
        
        # Assertions
        assert result is not None
        assert result.id == sample_task.id
        assert len(result.subtasks) == 2
        assert result.subtasks == sample_subtasks
        
        # Verify mocks were called correctly
        mock_task_manager.get_item_by_id.assert_called_once_with(sample_task.id)
        mock_llm_manager.generate_subtasks_for_task.assert_called_once()
        mock_task_manager.update_task_in_plan.assert_called_once_with(sample_task.id, result)
        mock_project_manager.save_project_plan.assert_called_once()

    @pytest.mark.asyncio
    async def test_expand_task_with_subtasks_handles_task_not_found(self, mocker):
        """Test that expand_task_with_subtasks handles task not found scenario."""
        # Setup mocks
        mock_task_manager = Mock()
        mock_task_manager.get_item_by_id.return_value = None
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        
        # Test the method
        result = await agent.expand_task_with_subtasks(uuid4())
        
        # Assertions
        assert result is None
        mock_task_manager.get_item_by_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_expand_task_with_subtasks_handles_non_task_item(self, mocker, sample_subtasks):
        """Test that expand_task_with_subtasks handles when item is not a Task."""
        # Setup mocks - return a Subtask instead of Task
        subtask = sample_subtasks[0]
        mock_task_manager = Mock()
        mock_task_manager.get_item_by_id.return_value = subtask
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        
        # Test the method
        result = await agent.expand_task_with_subtasks(subtask.id)
        
        # Assertions
        assert result is None
        mock_task_manager.get_item_by_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_expand_task_with_subtasks_uses_research_model(self, mocker, sample_task, sample_subtasks):
        """Test that expand_task_with_subtasks uses research model when specified."""
        # Setup mocks
        mock_task_manager = Mock()
        mock_task_manager.get_item_by_id.return_value = sample_task
        mock_task_manager.update_task_in_plan.return_value = True
        
        mock_llm_manager = Mock()
        mock_llm_manager.generate_subtasks_for_task = AsyncMock(return_value=sample_subtasks)
        
        mock_project_manager = Mock()
        mock_project_manager.get_current_project_plan.return_value = Mock()
        mock_project_manager.save_project_plan = Mock()
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        agent.llm_manager = mock_llm_manager
        agent.project_manager = mock_project_manager
        
        # Test the method with research model
        result = await agent.expand_task_with_subtasks(sample_task.id, use_research=True)
        
        # Verify the research model was requested
        call_args = mock_llm_manager.generate_subtasks_for_task.call_args
        assert call_args[1]['model_type'] == "research"


class TestExpandAllPendingTasks:
    """Test cases for expand_all_pending_tasks method."""

    @pytest.mark.asyncio
    async def test_expand_all_pending_tasks_calls_expand_on_correct_tasks(self, mocker, sample_subtasks):
        """Test that expand_all_pending_tasks calls expand on pending tasks correctly."""
        # Create test tasks
        pending_task1 = Task(
            id=uuid4(),
            title="Pending Task 1",
            description="First pending task",
            status=TaskStatus.PENDING,
            subtasks=[]
        )
        pending_task2 = Task(
            id=uuid4(),
            title="Pending Task 2", 
            description="Second pending task",
            status=TaskStatus.PENDING,
            subtasks=[]
        )
        completed_task = Task(
            id=uuid4(),
            title="Completed Task",
            description="Already completed task",
            status=TaskStatus.COMPLETED,
            subtasks=[]
        )
        
        # Setup mocks
        mock_task_manager = Mock()
        mock_task_manager.get_all_tasks.return_value = [pending_task1, pending_task2, completed_task]
        
        mock_project_manager = Mock()
        mock_project_manager.get_current_project_plan.return_value = Mock()
        mock_project_manager.save_project_plan = Mock()
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        agent.project_manager = mock_project_manager
        
        # Mock the expand_task_with_subtasks method
        agent.expand_task_with_subtasks = AsyncMock()
        agent.expand_task_with_subtasks.side_effect = [pending_task1, pending_task2]
        
        # Test the method
        result = await agent.expand_all_pending_tasks()
        
        # Assertions
        assert result == 2  # Two pending tasks were expanded
        
        # Verify expand_task_with_subtasks was called for pending tasks only
        assert agent.expand_task_with_subtasks.call_count == 2
        call_args_list = agent.expand_task_with_subtasks.call_args_list
        called_task_ids = {call[1]['task_id'] for call in call_args_list}
        assert pending_task1.id in called_task_ids
        assert pending_task2.id in called_task_ids
        assert completed_task.id not in called_task_ids

    @pytest.mark.asyncio
    async def test_expand_all_pending_tasks_skips_tasks_with_existing_subtasks(self, mocker, sample_subtasks):
        """Test that expand_all_pending_tasks skips tasks that already have subtasks unless force_regeneration is True."""
        # Create test tasks
        pending_task_no_subtasks = Task(
            id=uuid4(),
            title="Pending Task No Subtasks",
            description="Pending task without subtasks",
            status=TaskStatus.PENDING,
            subtasks=[]
        )
        pending_task_with_subtasks = Task(
            id=uuid4(),
            title="Pending Task With Subtasks",
            description="Pending task with existing subtasks",
            status=TaskStatus.PENDING,
            subtasks=sample_subtasks
        )
        
        # Setup mocks
        mock_task_manager = Mock()
        mock_task_manager.get_all_tasks.return_value = [pending_task_no_subtasks, pending_task_with_subtasks]
        
        mock_project_manager = Mock()
        mock_project_manager.get_current_project_plan.return_value = Mock()
        mock_project_manager.save_project_plan = Mock()
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        agent.project_manager = mock_project_manager
        
        # Mock the expand_task_with_subtasks method
        agent.expand_task_with_subtasks = AsyncMock(return_value=pending_task_no_subtasks)
        
        # Test the method without force_regeneration
        result = await agent.expand_all_pending_tasks(force_regeneration=False)
        
        # Should only expand the task without subtasks
        assert result == 1
        agent.expand_task_with_subtasks.assert_called_once_with(
            task_id=pending_task_no_subtasks.id,
            num_subtasks=None,
            use_research=False
        )

    @pytest.mark.asyncio
    async def test_expand_all_pending_tasks_with_force_regeneration(self, mocker, sample_subtasks):
        """Test that expand_all_pending_tasks expands all pending tasks when force_regeneration is True."""
        # Create test tasks
        pending_task_no_subtasks = Task(
            id=uuid4(),
            title="Pending Task No Subtasks",
            description="Pending task without subtasks",
            status=TaskStatus.PENDING,
            subtasks=[]
        )
        pending_task_with_subtasks = Task(
            id=uuid4(),
            title="Pending Task With Subtasks",
            description="Pending task with existing subtasks",
            status=TaskStatus.PENDING,
            subtasks=sample_subtasks
        )
        
        # Setup mocks
        mock_task_manager = Mock()
        mock_task_manager.get_all_tasks.return_value = [pending_task_no_subtasks, pending_task_with_subtasks]
        
        mock_project_manager = Mock()
        mock_project_manager.get_current_project_plan.return_value = Mock()
        mock_project_manager.save_project_plan = Mock()
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        agent.project_manager = mock_project_manager
        
        # Mock the expand_task_with_subtasks method
        agent.expand_task_with_subtasks = AsyncMock()
        agent.expand_task_with_subtasks.side_effect = [pending_task_no_subtasks, pending_task_with_subtasks]
        
        # Test the method with force_regeneration
        result = await agent.expand_all_pending_tasks(force_regeneration=True)
        
        # Should expand both tasks
        assert result == 2
        assert agent.expand_task_with_subtasks.call_count == 2

    @pytest.mark.asyncio
    async def test_expand_all_pending_tasks_handles_no_pending_tasks(self, mocker):
        """Test that expand_all_pending_tasks handles when there are no pending tasks."""
        # Setup mocks
        mock_task_manager = Mock()
        mock_task_manager.get_all_tasks.return_value = []
        
        mock_project_manager = Mock()
        mock_project_manager.get_current_project_plan.return_value = Mock()
        
        # Create agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.task_manager = mock_task_manager
        agent.project_manager = mock_project_manager
        
        # Test the method
        result = await agent.expand_all_pending_tasks()
        
        # Should return 0
        assert result == 0
        # Save should not be called when no tasks are expanded
        mock_project_manager.save_project_plan.assert_not_called()