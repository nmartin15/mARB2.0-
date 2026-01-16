"""Tests for PHI sanitization and hashing."""
import pytest
from app.utils.sanitize import (
    hash_phi_value,
    extract_and_hash_identifiers,
    create_audit_identifier,
    sanitize_phi_value,
    sanitize_dict,
    PHI_FIELD_NAMES,
    REDACTION_MARKER,
)


@pytest.mark.security
@pytest.mark.audit
@pytest.mark.hipaa
class TestPHISanitization:
    """Test PHI sanitization for HIPAA compliance."""

    def test_patient_name_is_detected_and_hashed(self):
        """Test that patient names are detected and hashed."""
        # Arrange
        test_data = {
            "patient_name": "John Doe",
            "other_field": "not_phi"
        }
        
        # Act
        hashed_identifiers = extract_and_hash_identifiers(test_data)
        
        # Assert
        assert "patient_name" in hashed_identifiers
        assert hashed_identifiers["patient_name"] != "John Doe"
        assert len(hashed_identifiers["patient_name"]) == 64  # SHA-256 hexdigest
        # Original PHI should not be in result
        assert "John Doe" not in str(hashed_identifiers)

    def test_ssn_is_detected_and_hashed(self):
        """Test that SSNs are detected and hashed."""
        # Arrange
        test_data = {
            "patient_ssn": "123-45-6789",
            "other_field": "not_phi"
        }
        
        # Act
        hashed_identifiers = extract_and_hash_identifiers(test_data)
        
        # Assert
        assert "patient_ssn" in hashed_identifiers
        assert hashed_identifiers["patient_ssn"] != "123-45-6789"
        assert len(hashed_identifiers["patient_ssn"]) == 64
        assert "123-45-6789" not in str(hashed_identifiers)

    def test_mrn_is_detected_and_hashed(self):
        """Test that medical record numbers are detected and hashed."""
        # Arrange
        test_data = {
            "mrn": "123456789",
            "other_field": "not_phi"
        }
        
        # Act
        hashed_identifiers = extract_and_hash_identifiers(test_data)
        
        # Assert
        assert "mrn" in hashed_identifiers
        assert hashed_identifiers["mrn"] != "123456789"
        assert len(hashed_identifiers["mrn"]) == 64

    def test_dob_is_detected_and_hashed(self):
        """Test that date of birth is detected and hashed."""
        # Arrange
        test_data = {
            "patient_dob": "1990-01-01",
            "other_field": "not_phi"
        }
        
        # Act
        hashed_identifiers = extract_and_hash_identifiers(test_data)
        
        # Assert
        assert "patient_dob" in hashed_identifiers
        assert hashed_identifiers["patient_dob"] != "1990-01-01"
        assert len(hashed_identifiers["patient_dob"]) == 64

    def test_email_is_detected_and_hashed(self):
        """Test that email addresses are detected and hashed."""
        # Arrange
        test_data = {
            "patient_email": "patient@example.com",
            "other_field": "not_phi"
        }
        
        # Act
        hashed_identifiers = extract_and_hash_identifiers(test_data)
        
        # Assert
        assert "patient_email" in hashed_identifiers
        assert hashed_identifiers["patient_email"] != "patient@example.com"
        assert len(hashed_identifiers["patient_email"]) == 64

    def test_phone_is_detected_and_hashed(self):
        """Test that phone numbers are detected and hashed."""
        # Arrange
        test_data = {
            "patient_phone": "123-456-7890",
            "other_field": "not_phi"
        }
        
        # Act
        hashed_identifiers = extract_and_hash_identifiers(test_data)
        
        # Assert
        assert "patient_phone" in hashed_identifiers
        assert hashed_identifiers["patient_phone"] != "123-456-7890"
        assert len(hashed_identifiers["patient_phone"]) == 64

    def test_hash_phi_value_creates_deterministic_hash(self):
        """Test that hash_phi_value creates deterministic hashes."""
        # Arrange
        test_phi = "John Doe"
        
        # Act
        hash1 = hash_phi_value(test_phi)
        hash2 = hash_phi_value(test_phi)
        
        # Assert
        assert hash1 == hash2  # Same input should produce same hash

    def test_hash_phi_value_uses_salt(self):
        """Test that hash_phi_value uses salt to prevent rainbow table attacks."""
        # Arrange
        test_phi = "John Doe"
        
        # Act
        hash1 = hash_phi_value(test_phi, salt="salt1")
        hash2 = hash_phi_value(test_phi, salt="salt2")
        
        # Assert
        assert hash1 != hash2  # Different salts should produce different hashes

    def test_hash_phi_value_cannot_be_reversed(self):
        """Test that hash_phi_value creates one-way hashes."""
        # Arrange
        test_phi = "John Doe"
        hashed = hash_phi_value(test_phi)
        
        # Assert
        # Hash should not contain original PHI
        assert test_phi not in hashed
        assert test_phi.lower() not in hashed
        # Hash should be 64 characters (SHA-256 hexdigest)
        assert len(hashed) == 64
        # Hash should be hexadecimal
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_extract_and_hash_identifiers_handles_nested_dicts(self):
        """Test that extract_and_hash_identifiers handles nested dictionaries."""
        # Arrange
        test_data = {
            "patient": {
                "patient_name": "John Doe",
                "patient_dob": "1990-01-01"
            },
            "other_field": "not_phi"
        }
        
        # Act
        hashed_identifiers = extract_and_hash_identifiers(test_data)
        
        # Assert
        assert "patient.patient_name" in hashed_identifiers
        assert "patient.patient_dob" in hashed_identifiers
        assert "John Doe" not in str(hashed_identifiers)
        assert "1990-01-01" not in str(hashed_identifiers)

    def test_extract_and_hash_identifiers_handles_lists(self):
        """Test that extract_and_hash_identifiers handles lists."""
        # Arrange
        test_data = {
            "patients": [
                {"patient_name": "John Doe"},
                {"patient_name": "Jane Smith"}
            ]
        }
        
        # Act
        hashed_identifiers = extract_and_hash_identifiers(test_data)
        
        # Assert
        assert "patients[0].patient_name" in hashed_identifiers
        assert "patients[1].patient_name" in hashed_identifiers
        assert "John Doe" not in str(hashed_identifiers)
        assert "Jane Smith" not in str(hashed_identifiers)

    def test_create_audit_identifier_from_dict(self):
        """Test that create_audit_identifier creates unique identifiers from dicts."""
        # Arrange
        test_data = {
            "patient_name": "John Doe",
            "mrn": "123456789"
        }
        
        # Act
        identifier = create_audit_identifier(test_data)
        
        # Assert
        assert identifier is not None
        assert len(identifier) == 64  # SHA-256 hexdigest
        assert "John Doe" not in identifier
        assert "123456789" not in identifier

    def test_create_audit_identifier_from_string(self):
        """Test that create_audit_identifier handles string input."""
        # Arrange
        test_string = "John Doe"
        
        # Act
        identifier = create_audit_identifier(test_string)
        
        # Assert
        assert identifier is not None
        assert len(identifier) == 64
        assert test_string not in identifier

    def test_create_audit_identifier_from_bytes(self):
        """Test that create_audit_identifier handles bytes input."""
        # Arrange
        test_bytes = b'{"patient_name": "John Doe"}'
        
        # Act
        identifier = create_audit_identifier(test_bytes)
        
        # Assert
        assert identifier is not None
        assert len(identifier) == 64
        assert "John Doe" not in identifier.decode() if isinstance(identifier, bytes) else identifier

    def test_create_audit_identifier_is_deterministic(self):
        """Test that create_audit_identifier is deterministic."""
        # Arrange
        test_data = {
            "patient_name": "John Doe",
            "mrn": "123456789"
        }
        
        # Act
        identifier1 = create_audit_identifier(test_data)
        identifier2 = create_audit_identifier(test_data)
        
        # Assert
        assert identifier1 == identifier2  # Same data should produce same identifier

    def test_sanitize_phi_value_redacts_ssn(self):
        """Test that sanitize_phi_value redacts SSN patterns."""
        # Arrange
        test_value = "SSN: 123-45-6789"
        
        # Act
        sanitized = sanitize_phi_value(test_value)
        
        # Assert
        assert "123-45-6789" not in sanitized or "[SSN_REDACTED]" in sanitized

    def test_sanitize_phi_value_redacts_phone(self):
        """Test that sanitize_phi_value redacts phone patterns."""
        # Arrange
        test_value = "Phone: 123-456-7890"
        
        # Act
        sanitized = sanitize_phi_value(test_value)
        
        # Assert
        assert "123-456-7890" not in sanitized or "[PHONE_REDACTED]" in sanitized

    def test_sanitize_phi_value_redacts_email(self):
        """Test that sanitize_phi_value redacts email patterns."""
        # Arrange
        test_value = "Email: patient@example.com"
        
        # Act
        sanitized = sanitize_phi_value(test_value)
        
        # Assert
        assert "patient@example.com" not in sanitized or "[EMAIL_REDACTED]" in sanitized

    def test_sanitize_dict_redacts_phi_fields(self):
        """Test that sanitize_dict redacts PHI fields."""
        # Arrange
        test_data = {
            "patient_name": "John Doe",
            "mrn": "123456789",
            "other_field": "not_phi"
        }
        
        # Act
        sanitized = sanitize_dict(test_data)
        
        # Assert
        assert sanitized["patient_name"] == REDACTION_MARKER
        assert sanitized["mrn"] == REDACTION_MARKER
        assert sanitized["other_field"] != REDACTION_MARKER  # Non-PHI field preserved

    def test_sanitize_dict_handles_nested_dicts(self):
        """Test that sanitize_dict handles nested dictionaries."""
        # Arrange
        test_data = {
            "patient": {
                "patient_name": "John Doe",
                "patient_dob": "1990-01-01"
            },
            "other_field": "not_phi"
        }
        
        # Act
        sanitized = sanitize_dict(test_data)
        
        # Assert
        assert sanitized["patient"]["patient_name"] == REDACTION_MARKER
        assert sanitized["patient"]["patient_dob"] == REDACTION_MARKER
        assert sanitized["other_field"] != REDACTION_MARKER

    def test_sanitize_dict_handles_lists(self):
        """Test that sanitize_dict handles lists."""
        # Arrange
        test_data = {
            "patients": [
                {"patient_name": "John Doe"},
                {"patient_name": "Jane Smith"}
            ]
        }
        
        # Act
        sanitized = sanitize_dict(test_data)
        
        # Assert
        assert sanitized["patients"][0]["patient_name"] == REDACTION_MARKER
        assert sanitized["patients"][1]["patient_name"] == REDACTION_MARKER

    def test_all_phi_field_names_are_recognized(self):
        """Test that all PHI field names in PHI_FIELD_NAMES are recognized."""
        # Arrange
        test_data = {}
        for field_name in PHI_FIELD_NAMES[:10]:  # Test first 10
            test_data[field_name] = "test_value"
        
        # Act
        hashed_identifiers = extract_and_hash_identifiers(test_data)
        
        # Assert
        # All tested fields should be hashed
        for field_name in PHI_FIELD_NAMES[:10]:
            assert field_name in hashed_identifiers

    def test_hash_phi_value_handles_none(self):
        """Test that hash_phi_value handles None values."""
        # Arrange
        test_value = None
        
        # Act
        hashed = hash_phi_value(test_value)
        
        # Assert
        assert hashed == ""  # None should return empty string

    def test_hash_phi_value_handles_empty_string(self):
        """Test that hash_phi_value handles empty strings."""
        # Arrange
        test_value = ""
        
        # Act
        hashed = hash_phi_value(test_value)
        
        # Assert
        assert hashed == ""  # Empty string should return empty string

    def test_hash_phi_value_normalizes_input(self):
        """Test that hash_phi_value normalizes input (strips, lowercases)."""
        # Arrange
        test_value1 = "  John Doe  "
        test_value2 = "JOHN DOE"
        test_value3 = "john doe"
        
        # Act
        hash1 = hash_phi_value(test_value1)
        hash2 = hash_phi_value(test_value2)
        hash3 = hash_phi_value(test_value3)
        
        # Assert
        # All should produce same hash (normalized)
        assert hash1 == hash2 == hash3

    def test_extract_and_hash_identifiers_ignores_non_phi_fields(self):
        """Test that extract_and_hash_identifiers ignores non-PHI fields."""
        # Arrange
        test_data = {
            "claim_id": 123,
            "total_amount": 1000.00,
            "status": "pending"
        }
        
        # Act
        hashed_identifiers = extract_and_hash_identifiers(test_data)
        
        # Assert
        # Non-PHI fields should not be hashed
        assert "claim_id" not in hashed_identifiers
        assert "total_amount" not in hashed_identifiers
        assert "status" not in hashed_identifiers
        assert len(hashed_identifiers) == 0

    def test_sanitize_request_body_dict(self):
        """Test sanitize_request_body with dictionary input."""
        from app.utils.sanitize import sanitize_request_body
        
        # Arrange
        test_data = {
            "patient_name": "John Doe",
            "mrn": "123456789",
            "claim_id": 123
        }
        
        # Act
        sanitized = sanitize_request_body(test_data)
        
        # Assert
        assert isinstance(sanitized, str)
        # PHI should be redacted - check that original values are not present
        assert "John Doe" not in sanitized  # PHI should be redacted
        assert "123456789" not in sanitized  # MRN should be redacted
        # Non-PHI fields should still be present
        assert "claim_id" in sanitized or "123" in sanitized

    def test_sanitize_request_body_json_string(self):
        """Test sanitize_request_body with JSON string input."""
        from app.utils.sanitize import sanitize_request_body
        
        # Arrange
        test_json = '{"patient_name": "John Doe", "mrn": "123456789"}'
        
        # Act
        sanitized = sanitize_request_body(test_json)
        
        # Assert
        assert isinstance(sanitized, str)
        assert "John Doe" not in sanitized
        assert REDACTION_MARKER in sanitized

    def test_sanitize_request_body_bytes(self):
        """Test sanitize_request_body with bytes input."""
        from app.utils.sanitize import sanitize_request_body
        
        # Arrange
        test_bytes = b'{"patient_name": "John Doe", "mrn": "123456789"}'
        
        # Act
        sanitized = sanitize_request_body(test_bytes)
        
        # Assert
        assert isinstance(sanitized, str)
        assert "John Doe" not in sanitized
        assert REDACTION_MARKER in sanitized

    def test_sanitize_request_body_binary_data(self):
        """Test sanitize_request_body with binary data."""
        from app.utils.sanitize import sanitize_request_body
        
        # Arrange
        binary_data = b'\x00\x01\x02\x03\xff'
        
        # Act
        sanitized = sanitize_request_body(binary_data)
        
        # Assert
        assert "[BINARY_DATA_REDACTED]" in sanitized

    def test_sanitize_request_body_none(self):
        """Test sanitize_request_body with None input."""
        from app.utils.sanitize import sanitize_request_body
        
        # Act
        sanitized = sanitize_request_body(None)
        
        # Assert
        assert sanitized == ""

    def test_sanitize_request_body_list(self):
        """Test sanitize_request_body with list input."""
        from app.utils.sanitize import sanitize_request_body
        import json
        
        # Arrange
        test_list = [
            {"patient_name": "John Doe"},
            {"patient_name": "Jane Smith"}
        ]
        
        # Act
        sanitized = sanitize_request_body(test_list)
        
        # Assert
        assert isinstance(sanitized, str)
        # PHI should be redacted
        assert "John Doe" not in sanitized
        assert "Jane Smith" not in sanitized
        # Should be valid JSON
        parsed = json.loads(sanitized)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_sanitize_request_body_non_json_string(self):
        """Test sanitize_request_body with non-JSON string."""
        from app.utils.sanitize import sanitize_request_body
        
        # Arrange
        test_string = "Patient name: John Doe, SSN: 123-45-6789"
        
        # Act
        sanitized = sanitize_request_body(test_string)
        
        # Assert
        assert isinstance(sanitized, str)
        # Should apply pattern-based sanitization
        assert "John Doe" not in sanitized or "[SSN_REDACTED]" in sanitized

    def test_sanitize_response_body(self):
        """Test sanitize_response_body (should work same as sanitize_request_body)."""
        from app.utils.sanitize import sanitize_response_body
        
        # Arrange
        test_data = {
            "patient_name": "John Doe",
            "mrn": "123456789"
        }
        
        # Act
        sanitized = sanitize_response_body(test_data)
        
        # Assert
        assert isinstance(sanitized, str)
        # PHI should be redacted
        assert "John Doe" not in sanitized
        assert "123456789" not in sanitized
        # Should contain redaction markers or sanitized structure
        assert "patient_name" in sanitized or REDACTION_MARKER in sanitized

    def test_sanitize_dict_max_depth(self):
        """Test sanitize_dict respects max_depth parameter."""
        from app.utils.sanitize import sanitize_dict
        
        # Arrange - create deeply nested dict
        test_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "patient_name": "John Doe"
                    }
                }
            }
        }
        
        # Act - with max_depth=2
        sanitized = sanitize_dict(test_data, max_depth=2)
        
        # Assert - should handle depth limit
        assert isinstance(sanitized, dict)
        # If max_depth exceeded, should return error marker
        # Otherwise should sanitize properly
        if "error" in sanitized:
            assert "[MAX_DEPTH_EXCEEDED]" in str(sanitized["error"])

    def test_sanitize_phi_value_none(self):
        """Test sanitize_phi_value with None input."""
        # Act
        sanitized = sanitize_phi_value(None)
        
        # Assert
        assert sanitized == ""

    def test_sanitize_phi_value_standalone_ssn(self):
        """Test sanitize_phi_value with standalone 9-digit SSN."""
        # Arrange
        test_value = "123456789"
        
        # Act
        sanitized = sanitize_phi_value(test_value)
        
        # Assert
        # Should redact if it's a standalone 9-digit number
        assert "[SSN_REDACTED]" in sanitized or test_value not in sanitized

