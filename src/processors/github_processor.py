"""Pandas-based data processor optimized for large files.

Uses chunked reading with pandas to handle large JSONL files efficiently.
"""

import gzip
import json
import logging
from io import StringIO
from typing import Dict, Generator, List, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class PandasDataProcessor:
    """Process large JSONL files using pandas with chunked reading."""

    def __init__(
        self,
        chunk_size: int = 10000,
        optimize_dtypes: bool = True
    ):
        """Initialize processor.

        Args:
            chunk_size: Number of rows to process at a time
            optimize_dtypes: Whether to use optimal pandas dtypes to reduce memory
        """
        self.chunk_size = chunk_size
        self.optimize_dtypes = optimize_dtypes

    def read_jsonl_chunks(
        self,
        file_path: str,
        compressed: bool = False
    ) -> Generator[pd.DataFrame, None, None]:
        """Read JSONL file in chunks, yielding pandas DataFrames.

        This is memory-efficient for large files as it only keeps
        `chunk_size` rows in memory at a time.

        Args:
            file_path: Path to JSONL file
            compressed: Whether file is gzip compressed

        Yields:
            DataFrame with chunk_size rows
        """
        open_func = gzip.open if compressed else open
        mode = 'rt' if compressed else 'r'

        chunk = []
        line_count = 0

        with open_func(file_path, mode, encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                    chunk.append(record)
                    line_count += 1

                    # Yield chunk when full
                    if len(chunk) >= self.chunk_size:
                        yield self._chunk_to_dataframe(chunk)
                        chunk = []

                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON at line {line_num}: {e}")
                    continue

        # Yield remaining records
        if chunk:
            yield self._chunk_to_dataframe(chunk)

    def read_jsonl_chunks_from_storage(
        self,
        storage_backend,
        blob_name: str,
        compressed: bool = False
    ) -> Generator[pd.DataFrame, None, None]:
        """Read JSONL from storage backend in chunks.

        Args:
            storage_backend: Storage backend instance
            blob_name: Name/path of the blob
            compressed: Whether file is gzip compressed

        Yields:
            DataFrame with chunk_size rows
        """
        chunk = []

        for record in storage_backend.read_jsonl_file(blob_name, compressed=compressed):
            chunk.append(record)

            if len(chunk) >= self.chunk_size:
                yield self._chunk_to_dataframe(chunk)
                chunk = []

        # Yield remaining
        if chunk:
            yield self._chunk_to_dataframe(chunk)

    def _chunk_to_dataframe(self, chunk: List[Dict[str, Any]]) -> pd.DataFrame:
        """Convert list of dicts to DataFrame with optimizations."""
        df = pd.DataFrame(chunk)

        if self.optimize_dtypes:
            # Use optimal dtypes to reduce memory usage
            df = self._optimize_dtypes(df)

        return df

    def _optimize_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Optimize DataFrame dtypes for memory efficiency.

        Converts:
        - object columns with limited unique values to 'category'
        - int64 to smallest possible int type
        - float64 to float32 where possible

        Note: Skips columns with unhashable types (dicts, lists)
        """
        for col in df.columns:
            col_type = df[col].dtype

            if col_type == 'object':
                # Skip columns with unhashable types (dicts, lists)
                try:
                    # Check first value
                    first_val = df[col].dropna().iloc[0] if len(df[col]) > 0 else None
                    if isinstance(first_val, (dict, list)):
                        continue  # Skip nested structures

                    # Convert to category if low cardinality
                    num_unique = df[col].nunique()
                    num_total = len(df[col])
                    if num_unique / num_total < 0.5:  # Less than 50% unique
                        df[col] = df[col].astype('category')
                except (TypeError, ValueError, IndexError):
                    # Contains unhashable types or empty - skip
                    pass

            elif col_type == 'int64':
                # Downcast to smallest possible int type
                df[col] = pd.to_numeric(df[col], downcast='integer')

            elif col_type == 'float64':
                # Downcast to float32
                df[col] = pd.to_numeric(df[col], downcast='float')

        return df


class GitHubEventProcessor(PandasDataProcessor):
    """Process GitHub Archive events using pandas.

    Extracts and flattens nested fields from GitHub events.
    """

    # Fields to extract from nested structures
    FIELD_MAPPINGS = {
        'id': 'event_id',
        'type': 'event_type',
        'actor.id': 'actor_id',
        'actor.login': 'actor_login',
        'actor.avatar_url': 'actor_avatar_url',
        'repo.id': 'repo_id',
        'repo.name': 'repo_name',
        'repo.url': 'repo_url',
        'created_at': 'created_at',
        'public': 'public',
    }

    def __init__(
        self,
        chunk_size: int = 10000,
        extract_payload: bool = False
    ):
        """Initialize GitHub event processor.

        Args:
            chunk_size: Number of rows to process at a time
            extract_payload: Whether to extract payload fields (can be large)
        """
        super().__init__(chunk_size=chunk_size)
        self.extract_payload = extract_payload

    def process_chunk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process a chunk of GitHub events.

        Extracts and flattens nested fields using vectorized operations.

        Args:
            df: Input DataFrame with raw GitHub events

        Returns:
            Processed DataFrame with flattened columns
        """
        # Create result DataFrame with extracted fields
        result = pd.DataFrame(index=df.index)

        # Simple column copies
        if 'id' in df.columns:
            result['event_id'] = df['id'].astype(str)

        if 'type' in df.columns:
            result['event_type'] = df['type'].astype('category')

        if 'created_at' in df.columns:
            result['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')

        if 'public' in df.columns:
            result['public'] = df['public'].astype(boolean)

        # Extract nested actor fields using vectorized operations
        if 'actor' in df.columns:
            actor_df = pd.json_normalize(df['actor'].tolist())
            result['actor_login'] = actor_df.get('login', '')
            result['actor_id'] = actor_df.get('id', '').astype(str)

        # Extract nested repo fields
        if 'repo' in df.columns:
            repo_df = pd.json_normalize(df['repo'].tolist())
            result['repo_name'] = repo_df.get('name', '')
            result['repo_id'] = repo_df.get('id', '').astype(str)

        # Extract payload fields if requested
        if self.extract_payload and 'payload' in df.columns:
            # Payload structure varies by event type
            # Extract common fields safely
            payload_data = df['payload'].apply(self._extract_payload_fields)
            payload_df = pd.DataFrame(payload_data.tolist())
            result = pd.concat([result, payload_df], axis=1)

        return result

    def _extract_payload_fields(self, payload: Dict) -> Dict:
        """Extract common payload fields safely.

        Args:
            payload: Payload dictionary from GitHub event

        Returns:
            Dictionary of extracted fields
        """
        if not isinstance(payload, dict):
            return {}

        result = {}

        # Common fields across event types
        for field in ['ref', 'ref_type', 'action', 'number', 'size',
                      'distinct_size', 'push_id', 'commit_id']:
            if field in payload:
                result[f'payload_{field}'] = payload[field]

        return result

    def get_insert_rows(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Convert DataFrame to list of dicts for BigQuery insertion.

        Handles NaN values and converts types appropriately.
        - Timestamps -> ISO format strings
        - NaN/NaT -> None
        - Categories -> strings

        Args:
            df: Processed DataFrame

        Returns:
            List of row dictionaries
        """
        # Make a copy to avoid modifying original
        df = df.copy()

        # Convert timestamps to ISO format strings (JSON serializable)
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            elif isinstance(df[col].dtype, pd.CategoricalDtype):
                df[col] = df[col].astype(str)

        # Replace NaN/NaT with None (BigQuery doesn't like NaN)
        df = df.where(pd.notnull(df), None)

        # Convert to records
        rows = df.to_dict('records')

        # Clean up each row
        cleaned_rows = []
        for row in rows:
            cleaned = {k: v for k, v in row.items() if v is not None}
            cleaned_rows.append(cleaned)

        return cleaned_rows

    def get_base_schema(self) -> List[tuple]:
        """Get base schema for GitHub events table.

        Returns:
            List of (field_name, field_type) tuples
        """
        return [
            ("event_id", "STRING"),
            ("event_type", "STRING"),
            ("actor_login", "STRING"),
            ("actor_id", "STRING"),
            ("repo_name", "STRING"),
            ("repo_id", "STRING"),
            ("created_at", "TIMESTAMP"),
            ("public", "BOOLEAN"),
        ]


# Boolean type reference for pandas
try:
    from pandas import BooleanDtype
    boolean = "boolean"
except ImportError:
    boolean = "bool"


def process_storage_to_bigquery(
    storage_backend,
    blob_name: str,
    bigquery_client,
    dataset_id: str,
    table_id: str,
    compressed: bool = True,
    chunk_size: int = 10000,
    use_bulk_load: bool = True
) -> Dict[str, Any]:
    """Process data from storage to BigQuery using pandas.

    This function supports two loading methods:

    1. Bulk Load (recommended for production):
       - Uses load_dataframe() which creates BigQuery load jobs
       - FREE loading (uses shared compute pool)
       - Best for large datasets
       - Emulator falls back to streaming (with warning)

    2. Streaming Insert:
       - Uses insert_rows() with row-by-row insertion
       - $0.05/GB streaming cost
       - Rate limited (10,000 rows/sec)
       - Best for real-time/near real-time data

    Args:
        storage_backend: Storage backend instance
        blob_name: Name of blob to read
        bigquery_client: BigQuery client instance (must support load_dataframe())
        dataset_id: Target dataset ID
        table_id: Target table ID
        compressed: Whether file is gzip compressed
        chunk_size: Processing chunk size
        use_bulk_load: If True, use bulk load (recommended). If False, use streaming.

    Returns:
        Dictionary with processing statistics
    """
    from google.cloud import bigquery as bq

    processor = GitHubEventProcessor(chunk_size=chunk_size)
    stats = {
        'total_rows': 0,
        'total_chunks': 0,
        'errors': 0,
        'loading_method': 'bulk' if use_bulk_load else 'streaming',
        'chunk_results': []
    }

    # Get schema and ensure table exists
    schema_fields = [bq.SchemaField(name, ft) for name, ft in processor.get_base_schema()]

    if not bigquery_client.table_exists(dataset_id, table_id):
        bigquery_client.create_table(
            dataset_id=dataset_id,
            table_id=table_id,
            schema=schema_fields,
            overwrite=False
        )

    # Determine write disposition for bulk load
    write_disposition = "WRITE_APPEND"

    # Process chunks
    for chunk_df in processor.read_jsonl_chunks_from_storage(storage_backend, blob_name, compressed):
        stats['total_chunks'] += 1

        # Process the chunk
        processed_df = processor.process_chunk(chunk_df)

        if use_bulk_load and hasattr(bigquery_client, 'load_dataframe'):
            # Use bulk load (recommended for production)
            load_result = bigquery_client.load_dataframe(
                dataset_id=dataset_id,
                table_id=table_id,
                dataframe=processed_df,
                schema=schema_fields,
                write_disposition=write_disposition
            )

            num_rows = load_result.get('num_rows', 0)
            errors = load_result.get('errors', [])
            stats['total_rows'] += num_rows
            stats['errors'] += len(errors)

            logger.info(
                f"Processed chunk {stats['total_chunks']}: {num_rows} rows "
                f"(method: {load_result.get('method', 'unknown')})"
            )

            stats['chunk_results'].append({
                'chunk': stats['total_chunks'],
                'method': load_result.get('method', 'unknown'),
                'rows': num_rows,
                'errors': len(errors)
            })
        else:
            # Fall back to streaming insert (legacy behavior)
            rows = processor.get_insert_rows(processed_df)
            errors = bigquery_client.insert_rows(dataset_id, table_id, rows)

            stats['total_rows'] += len(rows)
            stats['errors'] += len(errors)

            logger.info(f"Processed chunk {stats['total_chunks']}: {len(rows)} rows (streaming)")

    return stats
