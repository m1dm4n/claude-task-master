import unittest
import os
import shutil
import sqlite3
import json
import tempfile
from pathlib import Path
from uuid import UUID, uuid4 # Import uuid4

from src.persistence_manager import PersistenceManager
from src.data_models import ProjectPlan, Task, Subtask, AppConfig, ModelConfig, TaskStatus, TaskPriority

class TestPersistenceManager(unittest.TestCase):

    def setUp(self):
        """Set up a temporary workspace for each test."""
        self.test_workspace = Path(tempfile.mkdtemp())
        
        # Create a dummy AppConfig for initialization
        self.dummy_app_config = AppConfig(
            main_model=ModelConfig(model_name="test-model", provider="test"),
            project_plan_file="project_plan.json", # This is still in AppConfig but not used for SQLite directly
            tasks_dir="tasks"
        )
        self.manager = PersistenceManager(str(self.test_workspace), self.dummy_app_config)
        self.db_path = self.test_workspace / '.tasks' / 'tasks.db'

    def tearDown(self):
        """Clean up the temporary workspace after each test."""
        shutil.rmtree(self.test_workspace)

    def test_init_and_paths(self):
        """Test initialization correctly sets paths and creates manager instance."""
        self.assertEqual(str(self.manager.workspace_path), str(self.test_workspace.resolve())) # Compare resolved paths as strings
        self.assertEqual(str(self.manager.db_path), str((self.test_workspace / '.tasks' / 'tasks.db').resolve())) # Compare resolved paths as strings
        self.assertEqual(str(self.manager.tasks_dir_path), str((self.test_workspace / 'tasks').resolve())) # Compare resolved paths as strings

    def test_initialize_project_structure(self):
        """Test initialize_project_structure creates directories, DB, and default plan."""
        # The test_workspace itself is created by tempfile.mkdtemp() in setUp, so it exists.
        # We check if *subdirectories* and DB are created.
        self.assertFalse((self.test_workspace / '.tasks').exists())
        self.assertFalse(self.db_path.exists())
        self.assertFalse((self.test_workspace / 'tasks').exists())

        self.manager.initialize_project_structure()

        self.assertTrue(self.test_workspace.exists())
        self.assertTrue((self.test_workspace / '.tasks').exists())
        self.assertTrue(self.db_path.exists())
        self.assertTrue((self.test_workspace / 'tasks').exists())

        # Verify tables are created
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        self.assertIn("project_plans", tables)
        self.assertIn("tasks", tables)
        self.assertIn("subtasks", tables)

        # Verify a default project plan is created
        loaded_plan = self.manager.load_project_plan()
        self.assertIsNotNone(loaded_plan)
        self.assertEqual(loaded_plan.project_title, "New Project")
        self.assertEqual(loaded_plan.overall_goal, "No project goal defined yet.")
        self.assertEqual(len(loaded_plan.tasks), 0)

    def test_initialize_project_structure_idempotent(self):
        """Test initialize_project_structure is idempotent and doesn't overwrite existing."""
        self.manager.initialize_project_structure() # First call
        
        # Create a custom plan
        custom_plan = ProjectPlan(
            project_title="Custom Project",
            overall_goal="To test idempotency.",
            tasks=[] # Ensure tasks is provided
        )
        self.manager.save_project_plan(custom_plan)

        self.manager.initialize_project_structure() # Second call

        # Should still load the custom plan, not a new default
        loaded_plan = self.manager.load_project_plan()
        self.assertIsNotNone(loaded_plan)
        self.assertEqual(loaded_plan.project_title, "Custom Project")
        self.assertEqual(loaded_plan.overall_goal, "To test idempotency.")


    def test_save_and_load_project_plan_full_structure(self):
        """Test saving and loading a complex ProjectPlan with tasks and subtasks."""
        self.manager.initialize_project_structure() # Ensure DB is set up

        subtask1 = Subtask(title="Subtask A", description="Desc A", status=TaskStatus.PENDING, priority=TaskPriority.LOW, details="Details for Subtask A", testStrategy="Test strategy for Subtask A", dependencies=[])
        subtask2 = Subtask(title="Subtask B", description="Desc B", status=TaskStatus.IN_PROGRESS, dependencies=[subtask1.id], priority=TaskPriority.MEDIUM, details="Details for Subtask B", testStrategy="Test strategy for Subtask B")
        
        task1 = Task(
            title="Task 1",
            description="Main task 1",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            dependencies=[],
            details="Details for Task 1",
            testStrategy="Test strategy for Task 1",
            subtasks=[subtask1, subtask2]
        )
        task2 = Task(title="Task 2", description="Main task 2", status=TaskStatus.COMPLETED, dependencies=[task1.id], priority=TaskPriority.LOW, details="Details for Task 2", testStrategy="Test strategy for Task 2")

        original_plan = ProjectPlan(
            project_title="Complex Project",
            overall_goal="Test complex plan saving.",
            tasks=[task1, task2],
            notes="Some notes for the complex plan."
        )

        self.manager.save_project_plan(original_plan)

        loaded_plan = self.manager.load_project_plan(str(original_plan.id))
        self.assertIsNotNone(loaded_plan)
        self.assertEqual(loaded_plan.id, original_plan.id)
        self.assertEqual(loaded_plan.project_title, original_plan.project_title)
        self.assertEqual(loaded_plan.overall_goal, original_plan.overall_goal)
        self.assertEqual(loaded_plan.notes, original_plan.notes)

        self.assertEqual(len(loaded_plan.tasks), len(original_plan.tasks))

        # Compare tasks
        for loaded_t, original_t in zip(loaded_plan.tasks, original_plan.tasks):
            self.assertEqual(loaded_t.id, original_t.id)
            self.assertEqual(loaded_t.title, original_t.title)
            self.assertEqual(loaded_t.description, original_t.description)
            self.assertEqual(loaded_t.status, original_t.status)
            self.assertListEqual(loaded_t.dependencies, original_t.dependencies)
            self.assertEqual(loaded_t.priority, original_t.priority) # Now can be None
            
            self.assertEqual(len(loaded_t.subtasks), len(original_t.subtasks))
            # Compare subtasks
            for loaded_st, original_st in zip(loaded_t.subtasks, original_t.subtasks):
                self.assertEqual(loaded_st.id, original_st.id)
                self.assertEqual(loaded_st.title, original_st.title)
                self.assertEqual(loaded_st.description, original_st.description)
                self.assertEqual(loaded_st.status, original_st.status)
                self.assertListEqual(loaded_st.dependencies, original_st.dependencies)
                self.assertEqual(loaded_st.priority, original_st.priority) # Now can be None
                
    def test_save_project_plan_update_existing(self):
        """Test saving an existing project plan updates it."""
        self.manager.initialize_project_structure()
        
        initial_plan = ProjectPlan(project_title="Update Test", overall_goal="Initial goal", tasks=[]) # Ensure tasks is provided
        self.manager.save_project_plan(initial_plan)

        # Modify the plan
        initial_plan.overall_goal = "Updated goal"
        initial_plan.tasks.append(Task(title="New Task", description="Added for update", status=TaskStatus.PENDING, priority=TaskPriority.MEDIUM, dependencies=[], details="Details for New Task", testStrategy="Test strategy for New Task"))
        self.manager.save_project_plan(initial_plan) # Save updated plan

        loaded_plan = self.manager.load_project_plan(str(initial_plan.id))
        self.assertIsNotNone(loaded_plan)
        self.assertEqual(loaded_plan.overall_goal, "Updated goal")
        self.assertEqual(len(loaded_plan.tasks), 1)
        self.assertEqual(loaded_plan.tasks[0].title, "New Task")

        # Verify old tasks/subtasks are correctly deleted before new ones are inserted
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_plan_id = ?", (str(initial_plan.id),))
        self.assertEqual(cursor.fetchone()[0], 1) # Should only have the one new task
        conn.close()

    def test_load_project_plan_by_id(self):
        """Test loading a specific project plan by ID."""
        self.manager.initialize_project_structure()
        
        plan1 = ProjectPlan(project_title="Plan One", overall_goal="Goal 1", tasks=[]) # Ensure tasks is provided
        plan2 = ProjectPlan(project_title="Plan Two", overall_goal="Goal 2", tasks=[]) # Ensure tasks is provided

        self.manager.save_project_plan(plan1)
        self.manager.save_project_plan(plan2) # This will be the "most recent"

        loaded_plan1 = self.manager.load_project_plan(str(plan1.id))
        loaded_plan2 = self.manager.load_project_plan(str(plan2.id))

        self.assertIsNotNone(loaded_plan1)
        self.assertEqual(loaded_plan1.project_title, "Plan One")
        self.assertIsNotNone(loaded_plan2)
        self.assertEqual(loaded_plan2.project_title, "Plan Two")
        
        # Test loading without ID gets the most recent (plan2)
        loaded_recent_plan = self.manager.load_project_plan()
        self.assertEqual(loaded_recent_plan.id, plan2.id)

    def test_load_project_plan_non_existent_id(self):
        """Test loading a non-existent project plan ID returns None."""
        self.manager.initialize_project_structure()
        non_existent_id = str(UUID(int=0))
        loaded_plan = self.manager.load_project_plan(non_existent_id)
        self.assertIsNone(loaded_plan)

    def test_load_project_plan_empty_db(self):
        """Test loading when no project plans exist in the DB."""
        # Don't initialize_project_structure to simulate fresh DB without default plan
        # Manually create directories and empty DB
        (self.test_workspace / '.tasks').mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.close()
        self.manager._init_database() # Just create schema, no default plan here
        
        loaded_plan = self.manager.load_project_plan()
        self.assertIsNone(loaded_plan)

    def test_list_project_plans(self):
        """Test listing all project plans."""
        self.manager.initialize_project_structure() # Creates a default plan
        
        plan1 = ProjectPlan(project_title="Alpha Project", overall_goal="Goal A", tasks=[]) # Ensure tasks is provided
        plan2 = ProjectPlan(project_title="Beta Project", overall_goal="Goal B", tasks=[]) # Ensure tasks is provided
        self.manager.save_project_plan(plan1)
        self.manager.save_project_plan(plan2)

        plans_list = self.manager.list_project_plans()
        self.assertEqual(len(plans_list), 3) # Default plan + plan1 + plan2
        
        # Check for expected titles and IDs, sorting by title
        titles = sorted([p['project_title'] for p in plans_list])
        self.assertEqual(titles, ["Alpha Project", "Beta Project", "New Project"])
        
        # Check IDs
        ids = {p['id'] for p in plans_list}
        self.assertIn(str(plan1.id), ids)
        self.assertIn(str(plan2.id), ids)
        
    def test_delete_project_plan(self):
        """Test deleting a project plan and its associated tasks/subtasks."""
        self.manager.initialize_project_structure()
        
        subtask1 = Subtask(title="Subtask to delete", description="Desc", status=TaskStatus.PENDING, priority=TaskPriority.LOW, details="Details for subtask to delete", testStrategy="Test strategy for subtask to delete", dependencies=[])
        task1 = Task(title="Task to delete", description="Desc", status=TaskStatus.PENDING, subtasks=[subtask1], priority=TaskPriority.MEDIUM, dependencies=[], details="Details for task to delete", testStrategy="Test strategy for task to delete")
        plan_to_delete = ProjectPlan(project_title="Plan to Delete", overall_goal="Delete me", tasks=[task1])
        self.manager.save_project_plan(plan_to_delete)

        # Verify plan exists
        self.assertIsNotNone(self.manager.load_project_plan(str(plan_to_delete.id)))
        
        # Verify tasks and subtasks exist in DB
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM project_plans WHERE id = ?", (str(plan_to_delete.id),))
        self.assertEqual(cursor.fetchone()[0], 1)
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_plan_id = ?", (str(plan_to_delete.id),))
        self.assertEqual(cursor.fetchone()[0], 1)
        cursor.execute("SELECT COUNT(*) FROM subtasks WHERE task_id = ?", (str(task1.id),))
        self.assertEqual(cursor.fetchone()[0], 1)
        conn.close()

        success = self.manager.delete_project_plan(str(plan_to_delete.id))
        self.assertTrue(success)

        # Verify plan no longer exists
        self.assertIsNone(self.manager.load_project_plan(str(plan_to_delete.id)))
        
        # Verify tasks and subtasks are also deleted due to CASCADE
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM project_plans WHERE id = ?", (str(plan_to_delete.id),))
        self.assertEqual(cursor.fetchone()[0], 0)
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_plan_id = ?", (str(plan_to_delete.id),))
        self.assertEqual(cursor.fetchone()[0], 0)
        cursor.execute("SELECT COUNT(*) FROM subtasks WHERE task_id = ?", (str(task1.id),))
        self.assertEqual(cursor.fetchone()[0], 0)
        conn.close()

    def test_delete_non_existent_project_plan(self):
        """Test deleting a non-existent project plan returns True (as nothing to delete)."""
        self.manager.initialize_project_structure()
        non_existent_id = str(UUID(int=0))
        success = self.manager.delete_project_plan(non_existent_id)
        self.assertTrue(success) # Should report success if nothing was there to begin with

    def test_save_project_plan_with_missing_fields(self):
        """Test saving a plan with optional fields as None."""
        self.manager.initialize_project_structure()
        plan = ProjectPlan(
            project_title="Minimal Plan",
            overall_goal="Just the basics.",
            tasks=[]
        )
        plan.notes = None # Explicitly None
        
        self.manager.save_project_plan(plan)
        loaded_plan = self.manager.load_project_plan(str(plan.id))
        
        self.assertIsNotNone(loaded_plan)
        self.assertEqual(loaded_plan.project_title, "Minimal Plan")
        self.assertIsNone(loaded_plan.notes) # Ensure None is handled

    def test_dependencies_serialization(self):
        """Test that UUID dependencies are correctly serialized/deserialized."""
        self.manager.initialize_project_structure()
        
        dep_id1 = str(uuid4())
        dep_id2 = str(uuid4())
        
        subtask = Subtask(title="Subtask with deps", description="...", status=TaskStatus.PENDING, dependencies=[UUID(dep_id1)], details="Details for subtask with deps", testStrategy="Test strategy for subtask with deps")
        task = Task(title="Task with deps", description="...", status=TaskStatus.PENDING, dependencies=[UUID(dep_id1), UUID(dep_id2)], subtasks=[subtask], details="Details for task with deps", testStrategy="Test strategy for task with deps")
        plan = ProjectPlan(project_title="Deps Test", overall_goal="Test deps", tasks=[task])
        
        self.manager.save_project_plan(plan)
        loaded_plan = self.manager.load_project_plan(str(plan.id))
        
        self.assertIsNotNone(loaded_plan)
        loaded_task = loaded_plan.tasks[0]
        loaded_subtask = loaded_task.subtasks[0]
        
        self.assertListEqual(loaded_task.dependencies, [UUID(dep_id1), UUID(dep_id2)])
        self.assertListEqual(loaded_subtask.dependencies, [UUID(dep_id1)])

if __name__ == '__main__':
    unittest.main()