import time
import logging
from typing import Any, Dict, List, Literal, Optional, Union
import json # Added import for json

from langchain_google_genai import ChatGoogleGenerativeAi
from langchain_openai import ChatOpenAI
# We will add configuration management later
# from .config_manager import get_config, get_model_config_for_role 

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_RETRY_DELAY_MS = 1000

# Placeholder for provider and model configuration
# This will eventually be loaded from a config file (equivalent to config-manager.js)
# For now, we can use a mock structure.
MOCK_CONFIG = {
    "main": {"provider": "google", "model_id": "gemini-pro"},
    "research": {"provider": "openai", "model_id": "gpt-3.5-turbo"},
    "fallback": {"provider": "openai", "model_id": "gpt-3.5-turbo"},
    "params": {
        "main": {"max_tokens": 1000, "temperature": 0.7},
        "research": {"max_tokens": 1500, "temperature": 0.5},
        "fallback": {"max_tokens": 1000, "temperature": 0.7},
    },
    "api_keys": { # This will be handled by a proper config/secrets manager
        "google_api_key": "YOUR_GOOGLE_API_KEY",
        "openai_api_key": "YOUR_OPENAI_API_KEY",
    }
}

class AIService:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config if config else MOCK_CONFIG # Later use config_manager

    def _get_llm_client(self, provider: str, model_id: str, api_key: Optional[str] = None):
        if provider == "google":
            key = api_key or self.config.get("api_keys", {}).get("google_api_key")
            if not key:
                raise ValueError("Google API Key not found in config.")
            return ChatGoogleGenerativeAi(model=model_id, google_api_key=key)
        elif provider == "openai":
            key = api_key or self.config.get("api_keys", {}).get("openai_api_key")
            if not key:
                raise ValueError("OpenAI API Key not found in config.")
            return ChatOpenAI(model=model_id, openai_api_key=key)
        # Add other providers as needed (e.g., Anthropic)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def _is_retryable_error(self, error: Exception) -> bool:
        # Basic retryable error check, can be expanded
        error_str = str(error).lower()
        retryable_terms = ["rate limit", "overloaded", "service temporarily unavailable", "timeout", "network error"]
        if any(term in error_str for term in retryable_terms):
            return True
        # Add status code checks if the error object has them (e.g., from HTTP exceptions)
        # if hasattr(error, 'status_code') and error.status_code in [429, 500, 502, 503, 504]:
        #     return True
        return False

    def _call_llm_with_retries(
        self,
        llm_client: Any, # Langchain LLM client
        messages: List[Dict[str, str]], # e.g. [{"role": "user", "content": "Hello"}]
        attempt_role: str, # For logging
        provider_name: str, # For logging
        model_id: str # For logging
    ) -> Any: # Langchain LLM response (AIMessage, etc.)
        retries = 0
        while retries <= MAX_RETRIES:
            try:
                logger.info(f"Attempt {retries + 1}/{MAX_RETRIES + 1} calling LLM (Provider: {provider_name}, Model: {model_id}, Role: {attempt_role})")
                # Langchain's invoke method is typically used for a single call
                response = llm_client.invoke(messages)
                logger.info(f"LLM call succeeded for role {attempt_role} (Provider: {provider_name}) on attempt {retries + 1}")
                return response
            except Exception as e:
                logger.warning(f"Attempt {retries + 1} failed for role {attempt_role} (Provider: {provider_name}): {e}")
                if self._is_retryable_error(e) and retries < MAX_RETRIES:
                    retries += 1
                    delay = (INITIAL_RETRY_DELAY_MS * (2 ** (retries - 1))) / 1000  # in seconds
                    logger.info(f"Retryable error. Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"Max retries reached or non-retryable error for role {attempt_role} (Provider: {provider_name}).")
                    raise e
        raise Exception(f"Exhausted all retries for role {attempt_role} (Provider: {provider_name})")


    def _unified_service_runner(
        self,
        service_type: Literal["generate_text", "stream_text", "generate_object"],
        initial_role: Literal["main", "research", "fallback"],
        prompt: str,
        system_prompt: Optional[str] = None,
        # schema: Optional[Any] = None, # For generate_object with Langchain output parsers
        # object_name: Optional[str] = None, # For generate_object
        command_name: str = "unknown_command", # For telemetry
        output_type: Literal["cli", "mcp"] = "cli", # For telemetry/logging differences
        **kwargs 
    ) -> Dict[str, Any]:
        
        # Determine role sequence (main -> fallback -> research or research -> fallback -> main)
        sequence: List[Literal["main", "research", "fallback"]]
        if initial_role == "main":
            sequence = ["main", "research", "fallback"] # Original JS logic was main -> fallback -> research. Adjusted to match typical preference.
        elif initial_role == "research":
            sequence = ["research", "main", "fallback"] # Original JS logic was research -> fallback -> main.
        elif initial_role == "fallback":
            sequence = ["fallback", "main", "research"]
        else:
            logger.warning(f"Unknown initial role: {initial_role}. Defaulting to main -> research -> fallback.")
            sequence = ["main", "research", "fallback"]

        last_error: Optional[Exception] = None
        
        for current_role in sequence:
            provider_config = self.config.get(current_role)
            if not provider_config or not provider_config.get("provider") or not provider_config.get("model_id"):
                logger.warning(f"Skipping role '{current_role}': Provider or Model ID not configured.")
                last_error = last_error or ValueError(f"Configuration missing for role '{current_role}'.")
                continue

            provider_name = provider_config["provider"]
            model_id = provider_config["model_id"]
            # role_params = self.config.get("params", {}).get(current_role, {}) # For max_tokens, temp

            try:
                logger.info(f"Attempting AI service call with role: {current_role} (Provider: {provider_name}, Model: {model_id})")
                
                # API key will be fetched by _get_llm_client based on provider_name
                llm_client = self._get_llm_client(provider_name, model_id)

                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                if service_type == "generate_text":
                    response = self._call_llm_with_retries(llm_client, messages, current_role, provider_name, model_id)
                    # Langchain AIMessage has 'content' attribute
                    text_content = response.content if hasattr(response, 'content') else str(response)
                    
                    # TODO: Add telemetry logging similar to logAiUsage from JS
                    # telemetry_data = self.log_ai_usage(...)
                    
                    return {"main_result": text_content, "telemetry_data": None} # Placeholder for telemetry
                
                elif service_type == "stream_text":
                    # Streaming with Langchain: llm.stream()
                    # This will require a different handling of response and telemetry
                    logger.warning("stream_text is not fully implemented yet with Langchain.")
                    # For now, simulate with a non-streaming call
                    response = self._call_llm_with_retries(llm_client, messages, current_role, provider_name, model_id)
                    return {"main_result": response.content if hasattr(response, 'content') else str(response), "telemetry_data": None}


                elif service_type == "generate_object":
                    # Object generation with Langchain often involves output parsers
                    # or models specifically fine-tuned for function calling/JSON output.
                    # This is a simplified version.
                    logger.warning("generate_object is not fully implemented yet with Langchain's structured output features.")
                    # For now, simulate with a non-streaming call, expecting JSON in string
                    response = self._call_llm_with_retries(llm_client, messages, current_role, provider_name, model_id)
                    # Attempt to parse if the model is expected to return JSON string
                    # This part needs to be robust and align with how models are prompted for JSON.
                    try:
                        parsed_object = json.loads(response.content) if hasattr(response, 'content') else json.loads(str(response))
                        return {"main_result": parsed_object, "telemetry_data": None}
                    except json.JSONDecodeError as json_err:
                        logger.error(f"Failed to parse LLM response as JSON for generate_object: {json_err}")
                        raise ValueError(f"LLM response for generate_object was not valid JSON: {response.content[:100]}...") # Show first 100 chars

                else:
                    raise ValueError(f"Unsupported service type: {service_type}")

            except Exception as e:
                logger.error(f"Service call failed for role {current_role} (Provider: {provider_name}, Model: {model_id}): {e}")
                last_error = e
        
        logger.error(f"All roles in the sequence [{', '.join(sequence)}] failed.")
        if last_error:
            raise last_error
        else:
            raise Exception("AI service call failed for all configured roles.")

    def generate_text_service(self, role: Literal["main", "research", "fallback"], prompt: str, **kwargs) -> Dict[str, Any]:
        return self._unified_service_runner("generate_text", initial_role=role, prompt=prompt, **kwargs)

    def stream_text_service(self, role: Literal["main", "research", "fallback"], prompt: str, **kwargs) -> Dict[str, Any]:
        # Placeholder: Streaming needs specific handling for iterating over chunks
        logger.warning("Streaming is not fully implemented. Returning non-streamed result for now.")
        return self._unified_service_runner("generate_text", initial_role=role, prompt=prompt, **kwargs) # Fallback to generate_text

    def generate_object_service(self, role: Literal["main", "research", "fallback"], prompt: str, **kwargs) -> Dict[str, Any]:
        # Placeholder: Object generation might require specific prompting or model features
        logger.warning("Object generation is not fully implemented. Expecting JSON string in response.")
        return self._unified_service_runner("generate_object", initial_role=role, prompt=prompt, **kwargs)

    # TODO: Implement log_ai_usage equivalent for telemetry

if __name__ == '__main__':
    # Example Usage (requires API keys to be set in MOCK_CONFIG or environment)
    # Ensure you have your API keys in the MOCK_CONFIG above or set as environment variables
    # that the config_manager (when integrated) would pick up.
    
    ai_service = AIService()

    try:
        print("\n--- Testing generate_text_service (main role) ---")
        # Replace with actual API keys in MOCK_CONFIG or ensure your config solution loads them
        if MOCK_CONFIG["api_keys"]["google_api_key"] == "YOUR_GOOGLE_API_KEY" or \
           MOCK_CONFIG["api_keys"]["openai_api_key"] == "YOUR_OPENAI_API_KEY":
            print("SKIPPING TEST: API keys not set in MOCK_CONFIG. Please update them to run the example.")
        else:
            response_main = ai_service.generate_text_service(
                role="main", 
                prompt="Hello, what is the weather like today in Mountain View, CA?",
                system_prompt="You are a helpful assistant.",
                command_name="test_main_text"
            )
            print("Main response:", response_main["main_result"])

            # print("\n--- Testing generate_text_service (research role) ---")
            # response_research = ai_service.generate_text_service(
            #     role="research",
            #     prompt="What are the latest advancements in AI as of late 2023?",
            #     system_prompt="You are a research assistant.",
            #     command_name="test_research_text"
            # )
            # print("Research response:", response_research["main_result"])

            # print("\n--- Testing generate_object_service (main role) ---")
            # # This requires the model to be prompted to return JSON.
            # # The prompt below is a simple example and might need adjustment.
            # object_prompt = "Return a JSON object with two keys: 'name' (string) and 'age' (integer). Example: {\"name\": \"John Doe\", \"age\": 30}"
            # response_object = ai_service.generate_object_service(
            #     role="main",
            #     prompt=object_prompt,
            #     system_prompt="You are an assistant that returns JSON.",
            #     command_name="test_main_object"
            # )
            # print("Object response:", response_object["main_result"])

    except Exception as e:
        print(f"An error occurred during testing: {e}")
