"""
File splitter for GitHub Archive Phase 2 processing.

Splits large files (≥500MB) into smaller chunks for parallel processing.
Each chunk is written to the landing/chunks/ directory, triggering Eventarc events.
"""

import os
import gzip
import tempfile
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from urllib.parse import quote

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from utils.gcs_client import GCSClient, GCSPath
from utils.logger import Phase2Logger
from validators.file_validator import FILE_NAME_PATTERN


# =============================================================================
# SPLIT RESULT
# =============================================================================
@dataclass
class FileSplitResult:
    """Result of file splitting operation."""
    success: bool
    input_file: str
    chunk_count: int
    total_records: int
    output_files: List[str]
    bytes_processed: int
    duration_seconds: float
    error_message: Optional[str] = None


# =============================================================================
# FILE SPLITTER
# =============================================================================
class GitHubArchiveFileSplitter:
    """
    Splits large GitHub Archive files into smaller chunks.

    Process:
    1. Download large file from landing/raw/
    2. Stream read line by line
    3. Every N lines, write a chunk to landing/chunks/
    4. Each chunk triggers Eventarc for parallel processing
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        landing_bucket: Optional[str] = None,
        chunk_lines: int = 10_000,
        target_chunk_size_mb: int = 50,
        logger: Optional[Phase2Logger] = None
    ):
        """
        Initialize the file splitter.

        Args:
            project_id: GCP project ID
            landing_bucket: Landing bucket name
            chunk_lines: Number of lines per chunk (default: 10,000)
            target_chunk_size_mb: Target chunk size in MB (approximate)
            logger: Logger instance
        """
        self.project_id = project_id or os.getenv('PROJECT_ID')
        self.landing_bucket = landing_bucket or os.getenv('LANDING_BUCKET')
        self.chunk_lines = chunk_lines
        self.target_chunk_size_mb = target_chunk_size_mb

        self.logger = logger or Phase2Logger(component='file-splitter', project_id=self.project_id)
        self.gcs_client = GCSClient(project_id=self.project_id)

    def split_file(
        self,
        input_gcs_path: str,
        output_prefix: Optional[str] = None
    ) -> FileSplitResult:
        """
        Split a large file into chunks.

        Args:
            input_gcs_path: Input GCS path (gs://landing/raw/file.json.gz)
            output_prefix: Prefix for output files (auto-generated if not provided)

        Returns:
            FileSplitResult with chunk information
        """
        start_time = time.time()

        # Parse input path
        input_path = GCSPath.parse(input_gcs_path)
        file_name = input_path.get_filename()

        # Extract date prefix for output naming
        date_str = file_name.replace('.json.gz', '')
        if output_prefix is None:
            output_prefix = date_str

        self.logger.info(
            f"Starting file split: {file_name}",
            input_file=input_gcs_path,
            chunk_lines=self.chunk_lines
        )

        # Download to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json.gz') as tmp:
            tmp_path = tmp.name

        try:
            # Download from GCS
            tmp_path, _ = self.gcs_client.read_file_to_local(input_gcs_path, tmp_path, decompress=True)

            # Get file size
            file_size = os.path.getsize(tmp_path)

            # Split and upload chunks
            result = self._split_and_upload_chunks(tmp_path, file_name, output_prefix, file_size)

        except Exception as e:
            self.logger.log_file_error(file_name, f"Split failed: {e}")
            return FileSplitResult(
                success=False,
                input_file=input_gcs_path,
                chunk_count=0,
                total_records=0,
                output_files=[],
                bytes_processed=0,
                duration_seconds=time.time() - start_time,
                error_message=str(e)
            )

        finally:
            # Clean up temp file
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        duration = time.time() - start_time

        # Log completion
        self.logger.info(
            f"Split complete: {result.chunk_count} chunks",
            input_file=input_gcs_path,
            chunk_count=result.chunk_count,
            total_records=result.total_records,
            duration_seconds=round(duration, 2)
        )

        return result

    def _split_and_upload_chunks(
        self,
        local_path: str,
        file_name: str,
        output_prefix: str,
        file_size: int
    ) -> FileSplitResult:
        """
        Split local file into chunks and upload to GCS.

        Args:
            local_path: Local file path
            file_name: Original filename
            output_prefix: Prefix for output chunk names
            file_size: Size of the input file

        Returns:
            FileSplitResult
        """
        output_files = []
        chunk_num = 0
        total_records = 0
        bytes_processed = 0

        # Read and split
        with open(local_path, 'r', encoding='utf-8') as f:
            chunk_buffer = []
            current_size = 0
            line_count = 0

            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    # Validate JSON
                    json.loads(line)
                    chunk_buffer.append(line)
                    line_count += 1
                    current_size += len(line.encode('utf-8'))

                    # Check if we should start a new chunk
                    should_split = (
                        line_count >= self.chunk_lines or
                        current_size >= (self.target_chunk_size_mb * 1024 * 1024)
                    )

                    if should_split and chunk_buffer:
                        # Write this chunk
                        chunk_num += 1
                        chunk_path = self._write_chunk(
                            chunk_buffer,
                            output_prefix,
                            chunk_num,
                            len(chunk_buffer)
                        )
                        output_files.append(chunk_path)
                        total_records += len(chunk_buffer)
                        bytes_processed += current_size

                        # Reset buffer
                        chunk_buffer = []
                        current_size = 0
                        line_count = 0

                except json.JSONDecodeError:
                    # Skip invalid lines
                    self.logger.warning(f"Skipping invalid JSON line in {file_name}")
                    continue

            # Write final chunk
            if chunk_buffer:
                chunk_num += 1
                chunk_path = self._write_chunk(
                    chunk_buffer,
                    output_prefix,
                    chunk_num,
                    len(chunk_buffer)
                )
                output_files.append(chunk_path)
                total_records += len(chunk_buffer)
                bytes_processed += current_size

        return FileSplitResult(
            success=True,
            input_file=file_name,
            chunk_count=chunk_num,
            total_records=total_records,
            output_files=output_files,
            bytes_processed=bytes_processed,
            duration_seconds=0  # Set by caller
        )

    def _write_chunk(
        self,
        lines: List[str],
        prefix: str,
        chunk_num: int,
        line_count: int
    ) -> str:
        """
        Write a chunk to GCS.

        Args:
            lines: List of JSON lines
            prefix: Output prefix (e.g., "2026-03-06-12")
            chunk_num: Chunk number
            line_count: Number of lines in chunk

        Returns:
            GCS path of uploaded chunk
        """
        # Generate chunk filename
        # Format: {prefix}-chunk-{num:03d}-of-{total:03d}-{count}.json.gz
        # We don't know total yet, so use a simpler format
        chunk_filename = f"{prefix}-chunk-{chunk_num:03d}.json.gz"

        # GCS path: gs://landing-bucket/github-archive/chunks/chunk_filename
        blob_name = f"github-archive/chunks/{chunk_filename}"
        gcs_path = f"gs://{self.landing_bucket}/{blob_name}"

        # Upload as gzipped NDJSON
        try:
            from google.cloud import storage

            client = storage.Client(project=self.project_id)
            bucket = client.bucket(self.landing_bucket)
            blob = bucket.blob(blob_name)

            # Write content
            with blob.open('wb') as f:
                with gzip.GzipFile(fileobj=f, mode='wb') as gzip_file:
                    for line in lines:
                        gzip_file.write((line + '\n').encode('utf-8'))

            self.logger.debug(
                f"Uploaded chunk {chunk_num}: {chunk_filename}",
                lines=line_count,
                size_bytes=blob.size
            )

            return gcs_path

        except Exception as e:
            self.logger.error(f"Failed to upload chunk {chunk_num}: {e}")
            raise


# =============================================================================
# MAIN ENTRY POINT (for Cloud Run Job)
# =============================================================================
def run_splitter_job(
    input_file: str,
    project_id: Optional[str] = None,
    landing_bucket: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run the file splitter as a Cloud Run Job.

    This is the entry point when the splitter job is invoked.

    Environment variables:
    - PROJECT_ID: GCP project ID
    - LANDING_BUCKET: Landing bucket name
    - CHUNK_SIZE_LINES: Lines per chunk (default: 10000)

    Args:
        input_file: GCS path to input file
        project_id: GCP project ID
        landing_bucket: Landing bucket name

    Returns:
        Dictionary with job result
    """
    project_id = project_id or os.getenv('PROJECT_ID')
    landing_bucket = landing_bucket or os.getenv('LANDING_BUCKET')
    chunk_lines = int(os.getenv('CHUNK_SIZE_LINES', '10000'))

    logger = Phase2Logger(component='file-splitter', project_id=project_id)

    logger.info(
        "File splitter job started",
        input_file=input_file,
        project_id=project_id,
        landing_bucket=landing_bucket,
        chunk_lines=chunk_lines
    )

    splitter = GitHubArchiveFileSplitter(
        project_id=project_id,
        landing_bucket=landing_bucket,
        chunk_lines=chunk_lines,
        logger=logger
    )

    result = splitter.split_file(input_file)

    # SAFETY: Do NOT delete original file immediately after split.
    # Original file should only be deleted after ALL chunks are successfully processed.
    # This prevents data loss if chunk processing fails.
    #
    # Deletion strategy:
    # 1. Write a metadata file alongside chunks: {prefix}-chunk-metadata.json
    # 2. Metadata contains: original_file, chunk_count, created_timestamp
    # 3. After all chunks are processed, a cleanup job deletes the original
    #
    # For now, we keep the original file and log that cleanup is needed.
    if result.success and result.output_files:
        logger.info(
            f"Split complete - original file preserved for safety",
            input_file=input_file,
            chunk_count=result.chunk_count,
            note="Original file should be deleted after all chunks are processed"
        )

        # Write metadata file for cleanup job (future implementation)
        try:
            _write_split_metadata(
                project_id=project_id,
                landing_bucket=landing_bucket,
                original_file=input_file,
                output_prefix=input_file.split('/')[-1].replace('.json.gz', ''),
                chunk_count=result.chunk_count,
                output_files=result.output_files,
                logger=logger
            )
        except Exception as meta_err:
            logger.warning(f"Failed to write split metadata: {meta_err}")

    return {
        'success': result.success,
        'input_file': result.input_file,
        'chunk_count': result.chunk_count,
        'total_records': result.total_records,
        'output_files': result.output_files,
        'duration_seconds': result.duration_seconds,
        'error_message': result.error_message
    }


def _write_split_metadata(
    project_id: str,
    landing_bucket: str,
    original_file: str,
    output_prefix: str,
    chunk_count: int,
    output_files: List[str],
    logger: Phase2Logger
) -> None:
    """
    Write metadata file for tracking split files.

    This metadata file is used to:
    1. Track which files have been split
    2. Enable cleanup after all chunks are processed
    3. Support recovery from failures

    Args:
        project_id: GCP project ID
        landing_bucket: Landing bucket name
        original_file: Original file GCS path
        output_prefix: Output prefix for chunks
        chunk_count: Number of chunks created
        output_files: List of chunk GCS paths
        logger: Logger instance
    """
    from google.cloud import storage
    import json
    from datetime import datetime

    client = storage.Client(project=project_id)
    bucket = client.bucket(landing_bucket)

    # Metadata filename based on original
    # e.g., 2026-03-06-12.json.gz -> 2026-03-06-12.split-metadata.json
    metadata_filename = f"{output_prefix}.split-metadata.json"
    blob_name = f"github-archive/chunks/{metadata_filename}"

    metadata = {
        'original_file': original_file,
        'split_timestamp': datetime.utcnow().isoformat(),
        'chunk_count': chunk_count,
        'output_files': output_files,
        'chunks_processed': [],  # Will be updated as chunks are processed
        'status': 'pending_cleanup',  # pending_cleanup, cleanup_complete
        'cleanup_after': chunk_count  # Delete original after this many chunks processed
    }

    blob = bucket.blob(blob_name)
    blob.upload_from_string(
        json.dumps(metadata, indent=2),
        content_type='application/json'
    )

    logger.info(
        f"Split metadata written: {metadata_filename}",
        original_file=original_file,
        chunk_count=chunk_count
    )


def mark_chunk_processed(
    project_id: str,
    landing_bucket: str,
    chunk_file: str,
    logger: Phase2Logger
) -> Dict[str, Any]:
    """
    Mark a chunk as processed and check if original can be deleted.

    This should be called by the processor after successfully processing a chunk.

    Args:
        project_id: GCP project ID
        landing_bucket: Landing bucket name
        chunk_file: GCS path of the processed chunk
        logger: Logger instance

    Returns:
        Dictionary with status and whether cleanup is complete
    """
    from google.cloud import storage
    import json
    import re

    client = storage.Client(project=project_id)
    bucket = client.bucket(landing_bucket)

    # Extract prefix from chunk filename
    # e.g., 2026-03-06-12-chunk-001.json.gz -> 2026-03-06-12
    chunk_name = chunk_file.split('/')[-1]
    match = re.match(r'(.+)-chunk-\d+\.json\.gz', chunk_name)

    if not match:
        logger.warning(f"Could not extract metadata prefix from chunk: {chunk_name}")
        return {'status': 'error', 'message': 'Could not extract prefix'}

    output_prefix = match.group(1)
    metadata_filename = f"{output_prefix}.split-metadata.json"
    blob_name = f"github-archive/chunks/{metadata_filename}"

    try:
        blob = bucket.blob(blob_name)
        if not blob.exists():
            logger.warning(f"Split metadata not found: {metadata_filename}")
            return {'status': 'not_found', 'message': 'Metadata not found'}

        # Download and update metadata
        metadata_str = blob.download_as_text()
        metadata = json.loads(metadata_str)

        # Add this chunk to processed list
        if chunk_file not in metadata.get('chunks_processed', []):
            metadata.setdefault('chunks_processed', []).append(chunk_file)

        # Check if all chunks are processed
        all_processed = len(metadata['chunks_processed']) >= metadata['chunk_count']

        if all_processed:
            metadata['status'] = 'cleanup_complete'

            # Delete original file
            try:
                original_path = GCSPath.parse(metadata['original_file'])
                original_blob = bucket.blob(original_path.blob_name)
                if original_blob.exists():
                    original_blob.delete()
                    logger.info(
                        f"Original file deleted after all chunks processed",
                        original_file=metadata['original_file'],
                        chunks_processed=len(metadata['chunks_processed'])
                    )
            except Exception as del_err:
                logger.error(f"Failed to delete original file: {del_err}")

            # Delete the processed chunks
            for chunk_path in metadata['chunks_processed']:
                try:
                    chunk_blob_name = chunk_path.replace(f'gs://{landing_bucket}/', '')
                    chunk_blob = bucket.blob(chunk_blob_name)
                    if chunk_blob.exists():
                        chunk_blob.delete()
                except Exception as chunk_del_err:
                    logger.warning(f"Failed to delete chunk {chunk_path}: {chunk_del_err}")

        # Update metadata
        blob.upload_from_string(
            json.dumps(metadata, indent=2),
            content_type='application/json'
        )

        return {
            'status': 'updated',
            'all_processed': all_processed,
            'chunks_processed': len(metadata['chunks_processed']),
            'total_chunks': metadata['chunk_count']
        }

    except Exception as e:
        logger.error(f"Failed to update split metadata: {e}")
        return {'status': 'error', 'message': str(e)}


if __name__ == '__main__':
    # Run as a standalone script (for Cloud Run Job)
    import sys

    # Get input file from command line or environment
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = os.getenv('INPUT_FILE')

    if not input_file:
        print("Error: INPUT_FILE must be provided", file=sys.stderr)
        sys.exit(1)

    result = run_splitter_job(input_file)

    # Exit with appropriate code
    sys.exit(0 if result['success'] else 1)
