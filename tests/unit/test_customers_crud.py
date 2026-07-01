# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.
"""
Property-based and example tests for the Customers CRUD Lambda handlers.

DynamoDB is mocked with ``moto``. Each property example runs against a freshly
created table (via the ``fresh_dynamodb`` context manager) so state never leaks
between generated examples.

Feature: customer-management-platform
"""
import importlib.util
import json
import os
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime
from unittest import mock

import boto3
from botocore.exceptions import ClientError
from hypothesis import given, settings, strategies as st
from moto import mock_aws

# ─────────────────────────────────────────────────────────────────────────────
# Environment + module loading
# ─────────────────────────────────────────────────────────────────────────────

TABLE_NAME = "customer_records_test"
EMAIL_INDEX = "email-index"
REGION = "us-east-1"

os.environ["TABLE_NAME"] = TABLE_NAME
os.environ["EMAIL_INDEX_NAME"] = EMAIL_INDEX
os.environ["AWS_REGION"] = REGION
os.environ["AWS_DEFAULT_REGION"] = REGION
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"


def _load_customers():
    """Load the customers Lambda under a unique module name to avoid clashing
    with the identically named authorizer ``lambda_function`` module."""
    path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "src", "customers",
            "lambda_function.py",
        )
    )
    spec = importlib.util.spec_from_file_location("customers_lambda_function", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["customers_lambda_function"] = module
    spec.loader.exec_module(module)
    return module


customers = _load_customers()


@contextmanager
def fresh_dynamodb():
    """Provision an isolated moto DynamoDB table matching the production schema."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name=REGION)
        client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "customer_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": "email", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
            GlobalSecondaryIndexes=[
                {
                    "IndexName": EMAIL_INDEX,
                    "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )
        yield boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)


def _event(method, resource, *, body=None, path_params=None, query_params=None):
    return {
        "httpMethod": method,
        "resource": resource,
        "pathParameters": path_params,
        "queryStringParameters": query_params,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body) if body is not None else None,
    }


def _parse_iso(value):
    """Parse an ISO 8601 UTC timestamp string (handles the trailing 'Z')."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ─────────────────────────────────────────────────────────────────────────────
# Strategies for valid customer bodies
# ─────────────────────────────────────────────────────────────────────────────

_printable = st.characters(min_codepoint=32, max_codepoint=126)

_names = st.text(alphabet=_printable, min_size=1, max_size=200)
_phones = st.text(alphabet="0123456789 -+()", min_size=7, max_size=20)
_addresses = st.text(alphabet=_printable, min_size=1, max_size=500)


def _unique_email():
    return f"user-{uuid.uuid4().hex}@example.com"


@st.composite
def valid_customer_bodies(draw):
    body = {"name": draw(_names), "email": _unique_email()}
    if draw(st.booleans()):
        body["phone"] = draw(_phones)
    if draw(st.booleans()):
        body["address"] = draw(_addresses)
    return body


# ─────────────────────────────────────────────────────────────────────────────
# Property 3: Valid customer creation always succeeds with a UUID v4 ID
# Feature: customer-management-platform, Property 3
# Validates: Requirements 2.1, 2.2
# ─────────────────────────────────────────────────────────────────────────────

@given(body=valid_customer_bodies())
@settings(max_examples=100, deadline=None)
def test_valid_create_returns_201_with_uuid4(body):
    with fresh_dynamodb():
        resp = customers.lambda_handler(_event("POST", "/customers", body=body), None)
        assert resp["statusCode"] == 201
        payload = json.loads(resp["body"])
        assert customers.is_valid_uuid4(payload["customer_id"]) is True


# ─────────────────────────────────────────────────────────────────────────────
# Property 4: Created records have a valid ISO 8601 UTC created_at timestamp
# Feature: customer-management-platform, Property 4
# Validates: Requirements 2.5
# ─────────────────────────────────────────────────────────────────────────────

@given(body=valid_customer_bodies())
@settings(max_examples=100, deadline=None)
def test_created_at_is_valid_iso8601(body):
    with fresh_dynamodb():
        resp = customers.lambda_handler(_event("POST", "/customers", body=body), None)
        payload = json.loads(resp["body"])
        # Must be parseable as an ISO 8601 timestamp.
        parsed = _parse_iso(payload["created_at"])
        assert parsed is not None


# ─────────────────────────────────────────────────────────────────────────────
# Property 6: Create-then-retrieve round trip preserves all fields
# Feature: customer-management-platform, Property 6
# Validates: Requirements 3.1
# ─────────────────────────────────────────────────────────────────────────────

@given(body=valid_customer_bodies())
@settings(max_examples=100, deadline=None)
def test_create_then_get_preserves_fields(body):
    with fresh_dynamodb():
        create_resp = customers.lambda_handler(
            _event("POST", "/customers", body=body), None
        )
        created = json.loads(create_resp["body"])
        customer_id = created["customer_id"]

        get_resp = customers.lambda_handler(
            _event(
                "GET",
                "/customers/{customer_id}",
                path_params={"customer_id": customer_id},
            ),
            None,
        )
        assert get_resp["statusCode"] == 200
        fetched = json.loads(get_resp["body"])

        # Every field from the create request survives unchanged.
        for key, value in body.items():
            assert fetched[key] == value
        assert fetched["customer_id"] == customer_id
        assert "created_at" in fetched


# ─────────────────────────────────────────────────────────────────────────────
# Property 7: GET on non-existent ID always returns 404
# Feature: customer-management-platform, Property 7
# Validates: Requirements 3.2
# ─────────────────────────────────────────────────────────────────────────────

@given(customer_id=st.uuids(version=4).map(str))
@settings(max_examples=100, deadline=None)
def test_get_nonexistent_returns_404(customer_id):
    with fresh_dynamodb():
        resp = customers.lambda_handler(
            _event(
                "GET",
                "/customers/{customer_id}",
                path_params={"customer_id": customer_id},
            ),
            None,
        )
        assert resp["statusCode"] == 404
        payload = json.loads(resp["body"])
        assert "error" in payload
        assert "name" not in payload
        assert "email" not in payload


# ─────────────────────────────────────────────────────────────────────────────
# Property 8: Update preserves immutable fields
# Feature: customer-management-platform, Property 8
# Validates: Requirements 4.5, 4.6
# ─────────────────────────────────────────────────────────────────────────────

@given(create_body=valid_customer_bodies(), new_name=_names)
@settings(max_examples=100, deadline=None)
def test_update_preserves_immutable_fields(create_body, new_name):
    with fresh_dynamodb():
        create_resp = customers.lambda_handler(
            _event("POST", "/customers", body=create_body), None
        )
        created = json.loads(create_resp["body"])
        customer_id = created["customer_id"]
        original_created_at = created["created_at"]

        # Update body attempts to override immutable fields — they must be ignored.
        update_body = {
            "name": new_name,
            "email": created["email"],
            "customer_id": "attacker-supplied-id",
            "created_at": "1999-01-01T00:00:00Z",
        }
        update_resp = customers.lambda_handler(
            _event(
                "PUT",
                "/customers/{customer_id}",
                body=update_body,
                path_params={"customer_id": customer_id},
            ),
            None,
        )
        assert update_resp["statusCode"] == 200
        updated = json.loads(update_resp["body"])

        assert updated["customer_id"] == customer_id
        assert updated["created_at"] == original_created_at
        assert _parse_iso(updated["updated_at"]) >= _parse_iso(original_created_at)


# ─────────────────────────────────────────────────────────────────────────────
# Property 9: DELETE removes the record and makes it unretrievable
# Feature: customer-management-platform, Property 9
# Validates: Requirements 5.1
# ─────────────────────────────────────────────────────────────────────────────

@given(body=valid_customer_bodies())
@settings(max_examples=100, deadline=None)
def test_delete_makes_record_unretrievable(body):
    with fresh_dynamodb():
        create_resp = customers.lambda_handler(
            _event("POST", "/customers", body=body), None
        )
        customer_id = json.loads(create_resp["body"])["customer_id"]

        delete_resp = customers.lambda_handler(
            _event(
                "DELETE",
                "/customers/{customer_id}",
                path_params={"customer_id": customer_id},
            ),
            None,
        )
        assert delete_resp["statusCode"] == 200
        assert customer_id in json.loads(delete_resp["body"])["message"]

        get_resp = customers.lambda_handler(
            _event(
                "GET",
                "/customers/{customer_id}",
                path_params={"customer_id": customer_id},
            ),
            None,
        )
        assert get_resp["statusCode"] == 404


# ─────────────────────────────────────────────────────────────────────────────
# Property 10: DELETE with non-UUID-v4 ID always returns 400
# Feature: customer-management-platform, Property 10
# Validates: Requirements 5.4
# ─────────────────────────────────────────────────────────────────────────────

@given(bad_id=st.text(max_size=60))
@settings(max_examples=200, deadline=None)
def test_delete_non_uuid_returns_400(bad_id):
    if customers.is_valid_uuid4(bad_id):
        return  # skip the astronomically rare valid-UUID draw
    resp = customers.lambda_handler(
        _event(
            "DELETE",
            "/customers/{customer_id}",
            path_params={"customer_id": bad_id},
        ),
        None,
    )
    assert resp["statusCode"] == 400
    assert "error" in json.loads(resp["body"])


# ─────────────────────────────────────────────────────────────────────────────
# Property 11: Responses never expose internal error details
# Feature: customer-management-platform, Property 11
# Validates: Requirements 7.4
# ─────────────────────────────────────────────────────────────────────────────

_INTERNAL_LEAK_MARKERS = ["arn:", "Traceback", "ProvisionedThroughput", "ClientError"]


def _client_error():
    return ClientError(
        {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": (
                    "arn:aws:dynamodb:us-east-1:123456789012:table/secret "
                    "Traceback ClientError internal detail"
                ),
            }
        },
        "OperationName",
    )


@given(body=valid_customer_bodies())
@settings(max_examples=50, deadline=None)
def test_write_error_response_is_sanitized(body):
    failing_table = mock.MagicMock()
    failing_table.query.return_value = {"Count": 0, "Items": []}
    failing_table.put_item.side_effect = _client_error()

    with mock.patch.object(customers, "get_dynamodb_table", return_value=failing_table):
        resp = customers.lambda_handler(_event("POST", "/customers", body=body), None)

    assert resp["statusCode"] == 500
    assert "customer_id" not in json.loads(resp["body"])  # Requirement 2.6
    for marker in _INTERNAL_LEAK_MARKERS:
        assert marker not in resp["body"]


@given(customer_id=st.uuids(version=4).map(str))
@settings(max_examples=50, deadline=None)
def test_read_error_response_is_sanitized(customer_id):
    failing_table = mock.MagicMock()
    failing_table.get_item.side_effect = _client_error()

    with mock.patch.object(customers, "get_dynamodb_table", return_value=failing_table):
        resp = customers.lambda_handler(
            _event(
                "GET",
                "/customers/{customer_id}",
                path_params={"customer_id": customer_id},
            ),
            None,
        )

    assert resp["statusCode"] == 503
    for marker in _INTERNAL_LEAK_MARKERS:
        assert marker not in resp["body"]


@given(customer_id=st.uuids(version=4).map(str))
@settings(max_examples=50, deadline=None)
def test_delete_error_response_is_sanitized(customer_id):
    failing_table = mock.MagicMock()
    failing_table.get_item.return_value = {"Item": {"customer_id": customer_id}}
    failing_table.delete_item.side_effect = _client_error()

    with mock.patch.object(customers, "get_dynamodb_table", return_value=failing_table):
        resp = customers.lambda_handler(
            _event(
                "DELETE",
                "/customers/{customer_id}",
                path_params={"customer_id": customer_id},
            ),
            None,
        )

    assert resp["statusCode"] == 503
    for marker in _INTERNAL_LEAK_MARKERS:
        assert marker not in resp["body"]


# ─────────────────────────────────────────────────────────────────────────────
# Example tests: conflict, not-found, and pagination behaviors
# Feature: customer-management-platform
# ─────────────────────────────────────────────────────────────────────────────

def test_duplicate_email_on_create_returns_409():
    with fresh_dynamodb():
        body = {"name": "First", "email": "dup@example.com"}
        first = customers.lambda_handler(_event("POST", "/customers", body=body), None)
        assert first["statusCode"] == 201

        second = customers.lambda_handler(
            _event("POST", "/customers", body={"name": "Second", "email": "dup@example.com"}),
            None,
        )
        assert second["statusCode"] == 409


def test_update_duplicate_email_returns_409():
    with fresh_dynamodb():
        a = customers.lambda_handler(
            _event("POST", "/customers", body={"name": "A", "email": "a@example.com"}), None
        )
        customers.lambda_handler(
            _event("POST", "/customers", body={"name": "B", "email": "b@example.com"}), None
        )
        a_id = json.loads(a["body"])["customer_id"]

        # Try to change A's email to B's — must conflict.
        resp = customers.lambda_handler(
            _event(
                "PUT",
                "/customers/{customer_id}",
                body={"name": "A", "email": "b@example.com"},
                path_params={"customer_id": a_id},
            ),
            None,
        )
        assert resp["statusCode"] == 409


def test_update_nonexistent_returns_404():
    with fresh_dynamodb():
        resp = customers.lambda_handler(
            _event(
                "PUT",
                "/customers/{customer_id}",
                body={"name": "Ghost", "email": "ghost@example.com"},
                path_params={"customer_id": str(uuid.uuid4())},
            ),
            None,
        )
        assert resp["statusCode"] == 404


def test_list_pagination_returns_next_token():
    with fresh_dynamodb():
        # Create more than one page (>100) of customers.
        for i in range(105):
            customers.lambda_handler(
                _event(
                    "POST",
                    "/customers",
                    body={"name": f"User {i}", "email": f"user{i}@example.com"},
                ),
                None,
            )

        first_page = customers.lambda_handler(_event("GET", "/customers"), None)
        assert first_page["statusCode"] == 200
        page1 = json.loads(first_page["body"])
        assert len(page1["customers"]) == 100
        assert page1["nextToken"] is not None

        second_page = customers.lambda_handler(
            _event("GET", "/customers", query_params={"nextToken": page1["nextToken"]}),
            None,
        )
        assert second_page["statusCode"] == 200
        page2 = json.loads(second_page["body"])
        assert len(page2["customers"]) == 5
