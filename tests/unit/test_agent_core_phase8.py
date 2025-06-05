"""Unit tests for Phase 8: Single Task/Task Refinement functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from uuid import uuid4, UUID
from datetime import datetime, timezone

from src.agent_core.assistant import DevTaskAIAssistant
from src.agent_core.llm_generator import LLMGenerator
from src.agent_core.project_io import ProjectIO
from src.agent_core.task_operations import TaskOperations
from src.data_models import Task, TaskStatus, TaskPriority, ProjectPlan, AppConfig, ModelConfig
from src.config_manager import ConfigManager

pytestmark = pytest.mark.asyncio


class TestRefineTaskOrSubtask:
    """Test the refine_task_or_subtask method in DevTaskAIAssistant."""

    @pytest.fixture
    def mock_agent(self, tmp_path):
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
            mock_project_io_instance.get_current_project_plan.return_value = Mock()
            mock_project_io_instance.save_project_plan.return_value = None

            agent = DevTaskAIAssistant(str(tmp_path))
            agent.config_manager = mock_config_manager_instance
            agent.llm_config_manager = MockLLMConfigManager.return_value
            agent.llm_provider = MockLLMProvider.return_value
            agent.llm_generator = MockLLMGenerator.return_value
            agent.plan_builder = MockPlanBuilder.return_value
            agent.project_io = mock_project_io_instance
            agent.task_operations = MockTaskOperations.return_value
            agent.dependency_manager = MockDependencyManager.return_value
            
            agent.task_operations._find_item_and_context = MagicMock()
            agent.project_io.save_project_plan = MagicMock()
            agent.project_io.get_current_project_plan = MagicMock()
            agent.llm_generator.refine_item_details = AsyncMock()
            
            yield agent

    @pytest.fixture
    def sample_task(self):
        """Create a sample task for testing."""
        return Task(
            id=uuid4(),
            title="Original Task Title",
            description="Original task description",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

    @pytest.fixture
    def sample_subtask(self):
        """Create a sample subtask for testing."""
        return Task(
            id=uuid4(),
            title="Original Task Title",
            description="Original subtask description",
            status=TaskStatus.PENDING,
            priority=TaskPriority.LOW,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

    async def test_refine_task_or_subtask_updates_task_details(self, mock_agent, sample_task):
        """Test that refine_task_or_subtask successfully updates task details."""
        # Arrange
        task_id = sample_task.id
        refinement_instruction = "Change the priority to HIGH and update the description"
        
        # Create updated task data that the LLM manager should return
        updated_task = Task(
            id=sample_task.id,
            title="Updated Task Title",
            description="Updated task description with new requirements",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            created_at=sample_task.created_at,
            updated_at=datetime.now(timezone.utc)
        )
        
        # Mock task manager to return the task and its context
        mock_tasks_list = [sample_task]
        mock_agent.task_operations._find_item_and_context.return_value = (
            sample_task, mock_tasks_list, 0, None
        )
        
        mock_agent.llm_generator.refine_item_details.return_value = updated_task
        
        mock_project_plan = MagicMock()
        mock_agent.project_io.get_current_project_plan.return_value = mock_project_plan
        
        result = await mock_agent.refine_task_or_subtask(task_id, refinement_instruction, use_research=False)
        
        assert result is not None
        assert isinstance(result, Task)
        assert result.title == "Updated Task Title"
        assert result.priority == TaskPriority.HIGH
        assert result.id == sample_task.id
        assert result.created_at == sample_task.created_at
        
        mock_agent.llm_generator.refine_item_details.assert_called_once_with(
            sample_task, refinement_instruction, "main"
        )
        
        mock_agent.project_io.save_project_plan.assert_called_once_with(mock_project_plan)
        
        assert mock_tasks_list[0] == result

    async def test_refine_task_or_subtask_updates_subtask_details(self, mock_agent, sample_subtask):
        """Test that refine_task_or_subtask successfully updates subtask details."""
        # Arrange
        subtask_id = sample_subtask.id
        refinement_instruction = "Add test strategy and change status to IN_PROGRESS"
        
        # Create updated subtask data that the LLM manager should return
        updated_subtask = Task(
            id=sample_subtask.id,
            title=sample_subtask.title,
            description="Updated subtask description",
            status=TaskStatus.IN_PROGRESS,
            priority=sample_subtask.priority,
            testStrategy="Comprehensive unit testing required",
            created_at=sample_subtask.created_at,
            updated_at=datetime.now(timezone.utc)
        )
        
        # Create a parent task with subtasks
        parent_task = Task(
            id=uuid4(),
            title="Parent Task",
            description="Parent task description",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
            subtasks=[sample_subtask]
        )
        
        # Mock task manager to return the subtask and its context
        mock_agent.task_operations._find_item_and_context.return_value = (
            sample_subtask, parent_task.subtasks, 0, parent_task
        )
        
        mock_agent.llm_generator.refine_item_details.return_value = updated_subtask
        
        mock_project_plan = MagicMock()
        mock_agent.project_io.get_current_project_plan.return_value = mock_project_plan
        
        result = await mock_agent.refine_task_or_subtask(subtask_id, refinement_instruction, use_research=True)
        
        assert result is not None
        assert isinstance(result, Task)
        assert result.status == TaskStatus.IN_PROGRESS
        assert result.testStrategy == "Comprehensive unit testing required"
        assert result.id == sample_subtask.id
        assert result.created_at == sample_subtask.created_at
        
        mock_agent.llm_generator.refine_item_details.assert_called_once_with(
            sample_subtask, refinement_instruction, "research"
        )
        
        mock_agent.project_io.save_project_plan.assert_called_once_with(mock_project_plan)
        
        assert parent_task.subtasks[0] == result

    async def test_refine_task_or_subtask_handles_item_not_found(self, mock_agent):
        """Test that refine_task_or_subtask handles item not found correctly."""
        # Arrange
        non_existent_id = uuid4()
        refinement_instruction = "This should fail"
        
        # Mock task manager to return None (item not found)
        mock_agent.task_operations._find_item_and_context.return_value = (None, None, None, None)
        
        result = await mock_agent.refine_task_or_subtask(non_existent_id, refinement_instruction)
        
        assert result is None
        
        mock_agent.llm_generator.refine_item_details.assert_not_called()
        
        mock_agent.project_io.save_project_plan.assert_not_called()


class TestRefineItemDetails:
    """Test the refine_item_details method in LLMManager."""

    @pytest.fixture
    def mock_llm_manager(self):
        """Create an LLMManager with mocked dependencies."""
        with patch('src.config_manager.ConfigManager'), \
             patch('src.agent_core.llm_provider.LLMProvider'):
            
            llm_generator = LLMGenerator(MagicMock())
            llm_generator.llm_provider.generate_text = AsyncMock()
            
            return llm_generator

    @pytest.fixture
    def sample_task_for_llm(self):
        """Create a sample task for LLM testing."""
        return Task(
            id=uuid4(),
            title="LLM Test Task",
            description="Task for testing LLM refinement",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

    async def test_refine_item_details_llm_interaction(self, mock_agent, sample_task_for_llm):
        mock_llm_generator = mock_agent.llm_generator
        refinement_instruction = "Change priority to HIGH and add details"
        
        updated_task_mock = Task(
            id=sample_task_for_llm.id,
            title="Updated LLM Test Task",
            description="Updated task description with refinements",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            details="Added comprehensive implementation details",
            created_at=sample_task_for_llm.created_at,
            updated_at=datetime.now(timezone.utc)
        )
        
        mock_llm_generator.llm_provider.generate_text.return_value = updated_task_mock
        
        result = await mock_llm_generator.refine_item_details(
            sample_task_for_llm, refinement_instruction, "main"
        )
        
        assert result is not None
        assert isinstance(result, Task)
        assert result.title == "Updated LLM Test Task"
        assert result.priority == TaskPriority.HIGH
        assert result.details == "Added comprehensive implementation details"
        assert result.id == sample_task_for_llm.id
        assert result.created_at == sample_task_for_llm.created_at
        
        mock_llm_generator.llm_provider.generate_text.assert_called_once()
        call_args = mock_llm_generator.llm_provider.generate_text.call_args
        assert call_args[1]['model_type'] == "main"
        
        prompt = call_args[0][0]
        assert refinement_instruction in prompt
        assert "refine" in prompt.lower()

    async def test_refine_item_details_handles_invalid_json(self, mock_llm_generator, sample_task_for_llm):
        refinement_instruction = "This will return invalid JSON"
        
        mock_llm_generator.llm_provider.generate_text.side_effect = ValueError("LLM returned invalid JSON")
        
        with pytest.raises(RuntimeError, match="Item refinement failed"):
            await mock_llm_generator.refine_item_details(
                sample_task_for_llm, refinement_instruction, "main"
            )

    async def test_refine_item_details_preserves_immutable_fields(self, mock_llm_generator, sample_task_for_llm):
        refinement_instruction = "Update task"
        original_id = sample_task_for_llm.id
        original_created_at = sample_task_for_llm.created_at
        
        different_id = uuid4()
        different_created_at = datetime.now(timezone.utc)
        
        updated_task_mock = Task(
            id=different_id,
            title="Updated Task",
            description="Updated description",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            created_at=different_created_at,
            updated_at=datetime.now(timezone.utc)
        )
        
        mock_llm_generator.llm_provider.generate_text.return_value = updated_task_mock
        
        result = await mock_llm_generator.refine_item_details(
            sample_task_for_llm, refinement_instruction, "main"
        )
        
        assert result.id == original_id
        assert result.created_at == original_created_at
        assert result.title == "Updated Task"
        assert result.status == TaskStatus.IN_PROGRESS