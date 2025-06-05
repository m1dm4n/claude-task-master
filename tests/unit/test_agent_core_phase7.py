"""Unit tests for Phase 7: Task Management (Clearing) functionality in agent core."""

import pytest
from unittest.mock import Mock, patch
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
def sample_task_with_subtasks():
    """Create a sample task with subtasks for testing."""
    subtasks = [
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
        mock_agent.task_operations.get_item_by_id.return_value = sample_task_with_subtasks
        mock_agent.project_io.get_current_project_plan.return_value = Mock()
        mock_agent.project_io.save_project_plan.return_value = None
        
        assert len(sample_task_with_subtasks.subtasks) == 2
        
        result = mock_agent.clear_subtasks_for_task(sample_task_with_subtasks.id)
        
        assert result is True
        assert len(sample_task_with_subtasks.subtasks) == 0
        
        mock_agent.task_operations.get_item_by_id.assert_called_once_with(sample_task_with_subtasks.id)
        mock_agent.project_io.save_project_plan.assert_called_once()

    def test_clear_subtasks_for_task_handles_task_not_found(self, mock_agent):
        mock_agent.task_operations.get_item_by_id.return_value = None
        
        result = mock_agent.clear_subtasks_for_task(uuid4())
        
        assert result is False
        mock_agent.task_operations.get_item_by_id.assert_called_once()

    def test_clear_subtasks_for_task_handles_non_task_item(self, mock_agent):
        subtask = Task(
            id=uuid4(),
            title="Test Task",
            description="A test subtask",
            status=TaskStatus.PENDING
        )
        mock_agent.task_operations.get_item_by_id.return_value = subtask
        
        result = mock_agent.clear_subtasks_for_task(subtask.id)
        
        assert result is False
        mock_agent.task_operations.get_item_by_id.assert_called_once()

    def test_clear_subtasks_for_task_handles_no_subtasks_to_clear(self, mock_agent, sample_task_without_subtasks):
        mock_agent.task_operations.get_item_by_id.return_value = sample_task_without_subtasks
        mock_agent.project_io.get_current_project_plan.return_value = Mock()
        mock_agent.project_io.save_project_plan.return_value = None
        
        assert len(sample_task_without_subtasks.subtasks) == 0
        
        result = mock_agent.clear_subtasks_for_task(sample_task_without_subtasks.id)
        
        assert result is True
        assert len(sample_task_without_subtasks.subtasks) == 0
        
        mock_agent.task_operations.get_item_by_id.assert_called_once_with(sample_task_without_subtasks.id)
        mock_agent.project_io.save_project_plan.assert_not_called()


class TestClearSubtasksForAllTasks:
    """Test cases for clear_subtasks_for_all_tasks method."""

    def test_clear_subtasks_for_all_tasks_affects_all_relevant_tasks(self, mock_agent):
        task_with_subtasks1 = Task(
            id=uuid4(),
            title="Task with Subtasks 1",
            description="First task with subtasks",
            status=TaskStatus.PENDING,
            subtasks=[
                Task(id=uuid4(), title="Sub 1", description="Desc 1", status=TaskStatus.PENDING),
                Task(id=uuid4(), title="Sub 2", description="Desc 2", status=TaskStatus.PENDING)
            ]
        )
        task_with_subtasks2 = Task(
            id=uuid4(),
            title="Task with Subtasks 2",
            description="Second task with subtasks",
            status=TaskStatus.IN_PROGRESS,
            subtasks=[
                Task(id=uuid4(), title="Sub 3", description="Desc 3", status=TaskStatus.PENDING)
            ]
        )
        task_without_subtasks = Task(
            id=uuid4(),
            title="Task without Subtasks",
            description="Task with no subtasks",
            status=TaskStatus.COMPLETED,
            subtasks=[]
        )
        
        mock_agent.get_all_tasks.return_value = [task_with_subtasks1, task_with_subtasks2, task_without_subtasks]
        mock_agent.project_io.get_current_project_plan.return_value = Mock()
        mock_agent.project_io.save_project_plan.return_value = None
        
        assert len(task_with_subtasks1.subtasks) == 2
        assert len(task_with_subtasks2.subtasks) == 1
        assert len(task_without_subtasks.subtasks) == 0
        
        result = mock_agent.clear_subtasks_for_all_tasks()
        
        assert result == 2
        assert len(task_with_subtasks1.subtasks) == 0
        assert len(task_with_subtasks2.subtasks) == 0
        assert len(task_without_subtasks.subtasks) == 0
        
        mock_agent.get_all_tasks.assert_called_once()
        mock_agent.project_io.save_project_plan.assert_called_once()

    def test_clear_subtasks_for_all_tasks_handles_no_tasks_with_subtasks(self, mock_agent):
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
        
        mock_agent.get_all_tasks.return_value = [task1, task2]
        mock_agent.project_io.save_project_plan.return_value = None
        
        result = mock_agent.clear_subtasks_for_all_tasks()
        
        assert result == 0
        
        mock_agent.get_all_tasks.assert_called_once()
        mock_agent.project_io.save_project_plan.assert_not_called()

    def test_clear_subtasks_for_all_tasks_handles_empty_task_list(self, mock_agent):
        mock_agent.get_all_tasks.return_value = []
        mock_agent.project_io.save_project_plan.return_value = None
        
        result = mock_agent.clear_subtasks_for_all_tasks()
        
        assert result == 0
        
        mock_agent.get_all_tasks.assert_called_once()
        mock_agent.project_io.save_project_plan.assert_not_called()