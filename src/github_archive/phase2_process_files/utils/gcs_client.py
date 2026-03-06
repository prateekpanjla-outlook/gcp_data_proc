"""
Google Cloud Storage client utilities for Phase 2 processing.

Provides functions for reading/writing files from GCS with proper error handling.
"""

import os
import gzip
import json
from typing import Dict, List, Any, Optional, Iterator, BinaryIO, TextIO
from pathlib import Path
from dataclasses import dataclass
from urllib.parse import urlparse


# =============================================================================
# GCS PATH COMPONENTS
# =============================================================================
@dataclass
class GCSPath:
    """Parsed GCS path components."""
    bucket: str
    blob_path: str
    is_gcs: bool = True

    @classmethod
    def parse(cls, path: str) -> 'GCSPath':
        """Parse a GCS path string."""
        if path.startswith('gs://'):
            # Remove gs:// prefix
            path = path[5:]
            parts = path.split('/', 1)
            bucket = parts[0]
            blob_path = parts[1] if len(parts) > 1 else ''
            return cls(bucket=bucket, blob_path=blob_path, is_gcs=True)
        else:
            # Local file path
            return cls(bucket='', blob_path=path, is_gcs=False)

    def to_string(self) -> str:
        """Convert back to GCS path string."""
        if self.is_gcs:
            return f"gs://{self.bucket}/{self.blob_path}" if self.blob_path else f"gs://{self.bucket}"
        return self.blob_path

    def get_filename(self) -> str:
        """Extract just the filename from the path."""
        if self.blob_path:
            return Path(self.blob_path).name
        return ''


# =============================================================================
# FILE METADATA
# =============================================================================
@dataclass
class FileMetadata:
    """Metadata about a file in GCS."""
    name: str
    size: int
    content_type: str
    updated: str
    md5_hash: str
    generation: str

    @property
    def size_mb(self) -> float:
        return self.size / (1024 * 1024)


# =============================================================================
# GCS CLIENT
# =============================================================================
class GCSClient:
    """
    Wrapper around Google Cloud Storage client with Phase 2 specific utilities.
    """

    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize the GCS client.

        Args:
            project_id: GCP project ID (uses default if not provided)
        """
        self.project_id = project_id or os.getenv('PROJECT_ID')
        self._client = None

    @property
    def client(self):
        """Lazy-load the GCS client."""
        if self._client is None:
            try:
                from google.cloud import storage
                if self.project_id:
                    self._client = storage.Client(project=self.project_id)
                else:
                    self._client = storage.Client()
            except ImportError:
                raise ImportError(
                    "google-cloud-storage is required. "
                    "Install with: pip install google-cloud-storage"
                )
        return self._client

    def read_file(
        self,
        gcs_path: str,
        compressed: bool = True
    ) -> Iterator[bytes]:
        """
        Read a file from GCS as an iterator of bytes.

        Args:
            gcs_path: GCS path (gs://bucket/path)
            compressed: Whether the file is gzip compressed

        Yields:
            Chunks of bytes from the file
        """
        path = GCSPath.parse(gcs_path)
        bucket = self.client.bucket(path.bucket)
        blob = bucket.blob(path.blob_path)

        with blob.open('rb') as f:
            if compressed:
                with gzip.GzipFile(fileobj=f, mode='rb') as gzip_f:
                    while chunk := gzip_f.read(1024 * 1024):  # 1MB chunks
                        yield chunk
            else:
                while chunk := f.read(1024 * 1024):
                    yield chunk

    def read_file_to_local(
        self,
        gcs_path: str,
        local_path: str,
        decompress: bool = True
    ) -> FileMetadata:
        """
        Download a file from GCS to local storage.

        Args:
            gcs_path: GCS path (gs://bucket/path)
            local_path: Local file path
            decompress: Whether to decompress if gzip

        Returns:
            FileMetadata with information about the downloaded file
        """
        path = GCSPath.parse(gcs_path)
        bucket = self.client.bucket(path.bucket)
        blob = bucket.blob(path.blob_path)

        # Get metadata
        blob.reload()

        metadata = FileMetadata(
            name=gcs_path,
            size=blob.size,
            content_type=blob.content_type or '',
            updated=str(blob.updated) if blob.updated else '',
            md5_hash=blob.md5_hash or '',
            generation=str(blob.generation) if blob.generation else ''
        )

        # Download
        blob.download_to_filename(local_path)

        # Decompress if needed
        if decompress and local_path.endswith('.gz'):
            # Decompress to a new file without .gz
            decompressed_path = local_path[:-3]
            with gzip.open(local_path, 'rb') as f_in:
                with open(decompressed_path, 'wb') as f_out:
                    f_out.write(f_in.read())
            # Remove compressed file
            os.remove(local_path)
            local_path = decompressed_path

        return metadata

    def write_file(
        self,
        local_path: str,
        gcs_path: str,
        compress: bool = True
    ) -> FileMetadata:
        """
        Upload a file to GCS.

        Args:
            local_path: Local file path
            gcs_path: GCS path (gs://bucket/path)
            compress: Whether to compress before uploading

        Returns:
            FileMetadata with information about the uploaded file
        """
        path = GCSPath.parse(gcs_path)
        bucket = self.client.bucket(path.bucket)
        blob = bucket.blob(path.blob_path)

        # Upload
        if compress and not local_path.endswith('.gz'):
            # Compress during upload
            blob.upload_from_filename(local_path, content_type='application/gzip')
        else:
            blob.upload_from_filename(local_path)

        # Reload to get metadata
        blob.reload()

        return FileMetadata(
            name=gcs_path,
            size=blob.size,
            content_type=blob.content_type or '',
            updated=str(blob.updated) if blob.updated else '',
            md5_hash=blob.md5_hash or '',
            generation=str(blob.generation) if blob.generation else ''
        )

    def get_file_metadata(self, gcs_path: str) -> FileMetadata:
        """
        Get metadata for a file in GCS.

        Args:
            gcs_path: GCS path (gs://bucket/path)

        Returns:
            FileMetadata with information about the file
        """
        path = GCSPath.parse(gcs_path)
        bucket = self.client.bucket(path.bucket)
        blob = bucket.blob(path.blob_path)
        blob.reload()

        return FileMetadata(
            name=gcs_path,
            size=blob.size,
            content_type=blob.content_type or '',
            updated=str(blob.updated) if blob.updated else '',
            md5_hash=blob.md5_hash or '',
            generation=str(blob.generation) if blob.generation else ''
        )

    def list_files(
        self,
        gcs_prefix: str,
        pattern: Optional[str] = None
    ) -> List[FileMetadata]:
        """
        List files in a GCS bucket with optional pattern matching.

        Args:
            gcs_prefix: GCS prefix (gs://bucket/prefix/)
            pattern: Optional glob pattern to match

        Returns:
            List of FileMetadata objects
        """
        path = GCSPath.parse(gcs_prefix)
        bucket = self.client.bucket(path.bucket)

        files = []
        for blob in bucket.list_blobs(prefix=path.blob_path):
            if pattern is None or Path(blob.name).match(pattern):
                files.append(FileMetadata(
                    name=f"gs://{path.bucket}/{blob.name}",
                    size=blob.size,
                    content_type=blob.content_type or '',
                    updated=str(blob.updated) if blob.updated else '',
                    md5_hash=blob.md5_hash or '',
                    generation=str(blob.generation) if blob.generation else ''
                ))

        return files

    def file_exists(self, gcs_path: str) -> bool:
        """
        Check if a file exists in GCS.

        Args:
            gcs_path: GCS path (gs://bucket/path)

        Returns:
            True if file exists
        """
        path = GCSPath.parse(gcs_path)
        bucket = self.client.bucket(path.bucket)
        blob = bucket.blob(path.blob_path)
        return blob.exists()

    def delete_file(self, gcs_path: str) -> bool:
        """
        Delete a file from GCS.

        Args:
            gcs_path: GCS path (gs://bucket/path)

        Returns:
            True if file was deleted
        """
        path = GCSPath.parse(gcs_path)
        bucket = self.client.bucket(path.bucket)
        blob = bucket.blob(path.blob_path)

        if blob.exists():
            blob.delete()
            return True
        return False

    def move_file(self, src_path: str, dst_path: str) -> bool:
        """
        Move a file within GCS (copy then delete).

        Args:
            src_path: Source GCS path
            dst_path: Destination GCS path

        Returns:
            True if file was moved
        """
        src = GCSPath.parse(src_path)
        dst = GCSPath.parse(dst_path)

        src_bucket = self.client.bucket(src.bucket)
        src_blob = src_bucket.blob(src.blob_path)

        dst_bucket = self.client.bucket(dst.bucket)
        dst_blob = dst_bucket.blob(dst.blob_path)

        if src_blob.exists():
            # Copy to destination
            src_blob.copy_to(dst_blob)
            # Delete source
            src_blob.delete()
            return True
        return False


# =============================================================================
# READER UTILITIES
# =============================================================================
def read_json_lines_from_gcs(
    gcs_path: str,
    project_id: Optional[str] = None,
    chunksize: Optional[int] = None
) -> Iterator[Dict[str, Any]]:
    """
    Read JSON lines from a GCS file.

    Args:
        gcs_path: GCS path (gs://bucket/path)
        project_id: GCP project ID
        chunksize: If specified, yield lists of records (for Pandas)

    Yields:
        Individual JSON records (or lists if chunksize specified)
    """
    client = GCSClient(project_id)
    path = GCSPath.parse(gcs_path)
    bucket = client.client.bucket(path.bucket)
    blob = bucket.blob(path.blob_path)

    with blob.open('rb') as f:
        # Handle gzip
        if gcs_path.endswith('.gz'):
            file_obj = gzip.GzipFile(fileobj=f, mode='rb')
        else:
            file_obj = f

        # Decode text
        if hasattr(file_obj, 'read'):
            import io
            text_wrapper = io.TextIOWrapper(file_obj, encoding='utf-8')
        else:
            text_wrapper = file_obj

        chunk = []
        for line in text_wrapper:
            line = line.strip()
            if line:
                try:
                    record = json.loads(line)
                    if chunksize:
                        chunk.append(record)
                        if len(chunk) >= chunksize:
                            yield chunk
                            chunk = []
                    else:
                        yield record
                except json.JSONDecodeError:
                    # Skip invalid JSON lines
                    continue

        # Yield remaining records
        if chunk and chunksize:
            yield chunk


def read_pandas_dataframe_from_gcs(
    gcs_path: str,
    project_id: Optional[str] = None,
    chunksize: Optional[int] = None,
    lines: bool = True
):
    """
    Read a Pandas DataFrame from a GCS JSON lines file.

    Args:
        gcs_path: GCS path (gs://bucket/path)
        project_id: GCP project ID
        chunksize: Number of records per chunk (for iterator)
        lines: Whether the file is newline-delimited JSON

    Returns:
        DataFrame or TextFileReader (if chunksize specified)
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("Pandas is required for this function")

    # Download to temp file
    import tempfile
    client = GCSClient(project_id)

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Download file
        metadata = client.read_file_to_local(gcs_path, tmp_path, decompress=True)

        # Read with Pandas
        if chunksize:
            return pd.read_json(tmp_path, lines=lines, chunksize=chunksize)
        else:
            return pd.read_json(tmp_path, lines=lines)
    finally:
        # Clean up temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass
