"""Task modification commands for the DevTask AI Assistant CLI."""

import typer
import typer
from typing_extensions import Annotated
from typing import Optional, List
from uuid import UUID

from ..utils.async_utils import run_async_tasks_sync
from ..data_models import TaskStatus
from .utils import parse_uuid_or_exit


def create_task_modification_commands(app: typer.Typer):
    """Add task modification-related commands to the main app."""

    @app.command("set-status")
    def set_status_command( # Reverted to synchronous def
        ctx: typer.Context,
        item_ids_str: Annotated[str, typer.Option("--id", "-i", help="Comma-separated list of item IDs (UUIDs) to update.")],
        new_status_str: Annotated[str, typer.Option(
            "--status", "-s", help="The new status to set (e.g., PENDING, IN_PROGRESS, COMPLETED, BLOCKED, CANCELLED, DEFERRED).")]
    ):
        """
        Update the status of one or more tasks or subtasks.
        """
        agent = ctx.obj["agent"]

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
                typer.secho(
                    f"   Invalid IDs: {', '.join(invalid_uuids)}", fg=typer.colors.YELLOW)
            raise typer.Exit(code=1)

        if invalid_uuids:
            typer.secho(
                f"⚠️ Warning: The following IDs are invalid and will be skipped: {', '.join(invalid_uuids)}", fg=typer.colors.YELLOW)

        try:
            status_enum = TaskStatus(new_status_str.upper())
        except ValueError:
            valid_statuses = ", ".join([s.value for s in TaskStatus])
            typer.secho(
                f"❌ Invalid status: '{new_status_str}'. Valid statuses are: {valid_statuses}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        typer.echo(
            f"🔄 Attempting to update status for {len(item_uuids)} items to '{status_enum.value}'...")

        try:
            results = run_async_tasks_sync(agent.update_item_status(item_uuids, status_enum))

            for item_id, success in results.items():
                if success:
                    typer.secho(
                        f"✅ Successfully updated status for ID {item_id} to {status_enum.value}.", fg=typer.colors.GREEN)
                else:
                    typer.secho(
                        f"❌ Failed to update status for ID {item_id}: Item not found or an error occurred.", fg=typer.colors.RED)

            num_successfully_updated = sum(
                1 for success in results.values() if success)
            num_agent_processed = len(results)

            if invalid_uuids:
                if num_successfully_updated > 0:
                    typer.secho(
                        f"\n⚠️ {num_successfully_updated} item(s) updated successfully, but some input IDs were invalid. See warnings above.", fg=typer.colors.YELLOW)
                elif num_agent_processed > 0:
                    typer.secho(
                        f"\n❌ No items were updated successfully by the agent, and some input IDs were invalid. See warnings above.", fg=typer.colors.RED)
            else:
                if num_successfully_updated == num_agent_processed and num_agent_processed > 0:
                    typer.secho(
                        "\n🎉 All requested items updated successfully!", fg=typer.colors.GREEN)
                elif num_successfully_updated > 0 and num_successfully_updated < num_agent_processed:
                    typer.secho(
                        "\n⚠️ Some items updated successfully, but others failed. Check messages above.", fg=typer.colors.YELLOW)
                elif num_agent_processed > 0:
                    typer.secho(
                        "\n❌ No items were updated successfully by the agent.", fg=typer.colors.RED)

        except Exception as e:
            typer.secho(
                f"❌ An unexpected error occurred during status update: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("update-task")
    def update_task_command( # Reverted to synchronous def
        ctx: typer.Context,
        task_id_str: Annotated[str, typer.Argument(help="ID of the task to update.")],
        refinement_instruction: Annotated[str, typer.Argument(help="Instructions for how to refine the task.")],
        use_research: Annotated[bool, typer.Option(
            "--research", help="Use the research model for refinement.")] = False
    ):
        """
        Update a task using AI-powered refinement.

        The refinement instruction can include requests to modify the title, description, 
        status, priority, details, test strategy, or other task properties.
        """
        try:
            agent = ctx.obj["agent"]

            task_uuid = parse_uuid_or_exit(task_id_str, "task ID")
 
            try:
                item = run_async_tasks_sync(agent.task_service.get_task_by_id(task_uuid))
                if item is None or item.parent:
                    typer.secho(
                        f"❌ Task with ID '{task_id_str}' not found or is a subtask.", fg=typer.colors.RED)
                    raise typer.Exit(code=1)

                typer.echo(
                    f"🔄 Updating task '{item.title}' using {'research' if use_research else 'main'} model...")

                updated_item = run_async_tasks_sync(agent.refine_task_or_subtask(
                    task_uuid, refinement_instruction, use_research=use_research
                ))

                if updated_item:
                    typer.secho(
                        f"✅ Successfully updated task '{updated_item.title}'", fg=typer.colors.GREEN)
                    typer.echo(f"Successfully updated task '{updated_item.title}'")
                else:
                    typer.secho(
                        f"❌ Failed to update task. Please check the logs for details.", fg=typer.colors.RED)
                    raise typer.Exit(code=1)

            except Exception as e:
                typer.secho(
                    f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
                raise typer.Exit(code=1)
        except:
            pass

    @app.command("update-subtask")
    def update_subtask_command( # Reverted to synchronous def
        ctx: typer.Context,
        task_id_str: Annotated[str, typer.Argument(help="ID of the subtask to update.")],
        refinement_instruction: Annotated[str, typer.Argument(help="Instructions for how to refine the subtask.")],
        use_research: Annotated[bool, typer.Option(
            "--research", help="Use the research model for refinement.")] = False
    ):
        """
        Update a subtask using AI-powered refinement.

        The refinement instruction can include requests to modify the title, description, 
        status, priority, details, test strategy, or other task properties.
        """
        try:
            agent = ctx.obj["agent"]

            task_uuid = parse_uuid_or_exit(task_id_str, "task ID")
 
            item = run_async_tasks_sync(agent.task_service.get_task_by_id(task_uuid))
            if item is None or item.parent:
                typer.secho(
                    f"❌ Subtask with ID '{task_id_str}' not found or is a main task. Use `update-task` to update main tasks.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

            typer.echo(
                f"🔄 Updating subtask '{item.title}' using {'research' if use_research else 'main'} model...")

            updated_item = run_async_tasks_sync(agent.refine_task_or_subtask(
                task_uuid, refinement_instruction, use_research=use_research
            ))

            if updated_item:
                typer.secho(
                    f"✅ Successfully updated subtask '{updated_item.title}'", fg=typer.colors.GREEN)
                typer.echo(f"Successfully updated subtask '{updated_item.title}'")
            else:
                typer.secho(
                    f"❌ Failed to update subtask. Please check the logs for details.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        except Exception as e:
            typer.secho(
                f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("move-task")
    def move_task_command( # Reverted to synchronous def
        ctx: typer.Context,
        task_id_str: Annotated[str, typer.Argument(help="ID of the task to move.")],
        new_parent_id_str: Annotated[Optional[str], typer.Option(
            "--new-parent-id", "-p", help="ID of the new parent task. If omitted, moves to top-level.")] = None
    ):
        """
        Move a task or subtask to a new parent task, or make it a top-level task.
        """
        try:
            agent = ctx.obj["agent"]

            task_uuid = parse_uuid_or_exit(task_id_str, "task ID")

            new_parent_uuid: Optional[UUID] = None
            if new_parent_id_str:
                new_parent_uuid = parse_uuid_or_exit(new_parent_id_str, "new parent ID")

            typer.echo(f"🔄 Moving task {task_id_str}...")

            success = run_async_tasks_sync(agent.move_task(task_uuid, new_parent_uuid))

            if success:
                if new_parent_uuid:
                    typer.secho(
                        f"✅ Successfully moved task {task_id_str} under new parent {new_parent_id_str}.", fg=typer.colors.GREEN)
                else:
                    typer.secho(
                        f"✅ Successfully moved task {task_id_str} to top-level.", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(
                f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
