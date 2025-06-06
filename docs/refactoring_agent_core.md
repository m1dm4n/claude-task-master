# Refactoring Plan: `src/agent_core`

## 1. Goals

*   **Decouple Core Logic:** Separate the core agent orchestration (`DevTaskAIAssistant`) from specific service implementations (LLM interaction, Project I/O, Task Management).
*   **Modularize Services:** Group related functionalities into distinct service modules, making them easier to manage, test, and potentially replace or extend.
*   **Clarify LLM Interactions:** Consolidate and abstract different LLM interaction patterns (generation, refinement, tool use).
*   **Improve Testability:** Smaller, more focused modules are generally easier to unit test.
*   **Prepare for Future Enhancements:** Lay a foundation for more complex agent behaviors, multi-agent systems, or more sophisticated tool use.

## 2. Proposed New File Structure within `src/agent_core`

The `src/agent_core` directory will be restructured to better reflect a service-oriented architecture.

```
src/agent_core/
├── __init__.py               # Exports the main DevTaskAIAssistant and key services
├── assistant.py              # DevTaskAIAssistant - core orchestrator (remains, but slimmer)
│
├── services/                 # New directory for specific service implementations
│   ├── __init__.py
│   ├── llm_service.py        # New: Consolidates LLMProvider and LLMGenerator logic
│   ├── project_service.py    # New: Combines ProjectIO and parts of PlanBuilder related to project state
│   ├── task_service.py       # New: Combines TaskOperations and DependencyManager logic
│   └── config_service.py     # New: Manages both general ConfigManager and LLMConfigManager
│
├── llm/                      # New or Refined: Focus on LLM specific configurations and prompts
│   ├── __init__.py
│   └── llm_config.py         # (Potentially merged into config_service.py or kept for LLM-specific settings)
│   └── prompts.py            # (Consolidate agent_prompts.py here or link to it)
│
└── mcp_handler.py            # New: Dedicated handler for FastMCP server interactions (extracted from assistant.py)
```

## 3. Logic Migration Details

### 3.1. `assistant.py` (`DevTaskAIAssistant`)

*   **Responsibilities:**
    *   Remain the primary entry point and orchestrator.
    *   Initialize and hold references to the new service modules (`LLMService`, `ProjectService`, `TaskService`, `ConfigService`, `MCPHandler`).
    *   Delegate high-level operations to the appropriate services.
    *   Maintain the overall agent lifecycle (`__init__`, `close`).
*   **Removed Logic:**
    *   Direct instantiation of `LLMConfigManager`, `LLMProvider`, `LLMGenerator`, `ProjectIO`, `PlanBuilder`, `TaskOperations`, `DependencyManager`.
    *   Direct MCP server management methods (moved to `MCPHandler`).
    *   Low-level implementation details of task/plan/dependency/LLM operations (delegated to services).

### 3.2. `services/config_service.py` (`ConfigService`)

*   **New Class:** `ConfigService`
*   **Responsibilities:**
    *   Initialize and manage `ConfigManager` (from `src.config_manager`).
    *   Initialize and manage `LLMConfigManager` ([`src/agent_core/llm_config.py`](src/agent_core/llm_config.py:9)).
    *   Provide unified access to both general and LLM-specific configurations.
    *   Methods: `get_model_config()`, `set_model_config()`, `get_app_config()`, etc.
*   **Source Files:**
    *   [`src/agent_core/llm_config.py`](src/agent_core/llm_config.py) (logic for `LLMConfigManager` remains or is integrated here).
    *   Initialization of `ConfigManager` from [`assistant.py`](src/agent_core/assistant.py:40).

### 3.3. `services/llm_service.py` (`LLMService`)

*   **New Class:** `LLMService`
*   **Responsibilities:**
    *   Encapsulate all direct LLM interactions.
    *   Initialize and manage `LLMProvider` logic.
    *   Initialize and manage `LLMGenerator` logic.
    *   Provide methods for different LLM tasks:
        *   `generate_text(prompt, output_type, model_type)`
        *   `generate_plan(text_content, project_goal, num_tasks, model_type)` (from `LLMGenerator.generate_plan_from_text`)
        *   `refine_item(item, instruction, model_type)` (from `LLMGenerator.refine_item_details`)
        *   `generate_subtasks(task_description, task_title, ...)` (from `LLMGenerator.generate_subtasks_for_task`)
        *   `generate_single_task_details(description_prompt, project_context, ...)` (from `LLMGenerator.generate_single_task`)
        *   `suggest_dependency_fixes(project_plan, validation_errors, ...)` (from `LLMGenerator.suggest_dependency_fixes`)
        *   `generate_code_for_task(task, ...)` (from `LLMGenerator.generate_code`)
        *   `research_query(query, tools, ...)` (from `LLMGenerator.research_query`)
    *   Handle selection of "main" vs. "research" models internally based on `model_type` parameter or configuration.
*   **Source Files:**
    *   [`src/agent_core/llm_provider.py`](src/agent_core/llm_provider.py)
    *   [`src/agent_core/llm_generator.py`](src/agent_core/llm_generator.py)

### 3.4. `services/project_service.py` (`ProjectService`)

*   **New Class:** `ProjectService`
*   **Responsibilities:**
    *   Manage the `ProjectPlan` lifecycle (loading, saving, updating).
    *   Handle project structure generation (if this remains a direct LLM call, it might be coordinated here but use `LLMService`).
    *   High-level planning operations that modify the `ProjectPlan` structure.
    *   Methods:
        *   `get_project_plan()`
        *   `save_project_plan(plan)`
        *   `initialize_project_plan()`
        *   `parse_prd_to_project_plan(prd_content, use_research)` (adapts [`PlanBuilder.plan_project_from_prd_file`](src/agent_core/plan_builder.py:82) using `LLMService`)
        *   `plan_project_from_goal(goal, title, num_tasks, use_research)` (adapts [`PlanBuilder.plan_project`](src/agent_core/plan_builder.py:29) using `LLMService`)
        *   `generate_project_structure_scaffold(plan, use_research)` (adapts existing method from `DevTaskAIAssistant` which calls `LLMGenerator`)
*   **Source Files:**
    *   [`src/agent_core/project_io.py`](src/agent_core/project_io.py)
    *   [`src/agent_core/plan_builder.py`](src/agent_core/plan_builder.py)

### 3.5. `services/task_service.py` (`TaskService`)

*   **New Class:** `TaskService`
*   **Responsibilities:**
    *   Manage all `Task` and subtask CRUD operations.
    *   Handle task status updates.
    *   Manage task dependencies (adding, removing, validating, fixing - using `LLMService` for AI-assisted fixes).
    *   Determine the next actionable task.
    *   Task expansion (breaking down tasks into subtasks - using `LLMService`).
    *   Methods:
        *   `get_task_by_id(task_id)`
        *   `get_all_tasks()`
        *   `get_tasks_by_status(status)`
        *   `add_task(description, ...)` (uses `LLMService` to generate task details)
        *   `update_task(task_data)`
        *   `remove_task(task_id)` (Needs careful implementation considering subtasks and dependencies)
        *   `update_task_status(task_id, new_status)`
        *   `expand_task_with_subtasks(task_id, num_subtasks, ...)` (uses `LLMService`)
        *   `clear_subtasks(task_id)`
        *   `add_dependency(task_id, dependency_ids)`
        *   `remove_dependency(task_id, dependency_id)`
        *   `validate_dependencies()`
        *   `fix_dependencies_ai(remove_invalid, remove_circular)` (uses `LLMService`)
        *   `get_next_actionable_task()`
        *   `get_tasks_summary_for_llm()`
*   **Source Files:**
    *   [`src/agent_core/task_operations.py`](src/agent_core/task_operations.py)
    *   [`src/agent_core/dependency_logic.py`](src/agent_core/dependency_logic.py)

### 3.6. `mcp_handler.py` (`MCPHandler`)

*   **New Class:** `MCPHandler`
*   **Responsibilities:**
    *   Manage the lifecycle of the `FastMCP` server (`start`, `stop`).
    *   Register tools and resources with the `FastMCP` server.
    *   Provide methods to `use_mcp_tool` and `access_mcp_resource`.
*   **Source Files:**
    *   MCP-related methods extracted from [`src/agent_core/assistant.py`](src/agent_core/assistant.py:426-483) (e.g., `register_mcp_tool`, `start_mcp_server`, `use_mcp_tool`, etc.).

### 3.7. `llm/llm_config.py` and `llm/prompts.py`

*   `llm_config.py`: Could be merged into `ConfigService` if its responsibilities are solely configuration management. If it contains logic beyond simple config (e.g., dynamic model selection logic not fitting `LLMProvider`), it might stay. For now, assume its data management aspect moves to `ConfigService`.
*   `prompts.py`: Either consolidate `src/agent_prompts.py` into `src/agent_core/llm/prompts.py` or have the new `LLMService` directly import from `src.agent_prompts`. The goal is to centralize prompt management related to `agent_core`'s LLM interactions.

## 4. LLM Interaction Patterns

*   **Direct Generation:** `LLMService` will expose methods like `generate_text(prompt, output_type)` for straightforward LLM calls where the primary goal is to get a structured Pydantic model or raw text.
*   **Refinement:** `LLMService.refine_item(item, instruction)` will encapsulate the pattern of providing an existing data structure and instructions to modify it.
*   **Task-Specific Generation:** Methods like `LLMService.generate_plan()`, `LLMService.generate_subtasks()`, `LLMService.generate_single_task_details()` will use specific prompts (from `llm/prompts.py` or `src.agent_prompts`) and expect particular output structures. These methods abstract the raw LLM call for common agent operations.
*   **AI-Assisted Operations:** For tasks like dependency fixing (`TaskService.fix_dependencies_ai()`), the service will prepare the context (current plan, errors) and use `LLMService.suggest_dependency_fixes()` to get AI suggestions, then apply them.
*   **Tool Use (Research):** `LLMService.research_query()` will handle interactions with the "research" model configuration, potentially including native tool invocation via `pydantic-ai`'s capabilities. The `MCPHandler` remains separate for external MCP tool usage.

## 5. Updates to Dependent Files

### 5.1. `src/cli/main.py`

*   The instantiation of `DevTaskAIAssistant` ([`src/cli/main.py:41`](src/cli/main.py:41)) will remain:
    ```python
    ctx.obj["agent"] = DevTaskAIAssistant(ctx.obj["workspace_path"])
    ```
*   Calls to methods on the `agent` object will need to be updated if the public API of `DevTaskAIAssistant` changes significantly. However, the goal is to keep the high-level API relatively stable, with `DevTaskAIAssistant` delegating to the new services. For example, if a CLI command was `agent.plan_project_from_prd_file(...)`, this method in `DevTaskAIAssistant` would now call `self.project_service.plan_project_from_prd_file(...)`.

### 5.2. `src/test.py`

*   The instantiation of `DevTaskAIAssistant` ([`src/test.py:28`](src/test.py:28)) will also remain.
    ```python
    task_master_agent = DevTaskAIAssistant(config_manager) # Note: config_manager might need to be workspace_dir based on DevTaskAIAssistant's __init__
    ```
    The `__init__` of `DevTaskAIAssistant` expects `workspace_dir`. If `config_manager` is passed directly, this will need to be adjusted in `test.py` or the `DevTaskAIAssistant` constructor needs to be more flexible (though the latter is less likely if `ConfigService` handles `ConfigManager` creation).
    **Correction:** `DevTaskAIAssistant` takes `workspace_dir`. The test will need to be:
    ```python
    # Assuming workspace_dir is defined in test.py
    task_master_agent = DevTaskAIAssistant(workspace_dir)
    ```
*   Similar to `cli/main.py`, test calls will need to adapt if `DevTaskAIAssistant`'s public methods change.

### 5.3. Internal Imports within `src/agent_core`

*   `__init__.py` ([`src/agent_core/__init__.py`](src/agent_core/__init__.py)) will need to be updated to export the new services and potentially hide the older, now internal, classes if they are not meant to be part of the public API of `agent_core`.
    ```python
    # src/agent_core/__init__.py
    from .assistant import DevTaskAIAssistant
    from .services.config_service import ConfigService
    from .services.llm_service import LLMService
    from .services.project_service import ProjectService
    from .services.task_service import TaskService
    from .mcp_handler import MCPHandler
    # Potentially other necessary exports like data models if they are primarily used with agent_core

    __all__ = [
        "DevTaskAIAssistant",
        "ConfigService",
        "LLMService",
        "ProjectService",
        "TaskService",
        "MCPHandler",
        # ...
    ]
    ```

## 6. Instantiation Flow

1.  `DevTaskAIAssistant(workspace_dir)` is created.
2.  `DevTaskAIAssistant.__init__`:
    *   Creates `ConfigService(workspace_dir)`.
        *   `ConfigService` creates `ConfigManager(workspace_dir)` and `LLMConfigManager(config_manager)`.
    *   Creates `LLMService(config_service)`.
        *   `LLMService` internally sets up `LLMProvider`-like logic and `LLMGenerator`-like logic, using configurations from `config_service`.
    *   Creates `ProjectService(workspace_dir, config_service, llm_service)`.
        *   `ProjectService` uses `config_service` for paths (e.g., `project_plan.json`) and `llm_service` for AI-driven planning.
    *   Creates `TaskService(project_service, llm_service)`.
        *   `TaskService` uses `project_service` to access/modify the project plan and `llm_service` for AI-driven task operations (refinement, subtask generation, dependency fixing).
    *   Creates `MCPHandler()`.

## 7. Risk Mitigation & Rollback

*   **Incremental Changes:** Apply changes module by module where possible.
*   **Testing:** Add/update unit tests for new service modules and integration tests for `DevTaskAIAssistant`.
*   **Version Control:** Use Git branches to manage the refactoring process, allowing for easy rollback if issues arise.
*   **Interface Stability:** Aim to keep the public interface of `DevTaskAIAssistant` as stable as possible initially to minimize immediate impact on `cli/main.py` and `test.py`. Method bodies will change to delegate to services.

This refactoring creates a more modular and maintainable structure for `agent_core`, separating concerns and making it easier to evolve the agent's capabilities.