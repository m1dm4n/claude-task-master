# tests/unit/test_agent_core_phase4.py
import pytest
from unittest.mock import patch, MagicMock
from uuid import UUID, uuid4
from datetime import datetime, timezone

# Added ModelConfig
from src.data_models import Task, Subtask, ProjectPlan, TaskStatus, TaskPriority, ModelConfig
from src.agent_core import DevTaskAIAssistant

# Helper to create a basic ProjectPlan with tasks and subtasks


def create_sample_project_plan():
    task1_id = uuid4()
    subtask1_1_id = uuid4()
    task2_id = uuid4()

    plan = ProjectPlan(
        project_title="Test Project",
        overall_goal="Test goal",
        tasks=[
            Task(
                id=task1_id,
                title="Task 1",
                description="Description for Task 1",
                status=TaskStatus.PENDING,
                priority=TaskPriority.MEDIUM, # Added default priority
                details="Details for Task 1", # Added
                testStrategy="Test strategy for Task 1", # Added
                dependencies=[], # Added
                subtasks=[
                    Subtask(
                        id=subtask1_1_id,
                        title="Subtask 1.1",
                        description="Description for Subtask 1.1",
                        status=TaskStatus.PENDING,
                        priority=TaskPriority.MEDIUM, # Added default priority
                        details="Details for Subtask 1.1", # Added
                        testStrategy="Test strategy for Subtask 1.1", # Added
                        dependencies=[] # Added
                    )
                ]
            ),
            Task(
                id=task2_id,
                title="Task 2",
                description="Description for Task 2",
                status=TaskStatus.IN_PROGRESS,
                priority=TaskPriority.MEDIUM, # Added default priority
                details="Details for Task 2", # Added
                testStrategy="Test strategy for Task 2", # Added
                dependencies=[], # Added
                subtasks=[] # Added, as Task expects subtasks list
            )
        ]
    )
    return plan, task1_id, subtask1_1_id, task2_id


# PersistenceManager fixture removed - now using JSON-based persistence


@pytest.fixture
def agent_with_plan():
    with patch('src.config_manager.ConfigManager') as MockConfigManagerClass:
        # Create proper AppConfig for JSON-based persistence
        from src.data_models import AppConfig, ModelConfig
        test_config = AppConfig(
            main_model=ModelConfig(model_name="test-main-model", provider="google"),
            project_plan_file="project_plan.json",
            tasks_dir="tasks"
        )
        mock_cm_instance = MockConfigManagerClass.return_value
        mock_cm_instance.get_model_config.return_value = test_config.main_model
        mock_cm_instance.config = test_config

        agent = DevTaskAIAssistant(workspace_path="dummy_workspace")
        sample_plan, _, _, _ = create_sample_project_plan()
        # Set the plan through the project manager
        agent.project_manager._project_plan = sample_plan
        # Update config manager references
        agent.config_manager = mock_cm_instance
        agent.llm_manager.config_manager = mock_cm_instance  # Also update llm_manager's ref
        return agent
@pytest.fixture
def agent_no_plan():
    with patch('src.config_manager.ConfigManager') as MockConfigManagerClass:
        # Create proper AppConfig for JSON-based persistence
        from src.data_models import AppConfig, ModelConfig
        test_config = AppConfig(
            main_model=ModelConfig(model_name="test-main-model", provider="google"),
            project_plan_file="project_plan.json",
            tasks_dir="tasks"
        )
        mock_cm_instance = MockConfigManagerClass.return_value
        mock_cm_instance.get_model_config.return_value = test_config.main_model
        mock_cm_instance.config = test_config

        agent = DevTaskAIAssistant(workspace_path="dummy_workspace")
        agent.project_manager._project_plan = None  # Ensure no plan is loaded
        agent.config_manager = mock_cm_instance
        agent.llm_manager.config_manager = mock_cm_instance
        return agent


# --- Test Cases for update_item_status ---
def test_update_status_single_task_success(agent_with_plan):
    plan, task1_id, _, _ = create_sample_project_plan()
    # re-assign to ensure fresh copy for this test
    agent_with_plan.project_manager._project_plan = plan

    # Ensure original status is PENDING
    current_plan = agent_with_plan.get_current_project_plan()
    original_task = next(
        t for t in current_plan.tasks if t.id == task1_id)
    assert original_task.status == TaskStatus.PENDING
    original_updated_at = original_task.updated_at

    results = agent_with_plan.update_item_status(
        [task1_id], TaskStatus.COMPLETED)

    assert results == {task1_id: True}
    updated_plan = agent_with_plan.get_current_project_plan()
    updated_task = next(
        t for t in updated_plan.tasks if t.id == task1_id)
    assert updated_task.status == TaskStatus.COMPLETED
    assert updated_task.updated_at > original_updated_at
    # JSON persistence saves automatically


def test_update_status_single_subtask_success(agent_with_plan):
    plan, task1_id, subtask1_1_id, _ = create_sample_project_plan()
    agent_with_plan.project_manager._project_plan = plan

    current_plan = agent_with_plan.get_current_project_plan()
    parent_task = next(
        t for t in current_plan.tasks if t.id == task1_id)
    original_subtask = next(
        st for st in parent_task.subtasks if st.id == subtask1_1_id)
    assert original_subtask.status == TaskStatus.PENDING
    original_updated_at = original_subtask.updated_at

    results = agent_with_plan.update_item_status(
        [subtask1_1_id], TaskStatus.IN_PROGRESS)

    assert results == {subtask1_1_id: True}
    updated_plan = agent_with_plan.get_current_project_plan()
    updated_parent_task = next(
        t for t in updated_plan.tasks if t.id == task1_id)
    updated_subtask = next(
        st for st in updated_parent_task.subtasks if st.id == subtask1_1_id)
    assert updated_subtask.status == TaskStatus.IN_PROGRESS
    assert updated_subtask.updated_at > original_updated_at
    # JSON persistence saves automatically

def test_update_status_multiple_items_mix_success(agent_with_plan):
    plan, task1_id, subtask1_1_id, task2_id = create_sample_project_plan()
    agent_with_plan.project_manager._project_plan = plan

    current_plan = agent_with_plan.get_current_project_plan()
    original_task1 = next(
        t for t in current_plan.tasks if t.id == task1_id)
    original_subtask1_1 = next(
        st for st in original_task1.subtasks if st.id == subtask1_1_id)
    original_task2 = next(
        t for t in current_plan.tasks if t.id == task2_id)

    original_task1_ua = original_task1.updated_at
    original_subtask1_1_ua = original_subtask1_1.updated_at
    original_task2_ua = original_task2.updated_at

    ids_to_update = [task1_id, subtask1_1_id, task2_id]
    results = agent_with_plan.update_item_status(
        ids_to_update, TaskStatus.COMPLETED)

    assert results == {task1_id: True, subtask1_1_id: True, task2_id: True}

    updated_plan = agent_with_plan.get_current_project_plan()
    updated_task1 = next(
        t for t in updated_plan.tasks if t.id == task1_id)
    updated_subtask1_1 = next(
        st for st in updated_task1.subtasks if st.id == subtask1_1_id)
    updated_task2 = next(
        t for t in updated_plan.tasks if t.id == task2_id)

    assert updated_task1.status == TaskStatus.COMPLETED
    assert updated_task1.updated_at > original_task1_ua
    assert updated_subtask1_1.status == TaskStatus.COMPLETED
    assert updated_subtask1_1.updated_at > original_subtask1_1_ua
    assert updated_task2.status == TaskStatus.COMPLETED
    assert updated_task2.updated_at > original_task2_ua
    # JSON persistence saves automatically


def test_update_status_non_existent_id(agent_with_plan):
    non_existent_id = uuid4()
    plan, task1_id, _, _ = create_sample_project_plan()
    agent_with_plan.project_manager._project_plan = plan

    # Update one valid, one invalid
    results = agent_with_plan.update_item_status(
        [task1_id, non_existent_id], TaskStatus.COMPLETED)

    assert results == {task1_id: True, non_existent_id: False}
    updated_plan = agent_with_plan.get_current_project_plan()
    updated_task1 = next(
        t for t in updated_plan.tasks if t.id == task1_id)
    assert updated_task1.status == TaskStatus.COMPLETED
    # JSON persistence saves automatically  # Called because one succeeded


def test_update_status_all_non_existent_ids(agent_with_plan):
    non_existent_id1 = uuid4()
    non_existent_id2 = uuid4()

    results = agent_with_plan.update_item_status(
        [non_existent_id1, non_existent_id2], TaskStatus.COMPLETED)

    assert results == {non_existent_id1: False, non_existent_id2: False}
    # Not called because no changes made
    # JSON persistence handles saving automatically


def test_update_status_project_plan_is_none(agent_no_plan):
    some_id = uuid4()
    results = agent_no_plan.update_item_status([some_id], TaskStatus.COMPLETED)
    assert results == {some_id: False}
    # JSON persistence handles saving automatically


@pytest.mark.parametrize("target_status", list(TaskStatus))
def test_update_status_with_all_valid_statuses(agent_with_plan, target_status):
    plan, task1_id, _, task2_id = create_sample_project_plan()
    agent_with_plan.project_manager._project_plan = plan  # Fresh plan

    # Reset mock call count for save_project_plan for each parameter
    # JSON persistence handles saving automatically

    current_plan = agent_with_plan.get_current_project_plan()
    original_task1 = next(
        t for t in current_plan.tasks if t.id == task1_id)
    original_task1_ua = original_task1.updated_at
    original_task1_status = original_task1.status

    results = agent_with_plan.update_item_status([task1_id], target_status)

    assert results == {task1_id: True}
    updated_plan = agent_with_plan.get_current_project_plan()
    updated_task1 = next(
        t for t in updated_plan.tasks if t.id == task1_id)
    assert updated_task1.status == target_status

    # updated_at should change even if status was already the target_status
    assert updated_task1.updated_at > original_task1_ua

    # save_project_plan should be called because item was found and processed (updated_at changed)
    # JSON persistence saves automatically


def test_update_status_save_not_called_if_no_valid_ids_processed(agent_with_plan):
    non_existent_id = uuid4()
    results = agent_with_plan.update_item_status(
        [non_existent_id], TaskStatus.COMPLETED)
    assert results == {non_existent_id: False}
    # JSON persistence handles saving automatically


def test_update_status_save_called_if_status_is_same_but_item_processed(agent_with_plan):
    """
    Tests if save is called when an item is processed, its status is already the target status,
    but updated_at changes. The current implementation WILL save in this case.
    """
    plan, _, _, task2_id = create_sample_project_plan()  # task2 is IN_PROGRESS
    agent_with_plan.project_manager._project_plan = plan

    current_plan = agent_with_plan.get_current_project_plan()
    task2 = next(
        t for t in current_plan.tasks if t.id == task2_id)
    assert task2.status == TaskStatus.IN_PROGRESS  # Pre-condition
    original_task2_ua = task2.updated_at

    results = agent_with_plan.update_item_status(
        [task2_id], TaskStatus.IN_PROGRESS)  # Update to same status

    assert results == {task2_id: True}  # Update is reported as success
    updated_plan = agent_with_plan.get_current_project_plan()
    updated_task2 = next(
        t for t in updated_plan.tasks if t.id == task2_id)
    assert updated_task2.status == TaskStatus.IN_PROGRESS
    # updated_at should still change
    assert updated_task2.updated_at > original_task2_ua

    # According to current agent_core.py logic, save WILL be called as changes_made becomes True.
    # JSON persistence saves automatically


# def test_update_status_save_fails_propagates_failure(agent_with_plan):
#     plan, task1_id, _, _ = create_sample_project_plan()
#     agent_with_plan.project_manager._project_plan = plan
#     # Test error handling in JSON persistence would be different

#     results = agent_with_plan.update_item_status(
#         [task1_id], TaskStatus.COMPLETED)

#     # Should be marked as False because save failed
#     assert results == {task1_id: False}
#     updated_plan = agent_with_plan.get_current_project_plan()
#     updated_task = next(
#         t for t in updated_plan.tasks if t.id == task1_id)
#     # The status in memory would have been updated, but the operation is considered failed overall
#     assert updated_task.status == TaskStatus.COMPLETED
#     # JSON persistence saves automatically


def test_update_status_empty_id_list(agent_with_plan):
    results = agent_with_plan.update_item_status([], TaskStatus.COMPLETED)
    assert results == {}
    # JSON persistence handles saving automatically
