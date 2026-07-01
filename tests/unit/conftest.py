# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.
"""
Unit-test fixtures for the Customer Management Platform.
"""
import json
import os
import pytest
import boto3
from moto import mock_aws


TABLE_NAME = "customer_records_test"
EMAIL_INDEX = "email-index"


@pytest.fixture
def aws_credentials():
    """Mock AWS credentials so moto does not hit real AWS."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def dynamodb_table(aws_credentials):
    """Provision a moto DynamoDB table matching the real schema."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
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
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.Table(TABLE_NAME)

        os.environ["TABLE_NAME"] = TABLE_NAME
        os.environ["EMAIL_INDEX_NAME"] = EMAIL_INDEX
        os.environ["AWS_REGION"] = "us-east-1"

        yield table


@pytest.fixture
def valid_customer_body():
    """A valid customer payload dict."""
    return {
        "name": "Jane Smith",
        "email": "jane.smith@example.com",
        "phone": "+1 555-123-4567",
        "address": "123 Main St, Anytown, CA 90210",
    }


@pytest.fixture
def mock_context():
    """A minimal Lambda context object."""
    class MockContext:
        function_name = "test-customer-function"
        memory_limit_in_mb = 128
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
        aws_request_id = "test-request-id"
    return MockContext()


@pytest.fixture
def api_event_factory():
    """Factory for creating API Gateway proxy event dicts."""
    def _factory(method, resource, body=None, path_params=None, query_params=None):
        event = {
            "httpMethod": method,
            "resource": resource,
            "pathParameters": path_params or {},
            "queryStringParameters": query_params or {},
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body) if body is not None else None,
        }
        return event
    return _factory
