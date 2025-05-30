import logging
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)

# Placeholder for add_complexity_to_task from utils.py (if/when ported)
# def add_complexity_to_task_py(task: Dict[str, Any], complexity_report: Optional[Dict]) -> None:
#     if not complexity_report or not isinstance(complexity_report.get("complexityAnalysis"), list):
#         task["complexityScore"] = "N/A" # Default if no report
#         return
#     # Simplified: find complexity by task ID (assuming ID structure matches report)
#     task_id_to_match = task.get("id")
#     # If it's a subtask, complexity might be on parent or subtask itself.
#     # This part needs clarification based on how complexity report handles subtasks.
#     # For now, assuming complexity is primarily for top-level tasks or subtasks have own entries.
#     analysis_entry = next((entry for entry in complexity_report["complexityAnalysis"] 
#                            if str(entry.get("id")) == str(task_id_to_match)), None)
#     if analysis_entry:
#         task["complexityScore"] = analysis_entry.get("complexityScore", "N/A")
#         task["complexityPrompt"] = analysis_entry.get("expansionPrompt", "")
#     else:
#         task["complexityScore"] = "N/A"


def _to_full_id_str(id_val: Union[int, str], parent_id: Optional[int] = None) -> str:
    if parent_id is not None: # It's a subtask
        return f"{parent_id}.{id_val}"
    return str(id_val) # It's a main task

def find_next_task_py(
    tasks_list: List[Dict[str, Any]], 
    complexity_report: Optional[Dict[str, Any]] = None # Currently unused placeholder
) -> Optional[Dict[str, Any]]:
    
    priority_values: Dict[str, int] = {"high": 3, "medium": 2, "low": 1, "default": 0}

    completed_ids: Set[str] = set()
    for task in tasks_list:
        task_id_val = task.get("id")
        if task_id_val is None: continue # Skip tasks without ID

        task_id_str = _to_full_id_str(task_id_val)
        if task.get("status", "").lower() in ["done", "completed"]:
            completed_ids.add(task_id_str)
        
        if isinstance(task.get("subtasks"), list):
            for subtask in task["subtasks"]:
                sub_id_val = subtask.get("id")
                if sub_id_val is None: continue

                sub_full_id_str = _to_full_id_str(sub_id_val, task_id_val)
                if subtask.get("status", "").lower() in ["done", "completed"]:
                    completed_ids.add(sub_full_id_str)

    # 1. Look for eligible subtasks of "in-progress" parent tasks
    candidate_subtasks: List[Dict[str, Any]] = []
    for parent_task in tasks_list:
        parent_id_val = parent_task.get("id")
        if parent_id_val is None: continue

        if parent_task.get("status", "").lower() == "in-progress" and isinstance(parent_task.get("subtasks"), list):
            for subtask in parent_task["subtasks"]:
                sub_id_val = subtask.get("id")
                if sub_id_val is None: continue
                
                subtask_status = subtask.get("status", "pending").lower()
                if subtask_status not in ["pending", "in-progress"]:
                    continue
                
                raw_dependencies = subtask.get("dependencies", [])
                if not isinstance(raw_dependencies, list):
                    logger.warning(f"Subtask {_to_full_id_str(sub_id_val, parent_id_val)} has malformed dependencies. Skipping.")
                    continue
                
                # Subtask dependencies can be:
                # - int: referring to another subtask of the SAME parent.
                # - str "X.Y": referring to subtask Y of parent X.
                # - str "X": referring to main task X. (less common for subtasks, but possible)
                # - int X (if not specified as str): referring to main task X (if context is clear, but safer to be explicit with strings for main tasks)
                # For subtask deps, we need to resolve them correctly.
                # The `_to_full_id_str` helper is for creating IDs, not parsing them.
                
                full_deps_str_list: List[str] = []
                valid_deps = True
                for dep in raw_dependencies:
                    if isinstance(dep, int): # Assumed to be a subtask of the same parent OR a main task ID
                        # Heuristic: if an int dep matches a main task ID, it's a main task dep.
                        # Otherwise, it's a subtask of the same parent.
                        # This can be ambiguous. The JS version's _toFullSubId was simple.
                        # A more robust system would require subtask deps to be explicitly "parent.sub" or sub-id for same parent.
                        # Let's assume int refers to subtask of same parent for now.
                        # If it needs to refer to a main task, it should be stringified in tasks.json, e.g. "1"
                        full_deps_str_list.append(_to_full_id_str(dep, parent_id_val))
                    elif isinstance(dep, str):
                        if "." in dep: # Already "parent.sub" format
                            full_deps_str_list.append(dep)
                        else: # Assumed to be a main task ID string
                            full_deps_str_list.append(dep) 
                    else:
                        logger.warning(f"Subtask {_to_full_id_str(sub_id_val, parent_id_val)} has invalid dependency type: {dep}. Skipping dep.")
                        # valid_deps = False; break # Or just skip this dependency
                        continue # Skip this specific malformed dependency

                # if not valid_deps: continue

                deps_satisfied = not full_deps_str_list or all(dep_id_str in completed_ids for dep_id_str in full_deps_str_list)

                if deps_satisfied:
                    subtask_priority = subtask.get("priority", parent_task.get("priority", "medium"))
                    candidate_subtasks.append({
                        "id": _to_full_id_str(sub_id_val, parent_id_val), # Full ID "parent.sub"
                        "title": subtask.get("title", f"Subtask {sub_id_val} of {parent_id_val}"),
                        "status": subtask.get("status", "pending"),
                        "priority": subtask_priority,
                        "dependencies": full_deps_str_list, # Store resolved, full string IDs
                        "parent_id": parent_id_val,
                        "description": subtask.get("description", ""),
                        "details": subtask.get("details", ""),
                        "test_strategy": subtask.get("test_strategy", ""),
                        # "complexityScore": "N/A" # Initialize, will be filled by add_complexity_to_task_py
                    })

    if candidate_subtasks:
        candidate_subtasks.sort(key=lambda st: (
            -priority_values.get(st["priority"], priority_values["default"]), 
            len(st["dependencies"]),
            st["parent_id"], # Lower parent ID first
            int(st["id"].split(".")[1]) # Then by numeric subtask ID
        ))
        next_item_sub = candidate_subtasks[0]
        # add_complexity_to_task_py(next_item_sub, complexity_report)
        return next_item_sub

    # 2. Fall back to top-level tasks
    eligible_main_tasks: List[Dict[str, Any]] = []
    for task in tasks_list:
        task_id_val = task.get("id")
        if task_id_val is None: continue

        task_status = task.get("status", "pending").lower()
        if task_status not in ["pending", "in-progress"]:
            continue
        
        raw_task_dependencies = task.get("dependencies", [])
        if not isinstance(raw_task_dependencies, list):
            logger.warning(f"Task {task_id_val} has malformed dependencies. Skipping.")
            continue

        # Main task dependencies are assumed to be int or str (numeric) referring to other main task IDs
        task_deps_str_list = [_to_full_id_str(dep) for dep in raw_task_dependencies]
        
        deps_satisfied = not task_deps_str_list or all(dep_id_str in completed_ids for dep_id_str in task_deps_str_list)

        if deps_satisfied:
            task_copy = {k:v for k,v in task.items() if k != "subtasks"} # Exclude subtasks from returned object for clarity
            task_copy["id"] = _to_full_id_str(task_id_val)
            task_copy["dependencies"] = task_deps_str_list
            # task_copy["complexityScore"] = "N/A" # Initialize
            eligible_main_tasks.append(task_copy)

    if not eligible_main_tasks:
        return None

    eligible_main_tasks.sort(key=lambda t: (
        -priority_values.get(t.get("priority", "medium"), priority_values["default"]),
        len(t.get("dependencies", [])),
        int(t.get("id", 0)) # Sort by numeric task ID
    ))
    
    next_item_main = eligible_main_tasks[0]
    # add_complexity_to_task_py(next_item_main, complexity_report)
    return next_item_main


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Test cases
    sample_tasks_1 = [
        {"id": 1, "title": "Parent Task 1", "status": "in-progress", "priority": "high", "subtasks": [
            {"id": 1, "title": "Sub 1.1", "status": "pending", "priority": "high", "dependencies": []}, 
            {"id": 2, "title": "Sub 1.2", "status": "pending", "priority": "medium", "dependencies": [1]}, # Depends on 1.1
        ]},
        {"id": 2, "title": "Parent Task 2", "status": "in-progress", "priority": "medium", "subtasks": [
            {"id": 1, "title": "Sub 2.1", "status": "done"}, # Note: subtask deps are relative to parent: dep "1" here means "2.1"
            {"id": 2, "title": "Sub 2.2", "status": "pending", "priority": "high", "dependencies": [1]}, # Depends on 2.1 
        ]},
        {"id": 3, "title": "Top-level Task 3", "status": "pending", "priority": "low", "dependencies": []} 
    ]
    
    logger.info("--- Test Case 1 ---")
    # Expected: 1.1 (Prio:high, Deps:0, Parent:1, SubID:1)
    #   vs 2.2 (Prio:high, Deps:1 ["2.1"], Parent:2, SubID:2) -> 2.1 is done for 2.2
    #   - Sub 1.1: Prio high, 0 deps.
    #   - Sub 2.2: Prio high, 1 dep (2.1), which is done. So effectively 0 *pending* deps.
    #     Sort order: Prio (both high) -> Dep count (0 for 1.1, 1 for 2.2) -> Parent ID (1 for 1.1)
    next_task_1 = find_next_task_py(sample_tasks_1)
    logger.info(f"Next task 1: {next_task_1.get('id') if next_task_1 else 'None'}") 
    assert next_task_1 and next_task_1.get('id') == "1.1"


    sample_tasks_2 = [
        {"id": 1, "title": "Parent Task 1", "status": "in-progress", "subtasks": [
            {"id": 1, "title": "Sub 1.1", "status": "done"},
            {"id": 2, "title": "Sub 1.2", "status": "pending", "dependencies": [1]}, # Depends on 1.1 (which is done)
        ]},
        {"id": 2, "title": "Top-level Task 2", "status": "pending", "priority": "high", "dependencies": []}
    ]
    logger.info("\n--- Test Case 2 ---")
    # Expected: 1.2 (Subtask of in-progress parent, deps satisfied)
    next_task_2 = find_next_task_py(sample_tasks_2)
    logger.info(f"Next task 2: {next_task_2.get('id') if next_task_2 else 'None'}") 
    assert next_task_2 and next_task_2.get('id') == "1.2"

    sample_tasks_3 = [
        {"id": 1, "title": "Parent Task 1", "status": "done", "subtasks": [ # Parent not in-progress
             {"id": 1, "title": "Sub 1.1", "status": "pending"},
        ]},
        {"id": 2, "title": "Top-level Task 2", "status": "pending", "priority": "high", "dependencies": []}, 
        {"id": 3, "title": "Top-level Task 3", "status": "pending", "priority": "medium", "dependencies": [2]} 
    ]
    logger.info("\n--- Test Case 3 ---")
    # Expected: 2 (Top-level, high prio, 0 deps)
    next_task_3 = find_next_task_py(sample_tasks_3)
    logger.info(f"Next task 3: {next_task_3.get('id') if next_task_3 else 'None'}") 
    assert next_task_3 and next_task_3.get('id') == "2"
    
    sample_tasks_4 = [
        {"id": 1, "title": "All Done", "status": "done", "subtasks": [
            {"id": 1, "title": "Sub 1.1", "status": "done"}
        ]},
        {"id": 2, "title": "Also Done", "status": "done"}
    ]
    logger.info("\n--- Test Case 4 (All done) ---")
    next_task_4 = find_next_task_py(sample_tasks_4)
    logger.info(f"Next task 4: {next_task_4.get('id') if next_task_4 else 'None'}") 
    assert next_task_4 is None

    sample_tasks_5 = [ 
        {"id": 1, "title": "Main Blocker Task", "status": "pending"}, # Eligible
        {"id": 2, "title": "Parent Task 2", "status": "in-progress", "subtasks": [
             # Subtask dependency on a main task ID (needs to be string if not int)
            {"id": 1, "title": "Sub 2.1", "status": "pending", "dependencies": ["1"]} 
        ]}
    ]
    logger.info("\n--- Test Case 5 (Subtask depends on Main Task) ---")
    # Expected: 1 (Main Blocker Task, as Sub 2.1 depends on it)
    next_task_5 = find_next_task_py(sample_tasks_5)
    logger.info(f"Next task 5: {next_task_5.get('id') if next_task_5 else 'None'}") 
    assert next_task_5 and next_task_5.get('id') == "1"

    # Mark task 1 as done
    sample_tasks_5_b = [ 
        {"id": 1, "title": "Main Blocker Task", "status": "done"},
        {"id": 2, "title": "Parent Task 2", "status": "in-progress", "subtasks": [
            {"id": 1, "title": "Sub 2.1", "status": "pending", "dependencies": ["1"]} 
        ]}
    ]
    logger.info("\n--- Test Case 5b (Main Task 1 done) ---")
    # Expected: 2.1 (Subtask of in-progress parent, dep "1" is now done)
    next_task_5b = find_next_task_py(sample_tasks_5_b) 
    logger.info(f"Next task 5b: {next_task_5b.get('id') if next_task_5b else 'None'}") 
    assert next_task_5b and next_task_5b.get('id') == "2.1"

    sample_tasks_6_malformed_deps = [
        {"id": 1, "title": "Parent Task 1", "status": "in-progress", "priority": "high", "subtasks": [
            {"id": 1, "title": "Sub 1.1", "status": "pending", "priority": "high", "dependencies": "not-a-list"}, 
            {"id": 2, "title": "Sub 1.2", "status": "pending", "priority": "medium", "dependencies": []}, # Eligible
        ]},
    ]
    logger.info("\n--- Test Case 6 (Malformed subtask dependency) ---")
    # Expected: 1.2 (Sub 1.1 should be skipped due to malformed deps)
    next_task_6 = find_next_task_py(sample_tasks_6_malformed_deps)
    logger.info(f"Next task 6: {next_task_6.get('id') if next_task_6 else 'None'}") 
    assert next_task_6 and next_task_6.get('id') == "1.2"
    
    logger.info("\nAll find_next_task_py tests completed.")
```
