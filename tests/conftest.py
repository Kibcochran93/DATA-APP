"""
Pytest configuration and fixtures for test suite.
Provides proper Streamlit session state mocking and common fixtures.
"""

import pytest
import sys
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import pandas as pd


class MockSessionState(dict):
    """
    Mock Streamlit session state that behaves like both a dict and allows
    attribute access (which is how Streamlit's session_state works).
    """
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'MockSessionState' object has no attribute '{key}'")
    
    def __setattr__(self, key, value):
        self[key] = value
    
    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(f"'MockSessionState' object has no attribute '{key}'")


@pytest.fixture(autouse=True)
def mock_streamlit_session_state(monkeypatch):
    """
    Automatically mock st.session_state for all tests.
    Creates a fresh MockSessionState for each test.
    """
    import streamlit as st
    mock_state = MockSessionState()
    monkeypatch.setattr(st, 'session_state', mock_state)
    return mock_state


@pytest.fixture
def mock_monitoring():
    """Create a mock monitoring instance."""
    monitoring = MagicMock()
    monitoring.log = MagicMock()
    monitoring.track = MagicMock()
    monitoring.track_event = MagicMock()
    monitoring.get_metrics = MagicMock(return_value={})
    monitoring.get_events = MagicMock(return_value=[])
    monitoring.get_health_status = MagicMock(return_value={'status': 'healthy'})
    return monitoring


@pytest.fixture
def mock_protection():
    """Create a mock data protection instance."""
    protection = MagicMock()
    protection.mask_pii = MagicMock(side_effect=lambda df: df)
    protection.encrypt = MagicMock(side_effect=lambda x: x)
    protection.decrypt = MagicMock(side_effect=lambda x: x)
    return protection


@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame({
        'A': [1, 2, 3],
        'B': [4, 5, 6],
        'C': ['x', 'y', 'z']
    })


@pytest.fixture
def admin_user():
    """Create an admin user dict."""
    return {'role': 'admin', 'username': 'admin_user'}


@pytest.fixture
def regular_user():
    """Create a regular user dict."""
    return {'role': 'user', 'username': 'regular_user'}


# Helper to get timezone-aware UTC datetime (replaces deprecated utcnow)
def utcnow():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)
