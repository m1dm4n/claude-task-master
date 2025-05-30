import json
import os
import pathlib
import logging
from typing import Any, Dict, List, Literal, Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, RootModel

# Assuming ai_services_unified and config_manager are in the parent directory of task_manager
from ..ai_services_unified import AIService
from ..config_manager import get_debug_flag, get_project_name # Add other config getters as needed

# Placeholder for generate_task_files and ui elements, will be properly imported/implemented later
# from .generate_task_files import generate_task_files_py
# from ..ui import display_ai_usage_summary_py 

logger = logging.getLogger(__name__)

# --- Pydantic Schemas ---
class PrdSingleTask(BaseModel):
    id: int = Field(..., gt=0)
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    details: str = ""
    test_strategy: str = Field(default="")
    priority: Literal['high', 'medium', 'low'] = "medium"
    dependencies: List[int] = Field(default_factory=list)
    status: str = "pending"
    subtasks: List[Any] = Field(default_factory=list) # Added subtasks for consistency

    @field_validator('dependencies', mode='before')
    @classmethod
    def ensure_dependencies_are_positive_int(cls, v):
        if not isinstance(v, list):
            raise ValueError('Dependencies must be a list')
        # Allow empty list
        if not v:
            return v
        for item in v:
            if not isinstance(item, int) or item <= 0:
                # The JS version allows non-positive, but schema says positive. Sticking to schema.
                raise ValueError('Dependency IDs must be positive integers')
        return v

class PrdMetadata(BaseModel):
    project_name: str
    total_tasks: int
    source_file: str
    generated_at: str # Store as string, can be parsed to datetime if needed

class PrdResponse(BaseModel):
    tasks: List[PrdSingleTask]
    metadata: PrdMetadata

# --- Helper for JSON read/write (can be moved to utils.py later) ---
def read_json_file(file_path: str) -> Optional[Dict]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from file: {file_path}")
        return None

def write_json_file(file_path: str, data: Dict) -> bool:
    try:
        os.makedirs(pathlib.Path(file_path).parent, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error writing JSON to file {file_path}: {e}")
        return False

async def parse_prd_py(
    prd_path: str,
    tasks_path: str,
    num_tasks: int,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    options = options or {}
    force: bool = options.get("force", False)
    append: bool = options.get("append", False)
    research: bool = options.get("research", False)
    project_root: Optional[str] = options.get("project_root") 
    output_format: Literal["cli", "mcp"] = options.get("output_type", "cli")

    logger.info(f"Parsing PRD file: {prd_path}, Force: {force}, Append: {append}, Research: {research}, Num Tasks: {num_tasks}")

    existing_tasks_data: List[Dict] = []
    next_id = 1
    
    # Pass project_root to AIService if its config depends on it, or ensure config_manager is used by AIService
    # For now, assuming AIService handles its config internally or via config_manager.get_config()
    ai_service = AIService() 

    try:
        if os.path.exists(tasks_path):
            if append:
                logger.info(f"Append mode: Reading existing tasks from {tasks_path}")
                loaded_data = read_json_file(tasks_path)
                if loaded_data and isinstance(loaded_data.get("tasks"), list):
                    existing_tasks_data = loaded_data["tasks"]
                    if existing_tasks_data:
                        # Ensure all existing tasks have an 'id' and it's an int
                        valid_existing_ids = [t.get("id") for t in existing_tasks_data if isinstance(t.get("id"), int)]
                        if valid_existing_ids:
                             next_id = max(valid_existing_ids) + 1
                        else:
                            logger.warning("No valid integer IDs found in existing tasks. Starting new tasks from ID 1.")
                            next_id = 1 # Fallback if no valid IDs
                        logger.info(f"Found {len(existing_tasks_data)} existing tasks. Next ID for new tasks: {next_id}")
                else:
                    logger.warning(f"Could not read existing tasks from {tasks_path} or format invalid. Proceeding without appending.")
            elif not force:
                msg = f"Output file {tasks_path} already exists. Use --force to overwrite or --append."
                logger.error(msg)
                # In CLI, we might exit or raise a specific CLI error
                raise FileExistsError(msg) 
            else:
                logger.info(f"Force flag enabled. Overwriting {tasks_path}")
        
        logger.info(f"Reading PRD content from {prd_path}")
        prd_file_path = pathlib.Path(prd_path)
        if not prd_file_path.exists():
            raise FileNotFoundError(f"PRD file not found: {prd_path}")
        with open(prd_file_path, "r", encoding="utf-8") as f:
            prd_content = f.read()
        if not prd_content.strip():
            raise ValueError(f"Input file {prd_path} is empty or contains only whitespace.")

        research_prompt_addition = ""
        if research:
            # This is a very long prompt, ensure it's correctly formatted and doesn't exceed model context limits
            # For brevity in this example, I'll use a shorter version.
            # You should copy the full detailed research prompt from your JS version if it's crucial.
            research_prompt_addition = (
                "\n\nBefore breaking down the PRD into tasks, you will perform detailed research:\n"
                "1. Technology Stack: Identify the most suitable front-end and back-end technologies, databases, APIs, and services. "
                "Consider scalability, performance, security, developer community, and ease of integration. Provide specific recommendations.\n"
                "2. Libraries & Frameworks: Suggest relevant libraries and frameworks that can accelerate development. "
                "Evaluate based on features, maturity, documentation, and licensing.\n"
                "3. Best Practices: Outline key architectural patterns, design principles (e.g., SOLID, DRY), coding standards, "
                "and security best practices (e.g., OWASP Top 10) applicable to this project.\n"
                "4. Competitive Analysis: Briefly review 1-2 similar existing products or solutions. "
                "Identify their strengths and weaknesses to inform the design and feature set.\n"
                "5. Potential Challenges: Anticipate 2-3 potential technical challenges or risks (e.g., data migration, third-party integration, performance bottlenecks) "
                "and suggest mitigation strategies.\n\n"
                "Your task breakdown should then incorporate these research findings, "
                "making specific technology choices where appropriate and ensuring tasks reflect best practices."
            )
        
        system_prompt = (
            f"You are an AI assistant specialized in analyzing Product Requirements Documents (PRDs) and "
            f"generating a structured, logically ordered, dependency-aware, and sequenced list of "
            f"development tasks in JSON format. The project name is '{get_project_name(project_root)}'.\n"
            f"{research_prompt_addition}\n\n"
            f"Analyze the provided PRD content and generate approximately {num_tasks} top-level development tasks. "
            f"If the PRD complexity is high, you may generate more tasks to ensure thoroughness. "
            f"Each task should represent a logical unit of work. "
            f"For each task, provide a clear 'title', a concise 'description' of what needs to be done, "
            f"detailed 'details' which can include specific instructions or pseudo-code for implementation, "
            f"and a 'test_strategy' outlining how the task's functionality will be verified.\n"
            f"Assign sequential 'id's to tasks, starting from {next_id}. "
            f"Infer title, description, details, and test_strategy based *only* on the PRD content and your research (if applicable). "
            f"Set 'status' to 'pending' and 'priority' to 'medium' initially for all tasks. "
            f"Define 'dependencies' as a list of IDs of other tasks that must be completed before this task can start. Ensure dependencies are valid and point to earlier tasks.\n"
            f"Respond ONLY with a valid JSON object that matches the following Pydantic schema for PrdResponse. "
            f"Do not include any explanation, comments, or markdown formatting outside of the JSON structure.\n"
            f"The JSON output must include a 'tasks' array and a 'metadata' object. The metadata should include:\n"
            f"  'project_name': '{get_project_name(project_root)}',\n"
            f"  'total_tasks': the total number of tasks you generated in the 'tasks' array,\n"
            f"  'source_file': '{pathlib.Path(prd_path).name}',\n"
            f"  'generated_at': '{datetime.now().isoformat()}'\n"
            f"Ensure all text fields like title, description, details, test_strategy are populated and not empty strings unless truly not applicable (prefer providing some detail)."
        )
        
        user_prompt = (
            f"Here's the Product Requirements Document (PRD) for the project '{get_project_name(project_root)}'. "
            f"Please break it down into approximately {num_tasks} tasks, starting task IDs from {next_id}. "
            f"Remember to include your research findings in the task details if the research mode was enabled.\n\n"
            f"PRD Content:\n```\n{prd_content}\n```\n\n"
            f"Return your response as a single, valid JSON object matching the PrdResponse Pydantic model, as specified in the system prompt. "
            f"The 'metadata.total_tasks' field must accurately reflect the number of tasks in the 'tasks' array."
        )

        logger.info(f"Calling AI service to generate tasks from PRD{' with research' if research else ''} using model for role '{'research' if research else 'main'}'...")
        
        # AIService's generate_object_service should handle the actual LLM call
        # It needs to be robust enough to return a dict that can be parsed by Pydantic
        # The schema parameter here is more of an FYI for the LLM, Pydantic validation is the enforcer.
        ai_response_dict = ai_service.generate_object_service( 
            role="research" if research else "main",
            prompt=user_prompt,
            system_prompt=system_prompt,
            command_name="parse_prd_py",
            output_type=output_format,
            # project_root=project_root # Pass if AIService config needs it explicitly
        )
        
        if not ai_response_dict or "main_result" not in ai_response_dict:
            raise ValueError("AI service did not return the expected 'main_result' dictionary.")

        raw_generated_data = ai_response_dict["main_result"]
        
        if not isinstance(raw_generated_data, dict):
             # If main_result is a string (e.g. JSON string), try to parse it.
            if isinstance(raw_generated_data, str):
                try:
                    raw_generated_data = json.loads(raw_generated_data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse AI response string as JSON: {e}")
                    logger.debug(f"Raw AI response string: {raw_generated_data[:500]}...") # Log first 500 chars
                    raise ValueError(f"AI service returned a string that is not valid JSON: {e}")
            else:
                logger.error(f"AI main_result is not a dictionary or JSON string. Type: {type(raw_generated_data)}")
                raise ValueError(f"AI service returned unexpected data type: {type(raw_generated_data)}")
        
        try:
            # Validate the entire response structure using Pydantic
            prd_response_model = PrdResponse.model_validate(raw_generated_data)
            generated_tasks_models = prd_response_model.tasks
            logger.info(f"Successfully parsed and validated AI response. Got {len(generated_tasks_models)} new tasks.")
            if prd_response_model.metadata.total_tasks != len(generated_tasks_models):
                logger.warning(f"AI metadata.total_tasks ({prd_response_model.metadata.total_tasks}) "
                               f"does not match actual number of tasks generated ({len(generated_tasks_models)}). "
                               f"Will use actual count.")
                prd_response_model.metadata.total_tasks = len(generated_tasks_models)

        except Exception as e: # Catches Pydantic's ValidationError
            logger.error(f"AI response validation failed: {e}", exc_info=get_debug_flag(project_root))
            logger.debug(f"Raw AI response data being validated: {json.dumps(raw_generated_data, indent=2)}")
            raise ValueError(f"AI service returned data that failed Pydantic validation: {e}")


        current_id_counter = next_id
        task_id_map: Dict[int, int] = {} # Maps original AI-given ID to new sequential ID
        
        processed_new_tasks: List[Dict] = []
        for task_model_from_ai in generated_tasks_models:
            new_sequential_id = current_id_counter
            # Store the AI's original ID to new ID mapping for dependency remapping
            # The AI is instructed to start from next_id, but it might not comply perfectly.
            # We use its given ID for mapping, then assign our own sequential one.
            task_id_map[task_model_from_ai.id] = new_sequential_id 
            
            task_dict = task_model_from_ai.model_dump() # Convert Pydantic model to dict
            task_dict["id"] = new_sequential_id # Enforce sequential ID
            task_dict["status"] = "pending" # Ensure status is pending
            # Priority is already validated by Pydantic model
            # Dependencies are also validated by Pydantic model (as list of positive ints)
            task_dict.setdefault("subtasks", []) # Ensure subtasks list exists
            
            processed_new_tasks.append(task_dict)
            current_id_counter += 1
            
        # Remap dependencies for the newly processed tasks
        for task_dict in processed_new_tasks:
            remapped_deps = []
            original_deps = task_dict.get("dependencies", [])
            if not isinstance(original_deps, list):
                logger.warning(f"Task {task_dict['id']} has invalid dependencies format: {original_deps}. Resetting to empty.")
                original_deps = []

            for original_dep_id in original_deps:
                if not isinstance(original_dep_id, int) or original_dep_id <=0:
                    logger.warning(f"Task {task_dict['id']} has an invalid original dependency ID {original_dep_id}. Skipping.")
                    continue

                new_dep_id = task_id_map.get(original_dep_id) # Find the new sequential ID for this original_dep_id
                
                if new_dep_id is not None:
                    # Check if the new_dep_id refers to a task that exists AND is before the current task
                    dep_task_exists_in_new = any(t.get("id") == new_dep_id for t in processed_new_tasks)
                    
                    if new_dep_id < task_dict["id"] and dep_task_exists_in_new:
                        remapped_deps.append(new_dep_id)
                    elif new_dep_id >= task_dict["id"]:
                         logger.warning(f"Task {task_dict['id']} has a forward or self dependency on AI-generated ID {original_dep_id} (remapped to {new_dep_id}). Removing.")
                    elif not dep_task_exists_in_new:
                         logger.warning(f"Dependency AI-ID {original_dep_id} (remapped to {new_dep_id}) for task {task_dict['id']} does not exist in the set of newly generated tasks. Removing.")
                else: 
                    # If original_dep_id is not in task_id_map, it means the AI referred to an ID that it didn't generate.
                    # If append mode, it could be an existing task.
                    if append and any(t.get("id") == original_dep_id for t in existing_tasks_data):
                        if original_dep_id < task_dict["id"]: # Check if it's a valid existing task ID
                            remapped_deps.append(original_dep_id) # Keep original ID if it's from existing tasks
                        else:
                            logger.warning(f"Task {task_dict['id']} has a forward or self dependency on existing task ID {original_dep_id}. Removing.")
                    else:
                        logger.warning(f"Original dependency ID {original_dep_id} for task {task_dict['id']} was not found in AI's generated tasks map and is not a valid existing task ID. Removing.")
            task_dict["dependencies"] = sorted(list(set(remapped_deps))) # Ensure unique, sorted dependencies


        final_tasks_list = (existing_tasks_data + processed_new_tasks) if append else processed_new_tasks
        
        # Update metadata
        final_metadata = prd_response_model.metadata.model_dump()
        final_metadata["total_tasks"] = len(final_tasks_list) # Total tasks in the file
        final_metadata["newly_generated_tasks"] = len(processed_new_tasks)
        final_metadata["generated_at"] = datetime.now().isoformat()
        final_metadata["source_file"] = pathlib.Path(prd_path).name
        final_metadata["project_name"] = get_project_name(project_root) or "Unknown Project"


        output_data_final = {
            "tasks": final_tasks_list,
            "metadata": final_metadata
        }
        
        if not write_json_file(tasks_path, output_data_final):
            raise IOError(f"Failed to write tasks to {tasks_path}")

        logger.info(f"Successfully {'appended' if append else 'generated'} {len(processed_new_tasks)} new tasks. Total tasks in file: {len(final_tasks_list)} at {tasks_path}")

        # Placeholder for generating markdown task files
        # try:
        #    await generate_task_files_py(tasks_path, pathlib.Path(tasks_path).parent, logger=logger)
        # except Exception as gen_files_e:
        #    logger.error(f"Failed to generate task files (continuing): {gen_files_e}")
        logger.info("Placeholder: Skipped generating individual task files for now (generate_task_files_py not implemented).")

        if output_format == "cli":
            print(f"Successfully generated {len(processed_new_tasks)} new tasks. Total tasks in file: {len(final_tasks_list)}")
            # if ai_response_dict and ai_response_dict.get("telemetry_data"):
            #     display_ai_usage_summary_py(ai_response_dict["telemetry_data"], "cli") # Placeholder
            pass

        return {
            "success": True,
            "tasks_path": tasks_path,
            "num_new_tasks": len(processed_new_tasks),
            "total_tasks_in_file": len(final_tasks_list),
            "telemetry_data": ai_response_dict.get("telemetry_data") 
        }

    except Exception as e:
        logger.error(f"Error in parse_prd_py: {e}", exc_info=get_debug_flag(project_root))
        # For CLI, specific error messages might be printed by a higher-level handler
        # Re-throw for programmatic use or MCP server to handle and provide appropriate user feedback
        raise 

if __name__ == "__main__":
    # Basic test (requires API keys in AIService MOCK_CONFIG or proper config setup)
    async def main_test_parse_prd():
        # Setup basic logging for the test
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger.info("Starting parse_prd_py test...")

        # Determine project root for testing (e.g., current directory or a temp dir)
        # For simplicity, using current dir, but a temp dir is better for isolation
        test_project_root = os.getcwd() 
        
        # Create dummy PRD file in the determined root
        test_prd_filename = "test_prd_for_parser.txt"
        test_prd_path = os.path.join(test_project_root, test_prd_filename)
        
        test_tasks_filename = "test_tasks_from_parser.json"
        test_tasks_path = os.path.join(test_project_root, test_tasks_filename)

        with open(test_prd_path, "w", encoding="utf-8") as f:
            f.write("Feature: User Authentication\nAs a user, I want to be able to register and log in to the application.\n"
                    "Acceptance Criteria:\n- Registration page with email, password.\n- Login page with email, password.\n"
                    "- Secure password hashing.\n- Session management.")
        logger.info(f"Created dummy PRD file: {test_prd_path}")

        # Ensure the AIService has API keys (using MOCK_CONFIG for this test)
        # You might need to temporarily set these in MOCK_CONFIG in ai_services_unified.py
        # or ensure your actual config mechanism works for the test environment.
        temp_service_for_key_check = AIService()
        keys_are_placeholders = (
            temp_service_for_key_check.config.get("api_keys", {}).get("google_api_key", "").startswith("YOUR_") or
            temp_service_for_key_check.config.get("api_keys", {}).get("openai_api_key", "").startswith("YOUR_")
        )

        if keys_are_placeholders:
            logger.warning("SKIPPING parse_prd_py test: API keys in AIService MOCK_CONFIG are placeholders. "
                           "Please update them with real (test) keys to run this integration test.")
            # Clean up dummy PRD file if test is skipped
            if os.path.exists(test_prd_path):
                os.remove(test_prd_path)
            return

        try:
            logger.info("Running parse_prd_py with force overwrite...")
            result = await parse_prd_py(
                prd_path=test_prd_path,
                tasks_path=test_tasks_path,
                num_tasks=2, # Requesting 2 tasks, AI might vary
                options={
                    "force": True, 
                    "project_root": test_project_root,
                    "output_type": "cli" # Simulate CLI output for test messages
                }
            )
            logger.info(f"Test result (force overwrite): {result}")
            if result and result["success"]:
                logger.info(f"Tasks written to {result['tasks_path']}")
                data = read_json_file(test_tasks_path)
                assert data is not None, "Tasks JSON file should not be None"
                assert "tasks" in data, "'tasks' key should be in JSON"
                assert len(data["tasks"]) >= 1, "Should generate at least one task"
                assert "metadata" in data, "'metadata' key should be in JSON"
                assert data["metadata"]["total_tasks"] == len(data["tasks"]), "Metadata total_tasks should match actual task count"
                assert data["metadata"]["source_file"] == test_prd_filename, "Metadata source_file should match"
                logger.info("parse_prd_py test (force overwrite) completed successfully.")

                # Test append mode
                logger.info("Running parse_prd_py in append mode...")
                # For append, num_tasks is for new tasks. Let's ask for 1 more.
                append_result = await parse_prd_py(
                    prd_path=test_prd_path, # Same PRD, but tasks should be different due to next_id
                    tasks_path=test_tasks_path,
                    num_tasks=1,
                    options={
                        "append": True,
                        "force": False, # append implies not forcing a full overwrite
                        "project_root": test_project_root,
                        "output_type": "cli"
                    }
                )
                logger.info(f"Test result (append mode): {append_result}")
                if append_result and append_result["success"]:
                    appended_data = read_json_file(test_tasks_path)
                    assert appended_data is not None
                    assert len(appended_data["tasks"]) == result["total_tasks_in_file"] + append_result["num_new_tasks"]
                    assert appended_data["metadata"]["total_tasks"] == len(appended_data["tasks"])
                    logger.info("parse_prd_py test (append mode) completed successfully.")


        except Exception as e:
            logger.error(f"Error during parse_prd_py test: {e}", exc_info=True)
        finally:
            # Clean up dummy files
            if os.path.exists(test_prd_path):
                os.remove(test_prd_path)
                logger.info(f"Removed dummy PRD file: {test_prd_path}")
            if os.path.exists(test_tasks_path):
                os.remove(test_tasks_path)
                logger.info(f"Removed dummy tasks file: {test_tasks_path}")
            # If generate_task_files_py were active, cleanup those too:
            # task_files_dir = pathlib.Path(test_tasks_path).parent
            # for f_name in os.listdir(task_files_dir):
            #     if f_name.startswith("task_") and f_name.endswith(".md") and (task_files_dir / f_name).is_file():
            #         os.remove(task_files_dir / f_name)
            # logger.info(f"Cleaned up potential task markdown files from {task_files_dir}")

    import asyncio
    asyncio.run(main_test_parse_prd())

```
