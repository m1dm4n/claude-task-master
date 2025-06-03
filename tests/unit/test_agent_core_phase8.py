"""Unit tests for Phase 8: Single Task/Subtask Refinement functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime, timezone

from src.agent_core.main import DevTaskAIAssistant
from src.agent_core.llm_manager import LLMManager
from src.data_models import Task, Subtask, TaskStatus, TaskPriority, ProjectPlan

pytestmark = pytest.mark.asyncio


class TestRefineTaskOrSubtask:
    """Test the refine_task_or_subtask method in DevTaskAIAssistant."""

    @pytest.fixture
    def mock_agent(self):
        """Create a DevTaskAIAssistant with mocked dependencies."""
        with patch('src.agent_core.main.ConfigManager'), \
             patch('src.agent_core.main.ProjectManager'), \
             patch('src.agent_core.main.LLMManager'), \
             patch('src.agent_core.main.TaskManager'), \
             patch('src.agent_core.main.PlanningManager'):
            
            agent = DevTaskAIAssistant("/fake/workspace")
            
            # Mock the task manager methods
            agent.task_manager._find_item_and_context = MagicMock()
            agent.project_manager.save_project_plan = MagicMock()
            agent.project_manager.get_current_project_plan = MagicMock()
            agent.llm_manager.refine_item_details = AsyncMock()
            
            return agent

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
        return Subtask(
            id=uuid4(),
            title="Original Subtask Title",
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
        mock_agent.task_manager._find_item_and_context.return_value = (
            sample_task, mock_tasks_list, 0, None
        )
        
        # Mock LLM manager to return updated task
        mock_agent.llm_manager.refine_item_details.return_value = updated_task
        
        # Mock project plan
        mock_project_plan = MagicMock()
        mock_agent.project_manager.get_current_project_plan.return_value = mock_project_plan
        
        # Act
        result = await mock_agent.refine_task_or_subtask(task_id, refinement_instruction, use_research=False)
        
        # Assert
        assert result is not None
        assert isinstance(result, Task)
        assert result.title == "Updated Task Title"
        assert result.priority == TaskPriority.HIGH
        assert result.id == sample_task.id  # ID should be preserved
        assert result.created_at == sample_task.created_at  # created_at should be preserved
        
        # Verify that the LLM manager was called correctly
        mock_agent.llm_manager.refine_item_details.assert_called_once_with(
            sample_task, refinement_instruction, "main"
        )
        
        # Verify that the project plan was saved
        mock_agent.project_manager.save_project_plan.assert_called_once_with(mock_project_plan)
        
        # Verify that the task was replaced in the list
        assert mock_tasks_list[0] == result

    async def test_refine_task_or_subtask_updates_subtask_details(self, mock_agent, sample_subtask):
        """Test that refine_task_or_subtask successfully updates subtask details."""
        # Arrange
        subtask_id = sample_subtask.id
        refinement_instruction = "Add test strategy and change status to IN_PROGRESS"
        
        # Create updated subtask data that the LLM manager should return
        updated_subtask = Subtask(
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
        mock_agent.task_manager._find_item_and_context.return_value = (
            sample_subtask, parent_task.subtasks, 0, parent_task
        )
        
        # Mock LLM manager to return updated subtask
        mock_agent.llm_manager.refine_item_details.return_value = updated_subtask
        
        # Mock project plan
        mock_project_plan = MagicMock()
        mock_agent.project_manager.get_current_project_plan.return_value = mock_project_plan
        
        # Act
        result = await mock_agent.refine_task_or_subtask(subtask_id, refinement_instruction, use_research=True)
        
        # Assert
        assert result is not None
        assert isinstance(result, Subtask)
        assert result.status == TaskStatus.IN_PROGRESS
        assert result.testStrategy == "Comprehensive unit testing required"
        assert result.id == sample_subtask.id  # ID should be preserved
        assert result.created_at == sample_subtask.created_at  # created_at should be preserved
        
        # Verify that the LLM manager was called with research model
        mock_agent.llm_manager.refine_item_details.assert_called_once_with(
            sample_subtask, refinement_instruction, "research"
        )
        
        # Verify that the project plan was saved
        mock_agent.project_manager.save_project_plan.assert_called_once_with(mock_project_plan)
        
        # Verify that the subtask was replaced in the parent task's subtasks list
        assert parent_task.subtasks[0] == result

    async def test_refine_task_or_subtask_handles_item_not_found(self, mock_agent):
        """Test that refine_task_or_subtask handles item not found correctly."""
        # Arrange
        non_existent_id = uuid4()
        refinement_instruction = "This should fail"
        
        # Mock task manager to return None (item not found)
        mock_agent.task_manager._find_item_and_context.return_value = (None, None, None, None)
        
        # Act
        result = await mock_agent.refine_task_or_subtask(non_existent_id, refinement_instruction)
        
        # Assert
        assert result is None
        
        # Verify that LLM manager was not called
        mock_agent.llm_manager.refine_item_details.assert_not_called()
        
        # Verify that project plan was not saved
        mock_agent.project_manager.save_project_plan.assert_not_called()


class TestRefineItemDetails:
    """Test the refine_item_details method in LLMManager."""

    @pytest.fixture
    def mock_llm_manager(self):
        """Create an LLMManager with mocked dependencies."""
        with patch('src.agent_core.llm_manager.ConfigManager'), \
             patch('src.agent_core.llm_manager.LLMService'):
            
            llm_manager = LLMManager(MagicMock())
            llm_manager.llm_service.generate_text = AsyncMock()
            
            return llm_manager

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

    async def test_refine_item_details_llm_interaction(self, mock_llm_manager, sample_task_for_llm):
        """Test the refine_item_details method LLM interaction."""
        # Arrange
        refinement_instruction = "Change priority to HIGH and add details"
        
        # Mock LLM response - simulate a proper JSON response
        llm_response = f'''{{
            "id": "{sample_task_for_llm.id}",
            "title": "Updated LLM Test Task",
            "description": "Updated task description with refinements",
            "status": "PENDING",
            "priority": "HIGH",
            "details": "Added comprehensive implementation details",
            "created_at": "{sample_task_for_llm.created_at.isoformat()}",
            "updated_at": "{datetime.now(timezone.utc).isoformat()}",
            "subtasks": [],
            "dependencies": []
        }}'''
        
        mock_llm_manager.llm_service.generate_text.return_value = llm_response
        
        # Act
        result = await mock_llm_manager.refine_item_details(
            sample_task_for_llm, refinement_instruction, "main"
        )
        
        # Assert
        assert result is not None
        assert isinstance(result, Task)
        assert result.title == "Updated LLM Test Task"
        assert result.priority == TaskPriority.HIGH
        assert result.details == "Added comprehensive implementation details"
        assert result.id == sample_task_for_llm.id  # ID preserved
        assert result.created_at == sample_task_for_llm.created_at  # created_at preserved
        
        # Verify LLM service was called correctly
        mock_llm_manager.llm_service.generate_text.assert_called_once()
        call_args = mock_llm_manager.llm_service.generate_text.call_args
        assert call_args[1]['model_type'] == "main"
        
        # Verify the prompt contains the refinement instruction
        prompt = call_args[0][0]
        assert refinement_instruction in prompt
        assert "refine" in prompt.lower()

    async def test_refine_item_details_handles_invalid_json(self, mock_llm_manager, sample_task_for_llm):
        """Test that refine_item_details handles invalid JSON responses."""
        # Arrange
        refinement_instruction = "This will return invalid JSON"
        
        # Mock LLM to return invalid JSON
        mock_llm_manager.llm_service.generate_text.return_value = "Invalid JSON response"
        
        # Act & Assert
        with pytest.raises(ValueError, match="LLM returned invalid JSON"):
            await mock_llm_manager.refine_item_details(
                sample_task_for_llm, refinement_instruction, "main"
            )

    async def test_refine_item_details_preserves_immutable_fields(self, mock_llm_manager, sample_task_for_llm):
        """Test that refine_item_details preserves ID and created_at fields."""
        # Arrange
        refinement_instruction = "Update task"
        original_id = sample_task_for_llm.id
        original_created_at = sample_task_for_llm.created_at
        
        # Mock LLM response with different ID and created_at (should be overridden)
        different_id = uuid4()
        different_created_at = datetime.now(timezone.utc)
        
        llm_response = f'''{{
            "id": "{different_id}",
            "title": "Updated Task",
            "description": "Updated description",
            "status": "IN_PROGRESS",
            "priority": "HIGH",
            "created_at": "{different_created_at.isoformat()}",
            "updated_at": "{datetime.now(timezone.utc).isoformat()}",
            "subtasks": [],
            "dependencies": []
        }}'''
        
        mock_llm_manager.llm_service.generate_text.return_value = llm_response
        
        # Act
        result = await mock_llm_manager.refine_item_details(
            sample_task_for_llm, refinement_instruction, "main"
        )
        
        # Assert
        assert result.id == original_id  # Original ID preserved
        assert result.created_at == original_created_at  # Original created_at preserved
        assert result.title == "Updated Task"  # Other fields updated
        assert result.status == TaskStatus.IN_PROGRESS