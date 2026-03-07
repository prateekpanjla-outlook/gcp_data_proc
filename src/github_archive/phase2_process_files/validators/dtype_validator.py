"""
Data type validation for GitHub Archive events using Pandas.

Validates and coerces data types for event records using vectorized operations.
"""

import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass

# Import schema definitions from source of truth
from schemas.dtype_definitions import GITHUB_EVENT_DTYPES


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
    coercion_null_counts: Dict[str, int] = None  # New: track coercion failures separately

    def __post_init__(self):
        if self.coercion_null_counts is None:
            self.coercion_null_counts = {}

    @property
    def total_nulls(self) -> int:
        return sum(self.null_counts.values())

    @property
    def total_coercion_nulls(self) -> int:
        """Return count of nulls introduced by dtype coercion failures."""
        return sum(self.coercion_null_counts.values())


# =============================================================================
# DTYPE VALIDATOR
# =============================================================================
class DtypeValidator:
    """
    Validates and coerces data types for GitHub event dataframes.

    Uses vectorized Pandas operations for efficient processing.
    """

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

        Distinguishes between:
        - Source nulls: null values present in original data
        - Coercion nulls: new nulls introduced by dtype coercion failures

        Args:
            df: Input dataframe with raw GitHub events

        Returns:
            DtypeValidationResult with coerced dataframe and any errors
        """
        errors = []
        null_counts = {}  # Actual nulls in source data
        coercion_null_counts = {}  # Nulls introduced by coercion
        result_df = df.copy()

        for col, expected_dtype in GITHUB_EVENT_DTYPES.items():
            if col not in df.columns:
                errors.append(f"Required column '{col}' not found in dataframe")
                continue

            # Count source nulls BEFORE coercion (actual nulls in data)
            source_nulls = result_df[col].isna().sum()

            # Coerce to expected dtype
            try:
                if expected_dtype == 'string':
                    result_df[col] = result_df[col].astype('string')
                elif expected_dtype == 'boolean':
                    result_df[col] = result_df[col].astype('boolean')
                elif expected_dtype == 'object':
                    # Keep as object for nested JSON
                    result_df[col] = result_df[col].astype('object')

                # Count nulls AFTER coercion (includes source + coercion failures)
                nulls_after = result_df[col].isna().sum()

                # Calculate new nulls introduced by coercion
                coercion_nulls = int(nulls_after - source_nulls)

                # Track source nulls (for informational purposes, not counted as errors)
                if source_nulls > 0:
                    null_counts[col] = int(source_nulls)

                # Only count coercion failures as errors
                if coercion_nulls > 0:
                    coercion_null_counts[col] = coercion_nulls

            except Exception as e:
                error_msg = f"Error coercing column '{col}' to {expected_dtype}: {e}"
                if self.strict_mode:
                    errors.append(error_msg)
                else:
                    # In non-strict mode, count all nulls as coercion failures
                    coercion_null_counts[col] = result_df[col].isna().sum()

        return DtypeValidationResult(
            is_valid=len(errors) == 0,
            coerced_df=result_df if not errors else None,
            errors=errors,
            null_counts=null_counts,  # Source nulls (informational, not errors)
            coercion_null_counts=coercion_null_counts  # Coercion failures (actual errors)
        )
