# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.
"""
Shared pytest fixtures for the Customer Management Platform test suite.
"""
import json
import os
import pytest


@pytest.fixture
def mock_context():
    """A minimal Lambda context object for unit tests."""
    class MockContext:
        function_name = "test-function"
        memory_limit_in_mb = 128
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
        aws_request_id = "test-request-id"
    return MockContext()


@pytest.fixture
def customer_payload():
    """A valid customer payload for use in tests."""
    return {
        "name": "Jane Smith",
        "email": "jane.smith@example.com",
        "phone": "+1 555-123-4567",
        "address": "123 Main St, Anytown, CA 90210",
    }


@pytest.fixture
def load_event():
    """Helper to load event fixtures from tests/unit/events/."""
    def _load(filename):
        base = os.path.dirname(__file__)
        path = os.path.join(base, "tests", "unit", "events", filename)
        with open(path) as f:
            return json.load(f)
    return _load
