import json
import os
import pathlib
import logging
from typing import Any, Dict, List, Literal, Optional

# Assuming expand_task and config_manager are in the same/parent directory
from .expand_task import expand_task_py 
from ..config_manager import get_debug_flag, get_project_name # Import what's needed
# from ..ui import display_ai_usage_summary_py # Placeholder

logger = logging.getLogger(__name__)


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
    
# --- Helper for JSON read/write (can be moved to utils.py later) ---
def _read_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f: return json.load(f)
    except FileNotFoundError: 
        logger.warning(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError: 
        logger.error(f"Error decoding JSON from file: {file_path}")
        return None # Or raise specific error

def _aggregate_telemetry_py(
    telemetry_list: List[Optional[Dict[str, Any]]], 
    command_name: str = "expand_all_tasks_py" # Default command name
) -> Optional[Dict[str, Any]]:
    if not telemetry_list:
        return { # Return a default structure even if no telemetry entries
            "command_name": command_name, "total_calls": 0, "successful_calls": 0, 
            "errors": 0, "total_input_tokens": 0, "total_output_tokens": 0, 
            "total_tokens": 0, "total_cost": 0.0, "currency": "USD"
        }

    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    currency = None
    successful_calls = 0
    errors = 0 # Errors during AI call itself, not app logic errors
    
    # Filter out None entries and count them as errors if they represent failed calls
    # that should have returned telemetry.
    # For this aggregation, we assume an entry in telemetry_list means an AI call was attempted.
    
    for entry in telemetry_list:
        if entry and isinstance(entry, dict):
            total_input_tokens += entry.get("input_tokens", 0) or 0 
            total_output_tokens += entry.get("output_tokens", 0) or 0
            total_cost += entry.get("total_cost", 0.0) or 0.0
            if entry.get("currency") and not currency: 
                currency = entry.get("currency")
            # Assuming telemetry entry itself indicates success. Errors might be logged separately by expand_task_py
            # or an 'error' field could be in telemetry. For now, count valid entries as successful.
            successful_calls +=1 
        else:
            # If a None or non-dict entry is in the list, it might represent a failed call
            # where telemetry couldn't be captured. This depends on how `expand_task_py` reports errors.
            # For now, we'll count non-dict entries as indicative of some failure at the AI call stage.
            errors += 1 
            
    return {
        "command_name": command_name,
        "total_calls": successful_calls + errors, # Total AI calls attempted
        "successful_calls": successful_calls,
        "errors_in_ai_calls": errors, # Specifically errors from AI call telemetry (or lack thereof)
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "total_cost": round(total_cost, 6),
        "currency": currency or "USD" 
    }


async def expand_all_tasks_py(
    tasks_path: str,
    num_subtasks: Optional[int] = None, # Hint for AI, passed to expand_task_py
    use_research: bool = False,
    additional_context: Optional[str] = None, # User-provided extra context string
    force: bool = False, # If true, replace existing subtasks
    context: Optional[Dict[str, Any]] = None, # For project_root, etc.
    output_format: Literal["text", "json"] = "text", # For logging and summary display
) -> Dict[str, Any]:
    context = context or {}
    project_root = context.get("project_root")
    command_name_for_telemetry = context.get("command_name", "expand_all_tasks_py")
    
    # Simplified logging for now based on output_format
    # In a real CLI, would use Rich/Click for better output.
    def log_message(message: str, level: str = "info"):
        if output_format == "text":
            print(f"[{level.upper()}] {message}")
        logger.log(getattr(logging, level.upper(), logging.INFO), message)

    expanded_count = 0
    failed_to_expand_count = 0 # Tasks that were eligible but expand_task_py failed for
    all_individual_telemetry_data: List[Optional[Dict[str, Any]]] = []

    log_message("Starting 'expand all tasks' operation...")

    try:
        tasks_data_full = _read_json_file(tasks_path)
        if not tasks_data_full or not isinstance(tasks_data_full.get("tasks"), list):
            # If file doesn't exist or is malformed, no tasks can be expanded.
            log_message(f"Invalid or missing tasks data in {tasks_path}. Cannot proceed.", "error")
            # Return a structure consistent with success=False
            return {
                "success": False, "message": f"Invalid or missing tasks data in {tasks_path}.",
                "expanded_count": 0, "failed_count": 0, "skipped_count": 0, 
                "tasks_to_expand_count": 0, "telemetry_data": _aggregate_telemetry_py([], command_name_for_telemetry)
            }


        all_tasks_list: List[Dict[str, Any]] = tasks_data_full["tasks"]
        
        # Filter tasks eligible for expansion
        tasks_eligible_for_expansion = []
        for task_dict in all_tasks_list:
            if not isinstance(task_dict, dict): # Skip malformed task entries
                log_message(f"Skipping non-dictionary task item: {task_dict}", "warning")
                continue

            task_status = task_dict.get("status", "pending").lower()
            has_subtasks = bool(task_dict.get("subtasks") and isinstance(task_dict.get("subtasks"), list))

            if task_status in ["pending", "in-progress"]:
                if force or not has_subtasks:
                    tasks_eligible_for_expansion.append(task_dict)
        
        num_eligible_tasks = len(tasks_eligible_for_expansion)
        log_message(f"Found {num_eligible_tasks} tasks eligible for expansion (Status: pending/in-progress, Force: {force} or no existing subtasks).")

        if num_eligible_tasks == 0:
            log_message("No tasks require expansion based on current criteria.")
            return {
                "success": True, "expanded_count": 0, "failed_count": 0, "skipped_count": 0, 
                "tasks_to_expand_count": 0, 
                "telemetry_data": _aggregate_telemetry_py([], command_name_for_telemetry),
                "message": "No tasks eligible for expansion."
            }

        for i, task_to_process_dict in enumerate(tasks_eligible_for_expansion):
            task_id_to_expand = task_to_process_dict.get("id")
            if task_id_to_expand is None: # Should not happen if tasks.json is well-formed
                log_message(f"Task at index {i} (within eligible list) is missing an ID. Skipping.", "warning")
                failed_to_expand_count +=1 
                all_individual_telemetry_data.append(None) # Mark a failed attempt for telemetry
                continue

            log_message(f"Expanding task ID: {task_id_to_expand} (Task {i+1}/{num_eligible_tasks})...")
            try:
                # expand_task_py is async and handles its own file read/writes internally for each task
                # This means tasks_path is read multiple times. If performance is an issue for huge task lists,
                # expand_task_py could be refactored to accept the tasks_list and return modified list,
                # with a final single write here. For now, keeping it as per current design.
                expand_result = await expand_task_py(
                    tasks_path=tasks_path, 
                    task_id=task_id_to_expand,
                    num_subtasks=num_subtasks,
                    use_research=use_research,
                    additional_context=additional_context,
                    context=context, 
                    force=force # expand_task_py will use this to clear existing subtasks if true
                )
                
                # Check if expand_result itself indicates success for that specific task
                if expand_result and expand_result.get("success", True): # Assume success if not explicitly False
                    expanded_count += 1
                    log_message(f"Successfully expanded task {task_id_to_expand} with {expand_result.get('newly_added_subtasks_count',0)} new subtasks.")
                else: # expand_task_py itself might return a failure for a specific task
                    failed_to_expand_count += 1
                    log_message(f"Expansion attempt for task {task_id_to_expand} reported failure or unexpected result: {expand_result.get('message', 'No message')}", "warning")

                if expand_result and expand_result.get("telemetry_data"):
                    all_individual_telemetry_data.append(expand_result["telemetry_data"])
                else: # If no telemetry, could mean AI call was skipped or failed before telemetry
                    all_individual_telemetry_data.append(None) # Add placeholder for aggregation

            except Exception as e_expand: # Catch errors from individual expand_task_py calls
                failed_to_expand_count += 1
                all_individual_telemetry_data.append(None) # Mark a failed attempt for telemetry
                log_message(f"Failed to expand task {task_id_to_expand}: {e_expand}", "error")
                # Decide if one failure should stop all, or continue (current: continue)

        log_message(f"Finished expanding all eligible tasks. Expanded: {expanded_count}, Failures: {failed_to_expand_count}.")
        
        final_aggregated_telemetry = _aggregate_telemetry_py(all_individual_telemetry_data, command_name_for_telemetry)

        if output_format == "text":
            print(f"\n--- Overall Expansion Summary ---")
            print(f"Total tasks analyzed for expansion: {num_eligible_tasks}")
            print(f"Successfully expanded: {expanded_count}")
            print(f"Failed to expand: {failed_to_expand_count}")
            # if final_aggregated_telemetry and callable(display_ai_usage_summary_py):
            #     display_ai_usage_summary_py(final_aggregated_telemetry, "cli") 
            pass
            
        return {
            "success": True, # Represents overall completion of the batch operation
            "expanded_count": expanded_count,
            "failed_count": failed_to_expand_count,
            "skipped_count": 0, # Logic changed to pre-filter, so skipped_count during iteration is 0
            "tasks_to_expand_count": num_eligible_tasks, # Total number of tasks identified for expansion
            "telemetry_data": final_aggregated_telemetry
        }

    except Exception as e_main: # Catch errors in the main expand_all_tasks_py logic
        log_message(f"Critical error during 'expand all tasks' operation: {e_main}", "error")
        # If in debug mode, exc_info=True could be passed to logger.error
        # logger.error(f"Critical error: {e_main}", exc_info=get_debug_flag(project_root))
        if output_format == "text":
            print(f"Error: {e_main}")
        # Re-throw or return a specific error structure
        # For now, let's ensure it returns the standard dict with success=False
        return {
            "success": False, "message": str(e_main),
            "expanded_count": expanded_count, "failed_count": failed_to_expand_count + (num_eligible_tasks - expanded_count - failed_to_expand_count if 'num_eligible_tasks' in locals() else 0),
            "skipped_count": 0, "tasks_to_expand_count": locals().get('num_eligible_tasks', 0),
            "telemetry_data": _aggregate_telemetry_py(all_individual_telemetry_data, command_name_for_telemetry)
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Starting expand_all_tasks_py test...")

    test_project_root = os.getcwd()
    dummy_tasks_file_for_all = os.path.join(test_project_root, "test_expand_all_main_tasks.json")
    
    # Store original expand_task_py to restore it later
    original_expand_task_function = expand_task_py 
    
    # Mock expand_task_py for isolated testing of expand_all_tasks_py logic
    async def mock_expand_task_for_all_test(
        tasks_path: str, task_id: int, num_subtasks: Optional[int], **kwargs
    ) -> Dict[str, Any]:
        logger.info(f"[MOCK] Expanding task {task_id} in {tasks_path} with num_subtasks={num_subtasks}")
        # Simulate reading and writing to update the file state for the test
        current_tasks_data = _read_json_file(tasks_path)
        if current_tasks_data and isinstance(current_tasks_data.get("tasks"), list):
            task_found = False
            for t_dict in current_tasks_data['tasks']:
                if isinstance(t_dict, dict) and t_dict.get('id') == task_id:
                    num_new_subs = num_subtasks or 3 # Mock adds 3 subs if not specified
                    new_subs = [{"id": i+1, "title": f"Mock Subtask {i+1} for {task_id}"} for i in range(num_new_subs)]
                    
                    if kwargs.get("force", False) or not t_dict.get("subtasks"):
                        t_dict['subtasks'] = new_subs
                    else: # Append
                        t_dict.setdefault("subtasks", []).extend(new_subs)
                    
                    t_dict['status'] = 'pending' # Parent usually becomes pending after expansion
                    task_found = True
                    break
            if task_found:
                _write_json_file(tasks_path, current_tasks_data)
            else: # Should not happen if expand_all_tasks_py filters correctly
                raise ValueError(f"[MOCK] Task {task_id} not found for expansion.")

        mock_telemetry = {"input_tokens": 100, "output_tokens": 150, "total_cost": 0.0015, "currency": "USD"}
        return {
            "success": True, # Assume mock always succeeds for this part
            "task": {"id": task_id, "subtasks": [{"id":1}]}, # Simplified return
            "telemetry_data": mock_telemetry, 
            "newly_added_subtasks_count": num_subtasks or 3
        }

    # Monkey patch expand_task_py with the mock for this test suite
    # This requires the module to be addressable. If running as __main__, need to get current module.
    current_module_for_patch = __import__(__name__) 
    setattr(current_module_for_patch, 'expand_task_py', mock_expand_task_for_all_test)


    async def main_expand_all_tasks_test_run():
        initial_tasks_for_all_test = {
            "tasks": [
                {"id": 10, "title": "Task 10 (pending, no subs)", "status": "pending", "subtasks": []},
                {"id": 20, "title": "Task 20 (done, no subs)", "status": "done", "subtasks": []}, # Skipped (done)
                {"id": 30, "title": "Task 30 (in-progress, no subs)", "status": "in-progress", "subtasks": []},
                {"id": 40, "title": "Task 40 (pending, has subs, no force)", "status": "pending", "subtasks": [{"id":1, "title":"existing sub 40.1"}]}, # Skipped (no force)
                {"id": 50, "title": "Task 50 (pending, has subs, with force)", "status": "pending", "subtasks": [{"id":1, "title":"existing sub 50.1 to be replaced"}]},
            ]
        }
        with open(dummy_tasks_file_for_all, "w", encoding="utf-8") as f:
            json.dump(initial_tasks_for_all_test, f, indent=2)
        logger.info(f"Created dummy tasks file for expand_all tests: {dummy_tasks_file_for_all}")

        try:
            logger.info("\n--- Test 1: Expand All (no force) ---")
            # Expected: Task 10, Task 30 expanded. Task 40 skipped (has subs). Task 20 skipped (done). Task 50 skipped (has subs, no force).
            result1 = await expand_all_tasks_py(
                dummy_tasks_file_for_all, num_subtasks=2, force=False, 
                context={"project_root": test_project_root, "command_name": "test_expand_all_noforce"},
                output_format="text"
            )
            logger.info(f"Expand All Result 1 (no force): {json.dumps(result1, indent=2)}")
            assert result1["success"]
            assert result1["tasks_to_expand_count"] == 2, f"Test 1 Expected 2 tasks to expand, got {result1['tasks_to_expand_count']}" # Tasks 10, 30
            assert result1["expanded_count"] == 2, f"Test 1 Expected 2 expanded, got {result1['expanded_count']}"
            
            data_after_1 = _read_json_file(dummy_tasks_file_for_all)
            assert data_after_1 is not None
            assert len(next(t for t in data_after_1["tasks"] if t["id"] == 10)["subtasks"]) == 2
            assert len(next(t for t in data_after_1["tasks"] if t["id"] == 30)["subtasks"]) == 2
            assert len(next(t for t in data_after_1["tasks"] if t["id"] == 40)["subtasks"]) == 1, "Task 40 should not have been re-expanded"
            assert len(next(t for t in data_after_1["tasks"] if t["id"] == 50)["subtasks"]) == 1, "Task 50 should not have been re-expanded"


            logger.info("\n--- Test 2: Expand All (with force) ---")
            # Reset tasks file to initial state for a clean force test
            with open(dummy_tasks_file_for_all, "w", encoding="utf-8") as f:
                json.dump(initial_tasks_for_all_test, f, indent=2)
            
            # Expected: Task 10, 30, 40, 50 expanded. Task 40 and 50 subtasks replaced. Task 20 skipped.
            result2 = await expand_all_tasks_py(
                dummy_tasks_file_for_all, num_subtasks=3, force=True,
                context={"project_root": test_project_root, "command_name": "test_expand_all_force"},
                output_format="json" # Test JSON output mode
            )
            logger.info(f"Expand All Result 2 (force, JSON): {json.dumps(result2, indent=2)}")
            assert result2["success"]
            assert result2["tasks_to_expand_count"] == 4, f"Test 2 Expected 4 tasks to expand, got {result2['tasks_to_expand_count']}" # Tasks 10, 30, 40, 50
            assert result2["expanded_count"] == 4, f"Test 2 Expected 4 expanded, got {result2['expanded_count']}"
            
            data_after_2 = _read_json_file(dummy_tasks_file_for_all)
            assert data_after_2 is not None
            assert len(next(t for t in data_after_2["tasks"] if t["id"] == 10)["subtasks"]) == 3
            assert len(next(t for t in data_after_2["tasks"] if t["id"] == 30)["subtasks"]) == 3
            assert len(next(t for t in data_after_2["tasks"] if t["id"] == 40)["subtasks"]) == 3, "Task 40 should have been re-expanded with 3 subs"
            assert next(t for t in data_after_2["tasks"] if t["id"] == 40)["subtasks"][0]["title"] == "Mock Subtask 1 for 40", "Task 40 subtask title mismatch"
            assert len(next(t for t in data_after_2["tasks"] if t["id"] == 50)["subtasks"]) == 3, "Task 50 should have been re-expanded with 3 subs"
            assert next(t for t in data_after_2["tasks"] if t["id"] == 50)["subtasks"][0]["title"] == "Mock Subtask 1 for 50", "Task 50 subtask title mismatch"

            # Check telemetry aggregation
            assert result2["telemetry_data"] is not None
            assert result2["telemetry_data"]["total_calls"] == 4
            assert result2["telemetry_data"]["successful_calls"] == 4
            assert result2["telemetry_data"]["total_input_tokens"] == 4 * 100
            assert result2["telemetry_data"]["total_output_tokens"] == 4 * 150


        except Exception as e_main_test:
            logger.error(f"A test in main_expand_all_tasks_test_run FAILED: {e_main_test}", exc_info=True)
        finally:
            # Restore original expand_task_py function
            setattr(current_module_for_patch, 'expand_task_py', original_expand_task_function)
            logger.info("Restored original expand_task_py function.")
            
            if os.path.exists(dummy_tasks_file_for_all):
                os.remove(dummy_tasks_file_for_all)
                logger.info(f"Removed dummy tasks file after tests: {dummy_tasks_file_for_all}")
            logger.info("\nAll expand_all_tasks_py tests completed.")

    import asyncio
    asyncio.run(main_expand_all_tasks_test_run())

