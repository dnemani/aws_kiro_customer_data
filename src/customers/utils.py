# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.
"""
Shared utility functions for the Customer Management Lambda.
"""
import json
import os
import re
import uuid
import boto3


_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)
_PHONE_RE = re.compile(r'^[\d\s\-\+\(\)]+$')


def is_valid_uuid4(value: str) -> bool:
    """Return True if *value* is a valid UUID v4 string, False otherwise."""
    try:
        parsed = uuid.UUID(str(value), version=4)
        return str(parsed) == str(value).lower()
    except (ValueError, AttributeError, TypeError):
        return False


def build_response(status_code: int, body: dict) -> dict:
    """Build an API Gateway Lambda proxy response.

    Ensures the body is serialized to JSON and content-type is set.
    Never exposes internal error details — callers must pass sanitized messages.
    """
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def get_dynamodb_table():
    """Return a boto3 DynamoDB Table resource.

    Reads TABLE_NAME and AWS_REGION from environment variables.
    """
    table_name = os.environ["TABLE_NAME"]
    region = os.environ.get("AWS_REGION", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    return dynamodb.Table(table_name)


def validate_customer_body(body: dict) -> dict[str, str]:
    """Validate customer request body fields.

    Checks all fields and collects every error before returning — no early exit.
    Returns an empty dict if all fields are valid, or a dict mapping each
    failing field name to a human-readable reason string.
    """
    errors: dict[str, str] = {}

    # Validate name: required, non-empty string, max 200 characters
    if "name" not in body:
        errors["name"] = "Field is required"
    elif not isinstance(body["name"], str) or body["name"] == "":
        errors["name"] = "Field must not be empty"
    elif len(body["name"]) > 200:
        errors["name"] = "Field must not exceed 200 characters"

    # Validate email: required, RFC 5322 format
    if "email" not in body:
        errors["email"] = "Field is required"
    elif not isinstance(body["email"], str) or not _EMAIL_RE.match(body["email"]):
        errors["email"] = "Invalid email format"

    # Validate phone: optional — only validate if present
    if "phone" in body:
        phone = body["phone"]
        if not isinstance(phone, str) or not _PHONE_RE.match(phone):
            errors["phone"] = "Phone must contain only digits, spaces, hyphens, plus signs, and parentheses"
        elif len(phone) < 7:
            errors["phone"] = "Phone must be at least 7 characters"
        elif len(phone) > 20:
            errors["phone"] = "Phone must not exceed 20 characters"

    # Validate address: optional — only validate if present
    if "address" in body:
        address = body["address"]
        if not isinstance(address, str) or address == "":
            errors["address"] = "Field must not be empty"
        elif len(address) > 500:
            errors["address"] = "Field must not exceed 500 characters"

    return errors
