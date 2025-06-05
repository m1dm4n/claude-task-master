import pytest
import tempfile
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import List, Optional, Union, Tuple, Any, AsyncGenerator, Dict
import asyncio
import pytest_asyncio # Added import for pytest_asyncio

from typer.testing import CliRunner

from src.data_models import ProjectPlan, Task, TaskStatus, TaskPriority, AppConfig, ModelConfig
from src.agent_core.assistant import DevTaskAIAssistant
from src.config_manager import ConfigManager

# Mark as async and specify return type
@pytest_asyncio.fixture # Changed to pytest_asyncio.fixture
async def cli_test_workspace() -> AsyncGenerator[tuple[Path, DevTaskAIAssistant], None]:
    """
    Creates a temporary workspace directory for CLI tests and sets up
    a production-ready configuration for functional testing with real LLM services.
    Yields the workspace path and an initialized DevTaskAIAssistant instance.
    Ensures proper agent resource cleanup.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create a production-ready .taskmasterconfig
        # Use actual working model configurations
        config_content = """{
  "main_model": {
    "model_name": "gemini-2.0-flash",
    "provider": "google",
    "api_key": null,
    "base_url": null
  },
  "research_model": {
    "model_name": "gemini-2.0-flash-thinking-exp",
    "provider": "google",
    "api_key": null,
    "base_url": null
  },
  "fallback_model": {
    "model_name": "gemini-2.0-flash",
    "provider": "google",
    "api_key": null,
    "base_url": null
  },
  "project_plan_file": "project_plan.json",
  "tasks_dir": "tasks",
  "default_prd_filename": "prd.md"
}"""
        config_file = tmp_path / ".taskmasterconfig"
        config_file.write_text(config_content)

        # Create tasks directory
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        
        # Initialize DevTaskAIAssistant with the workspace
        # Manually instantiate ConfigManager to ensure it uses the temp workspace
        config_manager = ConfigManager(str(tmp_path))
        agent = DevTaskAIAssistant(str(tmp_path))
        # Ensure the agent's internal config_manager is the one we just created
        agent.config_manager = config_manager

        # Removed os.getcwd() and os.chdir() from here
        try:
            yield tmp_path, agent # Yield both workspace path and agent
        finally:
            # Teardown: Close the agent
            await agent.close() # Await the close method directly
            # Removed os.chdir(original_cwd) as we no longer change CWD globally


@pytest_asyncio.fixture # Changed to pytest_asyncio.fixture
async def real_agent(cli_test_workspace: Tuple[Path, DevTaskAIAssistant]) -> DevTaskAIAssistant:
    """
    Provides an initialized DevTaskAIAssistant instance from the cli_test_workspace fixture.
    """
    _, agent = cli_test_workspace # Unpack to get only the agent
    return agent

class ProjectPlanFactory:
   """
   Helper class to create and manage project_plan.json files for tests.
   """
   def __init__(self, workspace_path: Path):
       self.workspace_path = workspace_path
       self.plan_file_path = self.workspace_path / "project_plan.json"

   def create(self, project_plan: ProjectPlan):
       """Creates a project_plan.json file from a ProjectPlan object."""
       with open(self.plan_file_path, 'w') as f:
           f.write(project_plan.model_dump_json(indent=2, exclude_none=True))

   def create_with_tasks(self, tasks: List[Union[Task, Dict[str, Any]]], project_title: str = "Generated Project Plan", overall_goal: str = "A project generated for testing purposes."):
       """
       Creates a project_plan.json file with a list of tasks.
       Tasks can be Task objects or dictionaries that can be converted to Task objects.
       """
       # Ensure all tasks are Task objects
       task_objects = []
       for task_data in tasks:
           if isinstance(task_data, dict):
               task_objects.append(Task(**task_data))
           elif isinstance(task_data, Task):
               task_objects.append(task_data)
           else:
               raise TypeError(f"Expected task_data to be a dict or Task object, but got {type(task_data)}")

       project_plan = ProjectPlan(
           project_title=project_title,
           overall_goal=overall_goal,
           tasks=task_objects
       )
       self.create(project_plan)

   def load(self) -> Optional[ProjectPlan]:
       """Loads the project plan from the workspace."""
       if not self.plan_file_path.exists():
           return None
       with open(self.plan_file_path, 'r') as f:
           data = json.load(f)
           return ProjectPlan.model_validate(data)

@pytest.fixture
def project_plan_factory(cli_test_workspace: Tuple[Path, DevTaskAIAssistant]) -> ProjectPlanFactory:
   """
   Provides a ProjectPlanFactory instance for the current test workspace.
   """
   workspace_path, _ = cli_test_workspace
   return ProjectPlanFactory(workspace_path)


@pytest.fixture
def sample_project_plan():
   """
   Creates a sample project plan for testing.
   """
   return ProjectPlan(
       project_title="Test Project",
       overall_goal="This is a test project for CLI functional testing.",
       tasks=[
           Task(
               id=uuid4(),
               title="Task 1: Setup",
               description="Set up the project environment",
               status=TaskStatus.PENDING,
               priority=TaskPriority.HIGH,
               created_at=datetime.now(timezone.utc),
               updated_at=datetime.now(timezone.utc)
           ),
           Task(
               id=uuid4(),
               title="Task 2: Development",
               description="Implement core features",
               status=TaskStatus.IN_PROGRESS,
               priority=TaskPriority.MEDIUM,
               created_at=datetime.now(timezone.utc),
               updated_at=datetime.now(timezone.utc)
           ),
           Task(
               id=uuid4(),
               title="Task 3: Testing",
               description="Test the implementation",
               status=TaskStatus.COMPLETED,
               priority=TaskPriority.LOW,
               created_at=datetime.now(timezone.utc),
               updated_at=datetime.now(timezone.utc)
           )
       ]
   )


@pytest.fixture
def runner():
   """Returns a Typer CliRunner instance."""
   return CliRunner()

@pytest_asyncio.fixture(params=["simple_plan.json"])
async def llm_generated_plan_fixture(cli_test_workspace: Tuple[Path, DevTaskAIAssistant], request, project_plan_factory: ProjectPlanFactory):
   """
   Takes a fixture name via request.param and copies the named JSON fixture
   into the cli_test_workspace as project_plan.json.
   """
   workspace_path, _ = cli_test_workspace
   fixture_name = request.param
   # Define the path to the new fixtures directory
   fixtures_dir = Path(__file__).parent.parent / "fixtures" / "cli_e2e_plans"
   source_fixture_path = fixtures_dir / fixture_name
   
   if not source_fixture_path.exists():
       pytest.fail(f"Fixture file not found: {source_fixture_path}")

   # Load content and use project_plan_factory to write it
   with open(source_fixture_path, 'r') as src_f:
       content_data = json.load(src_f)
   
   # Assuming the fixture content is a valid ProjectPlan structure
   project_plan = ProjectPlan.model_validate(content_data)
   project_plan_factory.create(project_plan)
   
   # Yield the path to the copied plan for the test to use
   yield project_plan_factory.plan_file_path