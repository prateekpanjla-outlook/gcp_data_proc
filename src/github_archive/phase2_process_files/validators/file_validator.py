"""
File-level validation for GitHub Archive files.

Validates file name, format, and size before processing.
"""

import re
from typing import List, Optional
from dataclasses import dataclass


# =============================================================================
# FILE NAME PATTERN
# =============================================================================
# Expected format: YYYY-MM-DD-HH.json.gz
FILE_NAME_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2}-\d{2})\.json\.gz$')


# =============================================================================
# VALIDATION RESULT
# =============================================================================
@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================
def validate_file(file_name: str, file_size_bytes: int, max_size_gb: int = 10) -> ValidationResult:
    """
    Validate a GitHub Archive file.

    Checks:
    1. File name format (YYYY-MM-DD-HH.json.gz)
    2. Gzip extension
    3. File size is within limit

    Args:
        file_name: Name of the file (e.g., 2026-03-05-12.json.gz)
        file_size_bytes: Size of the file in bytes
        max_size_gb: Maximum allowed file size in GB (default: 10)

    Returns:
        ValidationResult with validation status
    """
    errors = []
    warnings = []

    # Check .gz extension
    if not file_name.endswith('.gz'):
        errors.append(f"File must have .gz extension, got: {file_name}")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # Check .json.gz extension specifically
    if not file_name.endswith('.json.gz'):
        errors.append(f"File must have .json.gz extension, got: {file_name}")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # Check pattern
    match = FILE_NAME_PATTERN.match(file_name)
    if not match:
        errors.append(f"File name must match format YYYY-MM-DD-HH.json.gz, got: {file_name}")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # Extract and validate date/time components
    date_str = match.group(1)  # YYYY-MM-DD-HH
    parts = date_str.split('-')

    try:
        year, month, day, hour = map(int, parts)

        # Basic sanity checks
        if year < 2011 or year > 2100:
            errors.append(f"Invalid year: {year}")
        if month < 1 or month > 12:
            errors.append(f"Invalid month: {month}")
        if day < 1 or day > 31:
            errors.append(f"Invalid day: {day}")
        if hour < 0 or hour > 23:
            errors.append(f"Invalid hour: {hour}")
    except ValueError:
        errors.append(f"Invalid date/time format: {date_str}")

    # Check file size
    max_size_bytes = max_size_gb * 1024 * 1024 * 1024
    if file_size_bytes > max_size_bytes:
        errors.append(
            f"File too large: {file_size_bytes} bytes "
            f"(maximum: {max_size_gb}GB = {max_size_bytes} bytes)"
        )

    # Minimum file size check (100 bytes)
    if file_size_bytes < 100:
        errors.append(f"File too small: {file_size_bytes} bytes (minimum: 100 bytes)")

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def should_split_file(file_size_bytes: int, threshold_mb: int = 500) -> bool:
    """
    Determine if a file should be split based on size.

    Args:
        file_size_bytes: Size of the file in bytes
        threshold_mb: Threshold in MB

    Returns:
        True if file should be split
    """
    threshold_bytes = threshold_mb * 1024 * 1024
    return file_size_bytes >= threshold_bytes
