import unittest
import json
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.config_manager import ConfigManager
from src.data_models import AppConfig, ModelConfig, SecretStr, AnyHttpUrl

class TestConfigManager(unittest.TestCase):

    def setUp(self):
        """Set up a temporary workspace for each test."""
        self.test_workspace = Path(tempfile.mkdtemp())
        self.config_filename = ".taskmasterconfig"
        self.config_file_path = self.test_workspace / self.config_filename

    def tearDown(self):
        """Clean up the temporary workspace after each test."""
        shutil.rmtree(self.test_workspace)

    def _create_dummy_config_file(self, content: dict):
        """Helper to create a dummy config file."""
        with open(self.config_file_path, 'w', encoding='utf-8') as f:
            json.dump(content, f)

    def test_init_no_config_file(self):
        """Test initialization when no config file exists."""
        # ConfigManager should create a default config and save it
        manager = ConfigManager(str(self.test_workspace), self.config_filename)
        
        self.assertIsInstance(manager.config, AppConfig)
        self.assertTrue(self.config_file_path.exists())
        
        # Verify default models are set
        self.assertIsNotNone(manager.config.main_model)
        self.assertIsNotNone(manager.config.research_model)
        self.assertIsNotNone(manager.config.fallback_model)
        self.assertEqual(manager.config.main_model.provider, "google")

    def test_init_with_existing_valid_config_file(self):
        """Test initialization with an existing valid config file."""
        valid_config_data = {
            "main_model": {"model_name": "test-main", "provider": "openai", "api_key": "sk-test"},
            "research_model": {"model_name": "test-research", "provider": "anthropic"},
            "fallback_model": {"model_name": "test-fallback", "provider": "google", "base_url": "http://localhost:8000"}
        }
        self._create_dummy_config_file(valid_config_data)

        manager = ConfigManager(str(self.test_workspace), self.config_filename)
        
        self.assertIsInstance(manager.config, AppConfig)
        self.assertEqual(manager.config.main_model.model_name, "test-main")
        self.assertEqual(manager.config.main_model.provider, "openai")
        self.assertEqual(manager.config.main_model.api_key.get_secret_value(), "sk-test")
        self.assertEqual(str(manager.config.fallback_model.base_url), "http://localhost:8000/")

    def test_load_or_initialize_config_corrupt_file(self):
        """Test handling of a corrupt/invalid config file."""
        with open(self.config_file_path, 'w', encoding='utf-8') as f:
            f.write("this is not valid json {") # Corrupt JSON

        # Expect it to fall back to default config and save it
        manager = ConfigManager(str(self.test_workspace), self.config_filename)
        self.assertIsInstance(manager.config, AppConfig)
        self.assertEqual(manager.config.main_model.provider, "google")
        # Ensure it attempts to save a valid default config
        with open(self.config_file_path, 'r', encoding='utf-8') as f:
            reloaded_content = json.load(f)
            self.assertIn("main_model", reloaded_content)

    def test_load_or_initialize_config_invalid_schema(self):
        """Test handling of a config file with invalid schema."""
        # Make the schema clearly invalid at the top level to force validation error
        invalid_schema_config = {
            "invalid_root_key": "some_value",
            "another_invalid": ["list", "of", "things"]
        }
        self._create_dummy_config_file(invalid_schema_config)

        # Expect it to fall back to default config and save it
        manager = ConfigManager(str(self.test_workspace), self.config_filename)
        self.assertIsInstance(manager.config, AppConfig)
        self.assertEqual(manager.config.main_model.provider, "google") # Should be google, as it falls back to defaults
        # Ensure it attempts to save a valid default config
        with open(self.config_file_path, 'r', encoding='utf-8') as f:
            reloaded_content = json.load(f)
            self.assertIn("main_model", reloaded_content)
            self.assertEqual(reloaded_content["main_model"]["provider"], "google") # Verify saved default

    def test_save_config(self):
        """Test save_config method correctly writes to file and handles Pydantic serialization."""
        manager = ConfigManager(str(self.test_workspace), self.config_filename)
        
        # Simulate a change in config including SecretStr and AnyHttpUrl
        new_main_model = ModelConfig(
            model_name="new-model", 
            provider="test-provider", 
            api_key=SecretStr("my_secret_key"), 
            base_url=AnyHttpUrl("http://custom-api.com")
        )
        manager.config.main_model = new_main_model
        
        manager.save_config()

        self.assertTrue(self.config_file_path.exists())
        with open(self.config_file_path, 'r', encoding='utf-8') as f:
            saved_content = json.load(f)
        
        self.assertEqual(saved_content["main_model"]["model_name"], "new-model")
        self.assertEqual(saved_content["main_model"]["provider"], "test-provider")
        # Pydantic's model_dump serializes SecretStr to its value, and AnyHttpUrl to string
        self.assertEqual(saved_content["main_model"]["api_key"], "my_secret_key")
        self.assertEqual(saved_content["main_model"]["base_url"], "http://custom-api.com/") # AnyHttpUrl adds trailing slash

    def test_get_model_config(self):
        """Test get_model_config for different model types."""
        manager = ConfigManager(str(self.test_workspace), self.config_filename) # Initializes with defaults
        
        main_config = manager.get_model_config("main")
        self.assertIsNotNone(main_config)
        self.assertEqual(main_config.model_name, "gemini-2.0-flash")
        self.assertEqual(main_config.provider, "google")

        research_config = manager.get_model_config("research")
        self.assertIsNotNone(research_config)
        self.assertEqual(research_config.model_name,
                         "gemini-2.5-flash-preview-05-20")
        self.assertEqual(research_config.provider, "google")

        fallback_config = manager.get_model_config("fallback")
        self.assertIsNotNone(fallback_config)
        self.assertEqual(fallback_config.model_name, "gemini-2.0-flash")
        self.assertEqual(fallback_config.provider, "google")

        self.assertIsNone(manager.get_model_config("invalid_type"))

    def test_set_model_config(self):
        """Test set_model_config updates and saves the configuration."""
        manager = ConfigManager(str(self.test_workspace), self.config_filename)
        
        new_research_model = ModelConfig(
            model_name="claude-3-sonnet", 
            provider="anthropic", 
            api_key=SecretStr("anthropic-key"), 
            base_url=AnyHttpUrl("https://api.anthropic.com")
        )
        manager.set_model_config("research", new_research_model)

        # Verify in-memory config updated
        updated_research_config = manager.config.research_model
        self.assertIsNotNone(updated_research_config)
        self.assertEqual(updated_research_config.model_name, "claude-3-sonnet")
        self.assertEqual(updated_research_config.provider, "anthropic")
        self.assertEqual(updated_research_config.api_key.get_secret_value(), "anthropic-key")
        self.assertEqual(str(updated_research_config.base_url), "https://api.anthropic.com/")

        # Verify saved config updated
        with open(self.config_file_path, 'r', encoding='utf-8') as f:
            saved_content = json.load(f)
        
        self.assertEqual(saved_content["research_model"]["model_name"], "claude-3-sonnet")
        self.assertEqual(saved_content["research_model"]["provider"], "anthropic")
        self.assertIn("api_key", saved_content["research_model"])
        self.assertIn("base_url", saved_content["research_model"])
        # Ensure SecretStr is serialized as its value, not the object
        self.assertEqual(saved_content["research_model"]["api_key"], "anthropic-key")
        self.assertEqual(saved_content["research_model"]["base_url"], "https://api.anthropic.com/")

        # Test setting main model
        new_main_model = ModelConfig(model_name="gpt-4o", provider="openai")
        manager.set_model_config("main", new_main_model)
        self.assertEqual(manager.config.main_model.model_name, "gpt-4o")
        with open(self.config_file_path, 'r', encoding='utf-8') as f:
            saved_content = json.load(f)
        self.assertEqual(saved_content["main_model"]["model_name"], "gpt-4o")

        with self.assertRaises(ValueError):
            manager.set_model_config("invalid_type", new_main_model)

    def test_get_all_model_configs(self):
        """Test get_all_model_configs returns all current model configurations."""
        manager = ConfigManager(str(self.test_workspace), self.config_filename)
        
        all_configs = manager.get_all_model_configs()
        
        self.assertIsInstance(all_configs, dict)
        self.assertIn("main", all_configs)
        self.assertIn("research", all_configs)
        self.assertIn("fallback", all_configs)

        # Verify the types are ModelConfig or None
        self.assertIsInstance(all_configs["main"], ModelConfig)
        self.assertIsInstance(all_configs["research"], ModelConfig)
        self.assertIsInstance(all_configs["fallback"], ModelConfig)

        # Modify one and re-check
        new_fallback_model = ModelConfig(model_name="test-fallback-new", provider="test")
        manager.set_model_config("fallback", new_fallback_model)
        updated_all_configs = manager.get_all_model_configs()
        
        self.assertEqual(updated_all_configs["fallback"].model_name, "test-fallback-new")

if __name__ == '__main__':
    unittest.main()