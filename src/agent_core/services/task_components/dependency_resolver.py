from typing import List, Dict, Optional, Literal
from uuid import UUID
import json
import logfire
from datetime import datetime, timezone
from src.data_models import ProjectPlan, Task, DependencyFixesLLMOutput
from src.agent_core.services.llm_service import LLMService
from src.agent_prompts import FIX_DEPENDENCIES_PROMPT


class DependencyResolver:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def suggest_dependency_fixes(self, project_plan: ProjectPlan, validation_errors: Dict[str, List[str]], model_type: Literal["main", "research"] = "main") -> Optional[ProjectPlan]:
        """
        Suggests fixes for dependency issues in the project plan using AI assistance.
        """
        logfire.info(f"Suggesting dependency fixes using {model_type} model")

        current_plan_json = project_plan.model_dump_json(indent=2)
        errors_json = json.dumps(validation_errors, indent=2)

        full_prompt = (
            f"{FIX_DEPENDENCIES_PROMPT}\n\n"
            f"Current Project Plan:\n{current_plan_json}\n\n"
            f"Dependency Validation Errors:\n{errors_json}\n\n"
            f"Please return a JSON object conforming to `DependencyFixesLLMOutput` with suggested fixes. "
            f"Focus on resolving the reported errors by modifying dependencies or task structures."
        )

        try:
            llm_response: DependencyFixesLLMOutput = await self.llm_service.generate_text(
                full_prompt,
                model_type=model_type,
                output_type=DependencyFixesLLMOutput
            )
            
            logfire.info(f"Raw LLM response for dependency fixes: {llm_response.model_dump_json(indent=2)}")

            if llm_response and llm_response.suggested_fixes:
                logfire.info(f"Successfully received {len(llm_response.suggested_fixes)} dependency fix suggestions from LLM.")
                
                updated_plan = project_plan.model_copy(deep=True)
                
                allowed_to_fix_missing_ids = bool(validation_errors.get("missing_ids"))
                allowed_to_fix_circular = bool(validation_errors.get("circular"))

                for fix in llm_response.suggested_fixes:
                    is_missing_id_fix = False
                    is_circular_fix = False

                    if allowed_to_fix_missing_ids:
                        for error_msg in validation_errors.get("missing_ids", []):
                            if str(fix.task_id) in error_msg:
                                is_missing_id_fix = True
                                break
                    
                    if allowed_to_fix_circular:
                        for error_msg in validation_errors.get("circular", []):
                            if str(fix.task_id) in error_msg:
                                is_circular_fix = True
                                break
                    
                    if (is_missing_id_fix and allowed_to_fix_missing_ids) or \
                       (is_circular_fix and allowed_to_fix_circular):
                        pass
                    else:
                        logfire.warning(f"Skipping LLM suggested fix for task {fix.task_id} as it does not correspond to an allowed or reported error type based on input flags.")
                        continue

                    found_task = False
                    for task in updated_plan.tasks:
                        if task.id == fix.task_id:
                            task.dependencies = fix.new_dependencies
                            task.updated_at = datetime.now(timezone.utc)
                            found_task = True
                            logfire.info(f"Applied fix for task {task.id}: new dependencies {task.dependencies}")
                            break
                        for subtask in task.subtasks:
                            if subtask.id == fix.task_id:
                                subtask.dependencies = fix.new_dependencies
                                subtask.updated_at = datetime.now(timezone.utc)
                                found_task = True
                                logfire.info(f"Applied fix for subtask {subtask.id}: new dependencies {subtask.dependencies}")
                                break
                    if not found_task:
                        logfire.warning(f"Task/subtask with ID {fix.task_id} not found in plan for applying fix.")
                
                return updated_plan
            else:
                logfire.warning("LLM did not provide dependency fix suggestions or returned an empty list.")
                return project_plan
        except Exception as e:
            logfire.error(f"Error suggesting dependency fixes: {e}", exc_info=True)
            raise RuntimeError(f"Dependency fix suggestion failed: {e}") from e