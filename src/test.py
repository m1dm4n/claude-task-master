
import asyncio
import os
# from httpx import AsyncClient # Not strictly needed for this agent structure
from dotenv import load_dotenv

from .agent_core import DevTaskAIAssistant
from .config_manager import ConfigManager
from .agent_core.llm_services import AgentDependencies

load_dotenv()


async def main():
    """
    Demonstrates the usage of the DevTaskAIAssistant.
    """
    config_manager = ConfigManager()

    google_api_key = os.getenv('GOOGLE_API_KEY')
    if not google_api_key:
        print("ERROR: GOOGLE_API_KEY is not set. Please set it in your .env file or environment.")
        return

    deps = AgentDependencies()  # Currently empty, but good practice

    try:
        task_master_agent = DevTaskAIAssistant(config_manager)
    except ValueError as e:
        print(f"Agent initialization failed: {e}")
        return

    print("\n--- Step 1: Planning a New Project ---")
    project_goal = "Develop a secure, multi-tenant SaaS application for managing small business invoices using Python/FastAPI, PostgreSQL, and React. Implement user authentication, invoice creation/management, and PDF export."
    print(f"Project Goal: {project_goal}\n")

    try:
        project_plan = await task_master_agent.plan_project(project_goal, project_title="InvoiceSaaS", deps=deps)
        print("Generated Project Plan:")
        print(project_plan.model_dump_json(indent=2))
    except Exception as e:
        print(f"Error during project planning: {e}")
        project_plan = None

    if project_plan and project_plan.tasks:
        first_task = project_plan.tasks[0]
        print(
            f"\n--- Step 2: Refining the First Task: '{first_task.title}' ---")
        refinement_prompt = "Elaborate on the specific FastAPI endpoints required for user authentication, outline database schema considerations for multi-tenancy, and suggest a testing strategy for user registration and login."
        print(f"Refinement Prompt: {refinement_prompt}")

        try:
            refined_task = await task_master_agent.refine_task(first_task, refinement_prompt, use_research=True, deps=deps)
            print("\nRefined First Task:")
            print(refined_task.model_dump_json(indent=2))
        except Exception as e:
            print(f"Error during task refinement: {e}")
            refined_task = None

        if refined_task:
            print(
                f"\n--- Step 3: Performing Research for a Specific Task: '{refined_task.title}' ---")
            research_query = "Best practices for multi-tenant database design in PostgreSQL"
            print(f"Research Query: {research_query}")

            try:
                research_summary = await task_master_agent.llm_manager.research_query(refined_task.title, research_query)
                print("\nResearch Summary:")
                print(research_summary)
            except Exception as e:
                print(f"Error during research: {e}")
        else:
            print("\nSkipping research as task refinement failed or no task was refined.")
    else:
        print("\nNo tasks were generated in the project plan. Skipping refinement and research steps.")

    print("\nAgent operations complete.")

if __name__ == '__main__':
    asyncio.run(main())
