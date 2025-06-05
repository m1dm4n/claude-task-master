import tempfile
from pathlib import Path
from typer.testing import CliRunner
from src.cli.main import app
from src.data_models import Task, TaskStatus, TaskPriority, ProjectPlan
from uuid import uuid4
from src.agent_core.main import DevTaskAIAssistant

# Create a temp directory
with tempfile.TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    
    # Create task with subtasks
    subtasks = [
        Task(id=uuid4(), title='Sub1', description='Desc1', status=TaskStatus.PENDING),
    ]
    task = Task(id=uuid4(), title='Test Task', description='Desc', status=TaskStatus.PENDING, subtasks=subtasks)
    plan = ProjectPlan(id=uuid4(), project_title='Test', overall_goal='Goal', tasks=[task])
    
    # Setup agent and save plan
    agent = DevTaskAIAssistant(str(temp_path))
    agent.project_manager.set_project_plan(plan)
    
    # Change to the temp directory to simulate the test environment
    import os
    original_cwd = os.getcwd()
    os.chdir(temp_path)
    
    try:
        # Run CLI
        runner = CliRunner()
        result = runner.invoke(app, ['clear-subtasks', '--task-id', str(task.id)])
        
        print(f'Exit Code: {result.exit_code}')
        print(f'Output: {result.stdout}')
        print(f'Exception: {result.exception}')
        if result.exception:
            import traceback
            traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)
    finally:
        os.chdir(original_cwd)