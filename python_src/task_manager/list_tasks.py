import json
import os
import pathlib
import logging
from typing import Any, Dict, List, Literal, Optional
from collections import Counter

# Attempt to import Rich, fallback to basic printing if not available
try:
    from rich.table import Table
    from rich.console import Console
    from rich.text import Text
    from rich.progress_bar import ProgressBar
    from rich.panel import Panel
    from rich.columns import Columns
    from rich.layout import Layout
    from rich.live import Live
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    # Define dummy classes if Rich is not available, so type hints don't break
    # and calls can be guarded by RICH_AVAILABLE
    class Table: pass
    class Console: pass
    class Text: pass
    class ProgressBar: pass
    class Panel: pass
    class Columns: pass
    class Layout: pass
    class Live: pass


logger = logging.getLogger(__name__)

# --- Simplified JSON read (can be replaced by a common util) ---
def _read_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from file: {file_path}")
        return None

def _truncate(text: str, length: int) -> str:
    if len(text) <= length:
        return text
    return text[:length-3] + "..."

def _get_status_style_py(status: Optional[str]) -> str:
    status_str = status.lower() if status else "pending"
    style_map = {
        "done": "green",
        "completed": "green",
        "in-progress": "blue",
        "pending": "yellow",
        "blocked": "red",
        "deferred": "dim", # Using 'dim' for grey-like appearance in Rich
        "review": "magenta",
        "cancelled": "dim"
    }
    return style_map.get(status_str, "dim")


def _format_dependencies_py(
    dep_ids: List[Any], 
    all_tasks: List[Dict], 
    for_rich_table: bool = False,
    parent_task_id: Optional[int] = None, 
    is_sub_dependency: bool = False
) -> Any: # Returns str or Text
    if not dep_ids:
        return "-" if for_rich_table else "None"
    
    parts = []
    for dep_id_any_type in dep_ids:
        actual_dep_id_str = str(dep_id_any_type)
        is_cross_task_sub_dep = isinstance(dep_id_any_type, str) and "." in dep_id_any_type
        
        dep_task_obj = None
        display_id = actual_dep_id_str

        try:
            if is_cross_task_sub_dep:
                p_id_str, s_id_str = actual_dep_id_str.split(".",1)
                p_id, s_id = int(p_id_str), int(s_id_str)
                parent_for_dep = next((t for t in all_tasks if t.get("id") == p_id), None)
                if parent_for_dep:
                    dep_task_obj = next((st for st in parent_for_dep.get("subtasks", []) if st.get("id") == s_id), None)
                display_id = f"{p_id}.{s_id}"
            elif is_sub_dependency and parent_task_id is not None:
                dep_id = int(dep_id_any_type)
                parent_for_dep = next((t for t in all_tasks if t.get("id") == parent_task_id), None)
                if parent_for_dep:
                    dep_task_obj = next((st for st in parent_for_dep.get("subtasks", []) if st.get("id") == dep_id), None)
                display_id = f"{parent_task_id}.{dep_id}"
            else:
                dep_id = int(dep_id_any_type)
                dep_task_obj = next((t for t in all_tasks if t.get("id") == dep_id), None)
                display_id = str(dep_id)
        except ValueError:
            parts.append(Text(f"⚠️ {display_id} (Err)", style="bright_red") if RICH_AVAILABLE and for_rich_table else f"⚠️ {display_id} (Err)")
            continue

        if dep_task_obj:
            status = dep_task_obj.get("status", "pending").lower()
            char = "✅" if status in ["done", "completed"] else ("🚧" if status == "in-progress" else "⏱️")
            style = _get_status_style_py(status) if RICH_AVAILABLE else ""
            if RICH_AVAILABLE and for_rich_table:
                parts.append(Text(f"{char} {display_id}", style=style))
            else:
                parts.append(f"{char} {display_id}")
        else:
            if RICH_AVAILABLE and for_rich_table:
                parts.append(Text(f"⚠️ {display_id} (NF)", style="bright_red"))
            else:
                 parts.append(f"⚠️ {display_id} (NF)")
    
    if not parts: return "-" if for_rich_table else "None"

    if RICH_AVAILABLE and for_rich_table:
        return Text(", ").join(parts)
    else:
        return ", ".join(parts)


def list_tasks_py(
    tasks_path: str,
    status_filter: Optional[str] = None,
    report_path: Optional[str] = None, 
    with_subtasks: bool = False,
    output_format: Literal["text", "json", "rich"] = "rich", # Default to rich
) -> Optional[Dict[str, Any]]:

    try:
        tasks_data_full = _read_json_file(tasks_path)
        if not tasks_data_full or not isinstance(tasks_data_full.get("tasks"), list):
            # Try to load if tasks_path is actually a list of tasks
            if isinstance(tasks_path, str) and os.path.exists(tasks_path):
                raw_list_data = _read_json_file(tasks_path)
                if isinstance(raw_list_data, list):
                    tasks_data_full = {"tasks": raw_list_data, "metadata": tasks_data_full.get("metadata", {})}
                    logger.info("Successfully loaded tasks as a direct list.")
                else:
                    raise ValueError(f"No valid tasks found in {tasks_path}. Content is not a list of tasks nor a dict with a 'tasks' key.")
            else:
                raise ValueError(f"No valid tasks found in {tasks_path} or tasks data is malformed.")

        all_tasks_list: List[Dict] = tasks_data_full.get("tasks", [])
        project_name = tasks_data_full.get("metadata", {}).get("project_name", "Project Tasks")


        filtered_tasks = all_tasks_list
        if status_filter and status_filter.lower() != "all":
            filtered_tasks = [
                task for task in all_tasks_list 
                if task.get("status", "").lower() == status_filter.lower()
            ]

        # Calculate Statistics
        total_tasks_count = len(all_tasks_list)
        task_status_counts = Counter(t.get("status", "pending").lower() for t in all_tasks_list)
        completed_tasks_count = task_status_counts.get("done", 0) + task_status_counts.get("completed", 0)
        task_completion_percentage = (completed_tasks_count / total_tasks_count * 100) if total_tasks_count > 0 else 0
        
        total_subtasks_count = 0
        subtask_status_counts = Counter()
        for task in all_tasks_list:
            subs = task.get("subtasks", [])
            if isinstance(subs, list):
                total_subtasks_count += len(subs)
                subtask_status_counts.update(st.get("status", "pending").lower() for st in subs)
        completed_subtasks_count = subtask_status_counts.get("done", 0) + subtask_status_counts.get("completed", 0)
        subtask_completion_percentage = (completed_subtasks_count / total_subtasks_count * 100) if total_subtasks_count > 0 else 0

        if output_format == "json":
            tasks_for_json = []
            for task_item in filtered_tasks:
                task_copy = {k: v for k, v in task_item.items() if k != "details"}
                if "subtasks" in task_copy and isinstance(task_copy["subtasks"], list):
                    task_copy["subtasks"] = [{k_s: v_s for k_s, v_s in sub.items() if k_s != "details"} for sub in task_copy["subtasks"]]
                tasks_for_json.append(task_copy)
            
            return {
                "project_name": project_name,
                "tasks": tasks_for_json,
                "filter": status_filter or "all",
                "stats": {
                    "total_tasks": total_tasks_count,
                    "completed_tasks": completed_tasks_count,
                    "task_status_counts": dict(task_status_counts),
                    "task_completion_percentage": task_completion_percentage,
                    "subtasks": {
                        "total": total_subtasks_count,
                        "completed": completed_subtasks_count,
                        "status_counts": dict(subtask_status_counts),
                        "completion_percentage": subtask_completion_percentage,
                    }
                }
            }

        if not RICH_AVAILABLE and output_format == "rich":
            logger.warning("Rich library not available, falling back to text output.")
            output_format = "text"


        if output_format == "rich" and RICH_AVAILABLE:
            console = Console()
            layout = Layout(name="root")
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="dashboard", ratio=1),
                Layout(name="task_table", ratio=3),
                Layout(name="footer", size=3)
            )
            layout["header"].update(Panel(Text(project_name, justify="center", style="bold magenta")))

            # Dashboard panels
            task_prog_bar = ProgressBar(total=100, completed=task_completion_percentage, width=30)
            task_stats_text = f"Done: {completed_tasks_count}, In-Progress: {task_status_counts.get('in-progress',0)}, Pending: {task_status_counts.get('pending',0)}"
            task_panel = Panel(Text.assemble(Text("Tasks Progress: ", style="bold"), task_prog_bar, f" {task_completion_percentage:.0f}%\n{task_stats_text}"), title="[b]Overall Progress[/b]", border_style="blue")
            
            sub_panel_content = Text("No subtasks.")
            if total_subtasks_count > 0:
                sub_prog_bar = ProgressBar(total=100, completed=subtask_completion_percentage, width=30)
                sub_stats_text = f"Completed: {completed_subtasks_count}/{total_subtasks_count}"
                sub_panel_content = Text.assemble(Text("Subtasks Progress: ", style="bold"), sub_prog_bar, f" {subtask_completion_percentage:.0f}%\n{sub_stats_text}")
            subtask_panel = Panel(sub_panel_content, title="[b]Subtasks[/b]", border_style="green")
            
            # Dependency Panel (simplified)
            dep_panel = Panel("Next Task: N/A (to be implemented)", title="[b]Dependency & Next Task[/b]", border_style="yellow")
            
            layout["dashboard"].split_row(task_panel, subtask_panel, dep_panel)
            
            # Task Table
            table = Table(title=f"Tasks (Filter: {status_filter or 'All'})", show_lines=True)
            table.add_column("ID", style="dim", width=5)
            table.add_column("Title", style="bold cyan", max_width=40)
            table.add_column("Status", style="bold", width=12)
            table.add_column("Priority", width=10)
            table.add_column("Deps", max_width=25)
            table.add_column("Subs", width=5, justify="right")

            for task in filtered_tasks:
                task_id_str = str(task.get("id", "N/A"))
                title_str = _truncate(task.get("title", "N/A"), 37)
                status_text = Text(task.get("status", "pending"), style=_get_status_style_py(task.get("status")))
                priority_text = Text(task.get("priority", "medium"), style=_get_status_style_py(task.get("priority"))) # Color priority too
                deps_text = _format_dependencies_py(task.get("dependencies", []), all_tasks_list, for_rich_table=True)
                sub_count = len(task.get("subtasks",[])) if isinstance(task.get("subtasks"),list) else 0
                
                table.add_row(task_id_str, title_str, status_text, priority_text, deps_text, str(sub_count))

                if with_subtasks and isinstance(task.get("subtasks"), list) and task["subtasks"]:
                    for subtask in task["subtasks"]:
                        sub_id_str = f"  └─{task.get('id')}.{subtask.get('id', '?')}"
                        sub_title_str = _truncate(subtask.get("title", "N/A"), 34)
                        sub_status_text = Text(subtask.get("status", "pending"), style=_get_status_style_py(subtask.get("status")))
                        sub_priority_text = Text(subtask.get("priority", "-"), style=_get_status_style_py(subtask.get("priority")))
                        sub_deps_text = _format_dependencies_py(subtask.get("dependencies", []), all_tasks_list, for_rich_table=True, parent_task_id=task.get("id"), is_sub_dependency=True)
                        
                        table.add_row(Text(sub_id_str, style="dim"), sub_title_str, sub_status_text, sub_priority_text, sub_deps_text, "")
            
            layout["task_table"].update(table)
            layout["footer"].update(Panel(Text("Run `task-master next` to see suggested next task. `task-master help` for more.", justify="center", style="dim italic")))
            console.print(layout)
            return None


        # Fallback to Text Output (CLI) if Rich is not used/available
        print(f"\n--- {project_name} Dashboard ---")
        print(f"Tasks Progress: [{'#' * int(task_completion_percentage/10)}{'-' * (10 - int(task_completion_percentage/10))}] {task_completion_percentage:.0f}%")
        print(f"Done: {completed_tasks_count}, In-Progress: {task_status_counts.get('in-progress',0)}, Pending: {task_status_counts.get('pending',0)}")
        
        if total_subtasks_count > 0:
            print(f"Subtasks Progress: [{'#' * int(subtask_completion_percentage/10)}{'-' * (10 - int(subtask_completion_percentage/10))}] {subtask_completion_percentage:.0f}%")
            print(f"Completed: {completed_subtasks_count}/{total_subtasks_count}")
        
        print("\n--- Dependency Status & Next Task ---")
        print("Next Task: N/A (to be implemented)")

        if not filtered_tasks:
            print(f"\nNo tasks found{f' with status {status_filter}' if status_filter and status_filter.lower() != 'all' else ''}.")
            return None
            
        print("\n--- Task List ---")
        header = ["ID", "Title", "Status", "Priority", "Dependencies", "Subtasks"]
        print(f"{header[0]:<5} | {header[1]:<40} | {header[2]:<12} | {header[3]:<10} | {header[4]:<25} | {header[5]:<10}")
        print("-" * 110) # Adjusted for wider dep column

        for task in filtered_tasks:
            task_id_str = str(task.get("id", "N/A"))
            title_str = _truncate(task.get("title", "N/A"), 37)
            # For text, _get_status_style_py is not used as it returns Rich styles
            status_str = task.get("status", "pending") 
            priority_str = task.get("priority", "medium")
            deps_str = _format_dependencies_py(task.get("dependencies", []), all_tasks_list, for_rich_table=False)
            sub_count = len(task.get("subtasks",[])) if isinstance(task.get("subtasks"),list) else 0
            
            print(f"{task_id_str:<5} | {title_str:<40} | {status_str:<12} | {priority_str:<10} | {deps_str:<25} | {sub_count:<10}")

            if with_subtasks and isinstance(task.get("subtasks"), list) and task["subtasks"]:
                for subtask in task["subtasks"]:
                    sub_id_str = f"  └─{task.get('id')}.{subtask.get('id', '?')}"
                    sub_title_str = _truncate(subtask.get("title", "N/A"), 34)
                    sub_status_str = subtask.get("status", "pending")
                    sub_priority_str = subtask.get("priority", "-")
                    sub_deps_str = _format_dependencies_py(subtask.get("dependencies", []), all_tasks_list, for_rich_table=False, parent_task_id=task.get("id"), is_sub_dependency=True)
                    
                    print(f"{sub_id_str:<5} | {sub_title_str:<40} | {sub_status_str:<12} | {sub_priority_str:<10} | {sub_deps_str:<25} | {'-':<10}")
        
        print("-" * 110)
        if status_filter and status_filter.lower() != "all":
            print(f"\nFiltered by status: {status_filter}. Showing {len(filtered_tasks)} of {total_tasks_count} tasks.")

        print("\n--- Suggested Next Steps ---")
        print("1. Run `task-master next` ...") 
        return None

    except Exception as e:
        logger.error(f"Error listing tasks: {e}", exc_info=True)
        if output_format == "json":
            raise 
        else:
            print(f"An error occurred: {e}") 
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Determine a writable path for the dummy file, e.g., current working directory
    dummy_tasks_file = os.path.join(os.getcwd(), "test_list_tasks_main.json")

    dummy_data = {
        "metadata": {"project_name": "My Test Project"},
        "tasks": [
            {"id": 1, "title": "Setup project infrastructure and CI/CD pipelines", "status": "done", "dependencies": [], "priority": "high"},
            {"id": 2, "title": "Implement user authentication module with OAuth2 support", "status": "in-progress", "dependencies": [1], "priority": "high", 
             "subtasks": [
                 {"id": 1, "title": "Design auth schema", "status": "done", "dependencies": []},
                 {"id": 2, "title": "Implement OAuth2 client", "status": "pending", "dependencies": [1]}
             ]},
            {"id": 3, "title": "Develop API for core features (CRUD ops)", "status": "pending", "dependencies": [2], "priority": "medium"},
            {"id": 4, "title": "Design database schema", "status": "blocked", "dependencies": [1], "priority": "high"},
            {"id": 5, "title": "Write tests for backend", "status": "deferred", "dependencies": [3], "priority": "low"}
        ]
    }
    with open(dummy_tasks_file, "w", encoding="utf-8") as f:
        json.dump(dummy_data, f, indent=2)

    output_pref: Literal["text", "json", "rich"] = "rich" if RICH_AVAILABLE else "text"

    print(f"--- Test: list_tasks_py ({output_pref} output, all tasks) ---")
    list_tasks_py(dummy_tasks_file, output_format=output_pref)

    print(f"\n\n--- Test: list_tasks_py ({output_pref} output, status 'pending') ---")
    list_tasks_py(dummy_tasks_file, status_filter="pending", output_format=output_pref)
    
    print(f"\n\n--- Test: list_tasks_py ({output_pref} output, with_subtasks) ---")
    list_tasks_py(dummy_tasks_file, with_subtasks=True, output_format=output_pref)

    print("\n\n--- Test: list_tasks_py (json output, status 'in-progress') ---")
    json_output = list_tasks_py(dummy_tasks_file, status_filter="in-progress", output_format="json")
    if json_output:
        # Basic print for CI/non-Rich environments, or use Rich's JSON pretty print if available
        if RICH_AVAILABLE:
            Console().print_json(data=json_output)
        else:
            print(json.dumps(json_output, indent=2))
            
        assert len(json_output.get("tasks",[])) == 1, "JSON output filtering failed"
        assert json_output["tasks"][0]["id"] == 2, "Incorrect task ID in JSON output"
        assert "details" not in json_output["tasks"][0], "Details field should be omitted in JSON tasks"
        if json_output["tasks"][0].get("subtasks"):
             assert "details" not in json_output["tasks"][0]["subtasks"][0], "Details field should be omitted in JSON subtasks"
        logger.info("JSON output test assertions passed.")


    # Clean up
    if os.path.exists(dummy_tasks_file):
        os.remove(dummy_tasks_file)
    print("\n\nList tasks tests complete.")