import pytest
import os

def requires_api_key(*args, **kwargs):
    """Skip test if no API key is available."""
    return pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY"),
        reason="GOOGLE_API_KEY environment variable not set"
    )
