# tests/cli/test_cli_phase4.py
import pytest
from uuid import UUID, uuid4
from typing import List

from src.cli import app
from src.data_models import TaskStatus, ProjectPlan, Task # Added Task for type hinting
from tests.cli.utils import requires_api_key
from tests.cli.test_utils import run_cli_command, get_task_by_id_from_file, assert_task_properties, create_task_dict

# --- Test Cases for 'task-master set-status' ---

@pytest.mark.asyncio
async def test_set_status_single_id_success(runner, cli_test_workspace, project_plan_factory, real_agent):
    # Arrange: Create a plan with a single task
    task_id = uuid4()
    initial_task = create_task_dict(
        description="Initial task for status update",
        status=TaskStatus.PENDING,
        _id=task_id # Pass ID directly
    )
    workspace_path, _ = cli_test_workspace
    project_plan_factory.create_with_tasks([initial_task])

    # Act: Set the status of the task to COMPLETED
    new_status_str = "COMPLETED"
    new_status_enum = TaskStatus.COMPLETED
    result = await run_cli_command(runner, ["set-status", "--id", str(task_id), "--status", new_status_str], cli_test_workspace)

    # Assert: Check CLI output and file content
    assert result.exit_code == 0, f"set-status command failed: {result.stdout}"
    assert f"Successfully updated status for ID {task_id} to {new_status_str}." in result.stdout
    assert "All requested items updated successfully!" in result.stdout

    # Verify the change in the JSON file
    updated_task = get_task_by_id_from_file(cli_test_workspace, task_id)
    assert updated_task is not None, f"Task {task_id} not found in plan after status update."
    assert_task_properties(cli_test_workspace, task_id, status=new_status_enum)


@pytest.mark.asyncio
async def test_set_status_multiple_ids_success(runner, cli_test_workspace, project_plan_factory, real_agent):
    # Arrange: Create a plan with multiple tasks
    task_id1 = uuid4()
    task_id2 = uuid4()
    task_id3 = uuid4() # Add a third task to ensure we can pick specific ones
    
    initial_tasks = [
        create_task_dict(title="Task 1 for multi-update", description="Desc 1", status=TaskStatus.PENDING, _id=task_id1),
        create_task_dict(title="Task 2 for multi-update", description="Desc 2", status=TaskStatus.IN_PROGRESS, _id=task_id2),
        create_task_dict(title="Task 3 for multi-update", description="Desc 3", status=TaskStatus.COMPLETED, _id=task_id3)
    ]
    workspace_path, _ = cli_test_workspace
    project_plan_factory.create_with_tasks(initial_tasks)

    ids_to_update = [task_id1, task_id2]
    new_status_str = "PENDING"
    new_status_enum = TaskStatus.PENDING
    ids_str_param = f"{task_id1},{task_id2}"

    # Act: Set the status of these tasks to PENDING
    result = await run_cli_command(runner, ["set-status", "--id", ids_str_param, "--status", new_status_str], cli_test_workspace)

    # Assert: Check CLI output and file content
    assert result.exit_code == 0, f"set-status command failed: {result.stdout}"
    assert f"Successfully updated status for ID {task_id1} to {new_status_str}." in result.stdout
    assert f"Successfully updated status for ID {task_id2} to {new_status_str}." in result.stdout
    assert "All requested items updated successfully!" in result.stdout

    # Verify the changes in the JSON file
    updated_task1 = get_task_by_id_from_file(cli_test_workspace, task_id1)
    updated_task2 = get_task_by_id_from_file(cli_test_workspace, task_id2)
    unchanged_task3 = get_task_by_id_from_file(cli_test_workspace, task_id3)

    assert updated_task1 is not None
    assert updated_task2 is not None
    assert unchanged_task3 is not None

    assert_task_properties(cli_test_workspace, task_id1, status=new_status_enum)
    assert_task_properties(cli_test_workspace, task_id2, status=new_status_enum)
    assert_task_properties(cli_test_workspace, task_id3, status=TaskStatus.COMPLETED) # Ensure task3's status is unchanged


@pytest.mark.asyncio
async def test_set_status_case_insensitive_status_string(runner, cli_test_workspace, project_plan_factory, real_agent):
    # Arrange: Create a plan and get a task ID
    task_id = uuid4()
    initial_task = create_task_dict(
        title="Task for case-insensitive status test",
        description="Description for case-insensitive status test.", # Added description
        status=TaskStatus.PENDING,
        _id=task_id
    )
    workspace_path, _ = cli_test_workspace
    project_plan_factory.create_with_tasks([initial_task])

    # Act: Set the status using a lowercase status string
    lowercase_status_str = "in_progress"
    expected_cli_status_str = "IN_PROGRESS" # CLI output should normalize
    expected_status_enum = TaskStatus.IN_PROGRESS
    
    result = await run_cli_command(runner, ["set-status", "--id", str(task_id), "--status", lowercase_status_str], cli_test_workspace)

    # Assert: Check CLI output and file content
    assert result.exit_code == 0, f"set-status command failed: {result.stdout}"
    assert f"Successfully updated status for ID {task_id} to {expected_cli_status_str}." in result.stdout
    assert "All requested items updated successfully!" in result.stdout

    # Verify the change in the JSON file
    updated_task = get_task_by_id_from_file(cli_test_workspace, task_id)
    assert updated_task is not None, f"Task {task_id} not found in plan after status update."
    assert_task_properties(cli_test_workspace, task_id, status=expected_status_enum)


@pytest.mark.asyncio
async def test_set_status_invalid_uuid_format(runner, cli_test_workspace, project_plan_factory, real_agent):
    # Arrange: Create a plan and get a valid task ID
    valid_id_to_update = uuid4()
    initial_task = create_task_dict(
        description="Task for invalid UUID test",
        status=TaskStatus.PENDING,
        _id=valid_id_to_update # Pass ID directly
    )
    workspace_path, _ = cli_test_workspace
    project_plan_factory.create_with_tasks([initial_task])

    invalid_id_str = "not-a-real-uuid"

    # Act: Attempt to set status with one valid and one invalid ID
    new_status_str = "COMPLETED"
    new_status_enum = TaskStatus.COMPLETED
    ids_str_param = f"{str(valid_id_to_update)},{invalid_id_str}"
    
    result = await run_cli_command(runner, ["set-status", "--id", ids_str_param, "--status", new_status_str], cli_test_workspace)

    # Assert: Check CLI output and file content
    assert result.exit_code == 0, f"set-status command failed: {result.stdout}" # Command proceeds with valid IDs
    assert f"Warning: The following IDs are invalid and will be skipped: {invalid_id_str}" in result.stdout
    assert f"Successfully updated status for ID {valid_id_to_update} to {new_status_str}." in result.stdout
    assert "All requested items updated successfully!" not in result.stdout # Because one was invalid

    # Verify the change for the valid ID in the JSON file
    updated_task = get_task_by_id_from_file(cli_test_workspace, valid_id_to_update)
    assert updated_task is not None, f"Task {valid_id_to_update} not found in plan after status update."
    assert_task_properties(cli_test_workspace, valid_id_to_update, status=new_status_enum)


@pytest.mark.asyncio
async def test_set_status_all_invalid_uuid_formats(runner, cli_test_workspace, real_agent):
    invalid_id1 = "totally-invalid-uuid"
    invalid_id2 = "another-bad-one"
    ids_str_param = f"{invalid_id1},{invalid_id2}"

    result = await run_cli_command(runner, ["set-status", "--id", ids_str_param, "--status", "COMPLETED"], cli_test_workspace)

    assert result.exit_code == 1, f"Expected exit code 1 for all invalid IDs, got {result.exit_code}. Output: {result.stdout}"
    assert "No valid item IDs provided." in result.stdout
    assert f"Invalid IDs: {invalid_id1}, {invalid_id2}" in result.stdout


@pytest.mark.asyncio
async def test_set_status_non_existent_id_agent_handles(runner, cli_test_workspace, project_plan_factory, real_agent):
    # Arrange: Create a plan and get an existent task ID
    existent_id_to_update = uuid4()
    initial_task = create_task_dict(
        title="Task for non-existent ID test",
        description="Description for non-existent ID test.", # Added description
        status=TaskStatus.PENDING,
        _id=existent_id_to_update
    )
    workspace_path, _ = cli_test_workspace
    project_plan_factory.create_with_tasks([initial_task])

    non_existent_id = uuid4() # A valid UUID, but not in the plan

    # Act: Attempt to set status for one existent and one non-existent ID
    new_status_str = "BLOCKED"
    new_status_enum = TaskStatus.BLOCKED
    ids_str_param = f"{str(existent_id_to_update)},{str(non_existent_id)}"
    
    result = await run_cli_command(runner, ["set-status", "--id", ids_str_param, "--status", new_status_str], cli_test_workspace)

    # Assert: Check CLI output and file content
    assert result.exit_code == 0, f"set-status command failed: {result.stdout}"
    assert f"Successfully updated status for ID {str(existent_id_to_update)} to {new_status_str}." in result.stdout
    assert f"Failed to update status for ID {str(non_existent_id)}: Item not found or an error occurred." in result.stdout
    assert "Some items updated successfully, but others failed. Check messages above." in result.stdout

    # Verify the change for the existent ID in the JSON file
    updated_task = get_task_by_id_from_file(cli_test_workspace, existent_id_to_update)
    assert updated_task is not None, f"Task {existent_id_to_update} not found in plan after status update."
    assert_task_properties(cli_test_workspace, existent_id_to_update, status=new_status_enum)


@pytest.mark.asyncio
async def test_set_status_invalid_status_string(runner, cli_test_workspace, project_plan_factory, real_agent):
    # Arrange: Create a plan and get a task ID
    item_id_to_attempt_update = uuid4()
    original_status = TaskStatus.PENDING
    initial_task = create_task_dict(
        title="Task for invalid status test",
        description="Description for invalid status test.", # Added description
        status=original_status,
        _id=item_id_to_attempt_update
    )
    workspace_path, _ = cli_test_workspace
    project_plan_factory.create_with_tasks(workspace_path, [initial_task])

    invalid_status_value = "NOT_A_REAL_STATUS"

    # Act: Attempt to set an invalid status
    result = await run_cli_command(runner, ["set-status", "--id", str(item_id_to_attempt_update), "--status", invalid_status_value], cli_test_workspace)

    # Assert: Check CLI output and that the file content is unchanged
    assert result.exit_code != 0, f"Expected non-zero exit code for invalid status, got {result.exit_code}. Output: {result.stdout}, Stderr: {result.stderr}"
    assert f"Invalid value for '--status': '{invalid_status_value.lower()}' is not one of" in result.stderr \
        or f"Invalid status: '{invalid_status_value}'." in result.stdout

    # Verify the status in the JSON file has NOT changed
    task_after_attempt = get_task_by_id_from_file(cli_test_workspace, item_id_to_attempt_update)
    assert task_after_attempt is not None, f"Task {item_id_to_attempt_update} not found in plan after invalid status update attempt."
    assert_task_properties(cli_test_workspace, item_id_to_attempt_update, status=original_status)


@pytest.mark.asyncio
async def test_set_status_some_succeed_some_fail(runner, cli_test_workspace, project_plan_factory, real_agent):
    # Arrange: Create a plan with at least two tasks
    id_success1 = uuid4()
    id_success2 = uuid4()
    
    initial_tasks = [
        create_task_dict(description="Task A for mixed update", status=TaskStatus.PENDING, _id=id_success1),
        create_task_dict(description="Task B for mixed update", status=TaskStatus.IN_PROGRESS, _id=id_success2)
    ]
    workspace_path, _ = cli_test_workspace
    project_plan_factory.create_with_tasks(initial_tasks)

    id_fail_non_existent = uuid4() # This ID won't be in the plan

    ids_to_update_statuses = { # For easier verification later
        id_success1: True,
        id_success2: True,
        id_fail_non_existent: False # Expected outcome (not found)
    }
    
    # Act: Attempt to set status for two existent and one non-existent ID
    new_status_str = "DEFERRED"
    new_status_enum = TaskStatus.DEFERRED
    # Mix the order to ensure processing isn't order-dependent for reporting
    ids_str_param = f"{str(id_success1)},{str(id_fail_non_existent)},{str(id_success2)}"
    
    result = await run_cli_command(runner, ["set-status", "--id", ids_str_param, "--status", new_status_str], cli_test_workspace)

    # Assert: Check CLI output and file content
    assert result.exit_code == 0, f"set-status command failed: {result.stdout}"
    assert f"Successfully updated status for ID {str(id_success1)} to {new_status_str}." in result.stdout
    assert f"Failed to update status for ID {str(id_fail_non_existent)}: Item not found or an error occurred." in result.stdout
    assert f"Successfully updated status for ID {str(id_success2)} to {new_status_str}." in result.stdout
    assert "Some items updated successfully, but others failed. Check messages above." in result.stdout

    # Verify the changes for successful IDs in the JSON file
    for task_id_key, expected_success_flag in ids_to_update_statuses.items():
        if task_id_key == id_fail_non_existent:
            # Ensure this non-existent ID didn't magically appear or get processed
            assert get_task_by_id_from_file(cli_test_workspace, task_id_key) is None, \
                   f"Non-existent task {task_id_key} should not appear in the plan."
            continue

        # For existent tasks:
        task_after_update = get_task_by_id_from_file(cli_test_workspace, task_id_key)
        assert task_after_update is not None, f"Existent task {task_id_key} missing from plan after update."

        if expected_success_flag: # id_success1, id_success2
            assert_task_properties(cli_test_workspace, task_id_key, status=new_status_enum)


@pytest.mark.asyncio
async def test_set_status_all_fail_agent_side(runner, cli_test_workspace, project_plan_factory, real_agent):
    # Arrange: Create a plan (so the workspace is set up and db exists)
    # but we will use IDs not present in this plan.
    initial_task = create_task_dict(title="Dummy task for all-fail test", description="Dummy description", status=TaskStatus.PENDING)
    workspace_path, _ = cli_test_workspace
    project_plan_factory.create_with_tasks([initial_task])

    # Keep a copy of the original plan data to ensure it's not modified
    original_plan_data = project_plan_factory.load()
    assert original_plan_data is not None, "Original plan should exist for this test."

    id1_non_existent = uuid4()
    id2_non_existent = uuid4()
    
    # Act: Attempt to set status for two non-existent IDs
    new_status_str = "CANCELLED"
    ids_str_param = f"{str(id1_non_existent)},{str(id2_non_existent)}"
    
    result = await run_cli_command(runner, ["set-status", "--id", ids_str_param, "--status", new_status_str], cli_test_workspace)
    # Assert: Check CLI output and that file content is unchanged
    assert result.exit_code == 0, f"set-status command failed: {result.stdout}" # Command completes
    assert f"Failed to update status for ID {str(id1_non_existent)}: Item not found or an error occurred." in result.stdout
    assert f"Failed to update status for ID {str(id2_non_existent)}: Item not found or an error occurred." in result.stdout
    assert "No items were updated successfully by the agent." in result.stdout

    # Verify the plan file has not changed
    plan_data_after = project_plan_factory.load()
    assert plan_data_after is not None
    assert plan_data_after.model_dump_json(indent=2) == original_plan_data.model_dump_json(indent=2), \
        "Plan file was modified despite all IDs being non-existent."


@pytest.mark.asyncio
async def test_set_status_no_ids_provided(runner, cli_test_workspace, real_agent):
    # This test verifies Typer's handling of missing required options.
    # No project plan is created as the command should fail before interacting with it.
    
    result = await run_cli_command(runner, ["set-status", "--status", "COMPLETED"], cli_test_workspace) # Missing --id
    
    assert result.exit_code != 0, f"Expected non-zero exit code for missing --id, got {result.exit_code}. Output: {result.stdout}, Stderr: {result.stderr}"
    assert "Missing option '--id'" in result.stderr, f"Expected '--id' missing error in stderr. Stderr: {result.stderr}"

    # Ensure no plan file was created or modified
    plan_file_path = cli_test_workspace / "project_plan.json"
    assert not plan_file_path.exists(), \
        "Plan file should not exist or be modified when --id option is missing."


@pytest.mark.asyncio
async def test_set_status_empty_id_string(runner, cli_test_workspace, real_agent):
    # cli_test_workspace is included for consistency.
    
    result = await run_cli_command(runner, ["set-status", "--id", "", "--status", "COMPLETED"], cli_test_workspace)
    
    assert result.exit_code == 1, f"Expected exit code 1 for empty --id string, got {result.exit_code}. Output: {result.stdout}"
    assert "No valid item IDs provided." in result.stdout


@pytest.mark.asyncio
async def test_set_status_ids_with_only_commas(runner, cli_test_workspace, real_agent):
    # cli_test_workspace is included for consistency.

    result = await run_cli_command(runner, ["set-status", "--id", ",,,", "--status", "COMPLETED"], cli_test_workspace)
    
    assert result.exit_code == 1, f"Expected exit code 1 for --id with only commas, got {result.exit_code}. Output: {result.stdout}"
    assert "No valid item IDs provided." in result.stdout

# The test_set_status_agent_raises_unexpected_exception is removed as per instructions.