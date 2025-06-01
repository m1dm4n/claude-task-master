"""Model management commands for the DevTask AI Assistant CLI."""

import typer
from typing_extensions import Annotated
from typing import Optional

from .utils import get_agent


def create_models_app() -> typer.Typer:
    """Create and configure the models subcommand app."""
    models_app = typer.Typer(help="Manage AI model configurations")

    @models_app.command("list")
    def list_models(ctx: typer.Context):
        """
        List all configured AI models.
        """
        try:
            agent = get_agent(ctx)
            configs = agent.get_model_configurations()
            
            typer.echo("🤖 Configured AI Models:")
            typer.echo("=" * 40)
            
            for model_type, config in configs.items():
                if config:
                    typer.echo(f"📋 {model_type.title()} Model:")
                    typer.echo(f"   Model: {config.model_name}")
                    typer.echo(f"   Provider: {config.provider}")
                    if config.base_url:
                        typer.echo(f"   Base URL: {config.base_url}")
                    if config.api_key:
                        typer.echo(f"   API Key: {'*' * 8}...")
                    else:
                        typer.echo(f"   API Key: (from environment)")
                    typer.echo()
                else:
                    typer.echo(f"❌ {model_type.title()} Model: Not configured")
                    typer.echo()
                    
        except Exception as e:
            typer.secho(f"❌ Error listing models: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @models_app.command("set")
    def set_model(
        ctx: typer.Context,
        model_type: Annotated[str, typer.Argument(help="Model type: main, research, or fallback")],
        model_name: Annotated[str, typer.Argument(help="Model name (e.g., gpt-4, claude-3-sonnet)")],
        provider: Annotated[Optional[str], typer.Option("--provider", "-p", help="Provider name")] = None,
        api_key: Annotated[Optional[str], typer.Option("--api-key", "-k", help="API key")] = None,
        base_url: Annotated[Optional[str], typer.Option("--base-url", "-u", help="Base URL")] = None
    ):
        """
        Set configuration for a specific AI model.
        """
        if model_type not in ["main", "research", "fallback"]:
            typer.secho("❌ Model type must be one of: main, research, fallback", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        
        try:
            agent = get_agent(ctx)
            success = agent.set_model_configuration(
                model_type=model_type,
                model_name=model_name,
                provider=provider,
                api_key_str=api_key,
                base_url_str=base_url
            )
            
            if success:
                typer.secho(f"✅ {model_type.title()} model configured: {model_name}", fg=typer.colors.GREEN)
            else:
                typer.secho(f"❌ Failed to configure {model_type} model", fg=typer.colors.RED)
                raise typer.Exit(code=1)
                
        except Exception as e:
            typer.secho(f"❌ Error setting model configuration: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @models_app.command("setup")
    def setup_models(ctx: typer.Context):
        """
        Interactive setup for AI model configurations.
        """
        try:
            agent = get_agent(ctx)
            
            typer.echo("🔧 AI Model Configuration Setup")
            typer.echo("=" * 40)
            
            # Main model setup
            typer.echo("\n📋 Main Model (primary agent for task planning):")
            main_model = typer.prompt("Model name", default="gemini-2.0-flash-exp")
            main_provider = typer.prompt("Provider", default="google")
            main_api_key = typer.prompt("API key (optional, leave blank to use environment)", default="", show_default=False)
            main_base_url = typer.prompt("Base URL (optional)", default="", show_default=False)
            
            success = agent.set_model_configuration(
                model_type="main",
                model_name=main_model,
                provider=main_provider if main_provider else None,
                api_key_str=main_api_key if main_api_key else None,
                base_url_str=main_base_url if main_base_url else None
            )
            
            if success:
                typer.secho("✅ Main model configured", fg=typer.colors.GREEN)
            else:
                typer.secho("❌ Failed to configure main model", fg=typer.colors.RED)
            
            # Research model setup
            setup_research = typer.confirm("\n🔬 Configure research model? (for enhanced research capabilities)")
            if setup_research:
                research_model = typer.prompt("Research model name", default=main_model)
                research_provider = typer.prompt("Provider", default=main_provider)
                research_api_key = typer.prompt("API key (optional)", default="", show_default=False)
                research_base_url = typer.prompt("Base URL (optional)", default="", show_default=False)
                
                success = agent.set_model_configuration(
                    model_type="research",
                    model_name=research_model,
                    provider=research_provider if research_provider else None,
                    api_key_str=research_api_key if research_api_key else None,
                    base_url_str=research_base_url if research_base_url else None
                )
                
                if success:
                    typer.secho("✅ Research model configured", fg=typer.colors.GREEN)
                else:
                    typer.secho("❌ Failed to configure research model", fg=typer.colors.RED)
            
            # Fallback model setup
            setup_fallback = typer.confirm("\n🆘 Configure fallback model? (backup model for reliability)")
            if setup_fallback:
                fallback_model = typer.prompt("Fallback model name", default="gemini-1.5-flash")
                fallback_provider = typer.prompt("Provider", default="google")
                fallback_api_key = typer.prompt("API key (optional)", default="", show_default=False)
                fallback_base_url = typer.prompt("Base URL (optional)", default="", show_default=False)
                
                success = agent.set_model_configuration(
                    model_type="fallback",
                    model_name=fallback_model,
                    provider=fallback_provider if fallback_provider else None,
                    api_key_str=fallback_api_key if fallback_api_key else None,
                    base_url_str=fallback_base_url if fallback_base_url else None
                )
                
                if success:
                    typer.secho("✅ Fallback model configured", fg=typer.colors.GREEN)
                else:
                    typer.secho("❌ Failed to configure fallback model", fg=typer.colors.RED)
            
            typer.echo("\n🎉 Model configuration setup complete!")
            typer.echo("💡 Use 'task-master models list' to view all configurations")
            
        except Exception as e:
            typer.secho(f"❌ Error during model setup: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    return models_app