"""
Unit tests for Phase 2 CLI functionality.
Tests the new plan and parse-prd commands.
"""

import pytest
from typer.testing import CliRunner
# Mock removed as we are doing functional tests
from unittest.mock import patch, AsyncMock
from pathlib import Path
import tempfile
import os
import json  # Added for loading project plan JSON

from src.cli import app
from src.data_models import ProjectPlan, Task, TaskStatus  # Task is used in one test
from src.config_manager import ConfigManager  # To get default filename


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


class TestPlanCommand:
    """Test cases for the plan command."""

    def test_plan_command_basic_usage(self, runner, cli_test_workspace):
        """Test basic usage of the plan command."""
        # Act
        result = runner.invoke(
            app, ['plan', 'Build a functional web application with user authentication'])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "✨ Generating project plan for: 'Build a functional web application with user authentication'..." in result.stdout
        assert "✅ Project plan" in result.stdout
        assert "generated and saved!" in result.stdout
        assert "📋 Plan Summary:" in result.stdout
        # Check for presence, not specific LLM content
        assert "Overall Goal:" in result.stdout
        assert "Total Tasks:" in result.stdout

        plan_file = cli_test_workspace / "test_project_plan.json"  # From fixture config
        assert plan_file.exists(
        ), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        with open(plan_file, "r") as f:
            plan_data = json.load(f)
        # Assertions that were previously inside the 'with' block, now correctly outside or re-evaluated
        assert "project_title" in plan_data
        # Project title can be dynamic from LLM, check for presence.
        # The fixture config "test_project_plan.json" doesn't enforce the title in the content,
        # so we check if it's not None. The CLI output assertion for title is separate.
        assert plan_data["project_title"] is not None
        assert "overall_goal" in plan_data
        assert "tasks" in plan_data
        assert isinstance(plan_data["tasks"], list)

    def test_plan_command_with_title_option(self, runner, cli_test_workspace):
        """Test plan command with --title option."""
        custom_title = "My Custom E-commerce Site"
        # Act
        result = runner.invoke(app, [
            'plan', 'Create an e-commerce platform',
            '--title', custom_title
        ])

        # Assert
        assert result.exit_code == 0, result.stdout
        # Make stdout assertion more flexible for functional LLM tests
        assert "✅ Project plan" in result.stdout
        assert "generated and saved!" in result.stdout
        # The important check for title is in the saved file content below

        plan_file = cli_test_workspace / "test_project_plan.json"  # From fixture config
        assert plan_file.exists(
        ), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        with open(plan_file, "r") as f:
            plan_data = json.load(f)
        # Check if the custom title is in the saved plan
        assert plan_data["project_title"] == custom_title

    def test_plan_command_with_num_tasks_option(self, runner, cli_test_workspace):
        """Test plan command with --num-tasks option."""
        # Act
        result = runner.invoke(app, [
            'plan', 'Develop a mobile game',
            '--num-tasks', '5'
        ])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "(Focusing on approximately 5 main tasks)" in result.stdout
        assert "✅ Project plan" in result.stdout  # Check for success message

        plan_file = cli_test_workspace / "test_project_plan.json"  # From fixture config
        assert plan_file.exists(
        ), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        with open(plan_file, "r") as f:
            plan_data = json.load(f)
        assert "tasks" in plan_data
        # Asserting exact number of tasks can be brittle with LLMs
        # For now, just check the message and file creation.
        # If an API key for a deterministic mock LLM is available, more specific checks are possible.

    def test_plan_command_with_research_option(self, runner, cli_test_workspace):
        """Test plan command with --research option."""
        # Act
        result = runner.invoke(app, [
            'plan', 'Research quantum computing applications',
            '--research'
        ])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "(Using research model for enhanced planning)" in result.stdout
        assert "✅ Project plan" in result.stdout  # Check for success message
        plan_file = cli_test_workspace / "test_project_plan.json"
        assert plan_file.exists()

    def test_plan_command_with_all_options(self, runner, cli_test_workspace):
        """Test plan command with all options combined."""
        custom_title = "AI Powered Recipe App"
        # Act
        result = runner.invoke(app, [
            'plan', 'Create an AI powered recipe suggestion app',
            '--title', custom_title,
            '--num-tasks', '8',
            '--research'
        ])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "(Focusing on approximately 8 main tasks)" in result.stdout
        assert "(Using research model for enhanced planning)" in result.stdout
        # More flexible check
        assert "✅ Project plan" in result.stdout and "generated and saved!" in result.stdout
        plan_file = cli_test_workspace / "test_project_plan.json"  # From fixture config
        assert plan_file.exists(
        ), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        with open(plan_file, "r") as f:
            plan_data = json.load(f)
        assert plan_data["project_title"] == custom_title

    def test_plan_command_shows_task_summary(self, runner, cli_test_workspace):
        """Test that plan command shows task summary correctly."""
        # Act
        result = runner.invoke(app, ['plan', 'Plan a holiday trip to Mars'])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "📋 Plan Summary:" in result.stdout
        assert "Overall Goal:" in result.stdout
        assert "Total Tasks:" in result.stdout
        # Check if at least one task line is printed (content will vary)
        # Example: checking for "TaskStatus.PENDING" or a similar structural element
        # Adapting for LLM output
        assert "TaskStatus.PENDING" in result.stdout or "TaskStatus.IN_PROGRESS" in result.stdout
        assert "💡 Use 'task-master list' to view the full plan." in result.stdout

    def test_plan_command_limits_task_display(self, runner, cli_test_workspace):
        """Test that plan command limits task display to first 3 tasks if more are generated."""
        # This test is harder to make deterministic with a live LLM.
        # We rely on the CLI output format if more than 3 tasks are present.
        # For this functional test, we'll invoke it and check for structural elements.
        # To truly test the limiting logic, one might need to pre-populate a plan
        # with many tasks and then 'list' it, or have a mock LLM return many tasks.
        # For now, we assume the 'plan' command output formatting is consistent.

        # Act
        # Use a goal that is likely to generate more than 3 tasks
        result = runner.invoke(
            app, ['plan', 'Develop a comprehensive operating system from scratch', '--num-tasks', '10'])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "Total Tasks:" in result.stdout

        plan_file = cli_test_workspace / "test_project_plan.json"  # From fixture config
        assert plan_file.exists(
        ), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        with open(plan_file, "r") as f:
            plan_data = json.load(f)

        num_tasks_generated = len(plan_data.get("tasks", []))

        # Check for specific task lines - content will vary
        if num_tasks_generated > 0:
            assert f"- {plan_data['tasks'][0]['title']}" in result.stdout
        if num_tasks_generated > 1:
            assert f"- {plan_data['tasks'][1]['title']}" in result.stdout
        if num_tasks_generated > 2:
            assert f"- {plan_data['tasks'][2]['title']}" in result.stdout

        if num_tasks_generated > 3:
            assert "..." in result.stdout
            # Ensure not all tasks are printed if more than 3
            # check if there's a 4th task
            if num_tasks_generated > 3 and len(plan_data['tasks']) > 3:
                assert f"- {plan_data['tasks'][3]['title']}" not in result.stdout
        else:
            # If 3 or fewer tasks, "..." should not be present
            assert "..." not in result.stdout

    def test_plan_command_handles_agent_exception(self, runner, cli_test_workspace):
        """Test that plan command handles exceptions from agent gracefully."""
        # To make this a functional test for exceptions, we'd need to reliably cause one.
        # E.g., misconfigure API key, or if the agent had specific input validation.
        # For now, we'll test a general CLI error if the agent part fails.
        # Patching 'asyncio.run' to raise an exception when agent.plan_project is called.
        with patch('asyncio.run', side_effect=Exception("Simulated agent error during plan")):
            # Act
            result = runner.invoke(app, ['plan', 'Induce an error'])

            # Assert
            assert result.exit_code == 1, result.stdout
            assert "❌ Error generating project plan: Simulated agent error during plan" in result.stdout


class TestParsePrdCommand:
    """Test cases for the parse-prd command."""

    def test_parse_prd_command_basic_usage(self, runner, cli_test_workspace):
        """Test basic usage of the parse-prd command."""
        prd_content = "# Product Requirements\nFeature: User Login\nGoal: Allow users to sign in."
        prd_file = cli_test_workspace / "test_prd.md"
        prd_file.write_text(prd_content)

        # Act
        result = runner.invoke(app, ['parse-prd', str(prd_file)])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert f"📄 Attempting to parse PRD file: '{prd_file.name}'..." in result.stdout
        assert "✅ Project plan" in result.stdout
        assert "generated from PRD and saved!" in result.stdout
        assert "Total Tasks:" in result.stdout

        plan_file = cli_test_workspace / "test_project_plan.json"  # From fixture config
        assert plan_file.exists(
        ), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        with open(plan_file, "r") as f:
            plan_data = json.load(f)
        assert "project_title" in plan_data
        # For PRD parsing, the title might be derived or default, so check for presence
        assert plan_data["project_title"] is not None
        assert "overall_goal" in plan_data
        assert "tasks" in plan_data

    def test_parse_prd_command_with_title_option(self, runner, cli_test_workspace):
        """Test parse-prd command with --title option."""
        prd_content = "Feature: Admin Dashboard"
        prd_file = cli_test_workspace / "admin_prd.md"
        prd_file.write_text(prd_content)
        custom_title = "Admin Portal Plan"

        # Act
        result = runner.invoke(app, [
            'parse-prd', str(prd_file),
            '--title', custom_title
        ])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert f"✅ Project plan '{custom_title}' generated from PRD and saved!" in result.stdout
        plan_file = cli_test_workspace / "test_project_plan.json"  # From fixture config
        assert plan_file.exists(
        ), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        with open(plan_file, "r") as f:
            plan_data = json.load(f)
        assert plan_data["project_title"] == custom_title

    def test_parse_prd_command_with_num_tasks_option(self, runner, cli_test_workspace):
        """Test parse-prd command with --num-tasks option."""
        prd_content = "User Story: As a user, I want to reset my password."
        prd_file = cli_test_workspace / "password_reset.md"
        prd_file.write_text(prd_content)

        # Act
        result = runner.invoke(app, [
            'parse-prd', str(prd_file),
            '--num-tasks', '7'
        ])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "(Focusing on approximately 7 main tasks)" in result.stdout
        assert "✅ Project plan" in result.stdout

        plan_file = cli_test_workspace / "test_project_plan.json"  # From fixture config
        assert plan_file.exists(
        ), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        # This test primarily checks CLI output messages, not detailed plan content.

    def test_parse_prd_command_with_research_option(self, runner, cli_test_workspace):
        """Test parse-prd command with --research option."""
        prd_content = "Research spike: Explore new payment gateway integrations."
        prd_file = cli_test_workspace / "research_prd.md"
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

        plan_file = cli_test_workspace / "test_project_plan.json"  # From fixture config
        assert plan_file.exists(
        ), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        # This test primarily checks CLI output messages, not detailed plan content for num_tasks.

    def test_parse_prd_command_with_all_options(self, runner, cli_test_workspace):
        """Test parse-prd command with all options combined."""
        prd_content = "Full project spec for social media app."
        prd_file = cli_test_workspace / "social_app.md"
        prd_file.write_text(prd_content)
        custom_title = "Social App MVP"

        # Act
        result = runner.invoke(app, [
            'parse-prd', str(prd_file),
            '--title', custom_title,
            '--num-tasks', '6',
            '--research'
        ])

        # TODO: Missing logic for checking if test passes with all options
        assert result.exit_code == 0, result.stdout
        assert "(Focusing on approximately 6 main tasks)" in result.stdout
        assert "(Using research model for enhanced parsing)" in result.stdout
        assert f"✅ Project plan '{custom_title}' generated from PRD and saved!" in result.stdout

        # Use filename from fixture's config
        plan_file = cli_test_workspace / "test_project_plan.json"
        assert plan_file.exists(
        ), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
        with open(plan_file, "r") as f:
            plan_data = json.load(f)
            # project_title from LLM might not exactly match custom_title if LLM refines/changes it.
            # For functional tests, checking for presence or a substring might be more robust
            # or if the exact title from CLI option MUST be preserved, that's a stricter requirement.
            # For now, let's assume the custom_title should be preserved if provided.
            assert plan_data["project_title"] == custom_title

    # mock_agent removed
    def test_parse_prd_command_with_nonexistent_file(self, runner, cli_test_workspace):
        """Test parse-prd command with non-existent file."""
        nonexistent_file = cli_test_workspace / \
            'nonexistent.md'  # Use path within workspace

        # Act
        result = runner.invoke(
            app, ['parse-prd', str(nonexistent_file)])  # No patch needed

        # Assert
        assert result.exit_code != 0  # Typer file validation error (often 2)
        assert "Invalid value for 'PRD_FILE'" in result.stderr or "does not exist" in result.stderr  # Check stderr

    # mock_agent removed
    def test_parse_prd_command_handles_file_not_found_exception(self, runner, cli_test_workspace):
        """Test parse-prd command handles FileNotFoundError from agent gracefully."""
        # This test becomes tricky for functional if Typer catches it first.
        # However, if agent.plan_project_from_prd_file itself raises FileNotFoundError
        # after Typer validates existence (e.g., file deleted between validation and read by agent).
        prd_file = cli_test_workspace / "existing_then_gone.md"
        prd_file.write_text("content")

        # To simulate agent raising FileNotFoundError *after* Typer's check,
        # we would need to patch agent.plan_project_from_prd_file.
        # For a pure functional test, this specific scenario is hard to trigger.
        # Let's assume for now Typer's 'exists=True' check covers most FileNotFoundError.
        # If agent has internal logic that re-checks path and could raise, then patching would be needed.
        # For now, this test might be redundant with test_parse_prd_command_with_nonexistent_file
        # if Typer's validation is the primary gate.

        # Let's adapt it to test the agent's own error message if it somehow gets past Typer's check
        # and then fails to find the file internally (less common with Path type hint).
        # For this, we'll patch the agent's method directly.
        with patch('src.agent_core.main.DevTaskAIAssistant.plan_project_from_prd_file',
                   new_callable=AsyncMock,
                   side_effect=FileNotFoundError("Agent could not find: " + str(prd_file))):
            result = runner.invoke(app, ['parse-prd', str(prd_file)])
            assert result.exit_code == 1, result.stdout
            assert f"❌ Error: Agent could not find: {str(prd_file)}" in result.stdout

    def test_parse_prd_command_handles_agent_exception(self, runner, cli_test_workspace):
        """Test parse-prd command handles exceptions from agent gracefully."""
        prd_file = cli_test_workspace / "error_prd.md"
        prd_file.write_text("Data to cause error")

        with patch('src.agent_core.main.DevTaskAIAssistant.plan_project_from_prd_file',
                   new_callable=AsyncMock,
                   side_effect=Exception("Simulated agent error during parse")):
            # Act
            result = runner.invoke(app, ['parse-prd', str(prd_file)])

            # Assert
            assert result.exit_code == 1, result.stdout
            assert "❌ Error parsing PRD and generating plan: Simulated agent error during parse" in result.stdout

    def test_parse_prd_command_shows_task_summary(self, runner, cli_test_workspace):
        """Test that parse-prd command shows task summary correctly."""
        prd_content = "authentication login for web api."
        prd_file = cli_test_workspace / "summary_prd.md"
        prd_file.write_text(prd_content)

        # Act
        result = runner.invoke(app, ['parse-prd', str(prd_file)])

        # Assert
        assert result.exit_code == 0, result.stdout
        assert "📋 Plan Summary:" in result.stdout
        assert "Overall Goal:" in result.stdout
        assert "Total Tasks:" in result.stdout
        # General check for task status
        assert "TaskStatus.PENDING" in result.stdout or "TaskStatus.IN_PROGRESS" in result.stdout
        assert "💡 Use 'task-master list' to view the full plan." in result.stdout

        # Check that the plan file was created
        plan_file = cli_test_workspace / "test_project_plan.json"  # From fixture config
        assert plan_file.exists(
        ), f"Expected plan file {plan_file} not found. Output: {result.stdout}"
