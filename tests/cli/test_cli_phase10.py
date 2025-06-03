import pytest
from typer.testing import CliRunner
from uuid import uuid4, UUID
from datetime import datetime, timezone
from unittest.mock import patch, Mock, AsyncMock # Import AsyncMock
import os # Import os
import json # Import json
import asyncio # Import asyncio

from src.data_models import Task, ProjectPlan, TaskStatus, TaskPriority, ModelConfig
from src.cli.main import app
from src.agent_core.task_manager import TaskManager # For direct manipulation in setup

runner = CliRunner()

@pytest.fixture
def cli_test_setup(tmp_path):
    """
    Sets up a temporary workspace for CLI tests, initializes a project,
    and provides a DevTaskAIAssistant instance for direct manipulation.
    """
    workspace_dir = tmp_path / "test_workspace"
    workspace_dir.mkdir()

    # Create a dummy .taskmasterconfig file with all required model configs
    config_content = {
        "project_plan_file": "project_plan.json",
        "tasks_dir": "tasks",
        "main_model": {"model_name": "mock-main-model", "provider": "google", "api_key": "mock-key"}, # Set provider to google
        "research_model": {"model_name": "mock-research-model", "provider": "google", "api_key": "mock-key"}, # Set provider to google
        "fallback_model": {"model_name": "mock-fallback-model", "provider": "google", "api_key": "mock-key"} # Set provider to google
    }
    config_file_path = workspace_dir / ".taskmasterconfig"
    with open(config_file_path, "w") as f:
        json.dump(config_content, f)

    # Change to the temporary workspace directory for the test
    original_cwd = os.getcwd()
    os.chdir(workspace_dir)

    # Patch ConfigManager, LLMService, and LLMManager during DevTaskAIAssistant init
    with patch('src.agent_core.main.ConfigManager') as MockConfigManager, \
         patch('src.agent_core.main.LLMManager') as MockLLMManager, \
         patch('src.agent_core.llm_manager.LLMService') as MockLLMService: # Patch LLMService in llm_manager's scope

        mock_config_manager_instance = MockConfigManager.return_value
        mock_config_manager_instance.get_all_model_configs.return_value = {}
        mock_config_manager_instance.get_model_config.side_effect = lambda model_type: Mock(model_name=f"mock-{model_type}-model", provider="google", api_key="mock-key")
        
        # Mock the config object and its attributes for ProjectManager init
        mock_config_instance = Mock()
        mock_config_instance.project_plan_file = "project_plan.json"
        mock_config_instance.tasks_dir = "tasks"
        mock_config_manager_instance.config = mock_config_instance

        mock_llm_service_instance = MockLLMService.return_value
        mock_llm_service_instance.get_main_agent.return_value = Mock(run=Mock(return_value=Mock(output="{}")))
        mock_llm_service_instance.generate_text.return_value = "{}"

        # Configure the mock LLMManager
        mock_llm_manager_instance = MockLLMManager.return_value
        mock_llm_manager_instance.suggest_dependency_fixes = AsyncMock(return_value=ProjectPlan(
            project_title="Fixed Plan", overall_goal="Fixed Goal", tasks=[]
        ))
        
        from src.agent_core.main import DevTaskAIAssistant
        agent = DevTaskAIAssistant(workspace_path=str(workspace_dir))
        
        # Manually set the mocked managers after init to ensure they are the patched ones
        agent.config_manager = mock_config_manager_instance
        agent.llm_manager = mock_llm_manager_instance
        agent.task_manager = TaskManager(agent.project_manager) # Re-init TaskManager with agent's project_manager

        agent.initialize_project(project_name="CLI Test Project")
        agent.reload_project_plan() # Ensure the project plan is loaded for the agent

        yield agent, workspace_dir

    # Revert to original working directory
    os.chdir(original_cwd)

def add_tasks_to_project(agent, tasks_data):
    """Helper to add tasks to the project plan via the agent's project manager."""
    project_plan = agent.get_current_project_plan()
    if not project_plan:
        project_plan = ProjectPlan(project_title="Test Project", overall_goal="Test Goal", tasks=[])
        agent.project_manager.set_project_plan(project_plan)

    for task_data in tasks_data:
        task = Task(
            id=UUID(task_data["id"]),
            title=task_data["title"],
            description=task_data["description"],
            status=TaskStatus[task_data.get("status", "PENDING").upper()],
            priority=TaskPriority[task_data.get("priority", "MEDIUM").upper()],
            dependencies=[UUID(dep) for dep in task_data.get("dependencies", [])],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        project_plan.tasks.append(task)
    agent.project_manager.save_project_plan()
    agent.reload_project_plan() # Ensure agent's internal plan is updated

def get_task_from_agent(agent, task_id: UUID) -> Task:
    """Helper to retrieve a task from the agent's current project plan."""
    return agent.get_item_by_id(task_id)

class TestCliPhase10Dependencies:

    def test_add_dependency_success(self, cli_test_setup):
        agent, workspace_dir = cli_test_setup
        
        task1_id = uuid4()
        task2_id = uuid4()
        add_tasks_to_project(agent, [
            {"id": str(task1_id), "title": "Task 1", "description": "Desc 1"},
            {"id": str(task2_id), "title": "Task 2", "description": "Desc 2"}
        ])

        result = runner.invoke(app, ["add-dependency", str(task1_id), str(task2_id)])
        assert result.exit_code == 0
        assert "Successfully added dependency" in result.stdout
        
        task1 = get_task_from_agent(agent, task1_id)
        assert task2_id in task1.dependencies

    def test_add_dependency_circular_prevention(self, cli_test_setup):
        agent, workspace_dir = cli_test_setup
        
        task1_id = uuid4()
        task2_id = uuid4()
        task3_id = uuid4()
        add_tasks_to_project(agent, [
            {"id": str(task1_id), "title": "Task 1", "description": "Desc 1", "dependencies": [str(task2_id)]},
            {"id": str(task2_id), "title": "Task 2", "description": "Desc 2", "dependencies": [str(task3_id)]},
            {"id": str(task3_id), "title": "Task 3", "description": "Desc 3"}
        ])

        # Attempt to create a cycle: Task 3 depends on Task 1 (3 -> 1 -> 2 -> 3)
        result = runner.invoke(app, ["add-dependency", str(task3_id), str(task1_id)])
        assert result.exit_code == 1
        assert "Failed to add dependency" in result.stdout
        assert "Adding this dependency would create a circular dependency" in result.stdout
        
        task3 = get_task_from_agent(agent, task3_id)
        assert task1_id not in task3.dependencies # Ensure it was not added

    def test_add_dependency_non_existent_task(self, cli_test_setup):
        agent, workspace_dir = cli_test_setup
        
        task1_id = uuid4()
        non_existent_id = uuid4()
        add_tasks_to_project(agent, [
            {"id": str(task1_id), "title": "Task 1", "description": "Desc 1"}
        ])

        result = runner.invoke(app, ["add-dependency", str(task1_id), str(non_existent_id)])
        assert result.exit_code == 1
        assert "Failed to add dependency" in result.stdout
        assert f"Error: Dependency task with ID {non_existent_id} not found." in result.stdout

    def test_remove_dependency_success(self, cli_test_setup):
        agent, workspace_dir = cli_test_setup
        
        task1_id = uuid4()
        task2_id = uuid4()
        add_tasks_to_project(agent, [
            {"id": str(task1_id), "title": "Task 1", "description": "Desc 1", "dependencies": [str(task2_id)]},
            {"id": str(task2_id), "title": "Task 2", "description": "Desc 2"}
        ])

        result = runner.invoke(app, ["remove-dependency", str(task1_id), str(task2_id)])
        assert result.exit_code == 0
        assert "Successfully removed dependency" in result.stdout
        
        task1 = get_task_from_agent(agent, task1_id)
        assert task2_id not in task1.dependencies

    def test_remove_dependency_not_existent(self, cli_test_setup):
        agent, workspace_dir = cli_test_setup
        
        task1_id = uuid4()
        task2_id = uuid4()
        add_tasks_to_project(agent, [
            {"id": str(task1_id), "title": "Task 1", "description": "Desc 1"}, # No dependency on task2
            {"id": str(task2_id), "title": "Task 2", "description": "Desc 2"}
        ])

        result = runner.invoke(app, ["remove-dependency", str(task1_id), str(task2_id)])
        assert result.exit_code == 1
        assert "Failed to remove dependency" in result.stdout
        assert f"Task {task1_id} not found or does not depend on {task2_id}." in result.stdout

    def test_validate_dependencies_no_errors(self, cli_test_setup):
        agent, workspace_dir = cli_test_setup
        
        task1_id = uuid4()
        task2_id = uuid4()
        add_tasks_to_project(agent, [
            {"id": str(task1_id), "title": "Task 1", "description": "Desc 1", "dependencies": [str(task2_id)]},
            {"id": str(task2_id), "title": "Task 2", "description": "Desc 2"}
        ])

        result = runner.invoke(app, ["validate-dependencies"])
        assert result.exit_code == 0
        assert "All dependencies validated successfully. No errors found." in result.stdout

    def test_validate_dependencies_missing_id_error(self, cli_test_setup):
        agent, workspace_dir = cli_test_setup
        
        task1_id = uuid4()
        non_existent_id = uuid4()
        add_tasks_to_project(agent, [
            {"id": str(task1_id), "title": "Task 1", "description": "Desc 1", "dependencies": [str(non_existent_id)]}
        ])

        result = runner.invoke(app, ["validate-dependencies"])
        assert result.exit_code == 1
        assert "Dependency validation found issues" in result.stdout
        assert "Missing Dependency IDs" in result.stdout
        assert f"Task 'Task 1' (ID: {task1_id}) depends on non-existent task ID: {non_existent_id}" in result.stdout

    def test_validate_dependencies_circular_error(self, cli_test_setup):
        agent, workspace_dir = cli_test_setup
        
        task1_id = uuid4()
        task2_id = uuid4()
        task3_id = uuid4()
        add_tasks_to_project(agent, [
            {"id": str(task1_id), "title": "Task 1", "description": "Desc 1", "dependencies": [str(task2_id)]},
            {"id": str(task2_id), "title": "Task 2", "description": "Desc 2", "dependencies": [str(task3_id)]},
            {"id": str(task3_id), "title": "Task 3", "description": "Desc 3", "dependencies": [str(task1_id)]}
        ])

        result = runner.invoke(app, ["validate-dependencies"])
        assert result.exit_code == 1
        assert "Dependency validation found issues" in result.stdout
        assert "Circular Dependencies" in result.stdout
        # The exact cycle string can vary, but it should contain the IDs
        assert str(task1_id) in result.stdout and str(task2_id) in result.stdout and str(task3_id) in result.stdout

    @pytest.mark.asyncio
    async def test_fix_dependencies_success(self, cli_test_setup):
        agent, workspace_dir = cli_test_setup
        
        task1_id = uuid4()
        task2_id = uuid4()
        task3_id = uuid4()
        task4_id = uuid4() # A task that LLM might suggest removing dependency from

        # Create a circular dependency (1 -> 2 -> 3 -> 1) and a missing ID
        non_existent_id = uuid4()
        add_tasks_to_project(agent, [
            {"id": str(task1_id), "title": "Task 1", "description": "Desc 1", "dependencies": [str(task2_id)]},
            {"id": str(task2_id), "title": "Task 2", "description": "Desc 2", "dependencies": [str(task3_id)]},
            {"id": str(task3_id), "title": "Task 3", "description": "Desc 3", "dependencies": [str(task1_id)]},
            {"id": str(task4_id), "title": "Task 4", "description": "Desc 4", "dependencies": [str(non_existent_id)]}
        ])

        # Mock the LLMManager's suggest_dependency_fixes to return a plan that fixes the cycle and missing ID
        fixed_task1 = Task(id=task1_id, title="Task 1", description="Desc 1", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM, dependencies=[task2_id])
        fixed_task2 = Task(id=task2_id, title="Task 2", description="Desc 2", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM, dependencies=[task3_id])
        fixed_task3 = Task(id=task3_id, title="Task 3", description="Desc 3", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM, dependencies=[]) # Fix: remove dependency on task1
        fixed_task4 = Task(id=task4_id, title="Task 4", description="Desc 4", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM, dependencies=[]) # Fix: remove missing dependency

        mock_fixed_plan = ProjectPlan(
            project_title="CLI Test Project", overall_goal="Test Goal",
            tasks=[fixed_task1, fixed_task2, fixed_task3, fixed_task4]
        )

        with patch.object(agent.llm_manager, 'suggest_dependency_fixes', return_value=mock_fixed_plan):
            # Await the runner.invoke call directly
            result = await runner.invoke(app, ["fix-dependencies"])
            
            assert result.exit_code == 0
            assert "AI-assisted dependency fixes applied." in result.stdout
            assert "All dependency errors resolved!" in result.stdout

            # Verify the underlying project plan was updated
            updated_task1 = get_task_from_agent(agent, task1_id)
            updated_task2 = get_task_from_agent(agent, task2_id)
            updated_task3 = get_task_from_agent(agent, task3_id)
            updated_task4 = get_task_from_agent(agent, task4_id)

            assert updated_task1.dependencies == [task2_id]
            assert updated_task2.dependencies == [task3_id]
            assert updated_task3.dependencies == [] # Fixed
            assert updated_task4.dependencies == [] # Fixed

            # Re-validate to ensure no errors remain
            validation_result = runner.invoke(app, ["validate-dependencies"])
            assert validation_result.exit_code == 0
            assert "All dependencies validated successfully. No errors found." in validation_result.stdout

    @pytest.mark.asyncio
    async def test_fix_dependencies_no_errors_initially(self, cli_test_setup):
        agent, workspace_dir = cli_test_setup
        
        task1_id = uuid4()
        task2_id = uuid4()
        add_tasks_to_project(agent, [
            {"id": str(task1_id), "title": "Task 1", "description": "Desc 1", "dependencies": [str(task2_id)]},
            {"id": str(task2_id), "title": "Task 2", "description": "Desc 2"}
        ])

        # Mock LLMManager to ensure it's not called if no errors
        with patch.object(agent.llm_manager, 'suggest_dependency_fixes') as mock_suggest_fixes:
            # Await the runner.invoke call directly
            result = await runner.invoke(app, ["fix-dependencies"])
            
            assert result.exit_code == 0
            assert "No dependency errors found to fix." in result.stdout
            mock_suggest_fixes.assert_not_called()

    @pytest.mark.asyncio
    async def test_fix_dependencies_partial_fix_remaining_errors(self, cli_test_setup):
        agent, workspace_dir = cli_test_setup
        
        task1_id = uuid4()
        task2_id = uuid4()
        task3_id = uuid4()
        task4_id = uuid4()
        task5_id = uuid4()

        # Create two circular dependencies (1->2->1) and (3->4->5->3)
        add_tasks_to_project(agent, [
            {"id": str(task1_id), "title": "Task 1", "description": "Desc 1", "dependencies": [str(task2_id)]},
            {"id": str(task2_id), "title": "Task 2", "description": "Desc 2", "dependencies": [str(task1_id)]},
            {"id": str(task3_id), "title": "Task 3", "description": "Desc 3", "dependencies": [str(task4_id)]},
            {"id": str(task4_id), "title": "Task 4", "description": "Desc 4", "dependencies": [str(task5_id)]},
            {"id": str(task5_id), "title": "Task 5", "description": "Desc 5", "dependencies": [str(task3_id)]}
        ])

        # Mock LLM to fix only the first cycle (1->2->1)
        fixed_task1 = Task(id=task1_id, title="Task 1", description="Desc 1", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM, dependencies=[])
        fixed_task2 = Task(id=task2_id, title="Task 2", description="Desc 2", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM, dependencies=[])
        
        mock_fixed_plan = ProjectPlan(
            project_title="CLI Test Project", overall_goal="Test Goal",
            tasks=[fixed_task1, fixed_task2, 
                   get_task_from_agent(agent, task3_id), # Unchanged
                   get_task_from_agent(agent, task4_id), # Unchanged
                   get_task_from_agent(agent, task5_id)] # Unchanged
        )

        with patch.object(agent.llm_manager, 'suggest_dependency_fixes', return_value=mock_fixed_plan):
            # Await the runner.invoke call directly
            result = await runner.invoke(app, ["fix-dependencies"])
            
            assert result.exit_code == 1 # Should exit with error because some errors remain
            assert "AI-assisted dependency fixes applied." in result.stdout
            assert "Some errors still remain after fixing:" in result.stdout
            assert "Remaining Circular Dependencies" in result.stdout
            assert str(task3_id) in result.stdout and str(task4_id) in result.stdout and str(task5_id) in result.stdout
            assert "Missing Dependency IDs" not in result.stdout # Ensure only circular is reported

            # Verify the first cycle was fixed, and the second remains
            updated_task1 = get_task_from_agent(agent, task1_id)
            updated_task2 = get_task_from_agent(agent, task2_id)
            updated_task3 = get_task_from_agent(agent, task3_id)

            assert updated_task1.dependencies == []
            assert updated_task2.dependencies == []
            assert task3_id in updated_task3.dependencies # Still has dependency leading to cycle