"""
File-level validation for GitHub Archive files.

Validates file metadata, format, and structure before processing.
"""

import re
import gzip
from pathlib import Path
from typing import Dict, Any, Optional, List
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

    def add_error(self, error: str) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


# =============================================================================
# FILE VALIDATOR
# =============================================================================
class FileValidator:
    """
    Validates GitHub Archive files before processing.

    Performs checks on:
    - File name format
    - File extension
    - File size
    - Gzip validity
    """

    # File size limits (bytes)
    MIN_FILE_SIZE = 100  # 100 bytes
    MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB

    def __init__(self, strict_mode: bool = False):
        """
        Initialize the file validator.

        Args:
            strict_mode: If True, treat warnings as errors
        """
        self.strict_mode = strict_mode

    def validate_file_name(self, file_name: str) -> ValidationResult:
        """
        Validate the file name format.

        Expected format: YYYY-MM-DD-HH.json.gz

        Args:
            file_name: Name of the file (with extension)

        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        # Check extension
        if not file_name.endswith('.json.gz'):
            result.add_error(f"File must have .json.gz extension, got: {file_name}")
            return result

        # Check pattern
        match = FILE_NAME_PATTERN.match(file_name)
        if not match:
            result.add_error(
                f"File name must match format YYYY-MM-DD-HH.json.gz, got: {file_name}"
            )
            return result

        # Extract and validate date/time components
        date_str = match.group(1)  # YYYY-MM-DD-HH
        parts = date_str.split('-')

        try:
            year, month, day, hour = map(int, parts)

            # Basic sanity checks
            if year < 2011 or year > 2100:
                result.add_error(f"Invalid year: {year}")
            if month < 1 or month > 12:
                result.add_error(f"Invalid month: {month}")
            if day < 1 or day > 31:
                result.add_error(f"Invalid day: {day}")
            if hour < 0 or hour > 23:
                result.add_error(f"Invalid hour: {hour}")
        except ValueError:
            result.add_error(f"Invalid date/time format: {date_str}")

        return result

    def validate_file_size(self, size_bytes: int) -> ValidationResult:
        """
        Validate the file size.

        Args:
            size_bytes: Size of the file in bytes

        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        if size_bytes < self.MIN_FILE_SIZE:
            result.add_error(
                f"File too small: {size_bytes} bytes (minimum: {self.MIN_FILE_SIZE})"
            )

        if size_bytes > self.MAX_FILE_SIZE:
            result.add_error(
                f"File too large: {size_bytes} bytes (maximum: {self.MAX_FILE_SIZE})"
            )

        return result

    def validate_gzip(self, file_path: str) -> ValidationResult:
        """
        Validate that the file is a valid gzip file.

        Args:
            file_path: Path to the file

        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        try:
            with gzip.open(file_path, 'rb') as f:
                # Try to read first byte to verify it's valid gzip
                f.read(1)
        except gzip.BadGzipFile:
            result.add_error(f"Invalid gzip file: {file_path}")
        except Exception as e:
            result.add_error(f"Error reading gzip file: {e}")

        return result

    def validate_json_lines(self, file_path: str, max_lines: int = 10) -> ValidationResult:
        """
        Validate that the file contains valid JSON lines.

        Checks the first N lines to verify JSON structure.

        Args:
            file_path: Path to the file
            max_lines: Maximum number of lines to check

        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        try:
            import json

            line_count = 0
            empty_count = 0

            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                for line in f:
                    line_count += 1

                    if line_count > max_lines:
                        break

                    line = line.strip()

                    # Skip empty lines
                    if not line:
                        empty_count += 1
                        continue

                    # Try to parse JSON
                    try:
                        json.loads(line)
                    except json.JSONDecodeError as e:
                        result.add_error(f"Invalid JSON on line {line_count}: {e}")
                        break

            # Warn if many empty lines
            if empty_count > max_lines * 0.5:
                result.add_warning(
                    f"More than 50% empty lines in first {max_lines} lines"
                )

        except Exception as e:
            result.add_error(f"Error reading JSON lines: {e}")

        return result

    def validate_all(
        self,
        file_name: str,
        file_size: int,
        file_path: Optional[str] = None,
        check_content: bool = True
    ) -> ValidationResult:
        """
        Perform all file-level validations.

        Args:
            file_name: Name of the file
            file_size: Size of the file in bytes
            file_path: Full path to the file (for content validation)
            check_content: Whether to check file content (gzip, JSON)

        Returns:
            Combined ValidationResult
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        # Validate file name
        name_result = self.validate_file_name(file_name)
        result.errors.extend(name_result.errors)
        result.warnings.extend(name_result.warnings)

        # Validate file size
        size_result = self.validate_file_size(file_size)
        result.errors.extend(size_result.errors)
        result.warnings.extend(size_result.warnings)

        # Content validation (if file path provided)
        if check_content and file_path:
            # Validate gzip
            gzip_result = self.validate_gzip(file_path)
            result.errors.extend(gzip_result.errors)
            result.warnings.extend(gzip_result.warnings)

            # Only check JSON if gzip is valid
            if gzip_result.is_valid:
                json_result = self.validate_json_lines(file_path)
                result.errors.extend(json_result.errors)
                result.warnings.extend(json_result.warnings)

        # Update validity
        if result.errors:
            result.is_valid = False

        # In strict mode, warnings also invalidate
        if self.strict_mode and result.warnings:
            result.is_valid = False

        return result

    def parse_file_metadata(self, file_name: str) -> Dict[str, Any]:
        """
        Parse metadata from file name.

        Args:
            file_name: Name of the file (e.g., 2026-03-05-12.json.gz)

        Returns:
            Dictionary with parsed metadata (date, hour, etc.)
        """
        metadata = {
            'file_name': file_name,
            'valid': False,
            'year': None,
            'month': None,
            'day': None,
            'hour': None,
            'date_str': None,
        }

        match = FILE_NAME_PATTERN.match(file_name)
        if match:
            metadata['valid'] = True
            date_str = match.group(1)
            metadata['date_str'] = date_str

            parts = date_str.split('-')
            metadata['year'] = int(parts[0])
            metadata['month'] = int(parts[1])
            metadata['day'] = int(parts[2])
            metadata['hour'] = int(parts[3])

        return metadata


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
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


def extract_hour_from_filename(file_name: str) -> Optional[int]:
    """
    Extract the hour from a filename.

    Args:
        file_name: File name (e.g., 2026-03-05-12.json.gz)

    Returns:
        Hour as integer, or None if invalid
    """
    match = FILE_NAME_PATTERN.match(file_name)
    if match:
        parts = match.group(1).split('-')
        return int(parts[3])
    return None
