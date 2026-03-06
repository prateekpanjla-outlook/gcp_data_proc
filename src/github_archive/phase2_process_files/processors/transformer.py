"""
Transformer for GitHub Archive events.

Flattens nested JSON structures into the staging schema format.
"""

import pandas as pd
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Import field mappings from source of truth
from ..schemas.dtype_definitions import (
    ACTOR_FIELD_MAPPING,
    REPO_FIELD_MAPPING,
)


# =============================================================================
# TRANSFORMATION RESULT
# =============================================================================
@dataclass
class TransformationResult:
    """Result of a transformation operation."""
    df: pd.DataFrame
    records_in: int
    records_out: int
    error_count: int


# =============================================================================
# PAYLOAD FIELD MAPPING (not in dtype_definitions as it varies by event type)
# =============================================================================
PAYLOAD_FIELD_MAPPING = {
    'ref': 'payload_ref',
    'ref_type': 'payload_ref_type',
    'push_id': 'payload_push_id',
    'size': 'payload_size',
    'distinct_size': 'payload_distinct_size',
    'head': 'payload_head',
    'before': 'payload_before',
}


# =============================================================================
# TRANSFORMER
# =============================================================================
class GitHubEventTransformer:
    """
    Transforms GitHub Archive events from nested JSON to flattened schema.

    Uses vectorized Pandas operations for efficient processing.
    """

    def __init__(self):
        """Initialize the transformer."""
        pass

    def extract_actor_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract actor fields from nested actor object.

        Args:
            df: Input dataframe with 'actor' column containing nested objects

        Returns:
            Dataframe with extracted actor fields
        """
        if 'actor' not in df.columns:
            return df

        result = df.copy()

        # Extract each actor field
        for source_field, target_field in ACTOR_FIELD_MAPPING.items():
            result[target_field] = result['actor'].apply(
                lambda x: self._safe_get(x, source_field),
                meta=(target_field, 'object')
            )

        return result

    def extract_repo_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract repo fields from nested repo object.

        Args:
            df: Input dataframe with 'repo' column containing nested objects

        Returns:
            Dataframe with extracted repo fields
        """
        if 'repo' not in df.columns:
            return df

        result = df.copy()

        # Extract each repo field
        for source_field, target_field in REPO_FIELD_MAPPING.items():
            result[target_field] = result['repo'].apply(
                lambda x: self._safe_get(x, source_field),
                meta=(target_field, 'object')
            )

        return result

    def extract_payload_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract common payload fields.

        Args:
            df: Input dataframe with 'payload' column containing nested objects

        Returns:
            Dataframe with extracted payload fields
        """
        if 'payload' not in df.columns:
            return df

        result = df.copy()

        # Extract each payload field
        for source_field, target_field in PAYLOAD_FIELD_MAPPING.items():
            result[target_field] = result['payload'].apply(
                lambda x: self._safe_get(x, source_field),
                meta=(target_field, 'object')
            )

        return result

    def flatten_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform nested schema to flattened staging schema.

        Args:
            df: Input dataframe with nested GitHub events

        Returns:
            Flattened dataframe ready for staging output
        """
        # Start with core fields
        result = pd.DataFrame()

        # Map core fields
        result['event_id'] = df.get('id', pd.Series(dtype='string'))
        result['event_type'] = df.get('type', pd.Series(dtype='string'))
        result['created_at'] = df.get('created_at', pd.Series(dtype='string'))
        result['public'] = df.get('public', True)

        # Extract nested fields
        result = self._merge_extracted(result, df, ['actor'], ACTOR_FIELD_MAPPING)
        result = self._merge_extracted(result, df, ['repo'], REPO_FIELD_MAPPING)
        result = self._merge_extracted(result, df, ['payload'], PAYLOAD_FIELD_MAPPING)

        return result

    def _merge_extracted(
        self,
        result: pd.DataFrame,
        source_df: pd.DataFrame,
        source_columns: List[str],
        field_mapping: Dict[str, str]
    ) -> pd.DataFrame:
        """Merge extracted fields into result dataframe."""
        for source_col in source_columns:
            if source_col not in source_df.columns:
                # Add empty columns with default None
                for target_field in field_mapping.values():
                    if target_field not in result.columns:
                        result[target_field] = None
                continue

            for source_field, target_field in field_mapping.items():
                if target_field not in result.columns:
                    result[target_field] = source_df[source_col].apply(
                        lambda x: self._safe_get(x, source_field) if isinstance(x, dict) else None
                    )

        return result

    def _safe_get(self, obj: Any, field: str, default: Any = None) -> Any:
        """Safely get a field from a dictionary."""
        if isinstance(obj, dict):
            return obj.get(field, default)
        return default

    def transform_chunk(self, df: pd.DataFrame) -> TransformationResult:
        """
        Transform a chunk of GitHub events.

        Args:
            df: Input dataframe with nested GitHub events

        Returns:
            TransformationResult with flattened dataframe
        """
        records_in = len(df)

        try:
            # Flatten schema
            flattened = self.flatten_schema(df)

            # Ensure proper dtypes
            flattened = self._ensure_dtypes(flattened)

            records_out = len(flattened)

            return TransformationResult(
                df=flattened,
                records_in=records_in,
                records_out=records_out,
                error_count=records_in - records_out
            )

        except Exception as e:
            # Return empty dataframe on error
            return TransformationResult(
                df=pd.DataFrame(),
                records_in=records_in,
                records_out=0,
                error_count=records_in
            )

    def _ensure_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure proper dtypes for output columns."""
        # String columns
        string_cols = [
            'event_id', 'event_type', 'created_at',
            'actor_login', 'actor_display_login', 'actor_avatar_url', 'actor_gravatar_id',
            'actor_type', 'actor_url',
            'repo_name', 'repo_url',
            'payload_ref', 'payload_ref_type',
            'payload_head', 'payload_before'
        ]

        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype('string')

        # Integer columns (nullable Int64 - handles JSON null properly)
        int_cols = [
            'actor_id', 'repo_id', 'payload_push_id',
            'payload_size', 'payload_distinct_size'
        ]

        for col in int_cols:
            if col in df.columns:
                df[col] = df[col].astype('Int64')

        # Boolean columns
        bool_cols = ['public', 'actor_site_admin']

        for col in bool_cols:
            if col in df.columns:
                df[col] = df[col].astype('boolean')

        return df


# =============================================================================
# BATCH TRANSFORMER
# =============================================================================
class BatchTransformer:
    """
    Transforms multiple chunks of GitHub events.

    Processes chunks sequentially and aggregates results.
    """

    def __init__(self, chunksize: int = 100_000):
        """
        Initialize the batch transformer.

        Args:
            chunksize: Number of records per chunk
        """
        self.chunksize = chunksize
        self.transformer = GitHubEventTransformer()
        self.stats = {
            'total_records_in': 0,
            'total_records_out': 0,
            'total_errors': 0,
            'chunks_processed': 0,
        }

    def transform_dataframe(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Transform a dataframe in chunks.

        Args:
            df: Input dataframe

        Returns:
            Transformed dataframe
        """
        results = []

        # Process in chunks
        for start_idx in range(0, len(df), self.chunksize):
            end_idx = min(start_idx + self.chunksize, len(df))
            chunk = df.iloc[start_idx:end_idx].copy()

            result = self.transformer.transform_chunk(chunk)
            results.append(result.df)

            # Update stats
            self.stats['total_records_in'] += result.records_in
            self.stats['total_records_out'] += result.records_out
            self.stats['total_errors'] += result.error_count
            self.stats['chunks_processed'] += 1

        # Concatenate results
        if results:
            return pd.concat(results, ignore_index=True)
        return pd.DataFrame()

    def get_stats(self) -> Dict[str, int]:
        """Get transformation statistics."""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset transformation statistics."""
        self.stats = {
            'total_records_in': 0,
            'total_records_out': 0,
            'total_errors': 0,
            'chunks_processed': 0,
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def transform_event_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a single GitHub event record.

    Args:
        record: Single event record with nested structure

    Returns:
        Flattened event record
    """
    transformer = GitHubEventTransformer()

    # Convert to dataframe for consistent processing
    df = pd.DataFrame([record])
    result = transformer.transform_chunk(df)

    if not result.df.empty:
        return result.df.iloc[0].to_dict()
    return {}
