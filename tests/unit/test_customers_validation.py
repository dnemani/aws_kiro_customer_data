# Copyright AnyCompany, Inc. or its affiliates. All Rights Reserved.
"""
Property-based and boundary tests for the shared customer validation utilities.

Feature: customer-management-platform
"""
import os
import sys
import uuid

from hypothesis import given, settings, strategies as st

# Make the customers Lambda source importable so we can exercise the real utils.
_SRC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "src", "customers")
)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from utils import is_valid_uuid4, validate_customer_body  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Reusable strategies
# ─────────────────────────────────────────────────────────────────────────────

# Printable ASCII avoids surrogate/serialization edge cases irrelevant to validation.
_printable = st.characters(min_codepoint=32, max_codepoint=126)

valid_names = st.text(alphabet=_printable, min_size=1, max_size=200)

valid_emails = st.builds(
    lambda local, domain, tld: f"{local}@{domain}.{tld}",
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=20),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=15),
    st.sampled_from(["com", "org", "net", "io", "co", "dev"]),
)


# ─────────────────────────────────────────────────────────────────────────────
# Property 5: Invalid input is always rejected with field-level errors
# Feature: customer-management-platform, Property 5
# Validates: Requirements 2.3, 4.3, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
# ─────────────────────────────────────────────────────────────────────────────

@given(email=valid_emails)
@settings(max_examples=100)
def test_missing_name_is_rejected(email):
    errors = validate_customer_body({"email": email})
    assert "name" in errors


@given(name=valid_names)
@settings(max_examples=100)
def test_missing_email_is_rejected(name):
    errors = validate_customer_body({"name": name})
    assert "email" in errors


@given(email=valid_emails)
@settings(max_examples=100)
def test_missing_both_required_fields_reports_each(email):
    errors = validate_customer_body({})
    assert "name" in errors
    assert "email" in errors


@given(
    name=st.text(alphabet=_printable, min_size=201, max_size=400),
    email=valid_emails,
)
@settings(max_examples=100)
def test_name_over_200_chars_is_rejected(name, email):
    errors = validate_customer_body({"name": name, "email": email})
    assert "name" in errors


@given(
    name=valid_names,
    # Text with no "@" can never satisfy an RFC 5322 address.
    email=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789.", min_size=1, max_size=30
    ),
)
@settings(max_examples=100)
def test_email_without_at_sign_is_rejected(name, email):
    errors = validate_customer_body({"name": name, "email": email})
    assert "email" in errors


@given(
    name=valid_names,
    email=valid_emails,
    # Letters are not permitted in the phone field.
    phone=st.text(alphabet="abcdefghXYZ", min_size=1, max_size=15),
)
@settings(max_examples=100)
def test_phone_with_letters_is_rejected(name, email, phone):
    errors = validate_customer_body({"name": name, "email": email, "phone": phone})
    assert "phone" in errors


# ─────────────────────────────────────────────────────────────────────────────
# Property 10: Non-UUID-v4 strings are always rejected
# Feature: customer-management-platform, Property 10
# Validates: Requirements 5.4
# ─────────────────────────────────────────────────────────────────────────────

def _is_actually_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(str(value), version=4)
        return str(parsed) == str(value).lower()
    except (ValueError, AttributeError, TypeError):
        return False


@given(st.text(max_size=60))
@settings(max_examples=200)
def test_arbitrary_text_is_not_uuid4(value):
    # Randomly generated text is astronomically unlikely to be a valid UUID v4;
    # on the rare chance it is, only assert the positive case instead.
    if _is_actually_uuid4(value):
        assert is_valid_uuid4(value) is True
    else:
        assert is_valid_uuid4(value) is False


@given(st.uuids(version=4))
@settings(max_examples=100)
def test_generated_uuid4_is_accepted(value):
    assert is_valid_uuid4(str(value)) is True


# ─────────────────────────────────────────────────────────────────────────────
# Boundary-value example tests
# Feature: customer-management-platform
# ─────────────────────────────────────────────────────────────────────────────

def test_name_boundaries():
    email = "boundary@example.com"
    assert validate_customer_body({"name": "a", "email": email}) == {}
    assert validate_customer_body({"name": "a" * 200, "email": email}) == {}
    assert "name" in validate_customer_body({"name": "a" * 201, "email": email})


def test_phone_boundaries():
    base = {"name": "Test", "email": "boundary@example.com"}
    assert "phone" in validate_customer_body({**base, "phone": "123456"})  # 6
    assert validate_customer_body({**base, "phone": "1234567"}) == {}  # 7
    assert validate_customer_body({**base, "phone": "1" * 20}) == {}  # 20
    assert "phone" in validate_customer_body({**base, "phone": "1" * 21})  # 21


def test_address_boundaries():
    base = {"name": "Test", "email": "boundary@example.com"}
    assert validate_customer_body({**base, "address": "a"}) == {}  # 1
    assert validate_customer_body({**base, "address": "a" * 500}) == {}  # 500
    assert "address" in validate_customer_body({**base, "address": "a" * 501})  # 501


def test_empty_address_is_rejected():
    base = {"name": "Test", "email": "boundary@example.com"}
    assert "address" in validate_customer_body({**base, "address": ""})
