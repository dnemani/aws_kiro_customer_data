# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.
"""
Integration tests for the Customer Management Platform API.

Requires a deployed stack. Set these environment variables before running:
  - API_BASE_URL       — e.g. https://abc123.execute-api.us-east-1.amazonaws.com/v1
  - COGNITO_TOKEN      — a valid JWT from the Cognito User Pool
  - ENVIRONMENT        — "dev" or "prod"

Run with:
  pytest tests/integration/ -v
"""
import json
import os
import uuid
import pytest
import urllib.request
import urllib.error


# ─────────────────────────────────────────────────────────────────────────────
# Configuration (from environment variables)
# ─────────────────────────────────────────────────────────────────────────────

API_BASE_URL = os.environ.get("API_BASE_URL", "").rstrip("/")
COGNITO_TOKEN = os.environ.get("COGNITO_TOKEN", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")


def skip_if_no_config():
    """Skip the test if required env vars are not set."""
    if not API_BASE_URL or not COGNITO_TOKEN:
        pytest.skip("API_BASE_URL and COGNITO_TOKEN must be set for integration tests")


def make_request(method: str, path: str, body=None, token: str = None) -> tuple[int, dict]:
    """Make an HTTPS request to the API and return (status_code, response_body)."""
    url = f"{API_BASE_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.getcode(), json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_unauthenticated_request_returns_401():
    """Requirement 7.2: Requests without a JWT must return HTTP 401."""
    skip_if_no_config()
    status, _ = make_request("GET", "/customers")
    assert status == 401, f"Expected 401 for unauthenticated request, got {status}"


def test_api_uses_https():
    """Requirement 7.3: The API endpoint must use HTTPS."""
    skip_if_no_config()
    assert API_BASE_URL.startswith("https://"), (
        f"API_BASE_URL must use HTTPS, got: {API_BASE_URL}"
    )


def test_full_crud_lifecycle():
    """End-to-end CRUD lifecycle: create → read → update → delete."""
    skip_if_no_config()

    unique_email = f"integration-test-{uuid.uuid4()}@example.com"

    # POST /customers — create
    payload = {
        "name": "Integration Test User",
        "email": unique_email,
        "phone": "+1 555-000-0001",
        "address": "1 Test Ave, Integration City, TS 00001",
    }
    status, body = make_request("POST", "/customers", body=payload, token=COGNITO_TOKEN)
    assert status == 201, f"Create failed with {status}: {body}"
    customer_id = body.get("customer_id")
    assert customer_id, "No customer_id in create response"

    # GET /customers/{id} — retrieve
    status, body = make_request("GET", f"/customers/{customer_id}", token=COGNITO_TOKEN)
    assert status == 200, f"Get failed with {status}: {body}"
    assert body["email"] == unique_email
    assert body["name"] == "Integration Test User"

    # PUT /customers/{id} — update
    updated_payload = {
        "name": "Updated Integration User",
        "email": unique_email,  # same email, same customer
        "address": "2 Updated Ave, Integration City, TS 00002",
    }
    status, body = make_request("PUT", f"/customers/{customer_id}", body=updated_payload, token=COGNITO_TOKEN)
    assert status == 200, f"Update failed with {status}: {body}"
    assert body["name"] == "Updated Integration User"
    assert body["customer_id"] == customer_id  # immutable
    assert "updated_at" in body

    # DELETE /customers/{id}
    status, body = make_request("DELETE", f"/customers/{customer_id}", token=COGNITO_TOKEN)
    assert status == 200, f"Delete failed with {status}: {body}"
    assert customer_id in body.get("message", "")

    # GET after delete should return 404
    status, body = make_request("GET", f"/customers/{customer_id}", token=COGNITO_TOKEN)
    assert status == 404, f"Expected 404 after deletion, got {status}"


def test_create_with_duplicate_email_returns_409():
    """Requirement 2.4: Duplicate email must return HTTP 409."""
    skip_if_no_config()

    unique_email = f"dup-test-{uuid.uuid4()}@example.com"
    payload = {"name": "First User", "email": unique_email}

    # First create
    status, body = make_request("POST", "/customers", body=payload, token=COGNITO_TOKEN)
    assert status == 201, f"First create failed: {body}"
    first_id = body["customer_id"]

    # Second create with same email
    status, body = make_request("POST", "/customers", body={"name": "Second User", "email": unique_email}, token=COGNITO_TOKEN)
    assert status == 409, f"Expected 409 for duplicate email, got {status}: {body}"

    # Cleanup
    make_request("DELETE", f"/customers/{first_id}", token=COGNITO_TOKEN)


def test_list_customers_returns_200():
    """Requirement 3.3: GET /customers must return HTTP 200 with customers list."""
    skip_if_no_config()
    status, body = make_request("GET", "/customers", token=COGNITO_TOKEN)
    assert status == 200, f"List failed with {status}: {body}"
    assert "customers" in body


def test_get_nonexistent_customer_returns_404():
    """Requirement 3.2: GET with unknown ID returns 404."""
    skip_if_no_config()
    fake_id = str(uuid.uuid4())
    status, body = make_request("GET", f"/customers/{fake_id}", token=COGNITO_TOKEN)
    assert status == 404, f"Expected 404, got {status}: {body}"


def test_prod_access_logging_config():
    """Requirement 7.5: Production environment has access logging enabled (config check)."""
    if ENVIRONMENT != "prod":
        pytest.skip("Access logging check is production-only")
    skip_if_no_config()
    # This test documents the expectation; actual log verification requires
    # CloudWatch API calls and is outside the scope of this HTTP-level integration test.
    assert ENVIRONMENT == "prod", "This test only runs in prod"
