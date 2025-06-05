"""Unit tests for Phase 6: Task Expansion (Subtasks) functionality in agent core."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4, UUID
from datetime import datetime, timezone

from src.agent_core.assistant import DevTaskAIAssistant
from src.agent_core.project_io import ProjectIO
from src.agent_core.task_operations import TaskOperations
from src.agent_core.llm_config import LLMConfigManager
from src.agent_core.llm_provider import LLMProvider
from src.agent_core.llm_generator import LLMGenerator
from src.agent_core.plan_builder import PlanBuilder
from src.agent_core.dependency_logic import DependencyManager
from src.data_models import Task, TaskStatus, TaskPriority, AppConfig, ModelConfig
from src.config_manager import ConfigManager


@pytest.fixture
def mock_agent():
    """Create a DevTaskAIAssistant instance with mocked dependencies."""
    with patch('src.config_manager.ConfigManager') as MockConfigManager, \
         patch('src.agent_core.llm_config.LLMConfigManager') as MockLLMConfigManager, \
         patch('src.agent_core.llm_provider.LLMProvider') as MockLLMProvider, \
         patch('src.agent_core.llm_generator.LLMGenerator') as MockLLMGenerator, \
         patch('src.agent_core.plan_builder.PlanBuilder') as MockPlanBuilder, \
         patch('src.agent_core.project_io.ProjectIO') as MockProjectIO, \
         patch('src.agent_core.task_operations.TaskOperations') as MockTaskOperations, \
         patch('src.agent_core.dependency_logic.DependencyManager') as MockDependencyManager:

        mock_config_manager_instance = MockConfigManager.return_value
        test_config = AppConfig(
            main_model=ModelConfig(model_name="test-model", provider="test"),
            project_plan_file="project_plan.json",
            tasks_dir="tasks"
        )
        mock_config_manager_instance.config = test_config
        mock_config_manager_instance.get_model_config.return_value = test_config.main_model

        mock_project_io_instance = MockProjectIO.return_value
        mock_project_io_instance.get_current_project_plan.return_value = Mock() # Default to a mock plan
        mock_project_io_instance.save_project_plan.return_value = None

        agent_instance = DevTaskAIAssistant("dummy_workspace")
        agent_instance.config_manager = mock_config_manager_instance
        agent_instance.llm_config_manager = MockLLMConfigManager.return_value
        agent_instance.llm_provider = MockLLMProvider.return_value
        agent_instance.llm_generator = MockLLMGenerator.return_value
        agent_instance.plan_builder = MockPlanBuilder.return_value
        agent_instance.project_io = mock_project_io_instance
        agent_instance.task_operations = MockTaskOperations.return_value
        agent_instance.dependency_manager = MockDependencyManager.return_value

        yield agent_instance


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
            title="Task 1",
            description="First subtask",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH
        ),
        Task(
            id=uuid4(),
            title="Task 2", 
            description="Second subtask",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM
        )
    ]


class TestExpandTaskWithSubtasks:
    """Test cases for expand_task_with_subtasks method."""

    @pytest.mark.asyncio
    async def test_expand_task_with_subtasks_adds_subtasks_and_updates_plan(self, mock_agent, sample_task, sample_subtasks):
        """Test that expand_task_with_subtasks adds subtasks and updates the plan."""
        # Setup mocks
        mock_agent.task_operations.get_item_by_id.return_value = sample_task
        mock_agent.task_operations.update_task_in_plan.return_value = True
        mock_agent.llm_generator.generate_subtasks_for_task.return_value = sample_subtasks
        mock_agent.project_io.get_current_project_plan.return_value = Mock()
        mock_agent.project_io.save_project_plan.return_value = None
        
        result = await mock_agent.expand_task_with_subtasks(sample_task.id, num_subtasks=2)
        
        assert result is not None
        assert result.id == sample_task.id
        assert len(result.subtasks) == 2
        assert result.subtasks == sample_subtasks
        
        mock_agent.task_operations.get_item_by_id.assert_called_once_with(sample_task.id)
        mock_agent.llm_generator.generate_subtasks_for_task.assert_called_once()
        mock_agent.project_io.save_project_plan.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_expand_task_with_subtasks_handles_task_not_found(self, mock_agent):
        mock_agent.task_operations.get_item_by_id.return_value = None
        
        result = await mock_agent.expand_task_with_subtasks(uuid4())
        
        assert result is None
        mock_agent.task_operations.get_item_by_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_expand_task_with_subtasks_handles_non_task_item(self, mock_agent, sample_subtasks):
        subtask = sample_subtasks[0]
        mock_agent.task_operations.get_item_by_id.return_value = subtask
        
        result = await mock_agent.expand_task_with_subtasks(subtask.id)
        
        assert result is None
        mock_agent.task_operations.get_item_by_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_expand_task_with_subtasks_uses_research_model(self, mock_agent, sample_task, sample_subtasks):
        mock_agent.task_operations.get_item_by_id.return_value = sample_task
        mock_agent.task_operations.update_task_in_plan.return_value = True
        mock_agent.llm_generator.generate_subtasks_for_task.return_value = sample_subtasks
        mock_agent.project_io.get_current_project_plan.return_value = Mock()
        mock_agent.project_io.save_project_plan.return_value = None
        
        result = await mock_agent.expand_task_with_subtasks(sample_task.id, use_research=True)
        
        call_args = mock_agent.llm_generator.generate_subtasks_for_task.call_args
        assert call_args[1]['model_type'] == "research"
class TestExpandAllPendingTasks:
    """Test cases for expand_all_pending_tasks method."""

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_expand_all_pending_tasks_calls_expand_on_correct_tasks(self, mock_agent, sample_subtasks):
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
        
        mock_agent.get_all_tasks.return_value = [pending_task1, pending_task2, completed_task]
        mock_agent.project_io.get_current_project_plan.return_value = Mock()
        mock_agent.project_io.save_project_plan.return_value = None
        
        mock_agent.expand_task_with_subtasks = AsyncMock()
        mock_agent.expand_task_with_subtasks.side_effect = [pending_task1, pending_task2]
        
        result = await mock_agent.expand_all_pending_tasks()
        
        assert result == 2
        assert mock_agent.expand_task_with_subtasks.call_count == 2
        call_args_list = mock_agent.expand_task_with_subtasks.call_args_list
        called_task_ids = {call[0][0] for call in call_args_list} # task_id is now first positional arg
        assert pending_task1.id in called_task_ids
        assert pending_task2.id in called_task_ids
        assert completed_task.id not in called_task_ids

    @pytest.mark.asyncio
    async def test_expand_all_pending_tasks_skips_tasks_with_existing_subtasks(self, mock_agent, sample_subtasks):
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
        
        mock_agent.get_all_tasks.return_value = [pending_task_no_subtasks, pending_task_with_subtasks]
        mock_agent.project_io.get_current_project_plan.return_value = Mock()
        mock_agent.project_io.save_project_plan.return_value = None
        
        mock_agent.expand_task_with_subtasks = AsyncMock(return_value=pending_task_no_subtasks)
        
        result = await mock_agent.expand_all_pending_tasks() # Removed force_regeneration
        
        assert result == 1
        mock_agent.expand_task_with_subtasks.assert_called_once_with(
            pending_task_no_subtasks.id, # task_id is now first positional arg
            None, # num_subtasks
            None, # prompt_override
            False # use_research
        )

    @pytest.mark.asyncio
    async def test_expand_all_pending_tasks_with_force_regeneration(self, mock_agent, sample_subtasks):
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
        
        mock_agent.get_all_tasks.return_value = [pending_task_no_subtasks, pending_task_with_subtasks]
        mock_agent.project_io.get_current_project_plan.return_value = Mock()
        mock_agent.project_io.save_project_plan.return_value = None
        
        mock_agent.expand_task_with_subtasks = AsyncMock()
        mock_agent.expand_task_with_subtasks.side_effect = [pending_task_no_subtasks, pending_task_with_subtasks]
        
        result = await mock_agent.expand_all_pending_tasks() # Removed force_regeneration
        
        assert result == 2
        assert mock_agent.expand_task_with_subtasks.call_count == 2

    @pytest.mark.asyncio
    async def test_expand_all_pending_tasks_handles_no_pending_tasks(self, mock_agent):
        mock_agent.get_all_tasks.return_value = []
        mock_agent.project_io.get_current_project_plan.return_value = Mock()
        
        result = await mock_agent.expand_all_pending_tasks()
        
        assert result == 0
        mock_agent.project_io.save_project_plan.assert_not_called()