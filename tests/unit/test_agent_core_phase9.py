"""Unit tests for Phase 9: Adding New Tasks (AI-driven) - Agent Core functionality."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from uuid import UUID, uuid4
from datetime import datetime, timezone

from src.agent_core.assistant import DevTaskAIAssistant
from src.agent_core.llm_generator import LLMGenerator
from src.agent_core.project_io import ProjectIO
from src.agent_core.task_operations import TaskOperations
from src.agent_core.llm_config import LLMConfigManager
from src.agent_core.llm_provider import LLMProvider
from src.agent_core.plan_builder import PlanBuilder
from src.agent_core.dependency_logic import DependencyManager
from src.data_models import Task, ProjectPlan, TaskStatus, TaskPriority, AppConfig, ModelConfig
from src.config_manager import ConfigManager


class TestAddNewTask:
    """Test the add_new_task functionality in DevTaskAIAssistant."""

    @pytest.fixture
    def sample_task_data(self):
        """Sample task data that would be returned by LLM."""
        return Task(
            id=uuid4(),
            title="Implement user authentication",
            description="Create a secure user authentication system with login and registration",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            details="Use JWT tokens for session management and bcrypt for password hashing",
            testStrategy="Unit tests for auth functions, integration tests for auth flow",
            dependencies=[],
            subtasks=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

    @pytest.fixture
    def sample_project_plan(self):
        """Sample project plan for testing."""
        return ProjectPlan(
            id=uuid4(),
            project_title="Test Project",
            overall_goal="Build a web application",
            tasks=[]
        )

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
            mock_project_io_instance.get_current_project_plan.return_value = Mock() # Default to a mock plan
            mock_project_io_instance.save_project_plan.return_value = MagicMock()

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

    async def test_add_new_task_appends_to_plan_and_saves(self, mock_agent, sample_task_data, sample_project_plan):
        mock_agent.project_io.get_current_project_plan.return_value = sample_project_plan
        mock_agent.llm_generator.generate_single_task = AsyncMock(return_value=sample_task_data)
        
        result = await mock_agent.add_new_task(
            description="Create user authentication system",
            use_research=False,
            dependencies_str=None,
            priority_str="HIGH"
        )
        
        assert result is not None
        assert result.title == sample_task_data.title
        assert result.priority == TaskPriority.HIGH
        assert len(sample_project_plan.tasks) == 1
        assert sample_project_plan.tasks[0] == sample_task_data
        
        mock_agent.llm_generator.generate_single_task.assert_called_once()
        call_args = mock_agent.llm_generator.generate_single_task.call_args
        assert call_args[0][0] == "Create user authentication system"
        assert call_args[1]["model_type"] == "main"
        
        mock_agent.project_io.save_project_plan.assert_called_once_with(sample_project_plan)

    async def test_add_new_task_with_dependencies_and_priority(self, mock_agent, sample_task_data, sample_project_plan):
        mock_agent.project_io.get_current_project_plan.return_value = sample_project_plan
        mock_agent.llm_generator.generate_single_task = AsyncMock(return_value=sample_task_data)
        
        dep_uuid = uuid4()
        dependencies_str = [str(dep_uuid)]
        
        result = await mock_agent.add_new_task(
            description="Create user dashboard",
            use_research=True,
            dependencies_str=dependencies_str,
            priority_str="CRITICAL"
        )
        
        assert result is not None
        assert result.dependencies == [dep_uuid]
        assert result.priority == TaskPriority.CRITICAL
        
        call_args = mock_agent.llm_generator.generate_single_task.call_args
        assert call_args[1]["model_type"] == "research"

    async def test_add_new_task_handles_llm_failure_gracefully(self, mock_agent, sample_project_plan):
        mock_agent.project_io.get_current_project_plan.return_value = sample_project_plan
        mock_agent.llm_generator.generate_single_task = AsyncMock(return_value=None) # Simulate LLM not generating a task
        
        result = await mock_agent.add_new_task(
            description="Create user authentication system",
            use_research=False
        )
        
        assert result is None
        assert len(sample_project_plan.tasks) == 0
        
        mock_agent.project_io.save_project_plan.assert_not_called()

    async def test_add_new_task_handles_invalid_dependencies(self, mock_agent, sample_project_plan):
        mock_agent.project_io.get_current_project_plan.return_value = sample_project_plan
        
        result = await mock_agent.add_new_task(
            description="Create user authentication system",
            dependencies_str=["invalid-uuid-format"]
        )
        
        assert result is None
        
        mock_agent.llm_generator.generate_single_task.assert_not_called()

    async def test_add_new_task_handles_invalid_priority(self, mock_agent, sample_project_plan):
        mock_agent.project_io.get_current_project_plan.return_value = sample_project_plan
        
        sample_task = Task(
            title="Test task",
            description="Test description",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM
        )
        mock_agent.llm_generator.generate_single_task = AsyncMock(return_value=sample_task)
        
        result = await mock_agent.add_new_task(
            description="Create user authentication system",
            priority_str="INVALID_PRIORITY"
        )
        
        assert result is None


class TestGenerateSingleTask:
    """Test the generate_single_task functionality in LLMManager."""

    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM service for testing."""
        mock_service = MagicMock()
        return mock_service

    @pytest.fixture
    def llm_manager(self, mock_llm_service):
        """LLMManager instance with mocked service."""
        manager = LLMManager.__new__(LLMManager)  # Create without calling __init__
        manager.llm_service = mock_llm_service
        return manager

    def test_generate_single_task_llm_interaction(self, llm_manager, mock_llm_service):
        """Test the LLM interaction for generating a single task."""
        # Sample LLM response JSON
        sample_llm_response = '''
        {
            "title": "Implement user authentication",
            "description": "Create a secure user authentication system with login and registration functionality",
            "status": "PENDING",
            "priority": "HIGH",
            "details": "Use JWT tokens for session management and bcrypt for password hashing",
            "testStrategy": "Unit tests for auth functions, integration tests for auth flow",
            "dependencies": [],
            "subtasks": [
                {
                    "title": "Design authentication API endpoints",
                    "description": "Define API routes for login, register, logout",
                    "status": "PENDING",
                    "priority": "HIGH"
                }
            ]
        }
        '''
        
        # Mock the LLM service to return the sample response
    @pytest.fixture
    def mock_llm_provider(self):
        mock_provider = MagicMock()
        return mock_provider

    @pytest.fixture
    def llm_generator(self, mock_llm_provider):
        generator = LLMGenerator(mock_llm_provider)
        return generator

    async def test_generate_single_task_llm_interaction(self, llm_generator, mock_llm_provider):
        sample_llm_output = Task(
            title="Implement user authentication",
            description="Create a secure user authentication system with login and registration functionality",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            details="Use JWT tokens for session management and bcrypt for password hashing",
            testStrategy="Unit tests for auth functions, integration tests for auth flow",
            dependencies=[],
            subtasks=[
                Task(
                    title="Design authentication API endpoints",
                    description="Define API routes for login, register, logout",
                    status=TaskStatus.PENDING,
                    priority=TaskPriority.HIGH
                )
            ]
        )
        
        mock_llm_provider.generate_text = AsyncMock(return_value=sample_llm_output)
        
        result = await llm_generator.generate_single_task(
            description_prompt="Create user authentication system",
            project_context="Project: Web App\nGoal: Build a secure web application",
            model_type="main"
        )
        
        assert isinstance(result, Task)
        assert result.title == "Implement user authentication"
        assert result.description == "Create a secure user authentication system with login and registration functionality"
        assert result.status == TaskStatus.PENDING
        assert result.priority == TaskPriority.HIGH
        assert result.details == "Use JWT tokens for session management and bcrypt for password hashing"
        assert result.testStrategy == "Unit tests for auth functions, integration tests for auth flow"
        
        assert result.id is not None
        assert result.created_at is not None
        assert result.updated_at is not None
        
        assert len(result.subtasks) == 1
        subtask = result.subtasks[0]
        assert subtask.title == "Design authentication API endpoints"
        assert subtask.status == TaskStatus.PENDING
        assert subtask.id is not None
        
        mock_llm_provider.generate_text.assert_called_once()
        call_args = mock_llm_provider.generate_text.call_args
        assert "Create user authentication system" in call_args[0][0]
        assert "Project: Web App" in call_args[0][0]
        assert call_args[1]["model_type"] == "main"

    async def test_generate_single_task_handles_json_parsing_error(self, llm_generator, mock_llm_provider):
        mock_llm_provider.generate_text = AsyncMock(side_effect=ValueError("LLM returned invalid JSON"))
        
        with pytest.raises(RuntimeError, match="Task generation failed"):
            await llm_generator.generate_single_task(
                description_prompt="Create user authentication system",
                model_type="main"
            )

    async def test_generate_single_task_handles_service_error(self, llm_generator, mock_llm_provider):
        mock_llm_provider.generate_text = AsyncMock(side_effect=RuntimeError("Service unavailable"))
        
        with pytest.raises(RuntimeError, match="Task generation failed"):
            await llm_generator.generate_single_task(
                description_prompt="Create user authentication system",
                model_type="main"
            )