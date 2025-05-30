import json
import os
import pathlib
import logging
from typing import Any, Dict, List, Optional, Union

# Placeholders - these will be properly imported or implemented later
# from .generate_task_files import generate_task_files_py
# from .is_task_dependent_on import is_task_dependent_on_py # Placeholder

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

# add_subtask_py is async because its __main__ test block uses await.
# If generate_task_files_py becomes async, this will be consistent.
async def add_subtask_py(
    tasks_path: str,
    parent_id: Union[int, str], # ID of the task to add subtask(s) to
    existing_task_id: Optional[Union[int, str]] = None, # ID of an existing task to convert
    new_subtask_data: Optional[Dict[str, Any]] = None, # Data for a completely new subtask
    generate_files: bool = True, # Parameter for future use (regenerating task markdown files)
    context: Optional[Dict[str, Any]] = None, # For project_root, session, etc.
) -> Dict[str, Any]: # Returns the newly created/converted subtask dictionary
    
    context = context or {} # Ensure context is a dict
    # project_root = context.get("project_root") # Example of using context

    logger.info(
        f"Initiating add_subtask. Parent Task ID: {parent_id}. "
        f"Convert Existing Task ID: {existing_task_id if existing_task_id is not None else 'N/A'}. "
        f"New Subtask Data Provided: {bool(new_subtask_data)}."
    )

    tasks_data_full = _read_json_file(tasks_path)
    if not tasks_data_full or not isinstance(tasks_data_full.get("tasks"), list):
        # If file doesn't exist or is malformed, cannot proceed.
        raise FileNotFoundError(f"Tasks file {tasks_path} not found or is not structured correctly (must be a dict with a 'tasks' list).")

    all_tasks_list: List[Dict[str, Any]] = tasks_data_full["tasks"]
    
    try:
        parent_id_num = int(parent_id)
    except ValueError:
        raise ValueError(f"Parent ID '{parent_id}' must be a valid integer.")

    parent_task_index = -1
    parent_task_obj_ref: Optional[Dict[str, Any]] = None # Direct reference to the parent task dict

    for i, task_dict_item in enumerate(all_tasks_list):
        if isinstance(task_dict_item, dict) and task_dict_item.get("id") == parent_id_num:
            parent_task_index = i
            parent_task_obj_ref = task_dict_item # Get a direct reference
            break
    
    if parent_task_index == -1 or parent_task_obj_ref is None:
        raise ValueError(f"Parent task with ID {parent_id_num} not found in {tasks_path}.")
    
    # Ensure 'subtasks' list exists in the parent task object
    if "subtasks" not in parent_task_obj_ref or not isinstance(parent_task_obj_ref["subtasks"], list):
        parent_task_obj_ref["subtasks"] = []
    
    # Variable to hold the subtask that is created or converted
    final_added_subtask: Optional[Dict[str, Any]] = None

    if existing_task_id is not None:
        # --- Convert an existing top-level task to a subtask ---
        logger.info(f"Mode: Convert existing task ID {existing_task_id} to a subtask of parent {parent_id_num}.")
        if new_subtask_data is not None:
            logger.warning("Both 'existing_task_id' and 'new_subtask_data' provided. Prioritizing 'existing_task_id'.")

        try:
            existing_task_id_num = int(existing_task_id)
        except ValueError:
            raise ValueError(f"Existing task ID to convert '{existing_task_id}' must be a valid integer.")

        original_task_to_convert_index = -1
        original_task_to_convert_data: Optional[Dict[str, Any]] = None
        for i, task_dict_item in enumerate(all_tasks_list):
             # Ensure we are not trying to remove the parent task itself if indices shift due to prior ops (unlikely here)
            if isinstance(task_dict_item, dict) and task_dict_item.get("id") == existing_task_id_num:
                # Check if this task is the parent task we are adding to - this check should be before finding parent
                if i == parent_task_index : # This means existing_task_id_num == parent_id_num
                     raise ValueError("A task cannot be made a subtask of itself.")
                original_task_to_convert_index = i
                original_task_to_convert_data = task_dict_item
                break
        
        if original_task_to_convert_index == -1 or original_task_to_convert_data is None:
            raise ValueError(f"Existing task with ID {existing_task_id_num} (to be converted) was not found.")

        # Check if the task to be converted is already a subtask of some other task
        if original_task_to_convert_data.get("parent_task_id") is not None:
            raise ValueError(f"Task {existing_task_id_num} is already a subtask of task {original_task_to_convert_data['parent_task_id']}. Cannot convert.")
        
        # Placeholder for more complex circular dependency check: is_task_dependent_on_py
        # This would check if parent_id_num is a subtask of existing_task_id_num, or if there's a chain.
        # For now, only direct self-parenting is caught above.
        logger.warning("Skipping advanced circular dependency check (is_task_dependent_on_py) - not yet ported.")

        # Determine the new ID for the subtask (sequential within the parent)
        highest_sub_id_in_parent = 0
        if parent_task_obj_ref["subtasks"]: # Check if list is not empty
            valid_sub_ids = [st.get("id",0) for st in parent_task_obj_ref["subtasks"] if isinstance(st.get("id"),int)]
            if valid_sub_ids:
                highest_sub_id_in_parent = max(valid_sub_ids)
        new_internal_sub_id = highest_sub_id_in_parent + 1

        # Create the subtask object from the original task's data
        final_added_subtask = original_task_to_convert_data.copy() # Shallow copy
        final_added_subtask["id"] = new_internal_sub_id # Set new ID relative to parent
        final_added_subtask["parent_task_id"] = parent_id_num # Add parent task ID reference
        # Ensure essential fields for a subtask are present
        final_added_subtask.setdefault("status", "pending")
        final_added_subtask.setdefault("dependencies", []) # Dependencies might need re-evaluation in future step

        parent_task_obj_ref["subtasks"].append(final_added_subtask)
        
        # Remove the original task from the top-level list
        # Adjust parent_task_index if original_task_index was before it, to avoid pop error
        # This is complex if parent_task_index itself changes.
        # Safer to rebuild all_tasks_list without the converted task.
        all_tasks_list_new = [t for i, t in enumerate(all_tasks_list) if i != original_task_to_convert_index]
        tasks_data_full["tasks"] = all_tasks_list_new # Update the main structure
        
        logger.info(f"Task {existing_task_id_num} successfully converted to subtask {parent_id_num}.{new_internal_sub_id}.")

    elif new_subtask_data is not None:
        # --- Create a brand new subtask from provided data ---
        logger.info(f"Mode: Creating a new subtask for parent ID {parent_id_num} from provided data.")
        if not isinstance(new_subtask_data.get("title"), str) or not new_subtask_data["title"].strip():
            raise ValueError("New subtask data must include a non-empty 'title'.")

        highest_sub_id_in_parent = 0
        if parent_task_obj_ref["subtasks"]: # Check if list is not empty
            valid_sub_ids = [st.get("id",0) for st in parent_task_obj_ref["subtasks"] if isinstance(st.get("id"),int)]
            if valid_sub_ids:
                highest_sub_id_in_parent = max(valid_sub_ids)
        new_internal_sub_id = highest_sub_id_in_parent + 1

        final_added_subtask = {
            "id": new_internal_sub_id,
            "title": new_subtask_data["title"],
            "description": new_subtask_data.get("description", ""),
            "details": new_subtask_data.get("details", ""),
            "status": new_subtask_data.get("status", "pending"),
            "dependencies": new_subtask_data.get("dependencies", []), # Validate these are int IDs of sibling subtasks
            "priority": new_subtask_data.get("priority", parent_task_obj_ref.get("priority", "medium")),
            "parent_task_id": parent_id_num,
            "test_strategy": new_subtask_data.get("test_strategy", "")
            # Add any other fields from new_subtask_data that are relevant for a subtask
        }
        # Validate dependencies for new subtask - they should be IDs of other subtasks of the same parent
        valid_new_sub_deps = []
        if isinstance(final_added_subtask["dependencies"], list):
            for dep_id in final_added_subtask["dependencies"]:
                if isinstance(dep_id, int) and dep_id < new_internal_sub_id and dep_id > 0: # Dep on prior sibling
                     if any(st.get("id") == dep_id for st in parent_task_obj_ref["subtasks"]): # Check it exists
                        valid_new_sub_deps.append(dep_id)
                     else:
                        logger.warning(f"New subtask dependency ID {dep_id} for subtask {new_internal_sub_id} (parent {parent_id_num}) does not exist as a prior sibling. Removing.")
                else:
                    logger.warning(f"Invalid dependency {dep_id} for new subtask {new_internal_sub_id} (parent {parent_id_num}). Must be int ID of prior sibling. Removing.")
        final_added_subtask["dependencies"] = valid_new_sub_deps
        
        parent_task_obj_ref["subtasks"].append(final_added_subtask)
        logger.info(f"New subtask {parent_id_num}.{new_internal_sub_id} ('{final_added_subtask['title']}') created successfully.")
    else:
        # This case should not be reached if called from CLI that requires one or the other.
        raise ValueError("To add a subtask, either 'existing_task_id' (to convert) or 'new_subtask_data' (to create new) must be provided.")

    # The parent_task_obj_ref is a direct reference to an item in all_tasks_list.
    # If all_tasks_list was not updated (e.g. when converting task), ensure tasks_data_full["tasks"] points to the modified list.
    # In the conversion case, tasks_data_full["tasks"] was already updated.
    # For adding new subtask, parent_task_obj_ref was modified in place, so all_tasks_list (and thus tasks_data_full["tasks"]) is also updated.

    if not _write_json_file(tasks_path, tasks_data_full):
        raise IOError(f"Failed to write updated tasks to {tasks_path} after adding subtask.")

    if generate_files:
        # Placeholder for regenerating markdown task files
        # try:
        #    from .generate_task_files import generate_task_files_py # Late import
        #    await generate_task_files_py(tasks_path, str(pathlib.Path(tasks_path).parent)) # Assuming async
        #    logger.info("Task files regenerated after adding subtask.")
        # except Exception as e_gen:
        #    logger.warning(f"Could not regenerate task files: {e_gen}")
        logger.info("Skipping regeneration of task files (generate_task_files_py call commented out).")
    
    if final_added_subtask is None: # Should ideally not be reached if logic is correct
        logger.error("Subtask creation process completed but no subtask object was finalized.")
        raise SystemError("Subtask creation failed unexpectedly without specific error.")

    return final_added_subtask


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Starting add_subtask_py test...")

    test_project_root = os.getcwd()
    dummy_tasks_file_for_add_sub = os.path.join(test_project_root, "test_add_subtask_main_tasks.json")

    async def main_add_subtask_test_run():
        initial_tasks_data_for_add_sub = {
            "metadata": {"project_name": "Add Subtask Test Project"},
            "tasks": [
                {"id": 1, "title": "Parent Task One", "status": "pending", "priority": "high", "subtasks": []},
                {"id": 2, "title": "Task to be Converted to Subtask", "status": "pending", "description": "This task will become a subtask."},
                {"id": 3, "title": "Parent Task Two (no subtasks key yet)", "status": "in-progress", "priority": "medium"},
                {"id": 4, "title": "Parent Task Three (with existing subtasks)", "status": "pending", "subtasks": [
                    {"id": 1, "title": "Existing Sub 4.1", "status":"done", "dependencies":[]},
                    {"id": 2, "title": "Existing Sub 4.2", "status":"pending", "dependencies":[1]}
                ]}
            ]
        }
        # Create a clean dummy file for each run or manage state carefully
        with open(dummy_tasks_file_for_add_sub, "w", encoding="utf-8") as f:
            json.dump(initial_tasks_data_for_add_sub, f, indent=2)
        logger.info(f"Created dummy tasks file for add_subtask tests: {dummy_tasks_file_for_add_sub}")

        try:
            logger.info("\n--- Test 1: Create a new subtask under Parent Task 1 ---")
            new_subtask_content = {"title": "Newly Created Subtask for Task 1", "description": "Description for the new subtask."}
            created_subtask_1 = await add_subtask_py(
                dummy_tasks_file_for_add_sub, parent_id=1, 
                new_subtask_data=new_subtask_content,
                context={"project_root": test_project_root}
            )
            logger.info(f"Test 1 Result - Created Subtask: {json.dumps(created_subtask_1, indent=2)}")
            assert created_subtask_1["title"] == new_subtask_content["title"]
            assert created_subtask_1["parent_task_id"] == 1
            assert created_subtask_1["id"] == 1 # First subtask for parent 1

            data_after_test1 = _read_json_file(dummy_tasks_file_for_add_sub)
            assert data_after_test1 is not None
            parent1_after_test1 = next(t for t in data_after_test1["tasks"] if t["id"] == 1)
            assert len(parent1_after_test1["subtasks"]) == 1
            assert parent1_after_test1["subtasks"][0]["title"] == new_subtask_content["title"]
            logger.info("Test 1 PASSED.")

            logger.info("\n--- Test 2: Convert existing Task 2 to a subtask of Parent Task 1 ---")
            # Parent 1 now has one subtask (ID 1). New converted subtask should get ID 2.
            converted_subtask = await add_subtask_py(
                dummy_tasks_file_for_add_sub, parent_id=1, 
                existing_task_id=2,
                context={"project_root": test_project_root}
            )
            logger.info(f"Test 2 Result - Converted Subtask: {json.dumps(converted_subtask, indent=2)}")
            assert converted_subtask["description"] == "This task will become a subtask."
            assert converted_subtask["parent_task_id"] == 1
            assert converted_subtask["id"] == 2 # Second subtask for parent 1

            data_after_test2 = _read_json_file(dummy_tasks_file_for_add_sub)
            assert data_after_test2 is not None
            parent1_after_test2 = next(t for t in data_after_test2["tasks"] if t["id"] == 1)
            assert len(parent1_after_test2["subtasks"]) == 2
            # Check that Task 2 is no longer a top-level task
            assert not any(t["id"] == 2 for t in data_after_test2["tasks"]), "Task 2 should have been removed from top-level."
            logger.info("Test 2 PASSED.")

            logger.info("\n--- Test 3: Add a new subtask to Parent Task 3 (which has no 'subtasks' key initially) ---")
            new_sub_for_task3 = {"title": "First Subtask for Task 3", "dependencies": []} # Test empty deps
            created_subtask_3 = await add_subtask_py(
                dummy_tasks_file_for_add_sub, parent_id=3, 
                new_subtask_data=new_sub_for_task3,
                context={"project_root": test_project_root}
            )
            logger.info(f"Test 3 Result - Created Subtask for Task 3: {json.dumps(created_subtask_3, indent=2)}")
            assert created_subtask_3["title"] == new_sub_for_task3["title"]
            assert created_subtask_3["parent_task_id"] == 3
            assert created_subtask_3["id"] == 1 # First subtask for parent 3
            assert created_subtask_3["priority"] == "medium" # Inherited from parent 3

            data_after_test3 = _read_json_file(dummy_tasks_file_for_add_sub)
            assert data_after_test3 is not None
            parent3_after_test3 = next(t for t in data_after_test3["tasks"] if t["id"] == 3)
            assert len(parent3_after_test3["subtasks"]) == 1
            assert parent3_after_test3["subtasks"][0]["title"] == new_sub_for_task3["title"]
            logger.info("Test 3 PASSED.")

            logger.info("\n--- Test 4: Add a new subtask to Parent Task 4 (which has existing subtasks) ---")
            # Parent 4 has subtasks with IDs 1, 2. New subtask should get ID 3.
            new_sub_for_task4 = {"title": "Third Subtask for Task 4", "dependencies": [1, 2]} # Depends on existing subs
            created_subtask_4 = await add_subtask_py(
                dummy_tasks_file_for_add_sub, parent_id=4,
                new_subtask_data=new_sub_for_task4,
                context={"project_root": test_project_root}
            )
            logger.info(f"Test 4 Result - Created Subtask for Task 4: {json.dumps(created_subtask_4, indent=2)}")
            assert created_subtask_4["id"] == 3 # New ID should be 3
            assert created_subtask_4["dependencies"] == [1, 2] # Check dependencies preserved and valid

            data_after_test4 = _read_json_file(dummy_tasks_file_for_add_sub)
            assert data_after_test4 is not None
            parent4_after_test4 = next(t for t in data_after_test4["tasks"] if t["id"] == 4)
            assert len(parent4_after_test4["subtasks"]) == 3
            logger.info("Test 4 PASSED.")


        except Exception as e_main_test:
            logger.error(f"A test in main_add_subtask_test_run FAILED: {e_main_test}", exc_info=True)
        finally:
            if os.path.exists(dummy_tasks_file_for_add_sub):
                os.remove(dummy_tasks_file_for_add_sub)
                logger.info(f"Removed dummy tasks file after tests: {dummy_tasks_file_for_add_sub}")
            logger.info("\nAll add_subtask_py tests completed.")

    import asyncio
    asyncio.run(main_add_subtask_test_run())

```
