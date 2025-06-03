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
    if not hasattr(ctx, 'obj') or ctx.obj is None or 'agent' not in ctx.obj:
        # workspace_path should be set by the main_callback in main.py
        # Default to os.getcwd() only if it's somehow not in ctx.obj
        workspace_path = ctx.obj.get("workspace_path", os.getcwd()) if ctx.obj else os.getcwd()
        
        ctx.ensure_object(dict) # Ensure ctx.obj is a dict
        ctx.obj['agent'] = DevTaskAIAssistant(workspace_path)
    return ctx.obj['agent']