"""
Data type validation for GitHub Archive events using Pandas.

Validates and coerces data types for event records using vectorized operations.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass


# =============================================================================
# VALIDATION RESULT
# =============================================================================
@dataclass
class DtypeValidationResult:
    """Result of dtype validation and coercion."""
    is_valid: bool
    coerced_df: Optional[pd.DataFrame]
    errors: List[str]
    null_counts: Dict[str, int]

    @property
    def total_nulls(self) -> int:
        return sum(self.null_counts.values())


# =============================================================================
# DTYPE VALIDATOR
# =============================================================================
class DtypeValidator:
    """
    Validates and coerces data types for GitHub event dataframes.

    Uses vectorized Pandas operations for efficient processing.
    """

    # Expected dtypes for input fields
    INPUT_DTYPES: Dict[str, str] = {
        'id': 'string',
        'type': 'string',
        'created_at': 'string',
        'public': 'boolean',
        # Nested objects kept as object initially
        'actor': 'object',
        'repo': 'object',
        'payload': 'object',
        'org': 'object',
    }

    # Expected dtypes for output (flattened) fields
    OUTPUT_DTYPES: Dict[str, str] = {
        'event_id': 'string',
        'event_type': 'string',
        'created_at': 'string',
        'actor_id': 'Int64',
        'actor_login': 'string',
        'actor_avatar_url': 'string',
        'actor_gravatar_id': 'string',
        'actor_type': 'string',
        'actor_url': 'string',
        'actor_site_admin': 'boolean',
        'repo_id': 'Int64',
        'repo_name': 'string',
        'repo_url': 'string',
        'public': 'boolean',
    }

    def __init__(self, strict_mode: bool = False):
        """
        Initialize the dtype validator.

        Args:
            strict_mode: If True, raise exceptions on coercion failures
        """
        self.strict_mode = strict_mode

    def validate_input_dtypes(self, df: pd.DataFrame) -> DtypeValidationResult:
        """
        Validate and coerce dtypes for input dataframe.

        Args:
            df: Input dataframe with raw GitHub events

        Returns:
            DtypeValidationResult with coerced dataframe and any errors
        """
        errors = []
        null_counts = {}
        result_df = df.copy()

        for col, expected_dtype in self.INPUT_DTYPES.items():
            if col not in df.columns:
                errors.append(f"Required column '{col}' not found in dataframe")
                continue

            # Coerce to expected dtype
            try:
                if expected_dtype == 'string':
                    result_df[col] = result_df[col].astype('string')
                elif expected_dtype == 'boolean':
                    result_df[col] = result_df[col].astype('boolean')
                elif expected_dtype == 'object':
                    # Keep as object for nested JSON
                    result_df[col] = result_df[col].astype('object')

                # Count nulls after coercion
                null_count = result_df[col].isna().sum()
                if null_count > 0:
                    null_counts[col] = int(null_count)

            except Exception as e:
                error_msg = f"Error coercing column '{col}' to {expected_dtype}: {e}"
                if self.strict_mode:
                    errors.append(error_msg)
                else:
                    # In non-strict mode, log but continue
                    null_counts[col] = result_df[col].isna().sum()

        return DtypeValidationResult(
            is_valid=len(errors) == 0,
            coerced_df=result_df if not errors else None,
            errors=errors,
            null_counts=null_counts
        )

    def validate_output_dtypes(self, df: pd.DataFrame) -> DtypeValidationResult:
        """
        Validate and coerce dtypes for output (flattened) dataframe.

        Args:
            df: Flattened dataframe ready for staging output

        Returns:
            DtypeValidationResult with coerced dataframe and any errors
        """
        errors = []
        null_counts = {}
        result_df = df.copy()

        for col, expected_dtype in self.OUTPUT_DTYPES.items():
            if col not in df.columns:
                # Optional field - skip with warning
                continue

            # Coerce to expected dtype
            try:
                if expected_dtype == 'string':
                    result_df[col] = result_df[col].astype('string')
                elif expected_dtype == 'Int64':
                    # Use pandas nullable integer
                    result_df[col] = pd.to_numeric(result_df[col], errors='coerce').astype('Int64')
                elif expected_dtype == 'boolean':
                    result_df[col] = result_df[col].astype('boolean')

                # Count nulls after coercion
                null_count = result_df[col].isna().sum()
                if null_count > 0:
                    null_counts[col] = int(null_count)

            except Exception as e:
                error_msg = f"Error coercing column '{col}' to {expected_dtype}: {e}"
                if self.strict_mode:
                    errors.append(error_msg)
                else:
                    null_counts[col] = result_df[col].isna().sum()

        return DtypeValidationResult(
            is_valid=len(errors) == 0,
            coerced_df=result_df if not errors else None,
            errors=errors,
            null_counts=null_counts
        )

    def coerce_nested_field(
        self,
        df: pd.DataFrame,
        source_col: str,
        field_name: str,
        target_dtype: str = 'string',
        default_value: Any = None
    ) -> pd.Series:
        """
        Extract and coerce a field from a nested object column.

        Args:
            df: Input dataframe
            source_col: Column containing nested objects (e.g., 'actor')
            field_name: Field to extract (e.g., 'id')
            target_dtype: Target data type
            default_value: Default value if field is missing

        Returns:
            Series with extracted and coerced values
        """
        def extract_field(obj: Any) -> Any:
            """Extract field from nested object."""
            if isinstance(obj, dict):
                return obj.get(field_name, default_value)
            return default_value

        # Extract field
        series = df[source_col].apply(extract_field)

        # Coerce dtype
        try:
            if target_dtype == 'string':
                series = series.astype('string')
            elif target_dtype == 'Int64':
                series = pd.to_numeric(series, errors='coerce').astype('Int64')
            elif target_dtype == 'boolean':
                series = series.astype('boolean')
            elif target_dtype == 'int64':
                series = pd.to_numeric(series, errors='coerce')
        except Exception:
            # Return as-is if coercion fails
            pass

        return series

    def validate_timestamp_format(
        self,
        df: pd.DataFrame,
        timestamp_col: str = 'created_at'
    ) -> Tuple[bool, List[str]]:
        """
        Validate timestamp format (ISO 8601).

        Args:
            df: Input dataframe
            timestamp_col: Column containing timestamps

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        if timestamp_col not in df.columns:
            return False, [f"Timestamp column '{timestamp_col}' not found"]

        try:
            import re
            from datetime import datetime

            # ISO 8601 pattern (simplified)
            iso_pattern = re.compile(
                r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?$'
            )

            # Check for nulls
            null_count = df[timestamp_col].isna().sum()
            if null_count > 0:
                errors.append(f"{null_count} null timestamps found")

            # Check format for non-null values
            non_null_ts = df[timestamp_col].dropna()
            invalid_count = 0

            for ts in non_null_ts.head(1000):  # Sample first 1000
                ts_str = str(ts)
                if not iso_pattern.match(ts_str):
                    try:
                        # Try to parse as datetime
                        datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    except Exception:
                        invalid_count += 1

            if invalid_count > 0:
                errors.append(f"{invalid_count} timestamps have invalid format")

        except Exception as e:
            errors.append(f"Error validating timestamps: {e}")

        return len(errors) == 0, errors


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def get_null_summary(df: pd.DataFrame) -> Dict[str, int]:
    """
    Get a summary of null values in a dataframe.

    Args:
        df: Input dataframe

    Returns:
        Dictionary mapping column names to null counts
    """
    return df.isna().sum().to_dict()


def get_dtypes_summary(df: pd.DataFrame) -> Dict[str, str]:
    """
    Get a summary of dtypes in a dataframe.

    Args:
        df: Input dataframe

    Returns:
        Dictionary mapping column names to dtype names
    """
    return {col: str(dtype) for col, dtype in df.dtypes.items()}
