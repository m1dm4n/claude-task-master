import json
import os
import pathlib
import logging
from typing import Any, Dict, List, Literal, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE_NAME = ".taskmasterconfig"
SUPPORTED_MODELS_FILE = "supported-models.json" # Assumed to be in the same directory

# --- Globals for caching config ---
loaded_config: Optional[Dict] = None
loaded_config_root: Optional[str] = None
MODEL_MAP: Dict[str, List[Dict]] = {}

# --- Default Configuration ---
DEFAULTS: Dict[str, Any] = {
    "models": {
        "main": {
            "provider": "google",  # Changed from anthropic for wider key availability
            "model_id": "gemini-pro", # Changed from claude-3-7-sonnet
            "max_tokens": 64000,
            "temperature": 0.2,
        },
        "research": {
            "provider": "openai", # Changed from perplexity
            "model_id": "gpt-3.5-turbo", # Changed from sonar-pro
            "max_tokens": 8700,
            "temperature": 0.1,
        },
        "fallback": {
            "provider": "openai", # Changed from anthropic
            "model_id": "gpt-3.5-turbo", # Changed from claude-3-5-sonnet
            "max_tokens": 64000,
            "temperature": 0.2,
        },
    },
    "global": {
        "log_level": "info",
        "debug": False,
        "default_subtasks": 5,
        "default_priority": "medium",
        "project_name": "Task Master",
        "ollama_base_url": "http://localhost:11434/api", # For Ollama provider
        "user_id": "default_python_user_id" # Added a default user_id
    },
}

class ConfigurationError(Exception):
    pass

def _find_project_root(start_path: Optional[str] = None) -> Optional[str]:
    current_path = pathlib.Path(start_path or os.getcwd())
    while current_path.parent != current_path: # Stop at root
        if (current_path / ".git").exists() or \
           (current_path / CONFIG_FILE_NAME).exists() or \
           (current_path / "pyproject.toml").exists(): # Added pyproject.toml as indicator
            return str(current_path)
        current_path = current_path.parent
    # Check current_path itself if it's the root
    if (current_path / ".git").exists() or \
       (current_path / CONFIG_FILE_NAME).exists() or \
       (current_path / "pyproject.toml").exists():
        return str(current_path)
    logger.warning("Project root not found.")
    return None

def _load_supported_models(base_dir: str) -> Dict[str, List[Dict]]:
    global MODEL_MAP
    models_file_path = pathlib.Path(base_dir) / SUPPORTED_MODELS_FILE
    if not models_file_path.exists():
        logger.error(f"FATAL ERROR: {SUPPORTED_MODELS_FILE} not found at {models_file_path}. Please ensure the file exists.")
        # In a real app, you might raise an error or exit
        return {} 
    try:
        with open(models_file_path, "r", encoding="utf-8") as f:
            MODEL_MAP = json.load(f)
        logger.info(f"Successfully loaded {SUPPORTED_MODELS_FILE}")
        return MODEL_MAP
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding {SUPPORTED_MODELS_FILE}: {e}. Using empty model map.")
        return {}
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading {SUPPORTED_MODELS_FILE}: {e}")
        return {}

# Load models when the module is imported. Assumes this script is in python_src/
_module_dir = pathlib.Path(__file__).parent.resolve()
MODEL_MAP = _load_supported_models(str(_module_dir))
VALID_PROVIDERS = list(MODEL_MAP.keys())


def _deep_merge_dicts(base: Dict, update: Dict) -> Dict:
    merged = base.copy()
    for key, value in update.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged

def _load_and_validate_config(explicit_root: Optional[str] = None) -> Dict:
    config = DEFAULTS.copy() # Start with a deep copy of defaults
    
    root_to_use = explicit_root
    if not root_to_use:
        root_to_use = _find_project_root()

    if not root_to_use:
        logger.warning(f"{CONFIG_FILE_NAME} not found (no project root identified). Using default configuration.")
        return config

    config_path = pathlib.Path(root_to_use) / CONFIG_FILE_NAME

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                parsed_config = json.load(f)
            
            # Deep merge parsed config onto defaults
            config = _deep_merge_dicts(DEFAULTS, parsed_config)
            logger.info(f"Loaded configuration from {config_path}")

            # Basic Validation (can be expanded)
            for role in ["main", "research", "fallback"]:
                provider = config.get("models", {}).get(role, {}).get("provider")
                if provider and provider not in VALID_PROVIDERS:
                    logger.warning(f"Invalid provider '{provider}' for role '{role}' in {config_path}. Check {SUPPORTED_MODELS_FILE}.")
                    # Potentially revert to default for this role or handle error
                    config["models"][role] = DEFAULTS["models"][role]

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding {config_path}: {e}. Using default configuration.")
            return DEFAULTS.copy() # Return fresh defaults on parse error
        except Exception as e:
            logger.error(f"Error loading {config_path}: {e}. Using default configuration.")
            return DEFAULTS.copy()
    else:
        logger.info(f"{CONFIG_FILE_NAME} not found at {config_path}. Using default configuration. Consider running setup.")
        
    return config

def get_config(explicit_root: Optional[str] = None, force_reload: bool = False) -> Dict:
    global loaded_config, loaded_config_root
    
    current_project_root = _find_project_root(explicit_root)

    needs_load = (
        not loaded_config or
        force_reload or
        (current_project_root and current_project_root != loaded_config_root) or
        (explicit_root and explicit_root != loaded_config_root)
    )
    
    if needs_load:
        # Determine the root to use for loading: explicit_root if provided, otherwise the found project root
        root_for_load = explicit_root if explicit_root else current_project_root
        
        new_config = _load_and_validate_config(root_for_load)
        loaded_config = new_config
        loaded_config_root = root_for_load # Cache the root that was actually used for loading
        logger.debug(f"Config loaded/reloaded. Root used: {loaded_config_root}")
    
    return loaded_config if loaded_config else DEFAULTS.copy()


def write_config(config_data: Dict, explicit_root: Optional[str] = None) -> bool:
    global loaded_config, loaded_config_root
    root_path = explicit_root or _find_project_root()
    if not root_path:
        logger.error("Cannot write config: Project root not found.")
        return False
    
    config_file_path = pathlib.Path(root_path) / CONFIG_FILE_NAME
    try:
        with open(config_file_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        loaded_config = config_data # Update cache
        loaded_config_root = root_path
        logger.info(f"Configuration successfully written to {config_file_path}")
        return True
    except Exception as e:
        logger.error(f"Error writing configuration to {config_file_path}: {e}")
        return False

def is_config_file_present(explicit_root: Optional[str] = None) -> bool:
    root_path = explicit_root or _find_project_root()
    if not root_path:
        return False
    return (pathlib.Path(root_path) / CONFIG_FILE_NAME).exists()

def get_model_config_for_role(role: Literal["main", "research", "fallback"], explicit_root: Optional[str] = None) -> Dict:
    config = get_config(explicit_root)
    # Ensure "models" key exists, defaulting to DEFAULTS["models"] if not
    models_config = config.get("models", DEFAULTS.get("models", {}))
    role_config = models_config.get(role)
    
    if not role_config:
        logger.warning(f"No model configuration found for role: {role}. Returning default for this role.")
        return DEFAULTS.get("models", {}).get(role, {}) # Ensure this path exists
    return role_config

# --- Getters for specific model properties ---
def get_provider_for_role(role: str, explicit_root: Optional[str] = None) -> Optional[str]:
    # Cast role to Literal to satisfy type checker for get_model_config_for_role
    literal_role = role if role in ["main", "research", "fallback"] else "main"
    if role not in ["main", "research", "fallback"]:
        logger.warning(f"Invalid role '{role}' in get_provider_for_role. Defaulting to 'main'.")
    return get_model_config_for_role(literal_role, explicit_root).get("provider")

def get_model_id_for_role(role: str, explicit_root: Optional[str] = None) -> Optional[str]:
    literal_role = role if role in ["main", "research", "fallback"] else "main"
    if role not in ["main", "research", "fallback"]:
        logger.warning(f"Invalid role '{role}' in get_model_id_for_role. Defaulting to 'main'.")
    return get_model_config_for_role(literal_role, explicit_root).get("model_id")

# --- Getters for global settings ---
def get_global_config(explicit_root: Optional[str] = None) -> Dict:
    config = get_config(explicit_root)
    # Ensure "global" key exists, defaulting to DEFAULTS["global"] if not
    return _deep_merge_dicts(DEFAULTS.get("global", {}), config.get("global", {}))


def get_log_level(explicit_root: Optional[str] = None) -> str:
    return get_global_config(explicit_root).get("log_level", "info").lower()

def get_debug_flag(explicit_root: Optional[str] = None) -> bool:
    return get_global_config(explicit_root).get("debug", False)
    
def get_user_id(explicit_root: Optional[str] = None) -> Optional[str]:
    config = get_config(explicit_root, force_reload=False) # Avoid unnecessary reloads if already loaded for this root
    
    # Ensure 'global' key exists in config, defaulting to a copy of DEFAULTS['global'] if necessary
    # This modification should be done on a temporary copy if we don't intend to persist it immediately
    # or ensure that write_config is called if changes are made.
    
    current_global_settings = config.get("global", DEFAULTS.get("global", {})).copy() # Work with a copy
    user_id_val = current_global_settings.get("user_id")
    
    needs_update_and_save = False
    if not user_id_val: # If None or empty string
        user_id_val = DEFAULTS.get("global", {}).get("user_id", "fallback_default_user_id")
        current_global_settings["user_id"] = user_id_val
        needs_update_and_save = True # Mark that we need to save this change
        logger.info(f"User ID not found or empty in config, setting to default: {user_id_val}.")

    if needs_update_and_save:
        # To persist this, we need to update the main 'config' object and then write it.
        config_to_save = get_config(explicit_root, force_reload=False).copy() # Get the current full config
        config_to_save["global"] = current_global_settings # Update its global part
        
        # Determine the correct root for saving. If explicit_root is given, use it. Otherwise, use the cached loaded_config_root.
        # If loaded_config_root is also None (e.g. config never loaded before), then try to find project root.
        save_root = explicit_root or loaded_config_root or _find_project_root()

        if not write_config(config_to_save, save_root): # Pass the determined root to write_config
             logger.warning(f"Failed to save updated config with new User ID: {user_id_val}. User ID will be default for this session only.")
        else:
            logger.info(f"Successfully saved new User ID '{user_id_val}' to config file.")
            # Ensure the global 'loaded_config' reflects this change if it was modified
            global loaded_config
            if loaded_config: # Should always be true if get_config was called
                 loaded_config["global"] = current_global_settings

    return user_id_val


def get_parameters_for_role(role: str, explicit_root: Optional[str] = None) -> Dict[str, Any]:
    literal_role = role if role in ["main", "research", "fallback"] else "main"
    if role not in ["main", "research", "fallback"]:
        logger.warning(f"Invalid role '{role}' in get_parameters_for_role. Defaulting to 'main'.")
        
    role_config = get_model_config_for_role(literal_role, explicit_root)
    default_role_params = DEFAULTS.get("models", {}).get(literal_role, {"max_tokens": 1000, "temperature": 0.7})

    role_max_tokens = role_config.get("max_tokens", default_role_params["max_tokens"])
    role_temp = role_config.get("temperature", default_role_params["temperature"])
    
    model_id = role_config.get("model_id")
    provider_name = role_config.get("provider")

    effective_max_tokens = role_max_tokens
    if provider_name and model_id and provider_name in MODEL_MAP:
        provider_models = MODEL_MAP.get(provider_name, [])
        model_definition = next((m for m in provider_models if m.get("id") == model_id), None)
        if model_definition and isinstance(model_definition.get("max_tokens"), int) and model_definition["max_tokens"] > 0:
            model_specific_max_tokens = model_definition["max_tokens"]
            effective_max_tokens = min(int(role_max_tokens), model_specific_max_tokens) # Ensure role_max_tokens is int
            logger.debug(f"Applying model-specific max_tokens ({model_specific_max_tokens}) for {model_id}. Effective: {effective_max_tokens}")
        else:
            logger.debug(f"No valid model-specific max_tokens for {model_id} in MODEL_MAP. Using role default: {role_max_tokens}")
            
    return {"max_tokens": int(effective_max_tokens), "temperature": float(role_temp)} # Ensure types

def resolve_env_variable(var_name: str, session: Optional[Dict] = None, project_root_override: Optional[str] = None) -> Optional[str]:
    # 1. Check os.environ
    val = os.environ.get(var_name)
    if val:
        logger.debug(f"Resolved '{var_name}' from environment variables.")
        return val
        
    # 2. Check session (if provided) - Assuming session might have an 'env' dict
    if session and isinstance(session.get("env"), dict):
        val = session["env"].get(var_name)
        if val:
            logger.debug(f"Resolved '{var_name}' from session variables.")
            return val
            
    # 3. Check .env file in project_root (requires python-dotenv or similar, simplified here)
    # Determine project root: use override if provided, else try to find it.
    actual_project_root = project_root_override or _find_project_root()

    if actual_project_root:
        try:
            from dotenv import load_dotenv # Lazy import
            dotenv_path = pathlib.Path(actual_project_root) / ".env"
            if dotenv_path.exists():
                logger.debug(f"Loading .env file from {dotenv_path} for '{var_name}'.")
                # Store current os.environ keys to compare later if needed, or just load and re-check
                # current_env_keys = set(os.environ.keys())
                load_dotenv(dotenv_path=dotenv_path, override=True) # Override to ensure fresh load
                val = os.environ.get(var_name) # Check os.environ again after loading .env
                if val:
                    # Potentially remove the key from os.environ if it was only from .env and you want to isolate it
                    # This is complex because load_dotenv modifies os.environ directly.
                    # For now, we accept that it pollutes os.environ for the session.
                    logger.debug(f"Resolved '{var_name}' from .env file at {dotenv_path}.")
                    return val
            else:
                logger.debug(f".env file not found at {dotenv_path}.")
        except ImportError:
            logger.warning("python-dotenv is not installed. Cannot load .env file for API keys. Run `poetry add python-dotenv`.")
        except Exception as e:
            logger.error(f"Error loading .env file: {e}")
    else:
        logger.debug("Project root not found, skipping .env file check.")
        
    logger.debug(f"Could not resolve '{var_name}'.")
    return None


def is_api_key_set(provider_name: str, session: Optional[Dict] = None, project_root_override: Optional[str] = None) -> bool:
    if not provider_name:
        logger.warning("is_api_key_set called with no provider name.")
        return False
        
    provider_name_lower = provider_name.lower()

    if provider_name_lower == "ollama": # Ollama doesn't require a key
        logger.debug(f"API key check for '{provider_name}' (Ollama): always true.")
        return True

    # Prioritize MODEL_MAP for determining key name, then fall back to static map
    env_var_name: Optional[str] = None
    if provider_name_lower in MODEL_MAP:
        # Assuming MODEL_MAP provider entry might have an 'api_key_env_var' field
        # This is an extension to the provided MODEL_MAP structure but good for future
        provider_meta = MODEL_MAP[provider_name_lower]
        if isinstance(provider_meta, list) and len(provider_meta) > 0: # provider_meta is a list of models
             # Look for api_key_env_var in the first model's meta, or a dedicated provider meta section if it existed
            first_model_example = provider_meta[0]
            if isinstance(first_model_example, dict) and "api_key_env_var" in first_model_example:
                 env_var_name = first_model_example["api_key_env_var"]
            # Or, if the provider itself has a direct entry in MODEL_MAP (not a list of models)
        elif isinstance(provider_meta, dict) and "api_key_env_var" in provider_meta:
            env_var_name = provider_meta["api_key_env_var"]


    if not env_var_name: # Fallback to static map or generate one
        key_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY", # Matches Gemini API key name
            "gemini": "GOOGLE_API_KEY", # Alias for google
            "perplexity": "PERPLEXITY_API_KEY",
            # Add other common ones if MODEL_MAP parsing is too complex
        }
        if provider_name_lower in key_map:
            env_var_name = key_map[provider_name_lower]
        elif provider_name_lower in VALID_PROVIDERS: # If it's a known provider from supported-models
             # Simple heuristic for env var name
            env_var_name = f"{provider_name_lower.upper()}_API_KEY"
            logger.debug(f"Guessed API key env var name for '{provider_name_lower}' as '{env_var_name}'.")


    if not env_var_name:
        logger.warning(f"Could not determine API key environment variable for provider: '{provider_name}'. Marking as not set.")
        return False

    logger.debug(f"Checking API key for provider '{provider_name}' using env var '{env_var_name}'.")
    api_key_value = resolve_env_variable(env_var_name, session, project_root_override)
    
    if not api_key_value or not api_key_value.strip():
        logger.debug(f"API key for '{provider_name}' ('{env_var_name}') is not set or empty.")
        return False
    if "YOUR_" in api_key_value and ("API_KEY" in api_key_value or "KEY_HERE" in api_key_value): # Basic placeholder check
        logger.warning(f"API key for '{provider_name}' ('{env_var_name}') appears to be a placeholder: '{api_key_value[:20]}...'.")
        return False
        
    logger.info(f"API key for '{provider_name}' ('{env_var_name}') is considered SET.")
    return True

if __name__ == "__main__":
    # Ensure python_src/supported-models.json exists and is a copy of scripts/modules/supported-models.json
    # Test basic config loading
    print("--- Testing Config Loading ---")
    # Create a dummy .taskmasterconfig in the project root for more thorough testing
    _test_project_root = _find_project_root()
    if _test_project_root:
        _dummy_config_path = pathlib.Path(_test_project_root) / CONFIG_FILE_NAME
        _original_config_content = None
        if _dummy_config_path.exists():
            with open(_dummy_config_path, "r") as f_orig:
                _original_config_content = f_orig.read()
        
        _test_config_data = {
            "models": {"main": {"provider": "openai", "model_id": "gpt-4"}, "research": {"provider": "google", "model_id": "gemini-1.5-pro-latest"}},
            "global": {"project_name": "Test Project TM", "debug": True}
        }
        with open(_dummy_config_path, "w") as f_test:
            json.dump(_test_config_data, f_test, indent=2)
        print(f"Created dummy config at {_dummy_config_path}")

    current_config = get_config(force_reload=True) # Force reload for testing
    if current_config:
        print(f"Project Name from config: {current_config.get('global', {}).get('project_name')}")
        assert current_config.get('global', {}).get('project_name') == "Test Project TM"
        print(f"Main model provider: {current_config.get('models', {}).get('main', {}).get('provider')}")
        assert current_config.get('models', {}).get('main', {}).get('provider') == "openai"
        print(f"Debug flag: {get_debug_flag()}")
        assert get_debug_flag() is True
        print(f"User ID: {get_user_id()}") # Test user ID creation/retrieval (might save config)

    # Test API key check (will depend on your .env or environment variables)
    # Create a dummy .env in the project root for this test if needed:
    # OPENAI_API_KEY="sk-real-key-for-testing"
    # GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY_HERE" 
    print("\n--- Testing API Key Resolution ---")
    if _test_project_root:
        _dummy_env_path = pathlib.Path(_test_project_root) / ".env"
        _original_env_content = None
        if _dummy_env_path.exists():
             with open(_dummy_env_path, "r") as f_env_orig:
                _original_env_content = f_env_orig.read()
        with open(_dummy_env_path, "w") as f_env:
            f_env.write("OPENAI_API_KEY=sk-dummy-key-from-env-test\n")
            f_env.write("GOOGLE_API_KEY=actual_google_key_not_placeholder\n") # Test non-placeholder
        print(f"Created dummy .env at {_dummy_env_path}")
        # Force reload of any cached env vars by python-dotenv by re-importing (hacky) or using its load function directly
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=_dummy_env_path, override=True)


    print(f"OpenAI API Key Set: {is_api_key_set('openai', project_root_override=_test_project_root)}")
    assert is_api_key_set('openai', project_root_override=_test_project_root) is True
    print(f"OpenAI API Key Value: {resolve_env_variable('OPENAI_API_KEY', project_root_override=_test_project_root)}")


    print(f"Google API Key Set: {is_api_key_set('google', project_root_override=_test_project_root)}")
    assert is_api_key_set('google', project_root_override=_test_project_root) is True
    print(f"Google API Key Value: {resolve_env_variable('GOOGLE_API_KEY', project_root_override=_test_project_root)}")
    
    print(f"Anthropic API Key Set (not in .env): {is_api_key_set('anthropic', project_root_override=_test_project_root)}")
    assert is_api_key_set('anthropic', project_root_override=_test_project_root) is False
    print(f"Ollama API Key Set (should be True): {is_api_key_set('ollama')}")
    assert is_api_key_set('ollama') is True
    
    # Test writing config
    print("\n--- Testing Config Writing ---")
    if current_config:
        current_config["global"]["project_name"] = "Task Master Py Test Write"
        if write_config(current_config, _test_project_root): # Write to test project root
            reloaded_config = get_config(explicit_root=_test_project_root, force_reload=True)
            print(f"New project name after write: {reloaded_config.get('global', {}).get('project_name')}")
            assert reloaded_config.get('global', {}).get('project_name') == "Task Master Py Test Write"
            # Revert change by writing defaults back for project name
            current_config["global"]["project_name"] = _test_config_data["global"]["project_name"] # Revert to dummy's original
            write_config(current_config, _test_project_root)


    print("\n--- Testing Parameters for Role ---")
    # Based on dummy config: main=openai/gpt-4, research=google/gemini-1.5-pro-latest
    # MODEL_MAP needs to be loaded for this. Assuming supported-models.json is present.
    if not MODEL_MAP:
        print("MODEL_MAP not loaded, cannot test parameters accurately.")
    else:
        main_params = get_parameters_for_role("main", explicit_root=_test_project_root)
        print(f"Main role params (openai/gpt-4 from dummy config): Max Tokens: {main_params['max_tokens']}, Temperature: {main_params['temperature']}")
        # Add assertions based on your supported-models.json content for gpt-4 if present
        # e.g. if gpt-4 has max_tokens 8192 in supported-models.json, and dummy config has 64000, it should be 8192.
        # Default max_tokens for main in DEFAULTS is 64000.
        # If gpt-4 is in MODEL_MAP and has a specific max_token, it will be min(role_config_max_token, model_map_max_token)
        # For the dummy config, no max_tokens or temperature are specified for main, so it will take from DEFAULTS.models.main or MODEL_MAP.
        # The current logic uses DEFAULTS for role's max_tokens/temp if not in role_config.
        # Then it applies min(role_max_tokens, model_specific_max_tokens_from_map).
        # DEFAULTS.models.main.max_tokens = 64000. If gpt-4 in map has 8192, result should be 8192.
        
        research_params = get_parameters_for_role("research", explicit_root=_test_project_root)
        print(f"Research role params (google/gemini-1.5-pro-latest from dummy config): Max Tokens: {research_params['max_tokens']}, Temperature: {research_params['temperature']}")
        # Similar logic for research role. DEFAULTS.models.research.max_tokens = 8700.
        # If gemini-1.5-pro-latest in map has e.g. 128000, result should be 8700.

    print(f"\n--- Loaded MODEL_MAP Keys (Providers) ---")
    print(list(MODEL_MAP.keys()))
    if "google" in MODEL_MAP:
        print(f"Google Models in MAP: {[m.get('id') for m in MODEL_MAP['google']]}")

    # Cleanup dummy files
    if _test_project_root:
        if _original_config_content is None:
            _dummy_config_path.unlink(missing_ok=True)
            print(f"Removed dummy config file: {_dummy_config_path}")
        else:
            with open(_dummy_config_path, "w") as f_orig_restore:
                f_orig_restore.write(_original_config_content)
            print(f"Restored original config file: {_dummy_config_path}")

        if _original_env_content is None:
            _dummy_env_path.unlink(missing_ok=True)
            print(f"Removed dummy .env file: {_dummy_env_path}")
        else:
            with open(_dummy_env_path, "w") as f_env_restore:
                f_env_restore.write(_original_env_content)
            print(f"Restored original .env file: {_dummy_env_path}")
        # Reload environment from original .env if it existed, or clear the dummy vars
        # This is tricky as python-dotenv modifies os.environ.
        # For a clean test environment, tests should run in a subprocess or manage os.environ carefully.
        # For now, just reload the original .env if it existed.
        if _original_env_content and _dummy_env_path.exists():
             load_dotenv(dotenv_path=_dummy_env_path, override=True)


    print("\n--- Config Manager Tests Complete ---")
