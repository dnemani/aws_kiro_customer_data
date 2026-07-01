# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.
"""
Lambda Authorizer — validates Cognito-issued JWTs and returns IAM policy documents.
"""
import json
import os
import urllib.request

from jose import jwt, JWTError

# Module-level JWKS cache — populated on first warm invocation per container
_JWKS_CACHE: dict | None = None

# Environment variables (read once at module load for efficiency)
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
COGNITO_REGION = os.environ.get("COGNITO_REGION", os.environ.get("AWS_REGION", "us-east-1"))
COGNITO_APP_CLIENT_ID = os.environ.get("COGNITO_APP_CLIENT_ID", "")

ISSUER_URL = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
JWKS_URL = f"{ISSUER_URL}/.well-known/jwks.json"


def get_jwks() -> dict:
    """Fetch JWKS from Cognito and cache for the container lifetime."""
    global _JWKS_CACHE
    if _JWKS_CACHE is None:
        with urllib.request.urlopen(JWKS_URL, timeout=5) as response:  # noqa: S310
            _JWKS_CACHE = json.loads(response.read())
    return _JWKS_CACHE


def validate_token(token: str, issuer: str, audience: str) -> dict:
    """Validate a JWT against Cognito JWKS.

    Raises JWTError or ValueError on any validation failure.
    Returns the decoded claims dict on success.
    """
    jwks = get_jwks()

    # Decode header without verification to find the matching key
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    if not kid:
        raise ValueError("Token header missing 'kid'")

    # Find matching key in JWKS
    matching_key = None
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            matching_key = key_data
            break

    if matching_key is None:
        raise ValueError(f"No matching key found for kid={kid}")

    # Verify signature, expiry, issuer, and audience
    claims = jwt.decode(
        token,
        matching_key,
        algorithms=["RS256"],
        audience=audience,
        issuer=issuer,
    )
    return claims


def _api_wildcard_resource(method_arn: str) -> str:
    """Build an execute-api ARN scoped to the whole API stage.

    API Gateway caches the authorizer's returned policy per identity token
    (TTL). If we returned the concrete ``methodArn``, the cached Allow would only
    cover the first route the caller happened to hit, and every other route would
    then be denied (403) until the cache expired. Scoping the policy to all
    methods and resources on the same API + stage avoids that.
    """
    # methodArn: arn:aws:execute-api:{region}:{account}:{apiId}/{stage}/{METHOD}/{path...}
    parts = method_arn.split(":")
    if len(parts) < 6:
        return "*"
    api_gateway_arn = parts[5].split("/")
    if len(api_gateway_arn) < 2:
        return method_arn
    prefix = ":".join(parts[:5])
    api_id, stage = api_gateway_arn[0], api_gateway_arn[1]
    return f"{prefix}:{api_id}/{stage}/*"


def build_policy(principal_id: str, effect: str, resource: str) -> dict:
    """Build an IAM policy document for API Gateway.

    effect must be 'Allow' or 'Deny'.
    resource is the API Gateway ARN (use '*' for all resources).
    """
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource,
                }
            ],
        },
    }


def lambda_handler(event: dict, context) -> dict:
    """Lambda Authorizer entry point.

    Extracts the Bearer token, validates it, and returns an IAM policy.
    Raises Exception("Unauthorized") on any failure so API Gateway returns 401.
    """
    token = event.get("authorizationToken", "")

    # Strip "Bearer " prefix (case-insensitive)
    if token.lower().startswith("bearer "):
        token = token[7:]
    elif not token:
        raise Exception("Unauthorized")

    try:
        claims = validate_token(
            token=token,
            issuer=ISSUER_URL,
            audience=COGNITO_APP_CLIENT_ID,
        )
        principal_id = claims.get("sub", "unknown")
        resource = _api_wildcard_resource(event.get("methodArn", "*"))
        return build_policy(principal_id, "Allow", resource)
    except Exception:
        raise Exception("Unauthorized")
