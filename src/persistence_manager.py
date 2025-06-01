import json
import os
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import UUID

# Assuming data_models.py is in the same src/ directory
from .data_models import ProjectPlan, Task, Subtask, AppConfig

# --- SQL Table Definitions ---
CREATE_PROJECT_PLANS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS project_plans (
    id TEXT PRIMARY KEY,
    project_title TEXT UNIQUE NOT NULL,
    overall_goal TEXT NOT NULL,
    notes TEXT
);
"""

CREATE_TASKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_plan_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    dependencies TEXT, -- Stored as JSON string
    priority TEXT,
    details TEXT,
    test_strategy TEXT,
    FOREIGN KEY (project_plan_id) REFERENCES project_plans (id) ON DELETE CASCADE
);
"""

CREATE_SUBTASKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    dependencies TEXT, -- Stored as JSON string
    priority TEXT,
    details TEXT,
    test_strategy TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
);
"""


class PersistenceManager:
    """
    Manages saving and loading of ProjectPlan data to/from an SQLite database
    scoped to a specific workspace. Updated for Phase 1 to take workspace_path
    and AppConfig in initialization.
    """
    
    def __init__(self, workspace_path: str, app_config: AppConfig):
        """
        Initializes the PersistenceManager with workspace path and app config.
        
        Args:
            workspace_path: Path to the workspace directory
            app_config: Application configuration containing file paths and settings
        """
        self.workspace_path = Path(workspace_path).resolve()
        self.app_config = app_config
        
        # Derive paths based on workspace and config
        self.project_plan_file_path = self.workspace_path / app_config.project_plan_file
        self.tasks_dir_path = self.workspace_path / app_config.tasks_dir
        self.db_dir_path = self.workspace_path / '.tasks'
        self.db_path = self.workspace_path / '.tasks' / 'tasks.db'
        
    def initialize_project_structure(self) -> None:
        """
        Ensures the workspace directory and required subdirectories exist,
        and initializes the SQLite database with the required schema.
        Creates default ProjectPlan if none exists.
        Idempotent: does not overwrite existing data.
        """
        # Ensure workspace directory exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Ensure database directory exists
        self.db_dir_path.mkdir(parents=True, exist_ok=True)
        
        # Ensure tasks directory exists
        self.tasks_dir_path.mkdir(parents=True, exist_ok=True)
        
        # Ensure .tasks directory exists for SQLite database
        # Ensure .tasks directory exists for SQLite database
        tasks_db_dir = self.workspace_path / '.tasks'
        tasks_db_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize SQLite database
        self._init_database()
        # Create default project plan if none exists
        if not self._has_project_plan():
            default_plan = ProjectPlan(
                project_title="New Project",
                overall_goal="No project goal defined yet.",
                tasks=[]
            )
            self.save_project_plan(default_plan)
    
    def _init_database(self) -> None:
        """Initialize SQLite database with required schema."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")  # Enable FK enforcement
            cursor.execute(CREATE_PROJECT_PLANS_TABLE_SQL)
            cursor.execute(CREATE_TASKS_TABLE_SQL)
            cursor.execute(CREATE_SUBTASKS_TABLE_SQL)
            conn.commit()
            print(f"Database schema ensured at {self.db_path}")
        except sqlite3.Error as e:
            print(f"Error initializing SQLite database at {self.db_path}: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """
        Returns a connection to the SQLite database.
        Ensures database is initialized.
        """
        self._init_database()  # Ensure database exists
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON;")  # Enable foreign key constraints
            return conn
        except sqlite3.Error as e:
            print(f"Error connecting to SQLite database at {self.db_path}: {e}")
            raise
    
    def _has_project_plan(self) -> bool:
        """Check if any project plan exists in the database."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM project_plans")
            count = cursor.fetchone()[0]
            return count > 0
        except sqlite3.Error:
            return False
        finally:
            conn.close()

    def save_project_plan(self, plan: ProjectPlan) -> None:
        """
        Saves the entire ProjectPlan object, including its tasks and subtasks,
        to the SQLite database within the workspace.
        If a project plan with the same ID already exists, it will be replaced.
        
        Args:
            plan: ProjectPlan object to save
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            # Save ProjectPlan: Try to update first, if it doesn't exist, then insert.
            cursor.execute(
                """UPDATE project_plans
                   SET project_title = ?, overall_goal = ?, notes = ?
                   WHERE id = ?""",
                (plan.project_title, plan.overall_goal, plan.notes, str(plan.id))
            )
            if cursor.rowcount == 0:  # No row was updated, so insert new plan
                cursor.execute(
                    """INSERT INTO project_plans
                       (id, project_title, overall_goal, notes)
                       VALUES (?, ?, ?, ?)""",
                    (str(plan.id), plan.project_title, plan.overall_goal, plan.notes)
                )

            # Save Tasks and their Subtasks
            # First, delete existing tasks and subtasks for this plan to handle updates correctly
            cursor.execute("DELETE FROM subtasks WHERE task_id IN (SELECT id FROM tasks WHERE project_plan_id = ?)", (str(plan.id),))
            cursor.execute("DELETE FROM tasks WHERE project_plan_id = ?", (str(plan.id),))

            for task in plan.tasks:
                task_dependencies_json = json.dumps([str(dep_id) for dep_id in task.dependencies])
                cursor.execute(
                    """INSERT INTO tasks 
                       (id, project_plan_id, title, description, status, dependencies, priority, details, test_strategy) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(task.id), str(plan.id), task.title, task.description, task.status,
                     task_dependencies_json, task.priority, task.details, task.testStrategy)
                )
                for subtask in task.subtasks:
                    subtask_dependencies_json = json.dumps([str(dep_id) for dep_id in subtask.dependencies])
                    cursor.execute(
                        """INSERT INTO subtasks 
                           (id, task_id, title, description, status, dependencies, priority, details, test_strategy) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (str(subtask.id), str(task.id), subtask.title, subtask.description, subtask.status,
                         subtask_dependencies_json, subtask.priority, subtask.details, subtask.testStrategy)
                    )
            conn.commit()
            print(f"Project plan '{plan.project_title}' (ID: {plan.id}) and its tasks/subtasks saved to database in workspace {self.workspace_path}")

            # Also save to the JSON file specified in app_config
            try:
                with open(self.project_plan_file_path, 'w', encoding='utf-8') as f:
                    # Use model_dump_json for Pydantic v2
                    f.write(plan.model_dump_json(indent=2, exclude_none=True))
                print(f"Project plan also saved to JSON file: {self.project_plan_file_path}")
            except Exception as e_json:
                print(f"Error saving project plan to JSON file {self.project_plan_file_path}: {e_json}")
                # Optionally, decide if this should be a critical error or just a warning
                # For now, let the original database save be the primary success indicator
        except sqlite3.IntegrityError as e:
            conn.rollback()
            print(f"SQLite integrity error saving project plan to workspace {self.workspace_path}: {e}")
            raise
        except sqlite3.Error as e:
            conn.rollback()
            print(f"SQLite error saving project plan to workspace {self.workspace_path}: {e}")
            raise
        except Exception as e:
            conn.rollback()
            print(f"An unexpected error occurred while saving project plan to workspace {self.workspace_path}: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def load_project_plan(self, project_plan_id: Optional[str] = None) -> Optional[ProjectPlan]:
        """
        Loads a ProjectPlan object, including its tasks and subtasks,
        from the SQLite database. If project_plan_id is None, loads the first/most recent plan.
        
        Args:
            project_plan_id: Optional ID of specific project plan to load
            
        Returns:
            ProjectPlan object or None if not found
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            if project_plan_id:
                cursor.execute(
                    "SELECT id, project_title, overall_goal, notes FROM project_plans WHERE id = ?",
                    (project_plan_id,)
                )
            else:
                # Load the most recent project plan if no ID specified
                cursor.execute(
                    "SELECT id, project_title, overall_goal, notes FROM project_plans ORDER BY rowid DESC LIMIT 1"
                )
            
            plan_row = cursor.fetchone()

            if not plan_row:
                if project_plan_id:
                    print(f"No project plan found with ID '{project_plan_id}' in workspace {self.workspace_path}.")
                else:
                    print(f"No project plans found in workspace {self.workspace_path}.")
                return None

            plan_id_str, fetched_project_title, overall_goal, notes = plan_row

            tasks_list: List[Task] = []
            cursor.execute(
                "SELECT id, title, description, status, dependencies, priority, details, test_strategy FROM tasks WHERE project_plan_id = ?",
                (plan_id_str,)
            )
            for task_row in cursor.fetchall():
                task_id_str, task_title, task_desc, task_status, task_deps_json, task_prio, task_details, task_test_strat = task_row
                # Dependencies are stored as JSON lists of strings (UUIDs)
                task_deps_raw = json.loads(task_deps_json) if task_deps_json else []
                task_dependencies = [dep_id for dep_id in task_deps_raw]

                subtasks_list: List[Subtask] = []
                cursor.execute(
                    "SELECT id, title, description, status, dependencies, priority, details, test_strategy FROM subtasks WHERE task_id = ?",
                    (task_id_str,)
                )
                for subtask_row in cursor.fetchall():
                    subtask_id_str, sub_title, sub_desc, sub_status, sub_deps_json, sub_prio, sub_details, sub_test_strat = subtask_row
                    sub_deps_raw = json.loads(sub_deps_json) if sub_deps_json else []
                    sub_dependencies = [dep_id for dep_id in sub_deps_raw]

                    subtasks_list.append(Subtask(
                        id=UUID(subtask_id_str), title=sub_title, description=sub_desc, status=sub_status,
                        dependencies=sub_dependencies, priority=sub_prio, details=sub_details, testStrategy=sub_test_strat
                    ))
                
                tasks_list.append(Task(
                    id=UUID(task_id_str), title=task_title, description=task_desc, status=task_status,
                    dependencies=task_dependencies, priority=task_prio, details=task_details, testStrategy=task_test_strat,
                    subtasks=subtasks_list
                ))
            
            project_plan = ProjectPlan(
                id=UUID(plan_id_str),
                project_title=fetched_project_title,
                overall_goal=overall_goal,
                notes=notes,
                tasks=tasks_list
            )
            print(f"Project plan '{fetched_project_title}' (ID: {plan_id_str}) loaded successfully from workspace {self.workspace_path}")
            return project_plan

        except sqlite3.Error as e:
            print(f"SQLite error loading project plan from workspace {self.workspace_path}: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON for dependencies from workspace {self.workspace_path}: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred while loading project plan from workspace {self.workspace_path}: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def list_project_plans(self) -> List[Dict[str, Any]]:
        """
        Lists all project plans (id and title) stored in the workspace's database.
        
        Returns:
            List of dicts with project plan info
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        project_plans_info = []
        try:
            cursor.execute("SELECT id, project_title FROM project_plans ORDER BY project_title")
            for row in cursor.fetchall():
                project_plans_info.append({"id": row[0], "project_title": row[1]})
            return project_plans_info
        except sqlite3.Error as e:
            print(f"SQLite error listing project plans from workspace {self.workspace_path}: {e}")
            return []  # Return empty list on error
        finally:
            if conn:
                conn.close()

    def delete_project_plan(self, project_plan_id: str) -> bool:
        """
        Deletes a project plan and its associated tasks and subtasks from the database
        using the project_plan_id. Relies on ON DELETE CASCADE for tasks and subtasks.
        
        Args:
            project_plan_id: ID of project plan to delete
            
        Returns:
            True if deletion was successful, False on error
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            # Check if plan exists before attempting delete
            cursor.execute("SELECT id FROM project_plans WHERE id = ?", (project_plan_id,))
            plan_exists = cursor.fetchone()

            if not plan_exists:
                print(f"Project plan with ID '{project_plan_id}' not found in workspace {self.workspace_path}. Nothing to delete.")
                return True

            cursor.execute("DELETE FROM project_plans WHERE id = ?", (project_plan_id,))
            conn.commit()
            
            # Verify deletion
            cursor.execute("SELECT COUNT(*) FROM project_plans WHERE id = ?", (project_plan_id,))
            if cursor.fetchone()[0] == 0:
                print(f"Project plan with ID '{project_plan_id}' and its associated tasks/subtasks deleted successfully from workspace {self.workspace_path}.")
                return True
            else:
                print(f"Project plan with ID '{project_plan_id}' was not deleted from workspace {self.workspace_path}.")
                conn.rollback()
                return False

        except sqlite3.Error as e:
            conn.rollback()
            print(f"SQLite error deleting project plan ID '{project_plan_id}' from workspace {self.workspace_path}: {e}")
            return False
        finally:
            if conn:
                conn.close()


# Example Usage (for testing purposes)
if __name__ == '__main__':
    import tempfile
    import shutil
    from .data_models import AppConfig, ModelConfig
    
    # Create a dummy workspace for testing
    test_workspace = tempfile.mkdtemp()
    print(f"Using test workspace: {test_workspace}")
    
    try:
        # Create test app config
        test_config = AppConfig(
            main_model=ModelConfig(model_name="test-model", provider="test"),
            project_plan_file="project_plan.json",
            tasks_dir="tasks"
        )
        
        # Initialize PersistenceManager
        manager = PersistenceManager(test_workspace, test_config)
        
        # Initialize the workspace structure
        manager.initialize_project_structure()
        
        # Create a sample ProjectPlan
        sample_subtask1 = Subtask(title="Subtask 1.1", description="Detail for subtask 1.1")
        sample_subtask2 = Subtask(title="Subtask 1.2", description="Detail for subtask 1.2", dependencies=[str(sample_subtask1.id)])
        
        sample_task1 = Task(
            title="Main Task 1", 
            description="Description for main task 1", 
            subtasks=[sample_subtask1, sample_subtask2]
        )
        sample_task2 = Task(title="Main Task 2", description="Description for main task 2", dependencies=[str(sample_task1.id)])
        
        project_plan1 = ProjectPlan(
            project_title="My Test Project Alpha",
            overall_goal="To thoroughly test the SQLite persistence layer.",
            tasks=[sample_task1, sample_task2],
            notes="This is a test plan."
        )
        
        # Save the project plan
        print(f"\n--- Saving Project Plan ({project_plan1.id}) ---")
        manager.save_project_plan(project_plan1)
        
        # Load the project plan
        print(f"\n--- Loading Project Plan ({project_plan1.id}) ---")
        loaded_plan = manager.load_project_plan(str(project_plan1.id))
        if loaded_plan:
            print(f"Successfully loaded: {loaded_plan.project_title}")
            assert loaded_plan.id == project_plan1.id
            assert len(loaded_plan.tasks) == len(project_plan1.tasks)
            print("Basic content of loaded plan matches original.")
        else:
            print(f"Could not load project plan with ID {project_plan1.id}")
        
        # List project plans
        print("\n--- Listing Project Plans ---")
        plans_list = manager.list_project_plans()
        if plans_list:
            for p_info in plans_list:
                print(f"  ID: {p_info['id']}, Title: {p_info['project_title']}")
        else:
            print("  No project plans found.")
        
        print("\n--- Test Run Complete ---")
        
    finally:
        # Clean up test workspace
        shutil.rmtree(test_workspace)
        print("Test workspace cleaned up")