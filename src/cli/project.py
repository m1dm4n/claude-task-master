"""Project initialization and status commands for the DevTask AI Assistant CLI."""

import typer
from typing_extensions import Annotated
from typing import Optional

from ..data_models import TaskStatus
from .utils import get_agent


def create_project_commands(app: typer.Typer):
    """Add project-related commands to the main app."""
    
    @app.command()
    def init(
        ctx: typer.Context,
        project_name: Annotated[Optional[str], typer.Option("--name", "-n", help="Name for the project")] = None
    ):
        """
        Initialize a new Task Master project in the current directory.
        """
        try:
            agent = get_agent(ctx)
            agent.initialize_project(project_name)
            
            if project_name:
                typer.secho(f"✅ Project '{project_name}' initialized successfully!", fg=typer.colors.GREEN)
            else:
                typer.secho("✅ Project initialized successfully!", fg=typer.colors.GREEN)
                
            typer.echo(f"📁 Workspace: {agent.workspace_path}")
            typer.echo("🔧 Use 'task-master models setup' to configure AI models")
            
        except Exception as e:
            typer.secho(f"❌ Error initializing project: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command()
    def status(ctx: typer.Context):
        """
        Show project and configuration status.
        """
        try:
            agent = get_agent(ctx)
            project_plan = agent.get_current_project_plan()
            configs = agent.get_model_configurations()
            
            typer.echo("📊 Task Master Status")
            typer.echo("=" * 30)
            
            # Project info
            if project_plan:
                typer.echo(f"📁 Project: {project_plan.project_title}")
                typer.echo(f"🎯 Goal: {project_plan.overall_goal}")
                typer.echo(f"📋 Total Tasks: {len(project_plan.tasks)}")
                
                # Task status summary
                status_counts = {}
                for task in project_plan.tasks:
                    status_counts[task.status] = status_counts.get(task.status, 0) + 1
                
                if status_counts:
                    typer.echo("\n📈 Task Status Summary:")
                    for status_enum, count in status_counts.items():
                        emoji = {
                            TaskStatus.PENDING.value: "⏳",
                            TaskStatus.IN_PROGRESS.value: "🔄",
                            TaskStatus.COMPLETED.value: "✅",
                            TaskStatus.BLOCKED.value: "🚫",
                            TaskStatus.CANCELLED.value: "❌",
                            TaskStatus.DEFERRED.value: "⏰"
                        }.get(status_enum.value, "📝")
                        typer.echo(f"   {emoji} {status_enum.value}: {count}")
            else:
                typer.echo("📁 No project loaded")
            
            # Model configurations
            typer.echo(f"\n🤖 Model Configurations:")
            configured_models = [name for name, config in configs.items() if config]
            if configured_models:
                typer.echo(f"   ✅ Configured: {', '.join(configured_models)}")
            else:
                typer.echo("   ❌ No models configured")
                typer.echo("   💡 Use 'task-master models setup' to configure")
            
            typer.echo(f"\n📁 Workspace: {agent.workspace_path}")
            
        except Exception as e:
            typer.secho(f"❌ Error getting status: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command()
    def next(ctx: typer.Context):
        """
        Show the next task to work on based on dependencies and status.
        """
        try:
            agent = get_agent(ctx)

            # Check for project initialization
            if not agent.config_manager.config_file_path.exists():
                typer.secho("❌ Project not initialized. Please run 'task-master init' first.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            
            typer.echo("🔍 Determining the next actionable task...")
            next_task = agent.get_next_task()
            
            if next_task:
                typer.secho("\n🎯 Next actionable task:", fg=typer.colors.GREEN, bold=True)
                typer.echo("=" * 50)
                typer.secho(f"Title: {next_task.title}", fg=typer.colors.CYAN, bold=True)
                typer.echo(f"ID: {next_task.id}")
                typer.echo(f"Description: {next_task.description if next_task.description else 'N/A'}")
                typer.echo(f"Status: {next_task.status.value}")
                if next_task.priority:
                    typer.echo(f"Priority: {next_task.priority.value}")
                if next_task.dependencies:
                    typer.echo(f"Dependencies: Yes (Count: {len(next_task.dependencies)})")
                else:
                    typer.echo("Dependencies: No")
                if next_task.due_date:
                    typer.echo(f"Due Date: {next_task.due_date.strftime('%Y-%m-%d')}")
                else:
                    typer.echo("Due Date: N/A")
                
                typer.echo("\n💡 Use 'task-master show <ID>' for more details on this task.")
            else:
                typer.secho("\n🤷 No actionable PENDING tasks found with all dependencies met.", fg=typer.colors.BRIGHT_YELLOW)
                typer.echo("💡 Use 'task-master list' to see all tasks and their statuses.")
            
        except Exception as e:
            typer.secho(f"❌ Error finding next task: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command()
    def hello(name: Annotated[str, typer.Option(help="The name to greet.")] = "World"):
        """
        A simple greeting command.
        """
        typer.echo(f"Hello {name} from Task Master CLI!")