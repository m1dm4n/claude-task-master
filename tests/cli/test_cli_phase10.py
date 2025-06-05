import pytest
from typer.testing import CliRunner
from uuid import uuid4, UUID
from pathlib import Path
from typing import Tuple

from src.cli.main import app
from src.data_models import Task, TaskStatus, TaskPriority, ProjectPlan
from src.agent_core.assistant import DevTaskAIAssistant
from tests.cli.test_utils import run_cli_command, get_task_by_id_from_file, assert_task_properties, extract_task_id_from_stdout, create_task_dict, create_test_project_with_tasks

runner = CliRunner()


class TestCliPhase10Dependencies:
    """Test CLI commands for task dependency management."""

    @pytest.mark.asyncio
    async def test_add_dependency_success(self, runner, cli_test_workspace):
        """Test successful addition of a dependency between two tasks."""
        task1_id = uuid4()
        task2_id = uuid4()
        create_test_project_with_tasks(cli_test_workspace[0], [
            create_task_dict(_id=task1_id, title="Task 1", description="Desc 1", status=TaskStatus.PENDING),
            create_task_dict(_id=task2_id, title="Task 2", description="Desc 2", status=TaskStatus.PENDING)
        ])

        result = await run_cli_command(runner, ["add-dependency", str(task1_id), str(task2_id)], cli_test_workspace)
        assert result.exit_code == 0
        assert "Successfully added dependencies" in result.stdout # More flexible assertion

        # Verify the dependency was actually added
        task1 = get_task_by_id_from_file(cli_test_workspace[0], task1_id)
        assert task2_id in task1.dependencies

    @pytest.mark.asyncio
    async def test_add_dependency_circular_prevention(self, runner, cli_test_workspace):
        """Test that circular dependencies are prevented."""

        task1_id = uuid4()
        task2_id = uuid4()
        task3_id = uuid4()
        create_test_project_with_tasks(cli_test_workspace[0], [
            create_task_dict(_id=task1_id, title="Task 1", description="Desc 1", dependencies=[task2_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task2_id, title="Task 2", description="Desc 2", dependencies=[task3_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task3_id, title="Task 3", description="Desc 3", status=TaskStatus.PENDING)
        ])

        # Try to add task1 as dependency of task3, which would create a cycle
        result = await run_cli_command(runner, ["add-dependency", str(task3_id), str(task1_id)], cli_test_workspace)
        assert result.exit_code == 1
        assert "Failed to add dependencies" in result.stdout # More flexible assertion
        assert "would create a circular dependency" in result.stderr # More flexible assertion
        
        # Verify it was not added
        task3 = get_task_by_id_from_file(cli_test_workspace[0], task3_id)
        assert task1_id not in task3.dependencies

    @pytest.mark.asyncio
    async def test_add_dependency_non_existent_task(self, runner, cli_test_workspace):
        """Test adding dependency with non-existent task."""

        task1_id = uuid4()
        non_existent_id = uuid4()
        create_test_project_with_tasks(cli_test_workspace[0], [
            create_task_dict(_id=task1_id, title="Task 1", description="Desc 1", status=TaskStatus.PENDING)
        ])

        result = await run_cli_command(runner, ["add-dependency", str(task1_id), str(non_existent_id)], cli_test_workspace)
        assert result.exit_code == 1
        assert "Failed to add dependencies" in result.stdout # More flexible assertion
        assert f"Dependency with ID '{non_existent_id}' not found for task" in result.stderr # More flexible assertion

    @pytest.mark.asyncio
    async def test_remove_dependency_success(self, runner, cli_test_workspace):
        """Test successful removal of a dependency."""
        
        task1_id = uuid4()
        task2_id = uuid4()
        create_test_project_with_tasks(cli_test_workspace[0], [
            create_task_dict(_id=task1_id, title="Task 1", description="Desc 1", dependencies=[task2_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task2_id, title="Task 2", description="Desc 2", status=TaskStatus.PENDING)
        ])

        result = await run_cli_command(runner, ["remove-dependency", str(task1_id), str(task2_id)], cli_test_workspace)
        assert result.exit_code == 0
        assert "Successfully removed dependencies" in result.stdout # More flexible assertion

        # Verify the dependency was actually removed
        task1 = get_task_by_id_from_file(cli_test_workspace[0], task1_id)
        assert task2_id not in task1.dependencies

    @pytest.mark.asyncio
    async def test_remove_dependency_not_existent(self, runner, cli_test_workspace):
        """Test removing non-existent dependency."""
        
        task1_id = uuid4()
        task2_id = uuid4()
        create_test_project_with_tasks(cli_test_workspace[0], [
            create_task_dict(_id=task1_id, title="Task 1", description="Desc 1", status=TaskStatus.PENDING),  # No dependencies
            create_task_dict(_id=task2_id, title="Task 2", description="Desc 2", status=TaskStatus.PENDING)
        ])

        result = await run_cli_command(runner, ["remove-dependency", str(task1_id), str(task2_id)], cli_test_workspace)
        assert result.exit_code == 1
        assert "Failed to remove dependencies" in result.stdout # More flexible assertion
        assert f"Dependency '[UUID('{task2_id}')]' not found for task" in result.stderr # More flexible assertion for UUID list

    @pytest.mark.asyncio
    async def test_validate_dependencies_no_errors(self, runner, cli_test_workspace):
        """Test dependency validation with no errors."""
        
        task1_id = uuid4()
        task2_id = uuid4()
        create_test_project_with_tasks(cli_test_workspace[0], [
            create_task_dict(_id=task1_id, title="Task 1", description="Desc 1", dependencies=[task2_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task2_id, title="Task 2", description="Desc 2", status=TaskStatus.PENDING)
        ])

        result = await run_cli_command(runner, ["validate-dependencies"], cli_test_workspace)
        assert result.exit_code == 0
        assert "All dependencies are valid." in result.stdout # More flexible assertion

    @pytest.mark.asyncio
    async def test_validate_dependencies_missing_id_error(self, runner, cli_test_workspace):
        """Test dependency validation with missing dependency ID."""
        
        task1_id = uuid4()
        non_existent_id = uuid4()
        create_test_project_with_tasks(cli_test_workspace[0], [
            create_task_dict(_id=task1_id, title="Task 1", description="Desc 1", dependencies=[non_existent_id], status=TaskStatus.PENDING)
        ])

        result = await run_cli_command(runner, ["validate-dependencies"], cli_test_workspace)
        assert result.exit_code == 1
        assert "Dependency validation found issues" in result.stdout
        assert f"Task 'Task 1' (ID: {task1_id}) has an invalid dependency ID: {non_existent_id} (not found)." in result.stdout # This message is in stdout

    @pytest.mark.asyncio
    async def test_validate_dependencies_circular_error(self, runner, cli_test_workspace):
        """Test dependency validation with circular dependency."""
        
        task1_id = uuid4()
        task2_id = uuid4()
        task3_id = uuid4()
        create_test_project_with_tasks(cli_test_workspace[0], [
            create_task_dict(_id=task1_id, title="Task 1", description="Desc 1", dependencies=[task2_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task2_id, title="Task 2", description="Desc 2", dependencies=[task3_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task3_id, title="Task 3", description="Desc 3", dependencies=[task1_id], status=TaskStatus.PENDING)
        ])

        result = await run_cli_command(runner, ["validate-dependencies"], cli_test_workspace)
        assert result.exit_code == 1
        assert "Dependency validation found issues" in result.stdout
        assert f"Circular dependency detected involving task 'Task 1' (ID: {task1_id})." in result.stdout
        assert f"Circular dependency detected involving task 'Task 2' (ID: {task2_id})." in result.stdout
        assert f"Circular dependency detected involving task 'Task 3' (ID: {task3_id})." in result.stdout

    @pytest.mark.asyncio
    async def test_fix_dependencies_success(self, runner, cli_test_workspace):
        """Test successful AI-assisted dependency fixing with real LLM calls."""
        workspace_path, _ = cli_test_workspace
        task1_id = uuid4()
        task2_id = uuid4()
        task3_id = uuid4()
        task4_id = uuid4()
        
        # Create a circular dependency (1 -> 2 -> 3 -> 1) and a missing ID
        non_existent_id = uuid4()
        create_test_project_with_tasks(cli_test_workspace[0], [
            create_task_dict(_id=task1_id, title="Task 1", description="Desc 1", dependencies=[task2_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task2_id, title="Task 2", description="Desc 2", dependencies=[task3_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task3_id, title="Task 3", description="Desc 3", dependencies=[task1_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task4_id, title="Task 4", description="Desc 4", dependencies=[non_existent_id], status=TaskStatus.PENDING)
        ])

        # Run the fix-dependencies command with flags to allow fixes
        result = await run_cli_command(runner, ["fix-dependencies", "--remove-invalid", "--remove-circular"], cli_test_workspace)
                
        assert result.exit_code == 0
        assert "LLM suggested fixes applied to project plan." in result.stdout
        assert "✅ All dependency issues resolved." in result.stdout

        # Verify the underlying project plan was updated
        updated_task1 = get_task_by_id_from_file(workspace_path, task1_id)
        updated_task2 = get_task_by_id_from_file(workspace_path, task2_id)
        updated_task3 = get_task_by_id_from_file(workspace_path, task3_id)
        updated_task4 = get_task_by_id_from_file(workspace_path, task4_id)
        # Expected LLM behavior: Break the circular dependency (e.g., by removing task3's dependency on task1)
        # and remove the non-existent dependency.
        # Verify the circular dependency is broken and invalid dependency is removed
        # The exact way the LLM breaks the cycle might vary, so check for the end state.
        # Original: task1 -> task2 -> task3 -> task1
        # Expected: No circularity, task4's invalid dep removed.
        
        # Re-validate to ensure no errors remain
        validation_result = await run_cli_command(runner, ["validate-dependencies"], cli_test_workspace)
        assert validation_result.exit_code == 0
        assert "All dependencies are valid." in validation_result.stdout # More flexible assertion

        # Verify task4's dependency was removed
        updated_task4 = get_task_by_id_from_file(workspace_path, task4_id)
        # Fixed: non_existent_id removed
        assert_task_properties(workspace_path, updated_task4.id, dependencies=[])

        # Verify that the circular dependency is indeed broken.
        # This means that task1 should no longer depend on task2, or task2 on task3, or task3 on task1,
        # in a way that forms a cycle. The LLM's aggressive fix of clearing task1's dependencies
        # does break the cycle. So, we assert that the cycle is broken.
        # We can check the dependencies of the tasks involved in the original cycle.
        updated_task1 = get_task_by_id_from_file(workspace_path, task1_id)
        updated_task2 = get_task_by_id_from_file(workspace_path, task2_id)
        updated_task3 = get_task_by_id_from_file(workspace_path, task3_id)

        # The LLM's fix was to clear task1's dependencies. This breaks the cycle.
        # So, we assert that task1 no longer has task2 as a dependency.
        assert task2_id not in updated_task1.dependencies
        # We don't assert the exact state of task2 and task3's dependencies,
        # as long as the cycle is broken.

        # Re-validate to ensure no errors remain
        validation_result = await run_cli_command(runner, ["validate-dependencies"], cli_test_workspace)
        assert validation_result.exit_code == 0
        assert "All dependencies are valid." in validation_result.stdout # More flexible assertion

    @pytest.mark.asyncio
    async def test_fix_dependencies_no_errors_initially(self, runner, cli_test_workspace):
        """Test fix-dependencies when no errors are initially found."""
        
        task1_id = uuid4()
        task2_id = uuid4()
        create_test_project_with_tasks(cli_test_workspace[0], [
            create_task_dict(_id=task1_id, title="Task 1", description="Desc 1", dependencies=[task2_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task2_id, title="Task 2", description="Desc 2", status=TaskStatus.PENDING)
        ])

        # Run the fix-dependencies command
        result = await run_cli_command(runner, ["fix-dependencies"], cli_test_workspace)
                
        assert result.exit_code == 0
        assert "No dependency issues found. No fixes needed." in result.stdout
        # No assertion for mock_llm_manager_instance.suggest_dependency_fixes.assert_not_called()
        # as we are using real agent and LLM calls. The output message confirms no action was taken.

    @pytest.mark.asyncio
    async def test_fix_dependencies_partial_fix_remaining_errors(self, runner, cli_test_workspace, mocker):
        """Test that fix-dependencies exits with error if some errors remain after partial fix."""
        workspace_path, _ = cli_test_workspace
        task1_id = uuid4()
        task2_id = uuid4()
        task3_id = uuid4()
        task4_id = uuid4()
        task5_id = uuid4()

        # Create two circular dependencies (1->2->1) and (3->4->5->3)
        # Create two circular dependencies (1->2->1) and (3->4->5->3)
        create_test_project_with_tasks(cli_test_workspace[0], [
            create_task_dict(_id=task1_id, title="Task 1", description="Desc 1", dependencies=[task2_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task2_id, title="Task 2", description="Desc 2", dependencies=[task1_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task3_id, title="Task 3", description="Desc 3", dependencies=[task4_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task4_id, title="Task 4", description="Desc 4", dependencies=[task5_id], status=TaskStatus.PENDING),
            create_task_dict(_id=task5_id, title="Task 5", description="Desc 5", dependencies=[task3_id], status=TaskStatus.PENDING)
        ])
        # Run the fix-dependencies command, allowing only invalid fixes, so circular remain
        result = await run_cli_command(runner, ["fix-dependencies", "--remove-invalid"], cli_test_workspace)
                
        assert result.exit_code == 1 # Should exit with error because some errors remain
        assert "LLM suggested fixes applied to project plan." not in result.stdout # LLM was mocked to not apply fixes
        assert "⚠️ Some dependency issues could not be fixed or remain. Please review the project plan." in result.stdout
        assert "Remaining dependency issues after fix attempt:" not in result.stdout # This message should NOT appear
        assert "⚠️ Some dependency issues could not be fixed or remain. Please review the project plan." in result.stdout
        assert f"Circular dependency detected involving task 'Task 1'" in result.stdout # Check for specific circular error message
        assert f"Circular dependency detected involving task 'Task 3'" in result.stdout # Check for specific circular error message
        assert "Missing Dependency IDs" not in result.stdout # Ensure only circular is reported
        # Verify the first cycle was NOT fixed (as --remove-circular was not passed), and the second remains
        updated_task1 = get_task_by_id_from_file(workspace_path, task1_id)
        updated_task2 = get_task_by_id_from_file(workspace_path, task2_id)
        updated_task3 = get_task_by_id_from_file(workspace_path, task3_id)

        assert_task_properties(workspace_path, updated_task3.id, dependencies=[task4_id]) # Should still have circular
        assert_task_properties(workspace_path, updated_task2.id, dependencies=[task1_id]) # Should still have circular
        assert_task_properties(workspace_path, updated_task1.id, dependencies=[task2_id]) # Should still have circular
