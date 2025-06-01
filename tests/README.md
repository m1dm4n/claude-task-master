# AI Agent Tests

This directory contains unit and integration tests for the Python AI agent.

## Setup

1.  **Install Dependencies**:
    Ensure you have Poetry installed. From the project root directory (`claude-task-master`), install the main and development dependencies:
    ```bash
    poetry install
    ```

## Running Unit Tests

Unit tests focus on individual components in isolation and do not require API keys.

To run all unit tests:
```bash
pytest tests/unit
```

## Running Integration Tests

Integration tests verify interactions between components, particularly those involving the Google Gemini LLM.

**Prerequisites**:
*   You MUST have a valid `GOOGLE_API_KEY` environment variable set.
    ```bash
    export GOOGLE_API_KEY="your_actual_google_api_key"
    ```
    Alternatively, you can add it to a `.env` file in the project root.

To run all integration tests:
```bash
pytest tests/integration
```

If the `GOOGLE_API_KEY` is not set, integration tests will be skipped.

## Contributing

When adding new tests:
*   Place unit tests in `tests/unit/`.
*   Place integration tests in `tests/integration/`.
*   Follow the `test_*.py` naming convention for test files.
*   Ensure unit tests mock external dependencies (API calls, file system).
*   Ensure integration tests clean up any created artifacts (e.g., using `tmp_path` fixture for files).