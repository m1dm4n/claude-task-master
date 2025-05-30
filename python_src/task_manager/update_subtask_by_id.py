import json
import os
import pathlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

# Assuming ai_services_unified and config_manager are in the parent directory
from ..ai_services_unified import AIService
from ..config_manager import get_debug_flag, get_project_name # Import what's needed

# Placeholders
# from .generate_task_files import generate_task_files_py
# from ..ui import display_ai_usage_summary_py 

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

# update_subtask_by_id_py is async because its __main__ test block uses await.
# AIService.generate_text_service is called synchronously.
async def update_subtask_by_id_py(
    tasks_path: str,
    subtask_id_str: str, # Expected format "parentId.subtaskId"
    prompt: str, # User's instruction for what to add/update in details
    use_research: bool = False, # Passed to AIService
    context: Optional[Dict[str, Any]] = None, # For project_root, session, etc.
    output_format: Literal["text", "json"] = "text", # For CLI messages
) -> Optional[Dict[str, Any]]: # Returns a dict with updated_subtask and telemetry, or None on some errors
    
    context = context or {}
    project_root = context.get("project_root")
    command_name_for_telemetry = context.get("command_name", "update_subtask_by_id_py")
    
    logger.info(
        f"Attempting to update subtask: {subtask_id_str} using prompt: '{prompt[:100]}...'. "
        f"Research mode: {use_research}"
    )

    # --- Input Validations ---
    if not isinstance(subtask_id_str, str) or "." not in subtask_id_str:
        raise ValueError(f"Invalid subtask ID format: '{subtask_id_str}'. Expected 'ParentID.SubtaskID'.")
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty for subtask update.")
    if not os.path.exists(tasks_path): # Check if tasks file exists before trying to read
        raise FileNotFoundError(f"Tasks file not found at path: {tasks_path}")

    try:
        parent_id_str_part, actual_sub_id_str_part = subtask_id_str.split(".", 1)
        parent_id_num = int(parent_id_str_part)
        actual_sub_id_num = int(actual_sub_id_str_part)
        if parent_id_num <= 0 or actual_sub_id_num <= 0: # IDs are typically positive
            raise ValueError("Parent and subtask IDs must be positive integers.")
    except ValueError: # Catches non-integer parts or non-positive if condition above is part of try
        raise ValueError(f"Invalid parent or subtask ID number in '{subtask_id_str}'. Must be positive integers.")

    tasks_data_full = _read_json_file(tasks_path)
    if not tasks_data_full or not isinstance(tasks_data_full.get("tasks"), list):
        # This implies the file was found but content is not as expected.
        raise FileNotFoundError(f"Tasks file {tasks_path} is malformed or does not contain a 'tasks' list.")

    all_tasks_list_ref: List[Dict[str, Any]] = tasks_data_full["tasks"] # Direct reference
    
    parent_task_obj_ref: Optional[Dict[str, Any]] = None
    parent_task_index_in_list = -1
    for i, task_dict_item in enumerate(all_tasks_list_ref):
        if isinstance(task_dict_item, dict) and task_dict_item.get("id") == parent_id_num:
            parent_task_obj_ref = task_dict_item # Direct reference
            parent_task_index_in_list = i
            break
    
    if parent_task_obj_ref is None:
        raise ValueError(f"Parent task with ID {parent_id_num} not found in tasks list.")
    
    # Ensure parent task has a 'subtasks' list, initialize if missing (though less likely for an update scenario)
    if "subtasks" not in parent_task_obj_ref or not isinstance(parent_task_obj_ref["subtasks"], list):
        parent_task_obj_ref["subtasks"] = [] 
    
    subtask_to_update_ref: Optional[Dict[str, Any]] = None
    subtask_index_in_parent_list = -1
    for idx, st_dict_item in enumerate(parent_task_obj_ref["subtasks"]):
        if isinstance(st_dict_item, dict) and st_dict_item.get("id") == actual_sub_id_num:
            subtask_to_update_ref = st_dict_item # Direct reference
            subtask_index_in_parent_list = idx
            break
            
    if subtask_to_update_ref is None:
        raise ValueError(f"Subtask with ID {actual_sub_id_num} not found in parent task {parent_id_num}.")

    # --- AI Interaction to get new details snippet ---
    parent_context_info = {"id": parent_task_obj_ref.get("id"), "title": parent_task_obj_ref.get("title", "N/A")}
    
    # Context from sibling subtasks
    prev_sibling_sub_info: Optional[Dict[str, Any]] = None
    if subtask_index_in_parent_list > 0:
        prev_st_dict = parent_task_obj_ref["subtasks"][subtask_index_in_parent_list - 1]
        if isinstance(prev_st_dict, dict):
            prev_sibling_sub_info = {"id": f"{parent_id_num}.{prev_st_dict.get('id')}", "title": prev_st_dict.get("title", "N/A"), "status": prev_st_dict.get("status", "N/A")}

    next_sibling_sub_info: Optional[Dict[str, Any]] = None
    if subtask_index_in_parent_list < len(parent_task_obj_ref["subtasks"]) - 1:
        next_st_dict = parent_task_obj_ref["subtasks"][subtask_index_in_parent_list + 1]
        if isinstance(next_st_dict, dict):
            next_sibling_sub_info = {"id": f"{parent_id_num}.{next_st_dict.get('id')}", "title": next_st_dict.get("title", "N/A"), "status": next_st_dict.get("status", "N/A")}

    # Prepare context string for AI, ensuring JSON serializable parts
    context_parts_for_ai = [f"Parent Task: {json.dumps(parent_context_info)}"]
    if prev_sibling_sub_info: context_parts_for_ai.append(f"Previous Sibling Subtask: {json.dumps(prev_sibling_sub_info)}")
    if next_sibling_sub_info: context_parts_for_ai.append(f"Next Sibling Subtask: {json.dumps(next_sibling_sub_info)}")
    context_parts_for_ai.append(f"Current Subtask (ID: {subtask_id_str}, Title: '{subtask_to_update_ref.get('title', 'N/A')}') existing details (for context only, do not repeat unless modifying):\n```\n{subtask_to_update_ref.get('details', '(No existing details)')}\n```")
    
    full_context_str_for_ai = "\n".join(context_parts_for_ai)

    # System and User prompts for the AI
    ai_system_prompt = (
        "You are an AI assistant that helps update the 'details' of a specific subtask for a software project. "
        "Based *only* on the user's request and the provided context (parent task, sibling subtasks, current subtask details), "
        "your primary goal is to GENERATE ONLY THE NEW TEXT content that should be ADDED to this subtask's 'details' field. "
        "Key Instructions: "
        "1. Output Format: Your response MUST be ONLY a plain text string containing the new information. Do NOT use JSON, XML, or markdown formatting (like ```) in your response. "
        "2. Conciseness: Provide only the new text. Do NOT repeat or rephrase information already present in the 'Current Subtask Details' unless the user's request specifically asks for a modification or clarification of existing points. "
        "3. Relevance: Ensure the generated text directly addresses the user's request and fits within the context of the subtask and its surroundings. "
        "4. No Fillers: Avoid conversational phrases, apologies, or self-references (e.g., 'Okay, here's the update...'). Just provide the text to be added. "
        "5. Empty Response: If the user's request doesn't warrant adding any new text to the details (e.g., it's a question, or not actionable for details), return an empty string or a very brief note like 'No specific details to add based on this request.'"
    )
    ai_user_prompt = (
        f"Here is the context for the subtask you need to update:\n{full_context_str_for_ai}\n\n"
        f"User's Request for this subtask (ID: {subtask_id_str}): \"{prompt}\"\n\n"
        "Based on the User's Request and all provided context, what is the new information or text snippet that should be appended to this subtask's 'details' field? "
        "Return ONLY this new text as a plain string."
    )

    ai_service = AIService()
    logger.info(f"Calling AI to generate details update snippet for subtask {subtask_id_str}. Research mode: {use_research}")

    ai_response_obj = ai_service.generate_text_service( 
        role="research" if use_research else "main",
        prompt=ai_user_prompt,
        system_prompt=ai_system_prompt,
        command_name=command_name_for_telemetry,
        # project_root=project_root, # Pass if AIService config needs it
    )

    generated_content_snippet_str = ""
    telemetry_data_from_ai = None
    if ai_response_obj and "main_result" in ai_response_obj and isinstance(ai_response_obj["main_result"], str):
        generated_content_snippet_str = ai_response_obj["main_result"].strip()
        telemetry_data_from_ai = ai_response_obj.get("telemetry_data")
    else:
        logger.warning(f"AI service response for subtask {subtask_id_str} did not contain the expected text string result.")

    if generated_content_snippet_str:
        timestamp_utc_str = datetime.now(timezone.utc).isoformat(timespec="seconds") # Format like YYYY-MM-DDTHH:MM:SSZ
        formatted_block_to_append = f"<info added on {timestamp_utc_str}>\n{generated_content_snippet_str}\n</info added on {timestamp_utc_str}>"
        
        current_details = subtask_to_update_ref.get("details", "")
        if not isinstance(current_details, str): # Ensure details is a string
            current_details = str(current_details) if current_details is not None else ""
            
        subtask_to_update_ref["details"] = (current_details + "\n\n" + formatted_block_to_append).strip()
        logger.info(f"Successfully appended AI-generated content to details of subtask {subtask_id_str}.")
    else:
        logger.warning(f"AI returned an empty string for subtask {subtask_id_str} update. Original details remain unchanged.")

    # Optional: Update description with a timestamp (as in JS version, if prompt is short)
    if len(prompt) < 100: # Arbitrary condition from JS, adjust as needed
        current_description = subtask_to_update_ref.get("description", "")
        if not isinstance(current_description, str): # Ensure description is a string
            current_description = str(current_description) if current_description is not None else ""
        
        update_marker = f" [Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}]"
        if update_marker not in current_description: # Avoid duplicate markers
            subtask_to_update_ref["description"] = (current_description + update_marker).strip()

    # subtask_to_update_ref is a direct reference, so parent_task_obj_ref's subtasks list is updated.
    # parent_task_obj_ref is also a direct reference, so all_tasks_list_ref is updated.
    # tasks_data_full["tasks"] already reflects these changes.

    if not _write_json_file(tasks_path, tasks_data_full):
        raise IOError(f"Failed to write updated tasks data to {tasks_path} after updating subtask {subtask_id_str}.")

    logger.info(f"Successfully updated subtask {subtask_id_str} and saved to {tasks_path}.")

    # --- Placeholder for generating task files ---
    # if context.get("generate_files", True): # Assuming generate_files might be passed via context options
    #    try:
    #        from .generate_task_files import generate_task_files_py # Late import
    #        await generate_task_files_py(tasks_path, str(pathlib.Path(tasks_path).parent))
    #        logger.info("Task files regenerated after subtask update.")
    #    except Exception as e_gen:
    #        logger.warning(f"Could not regenerate task files: {e_gen}")
    logger.info("Skipping regeneration of task files (generate_task_files_py call commented out).")


    if output_format == "text": # Basic CLI success message
        print(f"\n✅ Successfully updated Subtask ID: {subtask_id_str}")
        print(f"  Title: {subtask_to_update_ref.get('title')}")
        if generated_content_snippet_str:
            print(f"  --- Newly Added Snippet to Details ---")
            print(generated_content_snippet_str)
            print(f"  --- End of Snippet ---")
        else:
            print("  No new details were added by the AI for this update.")
        # if telemetry_data_from_ai and callable(display_ai_usage_summary_py):
        #     display_ai_usage_summary_py(telemetry_data_from_ai, "cli")
        pass

    return {
        "success": True,
        "updated_subtask": subtask_to_update_ref, 
        "telemetry_data": telemetry_data_from_ai
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Starting update_subtask_by_id_py test...")

    test_project_root = os.getcwd()
    dummy_tasks_file_for_update_sub = os.path.join(test_project_root, "test_update_subtask_main_tasks.json")

    async def main_update_subtask_by_id_test_run():
        initial_tasks_data_for_update_sub = {
            "metadata": {"project_name": "Update Subtask Test Project"},
            "tasks": [
                {"id": 1, "title": "Parent Task One", "status": "in-progress", "subtasks": [
                    {"id": 1, "title": "Subtask 1.1 - Initial", "status": "pending", "description": "Initial description for subtask 1.1.", "details": "Original details content for subtask 1.1."},
                    {"id": 2, "title": "Subtask 1.2 - Sibling", "status": "pending", "description": "Sibling subtask for context.", "details": "Details for 1.2."}
                ]},
                {"id": 2, "title": "Parent Task Two", "status": "pending"}
            ]
        }
        with open(dummy_tasks_file_for_update_sub, "w", encoding="utf-8") as f:
            json.dump(initial_tasks_data_for_update_sub, f, indent=2)
        logger.info(f"Created dummy tasks file for update_subtask tests: {dummy_tasks_file_for_update_sub}")

        # Check API keys before attempting AI calls
        ai_service_instance_for_test = AIService()
        api_keys_config = ai_service_instance_for_test.config.get("api_keys", {})
        google_api_key = api_keys_config.get("google_api_key", "YOUR_GOOGLE_API_KEY")
        openai_api_key = api_keys_config.get("openai_api_key", "YOUR_OPENAI_API_KEY")
        keys_are_placeholders = google_api_key.startswith("YOUR_") or openai_api_key.startswith("YOUR_")

        if keys_are_placeholders:
            logger.warning("SKIPPING update_subtask_by_id_py AI TEST: API keys in AIService MOCK_CONFIG are placeholders.")
        else:
            try:
                logger.info("\n--- Test 1: Update details of Subtask 1.1 ---")
                update_prompt_for_subtask1_1 = "Please add information regarding the new authentication flow using OAuth2. Specifically mention the redirect URI and scope requirements."
                
                result1 = await update_subtask_by_id_py(
                    dummy_tasks_file_for_update_sub, 
                    subtask_id_str="1.1", 
                    prompt=update_prompt_for_subtask1_1,
                    context={"project_root": test_project_root, "command_name": "test_update_sub_1.1"},
                    output_format="text"
                )
                
                assert result1 is not None and result1.get("success"), "Test 1 Failed: Update was not successful or returned None."
                updated_subtask1_1 = result1.get("updated_subtask", {})
                logger.info(f"Update Result 1: Subtask {updated_subtask1_1.get('parent_task_id')}.{updated_subtask1_1.get('id')} updated.")
                logger.debug(f"Full updated subtask 1.1: {json.dumps(updated_subtask1_1, indent=2)}")

                data_after_1 = _read_json_file(dummy_tasks_file_for_update_sub)
                assert data_after_1 is not None
                parent1_after_1 = next(t for t in data_after_1["tasks"] if t["id"] == 1)
                sub1_1_in_file = next(st for st in parent1_after_1["subtasks"] if st["id"] == 1)
                
                # Assertions depend on AI's output, check for timestamp and some keywords
                assert "<info added on" in sub1_1_in_file.get("details", ""), "Test 1 Failed: Timestamp block missing in details."
                assert "OAuth2" in sub1_1_in_file.get("details", "") or "redirect URI" in sub1_1_in_file.get("details", ""), "Test 1 Failed: Expected keywords from prompt not found in updated details."
                # Description timestamp check
                assert "[Updated:" in sub1_1_in_file.get("description", ""), "Test 1 Failed: Description update timestamp missing."
                logger.info("Test 1 PASSED (or AI dependent parts noted).")

            except Exception as e_test1:
                logger.error(f"Test 1 (Update Subtask 1.1) FAILED: {e_test1}", exc_info=True)
        
    import asyncio
    asyncio.run(main_update_subtask_by_id_test_run())

    # Clean up the dummy file after all tests
    if os.path.exists(dummy_tasks_file_for_update_sub):
        os.remove(dummy_tasks_file_for_update_sub)
        logger.info(f"Removed dummy tasks file after tests: {dummy_tasks_file_for_update_sub}")
    logger.info("\nAll update_subtask_by_id_py tests completed.")

