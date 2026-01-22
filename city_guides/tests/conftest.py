"""
Pytest configuration for Travelland tests.

This file is automatically loaded by pytest and sets up the test environment.
"""
import os
import pytest

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables before any tests run."""
    os.environ["DISABLE_PREWARM"] = "true"
    os.environ["REDIS_URL"] = ""
    os.environ["TESTING"] = "true"
    yield
    # Cleanup after all tests
    os.environ.pop("TESTING", None)


@pytest.fixture
def app_client():
    """Create a test client for the Quart app."""
    from app import app
    
    app.config["TESTING"] = True
    
    client = app.test_client()
    yield client
    try:
        client.close()
    except Exception:
        pass
