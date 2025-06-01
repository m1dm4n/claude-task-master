"""Main CLI application for the DevTask AI Assistant."""

import typer

from .models import create_models_app
from .project import create_project_commands
from .planning import create_planning_commands
from .tasks import create_task_commands

app = typer.Typer(
    name="task-master",
    help="A CLI for managing tasks with the DevTask AI Assistant.",
    add_completion=True,
)

# Create and add subcommand group for model management
models_app = create_models_app()
app.add_typer(models_app, name="models")

# Add commands from other modules
create_project_commands(app)
create_planning_commands(app)
create_task_commands(app)

if __name__ == "__main__":
    app()