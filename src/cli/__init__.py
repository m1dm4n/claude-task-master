"""CLI module for the DevTask AI Assistant.

This module provides the main Typer CLI application and command interface
for interacting with the DevTask AI Assistant.
"""

from .main import app
from .utils import parse_uuid_or_exit

__all__ = ["app", "parse_uuid_or_exit"]