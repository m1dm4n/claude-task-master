# Product Context
## Project Title
Task Master (AI-Driven Development Assistant)

## Overall Goal
To provide a task management system for AI-driven development, facilitating planning, execution, and tracking of development tasks with AI assistance. The system aims to integrate with various AI models and provide a robust CLI and/or agent core for developers.

## Stakeholders
*   Developers using AI for coding tasks
*   Project managers overseeing AI-assisted development

## Target Users
*   Software developers
*   AI engineers

## Core Functionality Pillars
*   AI-driven PRD parsing and task generation
*   Intelligent task refinement and expansion
*   Comprehensive task lifecycle management (CRUD, status, dependencies)
*   Configuration flexibility for AI models and providers
*   Research assistance for tasks
*   Project context persistence and recall

## Original Implementation Details
{'version_tag': 'v1-js', 'language_stack': 'JavaScript (Node.js)', 'key_features_implemented': ['Extensive CLI for task management (parse PRD, list, update, expand, set status, dependency management, complexity analysis, etc.)', 'File-based task persistence (tasks.json, individual .txt task files in tasks/)', 'Multi-AI provider support (Anthropic, Perplexity, OpenAI, Google, Mistral, OpenRouter, XAI, Azure OpenAI)', 'Configuration via .taskmasterconfig (for model settings, global params) and .env (for API keys)', 'Module for loading supported models (supported-models.json)', 'Research-backed task generation and updates using configured research models'], 'source_code_location': 'iteration/v1-js/', 'primary_interface': 'Command Line Interface (CLI)'}

## Current Python Implementation Focus
{'version_tag': 'src-python-core', 'language_stack': 'Python', 'primary_focus': 'Development of a core AI agent (`DevTaskAIAssistant`) for intelligent project planning, task refinement, and research.', 'key_components': ['DevTaskAIAssistant (agent_core.py)', 'ConfigManager (config_manager.py)', 'LLMService (llm_services.py)', 'Pydantic Data Models (data_models.py)'], 'current_llm_integration': 'pydantic-ai for structured interaction, Google Gemini (via native SDK and pydantic-ai wrapper). Currently Google-centric.', 'data_handling': 'In-memory task representation using Pydantic models. No file-based persistence observed in `src/`.', 'status_and_scope': 'Appears to be a foundational agent core, not a full CLI replacement for the JS version yet. Lacks many CLI features and multi-provider support of the JS version.', 'source_code_location': 'src/'}

## Project Documentation Overview
{'main_location': 'docs/', 'content_alignment': 'Primarily describes the features and architecture of the JavaScript CLI version.', 'key_documents_referenced': ['README.md', 'configuration.md', 'task-structure.md', 'command-reference.md', 'examples.md']}

## Identified Gaps And Deviations
{'python_vs_js_docs': ['CLI Feature Set: Python `src/` currently lacks the comprehensive CLI of the JS version and documentation.', 'Task Persistence: Python uses in-memory Pydantic models; JS/docs describe file-based persistence (`tasks.json`, `.txt` files).', 'AI Provider Flexibility: Python is Google-centric in `src/`; JS/docs describe multi-provider support.', "Configuration Management: Python's `taskmasterconfig.json` and env var usage is simpler than the JS `.taskmasterconfig`, `supported-models.json`, and broader env var schema.", 'Task ID Scheme: Python uses UUIDs; JS/docs use sequential integers.'], 'tasks_json_missing': "The file 'tasks/tasks.json', while central to the JS version's documented operation, was not found in the provided file listing for the 'tasks/' directory. Task structure was inferred from 'docs/task-structure.md' and 'tasks/task_008.txt'."}

## Future Directions Considerations
*   Clarify the strategic role of the Python implementation (replacement, backend, new tool).
*   Roadmap for feature parity if Python is to align with documented CLI capabilities.
*   Strategy for multi-provider AI support in Python.
*   Decision on task persistence mechanism for Python version.

