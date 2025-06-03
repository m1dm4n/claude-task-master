#!/usr/bin/env python3
"""
Script to generate test fixtures by making real LLM calls.
This creates realistic test data that can be used in both integration and unit tests.

Requirements:
    - GOOGLE_API_KEY environment variable must be set
    
Usage:
    export GOOGLE_API_KEY="your-google-api-key"
    python tests/fixtures/generate_expansion_fixtures.py
"""
from copy import deepcopy
import json
import asyncio
import os
from pathlib import Path
from uuid import uuid4

# Add src to path for imports
# import sys
# sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.agent_core.main import DevTaskAIAssistant
from src.data_models import Task, Subtask, TaskStatus, TaskPriority

temp_workspace = Path(__file__).parent / "fixture_generation_workspace"
temp_workspace.mkdir(exist_ok=True)

async def generate_project_plan_from_prd():
    """Generate a project plan from the test PRD using real LLM calls."""
    print("🚀 Generating project plan from PRD using real LLM...")
    
    # Initialize agent in a temporary workspace
    
    agent = DevTaskAIAssistant(str(temp_workspace))
    
    # Load the test PRD
    prd_path = Path(__file__).parent / "test_prd_for_expansion.txt"
    
    try:
        # Generate project plan from PRD
        project_plan = await agent.planning_manager.plan_project_from_prd_file(
            prd_file_path=prd_path,
            project_title="Test Task Management App",
        )
        
        print(f"✅ Generated project plan with {len(project_plan.tasks)} tasks")
        return project_plan
        
    except Exception as e:
        print(f"❌ Error generating project plan: {e}")
        raise


async def generate_subtasks_for_tasks(agent, tasks: list[Task]):
    """Generate subtasks for a subset of tasks using real LLM calls."""
    print(f"🔄 Generating subtasks for {len(tasks)} tasks...")
    
    enhanced_tasks = []
    
    for i, task in enumerate(tasks[:3]):  # Limit to first 3 tasks for fixtures
        try:
            print(f"  📝 Generating subtasks for task {i+1}: {task.title}")
            
            subtasks = await agent.llm_manager.generate_subtasks_for_task(
                task.description,
                task.title,
                task.subtasks
            )
            
            # Create new task with subtasks
            enhanced_task = deepcopy(task)
            enhanced_task.subtasks = subtasks
            
            enhanced_tasks.append(enhanced_task)
            print(f"    ✅ Generated {len(subtasks)} subtasks")
            
        except Exception as e:
            print(f"    ❌ Error generating subtasks for {task.title}: {e}")
            # Include task without subtasks as fallback
            enhanced_tasks.append(task)
    
    return enhanced_tasks


def serialize_fixtures(project_plan, enhanced_tasks):
    """Serialize fixture data to JSON format."""
    
    def serialize_task(task):
        return {
            "id": str(task.id),
            "title": task.title,
            "description": task.description,
            "status": task.status.value,
            "priority": task.priority.value,
            "subtasks": [serialize_subtask(subtask) for subtask in task.subtasks]
        }
    
    def serialize_subtask(subtask):
        return {
            "id": str(subtask.id),
            "title": subtask.title,
            "description": subtask.description,
            "status": subtask.status.value,
            "priority": subtask.priority.value
        }
    
    def serialize_project_plan(plan):
        return {
            "id": str(plan.id),
            "project_title": plan.project_title,
            "overall_goal": plan.overall_goal,
            "tasks": [serialize_task(task) for task in plan.tasks]
        }
    
    fixtures = {
        "generated_at": "2025-01-06T21:37:00Z",
        "description": "Real LLM-generated fixtures for Phase 6 CLI testing",
        "base_project_plan": serialize_project_plan(project_plan),
        "tasks_with_subtasks": [serialize_task(task) for task in enhanced_tasks],
        "sample_subtasks_only": [
            serialize_subtask(subtask) 
            for task in enhanced_tasks 
            for subtask in task.subtasks
        ]
    }
    
    return fixtures


async def main():
    """Main function to generate all fixtures."""
    try:
        # Check for required environment variable
        if not os.getenv("GOOGLE_API_KEY"):
            print("❌ GOOGLE_API_KEY environment variable is required")
            print("   Set it using: export GOOGLE_API_KEY='your-google-api-key'")
            return 1
            
        print("🎯 Starting fixture generation process...")
        print("✅ Using Google API for LLM calls")
        
        # Generate base project plan
        project_plan = await generate_project_plan_from_prd()
        
        # Initialize agent for subtask generation
        agent = DevTaskAIAssistant(str(temp_workspace))
        
        # Generate subtasks for subset of tasks
        enhanced_tasks = await generate_subtasks_for_tasks(agent, project_plan.tasks)
        
        # Serialize to JSON
        fixtures = serialize_fixtures(project_plan, enhanced_tasks)
        
        # Save fixtures
        output_path = Path(__file__).parent / "phase6_expansion_fixtures.json"
        output_path.write_text(json.dumps(fixtures, indent=2))
        
        print(f"💾 Fixtures saved to {output_path}")
        print(f"📊 Generated:")
        print(f"   - Base project with {len(project_plan.tasks)} tasks")
        print(f"   - {len(enhanced_tasks)} tasks with subtasks")
        print(f"   - {sum(len(task.subtasks) for task in enhanced_tasks)} total subtasks")
        print("✨ Fixture generation complete!")
        
    except Exception as e:
        print(f"💥 Fixture generation failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())