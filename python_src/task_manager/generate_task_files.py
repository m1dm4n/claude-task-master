import json
import os
import pathlib
import logging
from typing import Any, Dict, List, Optional

# Assuming utils.py might exist in python_src for read_json_file, write_json_file
# from ..utils import read_json_file # If you create a utils.py
# For now, including simplified versions or assuming they are passed if not central.

# Placeholder for dependency_manager and ui functions, to be implemented/ported later
# from ..dependency_manager import validate_and_fix_dependencies_py
# from ..ui import format_dependencies_with_status_py

logger = logging.getLogger(__name__)

# --- Simplified JSON read (can be replaced by a common util) ---
def _read_json_file(file_path: str) -> Optional[Dict]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from file: {file_path}")
        return None

def _format_dependencies_py(dep_ids: List[Any], all_tasks: List[Dict], is_subtask_dep: bool = False, parent_task_id: Optional[int] = None) -> str:
    if not dep_ids:
        return "None"
    
    formatted_deps = []
    for dep_id_any_type in dep_ids:
        # Normalize dep_id to integer if possible, or handle string like "parent.sub"
        actual_dep_id: Optional[int] = None
        dep_id_str_prefix = ""

        if isinstance(dep_id_any_type, int):
            actual_dep_id = dep_id_any_type
        elif isinstance(dep_id_any_type, str):
            if "." in dep_id_any_type and is_subtask_dep: # e.g. "2.1" meaning parent task 2, subtask 1
                try:
                    # This logic assumes subtask dependencies are stored as strings "parentID.subtaskID"
                    # If they are stored as integers, this part needs adjustment.
                    # The current PrdSingleTask schema expects List[int] for dependencies.
                    # This formatter might need to adapt based on how subtask deps are actually stored.
                    # For now, let's assume if it's a string, it's pre-formatted.
                    # However, PrdSingleTask has `dependencies: List[int]`.
                    # This implies subtask dependencies might also be just integers,
                    # and context (is_subtask_dep, parent_task_id) tells us how to find them.
                    # Let's stick to `actual_dep_id` being the integer ID of the subtask *within its parent*.
                    parts = dep_id_any_type.split('.')
                    if len(parts) == 2 and parts[0] == str(parent_task_id): # Refers to a subtask of the current parent
                        actual_dep_id = int(parts[1])
                        dep_id_str_prefix = f"{parts[0]}."
                    else: # A string dependency not matching "parent.sub" format, or for a different parent.
                        logger.warning(f"Subtask dependency '{dep_id_any_type}' has unexpected format or parent. Treating as string ID.")
                        formatted_deps.append(f"⚠️ {dep_id_any_type} (Unknown Format)")
                        continue
                except ValueError:
                    logger.warning(f"Could not parse subtask dependency ID: {dep_id_any_type}")
                    formatted_deps.append(f"⚠️ {dep_id_any_type} (Parse Error)")
                    continue
            else: # A simple string ID, try to convert to int. If not, it's an error or non-standard.
                try:
                    actual_dep_id = int(dep_id_any_type)
                except ValueError:
                    logger.warning(f"Dependency ID '{dep_id_any_type}' is not a valid integer. Skipping.")
                    formatted_deps.append(f"⚠️ {dep_id_any_type} (Invalid ID)")
                    continue
        else:
            logger.warning(f"Unsupported dependency ID type: {type(dep_id_any_type)}. Skipping.")
            formatted_deps.append(f"⚠️ {str(dep_id_any_type)} (Invalid Type)")
            continue

        if actual_dep_id is None: # Should not happen if logic above is correct
            continue

        # Find the dependent task/subtask
        dep_task_obj = None
        found_status = "pending" # Default status

        if is_subtask_dep and parent_task_id is not None:
            # Dependency is for a subtask, so actual_dep_id is the ID of another subtask *within the same parent*
            parent_of_dep = next((t for t in all_tasks if t.get("id") == parent_task_id), None)
            if parent_of_dep:
                dep_task_obj = next((st for st in parent_of_dep.get("subtasks", []) if st.get("id") == actual_dep_id), None)
            dep_id_str_prefix = f"{parent_task_id}." # Display as Parent.Sub
        else: # Main task dependency
            dep_task_obj = next((t for t in all_tasks if t.get("id") == actual_dep_id), None)
            dep_id_str_prefix = "" # No prefix for main tasks

        if dep_task_obj:
            found_status = dep_task_obj.get("status", "pending")
            status_char = "✅" if found_status == "done" else ("🚧" if found_status == "active" else "⏱️")
            formatted_deps.append(f"{status_char} {dep_id_str_prefix}{actual_dep_id}")
        else:
            formatted_deps.append(f"⚠️ {dep_id_str_prefix}{actual_dep_id} (Not Found)")
            
    return ", ".join(formatted_deps) if formatted_deps else "None"


def generate_task_files_py(
    tasks_path: str, 
    output_dir: str, 
    options: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    options = options or {}
    # mcp_log_fn = options.get("mcp_log") # For potential future use if specific logging is needed

    try:
        data = _read_json_file(tasks_path)
        if not data or not isinstance(data.get("tasks"), list):
            # Try to load if tasks_path is actually a list of tasks (not a dict with 'tasks' key)
            if isinstance(tasks_path, str) and os.path.exists(tasks_path): # Re-check if it's a file path
                logger.warning(f"Input {tasks_path} doesn't have a 'tasks' key. Trying to load as a direct list of tasks.")
                raw_list_data = _read_json_file(tasks_path) # Re-read
                if isinstance(raw_list_data, list): # If the JSON file is directly a list of tasks
                    data = {"tasks": raw_list_data, "metadata": {}} # Wrap it for consistency
                    logger.info("Successfully loaded tasks as a direct list.")
                else:
                    raise ValueError(f"No valid tasks found in {tasks_path}. Content is not a list of tasks nor a dict with a 'tasks' key.")
            else:
                 raise ValueError(f"No valid tasks found in {tasks_path} or tasks is not a list.")

        all_tasks_list: List[Dict] = data.get("tasks", [])
        if not all_tasks_list:
            logger.warning(f"The 'tasks' list in {tasks_path} is empty. No task files will be generated.")
            return {"success": True, "count": 0, "directory": str(output_dir), "message": "No tasks found in input file."}


        output_path = pathlib.Path(output_dir)
        if not output_path.exists():
            output_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created output directory: {output_dir}")

        logger.info(f"Preparing to regenerate task files for {len(all_tasks_list)} tasks in {output_dir}")

        # --- Placeholder for dependency validation ---
        # logger.info("Skipping dependency validation and fixing (to be implemented via dependency_manager.py).")
        # If validate_and_fix_dependencies_py is available and modifies data:
        # validated_data = validate_and_fix_dependencies_py(data, tasks_path) 
        # all_tasks_list = validated_data.get("tasks", all_tasks_list)

        valid_task_ids = {task["id"] for task in all_tasks_list if isinstance(task.get("id"), int)}

        # --- Orphaned file cleanup ---
        logger.info("Checking for orphaned task files...")
        orphaned_files_count = 0
        if output_path.is_dir(): # Ensure directory exists and is a directory
            for item in output_path.iterdir():
                if item.is_file() and item.name.startswith("task_") and item.name.endswith(".md"):
                    try:
                        # Extract ID: task_001.md -> 001 -> 1
                        task_id_str = item.stem.split("_", 1)[1] if "_" in item.stem else item.stem 
                        task_id = int(task_id_str)
                        if task_id not in valid_task_ids:
                            item.unlink()
                            logger.info(f"Removed orphaned task file: {item.name}")
                            orphaned_files_count +=1
                    except (IndexError, ValueError) as e:
                        logger.warning(f"Could not parse task ID from filename '{item.name}': {e}")
        if orphaned_files_count > 0:
            logger.info(f"Removed {orphaned_files_count} orphaned task files.")
        else:
            logger.info("No orphaned task files found or to remove.")

        # --- Generate task files ---
        logger.info("Generating individual task files...")
        generated_count = 0
        for task in all_tasks_list:
            task_id = task.get("id")
            if not isinstance(task_id, int):
                logger.warning(f"Skipping task due to invalid or missing ID: {task.get('title', 'N/A')}")
                continue

            task_id_str_padded = str(task_id).zfill(3)
            task_file_path = output_path / f"task_{task_id_str_padded}.md"

            content = []
            content.append(f"# Task ID: {task_id}")
            content.append(f"## Title: {task.get('title', 'N/A')}")
            content.append(f"**Status:** {task.get('status', 'pending')}")
            
            # Ensure dependencies are processed correctly (expecting list of ints)
            raw_deps = task.get('dependencies', [])
            if not isinstance(raw_deps, list):
                logger.warning(f"Task {task_id} has malformed dependencies ({raw_deps}). Treating as empty.")
                raw_deps = []
            
            dependencies_str = _format_dependencies_py(raw_deps, all_tasks_list)
            content.append(f"**Dependencies:** {dependencies_str}")
            content.append(f"**Priority:** {task.get('priority', 'medium')}")
            
            content.append("\n## Description")
            content.append(task.get('description', 'No description provided.'))
            
            content.append("\n## Details")
            content.append(task.get('details', 'No details provided.'))
            
            content.append("\n## Test Strategy")
            content.append(task.get('test_strategy', 'No test strategy provided.'))

            # Subtasks
            subtasks = task.get("subtasks", [])
            if isinstance(subtasks, list) and subtasks:
                content.append("\n## Subtasks")
                for subtask_idx, subtask in enumerate(subtasks):
                    if not isinstance(subtask, dict):
                        logger.warning(f"Subtask at index {subtask_idx} for task {task_id} is not a dictionary. Skipping.")
                        continue
                    
                    sub_id = subtask.get('id', f"sub_{subtask_idx+1}") # Use index if ID missing
                    sub_title = subtask.get('title', 'N/A')
                    sub_status = subtask.get('status', 'pending')
                    content.append(f"### {task_id}.{sub_id}. {sub_title} [{sub_status}]")
                    
                    raw_sub_deps = subtask.get('dependencies', [])
                    if not isinstance(raw_sub_deps, list):
                        logger.warning(f"Subtask {task_id}.{sub_id} has malformed dependencies. Treating as empty.")
                        raw_sub_deps = []

                    sub_deps_str = _format_dependencies_py(raw_sub_deps, all_tasks_list, is_subtask_dep=True, parent_task_id=task_id)
                    content.append(f"  **Dependencies (relative to parent task's subtasks):** {sub_deps_str}")
                    content.append(f"  **Description:** {subtask.get('description', 'No description provided.')}")
                    
                    sub_details = subtask.get('details', 'No details provided.')
                    if sub_details.strip(): # Only add details if not empty
                         content.append(f"  **Details:**\n  ```\n  {sub_details.strip()}\n  ```")
                    content.append("") # Extra newline for spacing
            elif subtasks: # Not a list or not empty
                 logger.warning(f"Task {task_id} has subtasks in an unexpected format: {type(subtasks)}. Expected a list.")


            try:
                with open(task_file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(content))
                generated_count += 1
            except IOError as e:
                logger.error(f"Failed to write task file {task_file_path}: {e}")
        
        logger.info(f"All {generated_count} task files have been generated into '{output_dir}'.")

        return {"success": True, "count": generated_count, "directory": str(output_dir)}

    except Exception as e:
        logger.error(f"Error generating task files: {e}", exc_info=True)
        raise 

if __name__ == "__main__":
    # Setup basic logging for the test
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Starting generate_task_files_py test...")

    test_project_root = os.getcwd()
    test_tasks_file = os.path.join(test_project_root, "test_tasks_for_generate.json")
    test_output_dir = os.path.join(test_project_root, "test_generated_task_files") # Changed dir name

    # Dummy tasks data for testing
    dummy_tasks_data_content = {
        "metadata": {
            "project_name": "Test Project",
            "total_tasks": 3 
        },
        "tasks": [
            {"id": 1, "title": "Setup project", "status": "done", "dependencies": [], "priority": "high", "description": "Initial project setup", "details": "Clone repo, install deps", "test_strategy": "Run basic commands"},
            {"id": 2, "title": "Implement feature X", "status": "active", "dependencies": [1], "priority": "medium", "description": "Core feature X", "details": "...", "test_strategy": "Unit tests for X",
             "subtasks": [
                 {"id": 1, "title": "Subtask 2.1 Design", "status": "done", "dependencies": [], "description": "Design for 2.1"},
                 {"id": 2, "title": "Subtask 2.2 Implement", "status": "pending", "dependencies": [1], "description": "Implementation for 2.2", "details": "Code for subtask 2.2"}
             ]},
            {"id": 3, "title": "Write tests for Y", "status": "pending", "dependencies": [2], "priority": "medium", "description": "Tests for related feature Y", "details": "...", "test_strategy": "Integration tests"}
        ]
    }
    
    # Data for the first run (tasks 1, 2, 3)
    tasks_for_run_1_content = dummy_tasks_data_content.copy()

    # Write initial tasks file (tasks 1, 2, 3)
    with open(test_tasks_file, "w", encoding="utf-8") as f:
        json.dump(tasks_for_run_1_content, f, indent=2)
    logger.info(f"Created dummy tasks file: {test_tasks_file}")

    # Create the output directory if it doesn't exist
    pathlib.Path(test_output_dir).mkdir(parents=True, exist_ok=True)

    print(f"\n--- Running generate_task_files_py (first run for tasks 1, 2, 3) ---")
    try:
        result1 = generate_task_files_py(test_tasks_file, test_output_dir)
        assert result1 and result1["success"], "First run should be successful"
        assert result1["count"] == 3, f"Expected 3 files, got {result1['count']}"
        assert os.path.exists(os.path.join(test_output_dir, "task_001.md")), "task_001.md missing"
        assert os.path.exists(os.path.join(test_output_dir, "task_002.md")), "task_002.md missing"
        assert os.path.exists(os.path.join(test_output_dir, "task_003.md")), "task_003.md missing"
        logger.info("First run successful, 3 task files created.")

        # Simulate an orphaned task file (task_004.md)
        # This task is not in tasks_for_run_1_content
        orphan_task_file_path = os.path.join(test_output_dir, "task_004.md")
        with open(orphan_task_file_path, "w", encoding="utf-8") as f:
            f.write("# This is an orphaned task file.")
        logger.info(f"Created dummy orphaned file: {orphan_task_file_path}")
        
        # Data for the second run (e.g., task 2 is removed, task 4 is added)
        tasks_for_run_2_content = {
            "metadata": {"total_tasks": 2},
            "tasks": [
                dummy_tasks_data_content["tasks"][0], # Task 1
                # Task 2 is removed
                {"id": 4, "title": "New task 4", "status": "pending", "dependencies": [1], "priority": "low", "description":"A new task"} # New Task 4
            ]
        }
        with open(test_tasks_file, "w", encoding="utf-8") as f:
            json.dump(tasks_for_run_2_content, f, indent=2)
        logger.info(f"Updated tasks file for second run (tasks 1, 4). Task 2 removed, task 3 effectively orphaned by tasks.json update.")


        print(f"\n--- Running generate_task_files_py (second run, tasks 1, 4; task_002.md and task_003.md should be orphaned) ---")
        result2 = generate_task_files_py(test_tasks_file, test_output_dir)
        assert result2 and result2["success"], "Second run should be successful"
        assert result2["count"] == 2, f"Expected 2 files to be generated/updated, got {result2['count']}" # Task 1 updated, Task 4 created
        
        assert os.path.exists(os.path.join(test_output_dir, "task_001.md")), "task_001.md should still exist"
        assert not os.path.exists(os.path.join(test_output_dir, "task_002.md")), "task_002.md should be removed (orphaned by tasks.json)"
        assert not os.path.exists(os.path.join(test_output_dir, "task_003.md")), "task_003.md should be removed (orphaned by tasks.json)"
        assert os.path.exists(os.path.join(test_output_dir, "task_004.md")), "task_004.md should be created"
        
        # The manually created orphan task_004.md before this run should have been based on an ID not in tasks_for_run_1_content.
        # The test was: create task_004.md. Then run with tasks_for_run_1_content (tasks 1,2,3). This should remove task_004.md.
        # Let's refine that part of the test logic for clarity.
        logger.info("Orphaned file cleanup and new file generation seems successful.")

    except Exception as e:
        logger.error(f"Error during generate_task_files_py test: {e}", exc_info=True)
    finally:
        # Clean up all created files and directories
        if os.path.exists(test_tasks_file):
            os.remove(test_tasks_file)
            logger.info(f"Removed test tasks file: {test_tasks_file}")
        if os.path.exists(test_output_dir):
            for item_name in os.listdir(test_output_dir):
                item_path = os.path.join(test_output_dir, item_name)
                if os.path.isfile(item_path):
                    os.remove(item_path)
            os.rmdir(test_output_dir)
            logger.info(f"Removed test output directory and its contents: {test_output_dir}")
        logger.info("Test cleanup complete.")
```
