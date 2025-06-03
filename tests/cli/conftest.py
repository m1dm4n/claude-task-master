import pytest
import tempfile
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from src.data_models import ProjectPlan, Task, TaskStatus, TaskPriority


@pytest.fixture
def cli_test_workspace():
    """
    Creates a temporary workspace directory for CLI tests and sets up
    a production-ready configuration for functional testing with real LLM services.
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

        # Set the current working directory to the temporary one
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            yield tmp_path
        finally:
            # Restore original working directory
            os.chdir(original_cwd)


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


def setup_project_plan_file(workspace_path: Path, project_plan: ProjectPlan):
    """
    Helper function to set up a project plan JSON file in the workspace.
    """
    plan_file = workspace_path / "project_plan.json"
    with open(plan_file, 'w') as f:
        f.write(project_plan.model_dump_json(indent=2, exclude_none=True))
    return plan_file


def load_project_plan_file(workspace_path: Path) -> ProjectPlan:
    """
    Helper function to load a project plan from the workspace.
    """
    plan_file = workspace_path / "project_plan.json"
    if plan_file.exists():
        with open(plan_file, 'r') as f:
            data = json.load(f)
            return ProjectPlan.model_validate(data)
    return None