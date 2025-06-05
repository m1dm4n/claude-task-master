import pytest
from uuid import uuid4, UUID
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from src.agent_core.project_io import ProjectIO
from src.agent_core.task_operations import TaskOperations
from src.agent_core.dependency_logic import DependencyManager
from src.agent_core.llm_generator import LLMGenerator
from src.data_models import Task, TaskStatus, TaskPriority, ProjectPlan, AppConfig, ModelConfig
from src.config_manager import ConfigManager
from src.agent_core.assistant import DevTaskAIAssistant

@pytest.fixture
def mock_project_io():
    mock_pio = Mock(spec=ProjectIO)
    mock_pio.get_current_project_plan.return_value = ProjectPlan(
        project_title="Test Project",
        overall_goal="Test Goal",
        tasks=[]
    )
    mock_pio.save_project_plan.return_value = None
    return mock_pio

@pytest.fixture
def dependency_manager(mock_project_io):
    return DependencyManager(mock_project_io)

@pytest.fixture
def task_operations(mock_project_io, mock_llm_generator, dependency_manager):
    return TaskOperations(mock_project_io, mock_llm_generator, dependency_manager)
@pytest.fixture
def sample_tasks():
    """Provides a set of interconnected tasks for dependency testing."""
    task_a = Task(id=uuid4(), title="Task A", description="Desc A", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM)
    task_b = Task(id=uuid4(), title="Task B", description="Desc B", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM)
    task_c = Task(id=uuid4(), title="Task C", description="Desc C", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM)
    task_d = Task(id=uuid4(), title="Task D", description="Desc D", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM)
    task_e = Task(id=uuid4(), title="Task E", description="Desc E", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM)
    task_f = Task(id=uuid4(), title="Task F", description="Desc F", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM)

    return {
        "A": task_a, "B": task_b, "C": task_c,
        "D": task_d, "E": task_e, "F": task_f
    }

def set_project_plan_tasks(mock_project_io, tasks_dict):
    mock_project_io.get_current_project_plan.return_value.tasks = list(tasks_dict.values())
    mock_project_io.get_current_project_plan.return_value.tasks = list(tasks_dict.values())

class TestPhase10DependencyManager:

    def test_add_dependencies_success(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        task_a = sample_tasks["A"]
        task_b = sample_tasks["B"]
 
        success = dependency_manager.add_dependencies(task_a.id, [task_b.id])
        assert success
        assert task_b.id in task_a.dependencies
        mock_project_io.save_project_plan.assert_called_once()

    def test_add_dependencies_already_exists(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        task_a = sample_tasks["A"]
        task_b = sample_tasks["B"]
        task_a.dependencies.append(task_b.id)
 
        success = dependency_manager.add_dependencies(task_a.id, [task_b.id])
        assert not success
        assert task_a.dependencies.count(task_b.id) == 1
        mock_project_io.save_project_plan.assert_not_called()

    def test_remove_dependencies_success(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        task_a = sample_tasks["A"]
        task_b = sample_tasks["B"]
        task_a.dependencies.append(task_b.id)
 
        success = dependency_manager.remove_dependencies(task_a.id, [task_b.id])
        assert success
        assert task_b.id not in task_a.dependencies
        mock_project_io.save_project_plan.assert_called_once()

    def test_remove_dependencies_not_found(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        task_a = sample_tasks["A"]
        task_b = sample_tasks["B"]
 
        success = dependency_manager.remove_dependencies(task_a.id, [task_b.id])
        assert not success
        mock_project_io.save_project_plan.assert_not_called()

    def test_is_circular_dependency_no_cycle(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        sample_tasks["A"].dependencies.append(sample_tasks["B"].id)
        sample_tasks["B"].dependencies.append(sample_tasks["C"].id)
 
        tasks_map = {t.id: t for t in sample_tasks.values()}
 
        assert not dependency_manager._is_circular_dependency(sample_tasks["C"].id, sample_tasks["D"].id, tasks_map)
        assert not dependency_manager._is_circular_dependency(sample_tasks["A"].id, sample_tasks["D"].id, tasks_map)

    def test_is_circular_dependency_direct_cycle(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        tasks_map = {t.id: t for t in sample_tasks.values()}
 
        sample_tasks["A"].dependencies.append(sample_tasks["B"].id)
        assert dependency_manager._is_circular_dependency(sample_tasks["B"].id, sample_tasks["A"].id, tasks_map)

    def test_is_circular_dependency_indirect_cycle(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        sample_tasks["A"].dependencies.append(sample_tasks["B"].id)
        sample_tasks["B"].dependencies.append(sample_tasks["C"].id)
        
        tasks_map = {t.id: t for t in sample_tasks.values()}
        assert dependency_manager._is_circular_dependency(sample_tasks["C"].id, sample_tasks["A"].id, tasks_map)

    def test_is_circular_dependency_self_dependency(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        tasks_map = {t.id: t for t in sample_tasks.values()}
        assert dependency_manager._is_circular_dependency(sample_tasks["A"].id, sample_tasks["A"].id, tasks_map)

    def test_get_canonical_cycle(self, dependency_manager):
        u1, u2, u3, u4 = uuid4(), uuid4(), uuid4(), uuid4()
        
        cycle1 = [u1, u2, u3]
        cycle1_rotated_1 = [u2, u3, u1]
        cycle1_rotated_2 = [u3, u1, u2]
 
        canonical1 = dependency_manager._get_canonical_cycle(cycle1)
        canonical_rotated_1 = dependency_manager._get_canonical_cycle(cycle1_rotated_1)
        canonical_rotated_2 = dependency_manager._get_canonical_cycle(cycle1_rotated_2)
 
        assert canonical1 == canonical_rotated_1 == canonical_rotated_2
        assert canonical1[0] == min(cycle1, key=str)
 
        t1 = UUID(int=1)
        t2 = UUID(int=2)
        t3 = UUID(int=3)
        t4 = UUID(int=4)
 
        cycle_path_1 = [t1, t2, t3]
        cycle_path_2 = [t2, t3, t1]
        cycle_path_3 = [t3, t1, t2]
 
        assert dependency_manager._get_canonical_cycle(cycle_path_1) == (t1, t2, t3)
        assert dependency_manager._get_canonical_cycle(cycle_path_2) == (t1, t2, t3)
        assert dependency_manager._get_canonical_cycle(cycle_path_3) == (t1, t2, t3)
 
        path_with_dupes = [t1, t2, t1, t3, t4]
        assert dependency_manager._get_canonical_cycle(path_with_dupes) == (t1, t2, t1, t3, t4)

    def test_validate_all_dependencies_no_errors(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        sample_tasks["A"].dependencies.append(sample_tasks["B"].id)
        sample_tasks["C"].dependencies.append(sample_tasks["D"].id)
 
        errors = dependency_manager.validate_all_dependencies()
        assert not errors["circular"]
        assert not errors["missing_ids"]

    def test_validate_all_dependencies_missing_id(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        non_existent_uuid = uuid4()
        sample_tasks["A"].dependencies.append(non_existent_uuid)
 
        errors = dependency_manager.validate_all_dependencies()
        assert not errors["circular"]
        assert len(errors["missing_ids"]) == 1
        assert f"Task 'Task A' (ID: {sample_tasks['A'].id}) depends on non-existent task ID: {non_existent_uuid}" in errors["missing_ids"]

    def test_validate_all_dependencies_single_cycle(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        sample_tasks["A"].dependencies.append(sample_tasks["B"].id)
        sample_tasks["B"].dependencies.append(sample_tasks["C"].id)
        sample_tasks["C"].dependencies.append(sample_tasks["A"].id)
 
        errors = dependency_manager.validate_all_dependencies()
        assert not errors["missing_ids"]
        assert len(errors["circular"]) == 1
        
        cycle_str = errors["circular"][0]
        assert "Circular dependency detected:" in cycle_str
        assert str(sample_tasks["A"].id) in cycle_str
        assert str(sample_tasks["B"].id) in cycle_str
        assert str(sample_tasks["C"].id) in cycle_str

    def test_validate_all_dependencies_multiple_cycles(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        sample_tasks["A"].dependencies.append(sample_tasks["B"].id)
        sample_tasks["B"].dependencies.append(sample_tasks["C"].id)
        sample_tasks["C"].dependencies.append(sample_tasks["A"].id)
 
        sample_tasks["D"].dependencies.append(sample_tasks["E"].id)
        sample_tasks["E"].dependencies.append(sample_tasks["D"].id)
 
        errors = dependency_manager.validate_all_dependencies()
        assert not errors["missing_ids"]
        assert len(errors["circular"]) == 2
 
        cycle_a_b_c = dependency_manager._get_canonical_cycle([sample_tasks["A"].id, sample_tasks["B"].id, sample_tasks["C"].id])
        cycle_d_e = dependency_manager._get_canonical_cycle([sample_tasks["D"].id, sample_tasks["E"].id])
 
        found_canonical_cycles = set()
        for err_msg in errors["circular"]:
            parts = err_msg.split(" -> ")
            cycle_uuids_str = parts[1:] if parts[0].startswith("Circular dependency detected:") else parts
            if len(cycle_uuids_str) > 1 and cycle_uuids_str[-1] == cycle_uuids_str[0]:
                cycle_uuids_str = cycle_uuids_str[:-1]
            
            cycle_uuids = [UUID(s) for s in cycle_uuids_str if s.strip()]
            if cycle_uuids:
                found_canonical_cycles.add(dependency_manager._get_canonical_cycle(cycle_uuids))
        
        assert cycle_a_b_c in found_canonical_cycles
        assert cycle_d_e in found_canonical_cycles

    def test_validate_all_dependencies_complex_graph_multiple_unique_elementary_cycles(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        sample_tasks["A"].dependencies.append(sample_tasks["B"].id)
        sample_tasks["B"].dependencies.append(sample_tasks["C"].id)
        sample_tasks["C"].dependencies.append(sample_tasks["A"].id)
 
        sample_tasks["B"].dependencies.append(sample_tasks["D"].id)
        sample_tasks["D"].dependencies.append(sample_tasks["E"].id)
        sample_tasks["E"].dependencies.append(sample_tasks["B"].id)
 
        sample_tasks["C"].dependencies.append(sample_tasks["F"].id)
        sample_tasks["F"].dependencies.append(sample_tasks["D"].id)
 
        errors = dependency_manager.validate_all_dependencies()
        assert not errors["missing_ids"]
        assert len(errors["circular"]) == 3
 
        cycle1_canonical = dependency_manager._get_canonical_cycle([sample_tasks["A"].id, sample_tasks["B"].id, sample_tasks["C"].id])
        cycle2_canonical = dependency_manager._get_canonical_cycle([sample_tasks["B"].id, sample_tasks["D"].id, sample_tasks["E"].id])
        
        found_canonical_cycles = set()
        for err_msg in errors["circular"]:
            parts = err_msg.split(" -> ")
            cycle_uuids_str = parts[1:] if parts[0].startswith("Circular dependency detected:") else parts
            if len(cycle_uuids_str) > 1 and cycle_uuids_str[-1] == cycle_uuids_str[0]:
                cycle_uuids_str = cycle_uuids_str[:-1]
            
            cycle_uuids = [UUID(s) for s in cycle_uuids_str if s.strip()]
            if cycle_uuids:
                found_canonical_cycles.add(dependency_manager._get_canonical_cycle(cycle_uuids))
        
        assert cycle1_canonical in found_canonical_cycles
        assert cycle2_canonical in found_canonical_cycles

    def test_validate_all_dependencies_no_circular_when_path_splits(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        sample_tasks["A"].dependencies.append(sample_tasks["B"].id)
        sample_tasks["A"].dependencies.append(sample_tasks["C"].id)
        sample_tasks["B"].dependencies.append(sample_tasks["D"].id)
        sample_tasks["C"].dependencies.append(sample_tasks["D"].id)
 
        errors = dependency_manager.validate_all_dependencies()
        assert not errors["circular"]
        assert not errors["missing_ids"]

    def test_validate_all_dependencies_disconnected_graph(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        sample_tasks["A"].dependencies.append(sample_tasks["B"].id)
 
        errors = dependency_manager.validate_all_dependencies()
        assert not errors["circular"]
        assert not errors["missing_ids"]

    def test_validate_all_dependencies_empty_plan(self, dependency_manager, mock_project_io):
        mock_project_io.get_current_project_plan.return_value = None
        errors = dependency_manager.validate_all_dependencies()
        assert not errors["circular"]
        assert not errors["missing_ids"]

    def test_validate_all_dependencies_empty_tasks_list(self, dependency_manager, mock_project_io):
        mock_project_io.get_current_project_plan.return_value.tasks = []
        errors = dependency_manager.validate_all_dependencies()
        assert not errors["circular"]
        assert not errors["missing_ids"]

    def test_add_dependencies_circular_prevention(self, dependency_manager, mock_project_io, sample_tasks):
        set_project_plan_tasks(mock_project_io, sample_tasks)
        
        sample_tasks["A"].dependencies.append(sample_tasks["B"].id)
 
        success = dependency_manager.add_dependencies(sample_tasks["B"].id, [sample_tasks["A"].id])
        assert not success
        assert sample_tasks["A"].id not in sample_tasks["B"].dependencies
        mock_project_io.save_project_plan.assert_not_called()
 
        sample_tasks["B"].dependencies.append(sample_tasks["C"].id)
        success = dependency_manager.add_dependencies(sample_tasks["C"].id, [sample_tasks["A"].id])
        assert not success
        assert sample_tasks["A"].id not in sample_tasks["C"].dependencies
        mock_project_io.save_project_plan.assert_not_called()

    @pytest.fixture
    def mock_llm_generator(self):
        mock_lg = Mock(spec=LLMGenerator)
        mock_lg.suggest_dependency_fixes = AsyncMock(return_value=ProjectPlan(
            project_title="Fixed Plan", overall_goal="Fixed Goal", tasks=[]
        ))
        return mock_lg
    @pytest.fixture
    def dev_task_ai_assistant(self, mock_project_io, mock_llm_generator, dependency_manager, task_operations, tmp_path):
        with patch('src.config_manager.ConfigManager') as MockConfigManager, \
             patch('src.agent_core.llm_config.LLMConfigManager') as MockLLMConfigManager, \
             patch('src.agent_core.llm_provider.LLMProvider') as MockLLMProvider, \
             patch('src.agent_core.plan_builder.PlanBuilder') as MockPlanBuilder:

            mock_config_manager_instance = MockConfigManager.return_value
            mock_config_manager_instance.get_all_model_configs.return_value = {}
            mock_config_manager_instance.get_model_config.return_value = Mock(model_name="test-model", provider="test-provider")
            
            mock_config_instance = Mock()
            mock_config_instance.project_plan_file = tmp_path / "project_plan.json"
            mock_config_instance.tasks_dir = "tasks"
            mock_config_manager_instance.config = mock_config_instance
            
            assistant = DevTaskAIAssistant(workspace_dir=str(tmp_path))
            assistant.config_manager = mock_config_manager_instance
            assistant.llm_config_manager = MockLLMConfigManager.return_value
            assistant.llm_provider = MockLLMProvider.return_value
            assistant.llm_generator = mock_llm_generator
            assistant.plan_builder = MockPlanBuilder.return_value
            assistant.project_io = mock_project_io
            assistant.task_operations = task_operations
            assistant.dependency_manager = dependency_manager
            return assistant
    @pytest.mark.asyncio
    async def test_fix_dependencies_no_errors_initially(self, dev_task_ai_assistant, mock_project_io):
        mock_project_io.get_current_project_plan.return_value.tasks = [
            Task(id=uuid4(), title="T1", description="", status=TaskStatus.PENDING),
            Task(id=uuid4(), title="T2", description="", status=TaskStatus.PENDING)
        ]
        
        with patch.object(dev_task_ai_assistant.dependency_manager, 'validate_all_dependencies', return_value={"circular": [], "missing_ids": []}):
            messages = await dev_task_ai_assistant.fix_dependencies(remove_invalid=True, remove_circular=True)
            assert "No dependency errors found. No fixes needed." in messages[0]
            dev_task_ai_assistant.llm_generator.suggest_dependency_fixes.assert_not_called()
            mock_project_io.save_project_plan.assert_not_called()

    @pytest.mark.asyncio
    async def test_fix_dependencies_with_errors_and_successful_fix(self, dev_task_ai_assistant, mock_project_io, sample_tasks):
        task_a = sample_tasks["A"]
        task_b = sample_tasks["B"]
        task_c = sample_tasks["C"]
        task_d = sample_tasks["D"]
 
        task_a.dependencies.append(task_b.id)
        task_b.dependencies.append(task_c.id)
        task_c.dependencies.append(task_a.id)
 
        set_project_plan_tasks(mock_project_io, {
            "A": task_a, "B": task_b, "C": task_c, "D": task_d
        })
 
        initial_errors = {
            "circular": [f"Circular dependency detected: {task_a.id} -> {task_b.id} -> {task_c.id} -> {task_a.id}"],
            "missing_ids": []
        }
        with patch.object(dev_task_ai_assistant.dependency_manager, 'validate_all_dependencies', side_effect=[initial_errors, {"circular": [], "missing_ids": []}]):
            fixed_task_c = Task(id=task_c.id, title=task_c.title, description=task_c.description, status=task_c.status, priority=task_c.priority, dependencies=[])
            
            mock_llm_plan = ProjectPlan(
                project_title="Fixed Plan", overall_goal="Fixed Goal",
                tasks=[task_a, task_b, fixed_task_c, task_d]
            )
            dev_task_ai_assistant.llm_generator.suggest_dependency_fixes.return_value = mock_llm_plan
            
            messages = await dev_task_ai_assistant.fix_dependencies(remove_circular=True)
            
            assert "All identified dependency errors have been fixed." in messages
            dev_task_ai_assistant.llm_generator.suggest_dependency_fixes.assert_called_once()
            mock_project_io.save_project_plan.assert_called_once()
            
            updated_task_c = dev_task_ai_assistant.get_item_by_id(task_c.id)
 
            assert updated_task_c.dependencies == []

    @pytest.mark.asyncio
    async def test_fix_dependencies_with_errors_and_partial_fix(self, dev_task_ai_assistant, mock_project_io, sample_tasks):
        task_a = sample_tasks["A"]
        task_b = sample_tasks["B"]
        task_c = sample_tasks["C"]
        task_d = sample_tasks["D"]
        task_e = sample_tasks["E"]
        non_existent_uuid = uuid4()
 
        task_a.dependencies.append(task_b.id)
        task_b.dependencies.append(task_a.id)
        task_c.dependencies.append(non_existent_uuid)
        task_d.dependencies.append(task_e.id)
        task_e.dependencies.append(task_d.id)
 
        set_project_plan_tasks(mock_project_io, {
            "A": task_a, "B": task_b, "C": task_c, "D": task_d, "E": task_e
        })
 
        initial_errors = {
            "circular": [
                f"Circular dependency detected: {task_a.id} -> {task_b.id} -> {task_a.id}",
                f"Circular dependency detected: {task_d.id} -> {task_e.id} -> {task_d.id}"
            ],
            "missing_ids": [f"Task 'Task C' (ID: {task_c.id}) depends on non-existent task ID: {non_existent_uuid}"]
        }
        remaining_errors = {
            "circular": [f"Circular dependency detected: {task_d.id} -> {task_e.id} -> {task_d.id}"],
            "missing_ids": []
        }
        with patch.object(dev_task_ai_assistant.dependency_manager, 'validate_all_dependencies', side_effect=[
            initial_errors,
            remaining_errors
        ]):
            fixed_task_a = Task(id=task_a.id, title=task_a.title, description=task_a.description, status=task_a.status, priority=task_a.priority, dependencies=[])
            fixed_task_b = Task(id=task_b.id, title=task_b.title, description=task_b.description, status=task_b.status, priority=task_b.priority, dependencies=[])
            fixed_task_c = Task(id=task_c.id, title=task_c.title, description=task_c.description, status=task_c.status, priority=task_c.priority, dependencies=[])
        
            mock_llm_plan = ProjectPlan(
                project_title="Fixed Plan", overall_goal="Fixed Goal",
                tasks=[fixed_task_a, fixed_task_b, fixed_task_c, task_d, task_e]
            )
            dev_task_ai_assistant.llm_generator.suggest_dependency_fixes.return_value = mock_llm_plan
        
            messages = await dev_task_ai_assistant.fix_dependencies(remove_invalid=True, remove_circular=True)
            
            assert f"Fixed some dependencies. Remaining errors: {remaining_errors}" in messages
            dev_task_ai_assistant.llm_generator.suggest_dependency_fixes.assert_called_once()
            mock_project_io.save_project_plan.assert_called_once()
            
            updated_task_a = dev_task_ai_assistant.get_item_by_id(task_a.id)
            updated_task_b = dev_task_ai_assistant.get_item_by_id(task_b.id)
            updated_task_c = dev_task_ai_assistant.get_item_by_id(task_c.id)
            updated_task_d = dev_task_ai_assistant.get_item_by_id(task_d.id)
            updated_task_e = dev_task_ai_assistant.get_item_by_id(task_e.id)
 
            assert updated_task_a.dependencies == []
            assert updated_task_b.dependencies == []
            assert updated_task_c.dependencies == []
            assert updated_task_d.dependencies == [task_e.id]
            assert updated_task_e.dependencies == [task_d.id]