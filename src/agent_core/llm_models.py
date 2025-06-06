from typing import List, Optional

from pydantic import BaseModel


class ProjectPlanLLMOutput(BaseModel):
    """
    Represents the project plan output from the LLM, without recursion.
    """
    title: str
    description: str
    tasks: List[dict]