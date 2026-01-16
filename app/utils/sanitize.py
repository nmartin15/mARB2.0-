"""Utilities for sanitizing PHI and sensitive data from logs and audit trails."""
from typing import Any, Dict, List, Union, Optional
import json
import re
import hashlib
import os

# Common PHI/PII field names that should be redacted
PHI_FIELD_NAMES = [
    # Patient identifiers
    "patient_name",
    "patient_first_name",
    "patient_last_name",
    "patient_middle_name",
    "patient_dob",
    "date_of_birth",
    "dob",
    "mrn",
    "medical_record_number",
    "patient_id",
    "patient_control_number",
    "patient_ssn",
    "ssn",
    "social_security_number",
    "patient_phone",
    "patient_email",
    "patient_address",
    "patient_street",
    "patient_city",
    "patient_state",
    "patient_zip",
    "patient_zip_code",
    # Provider identifiers (can be PHI in some contexts)
    "provider_name",
    "provider_npi",
    "npi",
    "provider_phone",
    "provider_email",
    # Insurance information
    "member_id",
    "subscriber_id",
    "policy_number",
    "group_number",
    # Clinical information
    "diagnosis_description",
    "procedure_description",
    # Financial information
    "account_number",
    "routing_number",
    "credit_card",
    "card_number",
    # Authentication tokens
    "password",
    "token",
    "secret",
    "api_key",
    "access_token",
    "refresh_token",
    "authorization",
    # Generic PHI marker
    "phi",
    "protected_health_information",
]

# Patterns for detecting PHI in values (e.g., SSN, phone numbers, emails)
PHI_PATTERNS = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]"),  # SSN: 123-45-6789
    (r"\b\d{3}\.\d{2}\.\d{4}\b", "[SSN_REDACTED]"),  # SSN: 123.45.6789
    (r"\b\d{9}\b", None),  # 9-digit numbers (potential SSN without dashes)
    (r"\b\d{3}-\d{3}-\d{4}\b", "[PHONE_REDACTED]"),  # Phone: 123-456-7890
    (r"\b\(\d{3}\)\s?\d{3}-\d{4}\b", "[PHONE_REDACTED]"),  # Phone: (123) 456-7890
    (
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "[EMAIL_REDACTED]",
    ),  # Email addresses
]

REDACTION_MARKER = "[REDACTED]"

# Salt for hashing PHI (should be set via environment variable for production)
# This ensures deterministic hashing while preventing rainbow table attacks
_HASH_SALT = os.getenv("PHI_HASH_SALT", "default-salt-change-in-production")


def hash_phi_value(value: Any, salt: Optional[str] = None) -> str:
    """
    Create a deterministic hash of a PHI value for audit trail purposes.
    
    This function creates a one-way hash that:
    - Cannot be reversed to reveal the original PHI
    - Is deterministic (same input = same hash) for matching related records
    - Uses a salt to prevent rainbow table attacks
    
    Args:
        value: The PHI value to hash (will be converted to string)
        salt: Optional salt override (defaults to PHI_HASH_SALT env var)
        
    Returns:
        SHA-256 hash hexdigest (64 characters)
    """
    if value is None:
        return ""
    
    # Normalize the value (strip whitespace, lowercase for consistency)
    normalized = str(value).strip().lower()
    if not normalized:
        return ""
    
    # Use provided salt or default
    used_salt = salt or _HASH_SALT
    
    # Create hash: salt + normalized value
    hash_input = f"{used_salt}:{normalized}"
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()


def extract_and_hash_identifiers(data: Dict[str, Any], max_depth: int = 10) -> Dict[str, str]:
    """
    Extract PHI identifiers from data and return their hashed values.
    
    This function scans a dictionary for PHI fields and returns a dictionary
    of field names mapped to their hashed values. This allows creating
    unique identifiers for audit trails without exposing PHI.
    
    Args:
        data: Dictionary to scan for PHI identifiers
        max_depth: Maximum recursion depth to prevent infinite loops
        
    Returns:
        Dictionary mapping PHI field names to their hashed values
        Example: {"patient_name": "abc123...", "mrn": "def456..."}
    """
    if max_depth <= 0:
        return {}
    
    identifiers: Dict[str, str] = {}
    
    for key, value in data.items():
        key_lower = key.lower()
        is_phi_field = any(phi_field in key_lower for phi_field in PHI_FIELD_NAMES)
        
        if is_phi_field and value is not None:
            # Hash the PHI value
            hashed = hash_phi_value(value)
            if hashed:
                # Store with original key name for reference
                identifiers[key] = hashed
        elif isinstance(value, dict):
            # Recursively extract from nested dictionaries
            nested_ids = extract_and_hash_identifiers(value, max_depth - 1)
            # Prefix with parent key to avoid collisions
            for nested_key, nested_hash in nested_ids.items():
                identifiers[f"{key}.{nested_key}"] = nested_hash
        elif isinstance(value, list):
            # Extract from list items
            for idx, item in enumerate(value):
                if isinstance(item, dict):
                    nested_ids = extract_and_hash_identifiers(item, max_depth - 1)
                    for nested_key, nested_hash in nested_ids.items():
                        identifiers[f"{key}[{idx}].{nested_key}"] = nested_hash
    
    return identifiers


def create_audit_identifier(data: Union[Dict[str, Any], str, bytes, None]) -> Optional[str]:
    """
    Create a unique audit identifier from request/response data.
    
    This function extracts PHI identifiers from data, hashes them, and creates
    a composite hash that can be used as a unique identifier for audit trails.
    The identifier is deterministic (same data = same identifier) but cannot
    be reversed to reveal PHI.
    
    Args:
        data: Request/response body (dict, string, bytes, or None)
        
    Returns:
        Composite hash identifier (64 characters) or None if no data
    """
    if data is None:
        return None
    
    # Convert to dict if needed
    if isinstance(data, bytes):
        try:
            data_str = data.decode("utf-8")
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                # Not JSON, hash the string directly
                return hash_phi_value(data_str)
        except UnicodeDecodeError:
            return None
    elif isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            # Not JSON, hash the string directly
            return hash_phi_value(data)
    
    if not isinstance(data, dict):
        return hash_phi_value(str(data))
    
    # Extract and hash all PHI identifiers
    hashed_identifiers = extract_and_hash_identifiers(data)
    
    if not hashed_identifiers:
        # No PHI found, create hash from non-PHI fields for uniqueness
        # Use a combination of keys and values (sanitized)
        safe_data = {k: str(v)[:50] for k, v in data.items() if k.lower() not in [f.lower() for f in PHI_FIELD_NAMES]}
        if safe_data:
            data_str = json.dumps(safe_data, sort_keys=True)
            return hash_phi_value(data_str)
        return None
    
    # Create composite hash from all hashed identifiers
    # Sort keys for deterministic output
    composite = json.dumps(hashed_identifiers, sort_keys=True)
    return hash_phi_value(composite)


def sanitize_phi_value(value: Any) -> str:
    """
    Sanitize a value that may contain PHI by applying pattern matching.
    
    Args:
        value: The value to sanitize (will be converted to string)
        
    Returns:
        Sanitized string with PHI patterns replaced
    """
    if value is None:
        return ""
    
    str_value = str(value)
    
    # Apply pattern-based redaction
    for pattern, replacement in PHI_PATTERNS:
        if replacement:
            str_value = re.sub(pattern, replacement, str_value)
        else:
            # For patterns without specific replacement, check if it looks like PHI
            # and redact if it matches common PHI patterns
            matches = re.findall(pattern, str_value)
            if matches:
                # If it's a standalone 9-digit number, it might be an SSN
                # Only redact if it's the entire value or clearly an SSN
                if len(str_value.strip()) == 9 and str_value.strip().isdigit():
                    str_value = "[SSN_REDACTED]"
    
    return str_value


def sanitize_dict(data: Dict[str, Any], max_depth: int = 10) -> Dict[str, Any]:
    """
    Recursively sanitize a dictionary by redacting PHI fields.
    
    Args:
        data: Dictionary to sanitize
        max_depth: Maximum recursion depth to prevent infinite loops
        
    Returns:
        Sanitized dictionary with PHI fields redacted
    """
    if max_depth <= 0:
        return {"error": "[MAX_DEPTH_EXCEEDED]"}
    
    sanitized: Dict[str, Any] = {}
    
    for key, value in data.items():
        # Check if key name indicates PHI
        key_lower = key.lower()
        is_phi_field = any(phi_field in key_lower for phi_field in PHI_FIELD_NAMES)
        
        if is_phi_field:
            # Redact the entire value
            sanitized[key] = REDACTION_MARKER
        elif isinstance(value, dict):
            # Recursively sanitize nested dictionaries
            sanitized[key] = sanitize_dict(value, max_depth - 1)
        elif isinstance(value, list):
            # Sanitize list items
            sanitized[key] = [
                sanitize_dict(item, max_depth - 1) if isinstance(item, dict) else sanitize_phi_value(item)
                for item in value
            ]
        else:
            # For other values, apply pattern-based sanitization
            sanitized[key] = sanitize_phi_value(value)
    
    return sanitized


def sanitize_request_body(body: Union[str, bytes, Dict[str, Any], None]) -> str:
    """
    Sanitize a request body to remove PHI before logging.
    
    Args:
        body: Request body (can be string, bytes, dict, or None)
        
    Returns:
        Sanitized string representation, safe for logging
    """
    if body is None:
        return ""
    
    # Handle bytes
    if isinstance(body, bytes):
        try:
            body_str = body.decode("utf-8")
        except UnicodeDecodeError:
            return "[BINARY_DATA_REDACTED]"
    else:
        body_str = str(body)
    
    # Try to parse as JSON
    try:
        body_dict = json.loads(body_str)
        if isinstance(body_dict, dict):
            sanitized = sanitize_dict(body_dict)
            return json.dumps(sanitized, default=str)
        elif isinstance(body_dict, list):
            # Handle list of items
            sanitized_list = [
                sanitize_dict(item, max_depth=10) if isinstance(item, dict) else sanitize_phi_value(item)
                for item in body_dict
            ]
            return json.dumps(sanitized_list, default=str)
        else:
            # Not a dict or list, apply pattern-based sanitization
            return sanitize_phi_value(body_str)
    except (json.JSONDecodeError, TypeError):
        # Not JSON, apply pattern-based sanitization to the string
        return sanitize_phi_value(body_str)


def sanitize_response_body(body: Union[str, bytes, Dict[str, Any], None]) -> str:
    """
    Sanitize a response body to remove PHI before logging.
    
    Args:
        body: Response body (can be string, bytes, dict, or None)
        
    Returns:
        Sanitized string representation, safe for logging
    """
    # Same logic as request body sanitization
    return sanitize_request_body(body)

