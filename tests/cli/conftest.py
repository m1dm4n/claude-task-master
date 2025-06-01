import pytest
import os
import shutil
import tempfile
from pathlib import Path
import json

@pytest.fixture(scope="function")
def cli_test_workspace():
    """Create a temporary workspace for CLI tests."""
    temp_dir = tempfile.mkdtemp(prefix="taskmaster_cli_test_")
    original_cwd = Path.cwd()
    
    # Create a dummy .taskmasterconfig file
    # Define what AppConfig expects directly.
    # ConfigManager.load_or_initialize_config will pass this dict to AppConfig.model_validate()
    # AppConfig fields: main_model, research_model, fallback_model,
    #                   project_plan_file, tasks_dir, default_prd_filename
    config_data = {
        "main_model": {
            # Updated to a standard Google model
            "model_name": "gemini-2.0-flash",
            "provider": "google",
            "base_url": None
        },
        # research_model and fallback_model are optional in AppConfig.
        # If we want to test with them, they should be structured similarly.
        # For now, let's omit them to rely on AppConfig's defaults if any, or None.
        "research_model": {
            # Updated to a standard Google model for research
            "model_name": "gemini-2.5-flash-preview-05-20",
            "provider": "google",
            "base_url": None
        },
        "project_plan_file": "test_project_plan.json", # Matches AppConfig field
        "tasks_dir": "tasks",                           # Matches AppConfig field
        "default_prd_filename": "prd.md"                # Matches AppConfig field
        
        # Fields like db_path, project_plans_dir, current_project_id, log_level,
        # llm_providers, default_llm_provider, and the nested 'models' structure
        # are NOT part of AppConfig pydantic model.
        # The PersistenceManager uses its own default for db_path (.tasks/tasks.db).
        # Other settings might be handled by ConfigManager instance vars or other mechanisms.
    }
    config_file_path = Path(temp_dir) / ".taskmasterconfig"
    with open(config_file_path, 'w') as f:
        json.dump(config_data, f, indent=4)
        
    with open(Path(temp_dir) / "prd.md", 'w') as f:
        f.write("# Product Requirements Document\n\nThis is a test PRD file.")
        f.write("\n\n## Requirements\n\n- Create calulator app\n- Support basic arithmetic operations")

    # Create project_plans_dir if it doesn't exist (it should be created by agent if needed)
    # os.makedirs(Path(temp_dir) / "project_plans", exist_ok=True)

    os.chdir(temp_dir)
    yield Path(temp_dir)  # Provide the path to the temporary workspace
    
    os.chdir(original_cwd)
    try:
        shutil.rmtree(temp_dir)
    except OSError as e:
        print(f"Error removing temporary directory {temp_dir}: {e}")