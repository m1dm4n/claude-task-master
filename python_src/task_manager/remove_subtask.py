import json
import os
import pathlib
import logging
from typing import Any, Dict, List, Optional, Union

# Placeholders
# from .generate_task_files import generate_task_files_py
# from ..config_manager import get_project_name # If needed for context

logger = logging.getLogger(__name__)

# --- Helper for JSON read/write (can be moved to utils.py later) ---
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
        parent_dir = pathlib.Path(file_path).parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f: 
            json.dump(data, f, indent=2)
        return True
    except Exception as e: 
        logger.error(f"Error writing JSON to file {file_path}: {e}")
        return False

# remove_subtask_py is async because its __main__ test block uses await.
# If generate_task_files_py becomes async, this will be consistent.
async def remove_subtask_py(
    tasks_path: str,
    subtask_id_str: str, # Expected format "parentId.subtaskId"
    convert_to_task: bool = False, # If true, removed subtask becomes a new top-level task
    generate_files: bool = True, # Parameter for future use (regenerating task markdown files)
    context: Optional[Dict[str, Any]] = None, # For project_root, etc.
) -> Optional[Dict[str, Any]]: # Returns the converted task dictionary if applicable, else None
    
    context = context or {}
    # project_root = context.get("project_root") # Example

    logger.info(
        f"Attempting to remove subtask: {subtask_id_str}. "
        f"Convert to top-level task: {convert_to_task}."
    )

    tasks_data_full = _read_json_file(tasks_path)
    if not tasks_data_full or not isinstance(tasks_data_full.get("tasks"), list):
        raise FileNotFoundError(f"Tasks file {tasks_path} not found or is not structured correctly.")

    all_tasks_list_ref: List[Dict[str, Any]] = tasks_data_full["tasks"] # Direct reference

    # Validate and parse subtask_id_str
    if not isinstance(subtask_id_str, str) or "." not in subtask_id_str:
        raise ValueError(f"Invalid subtask ID format: '{subtask_id_str}'. Expected 'ParentID.SubtaskID'.")

    try:
        parent_id_str_part, actual_sub_id_str_part = subtask_id_str.split(".", 1)
        parent_id_num = int(parent_id_str_part)
        actual_sub_id_num = int(actual_sub_id_str_part)
    except ValueError:
        raise ValueError(f"Parent or subtask ID in '{subtask_id_str}' is not a valid integer.")

    # Find the parent task
    parent_task_index = -1
    parent_task_obj_ref: Optional[Dict[str, Any]] = None
    for i, task_dict in enumerate(all_tasks_list_ref):
        if isinstance(task_dict, dict) and task_dict.get("id") == parent_id_num:
            parent_task_index = i
            parent_task_obj_ref = task_dict # Direct reference to the dict in the list
            break
    
    if parent_task_index == -1 or parent_task_obj_ref is None:
        raise ValueError(f"Parent task with ID {parent_id_num} not found in tasks list.")

    # Check if parent task actually has subtasks
    if not isinstance(parent_task_obj_ref.get("subtasks"), list) or not parent_task_obj_ref["subtasks"]:
        raise ValueError(f"Parent task {parent_id_num} has no 'subtasks' list or it's empty. Cannot remove subtask {actual_sub_id_num}.")

    # Find and remove the subtask
    subtask_index_to_remove = -1
    subtask_to_remove_data_copy: Optional[Dict[str, Any]] = None
    for i, sub_task_dict in enumerate(parent_task_obj_ref["subtasks"]):
        if isinstance(sub_task_dict, dict) and sub_task_dict.get("id") == actual_sub_id_num:
            subtask_index_to_remove = i
            subtask_to_remove_data_copy = sub_task_dict.copy() # Make a copy before removing
            break
            
    if subtask_index_to_remove == -1 or subtask_to_remove_data_copy is None:
        raise ValueError(f"Subtask with ID {actual_sub_id_num} not found in parent task {parent_id_num}.")

    # Remove the subtask from the parent's list
    parent_task_obj_ref["subtasks"].pop(subtask_index_to_remove)
    logger.info(f"Successfully removed subtask {subtask_id_str} from parent task {parent_id_num}.")

    # If the subtasks list becomes empty, remove the key from the parent task object
    if not parent_task_obj_ref["subtasks"]:
        del parent_task_obj_ref["subtasks"]
        logger.info(f"Removed empty 'subtasks' list key from parent task {parent_id_num}.")
    
    # parent_task_obj_ref is a direct reference, so all_tasks_list_ref is already updated.
    # No need for: all_tasks_list_ref[parent_task_index] = parent_task_obj_ref

    newly_created_top_level_task: Optional[Dict[str, Any]] = None
    if convert_to_task:
        logger.info(f"Converting removed subtask {subtask_id_str} to a new top-level task.")
        
        # Determine the new ID for the top-level task
        highest_current_id = 0
        if all_tasks_list_ref: # Check if there are any tasks left
            valid_ids = [t.get("id",0) for t in all_tasks_list_ref if isinstance(t.get("id"),int)]
            if valid_ids:
                 highest_current_id = max(valid_ids)
        new_top_level_task_id = highest_current_id + 1

        # Create the new task dictionary from the removed subtask's data
        newly_created_top_level_task = {
            "id": new_top_level_task_id,
            "title": subtask_to_remove_data_copy.get("title", f"Converted Subtask (Original: {subtask_id_str})"),
            "description": subtask_to_remove_data_copy.get("description", ""),
            "details": subtask_to_remove_data_copy.get("details", ""),
            "status": subtask_to_remove_data_copy.get("status", "pending"), # Retain status
            "priority": subtask_to_remove_data_copy.get("priority", parent_task_obj_ref.get("priority", "medium")), # Inherit from original parent
            "dependencies": [], # Initialize, will be populated carefully
            "subtasks": [], # A new top-level task starts with no subtasks of its own
            "test_strategy": subtask_to_remove_data_copy.get("test_strategy", ""),
            "original_parent_id": parent_id_num, # Custom field to track origin
            "original_sub_id": actual_sub_id_num  # Custom field
        }
        
        # Dependency handling for the new top-level task:
        # 1. Add its original parent task as a dependency.
        # 2. Subtask dependencies were integers relative to sibling subtasks. These are generally not directly translatable.
        #    If a subtask depended on e.g. subtask ID 1 (of same parent), that context is lost.
        #    For simplicity, we only add the original parent as a dependency.
        #    More advanced logic could try to map if other sibling subtasks were also converted.
        
        current_deps_for_new_task: List[Union[int, str]] = []
        # Add original parent as a dependency, if it still exists
        if any(t.get("id") == parent_id_num for t in all_tasks_list_ref):
            current_deps_for_new_task.append(parent_id_num)
        else: # Should not happen unless parent was deleted in same atomic operation (not supported here)
            logger.warning(f"Original parent task {parent_id_num} seems to no longer exist. Not adding as dependency to new task {new_top_level_task_id}.")

        # If the subtask had dependencies on other *main* tasks (if subtasks could do that, e.g. "dep: [101]")
        # This part depends on how subtask dependencies were structured. Assuming they were only sibling IDs.
        # If subtask_to_remove_data_copy['dependencies'] contained main task IDs, they could be preserved if they are valid.
        # For now, the example data implies subtask dependencies are relative sibling IDs (integers).

        newly_created_top_level_task["dependencies"] = sorted(list(set(current_deps_for_new_task)))

        all_tasks_list_ref.append(newly_created_top_level_task) # Add to the main list
        logger.info(f"Created new top-level task ID {new_top_level_task_id} from subtask {subtask_id_str} with dependencies {newly_created_top_level_task['dependencies']}.")

    # tasks_data_full["tasks"] is already updated as all_tasks_list_ref is a direct reference.

    if not _write_json_file(tasks_path, tasks_data_full):
        # Consider rollback or error state if write fails. For now, raise IOError.
        raise IOError(f"Failed to write updated tasks data to {tasks_path} after removing/converting subtask.")

    if generate_files:
        # Placeholder for regenerating markdown task files
        # try:
        #    from .generate_task_files import generate_task_files_py # Late import
        #    await generate_task_files_py(tasks_path, str(pathlib.Path(tasks_path).parent)) # Assuming async
        #    logger.info("Task files regenerated after removing/converting subtask.")
        # except Exception as e_gen:
        #    logger.warning(f"Could not regenerate task files: {e_gen}")
        logger.info("Skipping regeneration of task files (generate_task_files_py call commented out).")
    
    return newly_created_top_level_task # Returns the new task dict if converted, else None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Starting remove_subtask_py test...")

    test_project_root = os.getcwd()
    dummy_tasks_file_for_remove_sub = os.path.join(test_project_root, "test_remove_subtask_main_tasks.json")

    async def main_remove_subtask_test_run():
        initial_tasks_data_for_remove_sub = {
            "metadata": {"project_name": "Remove Subtask Test Project"},
            "tasks": [
                {"id": 1, "title": "Parent Task One", "status": "pending", "priority": "high", "subtasks": [
                    {"id": 1, "title": "Subtask 1.1 (to be removed)", "status": "pending", "description": "Description for 1.1", "dependencies": []},
                    {"id": 2, "title": "Subtask 1.2 (to be kept)", "status": "in-progress", "description": "Description for 1.2", "dependencies": [1]}
                ]},
                {"id": 2, "title": "Parent Task Two", "status": "in-progress", "subtasks": [
                     {"id": 1, "title": "Subtask 2.1 (to be converted)", "status": "pending", "description": "This subtask will become a top-level task.", "dependencies": []}
                ]},
                {"id": 3, "title": "Task Three (for ID generation check)", "status": "pending"}
            ]
        }
        # Create a clean dummy file for each run
        with open(dummy_tasks_file_for_remove_sub, "w", encoding="utf-8") as f:
            json.dump(initial_tasks_data_for_remove_sub, f, indent=2)
        logger.info(f"Created dummy tasks file for remove_subtask tests: {dummy_tasks_file_for_remove_sub}")

        try:
            logger.info("\n--- Test 1: Remove Subtask 1.1 (no conversion) ---")
            result1 = await remove_subtask_py(
                dummy_tasks_file_for_remove_sub, 
                subtask_id_str="1.1", 
                convert_to_task=False,
                context={"project_root": test_project_root}
            )
            assert result1 is None, "Test 1 Failed: Should return None when not converting."
            
            data_after_1 = _read_json_file(dummy_tasks_file_for_remove_sub)
            assert data_after_1 is not None
            parent1_after_1 = next(t for t in data_after_1["tasks"] if t["id"] == 1)
            assert len(parent1_after_1["subtasks"]) == 1, "Test 1 Failed: Subtask count for Parent 1 is incorrect."
            assert parent1_after_1["subtasks"][0]["id"] == 2, "Test 1 Failed: Remaining subtask ID for Parent 1 is incorrect."
            logger.info("Test 1 PASSED: Subtask 1.1 removed successfully.")

            logger.info("\n--- Test 2: Convert Subtask 2.1 to a new top-level task ---")
            converted_task_result = await remove_subtask_py(
                dummy_tasks_file_for_remove_sub, 
                subtask_id_str="2.1", 
                convert_to_task=True,
                context={"project_root": test_project_root}
            )
            assert converted_task_result is not None, "Test 2 Failed: Conversion should return the new task object."
            logger.info(f"Test 2 Result - Converted to New Task: {json.dumps(converted_task_result, indent=2)}")
            
            assert converted_task_result["title"] == "Subtask 2.1 (to be converted)"
            new_task_id_2 = converted_task_result["id"]
            assert new_task_id_2 > 3, f"Test 2 Failed: New task ID {new_task_id_2} should be greater than existing max ID 3."

            data_after_2 = _read_json_file(dummy_tasks_file_for_remove_sub)
            assert data_after_2 is not None
            parent2_after_2 = next(t for t in data_after_2["tasks"] if t["id"] == 2)
            assert "subtasks" not in parent2_after_2 or not parent2_after_2["subtasks"], "Test 2 Failed: Parent 2 should have no subtasks left."
            
            newly_created_top_level_task = next((t for t in data_after_2["tasks"] if t["id"] == new_task_id_2), None)
            assert newly_created_top_level_task is not None, f"Test 2 Failed: New top-level task with ID {new_task_id_2} not found."
            assert 2 in newly_created_top_level_task.get("dependencies", []), "Test 2 Failed: Original parent (ID 2) not added as dependency."
            logger.info(f"Test 2 PASSED: Subtask 2.1 converted to new top-level Task {new_task_id_2}.")

            # Verify current max ID before next conversion test
            max_id_after_test2 = max(t["id"] for t in data_after_2["tasks"])


            logger.info("\n--- Test 3: Convert remaining Subtask 1.2 to a new top-level task (ensure new ID increments) ---")
            # Parent 1 now has only subtask 1.2 (ID 2 within parent 1)
            converted_task_result_3 = await remove_subtask_py(
                dummy_tasks_file_for_remove_sub, 
                subtask_id_str="1.2", # Subtask with internal ID 2 from Parent 1
                convert_to_task=True,
                context={"project_root": test_project_root}
            )
            assert converted_task_result_3 is not None, "Test 3 Failed: Conversion should return new task object."
            logger.info(f"Test 3 Result - Converted to New Task: {json.dumps(converted_task_result_3, indent=2)}")
            
            new_task_id_3 = converted_task_result_3["id"]
            assert new_task_id_3 == max_id_after_test2 + 1, f"Test 3 Failed: New task ID {new_task_id_3} should be incremental from previous max {max_id_after_test2}."

            data_after_3 = _read_json_file(dummy_tasks_file_for_remove_sub)
            assert data_after_3 is not None
            parent1_after_3 = next(t for t in data_after_3["tasks"] if t["id"] == 1)
            assert "subtasks" not in parent1_after_3 or not parent1_after_3["subtasks"], "Test 3 Failed: Parent 1 should have no subtasks left."
            
            newly_created_top_level_task_3 = next((t for t in data_after_3["tasks"] if t["id"] == new_task_id_3), None)
            assert newly_created_top_level_task_3 is not None, f"Test 3 Failed: New top-level task {new_task_id_3} not found."
            assert 1 in newly_created_top_level_task_3.get("dependencies", []), "Test 3 Failed: Original parent (ID 1) not added as dependency."
            logger.info(f"Test 3 PASSED: Subtask 1.2 converted to new top-level Task {new_task_id_3}.")


        except Exception as e_main_test:
            logger.error(f"A test in main_remove_subtask_test_run FAILED: {e_main_test}", exc_info=True)
        finally:
            if os.path.exists(dummy_tasks_file_for_remove_sub):
                os.remove(dummy_tasks_file_for_remove_sub)
                logger.info(f"Removed dummy tasks file after tests: {dummy_tasks_file_for_remove_sub}")
            logger.info("\nAll remove_subtask_py tests completed.")

    import asyncio
    asyncio.run(main_remove_subtask_test_run())

