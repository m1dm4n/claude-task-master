import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime

# Assuming data_models.py and agent_core.py are in a package 'src'
# and tests are run from the project root.
from src.data_models import Task, ProjectPlan, TaskStatus, TaskPriority, ModelConfig, AppConfig
from src.agent_core.assistant import DevTaskAIAssistant
from src.agent_core.project_io import ProjectIO
from src.agent_core.task_operations import TaskOperations
from src.agent_core.llm_config import LLMConfigManager
from src.agent_core.llm_provider import LLMProvider
from src.agent_core.llm_generator import LLMGenerator
from src.agent_core.plan_builder import PlanBuilder
from src.agent_core.dependency_logic import DependencyManager

class TestAgentCorePhase5(unittest.TestCase):

    @patch('src.config_manager.ConfigManager')
    @patch('src.agent_core.llm_config.LLMConfigManager')
    @patch('src.agent_core.llm_provider.LLMProvider')
    @patch('src.agent_core.llm_generator.LLMGenerator')
    @patch('src.agent_core.plan_builder.PlanBuilder')
    @patch('src.agent_core.project_io.ProjectIO')
    @patch('src.agent_core.task_operations.TaskOperations')
    @patch('src.agent_core.dependency_logic.DependencyManager')
    def setUp(self, MockDependencyManager, MockTaskOperations, MockProjectIO, MockPlanBuilder, MockLLMGenerator, MockLLMProvider, MockLLMConfigManager, MockConfigManager):
        self.mock_config_manager_instance = MockConfigManager.return_value
        self.mock_llm_config_manager_instance = MockLLMConfigManager.return_value
        self.mock_llm_provider_instance = MockLLMProvider.return_value
        self.mock_llm_generator_instance = MockLLMGenerator.return_value
        self.mock_plan_builder_instance = MockPlanBuilder.return_value
        self.mock_project_io_instance = MockProjectIO.return_value
        self.mock_task_operations_instance = MockTaskOperations.return_value
        self.mock_dependency_manager_instance = MockDependencyManager.return_value

        mock_main_model_cfg = ModelConfig(model_name="mock-main", provider="mock")
        mock_research_model_cfg = ModelConfig(model_name="mock-research", provider="mock")
        mock_fallback_model_cfg = ModelConfig(model_name="mock-fallback", provider="mock")

        mock_app_config = AppConfig(
            main_model=mock_main_model_cfg,
            research_model=mock_research_model_cfg,
            fallback_model=mock_fallback_model_cfg,
            project_plan_file="project_plan.json",
            tasks_dir="tasks"
        )
        self.mock_config_manager_instance.config = mock_app_config
        self.mock_config_manager_instance.load_or_initialize_config.return_value = mock_app_config
        self.mock_config_manager_instance.get_model_config.side_effect = lambda model_type: {
            "main": mock_main_model_cfg, "research": mock_research_model_cfg, "fallback": mock_fallback_model_cfg
        }.get(model_type)
        self.mock_config_manager_instance.get_all_model_configs.return_value = {
            "main": mock_main_model_cfg, "research": mock_research_model_cfg, "fallback": mock_fallback_model_cfg
        }

        self.agent = DevTaskAIAssistant(workspace_dir="dummy_workspace")
        self.agent.config_manager = self.mock_config_manager_instance
        self.agent.llm_config_manager = self.mock_llm_config_manager_instance
        self.agent.llm_provider = self.mock_llm_provider_instance
        self.agent.llm_generator = self.mock_llm_generator_instance
        self.agent.plan_builder = self.mock_plan_builder_instance
        self.agent.project_io = self.mock_project_io_instance
        self.agent.task_operations = self.mock_task_operations_instance
        self.agent.dependency_manager = self.mock_dependency_manager_instance

    def _create_task(self, status=TaskStatus.PENDING, dependencies=None, title_suffix="", **kwargs):
        if dependencies is None:
            dependencies = []
        # Ensure dependencies are strings as per data_models.py
        str_dependencies = [str(dep) for dep in dependencies]
        return Task(
            id=uuid4(),
            title=f"Test Task {title_suffix}",
            description="Test task description", # Added required description
            status=status,
            dependencies=str_dependencies,
            **kwargs
        )

    @patch('src.agent_core.task_operations.logfire')
    @patch('src.agent_core.dependency_logic.logger')
    def test_get_next_task_no_project_plan(self, mock_logger, mock_logfire):
        self.agent.project_io.get_current_project_plan.return_value = None
        self.assertIsNone(self.agent.get_next_task())
        mock_logger.warn.assert_called_with("Cannot determine next task: Project plan not loaded or initialized.")
    @patch('src.agent_core.dependency_logic.logger')
    def test_get_next_task_empty_project_plan(self, mock_logger):
        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(project_title="Empty Test Plan", overall_goal="Goal for empty plan", tasks=[])
        self.assertIsNone(self.agent.get_next_task())
        mock_logger.info.assert_called_with("No actionable pending tasks found.")

    @patch('src.agent_core.dependency_logic.logger')
    def test_get_next_task_no_pending_tasks(self, mock_logger):
        task1 = self._create_task(status=TaskStatus.COMPLETED)
        task2 = self._create_task(status=TaskStatus.IN_PROGRESS)
        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(project_title="Test Plan No Pending", overall_goal="Goal for no pending", tasks=[task1, task2])
        self.assertIsNone(self.agent.get_next_task())
        mock_logger.info.assert_called_with("No actionable pending tasks found.")

    @patch('src.agent_core.dependency_logic.logger')
    def test_get_next_task_pending_task_no_dependencies(self, mock_logger):
        task_pending = self._create_task(status=TaskStatus.PENDING, title_suffix="NoDeps")
        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(project_title="Test Plan Single Pending", overall_goal="Goal for single pending", tasks=[task_pending])
        next_task = self.agent.get_next_task()
        self.assertEqual(next_task, task_pending)
        mock_logger.info.assert_called_with(f"Identified next actionable task: {task_pending.title} (ID: {task_pending.id})")

    @patch('src.agent_core.task_operations.logfire')
    @patch('src.agent_core.dependency_logic.logger')
    def test_get_next_task_pending_task_with_all_dependencies_completed(self, mock_logger, mock_logfire):
        dep1 = self._create_task(status=TaskStatus.COMPLETED, title_suffix="Dep1")
        task_pending = self._create_task(status=TaskStatus.PENDING, dependencies=[dep1.id], title_suffix="WithCompDeps")
        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(project_title="Test Plan Comp Deps", overall_goal="Goal for comp deps", tasks=[dep1, task_pending])
        next_task = self.agent.get_next_task()
        self.assertEqual(next_task, task_pending)
        mock_logger.info.assert_called_with(f"Identified next actionable task: {task_pending.title} (ID: {task_pending.id})")
    @patch('src.agent_core.dependency_logic.logger')
    def test_get_next_task_pending_task_with_some_dependencies_not_completed(self, mock_logger):
        dep_completed = self._create_task(status=TaskStatus.COMPLETED, title_suffix="DepComp")
        dep_pending = self._create_task(status=TaskStatus.PENDING, title_suffix="DepPend")
        task_blocked = self._create_task(status=TaskStatus.PENDING, dependencies=[dep_completed.id, dep_pending.id], title_suffix="Blocked")
        
        eligible_task = self._create_task(status=TaskStatus.PENDING, title_suffix="EligibleStandalone")

        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(
            project_title="Test Plan Some Not Comp",
            overall_goal="Goal for some not comp",
            tasks=[dep_completed, dep_pending, task_blocked, eligible_task]
        )
        next_task = self.agent.get_next_task()
        self.assertEqual(next_task, dep_pending)
        mock_logger.info.assert_called_with(f"Identified next actionable task: {dep_pending.title} (ID: {dep_pending.id})")
    @patch('src.agent_core.dependency_logic.logger')
    def test_get_next_task_pending_task_with_all_dependencies_not_completed(self, mock_logger):
        dep1_pending = self._create_task(status=TaskStatus.PENDING, title_suffix="Dep1Pend")
        dep2_in_progress = self._create_task(status=TaskStatus.IN_PROGRESS, title_suffix="Dep2InProg")
        task_blocked = self._create_task(status=TaskStatus.PENDING, dependencies=[dep1_pending.id, dep2_in_progress.id], title_suffix="BlockedAllNotComp")
        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(project_title="Test Plan All Not Comp", overall_goal="Goal for all not comp", tasks=[dep1_pending, dep2_in_progress, task_blocked])
        next_task_obj = self.agent.get_next_task()
        self.assertEqual(next_task_obj, dep1_pending)
        mock_logger.info.assert_called_with(f"Identified next actionable task: {dep1_pending.title} (ID: {dep1_pending.id})")

    def test_get_next_task_multiple_eligible_tasks_returns_first(self):
        task_eligible1 = self._create_task(status=TaskStatus.PENDING, title_suffix="Eligible1")
        task_eligible2 = self._create_task(status=TaskStatus.PENDING, title_suffix="Eligible2")
        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(project_title="Test Plan Multi Eligible", overall_goal="Goal for multi eligible", tasks=[task_eligible1, task_eligible2])
        next_task = self.agent.get_next_task()
        self.assertEqual(next_task, task_eligible1)

    def test_get_next_task_multiple_eligible_tasks_mix_no_deps_and_deps_completed(self):
        dep_completed = self._create_task(status=TaskStatus.COMPLETED, title_suffix="DepForB")
        task_a_no_deps = self._create_task(status=TaskStatus.PENDING, title_suffix="A_NoDeps")
        task_b_deps_completed = self._create_task(status=TaskStatus.PENDING, dependencies=[dep_completed.id], title_suffix="B_DepsComp")

        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(project_title="Test Plan Mix 1", overall_goal="Goal for mix 1", tasks=[task_a_no_deps, dep_completed, task_b_deps_completed])
        next_task = self.agent.get_next_task()
        self.assertEqual(next_task, task_a_no_deps)

        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(project_title="Test Plan Mix 2", overall_goal="Goal for mix 2", tasks=[dep_completed, task_b_deps_completed, task_a_no_deps])
        next_task = self.agent.get_next_task()
        self.assertEqual(next_task, task_b_deps_completed)

    @patch('src.agent_core.dependency_logic.logger')
    def test_get_next_task_pending_task_with_non_existent_dependency(self, mock_logger):
        non_existent_dep_id = uuid4()
        task_blocked_by_missing_dep = self._create_task(status=TaskStatus.PENDING, dependencies=[non_existent_dep_id], title_suffix="MissingDep")
        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(project_title="Test Plan Non-Exist Dep", overall_goal="Goal for non-exist dep", tasks=[task_blocked_by_missing_dep])
        self.assertIsNone(self.agent.get_next_task())
        mock_logger.warn.assert_called_with(f"Dependency task {str(non_existent_dep_id)} for task {task_blocked_by_missing_dep.id} not found. Assuming blocked.")

    def test_get_next_task_order_with_blocked_by_missing_dep_and_eligible(self):
        non_existent_dep_id = uuid4()
        task_blocked = self._create_task(status=TaskStatus.PENDING, dependencies=[non_existent_dep_id], title_suffix="BlockedMissing")
        task_eligible = self._create_task(status=TaskStatus.PENDING, title_suffix="EligibleStandalone")
        
        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(project_title="Test Plan Missing Dep Eligible", overall_goal="Goal for missing dep eligible", tasks=[task_blocked, task_eligible])
        next_task = self.agent.get_next_task()
        self.assertEqual(next_task, task_eligible)

    @patch('src.agent_core.dependency_logic.logger')
    def test_get_next_task_order_with_blocked_by_pending_dep_and_eligible(self, mock_logger):
        dep_pending = self._create_task(status=TaskStatus.PENDING, title_suffix="DepBlocker")
        task_blocked = self._create_task(status=TaskStatus.PENDING, dependencies=[dep_pending.id], title_suffix="BlockedByPending")
        task_eligible = self._create_task(status=TaskStatus.PENDING, title_suffix="EligibleAfterBlocked")

        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(
            project_title="Test Plan Pending Dep Eligible",
            overall_goal="Goal for pending dep eligible",
            tasks=[dep_pending, task_blocked, task_eligible]
        )
        next_task = self.agent.get_next_task()
        self.assertEqual(next_task, dep_pending)
        mock_logger.info.assert_called_with(f"Identified next actionable task: {dep_pending.title} (ID: {dep_pending.id})")

    def test_get_next_task_complex_scenario_correct_selection(self):
        task1_completed = self._create_task(status=TaskStatus.COMPLETED, title_suffix="1_Comp")
        task2_eligible = self._create_task(status=TaskStatus.PENDING, dependencies=[task1_completed.id], title_suffix="2_Eligible")
        
        task4_pending_dep_for_3 = self._create_task(status=TaskStatus.PENDING, title_suffix="4_PendDepFor3")
        task3_blocked_by_4 = self._create_task(status=TaskStatus.PENDING, dependencies=[task4_pending_dep_for_3.id], title_suffix="3_BlockedBy4")
        
        task5_blocked_by_missing = self._create_task(status=TaskStatus.PENDING, dependencies=[uuid4()], title_suffix="5_BlockedMissing")

        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(project_title="Test Plan Complex", overall_goal="Goal for complex", tasks=[
            task1_completed,
            task2_eligible,
            task4_pending_dep_for_3,
            task3_blocked_by_4,
            task5_blocked_by_missing
        ])
        next_task = self.agent.get_next_task()
        self.assertEqual(next_task, task2_eligible)

    def test_get_next_task_first_eligible_among_many_pending_with_completed_deps(self):
        dep1 = self._create_task(status=TaskStatus.COMPLETED, title_suffix="Dep1")
        dep2 = self._create_task(status=TaskStatus.COMPLETED, title_suffix="Dep2")

        task_a = self._create_task(status=TaskStatus.PENDING, dependencies=[dep1.id], title_suffix="A")
        task_b = self._create_task(status=TaskStatus.PENDING, dependencies=[dep2.id], title_suffix="B")
        task_c = self._create_task(status=TaskStatus.PENDING, title_suffix="C_NoDep")

        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(project_title="Test Plan First Eligible 1", overall_goal="Goal for first eligible 1", tasks=[task_a, task_b, task_c, dep1, dep2])
        next_task = self.agent.get_next_task()
        self.assertEqual(next_task, task_a)

        self.agent.project_io.get_current_project_plan.return_value = ProjectPlan(project_title="Test Plan First Eligible 2", overall_goal="Goal for first eligible 2", tasks=[dep1, dep2, task_c, task_a, task_b])
        next_task = self.agent.get_next_task()
        self.assertEqual(next_task, task_c)

if __name__ == '__main__':
    unittest.main()