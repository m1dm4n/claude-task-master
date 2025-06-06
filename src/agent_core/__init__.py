"""Agent core module for the DevTask AI Assistant.

This module provides the main DevTaskAIAssistant class and related functionality
for project management, task handling, and AI-powered development assistance.
"""

from .assistant import DevTaskAIAssistant
from .services.config_service import ConfigService
from .services.llm_service import LLMService
from .services.project_service import ProjectService
from .services.task_service import TaskService
from .mcp_handler import MCPHandler

__all__ = [
    "DevTaskAIAssistant",
    "ConfigService",
    "LLMService",
    "ProjectService",
    "TaskService",
    "MCPHandler",
]