"""
Unified validator for GitHub Archive events.

Validates dtypes, required fields, IDs, and timestamps in a single pass
using a boolean mask to avoid DataFrame copies.
"""

import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Optional
from dataclasses import dataclass, field

from schemas.dtype_definitions import GITHUB_EVENT_DTYPES, REQUIRED_FIELDS


@dataclass
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    valid_df: Optional[pd.DataFrame]
    records_in: int
    records_out: int
    errors: Dict[str, int] = field(default_factory=dict)
    warnings: Dict[str, int] = field(default_factory=dict)


def validate_chunk(df: pd.DataFrame) -> ValidationResult:
    """
    Validate a chunk of GitHub events in a single pass.

    Coerces dtypes, then builds a boolean mask across all checks.
    Drops invalid rows once at the end.

    Args:
        df: Raw chunk from pd.read_json

    Returns:
        ValidationResult with filtered DataFrame and error counts
    """
    errors = {}
    warnings = {}
    records_in = len(df)

    # --- Phase 1: Dtype coercion (in-place on the chunk, no copy) ---
    for col, expected_dtype in GITHUB_EVENT_DTYPES.items():
        if col not in df.columns:
            continue
        try:
            source_nulls = df[col].isna().sum()
            if expected_dtype in ('string', 'boolean', 'object'):
                df[col] = df[col].astype(expected_dtype)
            nulls_after = df[col].isna().sum()
            coercion_nulls = int(nulls_after - source_nulls)
            if coercion_nulls > 0:
                errors[f'{col}_coercion'] = coercion_nulls
        except Exception:
            warnings[f'{col}_coercion_error'] = 1

    # --- Phase 2: Build mask (all checks, one filter) ---
    mask = pd.Series(True, index=df.index)

    # Required fields: must be present, non-null, non-empty
    missing_cols = set(REQUIRED_FIELDS) - set(df.columns)
    if missing_cols:
        for col in missing_cols:
            errors[col] = records_in
        return ValidationResult(
            is_valid=False, valid_df=None,
            records_in=records_in, records_out=0,
            errors=errors, warnings=warnings,
        )

    for col in REQUIRED_FIELDS:
        bad = df[col].isna() | (df[col].astype(str).str.strip() == '')
        n = int(bad.sum())
        if n:
            errors[col] = n
        mask &= ~bad

    # ID fields: must be non-null and >= 0
    for col in ('actor_id', 'repo_id'):
        if col in df.columns:
            bad = df[col].isna() | (df[col] < 0)
            n = int(bad.sum())
            if n:
                errors[col] = n
            mask &= ~bad

    # event_id: non-null and non-empty (checked on flattened schema)
    if 'event_id' in df.columns:
        bad = df['event_id'].isna() | (df['event_id'] == '')
        n = int(bad.sum())
        if n:
            errors['event_id'] = n
        mask &= ~bad

    # Future timestamps
    if 'created_at' in df.columns:
        now = datetime.now(timezone.utc)

        def _is_future(ts):
            if pd.isna(ts):
                return False
            try:
                if isinstance(ts, str):
                    ts = ts.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(ts)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt > now
            except Exception:
                return False
            return False

        future = df['created_at'].apply(_is_future)
        n = int(future.sum())
        if n:
            errors['created_at_future'] = n
            warnings['future_timestamps'] = n
        mask &= ~future

    # --- Phase 3: Single filter ---
    valid_df = df[mask]
    records_out = len(valid_df)

    return ValidationResult(
        is_valid=records_out == records_in,
        valid_df=valid_df,
        records_in=records_in,
        records_out=records_out,
        errors=errors,
        warnings=warnings,
    )
