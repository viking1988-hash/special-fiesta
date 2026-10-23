"""Pure preflight validation for a reviewed schema-only archive selector.

No storage, database, or subprocess access.
"""
import re


def validate_schema_source(object_key: str, sha256: str) -> tuple[str, str]:
    if not re.fullmatch(r"crm-schema-only-\d{8}-\d{6}\.dump", object_key):
        raise ValueError("SCHEMA_ONLY_OBJECT_KEY_REQUIRED")
    digest = sha256.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("SCHEMA_ONLY_EXPECTED_SHA256_REQUIRED")
    return object_key, digest
