"""
Production functional tests for Phase 2 CLI functionality.
Tests the new plan and parse-prd commands with real LLM services.
"""

import pytest
from typer.testing import CliRunner
from pathlib import Path
import json
import os

from src.cli import app
from src.data_models import ProjectPlan, Task, TaskStatus
from tests.cli.utils import requires_api_key

@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


class TestPlanCommand:
    """Test cases for the plan command."""

    @requires_api_key()
    def test_plan_command_basic_usage(self, runner, cli_test_workspace):
        """Test basic usage of the plan command with real LLM service."""
        # Act
        result = runner.invoke(
            app, ['plan', 'Build a simple calculator app'])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "✨ Generating project plan for: 'Build a simple calculator app'..." in result.stdout
        assert "✅ Project plan" in result.stdout
        assert "generated and saved!" in result.stdout
        assert "📋 Plan Summary:" in result.stdout
        assert "Overall Goal:" in result.stdout
        assert "Total Tasks:" in result.stdout

        # Verify the project plan file was created and has correct structure
        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists(), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        
        with open(plan_file, "r") as f:
            plan_data = json.load(f)
        
        assert "project_title" in plan_data
        assert plan_data["project_title"] is not None
        assert "overall_goal" in plan_data
        assert 'Build a simple calculator app' in plan_data["overall_goal"]
        assert "tasks" in plan_data
        assert isinstance(plan_data["tasks"], list)
        assert len(plan_data["tasks"]) > 0  # Should have generated some tasks

    @requires_api_key()
    def test_plan_command_with_title_option(self, runner, cli_test_workspace):
        """Test plan command with --title option using real LLM."""
        custom_title = "My Calculator App"
        # Act
        result = runner.invoke(app, [
            'plan', 'Create a calculator',
            '--title', custom_title
        ])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "✅ Project plan" in result.stdout
        assert "generated and saved!" in result.stdout

        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists(), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        
        with open(plan_file, "r") as f:
            plan_data = json.load(f)
        
        # Check if the custom title is in the saved plan
        assert custom_title in plan_data["project_title"]

    @requires_api_key()
    def test_plan_command_with_num_tasks_option(self, runner, cli_test_workspace):
        """Test plan command with --num-tasks option using real LLM."""
        # Act
        result = runner.invoke(app, [
            'plan', 'Build a chatting app',
            '--num-tasks', '3'
        ])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "(Focusing on approximately 3 main tasks)" in result.stdout
        assert "✅ Project plan" in result.stdout

        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists(), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        
        with open(plan_file, "r") as f:
            plan_data = json.load(f)
        
        assert "tasks" in plan_data
        # LLM might generate slightly different number, check it's reasonable
        assert 2 <= len(plan_data["tasks"]) <= 5  # Allow some flexibility

    @requires_api_key()
    def test_plan_command_with_research_option(self, runner, cli_test_workspace):
        """Test plan command with --research option using real LLM."""
        # Act
        result = runner.invoke(app, [
            'plan', 'Create a simple web page',
            '--research'
        ])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "(Using research model for enhanced planning)" in result.stdout
        assert "✅ Project plan" in result.stdout
        
        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists()

    @requires_api_key()
    def test_plan_command_shows_task_summary(self, runner, cli_test_workspace):
        """Test that plan command shows task summary correctly using real LLM."""
        # Act
        result = runner.invoke(app, ['plan', 'Build a simple clock app'])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "📋 Plan Summary:" in result.stdout
        assert "Overall Goal:" in result.stdout
        assert "Total Tasks:" in result.stdout
        assert "TaskStatus.PENDING" in result.stdout
        assert "💡 Use 'task-master list' to view the full plan." in result.stdout

    @requires_api_key()
    def test_plan_command_limits_task_display(self, runner, cli_test_workspace):
        """Test that plan command limits task display to first 3 tasks if more are generated."""
        # Act - Request more tasks to test the display limiting
        result = runner.invoke(
            app, ['plan', 'Build a comprehensive web application', '--num-tasks', '6'])

        # Assert
        assert result.exit_code == 0, result.stdout

        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists(), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        
        with open(plan_file, "r") as f:
            plan_data = json.load(f)

        # Verify tasks were generated
        num_tasks = len(plan_data["tasks"])
        assert num_tasks > 3  # Should have generated more than 3 tasks

        # Check that only first 3 tasks are displayed in output (if more than 3 exist)
        if num_tasks > 3:
            assert f"- {plan_data['tasks'][0]['title']}" in result.stdout
            assert f"- {plan_data['tasks'][1]['title']}" in result.stdout
            assert f"- {plan_data['tasks'][2]['title']}" in result.stdout
            
            # Check that "..." is shown when there are more than 3 tasks
            assert "..." in result.stdout

    def test_plan_command_handles_invalid_input(self, runner, cli_test_workspace):
        """Test that plan command handles invalid input gracefully."""
        # Act - Use an empty goal which should cause an error
        result = runner.invoke(app, ['plan', ''])

        # Assert - Should handle gracefully, either with error or default behavior
        # The exact behavior depends on validation in the CLI
        assert result.exit_code != 0 or "✅ Project plan" in result.stdout


class TestParsePrdCommand:
    """Test cases for the parse-prd command."""

    @requires_api_key()
    def test_parse_prd_command_basic_usage(self, runner, cli_test_workspace):
        """Test basic usage of the parse-prd command with real LLM."""
        prd_content = "# Calculator App\n\nBuild a simple calculator that can perform basic arithmetic operations: addition, subtraction, multiplication, and division."
        prd_file = cli_test_workspace / "calculator_prd.md"
        prd_file.write_text(prd_content)

        # Act
        result = runner.invoke(app, ['parse-prd', str(prd_file)])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert f"📄 Attempting to parse PRD file: '{prd_file.name}'..." in result.stdout
        assert "✅ Project plan" in result.stdout
        assert "generated from PRD and saved!" in result.stdout
        assert "Total Tasks:" in result.stdout

        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists(), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        
        with open(plan_file, "r") as f:
            plan_data = json.load(f)
        
        assert "project_title" in plan_data
        assert plan_data["project_title"] is not None
        assert "overall_goal" in plan_data
        assert "tasks" in plan_data
        assert isinstance(plan_data["tasks"], list)
        assert len(plan_data["tasks"]) > 0  # Should have generated some tasks

    @requires_api_key()
    def test_parse_prd_command_with_title_option(self, runner, cli_test_workspace):
        """Test parse-prd command with --title option using real LLM."""
        prd_content = "# Simple Timer App\nCreate a basic countdown timer application."
        prd_file = cli_test_workspace / "timer_prd.md"
        prd_file.write_text(prd_content)
        custom_title = "Timer Application"

        # Act
        result = runner.invoke(app, [
            'parse-prd', str(prd_file),
            '--title', custom_title
        ])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert f"✅ Project plan '{custom_title}' generated from PRD and saved!" in result.stdout
        
        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists(), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        
        with open(plan_file, "r") as f:
            plan_data = json.load(f)
        assert plan_data["project_title"] == custom_title

    @requires_api_key()
    def test_parse_prd_command_with_num_tasks_option(self, runner, cli_test_workspace):
        """Test parse-prd command with --num-tasks option using real LLM."""
        prd_content = "# Simple Note App\nAs a user, I want to create, edit, and delete notes."
        prd_file = cli_test_workspace / "notes_prd.md"
        prd_file.write_text(prd_content)

        # Act
        result = runner.invoke(app, [
            'parse-prd', str(prd_file),
            '--num-tasks', '4'
        ])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "(Focusing on approximately 4 main tasks)" in result.stdout
        assert "✅ Project plan" in result.stdout

        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists(), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        
        with open(plan_file, "r") as f:
            plan_data = json.load(f)
        # LLM might generate slightly different number, check it's reasonable
        assert 3 <= len(plan_data["tasks"]) <= 6  # Allow some flexibility

    @requires_api_key()
    def test_parse_prd_command_with_research_option(self, runner, cli_test_workspace):
        """Test parse-prd command with --research option using real LLM."""
        prd_content = "# Weather App\nCreate a simple weather application that shows current conditions."
        prd_file = cli_test_workspace / "weather_prd.md"
        prd_file.write_text(prd_content)

        # Act
        result = runner.invoke(app, [
            'parse-prd', str(prd_file),
            '--research'
        ])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "(Using research model for enhanced parsing)" in result.stdout
        assert "✅ Project plan" in result.stdout
        
        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists(), f"Expected plan file {plan_file} not found. Output: {result.stdout}"

    def test_parse_prd_command_with_nonexistent_file(self, runner, cli_test_workspace):
        """Test parse-prd command with non-existent file."""
        nonexistent_file = cli_test_workspace / 'nonexistent.md'

        # Act
        result = runner.invoke(app, ['parse-prd', str(nonexistent_file)])

        # Assert
        assert result.exit_code != 0  # Typer file validation error
        assert "Invalid value for 'PRD_FILE'" in result.stderr or "does not exist" in result.stderr

    @requires_api_key()
    def test_parse_prd_command_shows_task_summary(self, runner, cli_test_workspace):
        """Test that parse-prd command shows task summary correctly using real LLM."""
        prd_content = "# Login System\nImplement user authentication with login and logout functionality."
        prd_file = cli_test_workspace / "login_prd.md"
        prd_file.write_text(prd_content)

        # Act
        result = runner.invoke(app, ['parse-prd', str(prd_file)])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "📋 Plan Summary:" in result.stdout
        assert "Overall Goal:" in result.stdout
        assert "Total Tasks:" in result.stdout
        assert "TaskStatus.PENDING" in result.stdout
        assert "💡 Use 'task-master list' to view the full plan." in result.stdout

        # Check that the plan file was created
        plan_file = cli_test_workspace / "project_plan.json"
        assert plan_file.exists(), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
