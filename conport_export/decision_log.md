# Decision Log

---
## Decision
*   [2025-05-31 08:30:18] Task Identification Scheme: Python uses UUIDs, JS/Docs use Sequential Integers.

## Rationale
*   Python's `Task` model in `data_models.py` specifies `id: uuid.UUID`. The `agent_core.py` ensures UUIDs are assigned. JS version, as seen in `tasks/task_008.txt` and implied by CLI operations, uses integer IDs.

## Implementation Details
*   Python uses `uuid.uuid4()`. JS logic implies integer-based indexing and referencing.

---
## Decision
*   [2025-05-31 08:29:18] Task Persistence Model Differs: Python In-Memory vs. JS File-Based.

## Rationale
*   Python's `src/` uses Pydantic models for tasks (`ProjectPlan`, `Task`, `Subtask`) with no observed file read/write operations for a `tasks.json`-like store. JS version and documentation describe a system reliant on `tasks.json` and individual `.txt` task files.

## Implementation Details
*   Python data models in `data_models.py`. JS file operations are implicit in `task-manager.js` functions and CLI command actions.

---
## Decision
*   [2025-05-31 08:29:10] Python Implementation Prioritizes Google Gemini for LLM Services.

## Rationale
*   `src/llm_services.py` and `src/config_manager.py` are currently hardcoded or default to Google provider and Gemini models. This contrasts with the JS version's documented multi-provider capability (`supported-models.json`, extensive API key configurations).

## Implementation Details
*   `LLMService` class directly initializes Google GenAI client and uses Gemini model IDs. `ConfigManager` defaults also point to Gemini.

---
## Decision
*   [2025-05-31 08:28:30] Architectural Divergence: Python `src/` implements an AI agent core, not a direct port or replacement of the JS CLI.

## Rationale
*   Analysis of `src/agent_core.py` shows focus on Pydantic models, AI planning/refinement methods, and Google Gemini integration, lacking the CLI structure, extensive command parsing, file I/O for tasks, and multi-provider support present in `iteration/v1-js/` and described in `docs/`.

## Implementation Details
*   Python version uses `DevTaskAIAssistant` class for core logic. JS version uses `commander` for CLI and modular scripts for functionality.
