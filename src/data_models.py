from __future__ import annotations as _annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, SecretStr, AnyHttpUrl
from datetime import datetime, date, timezone
from enum import Enum
from uuid import UUID, uuid4


class TaskStatus(str, Enum):
    """Enumeration for task status values."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    DEFERRED = "DEFERRED"


class TaskPriority(str, Enum):
    """Enumeration for task priority values."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ItemType(str, Enum):
    """Enumeration for the type of an item (Task or Task)."""
    TASK = "TASK"
    SUBTASK = "SUBTASK"


class Task(BaseModel):
    """Represents a main task in the Task Master system.
    This model is also used for subtasks, with `parent_id` indicating its parent.
    """
    id: UUID = Field(default_factory=uuid4,
                     description="Unique identifier for the task. Using RFC 4122 UUID format.")
    title: str = Field(description="Concise title of the task.")
    description: str = Field(
        description="Detailed description of the task, including its purpose and scope.")
    status: TaskStatus = Field(
        TaskStatus.PENDING, description="Current status of the task, indicating its progress in the workflow. If task is not started, it should be set to PENDING.")
    dependencies: List[UUID] = Field(
        default_factory=list, description="List of unique identifiers for tasks or subtasks that must be completed before this subtask can begin. Dependencies create execution order constraints and are used for scheduling, progress tracking, and identifying potential blockers in the task workflow."
    )
    priority: TaskPriority = Field(
        TaskPriority.MEDIUM, description="Priority level of the task.")
    details: Optional[str] = Field(
        None, description="In-depth implementation notes or AI-generated content.")
    testStrategy: Optional[str] = Field(
        None, description="Proposed strategy for testing the task's completion.")
    subtasks: List[Task] = Field(  # Changed from List[Task] to List[Task]
        default_factory=list, description="List of subtasks for further decomposition."
    )
    complexity_score: Optional[int] = Field(
        None, description="Complexity score of the task, if calculated.")
    complexity_analysis_notes: Optional[str] = Field(
        None, description="Notes from the complexity analysis, if performed.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(
        timezone.utc), description="Timestamp when the task was created.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(
        timezone.utc), description="Timestamp when the task was last updated.")
    due_date: Optional[date] = Field(
        None, description="Optional due date for the task, if applicable.")
    parent_id: Optional[UUID] = Field(
        None, description="ID of the parent task if this is a subtask.")


class SubtaskLLMInput(BaseModel):
    """A simplified Subtask model for LLM input."""
    title: str = Field(description="Concise title of the subtask.")
    description: str = Field(description="Detailed description of the subtask.")
    priority: Optional[TaskPriority] = Field(None, description="Priority level of the subtask.")
    details: Optional[str] = Field(None, description="In-depth implementation notes or AI-generated content for the subtask.")
    testStrategy: Optional[str] = Field(None, description="Proposed strategy for testing the subtask's completion.")
    dependencies: List[UUID] = Field(default_factory=list, description="List of unique identifiers for tasks or subtasks that must be completed before this subtask can begin.")
    due_date: Optional[date] = Field(None, description="Optional due date for the subtask.")


class TaskLLMInput(BaseModel):
    """A simplified Task model for LLM input, excluding recursive fields."""
    title: str = Field(description="Concise title of the task.")
    description: str = Field(description="Detailed description of the task.")
    status: Optional[TaskStatus] = Field(
        None, description="Current status of the task.")
    dependencies: List[UUID] = Field(
        default_factory=list, description="List of unique identifiers for tasks that must be completed before this task can begin.")
    priority: Optional[TaskPriority] = Field(
        None, description="Priority level of the task.")
    details: Optional[str] = Field(
        None, description="In-depth implementation notes or AI-generated content.")
    testStrategy: Optional[str] = Field(
        None, description="Proposed strategy for testing the task's completion.")
    due_date: Optional[date] = Field(
        None, description="Optional due date for the task.")
    parent_id: Optional[UUID] = Field(
        None, description="ID of the parent task if this is a subtask.")


class TaskLLMOutput(BaseModel):
    """A simplified Task model for LLM output, excluding recursive fields and immutable fields."""
    title: str = Field(description="Concise title of the task.")
    description: str = Field(description="Detailed description of the task.")
    status: Optional[TaskStatus] = Field(
        None, description="Current status of the task.")
    dependencies: Optional[List[UUID]] = Field(
        None, description="List of unique identifiers for tasks that must be completed before this task can begin.")
    priority: Optional[TaskPriority] = Field(
        None, description="Priority level of the task.")
    details: Optional[str] = Field(
        None, description="In-depth implementation notes or AI-generated content.")
    testStrategy: Optional[str] = Field(
        None, description="Proposed strategy for testing the task's completion.")
    due_date: Optional[date] = Field(
        None, description="Optional due date for the task.")
    parent_id: Optional[UUID] = Field(
        None, description="ID of the parent task if this is a subtask.")
    initial_subtasks: List[SubtaskLLMInput] = Field(
        default_factory=list, description="List of initial subtasks generated by the LLM, each conforming to SubtaskLLMInput.")


class DependencyFix(BaseModel):
    """Represents a suggested fix for task dependencies."""
    task_id: UUID = Field(description="The ID of the task whose dependencies are to be modified.")
    new_dependencies: List[UUID] = Field(default_factory=list, description="The new list of dependencies for the task. Omit dependencies to remove them.")


class DependencyFixesLLMOutput(BaseModel):
    """Represents the LLM's suggested fixes for dependencies."""
    suggested_fixes: List[DependencyFix] = Field(default_factory=list, description="A list of suggested dependency modifications.")


class ProjectPlan(BaseModel):
    """Represents a comprehensive project plan generated by the agent."""
    id: UUID = Field(default_factory=uuid4,
                     description="Unique identifier for the project plan. Using RFC 4122 UUID format.")
    project_title: str = Field(description="The title of the project.")
    overall_goal: str = Field(
        description="The high-level goal of the project.")
    tasks: List[Task] = Field(
        default_factory=list, description="A structured list of tasks derived from the project goal.")
    notes: Optional[str] = Field(
        "", description="Any additional notes or considerations for the project plan.")
    project_name: Optional[str] = Field(
        None, description="Optional name for the project, if different from the title.")
    workspace_path: Optional[str] = Field(
        None, description="Path to the local workspace directory where project files are stored.")
    config_file_path: Optional[str] = Field(
        None, description="Path to the configuration file for the project.")
    last_complexity_analysis_timestamp: Optional[datetime] = Field(
        None, description="Timestamp of the last complexity analysis performed on the project plan.")
    version: str = "1.0.0"


class ModelConfig(BaseModel):
    """Configuration for a specific LLM model."""
    model_name: str
    provider: Optional[str] = None  # e.g., "ollama", "openai", "anthropic"
    api_key: Optional[SecretStr] = None
    base_url: Optional[AnyHttpUrl] = None
    # Add other provider-specific settings if needed


class AppConfig(BaseModel):
    """Overall application configuration."""
    main_model: ModelConfig
    research_model: Optional[ModelConfig] = None
    fallback_model: Optional[ModelConfig] = None
    project_plan_file: str = "project_plan.json"
    tasks_dir: str = "tasks"
    default_prd_filename: str = "prd.md"
    # Add other app-level settings from the plan as needed


class ToolType(str, Enum):
    """Enumeration for the type of a tool."""
    CLI = "CLI"
    MCP = "MCP"
    # Add other types as needed, e.g., 'INTERNAL', 'EXTERNAL_API'


class ToolCode(BaseModel):
    """Represents code to be executed by a tool."""
    language: str = Field(
        description="Programming language of the code (e.g., 'python', 'javascript').")
    code: str = Field(description="The actual code string.")


class ToolOutput(BaseModel):
    """Represents the output of a tool execution."""
    stdout: Optional[str] = Field(
        None, description="Standard output from the tool.")
    stderr: Optional[str] = Field(
        None, description="Standard error from the tool.")
    exit_code: int = Field(0, description="Exit code of the tool execution.")
    result: Optional[Any] = Field(
        None, description="Structured result from the tool, if any.")
    error: Optional[str] = Field(
        None, description="Error message if the tool execution failed.")


class Tool(BaseModel):
    """Represents a tool that the agent can use."""
    name: str = Field(description="Unique name of the tool.")
    description: str = Field(description="Description of what the tool does.")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="JSON schema for the tool's input parameters.")
    tool_type: ToolType = Field(
        ToolType.MCP, description="Type of the tool (e.g., CLI, MCP).")
    # For MCP tools, you might add server_name or URI patterns here


class AgentState(BaseModel):
    """Represents the current state of the DevTask AI Assistant."""
    current_project_plan: ProjectPlan = Field(
        description="The current project plan being managed.")
    config: AppConfig = Field(
        description="The current application configuration.")
    # Add other relevant state information as needed
