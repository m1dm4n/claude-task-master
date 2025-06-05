import sys
import os
import pytest
import shutil
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timezone
import asyncio

from typer.testing import CliRunner

from src.data_models import ProjectPlan, Task, TaskStatus, TaskPriority
from src.agent_core.assistant import DevTaskAIAssistant

# Add the project root directory (which contains the 'src' folder) to the Python path
# This allows pytest to find modules in 'src' using 'from src.module import ...'
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Define a custom marker for tests requiring an API key
requires_api_key = pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="Requires GOOGLE_API_KEY environment variable to be set."
)

@pytest.fixture
def runner():
    """Provides a Typer CLI runner for testing."""
    return CliRunner()

class ProjectPlanFactory:
    """Helper for creating and managing project_plan.json files."""
    def __init__(self, workspace_path: Path):
        self._workspace_path = workspace_path

    def create_empty_plan(self) -> Path:
        """Creates an empty project_plan.json file."""
        project_plan = ProjectPlan(
            project_title="Test Project",
            overall_goal="Test project for CLI testing",
            tasks=[]
        )
        return self.create(project_plan)

    def create_with_tasks(self, task_list: List[Dict[str, Any]]) -> Path:
        """Creates project_plan.json with a list of tasks."""
        # Convert task_list (dicts) to Task objects for validation
        tasks = [Task.model_validate(task_data) for task_data in task_list]
        plan_obj = ProjectPlan(
            project_title="Generated Project Plan",
            overall_goal="A project plan generated for testing purposes.",
            tasks=tasks
        )
        return self.create(plan_obj)

    def create(self, project_plan: ProjectPlan) -> Path:
        """Writes a ProjectPlan object to project_plan.json."""
        project_plan_file = self._workspace_path / "project_plan.json"
        with open(project_plan_file, 'w') as f:
            f.write(project_plan.model_dump_json(indent=2))
        return project_plan_file

    def load(self, workspace_path: Path) -> ProjectPlan:
        """Loads project_plan.json from the given workspace path."""
        plan_file = workspace_path / "project_plan.json"
        with open(plan_file, 'r') as f:
            data = json.load(f)
            return ProjectPlan.model_validate(data)

@pytest.fixture
async def cli_test_workspace(tmp_path): # Mark as async fixture
    """
    Creates a temporary workspace for CLI testing and yields the workspace path
    and an initialized DevTaskAIAssistant instance.
    Ensures a clean workspace and proper agent resource cleanup for each test.
    """
    workspace = tmp_path / "test_workspace"
    workspace.mkdir()
    
    # Initialize DevTaskAIAssistant with the workspace
    agent = DevTaskAIAssistant(str(workspace))
    
    # Yield both the workspace path and the agent instance
    yield workspace, agent
    
    # Teardown: Close the agent and clean up the workspace
    await agent.close() # Await the close method directly
    if workspace.exists():
        shutil.rmtree(workspace)

@pytest.fixture
def project_plan_factory(cli_test_workspace: Tuple[Path, DevTaskAIAssistant]):
    """
    Factory fixture returning a helper object for project_plan.json manipulation.
    """
    workspace, _ = cli_test_workspace # Unpack to get only the workspace path
    return ProjectPlanFactory(workspace)

# Helper function for creating task dictionaries (moved from test_utils.py if needed)
# This is already in test_utils.py, so no need to duplicate here unless it's a direct dependency for conftest.
# def create_task_dict(...): ...