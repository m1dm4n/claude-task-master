import json
import os
import pathlib
import logging
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Assuming ai_services_unified and config_manager are in the parent directory
from .list_tasks import _truncate
from ..ai_services_unified import AIService
from ..config_manager import get_default_priority, get_project_name # Import what's needed

# Placeholders - these will be properly imported or implemented later
# from .generate_task_files import generate_task_files_py
# from ..ui import display_ai_usage_summary_py, get_status_with_color_py (if needed for CLI output)

logger = logging.getLogger(__name__)

# --- Pydantic Schema for AI Output ---
class AiTaskData(BaseModel):
    title: str = Field(..., description="Clear, concise title for the task")
    description: str = Field(..., description="A one or two sentence description of the task")
    details: str = Field(default="", description="In-depth implementation details, considerations, and guidance")
    test_strategy: str = Field(default="", description="Detailed approach for verifying task completion")
    dependencies: Optional[List[int]] = Field(default_factory=list, description="Array of task IDs that this task depends on")


# --- Helper for JSON read/write (can be moved to utils.py later) ---
def _read_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # If tasks file doesn't exist, it's fine, we'll create it.
        logger.info(f"Tasks file {file_path} not found. Will create a new one.")
        return {"tasks": [], "metadata": {}} 
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from file: {file_path}. Starting with empty tasks.")
        return {"tasks": [], "metadata": {}} # Treat as empty if malformed

def _write_json_file(file_path: str, data: Dict[str, Any]) -> bool:
    try:
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

# Note: add_task_py is defined as async because the original prompt's __main__ block uses await.
# However, AIService.generate_object_service is called synchronously.
# If AIService becomes async, then `await` will be needed for that call.
async def add_task_py(
    tasks_path: str,
    prompt: Optional[str] = None, 
    dependencies: Optional[List[int]] = None,
    priority: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    output_format: Literal["text", "json"] = "text", # Used for CLI messages
    manual_task_data: Optional[Dict[str, Any]] = None,
    use_research: bool = False,
) -> Dict[str, Any]:
    
    context = context or {}
    project_root = context.get("project_root")
    command_name = context.get("command_name", "add_task_py")
    
    dependencies = dependencies or []
    
    # Use get_default_priority from config_manager if available, else a hardcoded default
    default_priority_val = "medium"
    try:
        default_priority_val = get_default_priority(project_root)
    except Exception: # Broad except if config_manager or its functions aren't fully set up
        logger.warning("Could not fetch default priority from config_manager. Using 'medium'.")

    effective_priority = priority or default_priority_val

    logger.info(
        f"Adding new task. Prompt: '{prompt if prompt else 'N/A (manual)'}' "
        f"Priority: {effective_priority}, Dependencies: {dependencies}, "
        f"Research: {use_research}, Manual: {bool(manual_task_data)}"
    )

    ai_service = AIService() 
    telemetry_data_from_ai: Optional[Dict] = None

    try:
        tasks_data_full = _read_json_file(tasks_path)
        if not tasks_data_full or not isinstance(tasks_data_full.get("tasks"), list):
            logger.warning(f"Invalid or missing tasks data in {tasks_path}. Initializing with empty tasks list.")
            tasks_data_full = {"tasks": [], "metadata": tasks_data_full.get("metadata", {})} # Preserve metadata if any
        
        all_tasks_list: List[Dict[str, Any]] = tasks_data_full["tasks"]

        highest_id = 0
        if all_tasks_list:
            valid_ids = [task.get("id", 0) for task in all_tasks_list if isinstance(task.get("id"), int)]
            if valid_ids:
                highest_id = max(valid_ids)
        new_task_id = highest_id + 1

        # Validate dependencies
        valid_dependencies: List[int] = []
        if dependencies:
            existing_task_ids = {task.get("id") for task in all_tasks_list if isinstance(task.get("id"), int)}
            for dep_id in dependencies:
                if isinstance(dep_id, int) and dep_id in existing_task_ids:
                    valid_dependencies.append(dep_id)
                else:
                    logger.warning(f"Invalid or non-existent dependency ID: {dep_id}. It will be removed.")
        
        task_creation_data: AiTaskData

        if manual_task_data:
            logger.info(f"Creating task manually with ID {new_task_id}")
            try:
                task_creation_data = AiTaskData(
                    title=manual_task_data.get("title", f"Task {new_task_id}"), # Default title if missing
                    description=manual_task_data.get("description", "No description provided."),
                    details=manual_task_data.get("details", ""),
                    test_strategy=manual_task_data.get("test_strategy", ""),
                    dependencies=valid_dependencies 
                )
            except Exception as e: 
                logger.error(f"Manual task data validation failed: {e}")
                raise ValueError(f"Invalid manual task data: {e}")
        else:
            if not prompt:
                raise ValueError("Prompt is required for AI-powered task creation.")
            logger.info(f"Generating task data with AI for task ID {new_task_id}. Research: {use_research}")
            
            context_tasks_str = "\nRelevant existing tasks for context (max 10, most recent first):\n"
            if all_tasks_list:
                count = 0
                for task in reversed(all_tasks_list): # Show recent tasks
                    if count < 10:
                         context_tasks_str += f"- ID {task.get('id', 'N/A')}: {task.get('title', 'Untitled')}\n"
                         count +=1
                    else:
                        break
            else:
                context_tasks_str = "\nNo existing tasks for context.\n"

            project_name_str = "the current project"
            try:
                project_name_str = get_project_name(project_root) or project_name_str
            except Exception:
                 logger.warning("Could not fetch project name from config_manager.")


            ai_system_prompt = (
                "You are an AI assistant that creates well-structured development tasks for a software project. "
                f"The project is '{project_name_str}'. "
                "Generate a single new task based on the user's request. Adhere strictly to the provided JSON schema (AiTaskData). "
                "The 'dependencies' array should only contain task IDs (integers) of prerequisite tasks that already exist. "
                "Analyze the provided context of existing tasks to determine appropriate dependencies. If no existing tasks are relevant, dependencies should be empty. "
                "Ensure title, description, details, and test_strategy are comprehensive and actionable."
            )
            ai_user_prompt = (
                f"User's request for a new task (which will be assigned ID {new_task_id}): \"{prompt}\"\n"
                f"{context_tasks_str}\n"
                f"Explicitly suggested dependencies by the user (validate if they exist and make sense): {valid_dependencies if valid_dependencies else 'None'}.\n"
                f"The new task will have priority: {effective_priority}.\n"
                f"Respond ONLY with a single, valid JSON object matching the AiTaskData Pydantic schema. Do not add any explanations or markdown."
            )

            ai_response = ai_service.generate_object_service( 
                role="research" if use_research else "main",
                prompt=ai_user_prompt,
                system_prompt=ai_system_prompt,
                command_name=command_name,
            )
            
            if not ai_response or "main_result" not in ai_response:
                raise ValueError("AI service did not return 'main_result'.")
            
            raw_ai_output = ai_response["main_result"]
            telemetry_data_from_ai = ai_response.get("telemetry_data")

            try:
                # If raw_ai_output is a string, parse it first
                if isinstance(raw_ai_output, str):
                    try:
                        raw_ai_output = json.loads(raw_ai_output)
                    except json.JSONDecodeError as json_e:
                        logger.error(f"AI output was a string but not valid JSON: {json_e}. Output: {raw_ai_output[:200]}...")
                        raise ValueError(f"AI output was a string but not valid JSON: {json_e}")

                task_creation_data = AiTaskData.model_validate(raw_ai_output)
                logger.info("Successfully parsed and validated AI response for new task.")
            except Exception as e: 
                logger.error(f"AI task data validation failed: {e}. Raw AI output: {raw_ai_output}")
                raise ValueError(f"AI returned data that failed validation: {e}")

            # Dependency handling: Prioritize user-provided valid dependencies.
            # If AI suggests dependencies, validate them. Merge or replace as per desired logic.
            # Current: If user provided valid_dependencies, use them. Otherwise, use AI's (validated).
            if valid_dependencies: # User provided some valid dependencies
                task_creation_data.dependencies = valid_dependencies
                logger.info(f"Using user-provided valid dependencies: {valid_dependencies}")
            elif task_creation_data.dependencies: # AI provided dependencies
                ai_deps = task_creation_data.dependencies
                validated_ai_deps = []
                existing_task_ids_for_ai_check = {task.get("id") for task in all_tasks_list if isinstance(task.get("id"), int)}
                for dep_id in ai_deps:
                    if dep_id in existing_task_ids_for_ai_check:
                        validated_ai_deps.append(dep_id)
                    else:
                        logger.warning(f"AI suggested non-existent dependency ID: {dep_id}. Removing.")
                task_creation_data.dependencies = validated_ai_deps
                logger.info(f"Using AI-suggested (and validated) dependencies: {validated_ai_deps}")
            else: # No deps from user or AI
                 task_creation_data.dependencies = []


        new_task_dict = {
            "id": new_task_id,
            "title": task_creation_data.title,
            "description": task_creation_data.description,
            "details": task_creation_data.details,
            "test_strategy": task_creation_data.test_strategy,
            "status": "pending", # Default status for new tasks
            "dependencies": sorted(list(set(task_creation_data.dependencies or []))), # Ensure unique and sorted
            "priority": effective_priority,
            "subtasks": [] 
        }

        all_tasks_list.append(new_task_dict)
        # tasks_data_full["tasks"] = all_tasks_list # Already modified in place if all_tasks_list is a reference

        if not _write_json_file(tasks_path, tasks_data_full):
            # Consider how to handle write failure - rollback add? For now, error out.
            raise IOError(f"Failed to write updated tasks to {tasks_path}")

        logger.info(f"Successfully added new task with ID {new_task_id} to {tasks_path}")

        # --- Placeholder for generating task files ---
        # try:
        #    from .generate_task_files import generate_task_files_py # Late import if needed
        #    generate_task_files_py(tasks_path, str(pathlib.Path(tasks_path).parent))
        #    logger.info("Task files regenerated.")
        # except Exception as e_gen:
        #    logger.warning(f"Could not regenerate task files: {e_gen}")
        logger.info("Skipping regeneration of task files (generate_task_files_py call commented out).")


        if output_format == "text":
            print(f"\n✅ New task added successfully:")
            print(f"  ID: {new_task_dict['id']}")
            print(f"  Title: {_truncate(new_task_dict['title'], 70)}")
            print(f"  Status: {new_task_dict['status']}")
            print(f"  Priority: {new_task_dict['priority']}")
            print(f"  Dependencies: {new_task_dict['dependencies']}")
            # if telemetry_data_from_ai and callable(display_ai_usage_summary_py):
            #     display_ai_usage_summary_py(telemetry_data_from_ai, "cli")
            pass
            
        return {
            "success": True,
            "new_task_id": new_task_id,
            "new_task_data": new_task_dict, # Return the full task data
            "telemetry_data": telemetry_data_from_ai
        }

    except Exception as e:
        logger.error(f"Error in add_task_py: {e}", exc_info=True)
        if output_format == "text": # Basic error for CLI
            print(f"Error adding task: {e}")
        raise # Re-throw for programmatic or MCP server handling


if __name__ == "__main__":
    # Setup basic logging for the test
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Starting add_task_py test...")

    test_project_root = os.getcwd()
    dummy_tasks_file = os.path.join(test_project_root, "test_add_task_main_tasks.json")

    # Ensure clean state for tests by removing the dummy file if it exists
    if os.path.exists(dummy_tasks_file):
        os.remove(dummy_tasks_file)
        logger.info(f"Removed existing dummy tasks file: {dummy_tasks_file}")

    async def main_add_task_test_run():
        # Test 1: Manual task creation into a new/empty file
        logger.info("\n--- Test 1: Manual Task Creation (new file) ---")
        manual_data_1 = {
            "title": "Manual Task One (High Prio)",
            "description": "This is the first manually added task.",
            "details": "Detailed instructions for task one.",
            "test_strategy": "Test task one thoroughly."
        }
        try:
            result1 = await add_task_py(
                dummy_tasks_file, 
                manual_task_data=manual_data_1, 
                priority="high",
                dependencies=[],
                output_format="text",
                context={"project_root": test_project_root}
            )
            logger.info(f"Manual add result 1: {json.dumps(result1, indent=2)}")
            assert result1["success"] and result1["new_task_id"] == 1, "Test 1 Failed: Success or ID mismatch"
            
            data_after_1 = _read_json_file(dummy_tasks_file)
            assert data_after_1 and len(data_after_1.get("tasks", [])) == 1, "Test 1 Failed: Task count mismatch"
            assert data_after_1["tasks"][0]["title"] == "Manual Task One (High Prio)", "Test 1 Failed: Title mismatch"
            logger.info("Test 1 PASSED.")

        except Exception as e:
            logger.error(f"Test 1 (Manual task add) FAILED: {e}", exc_info=True)


        # Test 2: AI-powered task creation (requires AIService to be functional with keys)
        logger.info("\n--- Test 2: AI-Powered Task Creation ---")
        ai_service_instance_for_test = AIService() # Assuming MOCK_CONFIG is used if no other config
        api_keys_config = ai_service_instance_for_test.config.get("api_keys", {})
        google_api_key = api_keys_config.get("google_api_key", "YOUR_GOOGLE_API_KEY")
        openai_api_key = api_keys_config.get("openai_api_key", "YOUR_OPENAI_API_KEY")

        if google_api_key.startswith("YOUR_") or openai_api_key.startswith("YOUR_"):
            logger.warning("SKIPPING Test 2 (AI add_task_py): API keys in AIService MOCK_CONFIG are placeholders.")
        else:
            try:
                result2 = await add_task_py(
                    dummy_tasks_file,
                    prompt="Develop a new feature for user profile image uploads",
                    dependencies=[1], # Depends on the manually added task 1
                    priority="medium",
                    use_research=False, # Set to True to test research mode if desired
                    output_format="text",
                    context={"project_root": test_project_root, "command_name": "test_ai_add"}
                )
                logger.info(f"AI add result 2: {json.dumps(result2, indent=2)}")
                assert result2["success"] and result2["new_task_id"] == 2, "Test 2 Failed: Success or ID mismatch"
                
                data_after_2 = _read_json_file(dummy_tasks_file)
                assert data_after_2 and len(data_after_2.get("tasks", [])) == 2, "Test 2 Failed: Task count mismatch"
                # Check if AI respected the dependency or if it was overridden
                # The current logic prioritizes user-provided valid dependencies if AI doesn't provide any,
                # or validates AI's if it does. If both, it uses user's.
                assert data_after_2["tasks"][1].get("dependencies") == [1], f"Test 2 Failed: Dependencies mismatch. Got {data_after_2['tasks'][1].get('dependencies')}"
                logger.info("Test 2 PASSED.")
            except Exception as e:
                logger.error(f"Test 2 (AI task add) FAILED: {e}", exc_info=True)
        
        # Test 3: Add another AI task to check ID increment and empty dependencies
        logger.info("\n--- Test 3: AI-Powered Task Creation (ID Increment, No Deps) ---")
        if google_api_key.startswith("YOUR_") or openai_api_key.startswith("YOUR_"):
            logger.warning("SKIPPING Test 3 (AI add_task_py 2): API keys are placeholders.")
        else:
            try:
                result3 = await add_task_py(
                    dummy_tasks_file,
                    prompt="Setup project linting and formatting tools",
                    dependencies=[], # No explicit dependencies
                    priority="low",
                    output_format="json", # Test JSON output
                    context={"project_root": test_project_root}
                )
                logger.info(f"AI add result 3 (JSON): {json.dumps(result3, indent=2)}")
                assert result3["success"] and result3["new_task_id"] == 3, "Test 3 Failed: Success or ID mismatch"
                
                data_after_3 = _read_json_file(dummy_tasks_file)
                assert data_after_3 and len(data_after_3.get("tasks", [])) == 3, "Test 3 Failed: Task count mismatch"
                # AI might suggest dependencies, check if they are empty or valid if present
                newly_added_task_deps = data_after_3["tasks"][2].get("dependencies", [])
                assert isinstance(newly_added_task_deps, list), "Test 3 Failed: Dependencies should be a list"
                logger.info(f"Test 3 PASSED. Dependencies for task 3: {newly_added_task_deps}")

            except Exception as e:
                logger.error(f"Test 3 (AI task add 2) FAILED: {e}", exc_info=True)

    import asyncio
    asyncio.run(main_add_task_test_run())

    # Clean up the dummy file after all tests
    if os.path.exists(dummy_tasks_file):
        os.remove(dummy_tasks_file)
        logger.info(f"Removed dummy tasks file after tests: {dummy_tasks_file}")
    logger.info("\nAll add_task_py tests completed.")