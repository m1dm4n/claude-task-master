"""Main CLI application for the DevTask AI Assistant."""

import typer
import os # Added import for os
from typing import Optional # Added import for Optional
from typing_extensions import Annotated # Added import for Annotated

from .models import create_models_app
from .project import create_project_commands
from .planning import create_planning_commands
from .tasks import create_task_commands

app = typer.Typer(
    name="task-master",
    help="A CLI for managing tasks with the DevTask AI Assistant.",
    add_completion=True,
)

@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    workspace: Annotated[Optional[str], typer.Option(
        "--workspace", "-w",
        help="Path to the project workspace directory. Defaults to current directory.",
        envvar="TASKMASTER_WORKSPACE", # Optional: allow setting via env var
        show_default=False # Show CWD as default only if not explicitly set
    )] = None,
):
    """
    DevTask AI Assistant CLI.
    """
    if ctx.invoked_subcommand is None:
        # If no subcommand is called, and it's just 'task-master --workspace ...'
        # we might want to print help or a status, or just allow it.
        # For now, just ensure obj is ready for subcommands.
        pass

    ctx.ensure_object(dict)
    if workspace:
        ctx.obj["workspace_path"] = os.path.abspath(workspace)
    else:
        # If --workspace is not provided, then get_agent will use os.getcwd()
        # We can explicitly set it here too for consistency, or let get_agent handle it.
        # Let's set it here to be explicit and ensure it's absolute.
        ctx.obj["workspace_path"] = os.getcwd()
    
    # For testing purposes, we might want to echo the workspace path
    # typer.echo(f"CLI using workspace: {ctx.obj['workspace_path']}")


# Create and add subcommand group for model management
models_app = create_models_app()
app.add_typer(models_app, name="models")

# Add commands from other modules
create_project_commands(app)
create_planning_commands(app)
create_task_commands(app)

if __name__ == "__main__":
    app()