# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.
"""
Property-based and example tests for the Lambda Authorizer.

Feature: customer-management-platform
"""
import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from hypothesis import given, settings, strategies as st
from jose import jwk, jwt

# ─────────────────────────────────────────────────────────────────────────────
# Configure the authorizer's environment BEFORE importing the module, since it
# reads Cognito settings at import time to build the issuer / JWKS URLs.
# ─────────────────────────────────────────────────────────────────────────────

USER_POOL_ID = "us-east-1_TESTPOOL"
REGION = "us-east-1"
AUDIENCE = "test-app-client-id"
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
KID = "test-key-id"

os.environ["COGNITO_USER_POOL_ID"] = USER_POOL_ID
os.environ["COGNITO_REGION"] = REGION
os.environ["COGNITO_APP_CLIENT_ID"] = AUDIENCE


def _load_authorizer():
    """Load the authorizer module under a unique name to avoid clashing with the
    identically named ``lambda_function`` module in the customers package."""
    path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "src", "authorizer",
            "lambda_function.py",
        )
    )
    spec = importlib.util.spec_from_file_location("authorizer_lambda_function", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["authorizer_lambda_function"] = module
    spec.loader.exec_module(module)
    return module


authz = _load_authorizer()


# ─────────────────────────────────────────────────────────────────────────────
# Test signing keys + JWKS
# ─────────────────────────────────────────────────────────────────────────────

def _generate_key(kid):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
    )
    jwk_dict = jwk.construct(public_pem, "RS256").to_dict()
    jwk_dict["kid"] = kid
    jwk_dict["alg"] = "RS256"
    jwk_dict["use"] = "sig"
    return private_pem, jwk_dict


_PRIVATE_PEM, _PUBLIC_JWK = _generate_key(KID)
_OTHER_PRIVATE_PEM, _ = _generate_key(KID)  # different key, same kid -> bad signature

# Populate the module JWKS cache so the authorizer never hits the network.
authz._JWKS_CACHE = {"keys": [_PUBLIC_JWK]}


def _make_token(
    *,
    sub="user-123",
    issuer=ISSUER,
    audience=AUDIENCE,
    exp_delta_seconds=3600,
    private_pem=None,
    kid=KID,
):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": sub,
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=exp_delta_seconds)).timestamp()),
    }
    return jwt.encode(
        claims,
        private_pem or _PRIVATE_PEM,
        algorithm="RS256",
        headers={"kid": kid},
    )


def _effect(policy):
    return policy["policyDocument"]["Statement"][0]["Effect"]


def _event(auth_token):
    return {
        "authorizationToken": auth_token,
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abc/prod/GET/customers",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Property 1: Valid JWTs are always permitted
# Feature: customer-management-platform, Property 1
# Validates: Requirements 1.1
# ─────────────────────────────────────────────────────────────────────────────

@given(
    sub=st.text(
        alphabet=st.characters(min_codepoint=33, max_codepoint=126),
        min_size=1,
        max_size=40,
    ),
    exp_delta=st.integers(min_value=60, max_value=86400),
)
@settings(max_examples=100)
def test_valid_jwt_is_permitted(sub, exp_delta):
    token = _make_token(sub=sub, exp_delta_seconds=exp_delta)
    policy = authz.lambda_handler(_event(f"Bearer {token}"), None)
    assert _effect(policy) == "Allow"
    assert policy["principalId"] == sub


# ─────────────────────────────────────────────────────────────────────────────
# Property 2: Invalid JWTs are always denied
# Feature: customer-management-platform, Property 2
# Validates: Requirements 1.2, 1.3, 1.4, 1.5
# ─────────────────────────────────────────────────────────────────────────────

@given(garbage=st.text(max_size=80))
@settings(max_examples=100)
def test_arbitrary_string_is_denied(garbage):
    with pytest.raises(Exception, match="Unauthorized"):
        authz.lambda_handler(_event(f"Bearer {garbage}"), None)


@given(expired_by=st.integers(min_value=1, max_value=100000))
@settings(max_examples=50)
def test_expired_jwt_is_denied(expired_by):
    token = _make_token(exp_delta_seconds=-expired_by)
    with pytest.raises(Exception, match="Unauthorized"):
        authz.lambda_handler(_event(f"Bearer {token}"), None)


@given(sub=st.text(min_size=1, max_size=20))
@settings(max_examples=50)
def test_wrong_signing_key_is_denied(sub):
    token = _make_token(sub=sub, private_pem=_OTHER_PRIVATE_PEM)
    with pytest.raises(Exception, match="Unauthorized"):
        authz.lambda_handler(_event(f"Bearer {token}"), None)


@given(bad_issuer=st.text(min_size=1, max_size=40).filter(lambda s: s != ISSUER))
@settings(max_examples=50)
def test_wrong_issuer_is_denied(bad_issuer):
    token = _make_token(issuer=bad_issuer)
    with pytest.raises(Exception, match="Unauthorized"):
        authz.lambda_handler(_event(f"Bearer {token}"), None)


@given(bad_audience=st.text(min_size=1, max_size=40).filter(lambda s: s != AUDIENCE))
@settings(max_examples=50)
def test_wrong_audience_is_denied(bad_audience):
    token = _make_token(audience=bad_audience)
    with pytest.raises(Exception, match="Unauthorized"):
        authz.lambda_handler(_event(f"Bearer {token}"), None)


@given(unknown_kid=st.text(min_size=1, max_size=20).filter(lambda s: s != KID))
@settings(max_examples=50)
def test_unknown_kid_is_denied(unknown_kid):
    token = _make_token(kid=unknown_kid)
    with pytest.raises(Exception, match="Unauthorized"):
        authz.lambda_handler(_event(f"Bearer {token}"), None)


# ─────────────────────────────────────────────────────────────────────────────
# Example tests: header edge cases
# Feature: customer-management-platform
# ─────────────────────────────────────────────────────────────────────────────

def test_missing_authorization_header_is_denied():
    with pytest.raises(Exception, match="Unauthorized"):
        authz.lambda_handler({"methodArn": "arn:aws:execute-api:::/"}, None)


def test_empty_token_is_denied():
    with pytest.raises(Exception, match="Unauthorized"):
        authz.lambda_handler(_event(""), None)


def test_bearer_prefix_is_case_insensitive():
    token = _make_token()
    policy = authz.lambda_handler(_event(f"bearer {token}"), None)
    assert _effect(policy) == "Allow"
