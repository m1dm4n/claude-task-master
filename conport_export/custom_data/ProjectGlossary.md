# Custom Data: ProjectGlossary

### ConPort

```json
{
  "term": "ConPort (Context Portal)",
  "definition": "A system, likely an MCP (Model Context Protocol) server, designed for storing, managing, and retrieving project-related contextual information. This includes product context, active working context, architectural decisions, system patterns, progress logs, custom data, and a project glossary. Its purpose is to act as a persistent memory and knowledge base for AI agents and human developers involved in a project.",
  "aliases": [
    "Context Portal",
    "Project Memory Bank"
  ],
  "related_tools": [
    "get_product_context",
    "update_active_context",
    "log_decision",
    "get_system_patterns",
    "log_custom_data",
    "log_progress"
  ],
  "status": "Conceptualized for use with Task Master"
}
```

---
### TaskMasterJS_v1

```json
{
  "term": "TaskMasterJS (v1)",
  "definition": "The original JavaScript (Node.js) implementation of the Task Master system, located in the 'iteration/v1-js/' directory. It is characterized by a comprehensive Command Line Interface (CLI), support for multiple AI providers (Anthropic, Perplexity, Google, OpenAI, etc.), and file-based task management (relying on 'tasks.json' and individual '.txt' task files).",
  "aliases": [
    "JS Task Master",
    "Original Task Master CLI"
  ],
  "related_patterns": [
    "JS_CLI_Application_TaskMaster_v1"
  ],
  "status": "Mature reference implementation"
}
```

---
### TaskMasterPythonCore_src

```json
{
  "term": "TaskMasterPythonCore (src)",
  "definition": "The newer Python implementation of Task Master, located in the 'src/' directory. It focuses on providing a core AI agent (`DevTaskAIAssistant`) for functionalities like project planning, task refinement, and research. It utilizes Pydantic for data modeling and `pydantic-ai` for structured LLM interactions, currently centered around Google Gemini models. It does not feature a CLI or the extensive file-based task management of the JS version in its current state.",
  "aliases": [
    "Python Task Master Agent",
    "DevTaskAIAssistant Core"
  ],
  "related_patterns": [
    "Python_AIAgentCore_Pydantic_Gemini"
  ],
  "status": "Core development/prototype"
}
```
