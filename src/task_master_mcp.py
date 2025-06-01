#!/usr/bin/env python
import subprocess
import shlex
from typing import Optional, List, Union

from fastmcp import FastMCP

mcp = FastMCP(
    name="TaskMasterAgentMCP",
    instructions="This server provides tools to interact with the Task Master CLI.",
)

@mcp.tool()
def parse_prd(prd_file: str, num_tasks: Optional[int] = None) -> dict:
    """
    Parse a PRD file and generate tasks.
    Corresponds to: task-master parse-prd <prd-file.txt> [--num-tasks=N]
    """
    command = ["task-master", "parse-prd", prd_file]
    if num_tasks is not None:
        command.append(f"--num-tasks={num_tasks}")

    try:
        # Ensure task-master is executable or in PATH
        # Consider specifying the full path if it's not globally available
        # For example, if task-master is a local script:
        # command = ["python", "./path/to/task-master-cli.py", "parse-prd", prd_file]
        
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}

@mcp.tool()
def list_tasks(status: Optional[str] = None, with_subtasks: Optional[bool] = False) -> dict:
    """
    List tasks.
    Corresponds to: task-master list [--status=&lt;status&gt;] [--with-subtasks]
    """
    command = ["task-master", "list"]
    if status:
        command.append(f"--status={status}")
    if with_subtasks:
        command.append("--with-subtasks")

    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}
@mcp.tool()
def show_next_task() -> dict:
    """
    Show the next task to work on based on dependencies and status.
    Corresponds to: task-master next
    """
    command = ["task-master", "next"]
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}

@mcp.tool()
def show_task(task_id: str) -> dict:
    """
    Show details of a specific task.
    Corresponds to: task-master show &lt;id&gt;
    """
    # The CLI allows 'task-master show <id>' or 'task-master show --id=<id>'.
    # We'll use the simpler positional argument version.
    command = ["task-master", "show", task_id]
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}
@mcp.tool()
def update_tasks(from_id: str, prompt: str, research: Optional[bool] = False) -> dict:
    """
    Update tasks from a specific ID and provide context.
    Corresponds to: task-master update --from=&lt;id&gt; --prompt="&lt;prompt&gt;" [--research]
    """
    command = ["task-master", "update", f"--from={from_id}", f"--prompt={prompt}"]
    if research:
        command.append("--research")
    
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}

@mcp.tool()
def update_task(task_id: str, prompt: str, research: Optional[bool] = False) -> dict:
    """
    Update a single task by ID with new information.
    Corresponds to: task-master update-task --id=&lt;id&gt; --prompt="&lt;prompt&gt;" [--research]
    """
    command = ["task-master", "update-task", f"--id={task_id}", f"--prompt={prompt}"]
    if research:
        command.append("--research")

    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}

@mcp.tool()
def update_subtask(subtask_id: str, prompt: str, research: Optional[bool] = False) -> dict:
    """
    Update a specific subtask by ID with new information.
    Corresponds to: task-master update-subtask --id=&lt;parentId.subtaskId&gt; --prompt="&lt;prompt&gt;" [--research]
    """
    command = ["task-master", "update-subtask", f"--id={subtask_id}", f"--prompt={prompt}"]
    if research:
        command.append("--research")

    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}
@mcp.tool()
def generate_task_files() -> dict:
    """
    Generate individual task files from tasks.json.
    Corresponds to: task-master generate
    """
    command = ["task-master", "generate"]
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}

@mcp.tool()
def set_task_status(task_ids: str, status: str) -> dict:
    """
    Set status of one or more tasks.
    Corresponds to: task-master set-status --id=&lt;id1,id2,...&gt; --status=&lt;status&gt;
    """
    command = ["task-master", "set-status", f"--id={task_ids}", f"--status={status}"]
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}
@mcp.tool()
def expand_tasks(
    task_id: Optional[str] = None,
    expand_all: Optional[bool] = False,
    num_subtasks: Optional[int] = None,
    prompt: Optional[str] = None,
    force: Optional[bool] = False,
    research: Optional[bool] = False,
) -> dict:
    """
    Expand a specific task or all tasks with subtasks.
    Corresponds to: task-master expand [--id=&lt;id&gt;] [--all] [--num=&lt;number&gt;] [--prompt="&lt;context&gt;"] [--force] [--research]
    """
    command = ["task-master", "expand"]
    if task_id:
        command.append(f"--id={task_id}")
        if num_subtasks is not None:
            command.append(f"--num={num_subtasks}")
        if prompt:
            command.append(f"--prompt={prompt}")
        # research can be combined with --id alone, or with --num/--prompt
        # The CLI doc implies --id --research is one form, and --id --num is another, --id --prompt is another
        # Let's assume research can be added if only --id is present, or if --id and (--num or --prompt) is present.
        # The command reference says:
        # task-master expand --id=<id> --num=<number>
        # task-master expand --id=<id> --prompt="<context>"
        # task-master expand --id=<id> --research
        # So --research should not be combined with --num or --prompt if --id is present
        if research:
            if num_subtasks is not None or prompt is not None:
                 return {"error": "Cannot use --research with --num or --prompt when specifying --id for expand_tasks. Use --research alone with --id.", "returncode": -1}
            command.append("--research")
            
    elif expand_all:
        command.append("--all")
        if force:
            command.append("--force")
        if research: # research can be with --all
            command.append("--research")
    else:
        return {"error": "Either task_id or expand_all must be specified for expand_tasks.", "returncode": -1}

    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}

@mcp.tool()
def clear_subtasks(task_ids: Optional[str] = None, clear_all: Optional[bool] = False) -> dict:
    """
    Clear subtasks from specific tasks or all tasks.
    Corresponds to: task-master clear-subtasks [--id=&lt;id1,id2,...&gt;] [--all]
    """
    command = ["task-master", "clear-subtasks"]
    if task_ids:
        command.append(f"--id={task_ids}")
    elif clear_all:
        command.append("--all")
    else:
        return {"error": "Either task_ids or clear_all must be specified for clear_subtasks.", "returncode": -1}

    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}
@mcp.tool()
def analyze_task_complexity(
    output_file: Optional[str] = None,
    model: Optional[str] = None,
    threshold: Optional[int] = None,
    tasks_file: Optional[str] = None,
    research: Optional[bool] = False,
) -> dict:
    """
    Analyze complexity of tasks.
    Corresponds to: task-master analyze-complexity [--output=&lt;file&gt;] [--model=&lt;model_name&gt;] [--threshold=&lt;1-10&gt;] [--file=&lt;tasks_file&gt;] [--research]
    """
    command = ["task-master", "analyze-complexity"]
    if output_file:
        command.append(f"--output={output_file}")
    if model:
        command.append(f"--model={model}")
    if threshold is not None:
        command.append(f"--threshold={threshold}")
    if tasks_file:
        command.append(f"--file={tasks_file}")
    if research:
        command.append("--research")

    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}

@mcp.tool()
def view_complexity_report(report_file: Optional[str] = None) -> dict:
    """
    Display the task complexity analysis report.
    Corresponds to: task-master complexity-report [--file=&lt;report_file&gt;]
    """
    command = ["task-master", "complexity-report"]
    if report_file:
        command.append(f"--file={report_file}")

    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}
@mcp.tool()
def add_task_dependency(task_id: str, depends_on_id: str) -> dict:
    """
    Add a dependency to a task.
    Corresponds to: task-master add-dependency --id=&lt;id&gt; --depends-on=&lt;id&gt;
    """
    command = ["task-master", "add-dependency", f"--id={task_id}", f"--depends-on={depends_on_id}"]
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}

@mcp.tool()
def remove_task_dependency(task_id: str, depends_on_id: str) -> dict:
    """
    Remove a dependency from a task.
    Corresponds to: task-master remove-dependency --id=&lt;id&gt; --depends-on=&lt;id&gt;
    """
    command = ["task-master", "remove-dependency", f"--id={task_id}", f"--depends-on={depends_on_id}"]
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}

@mcp.tool()
def validate_task_dependencies() -> dict:
    """
    Validate dependencies without fixing them.
    Corresponds to: task-master validate-dependencies
    """
    command = ["task-master", "validate-dependencies"]
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}

@mcp.tool()
def fix_task_dependencies() -> dict:
    """
    Find and fix invalid dependencies automatically.
    Corresponds to: task-master fix-dependencies
    """
    command = ["task-master", "fix-dependencies"]
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}
@mcp.tool()
def move_tasks(from_ids: str, to_ids: str) -> dict:
    """
    Move a task or subtask to a new position.
    Corresponds to: task-master move --from=&lt;id(s)&gt; --to=&lt;id(s)&gt;
    """
    from_id_list = from_ids.split(',')
    to_id_list = to_ids.split(',')

    # The CLI doc says: "Move multiple tasks at once (must have the same number of IDs)"
    # This check is for the case where both are multi-item lists.
    if len(from_id_list) > 1 and len(to_id_list) > 1 and len(from_id_list) != len(to_id_list):
        return {"error": "When moving multiple tasks to multiple new positions, the number of 'from' IDs must match the number of 'to' IDs.", "returncode": -1}
    # Other cases (e.g., single to single, multiple to single parent, single to new position) are handled by the CLI.

    command = ["task-master", "move", f"--from={from_ids}", f"--to={to_ids}"]
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}

@mcp.tool()
def add_new_task(
    prompt: str,
    research: Optional[bool] = False,
    dependencies: Optional[str] = None,
    priority: Optional[str] = None,
) -> dict:
    """
    Add a new task using AI.
    Corresponds to: task-master add-task --prompt="&lt;Description&gt;" [--research] [--dependencies=1,2,3] [--priority=high|medium|low]
    """
    command = ["task-master", "add-task", f"--prompt={prompt}"]
    if research:
        command.append("--research")
    if dependencies:
        command.append(f"--dependencies={dependencies}")
    if priority:
        command.append(f"--priority={priority}")

    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}
@mcp.tool()
def initialize_project() -> dict:
    """
    Initialize a new project with Task Master structure.
    Corresponds to: task-master init
    """
    command = ["task-master", "init"]
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}

@mcp.tool()
def configure_ai_models(
    set_main: Optional[str] = None,
    set_research_model: Optional[str] = None, # Renamed to avoid conflict with 'research' bools in other tools
    set_fallback: Optional[str] = None,
    ollama: Optional[bool] = False,
    openrouter: Optional[bool] = False,
    setup: Optional[bool] = False,
) -> dict:
    """
    View or configure AI models.
    Corresponds to: task-master models [--set-main &lt;model&gt;] [--set-research &lt;model&gt;] [--set-fallback &lt;model&gt;] [--ollama] [--openrouter] [--setup]
    """
    command = ["task-master", "models"]
    
    if setup:
        if set_main or set_research_model or set_fallback or ollama or openrouter:
            return {"error": "--setup cannot be used with other model configuration options.", "returncode": -1}
        command.append("--setup")
    else:
        if set_main:
            command.append(f"--set-main={set_main}")
            if ollama:
                command.append("--ollama")
        if set_research_model:
            command.append(f"--set-research={set_research_model}") # CLI uses --set-research
            if openrouter:
                command.append("--openrouter")
        if set_fallback:
            command.append(f"--set-fallback={set_fallback}")
        
        if ollama and not set_main:
            return {"error": "--ollama can only be used with --set-main.", "returncode": -1}
        if openrouter and not set_research_model:
            return {"error": "--openrouter can only be used with --set-research.", "returncode": -1}

    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode, "error": str(e)}
    except FileNotFoundError:
        return {"error": "task-master command not found. Make sure it is installed and in your PATH.", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}
if __name__ == "__main__":
    # This will run the server using stdio transport by default
    mcp.run()