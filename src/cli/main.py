
"""Main CLI application for the DevTask AI Assistant."""

from typing import Optional
from typing_extensions import Annotated
import typer
# Removed asyncio import as per user instruction

from .init_llm import create_llm_app
from .project import create_project_commands
from .planning import create_planning_commands
from .task_query import create_task_query_commands
from .task_modification import create_task_modification_commands
from .task_generation import create_task_generation_commands
from ..agent_core.assistant import DevTaskAIAssistant

app = typer.Typer(
    name="task-master",
    help="A CLI for managing tasks with the DevTask AI Assistant.",
    add_completion=True,
)

@app.callback(invoke_without_command=True)
def main_callback( # Reverted to synchronous def
    ctx: typer.Context,
    workspace: Annotated[Optional[str], typer.Option(
        "--workspace", "-w",
        help="Path to the project workspace directory. Defaults to current directory.",
        envvar="TASKMASTER_WORKSPACE",
        show_default=False
    )] = None,
):
    """
    DevTask AI Assistant CLI.
    """
    if ctx.invoked_subcommand is None:
        pass

    # The workspace path is now handled internally by ProjectIO via DevTaskAIAssistant
    # No need for os.path.abspath or os.getcwd() here.
    ctx.obj = {}
    ctx.obj["workspace_path"] = workspace if workspace else "." # Pass relative path or current dir
    agent = DevTaskAIAssistant(ctx.obj["workspace_path"])
    # Removed await agent._ainit_() - asynchronous initialization will be handled by Architect's refactoring
    ctx.obj["agent"] = agent


# Create and add subcommand group for model management
models_app = create_llm_app()
app.add_typer(models_app, name="models")

# Add commands from other modules
create_project_commands(app)
create_planning_commands(app)
create_task_query_commands(app)
create_task_modification_commands(app)
create_task_generation_commands(app)

if __name__ == "__main__":
    app()