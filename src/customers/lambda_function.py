# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.
"""
Customer Management Lambda — handles CRUD operations for customer records.
"""
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# Allow importing utils when running locally from the src/customers directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from utils import is_valid_uuid4, build_response, get_dynamodb_table, validate_customer_body

EMAIL_INDEX_NAME = os.environ.get("EMAIL_INDEX_NAME", "email-index")


def lambda_handler(event: dict, context) -> dict:
    """Route incoming API Gateway proxy requests to the correct handler."""
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    if method == "POST" and resource == "/customers":
        return create_customer(event)
    elif method == "GET" and resource == "/customers":
        return list_customers(event)
    elif method == "GET" and resource == "/customers/{customer_id}":
        return get_customer(event)
    elif method == "PUT" and resource == "/customers/{customer_id}":
        return update_customer(event)
    elif method == "DELETE" and resource == "/customers/{customer_id}":
        return delete_customer(event)
    else:
        return build_response(404, {"error": "Route not found"})


def _now_iso8601() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_customer(event: dict) -> dict:
    """Handle POST /customers — create a new customer record.

    Steps:
    1. Parse and validate the request body.
    2. Check for a duplicate email via the email-index GSI.
    3. Persist the new record with a generated UUID v4 customer_id.
    4. Return HTTP 201 with the full customer record on success.
    """
    # --- Parse request body ---
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return build_response(400, {"error": "Invalid JSON body"})

    # --- Field validation ---
    errors = validate_customer_body(body)
    if errors:
        return build_response(400, {"error": "Validation failed", "fields": errors})

    table = get_dynamodb_table()

    # --- Duplicate-email check via GSI ---
    try:
        email_check = table.query(
            IndexName=EMAIL_INDEX_NAME,
            KeyConditionExpression=Key("email").eq(body["email"]),
        )
        if email_check.get("Count", 0) > 0:
            return build_response(409, {"error": "Email already registered"})
    except ClientError:
        return build_response(500, {"error": "Internal server error"})

    # --- Build the new customer record ---
    customer_id = str(uuid.uuid4())
    now = _now_iso8601()
    item = {
        "customer_id": customer_id,
        "name": body["name"],
        "email": body["email"],
        "created_at": now,
    }
    if "phone" in body:
        item["phone"] = body["phone"]
    if "address" in body:
        item["address"] = body["address"]

    # --- Persist to DynamoDB (Requirement 2.6: no customer_id on 500) ---
    try:
        table.put_item(Item=item)
    except ClientError:
        return build_response(500, {"error": "Internal server error"})

    # Return the full record (Requirement 2.1)
    return build_response(201, item)


def get_customer(event: dict) -> dict:
    """Handle GET /customers/{customer_id} — retrieve a customer record by ID."""
    customer_id = (event.get("pathParameters") or {}).get("customer_id", "")

    # Validate UUID format
    if not is_valid_uuid4(customer_id):
        return build_response(400, {"error": "Invalid customer_id format"})

    table = get_dynamodb_table()
    try:
        result = table.get_item(Key={"customer_id": customer_id})
    except ClientError:
        return build_response(503, {"error": "Service temporarily unavailable"})

    item = result.get("Item")
    if not item:
        return build_response(404, {"error": "Customer not found"})

    return build_response(200, item)


def list_customers(event: dict) -> dict:
    """Handle GET /customers — list up to 100 customer records with pagination."""
    import base64

    query_params = event.get("queryStringParameters") or {}
    next_token = query_params.get("nextToken")

    scan_kwargs = {"Limit": 100}
    if next_token:
        try:
            exclusive_start_key = json.loads(
                base64.b64decode(next_token.encode()).decode()
            )
            scan_kwargs["ExclusiveStartKey"] = exclusive_start_key
        except Exception:
            return build_response(400, {"error": "Invalid nextToken"})

    table = get_dynamodb_table()
    try:
        result = table.scan(**scan_kwargs)
    except ClientError:
        return build_response(503, {"error": "Service temporarily unavailable"})

    response_body = {"customers": result.get("Items", []), "nextToken": None}

    last_key = result.get("LastEvaluatedKey")
    if last_key:
        response_body["nextToken"] = base64.b64encode(
            json.dumps(last_key).encode()
        ).decode()

    return build_response(200, response_body)


def update_customer(event: dict) -> dict:
    """Handle PUT /customers/{customer_id} — update an existing customer record.

    Steps:
    1. Validate UUID path parameter.
    2. Parse and validate request body.
    3. Check for duplicate email (skip 409 if email belongs to the same customer).
    4. Confirm customer exists.
    5. Update record, preserving customer_id and created_at; set updated_at.
    6. Return 200 with full updated record.
    """
    customer_id = (event.get("pathParameters") or {}).get("customer_id", "")

    if not is_valid_uuid4(customer_id):
        return build_response(400, {"error": "Invalid customer_id format"})

    # Parse and validate body
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return build_response(400, {"error": "Invalid JSON body"})

    errors = validate_customer_body(body)
    if errors:
        return build_response(400, {"error": "Validation failed", "fields": errors})

    table = get_dynamodb_table()

    # Duplicate email check — allow the same customer to keep their email
    try:
        email_check = table.query(
            IndexName=EMAIL_INDEX_NAME,
            KeyConditionExpression=Key("email").eq(body["email"]),
        )
        for existing in email_check.get("Items", []):
            if existing.get("customer_id") != customer_id:
                return build_response(409, {"error": "Email already registered"})
    except ClientError:
        return build_response(500, {"error": "Internal server error"})

    # Confirm the record exists
    try:
        existing_result = table.get_item(Key={"customer_id": customer_id})
    except ClientError:
        return build_response(503, {"error": "Service temporarily unavailable"})

    existing_item = existing_result.get("Item")
    if not existing_item:
        return build_response(404, {"error": "Customer not found"})

    # Preserve immutable fields regardless of body values
    original_created_at = existing_item["created_at"]

    now = _now_iso8601()
    updated_item = {
        "customer_id": customer_id,          # immutable
        "name": body["name"],
        "email": body["email"],
        "created_at": original_created_at,   # immutable
        "updated_at": now,
    }
    if "phone" in body:
        updated_item["phone"] = body["phone"]
    elif "phone" in existing_item:
        # Clear phone if not in update body
        updated_item["phone"] = existing_item["phone"]

    if "address" in body:
        updated_item["address"] = body["address"]
    elif "address" in existing_item:
        updated_item["address"] = existing_item["address"]

    # Persist
    try:
        table.put_item(Item=updated_item)
    except ClientError:
        return build_response(500, {"error": "Internal server error"})

    return build_response(200, updated_item)


def delete_customer(event: dict) -> dict:
    """Handle DELETE /customers/{customer_id} — remove a customer record.

    Steps:
    1. Validate UUID path parameter.
    2. Confirm the customer exists.
    3. Delete the record.
    4. Return 200 with confirmation message.
    """
    customer_id = (event.get("pathParameters") or {}).get("customer_id", "")

    if not is_valid_uuid4(customer_id):
        return build_response(400, {"error": "Invalid customer_id format"})

    table = get_dynamodb_table()

    # Confirm existence before deleting
    try:
        existing_result = table.get_item(Key={"customer_id": customer_id})
    except ClientError:
        return build_response(503, {"error": "Service temporarily unavailable"})

    if not existing_result.get("Item"):
        return build_response(404, {"error": "Customer not found"})

    # Delete the record
    try:
        table.delete_item(Key={"customer_id": customer_id})
    except ClientError:
        return build_response(503, {"error": "Service temporarily unavailable"})

    return build_response(200, {"message": f"Customer {customer_id} deleted successfully"})
