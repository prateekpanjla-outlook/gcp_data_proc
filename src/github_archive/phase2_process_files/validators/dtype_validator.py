"""
Data type validation for GitHub Archive events using Pandas.

Validates and coerces data types for event records using vectorized operations.
"""

import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass

# Import schema definitions from source of truth
from ..schemas.dtype_definitions import GITHUB_EVENT_DTYPES


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

        for col, expected_dtype in GITHUB_EVENT_DTYPES.items():
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
