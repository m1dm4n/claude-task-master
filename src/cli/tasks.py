"""Task management commands for the DevTask AI Assistant CLI."""

import typer
from typing_extensions import Annotated
from typing import Optional, List
from uuid import UUID

from ..data_models import TaskStatus, Task
from .utils import get_agent


def create_task_commands(app: typer.Typer):
    """Add task-related commands to the main app."""
    
    @app.command("list")
    def list_tasks(
        ctx: typer.Context,
        status: Annotated[Optional[TaskStatus], typer.Option(help="Filter tasks by status.", case_sensitive=False)] = None,
        with_subtasks: Annotated[bool, typer.Option("--with-subtasks", "-s", help="Include subtasks in the list.")] = False,
    ):
        """
        List all tasks, optionally filtering by status and including subtasks.
        """
        try:
            agent = get_agent(ctx)
            
            if status:
                tasks = agent.get_tasks_by_status(status)
                typer.echo(f"📋 Tasks with status '{status.value}' for '{agent.get_current_project_plan().project_title if agent.get_current_project_plan() else 'No Project'}':")
            else:
                tasks = agent.get_all_tasks()
                typer.echo(f"📋 All Tasks for '{agent.get_current_project_plan().project_title if agent.get_current_project_plan() else 'No Project'}':")

            if not tasks:
                typer.echo("📝 No tasks found matching the criteria.")
                typer.echo("💡 Use 'task-master parse-prd' or 'task-master plan' to get started.")
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
                
                typer.secho(f"\n{status_emoji} {task.title}", fg=typer.colors.CYAN, bold=True)
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
                        typer.secho(f"     {sub_status_emoji} {subtask.title}", fg=typer.colors.BLUE)
                        typer.echo(f"       ID: {subtask.id}")
                        typer.echo(f"       Status: {subtask.status.value}")
                        if subtask.priority:
                            typer.echo(f"       Priority: {subtask.priority.value}")
                        typer.echo(f"       Description: {subtask.description}")
            
        except Exception as e:
            typer.secho(f"❌ Error listing tasks: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("show")
    def show_item(
        ctx: typer.Context,
        item_id_str: Annotated[str, typer.Argument(help="The ID (UUID) of the task or subtask to show.")]
    ):
        """
        Show detailed information for a specific task or subtask by its ID.
        """
        try:
            agent = get_agent(ctx)
            
            try:
                item_uuid = UUID(item_id_str)
            except ValueError:
                typer.secho(f"❌ Invalid ID format: '{item_id_str}'. Please provide a valid UUID.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
                
            item = agent.get_item_by_id(item_uuid)
            
            if item:
                typer.echo(f"🔍 Details for Item (ID: {item.id})")
                typer.echo("=" * 50)
                
                typer.secho(f"Title: {item.title}", fg=typer.colors.CYAN, bold=True)
                typer.echo(f"ID: {item.id}")
                typer.echo(f"Description: {item.description}")
                typer.echo(f"Status: {item.status.value}")
                
                if item.priority:
                    typer.echo(f"Priority: {item.priority.value}")
                if item.dependencies:
                    typer.echo(f"Dependencies: {', '.join(str(d) for d in item.dependencies)}")
                if hasattr(item, 'due_date') and item.due_date:
                    typer.echo(f"Due Date: {item.due_date.strftime('%Y-%m-%d')}")
                if hasattr(item, 'details') and item.details:
                    typer.echo(f"Details:\n{item.details}")
                if hasattr(item, 'testStrategy') and item.testStrategy:
                    typer.echo(f"Test Strategy:\n{item.testStrategy}")
                
                if isinstance(item, Task) and item.subtasks:
                    typer.echo("\nSubtasks:")
                    for subtask in item.subtasks:
                        typer.secho(f"  - {subtask.title} (ID: {subtask.id}, Status: {subtask.status.value})", fg=typer.colors.BLUE)
            else:
                typer.secho(f"❌ Item with ID '{item_id_str}' not found.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
                
        except Exception as e:
            typer.secho(f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("set-status")
    def set_status_command(
        ctx: typer.Context,
        item_ids_str: Annotated[str, typer.Option("--id", "-i", help="Comma-separated list of item IDs (UUIDs) to update.")],
        new_status_str: Annotated[str, typer.Option("--status", "-s", help="The new status to set (e.g., PENDING, IN_PROGRESS, COMPLETED, BLOCKED, CANCELLED, DEFERRED).")]
    ):
        """
        Update the status of one or more tasks or subtasks.
        """
        agent = get_agent(ctx)
        
        # 1. Parse item IDs
        item_uuids: List[UUID] = []
        invalid_uuids: List[str] = []
        for id_str in item_ids_str.split(','):
            id_str = id_str.strip()
            if id_str:
                try:
                    item_uuids.append(UUID(id_str))
                except ValueError:
                    invalid_uuids.append(id_str)
        
        if not item_uuids:
            typer.secho("❌ No valid item IDs provided.", fg=typer.colors.RED)
            if invalid_uuids:
                typer.secho(f"   Invalid IDs: {', '.join(invalid_uuids)}", fg=typer.colors.YELLOW)
            raise typer.Exit(code=1)
        
        if invalid_uuids:
            typer.secho(f"⚠️ Warning: The following IDs are invalid and will be skipped: {', '.join(invalid_uuids)}", fg=typer.colors.YELLOW)

        # 2. Parse new status
        try:
            status_enum = TaskStatus(new_status_str.upper())
        except ValueError:
            valid_statuses = ", ".join([s.value for s in TaskStatus])
            typer.secho(f"❌ Invalid status: '{new_status_str}'. Valid statuses are: {valid_statuses}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        typer.echo(f"🔄 Attempting to update status for {len(item_uuids)} items to '{status_enum.value}'...")

        # 3. Call agent to update status
        try:
            results = agent.update_item_status(item_uuids, status_enum)
            
            # 4. Display results
            for item_id, success in results.items():
                if success:
                    typer.secho(f"✅ Successfully updated status for ID {item_id} to {status_enum.value}.", fg=typer.colors.GREEN)
                else:
                    typer.secho(f"❌ Failed to update status for ID {item_id}: Item not found or an error occurred.", fg=typer.colors.RED)
            
            # Determine overall outcome based on initial parsing and agent results
            num_successfully_updated = sum(1 for success in results.values() if success)
            num_agent_processed = len(results) # How many valid UUIDs were sent to agent

            if invalid_uuids: # If there were any syntactically invalid UUIDs from the input
                if num_successfully_updated > 0:
                    typer.secho(f"\n⚠️ {num_successfully_updated} item(s) updated successfully, but some input IDs were invalid. See warnings above.", fg=typer.colors.YELLOW)
                elif num_agent_processed > 0: # Agent was called but all failed
                     typer.secho(f"\n❌ No items were updated successfully by the agent, and some input IDs were invalid. See warnings above.", fg=typer.colors.RED)
                # If num_agent_processed is 0 here, it means only invalid IDs were provided,
                # which is handled by the exit at line 157 ("No valid item IDs provided.")
            else: # No syntactically invalid UUIDs, all went to agent
                if num_successfully_updated == num_agent_processed and num_agent_processed > 0:
                    typer.secho("\n🎉 All requested items updated successfully!", fg=typer.colors.GREEN)
                elif num_successfully_updated > 0 and num_successfully_updated < num_agent_processed:
                    typer.secho("\n⚠️ Some items updated successfully, but others failed. Check messages above.", fg=typer.colors.YELLOW)
                elif num_agent_processed > 0: # All failed agent-side
                    typer.secho("\n❌ No items were updated successfully by the agent.", fg=typer.colors.RED)
                # If num_agent_processed == 0 (e.g. empty --id "" that somehow passed initial filter), this implies no action
                # This case should ideally be caught earlier.

        except Exception as e:
            typer.secho(f"❌ An unexpected error occurred during status update: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)