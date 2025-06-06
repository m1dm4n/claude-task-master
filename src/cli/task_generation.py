"""Task generation commands for the DevTask AI Assistant CLI."""

import typer
from typing_extensions import Annotated
from typing import Optional, List
from uuid import UUID
from ..utils.async_utils import run_async_tasks_sync

from ..data_models import TaskStatus
from .utils import parse_uuid_or_exit


def create_task_generation_commands(app: typer.Typer):
    """Add task generation-related commands to the main app."""

    @app.command("expand")
    def expand_command( # Reverted to synchronous def
        ctx: typer.Context,
        task_id_str: Annotated[Optional[str], typer.Option(
            "--task-id", "-id", help="ID of the task to expand.")] = None,
        all_pending: Annotated[bool, typer.Option(
            "--all-pending", "-a", help="Expand all pending tasks.")] = False,
        num_subtasks: Annotated[Optional[int], typer.Option(
            "--num", "-n", help="Target number of subtasks to generate.")] = None,
        use_research: Annotated[bool, typer.Option(
            "--research", help="Use the research model for expansion.")] = False,
        prompt_override: Annotated[Optional[str], typer.Option(
            "--prompt", help="Custom prompt for subtask generation.")] = None
    ):
        """
        Expand tasks by generating subtasks using AI assistance.

        Use either --task-id to expand a specific task or --all-pending to expand all pending tasks.
        """
        try:
            if task_id_str and all_pending:
                typer.secho(
                    "❌ Error: Cannot specify both --task-id and --all-pending.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

            agent = ctx.obj["agent"]

            if all_pending:
                typer.echo("🔄 Expanding all pending tasks...")

                try:
                    count = run_async_tasks_sync(agent.expand_all_pending_tasks(
                        num_subtasks_per_task=num_subtasks,
                        use_research=use_research
                    ))

                    if count > 0:
                        typer.secho(
                            f"✅ Successfully expanded {count} pending tasks with subtasks.", fg=typer.colors.GREEN)
                    else:
                        typer.secho(
                            "📝 No pending tasks were expanded. They may already have subtasks or no pending tasks exist.", fg=typer.colors.YELLOW)
                        typer.echo(
                            "💡 Use --force to regenerate subtasks for tasks that already have them.")

                except Exception as e:
                    typer.secho(
                        f"❌ Error expanding pending tasks: {e}", fg=typer.colors.RED)
                    raise typer.Exit(code=1)

            elif task_id_str:
                task_uuid = parse_uuid_or_exit(task_id_str, "task ID")

                typer.echo(f"🔄 Expanding task {task_id_str}...")

                try:
                    updated_task = run_async_tasks_sync(agent.expand_task_with_subtasks(
                        task_uuid,
                        num_subtasks=num_subtasks,
                        prompt_override=prompt_override,
                        use_research=use_research
                    ))

                    if updated_task:
                        typer.secho(
                            f"✅ Successfully expanded task '{updated_task.title}'", fg=typer.colors.GREEN)
                        typer.echo(
                            f"📋 Task now has {len(updated_task.subtasks)} subtasks:")

                        for i, subtask in enumerate(updated_task.subtasks, 1):
                            typer.secho(
                                f"  {i}. {subtask.title}", fg=typer.colors.BLUE)
                            typer.echo(f"     ID: {subtask.id}")
                            typer.echo(
                                f"     Description: {subtask.description}")
                            if subtask.priority:
                                typer.echo(
                                    f"     Priority: {subtask.priority.value}")
                            typer.echo()
                    else:
                        typer.secho(
                            f"❌ Task with ID '{task_id_str}' not found or could not be expanded.", fg=typer.colors.RED)
                        raise typer.Exit(code=1)

                except Exception as e:
                    typer.secho(
                        f"❌ Error expanding task: {e}", fg=typer.colors.RED)
                    raise typer.Exit(code=1)
            else:
                typer.secho(
                    "❌ Please specify either --task-id <UUID> to expand a specific task or --all-pending to expand all pending tasks.", fg=typer.colors.RED)
                typer.echo("\nExamples:")
                typer.echo(
                    "  task-master expand --task-id 123e4567-e89b-12d3-a456-426614174000")
                typer.echo("  task-master expand --all-pending")
                typer.echo(
                    "  task-master expand --task-id 123e4567-e89b-12d3-a456-426614174000 --num 5 --research")
                raise typer.Exit(code=1)

        except Exception as e:
            typer.secho(
                f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("clear-subtasks")
    def clear_subtasks_command( # Reverted to synchronous def
        ctx: typer.Context,
        task_id_str: Annotated[Optional[str], typer.Option(
            "--task-id", "-id", help="ID of the task whose subtasks to clear.")] = None,
        all_tasks: Annotated[bool, typer.Option(
            "--all", "-a", help="Clear subtasks from all tasks.")] = False
    ):
        """
        Clear subtasks from tasks.

        Use either --task-id to clear subtasks from a specific task or --all to clear subtasks from all tasks.
        """
        try:
            agent = ctx.obj["agent"]

            if all_tasks:
                typer.echo("🔄 Clearing subtasks from all tasks...")

                count = run_async_tasks_sync(agent.clear_subtasks_for_all_tasks())

                if count > 0:
                    typer.secho(
                        f"✅ Cleared subtasks from {count} tasks.", fg=typer.colors.GREEN)
                else:
                    typer.secho(
                        "📝 No tasks with subtasks found to clear.", fg=typer.colors.YELLOW)

            elif task_id_str:
                task_uuid = parse_uuid_or_exit(task_id_str, "task ID")

                typer.echo(f"🔄 Clearing subtasks for task {task_id_str}...")

                success = run_async_tasks_sync(agent.clear_subtasks_for_task(task_uuid))

                if success:
                    typer.secho(
                        f"✅ Subtasks cleared for task ID {task_uuid}.", fg=typer.colors.GREEN)
                else:
                    typer.secho(
                        f"❌ Task not found or no subtasks to clear for task ID {task_uuid}.", fg=typer.colors.RED)
                    raise typer.Exit(code=1)
            else:
                typer.secho(
                    "❌ Please specify either --task-id <UUID> to clear subtasks from a specific task or --all to clear subtasks from all tasks.", fg=typer.colors.RED)
                typer.echo("\nExamples:")
                typer.echo(
                    "  task-master clear-subtasks --task-id 123e4567-e89b-12d3-a456-426614174000")
                typer.echo("  task-master clear-subtasks --all")
                raise typer.Exit(code=1)

        except Exception as e:
            typer.secho(
                f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("add-task")
    def add_task_command( # Reverted to synchronous def
        ctx: typer.Context,
        description: Annotated[str, typer.Argument(help="Description or prompt for the new task.")],
        dependencies: Annotated[Optional[List[str]], typer.Option(
            "--dep", help="Task IDs this new task depends on (can be used multiple times).")] = None,
        priority: Annotated[Optional[str], typer.Option(
            "--priority", help="Priority of the new task (low, medium, high, critical).")] = None,
        parent_id: Annotated[Optional[str], typer.Option(
            "--parent-id", help="ID of the parent task if adding a subtask.")] = None,
        use_research: Annotated[bool, typer.Option(
            "--research", help="Use the research model for task generation.")] = False
    ):
        """
        Add a new task to the project using AI-driven task generation.

        The AI will analyze your description and generate a complete task with title,
        detailed description, implementation notes, and optionally initial subtasks.
        """
        try:
            agent = ctx.obj["agent"]

            if dependencies:
                for dep_id in dependencies:
                    parse_uuid_or_exit(dep_id, "dependency ID")

            if priority:
                valid_priorities = ["low", "medium", "high", "critical"]
                if priority.lower() not in valid_priorities:
                    typer.secho(
                        f"❌ Invalid priority: '{priority}'. Valid priorities are: {', '.join(valid_priorities)}", fg=typer.colors.RED)
                    raise typer.Exit(code=1)

            parent_uuid: Optional[UUID] = None
            if parent_id:
                parent_uuid = parse_uuid_or_exit(parent_id, "parent ID")

            typer.echo("🔄 Generating new task...")

            new_task = run_async_tasks_sync(agent.add_new_task(
                description=description,
                dependencies_str=dependencies,
                priority_str=priority,
                parent_id_str=parent_id,
                use_research=use_research
            ))

            if new_task:
                typer.secho(
                    f"✅ Successfully added new task: {new_task.title} (ID: {new_task.id})", fg=typer.colors.GREEN)
                if new_task.subtasks:
                    typer.echo(
                        f"📋 Generated {len(new_task.subtasks)} initial subtasks:")
                    for i, subtask in enumerate(new_task.subtasks, 1):
                        typer.secho(
                            f"  {i}. {subtask.title} (ID: {subtask.id})", fg=typer.colors.BLUE)
            else:
                typer.secho("❌ Failed to add new task.", fg=typer.colors.RED)
                if parent_id and not new_task:
                    typer.secho(
                        f"❌ Parent task with ID '{parent_uuid}' not found or could not be used.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        except ValueError as ve:
            typer.secho(f"❌ Error: {ve}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        except Exception as e:
            typer.secho(
                f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("remove-subtask")
    def remove_subtask_command( # Reverted to synchronous def
        ctx: typer.Context,
        subtask_id_str: Annotated[str, typer.Argument(
            help="ID of the subtask to remove.")]
    ):  
        """
        Remove a subtask from its parent task.
        """
        try:
            agent = ctx.obj["agent"]

            subtask_uuid = parse_uuid_or_exit(subtask_id_str, "subtask ID")

            typer.echo(f"🔄 Removing subtask {subtask_id_str}...")

            success = run_async_tasks_sync(agent.remove_subtask(subtask_uuid))

            if success:
                typer.secho(
                    f"✅ Successfully removed subtask {subtask_uuid}.", fg=typer.colors.GREEN)
            else:
                typer.secho(
                    f"❌ Failed to remove subtask {subtask_uuid}. Task not found or an error occurred.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        except Exception as e:
            typer.secho(
                f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)