"""Planning commands for the DevTask AI Assistant CLI."""

import typer
from ..utils.async_utils import run_async_tasks_sync
from typing_extensions import Annotated
from typing import Optional
from pathlib import Path



def create_planning_commands(app: typer.Typer):
    """Add planning-related commands to the main app."""
    
    @app.command()
    def plan( # Reverted to synchronous def
        ctx: typer.Context,
        project_goal: Annotated[str, typer.Argument(help="A concise description of the project's overall goal.")],
        project_title: Annotated[Optional[str], typer.Option("--title", "-t", help="Optional title for the project plan.")] = "New Project",
        num_tasks: Annotated[Optional[int], typer.Option("--num-tasks", "-n", help="Optional. Desired number of main tasks to generate.")] = None,
        use_research: Annotated[bool, typer.Option("--research", "-r", help="Use the research model for planning (if configured).")] = False,
    ):
        """
        Generate an initial project plan from a high-level goal.
        """
        typer.echo(f"✨ Generating project plan for: '{project_goal}'...")
        if num_tasks is not None:
            typer.echo(f"   (Focusing on approximately {num_tasks} main tasks)")
        if use_research:
            typer.echo("   (Using research model for enhanced planning)")

        try:
            agent = ctx.obj["agent"]
            project_plan = run_async_tasks_sync(agent.plan_project(
                project_goal=project_goal,
                project_title=project_title,
                num_tasks=num_tasks,
                use_research=use_research
            ))
            typer.secho(f"✅ Project plan '{project_plan.project_title}' generated and saved!", fg=typer.colors.GREEN)
            typer.echo("📋 Plan Summary:")
            typer.echo(f"   Overall Goal: {project_plan.overall_goal}")
            typer.echo(f"   Total Tasks: {len(project_plan.tasks)}")
            for i, task in enumerate(project_plan.tasks[:3]): # Show first 3 tasks
                typer.echo(f"     - {task.title} ({task.status})")
            if len(project_plan.tasks) > 3:
                typer.echo("     ...")
            typer.echo("\n💡 Use 'task-master list' to view the full plan.")
        except Exception as e:
            typer.secho(f"❌ Error generating project plan: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command("parse-prd")
    def parse_prd_command( # Reverted to synchronous def
        ctx: typer.Context,
        prd_file: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False, readable=True, help="Path to the Product Requirements Document (PRD) file.")],
        project_title: Annotated[Optional[str], typer.Option("--title", "-t", help="Optional title for the project plan. Defaults to derived from PRD filename.")] = "New Project",
        num_tasks: Annotated[Optional[int], typer.Option("--num-tasks", "-n", help="Optional. Desired number of main tasks to generate.")] = None,
        use_research: Annotated[bool, typer.Option("--research", "-r", help="Use the research model for parsing and planning (if configured).")] = False,
    ):
        """
        Parse a Product Requirements Document (PRD) file and generate a structured project plan.
        """
        typer.echo(f"📄 Attempting to parse PRD file: '{prd_file.name}'...")
        if num_tasks is not None:
            typer.echo(f"   (Focusing on approximately {num_tasks} main tasks)")
        if use_research:
            typer.echo("   (Using research model for enhanced parsing)")

        try:
            agent = ctx.obj["agent"]
            project_plan = run_async_tasks_sync(agent.plan_project_from_prd_file(
                prd_file_path=str(prd_file), # Pass the path directly
                project_title=project_title,
                num_tasks=num_tasks,
                use_research=use_research
            ))
            typer.secho(f"✅ Project plan '{project_plan.project_title}' generated from PRD and saved!", fg=typer.colors.GREEN)
            typer.echo("📋 Plan Summary:")
            typer.echo(f"   Overall Goal: {project_plan.overall_goal}")
            typer.echo(f"   Total Tasks: {len(project_plan.tasks)}")
            for i, task in enumerate(project_plan.tasks[:3]): # Show first 3 tasks
                typer.echo(f"     - {task.title} ({task.status})")
            if len(project_plan.tasks) > 3:
                typer.echo("     ...")
            typer.echo("\n💡 Use 'task-master list' to view the full plan.")
        except FileNotFoundError as e:
            typer.secho(f"❌ Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        except Exception as e:
            typer.secho(f"❌ Error parsing PRD and generating plan: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)