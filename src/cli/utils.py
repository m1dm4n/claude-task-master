"""Shared CLI utilities for the DevTask AI Assistant."""

import typer
from uuid import UUID


def parse_uuid_or_exit(uuid_str: str, item_name: str = "ID") -> UUID:
    """Parses a string to UUID. Exits with an error message if parsing fails."""
    try:
        return UUID(uuid_str)
    except ValueError:
        typer.secho(f"❌ Invalid {item_name} format: '{uuid_str}'. Please provide a valid UUID.", fg=typer.colors.RED)
        raise typer.Exit(code=1)