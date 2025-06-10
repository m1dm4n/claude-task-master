"""Task query commands for the DevTask AI Assistant CLI."""
import typer
from typing_extensions import Annotated
from typing import Optional
from uuid import UUID
from ..utils.async_utils import run_async_tasks_sync

from ..data_models import TaskStatus
from .utils import parse_uuid_or_exit


def create_task_query_commands(app: typer.Typer):
    """Add task query-related commands to the main app."""

    @app.command("list")
    def list_tasks( # Reverted to synchronous def
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
                agent = ctx.obj["agent"]
    
                tasks = run_async_tasks_sync(agent.get_tasks_by_status(status))
                project_plan = run_async_tasks_sync(agent.get_current_project_plan())
                project_title = project_plan.project_title if project_plan else 'No Project'
                typer.echo(f"📋 Tasks with status '{status.value}' for '{project_title}':")
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

                    # Remove subtasks
                    # if with_subtasks and task.subtasks:
                    #     typer.echo("   Subtasks:")
                    #     for subtask in task.subtasks:
                    #         sub_status_emoji = {
                    #             TaskStatus.PENDING: "⏳",
                    #             TaskStatus.IN_PROGRESS: "🔄",
                    #             TaskStatus.COMPLETED: "✅",
                    #             TaskStatus.BLOCKED: "🚫",
                    #             TaskStatus.CANCELLED: "❌",
                    #             TaskStatus.DEFERRED: "⏰"
                    #         }.get(subtask.status, "📝")
                    #         typer.secho(
                    #             f"     {sub_status_emoji} {subtask.title}", fg=typer.colors.BLUE)
                    #         typer.echo(f"       ID: {subtask.id}")
                    #         typer.echo(f"       Status: {subtask.status.value}")
                    #         if subtask.priority:
                    #             typer.echo(
                    #                 f"       Priority: {subtask.priority.value}")
                    #         typer.echo(
                    #             f"       Description: {subtask.description}")
            else:
                tasks = run_async_tasks_sync(agent.get_all_tasks())
                if tasks is None:
                    tasks = []
                project_plan = run_async_tasks_sync(agent.get_current_project_plan())
                project_title = project_plan.project_title if project_plan else 'No Project'
                typer.echo(
                    f"📋 All Tasks for '{project_title}':")
                if not tasks:
                    typer.echo(
                        "💡 Use 'task-master parse-prd' or 'task-master plan' to get started.")
                    typer.echo("=" * 50)
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

                    # Remove subtasks
                    # if with_subtasks and task.subtasks:
                    #     typer.echo("   Subtasks:")
                    #     for subtask in task.subtasks:
                    #         sub_status_emoji = {
                    #             TaskStatus.PENDING: "⏳",
                    #             TaskStatus.IN_PROGRESS: "🔄",
                    #             TaskStatus.COMPLETED: "✅",
                    #             TaskStatus.BLOCKED: "🚫",
                    #             TaskStatus.CANCELLED: "❌",
                    #             TaskStatus.DEFERRED: "⏰"
                    #         }.get(subtask.status, "📝")
                    #         typer.secho(
                    #             f"     {sub_status_emoji} {subtask.title}", fg=typer.colors.BLUE)
                    #         typer.echo(f"       ID: {subtask.id}")
                    #         typer.echo(f"       Status: {subtask.status.value}")
                    #         if subtask.priority:
                    #             typer.echo(
                    #                 f"       Priority: {subtask.priority.value}")
                    #         typer.echo(
                    #             f"       Description: {subtask.description}")

        except Exception as e:
            typer.secho(f"❌ Error listing tasks: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("next-task")
    def next_task_command( # Reverted to synchronous def
        ctx: typer.Context
    ):
        """
        Display the next actionable PENDING task.
        """
        try:
            agent = ctx.obj["agent"]
            next_task = run_async_tasks_sync(agent.task_service.get_next_actionable_task())

            if next_task:
                typer.secho("\n🚀 Next Actionable Task:",
                            fg=typer.colors.GREEN, bold=True)
                typer.echo("=" * 50)
                typer.secho(f"✨ {next_task.title}",
                            fg=typer.colors.CYAN, bold=True)
                typer.echo(f"   ID: {next_task.id}")
                typer.echo(f"   Status: {next_task.status.value}")
                if next_task.priority:
                    typer.echo(f"   Priority: {next_task.priority.value}")
                typer.echo(f"   Description: {next_task.description}")
                # Remove dependencies
                # if next_task.dependencies:
                #     typer.echo(
                #         f"   Dependencies: {', '.join([str(d) for d in next_task.dependencies])}")
                # Remove subtasks
                # if next_task.subtasks:
                #     typer.echo(
                #         f"   Subtasks: {len(next_task.subtasks)} present")
                typer.echo("=" * 50)
                typer.echo(
                    "\n💡 Use 'task-master set-status --id <ID> --status COMPLETED' when done.")
            else:
                typer.secho(
                    "\n🎉 No actionable tasks found. All tasks might be completed, blocked, or deferred.", fg=typer.colors.GREEN)
                typer.echo(
                    "💡 Use 'task-master list --status BLOCKED' to check for blocked tasks or 'task-master validate-dependencies' to check for dependency issues.")
                typer.echo(
                    "💡 Or, use 'task-master plan' or 'task-master parse-prd' to create new tasks.")
                raise typer.Exit(code=2) # Exit with code 2 to indicate no actionable tasks found, not an error

        except Exception as e:
            typer.secho(f"❌ Error getting next task: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("show")
    def show_item( # Reverted to synchronous def
        ctx: typer.Context,
        item_id_str: Annotated[str, typer.Argument(help="ID of the task or subtask to show.")]
    ):
        """
        Display detailed information about a specific task or subtask.
        """
        try:
            agent = ctx.obj["agent"]
            item_uuid = parse_uuid_or_exit(item_id_str, "item ID")

            typer.echo(f"🔍 Fetching details for item ID: {item_id_str}...")

            item = run_async_tasks_sync(agent.get_task_by_id(item_uuid))

            if item:
                typer.secho(f"\n🔍 Details for Item (ID: {item.id})",
                            fg=typer.colors.GREEN, bold=True)
                typer.echo("=" * 50)
                typer.secho(f"✨ Title: {item.title}",
                            fg=typer.colors.CYAN, bold=True)
                typer.echo(f"   Description: {item.description}")
                typer.echo(f"   Status: {item.status.value}")
                if item.priority:
                    typer.echo(f"   Priority: {item.priority.value}")
                if item.parent:
                    typer.echo(f"   Parent IDs: {', '.join([str(p) for p in item.parent])}")
                if item.children:
                    typer.echo(f"   Children IDs: {', '.join([str(c) for c in item.children])}")
                if item.implementation_notes:
                     typer.echo(f"   Implementation Notes:\n{item.implementation_notes}")
                if item.test_strategy:
                    typer.echo(f"   Test Strategy:\n{item.test_strategy}")
                typer.echo(f"   Created At: {item.created_at}")
                if item.due_date:
                    typer.echo(f"   Due Date: {item.due_date}")
                typer.echo("=" * 50)
            else:
                typer.secho(
                    f"❌ Item with ID '{item_id_str}' not found.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        except ValueError as ve:
            typer.secho(f"❌ Error: {ve}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        except Exception as e:
            typer.secho(f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)