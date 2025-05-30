import json
import os
import pathlib
import logging
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, ValidationError

# Assuming ai_services_unified and config_manager are in the parent directory
from ..ai_services_unified import AIService
from ..config_manager import get_default_subtasks, get_debug_flag, get_project_name # Import what's needed

# Placeholders - these will be properly imported or implemented later
# from .generate_task_files import generate_task_files_py
# from ..ui import display_ai_usage_summary_py

logger = logging.getLogger(__name__)

# --- Pydantic Schemas ---
class Subtask(BaseModel):
    id: int = Field(..., gt=0, description="Sequential subtask ID, starting from the determined next_subtask_id")
    title: str = Field(..., min_length=3, description="Clear, specific title for the subtask")
    description: str = Field(..., min_length=5, description="Detailed description of the subtask")
    dependencies: List[int] = Field(default_factory=list, description="IDs of prerequisite subtasks within this generation batch")
    details: str = Field(default="", description="Implementation details and guidance")
    status: str = Field(default="pending", description="The current status of the subtask (should be 'pending')")
    test_strategy: Optional[str] = Field(default=None, description="Approach for testing this subtask")

    @field_validator('dependencies', mode='before')
    @classmethod
    def ensure_dependencies_are_list_of_int(cls, v: Any) -> List[int]:
        if not isinstance(v, list):
            if isinstance(v, str): 
                try: 
                    v_parsed = json.loads(v)
                    if not isinstance(v_parsed, list):
                        raise ValueError('Dependencies string parsed but is not a list')
                    v = v_parsed
                except json.JSONDecodeError: 
                    # If it's not a JSON list, maybe it's a single number as string, or comma-sep string
                    # For simplicity, the model expects a list or JSON string of list.
                    # More complex string parsing (e.g. "1,2,3") could be added if AI often returns that.
                    raise ValueError('Dependencies string is not valid JSON for a list')
            else:
                raise ValueError('Dependencies must be a list or a JSON string representing a list')

        processed_deps: List[int] = []
        for item in v:
            try: 
                processed_deps.append(int(item))
            except (ValueError, TypeError): 
                logger.warning(f"Invalid dependency item '{item}' skipped during Pydantic validation.")
        return processed_deps

class SubtaskWrapper(BaseModel):
    subtasks: List[Subtask]

# --- Helper for JSON read/write ---
def _read_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f: return json.load(f)
    except FileNotFoundError: 
        logger.warning(f"Tasks file {file_path} not found.")
        return None # Or raise error if file must exist
    except json.JSONDecodeError: 
        logger.error(f"Error decoding JSON from file: {file_path}")
        return None # Or raise

def _write_json_file(file_path: str, data: Dict[str, Any]) -> bool:
    try:
        parent_dir = pathlib.Path(file_path).parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
        return True
    except Exception as e: 
        logger.error(f"Error writing JSON to file {file_path}: {e}")
        return False

# --- Prompt Generation ---
def _generate_main_system_prompt(parent_task_title: str, subtask_count: int, next_subtask_id: int) -> str:
    project_name = get_project_name() # Assuming global access or passed via context
    return (
        f"You are an AI assistant specialized in breaking down complex software development tasks into smaller, actionable subtasks for the project '{project_name}'. "
        f"The parent task is '{parent_task_title}'. Your goal is to generate exactly {subtask_count} subtasks. "
        "Each subtask must be a logical step towards completing the parent task. "
        "Subtasks should be sequential where appropriate, and dependencies should reflect this. "
        "For each subtask, provide the following fields: "
        "  - 'id': A sequential integer ID for the subtask, starting from {next_subtask_id}. Increment this for each subsequent subtask you generate in this batch. "
        "  - 'title': A clear, concise title (e.g., 'Implement user registration endpoint'). "
        "  - 'description': A one or two sentence explanation of what the subtask entails. "
        "  - 'dependencies': A list of *subtask IDs from this current generation batch* that this subtask depends on. E.g., if subtask {next_subtask_id+1} depends on subtask {next_subtask_id}, dependencies would be [{next_subtask_id}]. Use an empty list [] if no such dependencies. "
        "  - 'details': (Optional) In-depth implementation notes, considerations, or pseudo-code. "
        "  - 'status': Default this to 'pending'. "
        "  - 'test_strategy': (Optional) A brief description of how to verify this subtask is complete. "
        "Respond ONLY with a valid JSON object strictly following this structure: {\"subtasks\": [{\"id\": ..., \"title\": ..., /* etc. */}]}. "
        "Do not include any explanations, comments, or markdown formatting outside of this JSON structure."
    )

def _generate_main_user_prompt(task: Dict[str, Any], subtask_count: int, additional_context: Optional[str], next_subtask_id: int) -> str:
    context_prompt = f"\nAdditional context from user: {additional_context}" if additional_context else ""
    
    # Create a more explicit example for the AI, showing the starting ID.
    example_subtasks = []
    for i in range(min(2, subtask_count)): # Show up to 2 examples
        example_id = next_subtask_id + i
        example_deps = [next_subtask_id + j for j in range(i) if i > 0] # Simple sequential dependency for example
        example_subtasks.append({
            "id": example_id, 
            "title": f"Example Title for Subtask {example_id}", 
            "description": "Detailed description for this example subtask.", 
            "dependencies": example_deps, 
            "details": "Implementation notes for this example.", 
            "status": "pending",
            "test_strategy": "How to test this example."
        })
    schema_example = json.dumps({"subtasks": example_subtasks}, indent=2)

    return (
        f"The parent task to break down is:\n"
        f"  ID: {task.get('id')}\n"
        f"  Title: {task.get('title')}\n"
        f"  Description: {task.get('description')}\n"
        f"  Existing Details: {task.get('details', 'None')}\n"
        f"{context_prompt}\n\n"
        f"Please generate exactly {subtask_count} subtasks for this parent task. "
        f"The first subtask you generate should have id = {next_subtask_id}. "
        f"Ensure all subtask IDs are sequential from this starting point. "
        f"Make sure dependencies correctly refer to the 'id' fields of other subtasks *within this same generation batch*. "
        f"Return ONLY the JSON object as specified in the system prompt. Example structure:\n{schema_example}"
    )

# --- AI Response Parsing ---
def _parse_subtasks_from_text(
    text_response: str, 
    expected_start_id: int, 
    expected_count: Optional[int], # Can be None if AI determines count
    parent_task_id: int # For logging/debugging
) -> List[Dict[str, Any]]:
    if not isinstance(text_response, str) or not text_response.strip():
        logger.error(f"AI response for expanding task {parent_task_id} is empty or not a string.")
        raise ValueError("AI response text is empty.")

    cleaned_response = text_response.strip()
    # Remove markdown code block fences (```json ... ``` or ``` ... ```)
    if cleaned_response.startswith("```json"):
        cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith("```"): cleaned_response = cleaned_response[:-3]
    elif cleaned_response.startswith("```"):
        cleaned_response = cleaned_response[3:]
        if cleaned_response.endswith("```"): cleaned_response = cleaned_response[:-3]
    
    cleaned_response = cleaned_response.strip() # Remove any leading/trailing whitespace
    
    try:
        # Attempt to parse the entire cleaned response as JSON
        parsed_object = json.loads(cleaned_response)
    except json.JSONDecodeError as e_full:
        logger.warning(f"Initial JSON parsing failed for task {parent_task_id}: {e_full}. Response: '{cleaned_response[:250]}...' Attempting extraction.")
        # If full parse fails, try to find a JSON object embedded in the text
        # This regex looks for a structure like {"subtasks": [...]}
        match = re.search(r'\{\s*"subtasks"\s*:\s*\[.*?\]\s*\}', cleaned_response, re.DOTALL)
        if match:
            json_str = match.group(0)
            logger.info(f"Extracted potential JSON block for task {parent_task_id}: {json_str[:250]}...")
            try:
                parsed_object = json.loads(json_str)
            except json.JSONDecodeError as e_extract:
                logger.error(f"Failed to parse extracted JSON block for task {parent_task_id}: {e_extract}.")
                raise ValueError(f"AI response JSON parsing failed even after extraction: {e_extract}. Original response snippet: {cleaned_response[:250]}")
        else:
            logger.error(f"Could not find a '{{ \"subtasks\": [...] }}' structure in AI response for task {parent_task_id}.")
            raise ValueError(f"AI response JSON parsing failed: {e_full}. No valid JSON structure found. Snippet: {cleaned_response[:250]}")

    if not isinstance(parsed_object, dict) or "subtasks" not in parsed_object or not isinstance(parsed_object["subtasks"], list):
        logger.error(f"Parsed AI response for task {parent_task_id} is not a dict with a 'subtasks' list. Type: {type(parsed_object)}, Keys: {list(parsed_object.keys()) if isinstance(parsed_object,dict) else 'N/A'}")
        raise ValueError("AI response structure is invalid (expected {'subtasks': [...]}).")

    raw_subtasks_from_ai = parsed_object["subtasks"]
    validated_subtasks: List[Dict[str, Any]] = []
    
    # AI might not respect the start_id or sequential nature perfectly. We will re-assign IDs.
    current_sequential_id = expected_start_id
    
    id_map_ai_to_sequential: Dict[int, int] = {} # Maps AI's given ID to our new sequential ID

    # First pass: Validate and assign sequential IDs, build map
    temp_validated_for_dep_check: List[Subtask] = []
    for i, raw_sub_data in enumerate(raw_subtasks_from_ai):
        if not isinstance(raw_sub_data, dict):
            logger.warning(f"Subtask item at index {i} for parent {parent_task_id} is not a dict, skipping: {raw_sub_data}")
            continue
        
        ai_given_id = raw_sub_data.get("id") # Get AI's ID for mapping
        raw_sub_data_copy = raw_sub_data.copy() # Work with a copy
        raw_sub_data_copy["id"] = current_sequential_id # Enforce our sequential ID
        raw_sub_data_copy.setdefault("status", "pending")
        raw_sub_data_copy.setdefault("dependencies", [])

        try:
            subtask_model = Subtask.model_validate(raw_sub_data_copy)
            temp_validated_for_dep_check.append(subtask_model)
            if ai_given_id is not None and isinstance(ai_given_id, int): # If AI gave a valid int ID
                 id_map_ai_to_sequential[ai_given_id] = current_sequential_id
            current_sequential_id += 1
        except ValidationError as e_val:
            logger.warning(f"Subtask data for parent {parent_task_id} failed Pydantic validation (ID {current_sequential_id}): {e_val}. Data: {raw_sub_data_copy}")

    # Second pass: Remap dependencies and finalize
    for subtask_model in temp_validated_for_dep_check:
        remapped_deps: List[int] = []
        for ai_dep_id in subtask_model.dependencies: # These are AI's original dep IDs
            sequential_dep_id = id_map_ai_to_sequential.get(ai_dep_id)
            if sequential_dep_id is not None:
                # Dependency must be on a previous subtask in this batch
                if sequential_dep_id < subtask_model.id: # Compare with the *new* sequential ID
                    remapped_deps.append(sequential_dep_id)
                else:
                    logger.warning(f"Subtask {subtask_model.id} (parent {parent_task_id}) has forward/self dependency on AI ID {ai_dep_id} (remapped to {sequential_dep_id}). Removing.")
            else:
                logger.warning(f"Subtask {subtask_model.id} (parent {parent_task_id}) depends on AI ID {ai_dep_id} which was not found or invalid in this batch. Removing.")
        
        subtask_model.dependencies = sorted(list(set(remapped_deps)))
        validated_subtasks.append(subtask_model.model_dump())


    if not validated_subtasks and raw_subtasks_from_ai:
        logger.error(f"AI response for task {parent_task_id} contained subtasks, but none passed validation.")
        raise ValueError("AI response contained subtasks, but none passed validation.")
    
    # Trim to expected_count if more were generated and validated, and expected_count is set
    if expected_count is not None and len(validated_subtasks) > expected_count:
        logger.info(f"AI generated {len(validated_subtasks)} subtasks for parent {parent_task_id}, but expected {expected_count}. Trimming.")
        return validated_subtasks[:expected_count]
    
    return validated_subtasks


# expand_task_py is async because the original prompt's __main__ block uses await for it.
# However, AIService.generate_text_service is called synchronously within it.
# If AIService methods become async, then `await` will be needed for those calls.
async def expand_task_py(
    tasks_path: str,
    task_id: int,
    num_subtasks: Optional[int] = None, # User's hint for how many subtasks
    use_research: bool = False,
    additional_context: Optional[str] = None, # User-provided extra context string
    context: Optional[Dict[str, Any]] = None, # For project_root, etc.
    force: bool = False, # If true, replace existing subtasks
) -> Dict[str, Any]:
    context = context or {}
    project_root = context.get("project_root") # Used by get_default_subtasks, get_project_name
    # output_format_for_log = context.get("output_type", "cli") # For AIService telemetry & logging

    logger.info(f"Attempting to expand task ID: {task_id}. Num subtasks hint: {num_subtasks}. Research: {use_research}. Force: {force}")

    tasks_data_full = _read_json_file(tasks_path)
    if not tasks_data_full or not isinstance(tasks_data_full.get("tasks"), list):
        # This case should ideally be handled by the caller or by ensuring tasks_path always exists and is valid.
        raise FileNotFoundError(f"Tasks file {tasks_path} not found or is malformed (must be a dict with a 'tasks' list).")

    all_tasks_list: List[Dict[str, Any]] = tasks_data_full["tasks"]
    task_to_expand_dict: Optional[Dict[str, Any]] = None
    task_index_in_list = -1

    for i, t_dict in enumerate(all_tasks_list):
        if isinstance(t_dict, dict) and t_dict.get("id") == task_id:
            task_to_expand_dict = t_dict
            task_index_in_list = i
            break
    
    if task_to_expand_dict is None or task_index_in_list == -1:
        raise ValueError(f"Task with ID {task_id} not found in {tasks_path}.")
    
    # Handle existing subtasks based on 'force' flag
    existing_subtasks = task_to_expand_dict.get("subtasks", [])
    if not isinstance(existing_subtasks, list): # Ensure it's a list
        logger.warning(f"Task {task_id} has malformed 'subtasks' field (not a list). Resetting to empty list.")
        existing_subtasks = []
        task_to_expand_dict["subtasks"] = existing_subtasks


    if force and existing_subtasks:
        logger.info(f"Force flag is true: Clearing {len(existing_subtasks)} existing subtasks for task {task_id}.")
        task_to_expand_dict["subtasks"] = []
        existing_subtasks = [] # Update local reference
    
    # Determine subtask count
    # If num_subtasks not provided, use default from config or a fallback
    final_subtask_count_hint = num_subtasks
    if not isinstance(final_subtask_count_hint, int) or final_subtask_count_hint <= 0:
        try:
            final_subtask_count_hint = get_default_subtasks(project_root)
        except Exception: # Broad except if config_manager or its functions aren't fully set up
            logger.warning("Could not fetch default subtasks from config_manager. Using fallback of 3.")
            final_subtask_count_hint = 3
    if final_subtask_count_hint <= 0: final_subtask_count_hint = 3 # Absolute fallback

    # Determine the starting ID for new subtasks
    next_subtask_id_start = 1
    if existing_subtasks: # Appending to existing subtasks
        valid_existing_sub_ids = [st.get("id") for st in existing_subtasks if isinstance(st.get("id"), int)]
        if valid_existing_sub_ids:
            next_subtask_id_start = max(valid_existing_sub_ids) + 1
    
    parent_task_title = task_to_expand_dict.get("title", f"Task {task_id}")
    system_prompt = _generate_main_system_prompt(parent_task_title, final_subtask_count_hint, next_subtask_id_start)
    user_prompt = _generate_main_user_prompt(task_to_expand_dict, final_subtask_count_hint, additional_context, next_subtask_id_start)

    ai_service = AIService()
    logger.info(f"Calling AI to generate ~{final_subtask_count_hint} subtasks for parent task {task_id} (starting new subtask IDs from {next_subtask_id_start}). Research: {use_research}")
    
    ai_response_obj = ai_service.generate_text_service( 
        role="research" if use_research else "main",
        prompt=user_prompt,
        system_prompt=system_prompt,
        command_name="expand_task_py",
        # project_root=project_root, # Pass if AIService config needs it explicitly
    )

    if not ai_response_obj or "main_result" not in ai_response_obj:
        # Handle cases where AI service might return None or an unexpected structure
        raise ConnectionError("AI service did not return the expected 'main_result' dictionary.")
    
    generated_subtasks_text = ai_response_obj["main_result"]
    telemetry_data_from_ai = ai_response_obj.get("telemetry_data")

    # Parse the text response to get a list of subtask dictionaries
    # The parser will handle validation and re-IDing based on next_subtask_id_start
    parsed_new_subtasks = _parse_subtasks_from_text(
        generated_subtasks_text, 
        next_subtask_id_start, 
        final_subtask_count_hint, # Pass the count AI was asked for
        task_id
    )
    
    # Append newly parsed subtasks to the (potentially cleared) list of subtasks
    task_to_expand_dict["subtasks"].extend(parsed_new_subtasks)
    
    # Optionally, update parent task status if it was, e.g., "done" or if subtasks imply progress
    if parsed_new_subtasks and task_to_expand_dict.get("status") == "done":
        task_to_expand_dict["status"] = "pending" # Or "in-progress"
        logger.info(f"Parent task {task_id} status changed to '{task_to_expand_dict['status']}' due to new subtasks.")
    elif not task_to_expand_dict["subtasks"] and task_to_expand_dict.get("status") == "in-progress":
        # If all subtasks were removed (e.g. force with 0 new subtasks), parent might revert to pending
        task_to_expand_dict["status"] = "pending"


    # Replace the old task dict with the updated one
    all_tasks_list[task_index_in_list] = task_to_expand_dict
    # tasks_data_full["tasks"] is already updated as all_tasks_list is a reference to it.

    if not _write_json_file(tasks_path, tasks_data_full):
        raise IOError(f"Failed to write updated tasks to {tasks_path}")

    num_actually_added = len(parsed_new_subtasks)
    logger.info(f"Successfully expanded task {task_id} with {num_actually_added} new subtask(s). Total subtasks now: {len(task_to_expand_dict['subtasks'])}.")

    # --- Placeholder for generating task files ---
    # try:
    #    from .generate_task_files import generate_task_files_py # Late import
    #    generate_task_files_py(tasks_path, str(pathlib.Path(tasks_path).parent))
    #    logger.info("Task files regenerated after expansion.")
    # except Exception as e_gen:
    #    logger.warning(f"Could not regenerate task files after expansion: {e_gen}")
    logger.info("Skipping regeneration of task files (generate_task_files_py call commented out).")
    
    return {
        "success": True,
        "task_id": task_id,
        "updated_task": task_to_expand_dict, 
        "newly_added_subtasks_count": num_actually_added,
        "telemetry_data": telemetry_data_from_ai
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Starting expand_task_py test...")

    test_project_root = os.getcwd()
    dummy_tasks_file = os.path.join(test_project_root, "test_expand_task_main_tasks.json")

    async def main_expand_task_test_run():
        initial_tasks_data = {
            "metadata": {"project_name": "Expansion Test Project"},
            "tasks": [
                {"id": 1, "title": "Parent Task for Expansion", "status": "pending", "description": "A complex task that needs to be broken down into several smaller, manageable subtasks.", "details": "Initial details for the parent task.", "subtasks": []},
                {"id": 2, "title": "Another Task with Existing Subtasks", "status": "in-progress", "subtasks": [
                    {"id": 1, "title": "Old Subtask 2.1", "status": "done", "description":"done old sub", "dependencies":[]},
                    {"id": 2, "title": "Old Subtask 2.2", "status": "pending", "description":"pending old sub", "dependencies":[1]}
                ]}
            ]
        }
        with open(dummy_tasks_file, "w", encoding="utf-8") as f:
            json.dump(initial_tasks_data, f, indent=2)
        logger.info(f"Created dummy tasks file for testing: {dummy_tasks_file}")

        # Check API keys before attempting AI calls
        ai_service_instance_for_test = AIService()
        api_keys_config = ai_service_instance_for_test.config.get("api_keys", {})
        google_api_key = api_keys_config.get("google_api_key", "YOUR_GOOGLE_API_KEY")
        openai_api_key = api_keys_config.get("openai_api_key", "YOUR_OPENAI_API_KEY")
        keys_are_placeholders = google_api_key.startswith("YOUR_") or openai_api_key.startswith("YOUR_")

        if keys_are_placeholders:
            logger.warning("SKIPPING ALL expand_task_py AI TESTS: API keys in AIService MOCK_CONFIG are placeholders.")
        else:
            try:
                logger.info("\n--- Test 1: Expand Task 1 (first time, request 2 subtasks) ---")
                result1 = await expand_task_py(
                    dummy_tasks_file, task_id=1, num_subtasks=2,
                    additional_context="Focus on backend and frontend separation.",
                    context={"project_root": test_project_root}
                )
                logger.info(f"Expansion Result 1: Added {result1['newly_added_subtasks_count']} subtasks to task {result1['task_id']}. Task: {json.dumps(result1['updated_task'], indent=2)}")
                assert result1["success"]
                # AI might not return exact count, but check if it added some.
                assert result1["newly_added_subtasks_count"] > 0, "Test 1 Failed: No subtasks added."
                data_after_1 = _read_json_file(dummy_tasks_file)
                assert data_after_1 is not None
                task1_after_1 = next(t for t in data_after_1["tasks"] if t["id"] == 1)
                assert len(task1_after_1["subtasks"]) == result1["newly_added_subtasks_count"]
                if task1_after_1["subtasks"]:
                    assert task1_after_1["subtasks"][0]["id"] == 1, "Test 1 Failed: First subtask ID should be 1."
                logger.info("Test 1 PASSED.")

                logger.info("\n--- Test 2: Expand Task 2 (append 1 new subtask to existing ones) ---")
                # Task 2 has 2 subtasks (IDs 1, 2). New one should start with ID 3.
                result2 = await expand_task_py(
                    dummy_tasks_file, task_id=2, num_subtasks=1, # Request 1 new subtask
                    additional_context="This is an additional subtask for an existing list.",
                    force=False, # Append
                    context={"project_root": test_project_root}
                )
                logger.info(f"Expansion Result 2: Added {result2['newly_added_subtasks_count']} subtasks to task {result2['task_id']}. Task: {json.dumps(result2['updated_task'], indent=2)}")
                assert result2["success"]
                assert result2["newly_added_subtasks_count"] > 0
                data_after_2 = _read_json_file(dummy_tasks_file)
                assert data_after_2 is not None
                task2_after_2 = next(t for t in data_after_2["tasks"] if t["id"] == 2)
                assert len(task2_after_2["subtasks"]) == 2 + result2["newly_added_subtasks_count"] # 2 existing + new ones
                if result2["newly_added_subtasks_count"] > 0:
                     assert task2_after_2["subtasks"][-1]["id"] == 2 + result2["newly_added_subtasks_count"], "Test 2 Failed: ID of newly appended subtask is incorrect."
                logger.info("Test 2 PASSED.")

                logger.info("\n--- Test 3: Expand Task 2 again (force replace with 3 new subtasks) ---")
                result3 = await expand_task_py(
                    dummy_tasks_file, task_id=2, num_subtasks=3,
                    force=True, # Replace existing
                    context={"project_root": test_project_root}
                )
                logger.info(f"Expansion Result 3 (force): Added {result3['newly_added_subtasks_count']} subtasks to task {result3['task_id']}. Task: {json.dumps(result3['updated_task'], indent=2)}")
                assert result3["success"]
                assert result3["newly_added_subtasks_count"] > 0
                data_after_3 = _read_json_file(dummy_tasks_file)
                assert data_after_3 is not None
                task2_after_3 = next(t for t in data_after_3["tasks"] if t["id"] == 2)
                assert len(task2_after_3["subtasks"]) == result3["newly_added_subtasks_count"] 
                if task2_after_3["subtasks"]:
                    assert task2_after_3["subtasks"][0]["id"] == 1, "Test 3 Failed: Subtask IDs should restart from 1 after force."
                logger.info("Test 3 PASSED.")

            except Exception as e:
                logger.error(f"A test in main_expand_task_test_run FAILED: {e}", exc_info=True)

    import asyncio
    asyncio.run(main_expand_task_test_run())

    # Clean up the dummy file after all tests
    if os.path.exists(dummy_tasks_file):
        os.remove(dummy_tasks_file)
        logger.info(f"Removed dummy tasks file after tests: {dummy_tasks_file}")
    logger.info("\nAll expand_task_py tests completed.")

```
