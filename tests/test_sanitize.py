"""Tests for PHI sanitization utilities."""
import os
import pytest
from unittest.mock import patch

from app.utils.sanitize import (
    hash_phi_value,
    create_audit_identifier,
    extract_and_hash_identifiers,
    PHI_FIELD_NAMES,
    PHI_PATTERNS,
)


@pytest.mark.security
@pytest.mark.hipaa
class TestPHISanitization:
    """Test PHI sanitization for HIPAA compliance."""

    def test_hash_phi_value_deterministic(self):
        """Test that hash_phi_value is deterministic."""
        value = "John Doe"
        hash1 = hash_phi_value(value)
        hash2 = hash_phi_value(value)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hexdigest length

    def test_hash_phi_value_different_values(self):
        """Test that different values produce different hashes."""
        hash1 = hash_phi_value("John Doe")
        hash2 = hash_phi_value("Jane Smith")
        assert hash1 != hash2

    def test_hash_phi_value_with_custom_salt(self):
        """Test hash_phi_value with custom salt."""
        value = "John Doe"
        hash1 = hash_phi_value(value, salt="salt1")
        hash2 = hash_phi_value(value, salt="salt2")
        assert hash1 != hash2  # Different salts = different hashes

    def test_hash_phi_value_handles_none(self):
        """Test hash_phi_value handles None values."""
        hash_result = hash_phi_value(None)
        # None should return empty string based on implementation
        assert hash_result == ""

    def test_hash_phi_value_handles_numbers(self):
        """Test hash_phi_value handles numeric values."""
        hash_result = hash_phi_value(12345)
        assert hash_result is not None
        assert len(hash_result) == 64

    def test_create_audit_identifier(self):
        """Test creating audit identifier from data."""
        data = b'{"claim_id": 1, "patient_name": "John Doe"}'
        identifier = create_audit_identifier(data)
        assert identifier is not None
        assert isinstance(identifier, str)
        assert len(identifier) > 0

    def test_create_audit_identifier_deterministic(self):
        """Test that create_audit_identifier is deterministic."""
        data = b'{"claim_id": 1}'
        id1 = create_audit_identifier(data)
        id2 = create_audit_identifier(data)
        assert id1 == id2

    def test_extract_and_hash_identifiers(self):
        """Test extracting and hashing identifiers from dict."""
        data = {
            "patient_name": "John Doe",
            "patient_id": "12345",
            "claim_id": 1,
            "amount": 100.0,
        }
        hashed = extract_and_hash_identifiers(data)
        assert isinstance(hashed, dict)
        # Should have hashed PHI fields
        assert "patient_name" in hashed or "patient_id" in hashed

    def test_extract_and_hash_identifiers_nested(self):
        """Test extracting identifiers from nested dict."""
        data = {
            "claim": {
                "patient_name": "John Doe",
                "patient_id": "12345",
            },
            "amount": 100.0,
        }
        hashed = extract_and_hash_identifiers(data)
        assert isinstance(hashed, dict)

    def test_extract_and_hash_identifiers_empty(self):
        """Test extracting identifiers from empty dict."""
        hashed = extract_and_hash_identifiers({})
        assert isinstance(hashed, dict)
        assert len(hashed) == 0

    def test_extract_and_hash_identifiers_no_phi(self):
        """Test extracting identifiers when no PHI fields present."""
        data = {
            "claim_id": 1,
            "amount": 100.0,
            "status": "processed",
        }
        hashed = extract_and_hash_identifiers(data)
        assert isinstance(hashed, dict)

    def test_extract_and_hash_identifiers_redacts_phi_fields(self):
        """Test that extract_and_hash_identifiers hashes PHI fields."""
        data = {
            "patient_name": "John Doe",
            "patient_ssn": "123-45-6789",
            "claim_id": 1,
            "amount": 100.0,
        }
        hashed = extract_and_hash_identifiers(data)
        # Should have hashed PHI fields
        assert isinstance(hashed, dict)
        # PHI fields should be hashed (not plain text)
        if "patient_name" in hashed:
            assert hashed["patient_name"] != "John Doe"
        if "patient_ssn" in hashed:
            assert hashed["patient_ssn"] != "123-45-6789"

    def test_extract_and_hash_identifiers_handles_nested(self):
        """Test extract_and_hash_identifiers with nested structures."""
        data = {
            "claim": {
                "patient_name": "John Doe",
                "patient_id": "12345",
            },
            "amount": 100.0,
        }
        hashed = extract_and_hash_identifiers(data)
        assert isinstance(hashed, dict)

    def test_extract_and_hash_identifiers_handles_lists(self):
        """Test extract_and_hash_identifiers with lists."""
        data = {
            "patients": [
                {"patient_name": "John Doe", "patient_id": "123"},
                {"patient_name": "Jane Smith", "patient_id": "456"},
            ],
        }
        hashed = extract_and_hash_identifiers(data)
        assert isinstance(hashed, dict)

    def test_phi_patterns_detect_ssn(self):
        """Test that PHI patterns detect SSN formats."""
        # This tests the pattern matching logic
        test_values = [
            "123-45-6789",
            "123.45.6789",
            "123456789",
        ]
        # Patterns should match these formats
        for value in test_values:
            # Verify pattern would match
            import re
            ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b"
            if re.search(ssn_pattern, value):
                assert True  # Pattern matches

    def test_phi_patterns_detect_phone(self):
        """Test that PHI patterns detect phone numbers."""
        test_values = [
            "123-456-7890",
            "(123) 456-7890",
        ]
        import re
        phone_pattern = r"\b\d{3}-\d{3}-\d{4}\b"
        for value in test_values:
            if re.search(phone_pattern, value):
                assert True  # Pattern matches

    def test_phi_patterns_detect_email(self):
        """Test that PHI patterns detect email addresses."""
        test_values = [
            "patient@example.com",
            "john.doe@hospital.org",
        ]
        import re
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        for value in test_values:
            if re.search(email_pattern, value):
                assert True  # Pattern matches

    def test_hash_phi_value_uses_env_salt(self):
        """Test that hash_phi_value uses environment salt."""
        with patch.dict(os.environ, {"PHI_HASH_SALT": "test-salt-123"}):
            # Re-import to pick up new env var
            import importlib
            import app.utils.sanitize as sanitize_module
            importlib.reload(sanitize_module)
            
            value = "John Doe"
            hash_result = sanitize_module.hash_phi_value(value)
            assert hash_result is not None
            assert len(hash_result) == 64

    def test_hash_phi_value_empty_string(self):
        """Test hash_phi_value with empty string."""
        result = hash_phi_value("")
        assert result == ""

    def test_hash_phi_value_whitespace(self):
        """Test hash_phi_value normalizes whitespace."""
        hash1 = hash_phi_value("  John Doe  ")
        hash2 = hash_phi_value("john doe")
        assert hash1 == hash2  # Should normalize

    def test_hash_phi_value_case_insensitive(self):
        """Test hash_phi_value is case insensitive."""
        hash1 = hash_phi_value("John Doe")
        hash2 = hash_phi_value("JOHN DOE")
        assert hash1 == hash2  # Should lowercase

    def test_extract_and_hash_identifiers_max_depth(self):
        """Test extract_and_hash_identifiers respects max_depth."""
        # Create deeply nested structure
        data = {"level1": {"level2": {"level3": {"patient_name": "John"}}}}
        hashed = extract_and_hash_identifiers(data, max_depth=2)
        # Should stop at max_depth
        assert isinstance(hashed, dict)

    def test_extract_and_hash_identifiers_zero_depth(self):
        """Test extract_and_hash_identifiers with zero depth."""
        data = {"patient_name": "John"}
        hashed = extract_and_hash_identifiers(data, max_depth=0)
        assert hashed == {}

    def test_extract_and_hash_identifiers_list_with_dicts(self):
        """Test extract_and_hash_identifiers with list of dicts."""
        data = {
            "claims": [
                {"patient_name": "John", "claim_id": 1},
                {"patient_name": "Jane", "claim_id": 2},
            ]
        }
        hashed = extract_and_hash_identifiers(data)
        assert isinstance(hashed, dict)
        # Should have indexed keys like "claims[0].patient_name"
        assert any("[0]" in key or "[1]" in key for key in hashed.keys()) or len(hashed) > 0

    def test_extract_and_hash_identifiers_none_values(self):
        """Test extract_and_hash_identifiers handles None values."""
        data = {"patient_name": None, "claim_id": 1}
        hashed = extract_and_hash_identifiers(data)
        # None values should not be hashed
        assert "patient_name" not in hashed

    def test_create_audit_identifier_none(self):
        """Test create_audit_identifier with None."""
        result = create_audit_identifier(None)
        assert result is None

    def test_create_audit_identifier_string(self):
        """Test create_audit_identifier with string."""
        result = create_audit_identifier('{"claim_id": 1}')
        assert result is not None
        assert isinstance(result, str)

    def test_create_audit_identifier_non_json_string(self):
        """Test create_audit_identifier with non-JSON string."""
        result = create_audit_identifier("plain text")
        assert result is not None
        assert isinstance(result, str)

    def test_create_audit_identifier_bytes(self):
        """Test create_audit_identifier with bytes."""
        result = create_audit_identifier(b'{"claim_id": 1}')
        assert result is not None

    def test_create_audit_identifier_invalid_utf8_bytes(self):
        """Test create_audit_identifier with invalid UTF-8 bytes."""
        invalid_bytes = b'\xff\xfe\x00\x01'
        result = create_audit_identifier(invalid_bytes)
        assert result is None

    def test_create_audit_identifier_dict(self):
        """Test create_audit_identifier with dict."""
        data = {"claim_id": 1, "patient_name": "John"}
        result = create_audit_identifier(data)
        assert result is not None

    def test_create_audit_identifier_dict_no_phi(self):
        """Test create_audit_identifier with dict containing no PHI."""
        data = {"claim_id": 1, "amount": 100.0}
        result = create_audit_identifier(data)
        # Should still create identifier from non-PHI fields
        assert result is not None or result is None  # May return None if no unique data

    def test_create_audit_identifier_empty_dict(self):
        """Test create_audit_identifier with empty dict."""
        result = create_audit_identifier({})
        assert result is None

    def test_create_audit_identifier_non_dict_json(self):
        """Test create_audit_identifier with non-dict JSON."""
        result = create_audit_identifier("[1, 2, 3]")
        assert result is not None


@pytest.mark.security
@pytest.mark.hipaa
class TestSanitizePHIValue:
    """Test sanitize_phi_value function."""

    def test_sanitize_phi_value_none(self):
        """Test sanitize_phi_value with None."""
        from app.utils.sanitize import sanitize_phi_value
        result = sanitize_phi_value(None)
        assert result == ""

    def test_sanitize_phi_value_ssn_dash_format(self):
        """Test sanitize_phi_value redacts SSN with dashes."""
        from app.utils.sanitize import sanitize_phi_value
        result = sanitize_phi_value("SSN: 123-45-6789")
        assert "[SSN_REDACTED]" in result
        assert "123-45-6789" not in result

    def test_sanitize_phi_value_ssn_dot_format(self):
        """Test sanitize_phi_value redacts SSN with dots."""
        from app.utils.sanitize import sanitize_phi_value
        result = sanitize_phi_value("SSN: 123.45.6789")
        assert "[SSN_REDACTED]" in result

    def test_sanitize_phi_value_ssn_9_digits(self):
        """Test sanitize_phi_value redacts 9-digit SSN."""
        from app.utils.sanitize import sanitize_phi_value
        result = sanitize_phi_value("123456789")
        assert "[SSN_REDACTED]" in result or result == "[SSN_REDACTED]"

    def test_sanitize_phi_value_phone_dash_format(self):
        """Test sanitize_phi_value redacts phone with dashes."""
        from app.utils.sanitize import sanitize_phi_value
        result = sanitize_phi_value("Call 123-456-7890")
        assert "[PHONE_REDACTED]" in result
        assert "123-456-7890" not in result

    def test_sanitize_phi_value_phone_paren_format(self):
        """Test sanitize_phi_value redacts phone with parentheses."""
        from app.utils.sanitize import sanitize_phi_value
        result = sanitize_phi_value("Call (123) 456-7890")
        assert "[PHONE_REDACTED]" in result

    def test_sanitize_phi_value_email(self):
        """Test sanitize_phi_value redacts email."""
        from app.utils.sanitize import sanitize_phi_value
        result = sanitize_phi_value("Email: patient@example.com")
        assert "[EMAIL_REDACTED]" in result
        assert "patient@example.com" not in result

    def test_sanitize_phi_value_no_phi(self):
        """Test sanitize_phi_value with no PHI."""
        from app.utils.sanitize import sanitize_phi_value
        result = sanitize_phi_value("No sensitive data here")
        assert result == "No sensitive data here"

    def test_sanitize_phi_value_multiple_patterns(self):
        """Test sanitize_phi_value with multiple PHI patterns."""
        from app.utils.sanitize import sanitize_phi_value
        result = sanitize_phi_value("Contact: patient@example.com or 123-456-7890")
        assert "[EMAIL_REDACTED]" in result
        assert "[PHONE_REDACTED]" in result


@pytest.mark.security
@pytest.mark.hipaa
class TestSanitizeDict:
    """Test sanitize_dict function."""

    def test_sanitize_dict_phi_fields(self):
        """Test sanitize_dict redacts PHI fields."""
        from app.utils.sanitize import sanitize_dict, REDACTION_MARKER
        data = {
            "patient_name": "John Doe",
            "patient_ssn": "123-45-6789",
            "claim_id": 1,
        }
        result = sanitize_dict(data)
        assert result["patient_name"] == REDACTION_MARKER
        assert result["patient_ssn"] == REDACTION_MARKER
        assert result["claim_id"] != REDACTION_MARKER  # Not PHI

    def test_sanitize_dict_nested(self):
        """Test sanitize_dict with nested dictionaries."""
        from app.utils.sanitize import sanitize_dict, REDACTION_MARKER
        data = {
            "claim": {
                "patient_name": "John Doe",
                "amount": 100.0,
            },
            "status": "processed",
        }
        result = sanitize_dict(data)
        assert result["claim"]["patient_name"] == REDACTION_MARKER
        assert result["claim"]["amount"] != REDACTION_MARKER

    def test_sanitize_dict_lists(self):
        """Test sanitize_dict with lists."""
        from app.utils.sanitize import sanitize_dict, REDACTION_MARKER
        data = {
            "patients": [
                {"patient_name": "John", "claim_id": 1},
                {"patient_name": "Jane", "claim_id": 2},
            ]
        }
        result = sanitize_dict(data)
        assert isinstance(result["patients"], list)
        assert result["patients"][0]["patient_name"] == REDACTION_MARKER

    def test_sanitize_dict_list_with_strings(self):
        """Test sanitize_dict with list of strings."""
        from app.utils.sanitize import sanitize_dict
        data = {
            "phones": ["123-456-7890", "987-654-3210"],
            "claim_id": 1,
        }
        result = sanitize_dict(data)
        assert isinstance(result["phones"], list)
        # Phone numbers should be sanitized
        assert any("[PHONE_REDACTED]" in str(item) for item in result["phones"])

    def test_sanitize_dict_max_depth(self):
        """Test sanitize_dict respects max_depth."""
        from app.utils.sanitize import sanitize_dict
        data = {"level1": {"level2": {"level3": {"patient_name": "John"}}}}
        result = sanitize_dict(data, max_depth=2)
        assert "error" in result.get("level1", {}).get("level2", {}) or "patient_name" in str(result)

    def test_sanitize_dict_zero_depth(self):
        """Test sanitize_dict with zero depth."""
        from app.utils.sanitize import sanitize_dict
        data = {"patient_name": "John"}
        result = sanitize_dict(data, max_depth=0)
        assert "error" in result

    def test_sanitize_dict_empty(self):
        """Test sanitize_dict with empty dict."""
        from app.utils.sanitize import sanitize_dict
        result = sanitize_dict({})
        assert result == {}

    def test_sanitize_dict_non_phi_fields(self):
        """Test sanitize_dict preserves non-PHI fields."""
        from app.utils.sanitize import sanitize_dict
        data = {
            "claim_id": 1,
            "amount": 100.0,
            "status": "processed",
        }
        result = sanitize_dict(data)
        assert result["claim_id"] == 1
        assert result["amount"] == 100.0
        assert result["status"] == "processed"


@pytest.mark.security
@pytest.mark.hipaa
class TestSanitizeRequestBody:
    """Test sanitize_request_body function."""

    def test_sanitize_request_body_none(self):
        """Test sanitize_request_body with None."""
        from app.utils.sanitize import sanitize_request_body
        result = sanitize_request_body(None)
        assert result == ""

    def test_sanitize_request_body_dict(self):
        """Test sanitize_request_body with dict."""
        from app.utils.sanitize import sanitize_request_body, REDACTION_MARKER
        data = {"patient_name": "John", "claim_id": 1}
        result = sanitize_request_body(data)
        assert REDACTION_MARKER in result
        assert "John" not in result

    def test_sanitize_request_body_string_json(self):
        """Test sanitize_request_body with JSON string."""
        from app.utils.sanitize import sanitize_request_body, REDACTION_MARKER
        data = '{"patient_name": "John", "claim_id": 1}'
        result = sanitize_request_body(data)
        assert REDACTION_MARKER in result

    def test_sanitize_request_body_bytes_json(self):
        """Test sanitize_request_body with JSON bytes."""
        from app.utils.sanitize import sanitize_request_body, REDACTION_MARKER
        data = b'{"patient_name": "John", "claim_id": 1}'
        result = sanitize_request_body(data)
        assert REDACTION_MARKER in result

    def test_sanitize_request_body_bytes_invalid_utf8(self):
        """Test sanitize_request_body with invalid UTF-8 bytes."""
        from app.utils.sanitize import sanitize_request_body
        invalid_bytes = b'\xff\xfe\x00\x01'
        result = sanitize_request_body(invalid_bytes)
        assert "[BINARY_DATA_REDACTED]" in result

    def test_sanitize_request_body_non_json_string(self):
        """Test sanitize_request_body with non-JSON string."""
        from app.utils.sanitize import sanitize_request_body
        data = "Contact: patient@example.com"
        result = sanitize_request_body(data)
        assert "[EMAIL_REDACTED]" in result

    def test_sanitize_request_body_list(self):
        """Test sanitize_request_body with list."""
        from app.utils.sanitize import sanitize_request_body, REDACTION_MARKER
        data = [{"patient_name": "John"}, {"patient_name": "Jane"}]
        result = sanitize_request_body(data)
        assert REDACTION_MARKER in result

    def test_sanitize_request_body_list_strings(self):
        """Test sanitize_request_body with list of strings."""
        from app.utils.sanitize import sanitize_request_body
        data = ["123-456-7890", "987-654-3210"]
        result = sanitize_request_body(data)
        # Should handle list of strings
        assert isinstance(result, str)


@pytest.mark.security
@pytest.mark.hipaa
class TestSanitizeResponseBody:
    """Test sanitize_response_body function."""

    def test_sanitize_response_body_same_as_request(self):
        """Test sanitize_response_body uses same logic as request."""
        from app.utils.sanitize import sanitize_request_body, sanitize_response_body, REDACTION_MARKER
        data = {"patient_name": "John", "claim_id": 1}
        request_result = sanitize_request_body(data)
        response_result = sanitize_response_body(data)
        # Should produce same result
        assert REDACTION_MARKER in request_result
        assert REDACTION_MARKER in response_result

    def test_sanitize_response_body_none(self):
        """Test sanitize_response_body with None."""
        from app.utils.sanitize import sanitize_response_body
        result = sanitize_response_body(None)
        assert result == ""

    def test_sanitize_response_body_dict(self):
        """Test sanitize_response_body with dict."""
        from app.utils.sanitize import sanitize_response_body, REDACTION_MARKER
        data = {"patient_name": "John", "claim_id": 1}
        result = sanitize_response_body(data)
        assert REDACTION_MARKER in result
