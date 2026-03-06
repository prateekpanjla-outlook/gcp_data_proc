"""
Value validation for GitHub Archive events.

Validates field values, enums, and business rules using vectorized operations.
"""

import pandas as pd
import re
from typing import Dict, List, Set, Any, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass


# Import valid event types from schema definitions
from ..schemas.dtype_definitions import (
    VALID_EVENT_TYPES,
    REQUIRED_FIELDS,
    ACTOR_FIELDS,
    REPO_FIELDS,
)


# =============================================================================
# VALIDATION RESULT
# =============================================================================
@dataclass
class ValueValidationResult:
    """Result of value validation."""
    is_valid: bool
    valid_df: Optional[pd.DataFrame]
    invalid_count: int
    errors: Dict[str, int]  # Field -> error count
    warnings: Dict[str, int]  # Field -> warning count

    @property
    def total_errors(self) -> int:
        return sum(self.errors.values())

    @property
    def total_warnings(self) -> int:
        return sum(self.warnings.values())


# =============================================================================
# VALUE VALIDATOR
# =============================================================================
class ValueValidator:
    """
    Validates field values in GitHub event dataframes.

    Uses vectorized Pandas operations for efficient validation.
    """

    def __init__(
        self,
        strict_mode: bool = False,
        max_error_rate: float = 0.10
    ):
        """
        Initialize the value validator.

        Args:
            strict_mode: If True, filter out all invalid records
            max_error_rate: Maximum error rate before aborting (0.0-1.0)
        """
        self.strict_mode = strict_mode
        self.max_error_rate = max_error_rate

    def validate_required_fields(self, df: pd.DataFrame) -> ValueValidationResult:
        """
        Validate that required fields are present and non-null.

        Args:
            df: Input dataframe

        Returns:
            ValueValidationResult
        """
        errors = {}
        warnings = {}
        valid_df = df.copy()

        # Check for required columns
        missing_cols = set(REQUIRED_FIELDS) - set(df.columns)
        if missing_cols:
            for col in missing_cols:
                errors[col] = df.shape[0]  # All rows are invalid
            return ValueValidationResult(
                is_valid=False,
                valid_df=None,
                invalid_count=df.shape[0],
                errors=errors,
                warnings=warnings
            )

        # Check for null values in required fields
        for col in REQUIRED_FIELDS:
            null_count = df[col].isna().sum()
            if null_count > 0:
                errors[col] = int(null_count)

        if errors:
            # Filter out rows with nulls in required fields
            for col in REQUIRED_FIELDS:
                valid_df = valid_df[valid_df[col].notna() | (valid_df[col] != '')]

        invalid_count = df.shape[0] - valid_df.shape[0]

        return ValueValidationResult(
            is_valid=invalid_count == 0,
            valid_df=valid_df if invalid_count > 0 or self.strict_mode else df,
            invalid_count=invalid_count,
            errors=errors,
            warnings=warnings
        )

    def validate_event_types(self, df: pd.DataFrame, type_col: str = 'type') -> ValueValidationResult:
        """
        Validate event types against known GitHub event types.

        Args:
            df: Input dataframe
            type_col: Column containing event types

        Returns:
            ValueValidationResult
        """
        errors = {}
        warnings = {}
        valid_df = df.copy()

        if type_col not in df.columns:
            errors[type_col] = df.shape[0]
            return ValueValidationResult(
                is_valid=False,
                valid_df=None,
                invalid_count=df.shape[0],
                errors=errors,
                warnings=warnings
            )

        # Find invalid event types (vectorized)
        if df[type_col].dtype == 'string':
            invalid_mask = ~df[type_col].isin(VALID_EVENT_TYPES) & df[type_col].notna()
        else:
            # Convert to string for comparison
            invalid_mask = ~df[type_col].astype(str).isin(VALID_EVENT_TYPES) & df[type_col].notna()

        invalid_count = invalid_mask.sum()

        if invalid_count > 0:
            errors[type_col] = int(invalid_count)

            # Get the invalid types for warning
            invalid_types = df.loc[invalid_mask, type_col].value_counts()
            for evt_type, count in invalid_types.items():
                warnings[f"unknown_type_{evt_type}"] = int(count)

            # Filter out invalid types
            valid_df = valid_df[~invalid_mask]

        return ValueValidationResult(
            is_valid=invalid_count == 0,
            valid_df=valid_df if invalid_count > 0 or self.strict_mode else df,
            invalid_count=int(invalid_count),
            errors=errors,
            warnings=warnings
        )

    def validate_timestamps(
        self,
        df: pd.DataFrame,
        timestamp_col: str = 'created_at'
    ) -> ValueValidationResult:
        """
        Validate timestamps are not in the future.

        Args:
            df: Input dataframe
            timestamp_col: Column containing timestamps

        Returns:
            ValueValidationResult
        """
        errors = {}
        warnings = {}
        valid_df = df.copy()

        if timestamp_col not in df.columns:
            return ValueValidationResult(
                is_valid=True,
                valid_df=df,
                invalid_count=0,
                errors=errors,
                warnings=warnings
            )

        now = datetime.now(timezone.utc)

        def is_future_timestamp(ts_str: Any) -> bool:
            """Check if timestamp is in the future."""
            if pd.isna(ts_str):
                return False
            try:
                # Parse ISO timestamp
                if isinstance(ts_str, str):
                    # Handle 'Z' suffix
                    ts_str = ts_str.replace('Z', '+00:00')
                    ts = datetime.fromisoformat(ts_str)
                    # Make timezone-aware if naive
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    return ts > now
            except Exception:
                return False
            return False

        # Check for future timestamps (vectorized where possible)
        try:
            future_mask = df[timestamp_col].apply(is_future_timestamp)
            future_count = future_mask.sum()

            if future_count > 0:
                errors[timestamp_col] = int(future_count)
                warnings['future_timestamps'] = int(future_count)

                # Filter out future timestamps
                valid_df = valid_df[~future_mask]

        except Exception as e:
            warnings['timestamp_validation_error'] = 1

        invalid_count = df.shape[0] - valid_df.shape[0]

        return ValueValidationResult(
            is_valid=invalid_count == 0,
            valid_df=valid_df if invalid_count > 0 or self.strict_mode else df,
            invalid_count=int(invalid_count),
            errors=errors,
            warnings=warnings
        )

    def validate_ids(self, df: pd.DataFrame) -> ValueValidationResult:
        """
        Validate that ID fields are positive integers.

        Args:
            df: Flattened dataframe with actor_id, repo_id, etc.

        Returns:
            ValueValidationResult
        """
        errors = {}
        warnings = {}
        valid_df = df.copy()

        # Check actor_id
        if 'actor_id' in df.columns:
            invalid_actor = (df['actor_id'] < 0) | (df['actor_id'].isna())
            invalid_actor_count = invalid_actor.sum()
            if invalid_actor_count > 0:
                errors['actor_id'] = int(invalid_actor_count)
                valid_df = valid_df[~invalid_actor]

        # Check repo_id
        if 'repo_id' in df.columns:
            invalid_repo = (df['repo_id'] < 0) | (df['repo_id'].isna())
            invalid_repo_count = invalid_repo.sum()
            if invalid_repo_count > 0:
                errors['repo_id'] = int(invalid_repo_count)
                valid_df = valid_df[~invalid_repo]

        # Check event_id (should be non-empty string)
        if 'event_id' in df.columns:
            invalid_event = df['event_id'].isna() | (df['event_id'] == '')
            invalid_event_count = invalid_event.sum()
            if invalid_event_count > 0:
                errors['event_id'] = int(invalid_event_count)
                valid_df = valid_df[~invalid_event]

        invalid_count = df.shape[0] - valid_df.shape[0]

        return ValueValidationResult(
            is_valid=invalid_count == 0,
            valid_df=valid_df if invalid_count > 0 or self.strict_mode else df,
            invalid_count=int(invalid_count),
            errors=errors,
            warnings=warnings
        )

    def validate_all(
        self,
        df: pd.DataFrame,
        validate_timestamps: bool = True,
        validate_ids: bool = True
    ) -> ValueValidationResult:
        """
        Perform all value validations.

        Args:
            df: Input dataframe
            validate_timestamps: Whether to validate timestamps
            validate_ids: Whether to validate IDs (requires flattened schema)

        Returns:
            Combined ValueValidationResult
        """
        all_errors = {}
        all_warnings = {}
        current_df = df.copy()
        total_invalid = 0

        # Validate required fields
        result = self.validate_required_fields(current_df)
        all_errors.update(result.errors)
        all_warnings.update(result.warnings)
        total_invalid += result.invalid_count
        current_df = result.valid_df if result.valid_df is not None else current_df

        if current_df.empty:
            return ValueValidationResult(
                is_valid=False,
                valid_df=None,
                invalid_count=df.shape[0],
                errors=all_errors,
                warnings=all_warnings
            )

        # Validate event types
        result = self.validate_event_types(current_df)
        all_errors.update(result.errors)
        all_warnings.update(result.warnings)
        total_invalid += result.invalid_count
        current_df = result.valid_df if result.valid_df is not None else current_df

        if current_df.empty:
            return ValueValidationResult(
                is_valid=False,
                valid_df=None,
                invalid_count=df.shape[0],
                errors=all_errors,
                warnings=all_warnings
            )

        # Validate timestamps
        if validate_timestamps:
            result = self.validate_timestamps(current_df)
            all_errors.update(result.errors)
            all_warnings.update(result.warnings)
            total_invalid += result.invalid_count
            current_df = result.valid_df if result.valid_df is not None else current_df

        if current_df.empty:
            return ValueValidationResult(
                is_valid=False,
                valid_df=None,
                invalid_count=df.shape[0],
                errors=all_errors,
                warnings=all_warnings
            )

        # Validate IDs (only for flattened schema)
        if validate_ids:
            result = self.validate_ids(current_df)
            all_errors.update(result.errors)
            all_warnings.update(result.warnings)
            total_invalid += result.invalid_count
            current_df = result.valid_df if result.valid_df is not None else current_df

        # Check error rate
        error_rate = total_invalid / df.shape[0] if df.shape[0] > 0 else 0
        is_valid = error_rate <= self.max_error_rate

        return ValueValidationResult(
            is_valid=is_valid,
            valid_df=current_df if is_valid or self.strict_mode else df,
            invalid_count=total_invalid,
            errors=all_errors,
            warnings=all_warnings
        )


# =============================================================================
# BUSINESS RULE VALIDATOR
# =============================================================================
class BusinessValidator:
    """
    Validates business rules specific to GitHub events.

    These are domain-specific validations beyond basic type/value checks.
    """

    def validate_push_event(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        Validate PushEvent-specific business rules.

        Args:
            df: Dataframe filtered to PushEvent records

        Returns:
            Dictionary of validation errors
        """
        errors = {}

        if df.empty:
            return errors

        # PushEvent should have a ref (branch/tag)
        if 'payload_ref' in df.columns:
            null_refs = df['payload_ref'].isna().sum()
            if null_refs > 0:
                errors['push_event_missing_ref'] = int(null_refs)

        # PushEvent should have size (number of commits)
        if 'payload_size' in df.columns:
            negative_sizes = (df['payload_size'] < 0).sum()
            if negative_sizes > 0:
                errors['push_event_negative_size'] = int(negative_sizes)

        return errors

    def validate_pr_event(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        Validate PullRequestEvent-specific business rules.

        Args:
            df: Dataframe filtered to PullRequestEvent records

        Returns:
            Dictionary of validation errors
        """
        errors = {}

        if df.empty:
            return errors

        # PR events should have action field
        # This would be in payload.action for nested schema
        return errors

    def validate_event_consistency(
        self,
        df: pd.DataFrame
    ) -> Dict[str, int]:
        """
        Validate cross-field consistency.

        Args:
            df: Flattened dataframe

        Returns:
            Dictionary of validation errors
        """
        errors = {}

        if df.empty:
            return errors

        # Actor should have login if ID is present
        if 'actor_id' in df.columns and 'actor_login' in df.columns:
            has_id = df['actor_id'].notna()
            missing_login = has_id & df['actor_login'].isna()
            missing_login_count = missing_login.sum()
            if missing_login_count > 0:
                errors['actor_without_login'] = int(missing_login_count)

        # Repo should have name if ID is present
        if 'repo_id' in df.columns and 'repo_name' in df.columns:
            has_id = df['repo_id'].notna()
            missing_name = has_id & df['repo_name'].isna()
            missing_name_count = missing_name.sum()
            if missing_name_count > 0:
                errors['repo_without_name'] = int(missing_name_count)

        return errors
