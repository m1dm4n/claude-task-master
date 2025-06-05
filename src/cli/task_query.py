"""Task query commands for the DevTask AI Assistant CLI."""

import typer
from typing_extensions import Annotated
from typing import Optional
from uuid import UUID
import asyncio

from ..data_models import TaskStatus
from .utils import parse_uuid_or_exit


def create_task_query_commands(app: typer.Typer):
    """Add task query-related commands to the main app."""

    @app.command("list")
    def list_tasks(
        ctx: typer.Context,
        status: Annotated[Optional[TaskStatus], typer.Option(
            help="Filter tasks by status.", case_sensitive=False)] = None,
        with_subtasks: Annotated[bool, typer.Option(
            "--with-subtasks", "-s", help="Include subtasks in the list.")] = False,
    ):
        """
        List all tasks, optionally filtering by status and including subtasks.
        """
        try:
            agent = ctx.obj["agent"]

            if status:
                tasks = agent.get_tasks_by_status(status)
                typer.echo(
                    f"📋 Tasks with status '{status.value}' for '{agent.get_current_project_plan().project_title if agent.get_current_project_plan() else 'No Project'}':")
            else:
                tasks = agent.get_all_tasks()
                typer.echo(
                    f"📋 All Tasks for '{agent.get_current_project_plan().project_title if agent.get_current_project_plan() else 'No Project'}':")

            if not tasks:
                typer.echo("📝 No tasks found matching the criteria.")
                typer.echo(
                    "💡 Use 'task-master parse-prd' or 'task-master plan' to get started.")
                return

            typer.echo("=" * 50)

            for task in tasks:
                status_emoji = {
                    TaskStatus.PENDING: "⏳",
                    TaskStatus.IN_PROGRESS: "🔄",
                    TaskStatus.COMPLETED: "✅",
                    TaskStatus.BLOCKED: "🚫",
                    TaskStatus.CANCELLED: "❌",
                    TaskStatus.DEFERRED: "⏰"
                }.get(task.status, "📝")

                typer.secho(f"\n{status_emoji} {task.title}",
                            fg=typer.colors.CYAN, bold=True)
                typer.echo(f"   ID: {task.id}")
                typer.echo(f"   Status: {task.status.value}")
                if task.priority:
                    typer.echo(f"   Priority: {task.priority.value}")
                typer.echo(f"   Description: {task.description}")

                if with_subtasks and task.subtasks:
                    typer.echo("   Subtasks:")
                    for subtask in task.subtasks:
                        sub_status_emoji = {
                            TaskStatus.PENDING: "⏳",
                            TaskStatus.IN_PROGRESS: "🔄",
                            TaskStatus.COMPLETED: "✅",
                            TaskStatus.BLOCKED: "🚫",
                            TaskStatus.CANCELLED: "❌",
                            TaskStatus.DEFERRED: "⏰"
                        }.get(subtask.status, "📝")
                        typer.secho(
                            f"     {sub_status_emoji} {subtask.title}", fg=typer.colors.BLUE)
                        typer.echo(f"       ID: {subtask.id}")
                        typer.echo(f"       Status: {subtask.status.value}")
                        if subtask.priority:
                            typer.echo(
                                f"       Priority: {subtask.priority.value}")
                        typer.echo(
                            f"       Description: {subtask.description}")

        except Exception as e:
            typer.secho(f"❌ Error listing tasks: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("next-task")
    def next_task_command(
        ctx: typer.Context
    ):
        """
        Display the next actionable PENDING task.
        """
        try:
            agent = ctx.obj["agent"]
            next_task = agent.get_next_task()

            if next_task:
                typer.secho("🎯 Next actionable task:", fg=typer.colors.GREEN, bold=True)
                typer.secho(f"Title: {next_task.title}", fg=typer.colors.CYAN, bold=True)
                typer.echo(f"ID: {next_task.id}")
                typer.echo(f"Description: {next_task.description}")
                typer.echo(f"Status: {next_task.status.value}")
                if next_task.priority:
                    typer.echo(f"Priority: {next_task.priority.value}")
                if next_task.dependencies:
                    typer.echo(f"Dependencies: {', '.join(str(d) for d in next_task.dependencies)}")
            else:
                typer.secho("🤷 No actionable PENDING tasks found. All tasks may be COMPLETED, BLOCKED, or DEFERRED, or no tasks exist.", fg=typer.colors.YELLOW)
                typer.echo("💡 Use 'task-master list --status PENDING' to see all pending tasks.")

        except Exception as e:
            typer.secho(f"❌ Error getting next task: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("show")
    def show_item(
        ctx: typer.Context,
        item_id_str: Annotated[str, typer.Argument(
            help="The ID (UUID) of the task or subtask to show.")]
    ):
        """
        Show detailed information for a specific task or subtask by its ID.
        """
        try:
            agent = ctx.obj["agent"]

            item_uuid = parse_uuid_or_exit(item_id_str, "item ID")

            item = agent.get_item_by_id(item_uuid)
            if item:
                typer.echo(f"🔍 Details for Item (ID: {item.id})")
                typer.echo("=" * 50)

                typer.secho(f"Title: {item.title}",
                            fg=typer.colors.CYAN, bold=True)
                typer.echo(f"ID: {item.id}")
                typer.echo(f"Description: {item.description}")
                typer.echo(f"Status: {item.status.value}")

                if item.priority:
                    typer.echo(f"Priority: {item.priority.value}")
                if item.dependencies:
                    typer.echo(
                        f"Dependencies: {', '.join(str(d) for d in item.dependencies)}")
                if hasattr(item, 'due_date') and item.due_date:
                    typer.echo(
                        f"Due Date: {item.due_date.strftime('%Y-%m-%d')}")
                if hasattr(item, 'details') and item.details:
                    typer.echo(f"Details:\n{item.details}")
                if hasattr(item, 'testStrategy') and item.testStrategy:
                    typer.echo(f"Test Strategy:\n{item.testStrategy}")

                if item.subtasks:
                    typer.echo("\nSubtasks:")
                    for subtask in item.subtasks:
                        typer.secho(
                            f"  - {subtask.title} (ID: {subtask.id}, Status: {subtask.status.value})", fg=typer.colors.BLUE)
            else:
                typer.secho(
                    f"❌ Item with ID '{item_id_str}' not found.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        except Exception as e:
            typer.secho(
                f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)