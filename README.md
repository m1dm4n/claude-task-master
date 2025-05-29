# Task Master [![GitHub stars](https://img.shields.io/github/stars/eyaltoledano/claude-task-master?style=social)](https://github.com/eyaltoledano/claude-task-master/stargazers)

[![CI](https://github.com/eyaltoledano/claude-task-master/actions/workflows/ci.yml/badge.svg)](https://github.com/eyaltoledano/claude-task-master/actions/workflows/ci.yml) [![npm version](https://badge.fury.io/js/task-master-ai.svg)](https://badge.fury.io/js/task-master-ai) [![Discord](https://dcbadge.limes.pink/api/server/https://discord.gg/taskmasterai?style=flat)](https://discord.gg/taskmasterai) [![License: MIT with Commons Clause](https://img.shields.io/badge/license-MIT%20with%20Commons%20Clause-blue.svg)](LICENSE)

### By [@eyaltoledano](https://x.com/eyaltoledano) & [@RalphEcom](https://x.com/RalphEcom)

[![Twitter Follow](https://img.shields.io/twitter/follow/eyaltoledano?style=flat)](https://x.com/eyaltoledano)
[![Twitter Follow](https://img.shields.io/twitter/follow/RalphEcom?style=flat)](https://x.com/RalphEcom)

A task management system for AI-driven development, designed to work seamlessly with AI assistants like Claude and Cursor AI.

**This README covers both the original JavaScript version and the new Python port.** Please ensure you are following the instructions relevant to the version you are using.

---

## Python Version (Port)

This section details the Python port of Task Master AI, located in the `python-impl` directory.

### Introduction
The Python version aims to replicate and extend the functionality of the original JavaScript Task Master AI, utilizing Python's ecosystem, including FastAPI for the MCP server and Typer for the CLI.

### Requirements (Python)
- Python 3.9+
- [Poetry](https://python-poetry.org/) for dependency management and virtual environments.
- API Keys: Similar to the JavaScript version, AI-powered commands require API keys for the respective providers (Anthropic, OpenAI, Google, Perplexity, etc.). These should be set as environment variables (e.g., in a `.env` file within the `python-impl` directory).

### Installation (Python)
1.  Clone the repository (if you haven't already):
    ```bash
    git clone https://github.com/eyaltoledano/claude-task-master.git
    cd claude-task-master
    ```
2.  Navigate to the Python implementation directory:
    ```bash
    cd python-impl
    ```
3.  Install dependencies using Poetry. This will also install development dependencies, including `pytest` for testing:
    ```bash
    poetry install --sync
    ```
    This command creates a virtual environment managed by Poetry.

### Running the CLI (Python)
All Python CLI commands are run from within the `python-impl` directory using `poetry run`. The main command is `taskmaster-ai-python`.

1.  Navigate to the Python implementation directory:
    ```bash
    cd python-impl
    ```
2.  Activate the Poetry virtual environment (optional, as `poetry run` handles it, but can be useful for multiple commands):
    ```bash
    poetry shell
    # If you activate the shell, you can omit 'poetry run' from subsequent commands.
    ```
3.  **Common CLI Commands:**
    *   Show version:
        ```bash
        poetry run taskmaster-ai-python --version
        ```
    *   Initialize a new project (interactive, will create files in the current directory, e.g., `python-impl` if run from there, or a dedicated project dir):
        ```bash
        # To initialize in a new directory, cd to that directory first or provide absolute paths if command supports it.
        # The init command in python-impl/task_master_ai_python/cli/commands/init_project.py creates files in CWD.
        poetry run taskmaster-ai-python init project 
        # For non-interactive with defaults:
        poetry run taskmaster-ai-python init project --yes 
        ```
    *   Parse a PRD and generate tasks (assuming PRD is at `../scripts/example_prd.txt` relative to `python-impl` and output to `python-impl/tasks/.tasks.json`):
        ```bash
        # Ensure your PRD file exists. The original sample is outside python-impl.
        # Adjust path to your PRD file as needed.
        poetry run taskmaster-ai-python prd parse ../scripts/example_prd.txt --output tasks/.tasks.json --force
        ```
    *   List all tasks:
        ```bash
        poetry run taskmaster-ai-python list all --file tasks/.tasks.json 
        ```
    *   Show the next task:
        ```bash
        poetry run taskmaster-ai-python next get --file tasks/.tasks.json
        ```
    *   Show current model configuration:
        ```bash
        poetry run taskmaster-ai-python models show
        ```
    *   For a full list of commands and options:
        ```bash
        poetry run taskmaster-ai-python --help
        ```

### Running the MCP Server (Python)
The Python MCP Server uses FastAPI.

1.  Navigate to the Python implementation directory:
    ```bash
    cd python-impl
    ```
2.  Ensure your API keys are set in a `.env` file in this directory or as environment variables.
3.  Run the FastAPI server using Uvicorn:
    ```bash
    poetry run uvicorn task_master_ai_python.mcp_server.main:app --reload --port 8000
    ```
    You can change the port number if needed.

4.  **Configuring your Editor for Python MCP Server:**
    Similar to the JavaScript version, you'll need to update your editor's MCP JSON configuration. The key difference is the `command` and `args`.

    **Example for Cursor & Windsurf (`mcpServers`):**
    ```jsonc
    {
        "mcpServers": {
            "taskmaster-ai-python": { // Unique name for the Python server
                "command": "poetry", // Use poetry to run the command in its environment
                "args": [
                    "run", // Poetry run command
                    "uvicorn",
                    "task_master_ai_python.mcp_server.main:app",
                    "--port", "8000" // Or your chosen port
                    // Add --host 0.0.0.0 if needed for your setup
                ],
                "env": { // API keys can also be loaded from a .env file in python-impl
                    "ANTHROPIC_API_KEY": "YOUR_ANTHROPIC_API_KEY_HERE",
                    "OPENAI_API_KEY": "YOUR_OPENAI_KEY_HERE"
                    // Add other keys as needed
                },
                // Important: Specify the working directory if your poetry command needs to be run from python-impl
                "workingDirectory": "/path/to/your/claude-task-master/python-impl" 
            }
        }
    }
    ```
    > **Note:** Replace `/path/to/your/claude-task-master/python-impl` with the absolute path to the `python-impl` directory on your system. API keys in `env` here are optional if you use a `.env` file in `python-impl`.

    **Example for VS Code (`servers` + `type`):**
    ```jsonc
    {
        "servers": {
            "taskmaster-ai-python": {
                "command": "poetry",
                "args": [
                    "run", 
                    "uvicorn",
                    "task_master_ai_python.mcp_server.main:app",
                    "--port", "8000"
                ],
                "env": { /* API Keys as above */ },
                "type": "stdio", // Or "http" if you adapt server/client for direct HTTP
                "workingDirectory": "/path/to/your/claude-task-master/python-impl" // Absolute path
            }
        }
    }
    ```

### Development (Python)
-   Ensure Poetry is installed and configured for your Python version.
-   Install dependencies: `cd python-impl && poetry install --sync`.
-   Activate the virtual environment: `poetry shell`.
-   Run tests: `pytest` or `poetry run pytest` from the `python-impl` directory.
-   Code is located in `python-impl/task_master_ai_python/`.
-   Tests are in `python-impl/tests/`.

### Testing Status (Python Version)
The Python port includes unit tests for core utilities, configuration management, and AI providers. Integration tests for CLI commands and MCP server endpoints have also been developed. However, during the automated porting and testing phase, persistent environment or file system interaction issues blocked the full execution and verification of all tests. **Manual review, debugging, and potential adjustments to the test environment or file path handling within the tests will be required to ensure all tests pass reliably.**

### Dependencies (Python)
Python dependencies are managed using Poetry and are listed in `python-impl/pyproject.toml`. Key dependencies include `typer` (for CLI), `fastapi` and `uvicorn` (for MCP server), `pydantic` (for data models), and SDKs for various AI providers.

---

## Original JavaScript Version

This section details the original JavaScript version of Task Master AI.

### Requirements (JavaScript)
Taskmaster utilizes AI across several commands, and those require a separate API key. You can use a variety of models from different AI providers provided you add your API keys. For example, if you want to use Claude 3.7, you'll need an Anthropic API key.

You can define 3 types of models to be used: the main model, the research model, and the fallback model (in case either the main or research fail). Whatever model you use, its provider API key must be present in either mcp.json or .env.

At least one (1) of the following is required:
- Anthropic API key (Claude API)
- OpenAI API key
- Google Gemini API key
- Perplexity API key (for research model)
- xAI API Key (for research or main model)
- OpenRouter API Key (for research or main model)

Using the research model is optional but highly recommended. You will need at least ONE API key. Adding all API keys enables you to seamlessly switch between model providers at will.

### Quick Start (JavaScript)

#### Option 1: MCP (Recommended)

MCP (Model Control Protocol) lets you run Task Master directly from your editor.

##### 1. Add your MCP config at the following path depending on your editor

| Editor       | Scope   | Linux/macOS Path                      | Windows Path                                      | Key          |
| ------------ | ------- | ------------------------------------- | ------------------------------------------------- | ------------ |
| **Cursor**   | Global  | `~/.cursor/mcp.json`                  | `%USERPROFILE%\.cursor\mcp.json`                  | `mcpServers` |
|              | Project | `<project_folder>/.cursor/mcp.json`   | `<project_folder>\.cursor\mcp.json`               | `mcpServers` |
| **Windsurf** | Global  | `~/.codeium/windsurf/mcp_config.json` | `%USERPROFILE%\.codeium\windsurf\mcp_config.json` | `mcpServers` |
| **VS Code**  | Project | `<project_folder>/.vscode/mcp.json`   | `<project_folder>\.vscode\mcp.json`               | `servers`    |

###### Cursor & Windsurf (`mcpServers`)

```jsonc
{
	"mcpServers": {
		"taskmaster-ai": {
			"command": "npx",
			"args": ["-y", "--package=task-master-ai", "task-master-ai"],
			"env": {
				"ANTHROPIC_API_KEY": "YOUR_ANTHROPIC_API_KEY_HERE",
				"PERPLEXITY_API_KEY": "YOUR_PERPLEXITY_API_KEY_HERE",
				"OPENAI_API_KEY": "YOUR_OPENAI_KEY_HERE",
				"GOOGLE_API_KEY": "YOUR_GOOGLE_KEY_HERE",
				"MISTRAL_API_KEY": "YOUR_MISTRAL_KEY_HERE",
				"OPENROUTER_API_KEY": "YOUR_OPENROUTER_KEY_HERE",
				"XAI_API_KEY": "YOUR_XAI_KEY_HERE",
				"AZURE_OPENAI_API_KEY": "YOUR_AZURE_KEY_HERE",
				"OLLAMA_API_KEY": "YOUR_OLLAMA_API_KEY_HERE"
			}
		}
	}
}
```

> 🔑 Replace `YOUR_…_KEY_HERE` with your real API keys. You can remove keys you don't use.

###### VS Code (`servers` + `type`)

```jsonc
{
	"servers": {
		"taskmaster-ai": {
			"command": "npx",
			"args": ["-y", "--package=task-master-ai", "task-master-ai"],
			"env": {
				"ANTHROPIC_API_KEY": "YOUR_ANTHROPIC_API_KEY_HERE",
				"PERPLEXITY_API_KEY": "YOUR_PERPLEXITY_API_KEY_HERE",
				"OPENAI_API_KEY": "YOUR_OPENAI_KEY_HERE",
				"GOOGLE_API_KEY": "YOUR_GOOGLE_KEY_HERE",
				"MISTRAL_API_KEY": "YOUR_MISTRAL_KEY_HERE",
				"OPENROUTER_API_KEY": "YOUR_OPENROUTER_KEY_HERE",
				"XAI_API_KEY": "YOUR_XAI_KEY_HERE",
				"AZURE_OPENAI_API_KEY": "YOUR_AZURE_KEY_HERE"
			},
			"type": "stdio"
		}
	}
}
```

> 🔑 Replace `YOUR_…_KEY_HERE` with your real API keys. You can remove keys you don't use.

##### 2. (Cursor-only) Enable Taskmaster MCP

Open Cursor Settings (Ctrl+Shift+J) ➡ Click on MCP tab on the left ➡ Enable task-master-ai with the toggle

##### 3. (Optional) Configure the models you want to use

In your editor’s AI chat pane, say:

```txt
Change the main, research and fallback models to <model_name>, <model_name> and <model_name> respectively.
```

[Table of available models](docs/models.md)

##### 4. Initialize Task Master

In your editor’s AI chat pane, say:

```txt
Initialize taskmaster-ai in my project
```

##### 5. Make sure you have a PRD in `<project_folder>/scripts/prd.txt`

An example of a PRD is located into `<project_folder>/scripts/example_prd.txt`.

**Always start with a detailed PRD.**

The more detailed your PRD, the better the generated tasks will be.

##### 6. Common Commands

Use your AI assistant to:

- Parse requirements: `Can you parse my PRD at scripts/prd.txt?`
- Plan next step: `What’s the next task I should work on?`
- Implement a task: `Can you help me implement task 3?`
- Expand a task: `Can you help me expand task 4?`

[More examples on how to use Task Master in chat](docs/examples.md)

#### Option 2: Using Command Line (JavaScript)

##### Installation

```bash
# Install globally
npm install -g task-master-ai

# OR install locally within your project
npm install task-master-ai
```

##### Initialize a new project

```bash
# If installed globally
task-master init

# If installed locally
npx task-master init
```

This will prompt you for project details and set up a new project with the necessary files and structure.

##### Common Commands (JavaScript)

```bash
# Initialize a new project
task-master init

# Parse a PRD and generate tasks
task-master parse-prd your-prd.txt

# List all tasks
task-master list

# Show the next task to work on
task-master next

# Generate task files
task-master generate
```

---

## Documentation (General)

The following documentation applies conceptually to both versions, but specific command examples or file paths might differ. Refer to the respective Python or JavaScript sections for version-specific details.

- [Configuration Guide](docs/configuration.md) - Set up environment variables and customize Task Master
- [Tutorial](docs/tutorial.md) - Step-by-step guide to getting started with Task Master
- [Command Reference](docs/command-reference.md) - List of available commands (check Python CLI help for Python specifics)
- [Task Structure](docs/task-structure.md) - Understanding the task format and features
- [Example Interactions](docs/examples.md) - Common Cursor AI interaction examples

## Troubleshooting (JavaScript Version)

### If `task-master init` doesn't respond:

Try running it with Node directly:

```bash
node node_modules/claude-task-master/scripts/init.js
```

Or clone the repository and run:

```bash
git clone https://github.com/eyaltoledano/claude-task-master.git
cd claude-task-master
node scripts/init.js
```

## Contributors

<a href="https://github.com/eyaltoledano/claude-task-master/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=eyaltoledano/claude-task-master" alt="Task Master project contributors" />
</a>

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=eyaltoledano/claude-task-master&type=Timeline)](https://www.star-history.com/#eyaltoledano/claude-task-master&Timeline)

## Licensing

Task Master is licensed under the MIT License with Commons Clause. This means you can:

✅ **Allowed**:

- Use Task Master for any purpose (personal, commercial, academic)
- Modify the code
- Distribute copies
- Create and sell products built using Task Master

❌ **Not Allowed**:

- Sell Task Master itself
- Offer Task Master as a hosted service
- Create competing products based on Task Master

See the [LICENSE](LICENSE) file for the complete license text and [licensing details](docs/licensing.md) for more information.
