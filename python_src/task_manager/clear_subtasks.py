import json
import os
import pathlib
import logging
from typing import Any, Dict, List, Literal, Optional, Union

# Placeholders
# from .generate_task_files import generate_task_files_py
# from ..ui import display_banner_py # If needed for CLI, e.g. from a python_src.cli.ui module

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
        return None # Or raise specific error

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

# clear_subtasks_py is async because its __main__ test block uses await.
# If generate_task_files_py becomes async, this will be consistent.
async def clear_subtasks_py(
    tasks_path: str,
    task_ids_input: str, # Comma-separated string of parent task IDs, or the keyword "all"
    generate_files: bool = True, # Parameter for future use (regenerating task markdown files)
    context: Optional[Dict[str, Any]] = None, # For project_root, etc.
    output_format: Literal["text", "json"] = "text", # For controlling output style
) -> Dict[str, Any]: # Returns a summary of actions

    context = context or {}
    # project_root = context.get("project_root") # Example of using context

    logger.info(f"Attempting to clear subtasks for parent task ID(s): '{task_ids_input}' from file '{tasks_path}'.")

    tasks_data_full = _read_json_file(tasks_path)
    if not tasks_data_full or not isinstance(tasks_data_full.get("tasks"), list):
        # If file doesn't exist or is malformed, cannot proceed.
        raise FileNotFoundError(f"Tasks file {tasks_path} not found or is not structured correctly (must be a dict with a 'tasks' list).")

    all_tasks_list_ref: List[Dict[str, Any]] = tasks_data_full["tasks"] # Direct reference
    
    parent_ids_to_process: List[int] = []
    parse_errors: List[str] = []

    if task_ids_input.strip().lower() == "all":
        parent_ids_to_process = [
            task_dict.get("id") for task_dict in all_tasks_list_ref 
            if isinstance(task_dict, dict) and isinstance(task_dict.get("id"), int)
        ]
        logger.info("Identified all tasks for potential subtask clearing.")
    else:
        id_str_list = [tid.strip() for tid in task_ids_input.split(",") if tid.strip()]
        if not id_str_list:
            raise ValueError("No task IDs provided for subtask clearing.")
            
        for id_str_item in id_str_list:
            try:
                parent_ids_to_process.append(int(id_str_item))
            except ValueError:
                logger.warning(f"Invalid task ID format: '{id_str_item}'. It must be an integer. Skipping this ID.")
                parse_errors.append(f"Invalid ID format: {id_str_item}")
    
    if not parent_ids_to_process and parse_errors:
        # All provided IDs were invalid
        raise ValueError(f"All provided task IDs were invalid. Errors: {'; '.join(parse_errors)}")
    elif not parent_ids_to_process:
        # "all" was specified but no tasks exist, or empty list provided
        logger.info("No valid task IDs found to process for subtask clearing.")
        return {
            "success": True, "summary": [], "tasks_modified_count": 0, 
            "message": "No valid tasks found to process."
        }

    cleared_action_summary: List[Dict[str, Any]] = []
    actual_tasks_modified_count = 0

    for parent_id_to_clear_num in parent_ids_to_process:
        parent_task_obj_ref: Optional[Dict[str, Any]] = None
        # parent_task_index_in_list = -1 # Not strictly needed if modifying by reference

        # Find the parent task object by ID
        found_parent = False
        for i, task_dict_item in enumerate(all_tasks_list_ref):
            if isinstance(task_dict_item, dict) and task_dict_item.get("id") == parent_id_to_clear_num:
                parent_task_obj_ref = task_dict_item # Direct reference
                # parent_task_index_in_list = i
                found_parent = True
                break
        
        if not found_parent or parent_task_obj_ref is None:
            logger.warning(f"Parent task with ID {parent_id_to_clear_num} not found in the tasks list. Skipping.")
            cleared_action_summary.append({
                "task_id": parent_id_to_clear_num, "title": "Task Not Found", 
                "cleared_count": 0, "status_outcome": "not_found"
            })
            continue # Skip to the next parent ID

        parent_title_for_log = parent_task_obj_ref.get('title', f"Task {parent_id_to_clear_num}")
        if "subtasks" in parent_task_obj_ref and \
           isinstance(parent_task_obj_ref["subtasks"], list) and \
           len(parent_task_obj_ref["subtasks"]) > 0:
            
            num_subtasks_cleared = len(parent_task_obj_ref["subtasks"])
            
            # Clear the subtasks list by deleting the key, as per JS behavior
            del parent_task_obj_ref["subtasks"] 
            # Note: all_tasks_list_ref[parent_task_index_in_list] = parent_task_obj_ref is not needed
            # because parent_task_obj_ref is a direct reference to the dictionary in the list.
            
            actual_tasks_modified_count += 1
            logger.info(f"Successfully cleared {num_subtasks_cleared} subtasks from parent task ID {parent_id_to_clear_num} ('{parent_title_for_log}').")
            cleared_action_summary.append({
                "task_id": parent_id_to_clear_num, "title": parent_title_for_log, 
                "cleared_count": num_subtasks_cleared, "status_outcome": "cleared"
            })
        else:
            logger.info(f"Parent task ID {parent_id_to_clear_num} ('{parent_title_for_log}') either has no 'subtasks' key or the list is already empty. No subtasks to clear.")
            cleared_action_summary.append({
                "task_id": parent_id_to_clear_num, "title": parent_title_for_log, 
                "cleared_count": 0, "status_outcome": "no_subtasks_present"
            })

    if actual_tasks_modified_count > 0:
        if not _write_json_file(tasks_path, tasks_data_full):
            # Consider implications of partial failure if some tasks were modified in memory but write failed.
            # For now, just raise an error. A more robust solution might involve backups or transactional writes.
            raise IOError(f"Failed to write updated tasks data to {tasks_path} after clearing subtasks.")
        logger.info(f"Successfully wrote updates to {tasks_path}. {actual_tasks_modified_count} parent task(s) had their subtasks cleared.")

        if generate_files:
            # Placeholder for regenerating markdown task files
            # try:
            #    from .generate_task_files import generate_task_files_py # Late import
            #    await generate_task_files_py(tasks_path, str(pathlib.Path(tasks_path).parent))
            #    logger.info("Task files regenerated after clearing subtasks.")
            # except Exception as e_gen:
            #    logger.warning(f"Could not regenerate task files: {e_gen}")
            logger.info("Skipping regeneration of task files (generate_task_files_py call commented out).")
    else:
        logger.info("No actual changes made to any tasks (no subtasks were cleared that required file update).")

    # --- Output final summary ---
    final_message = f"Processed {len(parent_ids_to_process)} task(s). {actual_tasks_modified_count} task(s) had subtasks cleared."
    if parse_errors:
        final_message += f" Encountered format errors for some IDs: {', '.join(parse_errors)}."
    
    if output_format == "text":
        # if callable(display_banner_py): display_banner_py("Subtask Clearing Summary") # Placeholder
        print(f"\n--- Subtask Clearing Summary for '{tasks_path}' ---")
        if cleared_action_summary:
            for item_summary in cleared_action_summary:
                if item_summary["status_outcome"] == "cleared":
                    print(f"  Task ID {item_summary['task_id']} ('{item_summary['title']}'): Cleared {item_summary['cleared_count']} subtasks.")
                elif item_summary["status_outcome"] == "no_subtasks_present":
                    print(f"  Task ID {item_summary['task_id']} ('{item_summary['title']}'): No subtasks were present to clear.")
                elif item_summary["status_outcome"] == "not_found":
                     print(f"  Task ID {item_summary['task_id']}: Was not found in the tasks list.")
        else:
            print("  No tasks were processed or found based on input.")
        
        if actual_tasks_modified_count > 0:
            print(f"\nSuccessfully updated tasks file: {tasks_path}")
        else:
            print("\nNo changes requiring update to tasks file were made.")
        if parse_errors:
            print(f"\nNote: Some provided IDs were skipped due to format errors: {', '.join(parse_errors)}")
            
    return {
        "success": True, # Indicates the operation ran; specific outcomes are in summary
        "summary": cleared_action_summary,
        "tasks_modified_count": actual_tasks_modified_count,
        "parse_errors": parse_errors,
        "message": final_message
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Starting clear_subtasks_py test...")

    test_project_root = os.getcwd()
    dummy_tasks_file_for_clear = os.path.join(test_project_root, "test_clear_subtasks_main_tasks.json")

    async def main_clear_subtasks_test_run():
        initial_tasks_data_for_clear = {
            "metadata": {"project_name": "Clear Subtasks Test Project"},
            "tasks": [
                {"id": 1, "title": "Parent One (has subs)", "status": "pending", "subtasks": [
                    {"id": 1, "title": "Subtask 1.1 of Parent One"}, {"id": 2, "title": "Subtask 1.2 of Parent One"}
                ]},
                {"id": 2, "title": "Parent Two (no subs key)", "status": "in-progress"},
                {"id": 3, "title": "Parent Three (empty subs list)", "status": "pending", "subtasks": []},
                {"id": 4, "title": "Parent Four (has subs)", "status": "pending", "subtasks": [
                    {"id": 1, "title": "Subtask 4.1 of Parent Four"}
                ]}
            ]
        }
        
        # Helper to reset file for each test scenario
        def reset_dummy_file_for_clear_test():
            with open(dummy_tasks_file_for_clear, "w", encoding="utf-8") as f:
                json.dump(initial_tasks_data_for_clear, f, indent=2)
            logger.debug(f"Reset dummy file for clear_subtasks test: {dummy_tasks_file_for_clear}")

        try:
            reset_dummy_file_for_clear_test()
            logger.info("\n--- Test 1: Clear subtasks from a single specified Task (ID 1) ---")
            result1 = await clear_subtasks_py(
                dummy_tasks_file_for_clear, task_ids_input="1",
                context={"project_root": test_project_root}, output_format="text"
            )
            logger.info(f"Clear Result 1: {json.dumps(result1, indent=2)}")
            assert result1["success"]
            assert result1["tasks_modified_count"] == 1
            assert result1["summary"][0]["task_id"] == 1 and result1["summary"][0]["cleared_count"] == 2
            
            data_after_1 = _read_json_file(dummy_tasks_file_for_clear)
            assert data_after_1 is not None
            task1_after_1 = next(t for t in data_after_1["tasks"] if t["id"] == 1)
            assert "subtasks" not in task1_after_1, "Test 1 Failed: 'subtasks' key should be removed from Task 1."
            logger.info("Test 1 PASSED.")

            reset_dummy_file_for_clear_test()
            logger.info("\n--- Test 2: Attempt to clear from Task 2 (no subtasks key) and Task 3 (empty subtasks list) ---")
            result2 = await clear_subtasks_py(dummy_tasks_file_for_clear, task_ids_input="2,3", output_format="json")
            logger.info(f"Clear Result 2 (JSON): {json.dumps(result2, indent=2)}")
            assert result2["success"]
            assert result2["tasks_modified_count"] == 0, "Test 2 Failed: No tasks should have been modified."
            assert any(s["task_id"] == 2 and s["status_outcome"] == "no_subtasks_present" for s in result2["summary"])
            assert any(s["task_id"] == 3 and s["status_outcome"] == "no_subtasks_present" for s in result2["summary"])
            logger.info("Test 2 PASSED.")

            reset_dummy_file_for_clear_test()
            logger.info("\n--- Test 3: Clear from Task 4 and a non-existent Task 99 ---")
            result3 = await clear_subtasks_py(dummy_tasks_file_for_clear, task_ids_input="4,99", output_format="text")
            logger.info(f"Clear Result 3: {json.dumps(result3, indent=2)}")
            assert result3["success"]
            assert result3["tasks_modified_count"] == 1, "Test 3 Failed: Only Task 4 should be modified."
            assert any(s["task_id"] == 4 and s["status_outcome"] == "cleared" and s["cleared_count"] == 1 for s in result3["summary"])
            assert any(s["task_id"] == 99 and s["status_outcome"] == "not_found" for s in result3["summary"])
            
            data_after_3 = _read_json_file(dummy_tasks_file_for_clear)
            assert data_after_3 is not None
            task4_after_3 = next(t for t in data_after_3["tasks"] if t["id"] == 4)
            assert "subtasks" not in task4_after_3, "Test 3 Failed: 'subtasks' key should be removed from Task 4."
            logger.info("Test 3 PASSED.")
            
            reset_dummy_file_for_clear_test()
            logger.info("\n--- Test 4: Clear subtasks from 'all' tasks ---")
            result4 = await clear_subtasks_py(dummy_tasks_file_for_clear, task_ids_input="all", output_format="json")
            logger.info(f"Clear Result 4 (all, JSON): {json.dumps(result4, indent=2)}")
            assert result4["success"]
            # Tasks 1 and 4 originally had subtasks
            assert result4["tasks_modified_count"] == 2, f"Test 4 Failed: Expected 2 tasks to be modified, got {result4['tasks_modified_count']}."
            
            data_after_4 = _read_json_file(dummy_tasks_file_for_clear)
            assert data_after_4 is not None
            for task_id_check in [1, 4]: # These had subtasks
                 task_after_all = next(t for t in data_after_4["tasks"] if t["id"] == task_id_check)
                 assert "subtasks" not in task_after_all, f"Test 4 Failed: Task {task_id_check} should have no subtasks key."
            task2_after_all = next(t for t in data_after_4["tasks"] if t["id"] == 2) # Had no subtasks key
            assert "subtasks" not in task2_after_all
            task3_after_all = next(t for t in data_after_4["tasks"] if t["id"] == 3) # Had empty subtasks list
            assert "subtasks" not in task3_after_all # Key should be removed if list was empty and then processed
            logger.info("Test 4 PASSED.")

        except Exception as e_main_test:
            logger.error(f"A test in main_clear_subtasks_test_run FAILED: {e_main_test}", exc_info=True)
        finally:
            if os.path.exists(dummy_tasks_file_for_clear):
                os.remove(dummy_tasks_file_for_clear)
                logger.info(f"Removed dummy tasks file after tests: {dummy_tasks_file_for_clear}")
            logger.info("\nAll clear_subtasks_py tests completed.")

    import asyncio
    asyncio.run(main_clear_subtasks_test_run())

