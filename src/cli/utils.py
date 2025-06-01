"""Shared CLI utilities for the DevTask AI Assistant."""

import typer
import os
from ..agent_core.main import DevTaskAIAssistant


def get_agent(ctx: typer.Context) -> DevTaskAIAssistant:
    """
    Get or create DevTaskAIAssistant instance for the current workspace.
    
    Args:
        ctx: Typer context
        
    Returns:
        DevTaskAIAssistant instance
    """
    if not hasattr(ctx, 'obj') or ctx.obj is None:
        workspace_path = os.getcwd()
        ctx.ensure_object(dict)
        ctx.obj['agent'] = DevTaskAIAssistant(workspace_path)
    return ctx.obj['agent']