#!/usr/bin/env python3
"""Debug script to test data model validation."""

import sys
sys.path.append('src')

from src.data_models import ProjectPlan, Task, TaskStatus, TaskPriority
from uuid import uuid4
from datetime import datetime, timezone, date

def test_basic_models():
    """Test basic model instantiation."""
    print("Testing basic model instantiation...")
    
    try:
        # Test TaskStatus enum
        status = TaskStatus.PENDING
        print(f"✅ TaskStatus.PENDING: {status}")
        
        # Test TaskPriority enum  
        priority = TaskPriority.MEDIUM
        print(f"✅ TaskPriority.MEDIUM: {priority}")
        
        # Test Task creation
        subtask = Task(
            title="Test Task",
            description="Test description"
        )
        print(f"✅ Task created: {subtask.id}")
        
        # Test Task creation
        task = Task(
            title="Test Task",
            description="Test description"
        )
        print(f"✅ Task created: {task.id}")
        
        # Test ProjectPlan creation
        project_plan = ProjectPlan(
            project_title="Test Project",
            overall_goal="Test goal"
        )
        print(f"✅ ProjectPlan created: {project_plan.id}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_task_with_subtasks():
    """Test task with subtasks."""
    print("\nTesting Task with Subtasks...")
    
    try:
        subtask1 = Task(
            title="Task 1",
            description="First subtask"
        )
        
        subtask2 = Task(
            title="Task 2", 
            description="Second subtask"
        )
        
        task = Task(
            title="Parent Task",
            description="Task with subtasks",
            subtasks=[subtask1, subtask2]
        )
        
        print(f"✅ Task with {len(task.subtasks)} subtasks created: {task.id}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_project_plan_with_tasks():
    """Test ProjectPlan with tasks."""
    print("\nTesting ProjectPlan with Tasks...")
    
    try:
        task1 = Task(
            title="Task 1",
            description="First task"
        )
        
        task2 = Task(
            title="Task 2",
            description="Second task",
            dependencies=[task1.id]
        )
        
        project_plan = ProjectPlan(
            project_title="Test Project Plan",
            overall_goal="Test overall goal",
            tasks=[task1, task2]
        )
        
        print(f"✅ ProjectPlan with {len(project_plan.tasks)} tasks created: {project_plan.id}")
        
        # Test serialization
        plan_dict = project_plan.model_dump()
        print(f"✅ ProjectPlan serialized to dict")
        
        # Test deserialization
        reconstructed_plan = ProjectPlan.model_validate(plan_dict)
        print(f"✅ ProjectPlan reconstructed from dict: {reconstructed_plan.id}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_json_schema():
    """Test JSON schema generation."""
    print("\nTesting JSON Schema generation...")
    
    try:
        schema = ProjectPlan.model_json_schema(mode="serialization")
        print(f"✅ JSON schema generated: {len(schema)} keys")
        print(f"Schema keys: {list(schema.keys())}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_basic_models()
    test_task_with_subtasks()
    test_project_plan_with_tasks()
    test_json_schema()
    print("\nValidation testing complete!")
