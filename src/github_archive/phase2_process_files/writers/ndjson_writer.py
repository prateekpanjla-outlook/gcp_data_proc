"""
NDJSON writer for GitHub Archive staging output.

Writes processed events as newline-delimited JSON with optional gzip compression.
"""

import json
import gzip
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, BinaryIO, TextIO
from dataclasses import dataclass
import os

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


# =============================================================================
# WRITE RESULT
# =============================================================================
@dataclass
class WriteResult:
    """Result of a write operation."""
    bytes_written: int
    records_written: int
    output_path: str
    compressed: bool


# =============================================================================
# NDJSON WRITER
# =============================================================================
class NDJSONWriter:
    """
    Writes dataframes or records in NDJSON format.

    Output format: One JSON object per line, optionally gzip compressed.
    """

    def __init__(self, compress: bool = True):
        """
        Initialize the NDJSON writer.

        Args:
            compress: Whether to gzip compress the output
        """
        self.compress = compress

    def write_dataframe(
        self,
        df: 'pd.DataFrame',
        output_path: str,
        orient: str = 'records'
    ) -> WriteResult:
        """
        Write a Pandas dataframe to NDJSON format.

        Args:
            df: Input dataframe
            output_path: Output file path
            orient: JSON orientation (records = one row per line)

        Returns:
            WriteResult with statistics
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("Pandas is required for write_dataframe")

        records_written = 0

        # Use gzip if compression enabled
        if self.compress:
            open_func = gzip.open
            mode = 'wt'
            suffix = '.gz'
        else:
            open_func = open
            mode = 'w'
            suffix = ''

        # Ensure correct extension
        final_path = output_path
        if self.compress and not final_path.endswith('.gz'):
            final_path = final_path + suffix

        with open_func(final_path, mode, encoding='utf-8') as f:
            for record in df.to_dict(orient=orient):
                # Write as JSON on one line
                json_str = json.dumps(record, default=self._json_serializer)
                f.write(json_str + '\n')
                records_written += 1

        # Get file size
        bytes_written = os.path.getsize(final_path)

        return WriteResult(
            bytes_written=bytes_written,
            records_written=records_written,
            output_path=final_path,
            compressed=self.compress
        )

    def write_records(
        self,
        records: List[Dict[str, Any]],
        output_path: str
    ) -> WriteResult:
        """
        Write a list of records to NDJSON format.

        Args:
            records: List of dictionaries to write
            output_path: Output file path

        Returns:
            WriteResult with statistics
        """
        records_written = 0

        # Use gzip if compression enabled
        if self.compress:
            open_func = gzip.open
            mode = 'wt'
            suffix = '.gz'
        else:
            open_func = open
            mode = 'w'
            suffix = ''

        # Ensure correct extension
        final_path = output_path
        if self.compress and not final_path.endswith('.gz'):
            final_path = final_path + suffix

        with open_func(final_path, mode, encoding='utf-8') as f:
            for record in records:
                # Write as JSON on one line
                json_str = json.dumps(record, default=self._json_serializer)
                f.write(json_str + '\n')
                records_written += 1

        # Get file size
        bytes_written = os.path.getsize(final_path)

        return WriteResult(
            bytes_written=bytes_written,
            records_written=records_written,
            output_path=final_path,
            compressed=self.compress
        )

    def write_to_fileobj(
        self,
        df: 'pd.DataFrame',
        fileobj: Union[BinaryIO, TextIO],
        close: bool = False
    ) -> WriteResult:
        """
        Write a dataframe to a file object.

        Args:
            df: Input dataframe
            fileobj: File object to write to
            close: Whether to close the file object after writing

        Returns:
            WriteResult with statistics (output_path will be None)
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("Pandas is required for write_to_fileobj")

        records_written = 0

        # Determine if text or binary mode
        if isinstance(fileobj, (gzip.GzipFile,)) or 'b' in getattr(fileobj, 'mode', ''):
            # Binary mode - need to wrap with TextIOWrapper if gzip
            if isinstance(fileobj, gzip.GzipFile):
                import io
                text_wrapper = io.TextIOWrapper(fileobj, encoding='utf-8')
                write_file = text_wrapper
            else:
                write_file = fileobj
        else:
            write_file = fileobj

        try:
            for record in df.to_dict(orient='records'):
                json_str = json.dumps(record, default=self._json_serializer)
                write_file.write(json_str + '\n')
                records_written += 1

            # Flush to ensure data is written
            write_file.flush()

        finally:
            if close:
                fileobj.close()

        return WriteResult(
            bytes_written=0,  # Cannot determine size without seeking
            records_written=records_written,
            output_path=None,
            compressed=self.compress
        )

    def write_chunk_to_temp(
        self,
        df: 'pd.DataFrame',
        prefix: str = 'chunk'
    ) -> tuple[str, WriteResult]:
        """
        Write a chunk to a temporary file.

        Args:
            df: Input dataframe
            prefix: Prefix for temp file name

        Returns:
            Tuple of (temp_file_path, WriteResult)
        """
        # Create temp file with appropriate extension
        suffix = '.ndjson.gz' if self.compress else '.ndjson'

        with tempfile.NamedTemporaryFile(
            mode='wb' if self.compress else 'w',
            prefix=prefix,
            suffix=suffix,
            delete=False
        ) as tmp:
            tmp_path = tmp.name

        # Write to temp file
        result = self.write_dataframe(df, tmp_path)

        return tmp_path, result

    def _json_serializer(self, obj: Any) -> Any:
        """
        Custom JSON serializer for non-serializable objects.

        Handles pandas types and other special cases.
        """
        # Handle pandas NA values
        if PANDAS_AVAILABLE:
            if pd.isna(obj):
                return None
            if isinstance(obj, pd.Int64Dtype):
                return int(obj)
            if isinstance(obj, pd.StringDtype):
                return str(obj)

        # Fallback to string representation
        return str(obj)


# =============================================================================
# GCS WRITER (helper for writing to Google Cloud Storage)
# =============================================================================
class GCSNDJSONWriter(NDJSONWriter):
    """
    Writes NDJSON files directly to Google Cloud Storage.

    Uses streaming upload to avoid local file storage.
    """

    def __init__(
        self,
        compress: bool = True,
        bucket_name: Optional[str] = None,
        project_id: Optional[str] = None
    ):
        """
        Initialize the GCS NDJSON writer.

        Args:
            compress: Whether to gzip compress the output
            bucket_name: Default GCS bucket name
            project_id: GCP project ID for authentication
        """
        super().__init__(compress=compress)
        self.bucket_name = bucket_name
        self.project_id = project_id or os.getenv('PROJECT_ID')

    def write_dataframe_to_gcs(
        self,
        df: 'pd.DataFrame',
        blob_name: str,
        bucket_name: Optional[str] = None,
        chunk_size: int = 10 * 1024 * 1024  # 10MB chunks
    ) -> WriteResult:
        """
        Write a dataframe to GCS as NDJSON.

        Args:
            df: Input dataframe
            blob_name: GCS blob name (e.g., 'processed/2026-03-05-12.ndjson.gz')
            bucket_name: GCS bucket name (uses default if not provided)
            chunk_size: Upload chunk size in bytes

        Returns:
            WriteResult with statistics

        Raises:
            ImportError: If google-cloud-storage is not installed
        """
        try:
            from google.cloud import storage
            from google.cloud.storage import Blob
        except ImportError:
            raise ImportError(
                "google-cloud-storage is required for GCS writing. "
                "Install with: pip install google-cloud-storage"
            )

        bucket = bucket_name or self.bucket_name
        if not bucket:
            raise ValueError("bucket_name must be provided")

        # Determine blob name with compression suffix
        blob_path = blob_name
        if self.compress and not blob_path.endswith('.gz'):
            blob_path = blob_path + '.gz'

        # Create client and blob with proper authentication
        client = storage.Client(project=self.project_id)
        blob = Blob(blob_path, client.bucket(bucket))

        records_written = 0
        bytes_written = 0

        # Stream upload
        with blob.open('wb', chunk_size=chunk_size) as f:
            # Wrap in gzip writer if compressing
            if self.compress:
                gzip_file = gzip.GzipFile(fileobj=f, mode='wb')
            else:
                gzip_file = f

            try:
                for record in df.to_dict(orient='records'):
                    # Write as JSON line
                    json_str = json.dumps(
                        record,
                        default=self._json_serializer,
                        ensure_ascii=False
                    )
                    line = (json_str + '\n').encode('utf-8')
                    gzip_file.write(line)
                    records_written += 1
            finally:
                if self.compress:
                    gzip_file.close()

        # Get blob size (non-critical, handle gracefully)
        try:
            blob.reload()
            bytes_written = blob.size
        except Exception as e:
            # Log but don't fail - upload was successful
            import logging
            logging.getLogger(__name__).warning(f"Could not get blob size after upload: {e}")
            bytes_written = -1  # Unknown size

        return WriteResult(
            bytes_written=bytes_written,
            records_written=records_written,
            output_path=f"gs://{bucket}/{blob_path}",
            compressed=self.compress
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def create_output_path(
    base_path: str,
    date_str: str,
    hour: Optional[int] = None,
    chunk_num: Optional[int] = None,
    compress: bool = True
) -> str:
    """
    Create an output file path for processed data.

    Args:
        base_path: Base GCS or local path (e.g., 'gs://bucket/processed')
        date_str: Date string (YYYY-MM-DD)
        hour: Hour value (0-23), optional
        chunk_num: Chunk number, optional
        compress: Whether output will be compressed

    Returns:
        Full output path
    """
    # Build filename (hour is NOT zero-padded to match GitHub Archive format)
    if hour is not None:
        filename = f"{date_str}-{hour}"
    else:
        filename = date_str

    if chunk_num is not None:
        filename = f"{filename}-chunk-{chunk_num:03d}"

    # Add extension
    if compress:
        filename = filename + ".ndjson.gz"
    else:
        filename = filename + ".ndjson"

    # Combine with base path
    return f"{base_path}/{filename}"


def merge_temp_files(
    temp_files: List[str],
    output_path: str,
    compress: bool = True
) -> WriteResult:
    """
    Merge multiple temporary files into a single output file.

    Args:
        temp_files: List of temporary file paths
        output_path: Output file path
        compress: Whether to compress the output

    Returns:
        WriteResult with statistics
    """
    records_written = 0

    # Use gzip if compression enabled
    if compress:
        open_func = gzip.open
        mode = 'wt'
        suffix = '.gz'
    else:
        open_func = open
        mode = 'w'
        suffix = ''

    # Ensure correct extension
    final_path = output_path
    if compress and not final_path.endswith('.gz'):
        final_path = final_path + suffix

    with open_func(final_path, mode, encoding='utf-8') as out_f:
        for temp_file in temp_files:
            # Determine how to open the temp file
            if temp_file.endswith('.gz'):
                open_mode = 'rt'  # Text mode for gzip
            else:
                open_mode = 'r'

            with gzip.open(temp_file, open_mode) if temp_file.endswith('.gz') else open(temp_file, 'r') as in_f:
                for line in in_f:
                    if line.strip():  # Skip empty lines
                        out_f.write(line)
                        records_written += 1

    # Get file size
    bytes_written = os.path.getsize(final_path)

    # Clean up temp files
    for temp_file in temp_files:
        try:
            os.remove(temp_file)
        except OSError:
            pass

    return WriteResult(
        bytes_written=bytes_written,
        records_written=records_written,
        output_path=final_path,
        compressed=compress
    )
