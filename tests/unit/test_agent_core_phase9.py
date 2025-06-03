"""Unit tests for Phase 9: Adding New Tasks (AI-driven) - Agent Core functionality."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime, timezone

from src.agent_core.main import DevTaskAIAssistant
from src.agent_core.llm_manager import LLMManager
from src.data_models import Task, ProjectPlan, TaskStatus, TaskPriority


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

    def test_add_new_task_appends_to_plan_and_saves(self, mocker, sample_task_data, sample_project_plan):
        """Test that add_new_task appends a new task to the plan and saves it."""
        # Mock the dependencies
        mock_config_manager = MagicMock()
        mock_project_manager = MagicMock()
        mock_llm_manager = MagicMock()
        
        # Setup the agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.config_manager = mock_config_manager
        agent.project_manager = mock_project_manager
        agent.llm_manager = mock_llm_manager
        
        # Mock the project manager methods
        mock_project_manager.get_current_project_plan.return_value = sample_project_plan
        mock_project_manager.save_project_plan = MagicMock()
        
        # Mock the LLM manager to return our sample task
        mock_llm_manager.generate_single_task = AsyncMock(return_value=sample_task_data)
        
        # Call the method
        result = asyncio.run(agent.add_new_task(
            description="Create user authentication system",
            use_research=False,
            dependencies_str=None,
            priority_str="HIGH"
        ))
        
        # Verify the task was added to the plan
        assert result is not None
        assert result.title == sample_task_data.title
        assert result.priority == TaskPriority.HIGH
        assert len(sample_project_plan.tasks) == 1
        assert sample_project_plan.tasks[0] == sample_task_data
        
        # Verify LLM manager was called correctly
        mock_llm_manager.generate_single_task.assert_called_once()
        call_args = mock_llm_manager.generate_single_task.call_args
        assert call_args[0][0] == "Create user authentication system"  # description
        assert call_args[0][2] == "main"  # model_type
        
        # Verify save was called
        mock_project_manager.save_project_plan.assert_called_once_with(sample_project_plan)

    def test_add_new_task_with_dependencies_and_priority(self, mocker, sample_task_data, sample_project_plan):
        """Test add_new_task with dependencies and custom priority."""
        # Mock the dependencies
        mock_config_manager = MagicMock()
        mock_project_manager = MagicMock()
        mock_llm_manager = MagicMock()
        
        # Setup the agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.config_manager = mock_config_manager
        agent.project_manager = mock_project_manager
        agent.llm_manager = mock_llm_manager
        
        # Mock the project manager methods
        mock_project_manager.get_current_project_plan.return_value = sample_project_plan
        mock_project_manager.save_project_plan = MagicMock()
        
        # Mock the LLM manager to return our sample task
        mock_llm_manager.generate_single_task = AsyncMock(return_value=sample_task_data)
        
        # Test with dependencies and priority
        dep_uuid = uuid4()
        dependencies_str = [str(dep_uuid)]
        
        result = asyncio.run(agent.add_new_task(
            description="Create user dashboard",
            use_research=True,
            dependencies_str=dependencies_str,
            priority_str="CRITICAL"
        ))
        
        # Verify the result
        assert result is not None
        assert result.dependencies == [dep_uuid]
        assert result.priority == TaskPriority.CRITICAL
        
        # Verify LLM manager was called with research model
        call_args = mock_llm_manager.generate_single_task.call_args
        assert call_args[0][2] == "research"  # model_type

    def test_add_new_task_handles_llm_failure_gracefully(self, mocker, sample_project_plan):
        """Test that add_new_task handles LLM failure gracefully."""
        # Mock the dependencies
        mock_config_manager = MagicMock()
        mock_project_manager = MagicMock()
        mock_llm_manager = MagicMock()
        
        # Setup the agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.config_manager = mock_config_manager
        agent.project_manager = mock_project_manager
        agent.llm_manager = mock_llm_manager
        
        # Mock the project manager methods
        mock_project_manager.get_current_project_plan.return_value = sample_project_plan
        
        # Mock the LLM manager to raise an exception
        mock_llm_manager.generate_single_task = AsyncMock(side_effect=RuntimeError("LLM service unavailable"))
        
        # Call the method and expect None return
        result = asyncio.run(agent.add_new_task(
            description="Create user authentication system",
            use_research=False
        ))
        
        # Verify graceful failure
        assert result is None
        assert len(sample_project_plan.tasks) == 0  # No task should be added
        
        # Verify save was not called
        mock_project_manager.save_project_plan.assert_not_called()

    def test_add_new_task_handles_invalid_dependencies(self, mocker, sample_project_plan):
        """Test that add_new_task handles invalid dependency IDs gracefully."""
        # Mock the dependencies
        mock_config_manager = MagicMock()
        mock_project_manager = MagicMock()
        mock_llm_manager = MagicMock()
        
        # Setup the agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.config_manager = mock_config_manager
        agent.project_manager = mock_project_manager
        agent.llm_manager = mock_llm_manager
        
        # Mock the project manager methods
        mock_project_manager.get_current_project_plan.return_value = sample_project_plan
        
        # Call with invalid dependency ID
        result = asyncio.run(agent.add_new_task(
            description="Create user authentication system",
            dependencies_str=["invalid-uuid-format"]
        ))
        
        # Verify graceful failure
        assert result is None
        
        # Verify LLM manager was not called
        mock_llm_manager.generate_single_task.assert_not_called()

    def test_add_new_task_handles_invalid_priority(self, mocker, sample_project_plan):
        """Test that add_new_task handles invalid priority gracefully."""
        # Mock the dependencies
        mock_config_manager = MagicMock()
        mock_project_manager = MagicMock()
        mock_llm_manager = MagicMock()
        
        # Setup the agent with mocked dependencies
        agent = DevTaskAIAssistant()
        agent.config_manager = mock_config_manager
        agent.project_manager = mock_project_manager
        agent.llm_manager = mock_llm_manager
        
        # Mock the project manager methods
        mock_project_manager.get_current_project_plan.return_value = sample_project_plan
        
        # Mock task generation
        sample_task = Task(
            title="Test task",
            description="Test description",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM
        )
        mock_llm_manager.generate_single_task = AsyncMock(return_value=sample_task)
        
        # Call with invalid priority
        result = asyncio.run(agent.add_new_task(
            description="Create user authentication system",
            priority_str="INVALID_PRIORITY"
        ))
        
        # Verify graceful failure
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
        mock_llm_service.generate_text = AsyncMock(return_value=sample_llm_response)
        
        # Call the method
        result = asyncio.run(llm_manager.generate_single_task(
            description_prompt="Create user authentication system",
            project_context="Project: Web App\nGoal: Build a secure web application",
            model_type="main"
        ))
        
        # Verify the result
        assert isinstance(result, Task)
        assert result.title == "Implement user authentication"
        assert result.description == "Create a secure user authentication system with login and registration functionality"
        assert result.status == TaskStatus.PENDING
        assert result.priority == TaskPriority.HIGH
        assert result.details == "Use JWT tokens for session management and bcrypt for password hashing"
        assert result.testStrategy == "Unit tests for auth functions, integration tests for auth flow"
        
        # Verify ID and timestamps are set
        assert result.id is not None
        assert result.created_at is not None
        assert result.updated_at is not None
        
        # Verify subtasks are properly created
        assert len(result.subtasks) == 1
        subtask = result.subtasks[0]
        assert subtask.title == "Design authentication API endpoints"
        assert subtask.status == TaskStatus.PENDING
        assert subtask.id is not None
        
        # Verify LLM service was called correctly
        mock_llm_service.generate_text.assert_called_once()
        call_args = mock_llm_service.generate_text.call_args
        assert "Create user authentication system" in call_args[0][0]
        assert "Project: Web App" in call_args[0][0]
        assert call_args[1]["model_type"] == "main"

    def test_generate_single_task_handles_json_parsing_error(self, llm_manager, mock_llm_service):
        """Test that generate_single_task handles JSON parsing errors."""
        # Mock the LLM service to return invalid JSON
        mock_llm_service.generate_text = AsyncMock(return_value="This is not valid JSON")
        
        # Call the method and expect ValueError
        with pytest.raises(ValueError, match="LLM returned invalid JSON"):
            asyncio.run(llm_manager.generate_single_task(
                description_prompt="Create user authentication system",
                model_type="main"
            ))

    def test_generate_single_task_handles_service_error(self, llm_manager, mock_llm_service):
        """Test that generate_single_task handles service errors."""
        # Mock the LLM service to raise an exception
        mock_llm_service.generate_text = AsyncMock(side_effect=RuntimeError("Service unavailable"))
        
        # Call the method and expect RuntimeError
        with pytest.raises(RuntimeError, match="Task generation failed"):
            asyncio.run(llm_manager.generate_single_task(
                description_prompt="Create user authentication system",
                model_type="main"
            ))