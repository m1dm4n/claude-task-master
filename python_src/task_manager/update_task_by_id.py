import json
import os
import pathlib
import logging
import re
from typing import Any, Dict, List, Literal, Optional, Union, Set

from pydantic import BaseModel, Field, ValidationError

# Assuming ai_services_unified and config_manager are in the parent directory
from ..ai_services_unified import AIService
from ..config_manager import get_debug_flag, is_api_key_set, get_project_name # Import what's needed
from .add_task import _truncate 

# Placeholders
# from .generate_task_files import generate_task_files_py
# from ..ui import display_ai_usage_summary_py 

logger = logging.getLogger(__name__)

# --- Pydantic Schema ---
class SubtaskForUpdate(BaseModel): # Subtask schema for validation within UpdatedTask
    id: int
    title: str
    description: str
    status: str = "pending"
    dependencies: List[Union[int, str]] = Field(default_factory=list) # Allow string for "parent.sub" if needed by AI
    details: Optional[str] = None
    test_strategy: Optional[str] = None
    
    class Config:
        extra = 'allow' # Allow other fields AI might add, but we only care about these

class UpdatedTask(BaseModel):
    id: int # Must match the original task_id
    title: str
    description: str
    status: str # Should ideally be preserved unless prompt implies change
    dependencies: List[Union[int, str]] = Field(default_factory=list)
    priority: Optional[str] = None
    details: Optional[str] = None
    test_strategy: Optional[str] = None
    subtasks: Optional[List[SubtaskForUpdate]] = Field(default_factory=list)

    class Config:
        extra = 'ignore' # Ignore fields from AI not defined in this model (like 'reasoning')

# --- Helper for JSON read/write ---
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

# --- AI Response Parsing ---
def _parse_updated_task_from_text_py(text_response: str, expected_task_id: int) -> Dict[str, Any]:
    if not isinstance(text_response, str) or not text_response.strip():
        logger.error(f"AI response for task {expected_task_id} update is empty or not a string.")
        raise ValueError("AI response text is empty.")

    cleaned_response = text_response.strip()
    original_for_debug = cleaned_response # For logging if all parsing fails
    
    json_str_to_parse: Optional[str] = None

    # Attempt 1: Look for JSON within markdown code blocks
    # Regex to find ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json|javascript)?\s*(\{[\s\S]*?\})\s*```", cleaned_response, re.IGNORECASE | re.DOTALL)
    if match:
        json_str_to_parse = match.group(1).strip()
        logger.info(f"Extracted JSON from markdown code block for task {expected_task_id}.")
    else:
        # Attempt 2: If no markdown, try to find the first '{' and last '}'
        # This is greedy and might fail if there's other text with braces.
        first_brace = cleaned_response.find('{')
        last_brace = cleaned_response.rfind('}')
        if first_brace != -1 and last_brace > first_brace:
            potential_json_str = cleaned_response[first_brace : last_brace + 1]
            # Try to parse this substring to see if it's valid JSON
            try:
                json.loads(potential_json_str) # Test parse
                json_str_to_parse = potential_json_str
                logger.info(f"Extracted JSON content between first and last braces for task {expected_task_id}.")
            except json.JSONDecodeError:
                logger.warning(f"Content between first/last braces for task {expected_task_id} wasn't valid JSON. Will attempt to parse raw response.")
                json_str_to_parse = cleaned_response # Fallback to raw cleaned response
        else:
            # If no braces or invalid range, assume the whole cleaned response might be JSON
            json_str_to_parse = cleaned_response
            logger.info(f"No markdown or clear braces found for task {expected_task_id}, attempting to parse raw cleaned response.")
            
    if json_str_to_parse is None: # Should not happen with fallbacks, but as a safeguard
        logger.error(f"Could not identify a JSON string to parse from AI response for task {expected_task_id}.")
        raise ValueError("Could not identify JSON string in AI response.")

    try:
        parsed_task_dict = json.loads(json_str_to_parse)
    except json.JSONDecodeError as e:
        logger.error(f"Final JSON parsing failed for task {expected_task_id}: {e}. String (first 500 chars): '{json_str_to_parse[:500]}'")
        logger.debug(f"Original response for debug (first 500 chars) for task {expected_task_id}: '{original_for_debug[:500]}'")
        raise ValueError(f"Failed to parse JSON response object from AI: {e}")

    if not isinstance(parsed_task_dict, dict):
        logger.error(f"Parsed AI response for task {expected_task_id} is not a dictionary. Type: {type(parsed_task_dict)}")
        raise ValueError("Parsed AI response is not a valid JSON object (dictionary).")

    # Validate with Pydantic
    try:
        # Before full validation, ensure 'id' is present for Pydantic model if AI omits it, using expected_task_id
        if 'id' not in parsed_task_dict:
            logger.warning(f"AI response for task {expected_task_id} missing 'id'. Injecting expected ID for validation.")
            parsed_task_dict['id'] = expected_task_id
        
        validated_task_model = UpdatedTask.model_validate(parsed_task_dict)
    except ValidationError as e_val:
        logger.error(f"Pydantic validation failed for AI response (task {expected_task_id}): {e_val}. Data: {parsed_task_dict}")
        raise ValueError(f"AI response failed task structure validation: {e_val}")
    
    # Ensure ID matches (AI might hallucinate it or change it)
    if validated_task_model.id != expected_task_id:
        logger.warning(f"AI returned task with ID {validated_task_model.id}, but expected {expected_task_id}. Correcting ID.")
        validated_task_model.id = expected_task_id
        
    return validated_task_model.model_dump(exclude_none=False) # Use exclude_none=False to keep fields AI might have set to null explicitly

# update_task_by_id_py is async because its __main__ test block uses await.
# AIService.generate_text_service is called synchronously.
async def update_task_by_id_py(
    tasks_path: str,
    task_id: int,
    prompt: str, # User's instruction for what to update
    use_research: bool = False,
    context: Optional[Dict[str, Any]] = None, # For project_root, etc.
    output_format: Literal["text", "json"] = "text", # For CLI messages
) -> Optional[Dict[str, Any]]: # Returns dict with updated_task and telemetry, or None on some errors
    context = context or {}
    project_root = context.get("project_root")
    command_name_for_telemetry = context.get("command_name", "update_task_by_id_py")
    
    logger.info(f"Attempting to update task ID: {task_id} using prompt: '{prompt[:100]}...'. Research: {use_research}")

    if not isinstance(task_id, int) or task_id <= 0:
        logger.error("Invalid Task ID provided for update.")
        raise ValueError("Task ID must be a positive integer.")
    if not prompt or not prompt.strip():
        logger.error("Update prompt is empty.")
        raise ValueError("Prompt cannot be empty for task update.")

    # API Key check for research mode (example: using perplexity for research)
    # This check should ideally be inside AIService or managed by it.
    if use_research:
        research_provider = "perplexity" # Example provider for research
        # Assuming is_api_key_set can check for a specific provider
        if not is_api_key_set(research_provider, project_root=project_root):
            logger.warning(f"Research mode requested with provider '{research_provider}', but its API key is not set. Falling back to non-research mode.")
            use_research = False 

    tasks_data_full = _read_json_file(tasks_path)
    if not tasks_data_full or not isinstance(tasks_data_full.get("tasks"), list):
        raise FileNotFoundError(f"Tasks file {tasks_path} not found or is malformed (must be a dict with a 'tasks' list).")

    all_tasks_list: List[Dict[str, Any]] = tasks_data_full["tasks"]
    task_index = -1
    original_task_data_copy: Optional[Dict[str, Any]] = None

    for i, t_dict in enumerate(all_tasks_list):
        if isinstance(t_dict, dict) and t_dict.get("id") == task_id:
            task_index = i
            original_task_data_copy = t_dict.copy() # Keep a copy of the original task
            break
    
    if task_index == -1 or original_task_data_copy is None:
        raise ValueError(f"Task with ID {task_id} not found in {tasks_path}.")

    original_status = original_task_data_copy.get("status", "pending").lower()
    if original_status in ["done", "completed"]:
        logger.warning(f"Task {task_id} is already '{original_status}' and cannot be updated by AI. Change status first if updates are needed.")
        if output_format == "text":
            print(f"Info: Task {task_id} is '{original_status}' and is considered locked for AI updates. Please change its status if you need to modify it with AI.")
        return None # Indicate no update occurred

    # --- Prompt Generation ---
    project_name_str = get_project_name(project_root) or "the project"
    system_prompt = (
        f"You are an AI assistant helping to update a specific task within the software project '{project_name_str}'. "
        "You will receive the current JSON data of the task and a user prompt detailing the desired changes. "
        "Your goal is to intelligently incorporate these changes into the task's fields (title, description, details, test_strategy, subtasks, priority, dependencies, status), "
        "while preserving the task's core identity and existing completed work. "
        "Key Guidelines: "
        "1. Critical: The 'id' field of the task MUST NOT be changed. Return it exactly as provided. "
        "2. Status Preservation: Unless the user's prompt explicitly requests a status change (e.g., 'mark this as blocked', 'set status to in-progress'), "
           "you should generally preserve the original 'status' of the task. If the prompt implies a natural progression (e.g., 'start working on this'), "
           "you can update to 'in-progress' from 'pending'. "
        "3. Dependency Management: Preserve existing 'dependencies' unless the prompt clearly indicates changes to them. If adding new dependencies, ensure they are valid integer IDs. "
        "4. Subtask Handling: "
        "   - VERY IMPORTANT: Any subtasks from the original task that are marked with 'status': 'done' or 'status': 'completed' MUST be preserved exactly as they are, including their content and status. Do not modify or omit them. "
        "   - For other subtasks (pending, in-progress, etc.), update them if the prompt implies changes, or add new subtasks if requested. "
        "   - Ensure all subtasks in your response have sequential integer 'id's (can be re-sequenced if you add/remove). "
        "5. Content Updates: Modify 'title', 'description', 'details', 'priority', and 'test_strategy' as per the user's prompt to reflect the new information. Be concise but comprehensive. "
        "6. Output Format: Respond ONLY with a single, complete, and valid JSON object representing the *entire updated task*. Do not use markdown, explanations, or any text outside this JSON object. "
        "   The JSON object must conform to the UpdatedTask schema (includes fields like id, title, description, status, dependencies, priority, details, test_strategy, subtasks). "
        "   Ensure all fields expected by the schema are present, even if some are optional (provide null or empty list [] if not applicable)."
    )
    
    original_task_json_str = json.dumps(original_task_data_copy, indent=2)
    user_prompt = (
        f"The current task (ID: {task_id}) to be updated is:\n"
        f"```json\n{original_task_json_str}\n```\n\n"
        f"Please apply the following updates based on this user instruction: \"{prompt}\"\n\n"
        "Remember all guidelines, especially preserving the task ID and completed subtasks. "
        "Return only the complete JSON object for the updated task."
    )

    ai_service = AIService()
    logger.info(f"Calling AI to get updates for task {task_id}. Research mode: {use_research}")
    
    ai_response_obj = ai_service.generate_text_service( 
        role="research" if use_research else "main",
        prompt=user_prompt,
        system_prompt=system_prompt,
        command_name=command_name_for_telemetry,
        # project_root=project_root, # Pass if AIService config needs it
    )

    if not ai_response_obj or "main_result" not in ai_response_obj:
        raise ConnectionError("AI service did not return the expected 'main_result' dictionary.")
    
    raw_ai_text_output = ai_response_obj["main_result"]
    telemetry_data_from_ai = ai_response_obj.get("telemetry_data")

    # Parse the AI's text response to get the updated task dictionary
    parsed_updated_task_dict = _parse_updated_task_from_text_py(raw_ai_text_output, task_id)
    
    # --- Post-processing and merging AI's response with original task ---

    # 1. Preserve original status if AI changed it without clear instruction from prompt
    #    (More sophisticated prompt analysis might be needed for "clear instruction")
    ai_suggested_status = parsed_updated_task_dict.get("status", original_status)
    prompt_lower = prompt.lower()
    status_keywords = ["status", "state", "mark as", "set to"] # Keywords that might indicate user wants status change
    if ai_suggested_status != original_status and not any(keyword in prompt_lower for keyword in status_keywords):
        logger.warning(f"AI changed task {task_id} status from '{original_status}' to '{ai_suggested_status}' without explicit prompt. Restoring original status.")
        parsed_updated_task_dict["status"] = original_status
    elif ai_suggested_status != original_status:
         logger.info(f"Task {task_id} status changed by AI from '{original_status}' to '{ai_suggested_status}' (prompt may have indicated this).")


    # 2. Preserve completed subtasks from the original task
    final_subtasks_list: List[Dict[str, Any]] = []
    original_completed_subtasks_map: Dict[int, Dict[str, Any]] = {
        st.get("id"): st for st in original_task_data_copy.get("subtasks", []) 
        if isinstance(st, dict) and st.get("id") is not None and st.get("status", "").lower() in ["done", "completed"]
    }
    
    ai_provided_subtasks = parsed_updated_task_dict.get("subtasks", [])
    if not isinstance(ai_provided_subtasks, list): # Should be list due to Pydantic, but double check
        logger.warning(f"AI provided subtasks for task {task_id} in non-list format: {type(ai_provided_subtasks)}. Ignoring AI subtasks.")
        ai_provided_subtasks = []

    processed_ai_subtask_ids: Set[int] = set()

    for ai_sub_dict in ai_provided_subtasks:
        if not isinstance(ai_sub_dict, dict): continue # Skip malformed
        ai_sub_id = ai_sub_dict.get("id")
        if ai_sub_id is None or not isinstance(ai_sub_id, int): # Skip if no ID or invalid ID
            logger.warning(f"AI subtask for task {task_id} missing or invalid ID: {ai_sub_dict.get('title', 'N/A')}. Skipping.")
            continue

        processed_ai_subtask_ids.add(ai_sub_id)
        
        if ai_sub_id in original_completed_subtasks_map:
            # AI included a subtask that was originally completed. Use the original version.
            logger.info(f"Preserving original completed subtask {task_id}.{ai_sub_id} over AI's version.")
            final_subtasks_list.append(original_completed_subtasks_map[ai_sub_id])
        else:
            # This is a new subtask from AI, or an update to a non-completed one. Add it.
            final_subtasks_list.append(ai_sub_dict)
            
    # Add back any original completed subtasks that AI might have omitted entirely
    for org_completed_sub_id, org_completed_sub_data in original_completed_subtasks_map.items():
        if org_completed_sub_id not in processed_ai_subtask_ids:
            logger.info(f"AI omitted original completed subtask {task_id}.{org_completed_sub_id}. Adding it back.")
            final_subtasks_list.append(org_completed_sub_data)
            
    # Ensure subtasks are sorted by ID and unique (Pydantic model should handle structure of each)
    # Deduplicate by ID, preferring the entry that came first (which includes preserved originals)
    temp_dedup_subtasks: Dict[int, Dict[str,Any]] = {}
    for sub in final_subtasks_list:
        sub_id = sub.get("id")
        if sub_id is not None and sub_id not in temp_dedup_subtasks:
            temp_dedup_subtasks[sub_id] = sub
    
    parsed_updated_task_dict["subtasks"] = sorted(list(temp_dedup_subtasks.values()), key=lambda x: x.get("id", 0))


    # Update the task in the main list
    all_tasks_list[task_index] = parsed_updated_task_dict

    if not _write_json_file(tasks_path, tasks_data_full):
        # Consider how to handle write failure - rollback? For now, error out.
        raise IOError(f"Failed to write updated tasks to {tasks_path}")

    logger.info(f"Successfully updated task {task_id} in {tasks_path}.")

    # --- Placeholder for generating task files ---
    # try:
    #    from .generate_task_files import generate_task_files_py # Late import
    #    generate_task_files_py(tasks_path, str(pathlib.Path(tasks_path).parent))
    #    logger.info("Task files regenerated after update.")
    # except Exception as e_gen:
    #    logger.warning(f"Could not regenerate task files after update: {e_gen}")
    logger.info("Skipping regeneration of task files (generate_task_files_py call commented out).")


    if output_format == "text": # Basic CLI success message
        print(f"\n✅ Successfully updated Task ID: {parsed_updated_task_dict['id']}")
        print(f"  New Title: {_truncate(parsed_updated_task_dict['title'], 70)}")
        print(f"  New Status: {parsed_updated_task_dict['status']}")
        # if telemetry_data_from_ai and callable(display_ai_usage_summary_py):
        #     display_ai_usage_summary_py(telemetry_data_from_ai, "cli")
        pass

    return {
        "success": True,
        "updated_task": parsed_updated_task_dict, 
        "telemetry_data": telemetry_data_from_ai
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Starting update_task_by_id_py test...")

    test_project_root = os.getcwd()
    dummy_tasks_file_for_update = os.path.join(test_project_root, "test_update_by_id_main_tasks.json")

    async def main_update_task_by_id_test_run():
        initial_tasks_data_for_update = {
            "metadata": {"project_name": "Update Test Project"},
            "tasks": [
                {"id": 1, "title": "Original Task 1 Title", "status": "pending", 
                 "description": "Initial description for task 1.", 
                 "details": "Initial details for task 1.", 
                 "dependencies": [], "priority": "medium",
                 "subtasks": [
                     {"id": 1, "title": "Subtask 1.1 (Completed)", "status": "done", "description": "This subtask is already done and should be preserved."},
                     {"id": 2, "title": "Subtask 1.2 (Pending)", "status": "pending", "description": "This subtask is pending and can be updated by AI."}
                 ]},
                {"id": 2, "title": "Task 2 (Already Done)", "status": "done", "description": "This task is already completed."}
            ]
        }
        with open(dummy_tasks_file_for_update, "w", encoding="utf-8") as f:
            json.dump(initial_tasks_data_for_update, f, indent=2)
        logger.info(f"Created dummy tasks file for update tests: {dummy_tasks_file_for_update}")

        ai_service_instance_for_test = AIService()
        api_keys_config = ai_service_instance_for_test.config.get("api_keys", {})
        google_api_key = api_keys_config.get("google_api_key", "YOUR_GOOGLE_API_KEY")
        openai_api_key = api_keys_config.get("openai_api_key", "YOUR_OPENAI_API_KEY")
        keys_are_placeholders = google_api_key.startswith("YOUR_") or openai_api_key.startswith("YOUR_")

        if keys_are_placeholders:
            logger.warning("SKIPPING ALL update_task_by_id_py AI TESTS: API keys in AIService MOCK_CONFIG are placeholders.")
        else:
            try:
                logger.info("\n--- Test 1: Update Task 1 (pending task) ---")
                update_prompt_task1 = (
                    "The requirements for Task 1 have changed. Please update its description to 'Updated description reflecting new requirements'. "
                    "Also, enhance the details with 'Additional details about API integration and performance considerations.' "
                    "For subtasks, Subtask 1.2 should now be about 'Implement API client for Subtask 1.2' and add a new subtask 'Subtask 1.3 for UI mockups'."
                )
                result1 = await update_task_by_id_py(
                    dummy_tasks_file_for_update, 
                    task_id=1, 
                    prompt=update_prompt_task1,
                    context={"project_root": test_project_root},
                    output_format="text"
                )
                
                assert result1 is not None and result1.get("success"), "Test 1 Failed: Update was not successful or returned None."
                updated_task1 = result1.get("updated_task", {})
                logger.info(f"Update Result 1: Task {updated_task1.get('id')} updated. New Title: '{updated_task1.get('title')}'. New Description: '{updated_task1.get('description')}'")
                logger.debug(f"Full updated task 1: {json.dumps(updated_task1, indent=2)}")

                data_after_1 = _read_json_file(dummy_tasks_file_for_update)
                assert data_after_1 is not None
                task1_in_file = next((t for t in data_after_1["tasks"] if t["id"] == 1), None)
                assert task1_in_file is not None, "Test 1 Failed: Task 1 not found in file after update."
                
                # These assertions depend heavily on AI following the prompt.
                # For a unit test, you'd mock the AI response. Here, it's an integration test.
                assert "Updated description" in task1_in_file.get("description", ""), "Test 1 Failed: Description not updated as expected."
                assert "API integration" in task1_in_file.get("details", ""), "Test 1 Failed: Details not updated as expected."
                assert task1_in_file.get("status") == "pending", "Test 1 Failed: Status should have been preserved." # AI was not asked to change status

                # Check subtask preservation and updates
                subs_after_1 = task1_in_file.get("subtasks", [])
                assert len(subs_after_1) >= 2, "Test 1 Failed: Expected at least 2 subtasks (original done one + AI's changes/additions)."
                
                preserved_sub_1_1 = next((st for st in subs_after_1 if st.get("id") == 1), None)
                assert preserved_sub_1_1 is not None and preserved_sub_1_1.get("status") == "done", "Test 1 Failed: Completed Subtask 1.1 was not preserved or its status changed."
                assert preserved_sub_1_1.get("description") == "This subtask is already done and should be preserved.", "Test 1 Failed: Content of completed Subtask 1.1 changed."
                
                sub_1_2_updated = next((st for st in subs_after_1 if st.get("id") == 2), None)
                assert sub_1_2_updated is not None, "Test 1 Failed: Subtask 1.2 (pending) should still exist or be updated."
                if sub_1_2_updated: # Check if AI updated it
                    assert "API client" in sub_1_2_updated.get("title",""), "Test 1 Failed: Subtask 1.2 title not updated as prompted."
                
                # Check if AI added a new subtask (e.g., ID 3)
                new_sub_1_3 = next((st for st in subs_after_1 if st.get("id") != 1 and st.get("id") != 2), None) # Find a subtask that's not 1 or 2
                if new_sub_1_3:
                     assert "UI mockups" in new_sub_1_3.get("title",""), "Test 1 Failed: New subtask for UI mockups seems incorrect or missing."
                else:
                    logger.warning("Test 1: AI did not add a new subtask as prompted, or it was malformed.")

                logger.info("Test 1 PASSED (or partially passed, AI dependent parts noted).")

            except Exception as e_test1:
                logger.error(f"Test 1 (Update Task 1) FAILED: {e_test1}", exc_info=True)

            try:
                logger.info("\n--- Test 2: Attempt to update Task 2 (already done) ---")
                result2 = await update_task_by_id_py(
                    dummy_tasks_file_for_update, 
                    task_id=2, 
                    prompt="This update should be ignored because the task is done.",
                    output_format="text"
                )
                assert result2 is None, "Test 2 Failed: Update should have been prevented for a 'done' task and returned None."
                logger.info("Test 2 PASSED: Attempt to update 'done' task correctly prevented.")

            except Exception as e_test2:
                logger.error(f"Test 2 (Update Done Task) FAILED: {e_test2}", exc_info=True)
        
    import asyncio
    asyncio.run(main_update_task_by_id_test_run())

    # Clean up the dummy file after all tests
    if os.path.exists(dummy_tasks_file_for_update):
        os.remove(dummy_tasks_file_for_update)
        logger.info(f"Removed dummy tasks file after tests: {dummy_tasks_file_for_update}")
    logger.info("\nAll update_task_by_id_py tests completed.")


