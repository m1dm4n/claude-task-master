import json
import os
import pathlib
import logging
from typing import Any, Dict, List, Literal, Optional, Union

# Assuming utils.py might exist in python_src for read_json_file, write_json_file, find_task_by_id_py
# from ..utils import read_json_file, write_json_file, find_task_by_id_py 
# For now, including simplified versions or assuming they are passed if not central.

# Placeholders, to be implemented/ported later
# from ..dependency_manager import validate_task_dependencies_py 
# from .generate_task_files import generate_task_files_py 

logger = logging.getLogger(__name__)

VALID_TASK_STATUSES = ["pending", "in-progress", "done", "deferred", "blocked", "review"]

# --- Simplified JSON read/write (can be replaced by a common util) ---
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

def _write_json_file(file_path: str, data: Dict[str, Any]) -> bool:
    try:
        # Ensure parent directory exists
        parent_dir = pathlib.Path(file_path).parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {parent_dir}")

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error writing JSON to file {file_path}: {e}")
        return False

def _find_task_by_id(tasks_list: List[Dict[str, Any]], task_id_str: str) -> Optional[Dict[str, Any]]:
    if not tasks_list: # Handle empty or None tasks_list
        return None

    if "." in task_id_str: # Subtask ID like "parent.sub"
        parent_id_str, sub_id_str = task_id_str.split(".", 1)
        try:
            parent_id = int(parent_id_str)
            sub_id = int(sub_id_str) # Assuming subtask IDs are integers as per PrdSingleTask (though not explicitly defined for subtasks there)
        except ValueError:
            logger.warning(f"Invalid subtask ID format (must be int.int): {task_id_str}")
            return None
        
        parent_task = next((task for task in tasks_list if isinstance(task, dict) and task.get("id") == parent_id), None)
        if parent_task and isinstance(parent_task.get("subtasks"), list):
            return next((st for st in parent_task["subtasks"] if isinstance(st, dict) and st.get("id") == sub_id), None)
        return None
    else: # Main task ID
        try:
            task_id = int(task_id_str)
            return next((task for task in tasks_list if isinstance(task, dict) and task.get("id") == task_id), None)
        except ValueError:
            logger.warning(f"Invalid task ID format (must be int): {task_id_str}")
            return None


def _update_single_task_status_py(
    task_id_str: str, 
    new_status: str, 
    tasks_data_obj: Dict[str, Any], 
) -> bool:
    """
    Updates the status of a single task or subtask.
    Modifies tasks_data_obj (the entire JSON object) directly.
    Returns True if updated, False otherwise.
    """
    all_tasks_list = tasks_data_obj.get("tasks", [])
    if not isinstance(all_tasks_list, list): # Ensure all_tasks_list is actually a list
        logger.error("Tasks data is not a list. Cannot update status.")
        return False
        
    task_to_update = _find_task_by_id(all_tasks_list, task_id_str)

    if not task_to_update:
        logger.warning(f"Task or subtask with ID '{task_id_str}' not found.")
        return False
    
    if not isinstance(task_to_update, dict): # Should be caught by _find_task_by_id returning None, but good practice
        logger.warning(f"Found item for ID '{task_id_str}' is not a dictionary. Cannot update status.")
        return False

    old_status = task_to_update.get("status", "unknown")
    task_to_update["status"] = new_status
    logger.info(f"Updated status of task/subtask '{task_id_str}' from '{old_status}' to '{new_status}'.")

    # If a parent task is marked "done", all its subtasks should be marked "done"
    if "." not in task_id_str and new_status == "done": # It's a parent task
        if "subtasks" in task_to_update and isinstance(task_to_update["subtasks"], list):
            for subtask in task_to_update["subtasks"]:
                if isinstance(subtask, dict) and subtask.get("status") != "done":
                    subtask["status"] = "done"
                    logger.info(f"  Subtask '{task_id_str}.{subtask.get('id', 'N/A')}' also marked 'done'.")
    
    # If a subtask is moved out of "done", its parent task should not be "done"
    if "." in task_id_str and old_status == "done" and new_status != "done":
        parent_id_str, _ = task_id_str.split(".", 1)
        parent_task = _find_task_by_id(all_tasks_list, parent_id_str)
        if parent_task and isinstance(parent_task, dict) and parent_task.get("status") == "done":
            parent_task["status"] = "in-progress" # Or "pending", depending on desired logic
            logger.info(f"  Parent task '{parent_id_str}' status changed from 'done' to 'in-progress' because subtask '{task_id_str}' moved out of 'done'.")
            
    return True


def set_task_status_py(
    tasks_path: str,
    task_id_input: str, # Comma-separated IDs
    new_status: str,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    options = options or {} # Not used yet, but good for future CLI/MCP options

    if new_status not in VALID_TASK_STATUSES:
        raise ValueError(f"Invalid status value: '{new_status}'. Must be one of: {', '.join(VALID_TASK_STATUSES)}")

    logger.info(f"Attempting to set status to '{new_status}' for task(s): {task_id_input} in file {tasks_path}")

    tasks_data_obj = _read_json_file(tasks_path)
    if not tasks_data_obj:
        raise FileNotFoundError(f"Tasks file {tasks_path} not found or is empty/invalid JSON.")
    if not isinstance(tasks_data_obj.get("tasks"), list):
         raise ValueError(f"Tasks data in {tasks_path} is malformed: 'tasks' key is not a list or is missing.")


    task_ids_to_process = [tid.strip() for tid in task_id_input.split(",") if tid.strip()]
    if not task_ids_to_process:
        raise ValueError("No task IDs provided for status update.")
        
    updated_task_ids_map: Dict[str, str] = {} # Stores original_id_str: new_status

    all_tasks_list_ref = tasks_data_obj["tasks"] # Keep a direct reference to the list of tasks

    for task_id_str_to_process in task_ids_to_process:
        if _update_single_task_status_py(task_id_str_to_process, new_status, tasks_data_obj):
            updated_task_ids_map[task_id_str_to_process] = new_status
    
    # Second pass: if a parent task has all subtasks "done", mark parent "done"
    # Also, if a parent is not "done" but was previously, and a subtask became not "done", this is handled in _update_single_task_status_py
    # This loop ensures parents become "done" if all subtasks are now "done".
    if isinstance(all_tasks_list_ref, list): # Ensure it's still a list
        for task_dict in all_tasks_list_ref:
            if isinstance(task_dict, dict) and task_dict.get("status") != "done" and \
               isinstance(task_dict.get("subtasks"), list) and task_dict["subtasks"]:
                
                all_subtasks_are_done = True
                for sub_t in task_dict["subtasks"]:
                    if not isinstance(sub_t, dict) or sub_t.get("status") != "done":
                        all_subtasks_are_done = False
                        break
                
                if all_subtasks_are_done:
                    task_dict["status"] = "done"
                    parent_task_id_str = str(task_dict.get('id', 'N/A'))
                    logger.info(f"Parent task '{parent_task_id_str}' automatically marked 'done' as all its subtasks are now 'done'.")
                    # Avoid adding if it was one of the explicitly updated tasks and already set to done
                    if parent_task_id_str not in updated_task_ids_map or updated_task_ids_map[parent_task_id_str] != "done":
                         updated_task_ids_map[parent_task_id_str] = "done"


    if not _write_json_file(tasks_path, tasks_data_obj):
        # Attempt to restore original data if write fails? Complex, for now, just error out.
        raise IOError(f"Failed to write updated tasks to {tasks_path}")

    logger.info(f"Successfully updated statuses in {tasks_path}. Touched {len(updated_task_ids_map)} tasks/subtasks directly or indirectly.")

    # --- Placeholders for further actions ---
    # logger.info("Skipping dependency validation (to be implemented via dependency_manager.py).")
    # if isinstance(tasks_data_obj.get("tasks"), list):
    #     validate_task_dependencies_py(tasks_data_obj["tasks"]) 

    # logger.info("Skipping regeneration of task files (to be implemented via generate_task_files.py).")
    # output_directory_for_tasks = str(pathlib.Path(tasks_path).parent)
    # generate_task_files_py(tasks_path, output_directory_for_tasks, options=options) # Assuming generate_task_files is not async

    return {
        "success": True,
        "updated_task_details": [{"id": tid, "status": status} for tid, status in updated_task_ids_map.items()]
    }


if __name__ == "__main__":
    # Setup basic logging for the test
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Starting set_task_status_py test...")
    
    test_project_root = os.getcwd()
    dummy_tasks_file = os.path.join(test_project_root, "test_set_status_tasks.json")
    
    # Initial dummy data for tasks.json
    initial_dummy_data = {
        "tasks": [
            {"id": 1, "title": "Task 1 Parent", "status": "pending", "dependencies": [], "subtasks": [
                {"id": 1, "title": "Subtask 1.1", "status": "pending", "dependencies": []},
                {"id": 2, "title": "Subtask 1.2", "status": "pending", "dependencies": []},
            ]},
            {"id": 2, "title": "Task 2 Standalone", "status": "in-progress", "dependencies": [1]},
            {"id": 3, "title": "Task 3 For Multi-Update", "status": "pending", "dependencies": []}
        ]
    }

    # Helper to reset the dummy file for each test case
    def reset_dummy_file():
        with open(dummy_tasks_file, "w", encoding="utf-8") as f:
            json.dump(initial_dummy_data, f, indent=2)
        logger.debug(f"Reset dummy file: {dummy_tasks_file}")

    try:
        reset_dummy_file()
        print("\n--- Test 1: Set Task 2 to 'done' ---")
        result1 = set_task_status_py(dummy_tasks_file, "2", "done")
        print(f"Result 1: {result1}")
        data_after_1 = _read_json_file(dummy_tasks_file)
        assert data_after_1 is not None, "File read error after Test 1"
        assert _find_task_by_id(data_after_1["tasks"], "2")["status"] == "done" # type: ignore
        logger.info("Test 1 PASSED: Task 2 status is 'done'.")

        reset_dummy_file()
        print("\n--- Test 2: Set Subtask 1.1 to 'done' ---")
        result2 = set_task_status_py(dummy_tasks_file, "1.1", "done")
        print(f"Result 2: {result2}")
        data_after_2 = _read_json_file(dummy_tasks_file)
        assert data_after_2 is not None, "File read error after Test 2"
        assert _find_task_by_id(data_after_2["tasks"], "1.1")["status"] == "done" # type: ignore
        assert _find_task_by_id(data_after_2["tasks"], "1")["status"] == "pending" # Parent should not be done yet # type: ignore
        logger.info("Test 2 PASSED: Subtask 1.1 is 'done', Parent 1 is 'pending'.")

        reset_dummy_file()
        # Manually set 1.1 to done first for this test case
        temp_data_for_test3 = _read_json_file(dummy_tasks_file)
        assert temp_data_for_test3 is not None
        _find_task_by_id(temp_data_for_test3["tasks"], "1.1")["status"] = "done" # type: ignore
        _write_json_file(dummy_tasks_file, temp_data_for_test3)
        
        print("\n--- Test 3: Set Subtask 1.2 to 'done' (should make Parent 1 'done') ---")
        result3 = set_task_status_py(dummy_tasks_file, "1.2", "done")
        print(f"Result 3: {result3}")
        data_after_3 = _read_json_file(dummy_tasks_file)
        assert data_after_3 is not None, "File read error after Test 3"
        assert _find_task_by_id(data_after_3["tasks"], "1.2")["status"] == "done" # type: ignore
        assert _find_task_by_id(data_after_3["tasks"], "1")["status"] == "done" # Parent should now be done # type: ignore
        logger.info("Test 3 PASSED: Subtask 1.2 is 'done', Parent 1 is also 'done'.")

        reset_dummy_file()
        # Manually set Parent 1 and its subtasks to 'done' for this test case
        temp_data_for_test4 = _read_json_file(dummy_tasks_file)
        assert temp_data_for_test4 is not None
        _find_task_by_id(temp_data_for_test4["tasks"], "1")["status"] = "done" # type: ignore
        _find_task_by_id(temp_data_for_test4["tasks"], "1.1")["status"] = "done" # type: ignore
        _find_task_by_id(temp_data_for_test4["tasks"], "1.2")["status"] = "done" # type: ignore
        _write_json_file(dummy_tasks_file, temp_data_for_test4)

        print("\n--- Test 4: Set Subtask 1.1 (from 'done') to 'in-progress' (should make Parent 1 'in-progress') ---")
        result4 = set_task_status_py(dummy_tasks_file, "1.1", "in-progress")
        print(f"Result 4: {result4}")
        data_after_4 = _read_json_file(dummy_tasks_file)
        assert data_after_4 is not None, "File read error after Test 4"
        assert _find_task_by_id(data_after_4["tasks"], "1.1")["status"] == "in-progress" # type: ignore
        assert _find_task_by_id(data_after_4["tasks"], "1")["status"] == "in-progress" # Parent should now be in-progress # type: ignore
        logger.info("Test 4 PASSED: Subtask 1.1 is 'in-progress', Parent 1 is also 'in-progress'.")
        
        reset_dummy_file()
        print("\n--- Test 5: Set multiple tasks '3, 1.1' to 'blocked' ---")
        # Parent 1 is initially 'pending', Subtask 1.1 is 'pending'
        result5 = set_task_status_py(dummy_tasks_file, "3,1.1", "blocked")
        print(f"Result 5: {result5}")
        data_after_5 = _read_json_file(dummy_tasks_file)
        assert data_after_5 is not None, "File read error after Test 5"
        assert _find_task_by_id(data_after_5["tasks"], "3")["status"] == "blocked" # type: ignore
        assert _find_task_by_id(data_after_5["tasks"], "1.1")["status"] == "blocked" # type: ignore
        # Parent 1 status should remain 'pending' as subtask 1.2 is still 'pending'
        assert _find_task_by_id(data_after_5["tasks"], "1")["status"] == "pending" # type: ignore
        logger.info("Test 5 PASSED: Task 3 and Subtask 1.1 are 'blocked'. Parent 1 remains 'pending'.")

        reset_dummy_file()
        print("\n--- Test 6: Set non-existent task '99' to 'done' ---")
        result6 = set_task_status_py(dummy_tasks_file, "99", "done")
        print(f"Result 6: {result6}") # Should indicate 0 updated tasks
        assert len(result6.get("updated_task_details", [])) == 0, "No tasks should be updated for non-existent ID."
        logger.info("Test 6 PASSED: Attempt to update non-existent task ID '99' handled gracefully.")


    except Exception as e:
        logger.error(f"Error during set_task_status_py test: {e}", exc_info=True)
    finally:
        if os.path.exists(dummy_tasks_file):
            os.remove(dummy_tasks_file)
            logger.info(f"Removed dummy tasks file: {dummy_tasks_file}")
        logger.info("Test cleanup complete.")
```
