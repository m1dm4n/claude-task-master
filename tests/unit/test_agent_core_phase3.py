"""
Unit tests for Phase 3 DevTaskAIAssistant functionality.
Tests the get_all_tasks, get_tasks_by_status, get_item_by_id, and get_current_project_plan methods.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from uuid import uuid4, UUID
import tempfile

from src.agent_core.assistant import DevTaskAIAssistant
from src.agent_core.llm_config import LLMConfigManager
from src.agent_core.llm_provider import LLMProvider
from src.agent_core.llm_generator import LLMGenerator
from src.agent_core.plan_builder import PlanBuilder
from src.agent_core.project_io import ProjectIO
from src.agent_core.task_operations import TaskOperations
from src.agent_core.dependency_logic import DependencyManager
from src.data_models import ProjectPlan, Task, TaskStatus, TaskPriority, AppConfig, ModelConfig
from src.config_manager import ConfigManager


@pytest.fixture
def agent():
    """Create DevTaskAIAssistant instance with mocked dependencies."""
    with tempfile.TemporaryDirectory() as temp_dir, \
         patch('src.config_manager.ConfigManager') as MockConfigManager, \
         patch('src.agent_core.llm_config.LLMConfigManager') as MockLLMConfigManager, \
         patch('src.agent_core.llm_provider.LLMProvider') as MockLLMProvider, \
         patch('src.agent_core.llm_generator.LLMGenerator') as MockLLMGenerator, \
         patch('src.agent_core.plan_builder.PlanBuilder') as MockPlanBuilder, \
         patch('src.agent_core.project_io.ProjectIO') as MockProjectIO, \
         patch('src.agent_core.task_operations.TaskOperations') as MockTaskOperations, \
         patch('src.agent_core.dependency_logic.DependencyManager') as MockDependencyManager:

        # Mock ConfigManager
        mock_config_manager_instance = MockConfigManager.return_value
        test_config = AppConfig(
            main_model=ModelConfig(model_name="test-model", provider="test"),
            project_plan_file="project_plan.json",
            tasks_dir="tasks"
        )
        mock_config_manager_instance.config = test_config
        MockConfigManager.return_value = mock_config_manager_instance

        # Mock other managers
        mock_llm_config_manager_instance = MockLLMConfigManager.return_value
        mock_llm_provider_instance = MockLLMProvider.return_value
        mock_llm_generator_instance = MockLLMGenerator.return_value
        mock_plan_builder_instance = MockPlanBuilder.return_value
        mock_project_io_instance = MockProjectIO.return_value
        mock_task_operations_instance = MockTaskOperations.return_value
        mock_dependency_manager_instance = MockDependencyManager.return_value

        # Instantiate DevTaskAIAssistant with mocked dependencies
        agent_instance = DevTaskAIAssistant(temp_dir)
        agent_instance.config_manager = mock_config_manager_instance
        agent_instance.llm_config_manager = mock_llm_config_manager_instance
        agent_instance.llm_provider = mock_llm_provider_instance
        agent_instance.llm_generator = mock_llm_generator_instance
        agent_instance.plan_builder = mock_plan_builder_instance
        agent_instance.project_io = mock_project_io_instance
        agent_instance.task_operations = mock_task_operations_instance
        agent_instance.dependency_manager = mock_dependency_manager_instance

        # Set default return values for methods called by DevTaskAIAssistant itself
        agent_instance.project_io.get_current_project_plan.return_value = None # Default to no plan
        agent_instance.project_io.save_project_plan.return_value = None

        yield agent_instance


@pytest.fixture
def sample_project_plan():
    """Create a sample project plan with tasks and subtasks."""
    task1_id = uuid4()
    task2_id = uuid4()
    subtask1_id = uuid4()
    subtask2_id = uuid4()
    subtask3_id = uuid4()
    
    return ProjectPlan(
        project_title="Sample Project",
        overall_goal="Build something awesome",
        tasks=[
            Task(
                id=task1_id,
                title="Task 1",
                description="First task description",
                status=TaskStatus.PENDING,
                priority=TaskPriority.HIGH,
                dependencies=[],  # Added
                details="Task 1 details", # Added
                testStrategy="Task 1 test strategy", # Added
                subtasks=[
                    Task(
                        id=subtask1_id,
                        title="Task 1.1",
                        description="First subtask",
                        status=TaskStatus.IN_PROGRESS,
                        priority=TaskPriority.MEDIUM,
                        details="Task 1.1 details",  # Added
                        testStrategy="Task 1.1 test strategy",  # Added
                        dependencies=[]  # Added
                    ),
                    Task(
                        id=subtask2_id,
                        title="Task 1.2",
                        description="Second subtask",
                        status=TaskStatus.COMPLETED,
                        priority=TaskPriority.LOW,
                        details="Task 1.2 details",  # Added
                        testStrategy="Task 1.2 test strategy",  # Added
                        dependencies=[]  # Added
                    )
                ]
            ),
            Task(
                id=task2_id,
                title="Task 2",
                description="Second task description",
                status=TaskStatus.COMPLETED,
                priority=TaskPriority.LOW,
                dependencies=[],  # Added
                details="Task 2 details", # Added
                testStrategy="Task 2 test strategy", # Added
                subtasks=[
                    Task(
                        id=subtask3_id,
                        title="Task 2.1",
                        description="Third subtask",
                        status=TaskStatus.BLOCKED,
                        priority=TaskPriority.HIGH,
                        details="Task 2.1 details",  # Added
                        testStrategy="Task 2.1 test strategy",  # Added
                        dependencies=[]  # Added
                    )
                ]
            )
        ]
    )


class TestGetAllTasks:
    """Test cases for the get_all_tasks method."""
    
    def test_get_all_tasks_when_project_plan_has_tasks(self, agent, sample_project_plan):
        """Test getting all tasks when project plan has tasks."""
        # Arrange
        agent.project_io.get_current_project_plan.return_value = sample_project_plan
        
        # Act
        tasks = agent.get_all_tasks()
        
        # Assert
        assert len(tasks) == 2
        assert tasks[0].title == "Task 1"
        assert tasks[1].title == "Task 2"
    
    def test_get_all_tasks_when_project_plan_has_no_tasks(self, agent):
        """Test getting all tasks when project plan has no tasks."""
        # Arrange
        empty_plan = ProjectPlan(project_title="Empty", overall_goal="Nothing", tasks=[])
        agent.project_io.get_current_project_plan.return_value = empty_plan
        
        # Act
        tasks = agent.get_all_tasks()
        
        # Assert
        assert tasks == []
    
    def test_get_all_tasks_when_project_plan_is_none(self, agent):
        """Test getting all tasks when no project plan exists."""
        # Arrange
        agent.project_io.get_current_project_plan.return_value = None
        
        # Act
        tasks = agent.get_all_tasks()
        
        # Assert
        assert tasks == []


class TestGetTasksByStatus:
    """Test cases for the get_tasks_by_status method."""
    
    def test_get_tasks_by_status_pending(self, agent, sample_project_plan):
        """Test getting tasks with PENDING status."""
        # Arrange
        agent.project_io.get_current_project_plan.return_value = sample_project_plan
        
        # Act
        pending_tasks = agent.get_tasks_by_status(TaskStatus.PENDING)
        
        # Assert
        assert len(pending_tasks) == 1
        assert pending_tasks[0].title == "Task 1"
        assert pending_tasks[0].status == TaskStatus.PENDING
    
    def test_get_tasks_by_status_completed(self, agent, sample_project_plan):
        """Test getting tasks with COMPLETED status."""
        # Arrange
        agent.project_io.get_current_project_plan.return_value = sample_project_plan
        
        # Act
        completed_tasks = agent.get_tasks_by_status(TaskStatus.COMPLETED)
        
        # Assert
        assert len(completed_tasks) == 1
        assert completed_tasks[0].title == "Task 2"
        assert completed_tasks[0].status == TaskStatus.COMPLETED
    
    def test_get_tasks_by_status_when_no_tasks_match(self, agent, sample_project_plan):
        """Test getting tasks by status when no tasks match the criteria."""
        # Arrange
        agent.project_io.get_current_project_plan.return_value = sample_project_plan
        
        # Act
        blocked_tasks = agent.get_tasks_by_status(TaskStatus.BLOCKED) # None in sample are BLOCKED
        
        # Assert
        assert len(blocked_tasks) == 0
    
    def test_get_tasks_by_status_when_project_plan_is_none(self, agent):
        """Test getting tasks by status when no project plan exists."""
        # Arrange
        agent.project_io.get_current_project_plan.return_value = None
        
        # Act
        tasks = agent.get_tasks_by_status(TaskStatus.PENDING)
        
        # Assert
        assert tasks == []


class TestGetItemById:
    """Test cases for the get_item_by_id method."""
    
    def test_get_item_by_id_successfully_retrieving_task(self, agent, sample_project_plan):
        """Test successfully retrieving a task by ID."""
        # Arrange
        agent.project_io.get_current_project_plan.return_value = sample_project_plan
        task_id = sample_project_plan.tasks[0].id
        
        # Act
        item = agent.get_item_by_id(task_id)
        
        # Assert
        assert item == sample_project_plan.tasks[0]
        assert item.title == "Task 1"
    
    def test_get_item_by_id_successfully_retrieving_subtask(self, agent, sample_project_plan):
        """Test successfully retrieving a subtask by ID."""
        # Arrange
        agent.project_io.get_current_project_plan.return_value = sample_project_plan
        subtask_id = sample_project_plan.tasks[0].subtasks[0].id
        
        # Act
        item = agent.get_item_by_id(subtask_id)
        
        # Assert
        assert item == sample_project_plan.tasks[0].subtasks[0]
        assert item.title == "Task 1.1"
    
    def test_get_item_by_id_with_nonexistent_id(self, agent, sample_project_plan):
        """Test retrieving an item with a nonexistent ID."""
        # Arrange
        agent.project_io.get_current_project_plan.return_value = sample_project_plan
        nonexistent_id = uuid4()
        
        # Act
        item = agent.get_item_by_id(nonexistent_id)
        
        # Assert
        assert item is None
    
    def test_get_item_by_id_when_project_plan_is_none(self, agent):
        """Test retrieving an item when no project plan exists."""
        # Arrange
        agent.project_io.get_current_project_plan.return_value = None
        some_id = uuid4()
        
        # Act
        item = agent.get_item_by_id(some_id)
        
        # Assert
        assert item is None


class TestGetCurrentProjectPlan:
    """Test cases for the get_current_project_plan method."""
    
    def test_get_current_project_plan_returns_existing_plan(self, agent, sample_project_plan):
        """Test that get_current_project_plan returns the existing project plan."""
        # Arrange
        agent.project_io.get_current_project_plan.return_value = sample_project_plan
        
        # Act
        plan = agent.get_current_project_plan() # This directly calls the mocked method
        
        # Assert
        assert plan == sample_project_plan
        assert plan.project_title == "Sample Project"
    
    def test_get_current_project_plan_returns_none_when_no_plan(self, agent):
        """Test that get_current_project_plan returns None when no project plan exists."""
        # Arrange
        agent.project_io.get_current_project_plan.return_value = None
        
        # Act
        plan = agent.get_current_project_plan() # This directly calls the mocked method
        
        # Assert
        assert plan is None
