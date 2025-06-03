"""Task management commands for the DevTask AI Assistant CLI."""

import asyncio
import typer
from typing_extensions import Annotated
from typing import Optional, List
from uuid import UUID

from ..data_models import TaskStatus, Task, Subtask
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

    @app.command("expand")
    def expand_command(
        ctx: typer.Context,
        task_id_str: Annotated[Optional[str], typer.Option("--task-id", "-id", help="ID of the task to expand.")] = None,
        all_pending: Annotated[bool, typer.Option("--all-pending", "-a", help="Expand all pending tasks.")] = False,
        num_subtasks: Annotated[Optional[int], typer.Option("--num", "-n", help="Target number of subtasks to generate.")] = None,
        use_research: Annotated[bool, typer.Option("--research", help="Use the research model for expansion.")] = False,
        prompt_override: Annotated[Optional[str], typer.Option("--prompt", help="Custom prompt for subtask generation.")] = None
    ):
        """
        Expand tasks by generating subtasks using AI assistance.
        
        Use either --task-id to expand a specific task or --all-pending to expand all pending tasks.
        """
        try:
            agent = get_agent(ctx)
            
            if all_pending:
                # Expand all pending tasks
                typer.echo("🔄 Expanding all pending tasks...")
                
                try:
                    count = asyncio.run(agent.expand_all_pending_tasks(
                        num_subtasks_per_task=num_subtasks,
                        use_research=use_research
                    ))
                    
                    if count > 0:
                        typer.secho(f"✅ Successfully expanded {count} pending tasks with subtasks.", fg=typer.colors.GREEN)
                    else:
                        typer.secho("📝 No pending tasks were expanded. They may already have subtasks or no pending tasks exist.", fg=typer.colors.YELLOW)
                        typer.echo("💡 Use --force to regenerate subtasks for tasks that already have them.")
                        
                except Exception as e:
                    typer.secho(f"❌ Error expanding pending tasks: {e}", fg=typer.colors.RED)
                    raise typer.Exit(code=1)
                    
            elif task_id_str:
                # Expand specific task
                try:
                    task_uuid = UUID(task_id_str)
                except ValueError:
                    typer.secho(f"❌ Invalid task ID format: '{task_id_str}'. Please provide a valid UUID.", fg=typer.colors.RED)
                    raise typer.Exit(code=1)
                
                typer.echo(f"🔄 Expanding task {task_id_str}...")
                
                try:
                    updated_task = asyncio.run(agent.expand_task_with_subtasks(
                        task_uuid,
                        num_subtasks=num_subtasks,
                        prompt_override=prompt_override,
                        use_research=use_research
                    ))
                    
                    if updated_task:
                        typer.secho(f"✅ Successfully expanded task '{updated_task.title}'", fg=typer.colors.GREEN)
                        typer.echo(f"📋 Task now has {len(updated_task.subtasks)} subtasks:")
                        
                        # Display the subtasks
                        for i, subtask in enumerate(updated_task.subtasks, 1):
                            typer.secho(f"  {i}. {subtask.title}", fg=typer.colors.BLUE)
                            typer.echo(f"     ID: {subtask.id}")
                            typer.echo(f"     Description: {subtask.description}")
                            if subtask.priority:
                                typer.echo(f"     Priority: {subtask.priority.value}")
                            typer.echo()
                    else:
                        typer.secho(f"❌ Task with ID '{task_id_str}' not found or could not be expanded.", fg=typer.colors.RED)
                        raise typer.Exit(code=1)
                        
                except Exception as e:
                    typer.secho(f"❌ Error expanding task: {e}", fg=typer.colors.RED)
                    raise typer.Exit(code=1)
            else:
                # Neither option provided
                typer.secho("❌ Please specify either --task-id <UUID> to expand a specific task or --all-pending to expand all pending tasks.", fg=typer.colors.RED)
                typer.echo("\nExamples:")
                typer.echo("  task-master expand --task-id 123e4567-e89b-12d3-a456-426614174000")
                typer.echo("  task-master expand --all-pending")
                typer.echo("  task-master expand --task-id 123e4567-e89b-12d3-a456-426614174000 --num 5 --research")
                raise typer.Exit(code=1)
                
        except Exception as e:
            typer.secho(f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("clear-subtasks")
    def clear_subtasks_command(
        ctx: typer.Context,
        task_id_str: Annotated[Optional[str], typer.Option("--task-id", "-id", help="ID of the task whose subtasks to clear.")] = None,
        all_tasks: Annotated[bool, typer.Option("--all", "-a", help="Clear subtasks from all tasks.")] = False
    ):
        """
        Clear subtasks from tasks.
        
        Use either --task-id to clear subtasks from a specific task or --all to clear subtasks from all tasks.
        """
        try:
            agent = get_agent(ctx)
            
            if all_tasks:
                # Clear subtasks from all tasks
                typer.echo("🔄 Clearing subtasks from all tasks...")
                
                count = agent.clear_subtasks_for_all_tasks()
                
                if count > 0:
                    typer.secho(f"✅ Cleared subtasks from {count} tasks.", fg=typer.colors.GREEN)
                else:
                    typer.secho("📝 No tasks with subtasks found to clear.", fg=typer.colors.YELLOW)
                    
            elif task_id_str:
                # Clear subtasks from specific task
                try:
                    task_uuid = UUID(task_id_str)
                except ValueError:
                    typer.secho(f"❌ Invalid task ID format: '{task_id_str}'. Please provide a valid UUID.", fg=typer.colors.RED)
                    raise typer.Exit(code=1)
                
                typer.echo(f"🔄 Clearing subtasks for task {task_id_str}...")
                
                success = agent.clear_subtasks_for_task(task_uuid)
                
                if success:
                    typer.secho(f"✅ Subtasks cleared for task ID {task_uuid}.", fg=typer.colors.GREEN)
                else:
                    typer.secho(f"❌ Task not found or no subtasks to clear for task ID {task_uuid}.", fg=typer.colors.RED)
                    raise typer.Exit(code=1)
            else:
                # Neither option provided
                typer.secho("❌ Please specify either --task-id <UUID> to clear subtasks from a specific task or --all to clear subtasks from all tasks.", fg=typer.colors.RED)
                typer.echo("\nExamples:")
                typer.echo("  task-master clear-subtasks --task-id 123e4567-e89b-12d3-a456-426614174000")
                typer.echo("  task-master clear-subtasks --all")
                raise typer.Exit(code=1)
                
        except Exception as e:
            typer.secho(f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("update-task")
    def update_task_command(
        ctx: typer.Context,
        task_id_str: Annotated[str, typer.Argument(help="ID of the task to update.")],
        refinement_instruction: Annotated[str, typer.Argument(help="Instructions for how to refine the task.")],
        use_research: Annotated[bool, typer.Option("--research", help="Use the research model for refinement.")] = False
    ):
        """
        Update a task using AI-powered refinement.
        
        The refinement instruction can include requests to modify the title, description, 
        status, priority, details, test strategy, or other task properties.
        """
        try:
            agent = get_agent(ctx)
            
            # Parse task ID
            try:
                task_uuid = UUID(task_id_str)
            except ValueError:
                typer.secho(f"❌ Invalid task ID format: '{task_id_str}'. Please provide a valid UUID.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            
            # Verify item exists and is a task
            item = agent.get_item_by_id(task_uuid)
            if item is None:
                typer.secho(f"❌ Task with ID '{task_id_str}' not found.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            
            if not isinstance(item, Task):
                typer.secho(f"❌ Item with ID '{task_id_str}' is not a task. Use 'update-subtask' for subtasks.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            
            typer.echo(f"🔄 Updating task '{item.title}' using {'research' if use_research else 'main'} model...")
            
            # Call the refinement method
            updated_item = asyncio.run(agent.refine_task_or_subtask(
                task_uuid, refinement_instruction, use_research=use_research
            ))
            
            if updated_item:
                typer.secho(f"✅ Successfully updated task '{updated_item.title}'", fg=typer.colors.GREEN)
                typer.echo("\n📋 Updated Task Details:")
                typer.echo("=" * 50)
                typer.secho(f"Title: {updated_item.title}", fg=typer.colors.CYAN, bold=True)
                typer.echo(f"ID: {updated_item.id}")
                typer.echo(f"Status: {updated_item.status.value}")
                typer.echo(f"Priority: {updated_item.priority.value}")
                typer.echo(f"Description: {updated_item.description}")
                if updated_item.details:
                    typer.echo(f"Details: {updated_item.details}")
                if updated_item.testStrategy:
                    typer.echo(f"Test Strategy: {updated_item.testStrategy}")
                if updated_item.subtasks:
                    typer.echo(f"Subtasks: {len(updated_item.subtasks)} subtask(s)")
            else:
                typer.secho(f"❌ Failed to update task. Please check the logs for details.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
                
        except Exception as e:
            typer.secho(f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("update-subtask")
    def update_subtask_command(
        ctx: typer.Context,
        subtask_id_str: Annotated[str, typer.Argument(help="ID of the subtask to update.")],
        refinement_instruction: Annotated[str, typer.Argument(help="Instructions for how to refine the subtask.")],
        use_research: Annotated[bool, typer.Option("--research", help="Use the research model for refinement.")] = False
    ):
        """
        Update a subtask using AI-powered refinement.
        
        The refinement instruction can include requests to modify the title, description, 
        status, priority, details, test strategy, or other subtask properties.
        """
        try:
            agent = get_agent(ctx)
            
            # Parse subtask ID
            try:
                subtask_uuid = UUID(subtask_id_str)
            except ValueError:
                typer.secho(f"❌ Invalid subtask ID format: '{subtask_id_str}'. Please provide a valid UUID.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            
            # Verify item exists and is a subtask
            item = agent.get_item_by_id(subtask_uuid)
            if item is None:
                typer.secho(f"❌ Subtask with ID '{subtask_id_str}' not found.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            
            if not isinstance(item, Subtask):
                typer.secho(f"❌ Item with ID '{subtask_id_str}' is not a subtask. Use 'update-task' for tasks.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            
            typer.echo(f"🔄 Updating subtask '{item.title}' using {'research' if use_research else 'main'} model...")
            
            # Call the refinement method
            updated_item = asyncio.run(agent.refine_task_or_subtask(
                subtask_uuid, refinement_instruction, use_research=use_research
            ))
            
            if updated_item:
                typer.secho(f"✅ Successfully updated subtask '{updated_item.title}'", fg=typer.colors.GREEN)
                typer.echo("\n📋 Updated Subtask Details:")
                typer.echo("=" * 50)
                typer.secho(f"Title: {updated_item.title}", fg=typer.colors.CYAN, bold=True)
                typer.echo(f"ID: {updated_item.id}")
                typer.echo(f"Status: {updated_item.status.value}")
                typer.echo(f"Priority: {updated_item.priority.value}")
                typer.echo(f"Description: {updated_item.description}")
                if updated_item.details:
                    typer.echo(f"Details: {updated_item.details}")
                if updated_item.testStrategy:
                    typer.echo(f"Test Strategy: {updated_item.testStrategy}")
            else:
                typer.secho(f"❌ Failed to update subtask. Please check the logs for details.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
                
        except Exception as e:
            typer.secho(f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("add-task")
    def add_task_command(
        ctx: typer.Context,
        description: Annotated[str, typer.Argument(help="Description or prompt for the new task.")],
        dependencies: Annotated[Optional[List[str]], typer.Option("--dep", help="Task IDs this new task depends on (can be used multiple times).")] = None,
        priority: Annotated[Optional[str], typer.Option("--priority", help="Priority of the new task (low, medium, high, critical).")] = None,
        use_research: Annotated[bool, typer.Option("--research", help="Use the research model for task generation.")] = False
    ):
        """
        Add a new task to the project using AI-driven task generation.
        
        The AI will analyze your description and generate a complete task with title,
        detailed description, implementation notes, and optionally initial subtasks.
        """
        try:
            agent = get_agent(ctx)
            
            # Validate dependencies format if provided
            if dependencies:
                for dep_id in dependencies:
                    try:
                        UUID(dep_id)
                    except ValueError:
                        typer.secho(f"❌ Invalid dependency ID format: '{dep_id}'. Please provide valid UUIDs.", fg=typer.colors.RED)
                        raise typer.Exit(code=1)
            
            # Validate priority format if provided
            if priority:
                valid_priorities = ["low", "medium", "high", "critical"]
                if priority.lower() not in valid_priorities:
                    typer.secho(f"❌ Invalid priority: '{priority}'. Valid priorities are: {', '.join(valid_priorities)}", fg=typer.colors.RED)
                    raise typer.Exit(code=1)
            
            typer.echo(f"🔄 Generating new task using {'research' if use_research else 'main'} model...")
            
            # Call the agent to add the new task
            new_task = asyncio.run(agent.add_new_task(
                description=description,
                use_research=use_research,
                dependencies_str=dependencies,
                priority_str=priority
            ))
            
            if new_task:
                typer.secho(f"✅ Successfully added new task: '{new_task.title}'", fg=typer.colors.GREEN)
                typer.echo(f"📋 Task ID: {new_task.id}")
                typer.echo(f"📝 Description: {new_task.description}")
                typer.echo(f"⚡ Priority: {new_task.priority.value}")
                typer.echo(f"📊 Status: {new_task.status.value}")
                
                if new_task.dependencies:
                    typer.echo(f"🔗 Dependencies: {', '.join(str(dep) for dep in new_task.dependencies)}")
                
                if new_task.details:
                    typer.echo(f"🔍 Details: {new_task.details}")
                
                if new_task.testStrategy:
                    typer.echo(f"🧪 Test Strategy: {new_task.testStrategy}")
                
                if new_task.subtasks:
                    typer.echo(f"📋 Generated {len(new_task.subtasks)} initial subtasks:")
                    for i, subtask in enumerate(new_task.subtasks, 1):
                        typer.secho(f"  {i}. {subtask.title}", fg=typer.colors.BLUE)
                        typer.echo(f"     ID: {subtask.id}")
                        typer.echo(f"     Description: {subtask.description}")
                
            else:
                typer.secho("❌ Failed to add new task. Please check the logs for details.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
                
        except Exception as e:
            typer.secho(f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("add-dependency")
    def add_dependency_command(
        ctx: typer.Context,
        task_id_str: Annotated[str, typer.Argument(help="ID (UUID) of the task to which the dependency will be added.")],
        depends_on_id_str: Annotated[str, typer.Argument(help="ID (UUID) of the task that 'task_id' will depend on.")],
    ):
        """
        Add a dependency between two tasks.
        """
        try:
            agent = get_agent(ctx)

            try:
                task_uuid = UUID(task_id_str)
                depends_on_uuid = UUID(depends_on_id_str)
            except ValueError:
                typer.secho(f"❌ Invalid UUID format for task or dependency ID. Please provide valid UUIDs.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            
            if task_uuid == depends_on_uuid:
                typer.secho(f"❌ A task cannot depend on itself. Task ID: {task_id_str}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

            typer.echo(f"🔄 Attempting to add dependency: Task {task_id_str} depends on {depends_on_id_str}...")

            success = agent.add_task_dependency(task_uuid, depends_on_uuid)

            if success:
                typer.secho(f"✅ Successfully added dependency: Task {task_id_str} now depends on {depends_on_id_str}.", fg=typer.colors.GREEN)
            else:
                typer.secho(f"❌ Failed to add dependency. This could be due to tasks not existing, a circular dependency, or the dependency already existing.", fg=typer.colors.RED)
                # Provide more specific feedback if possible (e.g., by checking validation errors)
                current_plan = agent.get_current_project_plan()
                if current_plan:
                    tasks_map = {t.id: t for t in current_plan.tasks}
                    if task_uuid not in tasks_map:
                        typer.secho(f"   Error: Task with ID {task_id_str} not found.", fg=typer.colors.RED)
                    elif depends_on_uuid not in tasks_map:
                        typer.secho(f"   Error: Dependency task with ID {depends_on_id_str} not found.", fg=typer.colors.RED)
                    else:
                        # Re-validate to check for circular dependency specifically
                        # Note: This is an approximation as agent.add_task_dependency already checks
                        # This is for user feedback purposes.
                        validation_errors = agent.validate_all_dependencies()
                        if validation_errors.get("circular"):
                            typer.secho(f"   Error: Adding this dependency would create a circular dependency.", fg=typer.colors.RED)
                            for err_msg in validation_errors["circular"]:
                                typer.secho(f"     - {err_msg}", fg=typer.colors.YELLOW)
                        elif depends_on_uuid in tasks_map[task_uuid].dependencies: # Check if already exists, since add_task_dependency handles this.
                            typer.secho(f"   Error: Task {task_id_str} already depends on {depends_on_id_str}.", fg=typer.colors.RED)
                        else:
                            typer.secho(f"   Error: Unknown reason for failure. Check logs.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        except Exception as e:
            typer.secho(f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("remove-dependency")
    def remove_dependency_command(
        ctx: typer.Context,
        task_id_str: Annotated[str, typer.Argument(help="ID (UUID) of the task from which the dependency will be removed.")],
        depends_on_id_str: Annotated[str, typer.Argument(help="ID (UUID) of the dependency to remove from 'task_id'.")],
    ):
        """
        Remove a dependency from a task.
        """
        try:
            agent = get_agent(ctx)

            try:
                task_uuid = UUID(task_id_str)
                depends_on_uuid = UUID(depends_on_id_str)
            except ValueError:
                typer.secho(f"❌ Invalid UUID format for task or dependency ID. Please provide valid UUIDs.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            
            typer.echo(f"🔄 Attempting to remove dependency: Task {task_id_str} from {depends_on_id_str}...")

            success = agent.remove_task_dependency(task_uuid, depends_on_uuid)

            if success:
                typer.secho(f"✅ Successfully removed dependency: Task {task_id_str} no longer depends on {depends_on_id_str}.", fg=typer.colors.GREEN)
            else:
                typer.secho(f"❌ Failed to remove dependency. Task {task_id_str} not found or does not depend on {depends_on_id_str}.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        except Exception as e:
            typer.secho(f"❌ An unexpected error occurred: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("validate-dependencies")
    def validate_dependencies_command(
        ctx: typer.Context,
    ):
        """
        Validate all dependencies in the current project plan.
        Checks for missing task IDs and circular dependencies.
        """
        try:
            agent = get_agent(ctx)
            typer.echo("🔄 Validating all dependencies in the project plan...")

            errors = agent.validate_all_dependencies()

            if not errors["circular"] and not errors["missing_ids"]:
                typer.secho("✅ All dependencies validated successfully. No errors found.", fg=typer.colors.GREEN)
            else:
                typer.secho("⚠️ Dependency validation found issues:", fg=typer.colors.YELLOW, bold=True)
                if errors["missing_ids"]:
                    typer.secho("\n  ❌ Missing Dependency IDs:", fg=typer.colors.RED)
                    for err_msg in errors["missing_ids"]:
                        typer.echo(f"    - {err_msg}")
                if errors["circular"]:
                    typer.secho("\n  ⭕ Circular Dependencies:", fg=typer.colors.RED)
                    for err_msg in errors["circular"]:
                        typer.echo(f"    - {err_msg}")
                raise typer.Exit(code=1)

        except Exception as e:
            typer.secho(f"❌ An unexpected error occurred during dependency validation: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("fix-dependencies")
    async def fix_dependencies_command( # Made async
        ctx: typer.Context,
    ):
        """
        Attempt to automatically fix dependency issues (missing IDs, circular dependencies)
        using AI assistance.
        """
        try:
            agent = get_agent(ctx)
            typer.echo("🤖 Attempting to auto-fix dependency issues using AI...")

            fix_summary = await agent.auto_fix_dependencies() # Await the async call

            if fix_summary["fixes_applied"]:
                typer.secho("✅ AI-assisted dependency fixes applied.", fg=typer.colors.GREEN)
                if fix_summary["remaining_errors"]["circular"] or fix_summary["remaining_errors"]["missing_ids"]:
                    typer.secho("⚠️ Some errors still remain after fixing:", fg=typer.colors.YELLOW, bold=True)
                    if fix_summary["remaining_errors"]["missing_ids"]:
                        typer.secho("\n  ❌ Remaining Missing Dependency IDs:", fg=typer.colors.RED)
                        for err_msg in fix_summary["remaining_errors"]["missing_ids"]:
                            typer.echo(f"    - {err_msg}")
                    if fix_summary["remaining_errors"]["circular"]:
                        typer.secho("\n  ⭕ Remaining Circular Dependencies:", fg=typer.colors.RED)
                        for err_msg in fix_summary["remaining_errors"]["circular"]:
                            typer.echo(f"    - {err_msg}")
                    raise typer.Exit(code=1)
                else:
                    typer.secho("🎉 All dependency errors resolved!", fg=typer.colors.GREEN)
            else:
                if fix_summary["remaining_errors"]["circular"] or fix_summary["remaining_errors"]["missing_ids"]:
                    typer.secho("📝 No fixes were applied, or no errors were found initially.", fg=typer.colors.YELLOW)
                    typer.secho("Current dependency errors:", fg=typer.colors.YELLOW, bold=True)
                    if fix_summary["remaining_errors"]["missing_ids"]:
                        typer.secho("\n  ❌ Missing Dependency IDs:", fg=typer.colors.RED)
                        for err_msg in fix_summary["remaining_errors"]["missing_ids"]:
                            typer.echo(f"    - {err_msg}")
                    if fix_summary["remaining_errors"]["circular"]:
                        typer.secho("\n  ⭕ Circular Dependencies:", fg=typer.colors.RED)
                        for err_msg in fix_summary["remaining_errors"]["circular"]:
                            typer.echo(f"    - {err_msg}")
                    raise typer.Exit(code=1)
                else:
                    typer.secho("📝 No dependency errors found to fix.", fg=typer.colors.GREEN)
            
        except Exception as e:
            typer.secho(f"❌ An unexpected error occurred during auto-fixing dependencies: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)