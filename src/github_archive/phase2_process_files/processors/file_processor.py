"""
File processor for GitHub Archive Phase 2 processing.

Main processing logic that validates, transforms, and writes files.
Uses Pandas with chunked processing for memory efficiency.
"""

import os
import tempfile
import time
from typing import List, Optional
from dataclasses import dataclass

import pandas as pd
from google.api_core import exceptions as gcp_exceptions

from validators.file_validator import validate_file, should_split_file
from validators.validator import validate_chunk
from processors.transformer import GitHubEventTransformer
from processors.file_splitter import mark_chunk_processed
from writers.ndjson_writer import GCSNDJSONWriter, create_output_path
from utils.gcs_client import GCSClient
from utils.logger import get_logger


# =============================================================================
# PROCESSING RESULT
# =============================================================================
@dataclass
class FileProcessingResult:
    """Result of processing a single file."""
    success: bool
    input_file: str
    output_file: Optional[str]
    output_files: List[str]  # Multiple output files when streaming chunks
    records_in: int
    records_out: int
    errors: int
    warnings: int
    duration_seconds: float
    error_message: Optional[str] = None

    @property
    def output_count(self) -> int:
        """Number of output files created."""
        return len(self.output_files) if self.output_files else 0


# =============================================================================
# FILE PROCESSOR
# =============================================================================
class GitHubArchiveFileProcessor:
    """
    Processes GitHub Archive files from landing to staging.

    Workflow:
    1. Validate file (name, size, format)
    2. Read with Pandas (chunked)
    3. Validate dtypes and values
    4. Transform (flatten schema)
    5. Write to staging (NDJSON + gzip)
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        landing_bucket: Optional[str] = None,
        staging_bucket: Optional[str] = None,
        chunksize: int = 100_000,
        file_size_threshold_mb: int = 500,
        logger=None
    ):
        """
        Initialize the file processor.

        Args:
            project_id: GCP project ID
            landing_bucket: Landing bucket name
            staging_bucket: Staging bucket name
            chunksize: Number of records per chunk for processing
            file_size_threshold_mb: File size threshold for splitting
            logger: Logger instance
        """
        self.project_id = project_id or os.getenv('PROJECT_ID')
        self.landing_bucket = landing_bucket or os.getenv('LANDING_BUCKET')
        self.staging_bucket = staging_bucket or os.getenv('STAGING_BUCKET')
        self.chunksize = chunksize
        self.file_size_threshold_mb = file_size_threshold_mb

        # Initialize components
        self.logger = logger or get_logger('file-processor')
        self.transformer = GitHubEventTransformer()
        self.gcs_client = GCSClient(project_id=self.project_id)

    def process_file(
        self,
        input_gcs_path: str,
        output_gcs_path: Optional[str] = None
    ) -> FileProcessingResult:
        """
        Process a GitHub Archive file.

        Args:
            input_gcs_path: Input GCS path (gs://landing-bucket/raw/file.json.gz)
            output_gcs_path: Output GCS path (auto-generated if not provided)

        Returns:
            FileProcessingResult with processing statistics
        """
        start_time = time.time()

        # Extract file name from path
        from utils.gcs_client import GCSPath
        input_path = GCSPath.parse(input_gcs_path)
        file_name = input_path.get_filename()

        # Get file metadata
        try:
            metadata = self.gcs_client.get_file_metadata(input_gcs_path)
        except (gcp_exceptions.Forbidden, gcp_exceptions.NotFound) as e:
            self.logger.error(f"Failed to get file metadata for {file_name}: {e}")
            return FileProcessingResult(
                success=False,
                input_file=input_gcs_path,
                output_file=None,
                output_files=[],
                records_in=0,
                records_out=0,
                errors=1,
                warnings=0,
                duration_seconds=time.time() - start_time,
                error_message=str(e)
            )

        # Validate file (name format and size)
        validation_result = validate_file(file_name, metadata.size)
        if not validation_result.is_valid:
            error_msg = '; '.join(validation_result.errors)
            self.logger.error(f"File validation failed for {file_name}: {error_msg}")
            return FileProcessingResult(
                success=False,
                input_file=input_gcs_path,
                output_file=None,
                output_files=[],
                records_in=0,
                records_out=0,
                errors=len(validation_result.errors),
                warnings=len(validation_result.warnings),
                duration_seconds=time.time() - start_time,
                error_message=error_msg
            )

        # Check if file should be split
        if should_split_file(metadata.size, self.file_size_threshold_mb):
            self.logger.info(f"File {file_name} ({round(metadata.size_mb, 2)}MB) exceeds threshold ({self.file_size_threshold_mb}MB), requires splitting")
            # In Phase 2, large files should be handled by the file splitter job
            # Return result indicating splitting is needed
            return FileProcessingResult(
                success=False,
                input_file=input_gcs_path,
                output_file=None,
                output_files=[],
                records_in=0,
                records_out=0,
                errors=0,
                warnings=0,
                duration_seconds=time.time() - start_time,
                error_message='FILE_SPLIT_REQUIRED'
            )

        # Generate output path if not provided
        if output_gcs_path is None:
            date_str = file_name.replace('.json.gz', '')
            output_gcs_path = create_output_path(
                f"gs://{self.staging_bucket}/processed",
                date_str,
                compress=True
            )

        # Log start
        self.logger.info(f"Processing file: {file_name} ({metadata.size} bytes)")

        # Process the file
        try:
            result = self._process_with_pandas(input_gcs_path, output_gcs_path, file_name)

            # Log completion
            self.logger.info(f"Completed {file_name}: {result.records_in} in, {result.records_out} out, {result.errors} errors, {result.duration_seconds:.1f}s")

            return result

        except gcp_exceptions.Forbidden as e:
            # This provides a much clearer error message for permission issues
            error_message = f"Permission Denied during processing. Check IAM roles and bucket policies (e.g., Retention Policy). Details: {e.message}"
            self.logger.error(f"{file_name}: {error_message}")
            return FileProcessingResult(
                success=False, input_file=input_gcs_path, output_file=None, output_files=[],
                records_in=0, records_out=0, errors=1, warnings=0,
                duration_seconds=time.time() - start_time,
                error_message=error_message
            )

        except Exception as e:
            self.logger.error(f"{file_name}: An unexpected error occurred: {e}")
            return FileProcessingResult(
                success=False,
                input_file=input_gcs_path,
                output_file=None,
                output_files=[],
                records_in=0,
                records_out=0,
                errors=1,
                warnings=0,
                duration_seconds=time.time() - start_time,
                error_message=str(e)
            )

    def _process_with_pandas(
        self,
        input_gcs_path: str,
        output_gcs_path: str,
        file_name: str
    ) -> FileProcessingResult:
        """
        Process file using Pandas with chunked reading and streaming writes.

        Each chunk is processed and written immediately to GCS, avoiding memory accumulation.

        Args:
            input_gcs_path: Input GCS path
            output_gcs_path: Output GCS path (base path for chunks)
            file_name: File name for logging

        Returns:
            FileProcessingResult with multiple output files
        """
        start_time = time.time()
        total_records_in = 0
        total_records_out = 0
        total_errors = 0
        total_warnings = 0

        # Download to temp file (use .json.gz suffix so decompress logic works)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json.gz') as tmp:
            tmp_path = tmp.name

        try:
            # Download and decompress from GCS
            tmp_path, _ = self.gcs_client.read_file_to_local(input_gcs_path, tmp_path, decompress=True)

            # Extract date/hour from filename for output naming
            date_str = file_name.replace('.json.gz', '')
            date_prefix = date_str  # e.g., "2026-03-06-12"

            # Initialize GCS writer for streaming uploads
            writer = GCSNDJSONWriter(
                compress=True,
                bucket_name=self.staging_bucket,
                project_id=self.project_id
            )

            # Track output files
            output_files = []
            chunks_processed = 0

            # Process chunks sequentially
            for chunk_df in pd.read_json(tmp_path, lines=True, chunksize=self.chunksize):
                chunks_processed += 1
                records_in_chunk = len(chunk_df)
                total_records_in += records_in_chunk

                # Validate (dtypes + values in single pass)
                val_result = validate_chunk(chunk_df)
                total_errors += len(val_result.errors)
                total_warnings += len(val_result.warnings)

                working_df = val_result.valid_df if val_result.valid_df is not None else chunk_df

                # Transform (flatten schema)
                transform_result = self.transformer.transform_chunk(working_df)
                total_records_out += transform_result.records_out
                total_errors += transform_result.error_count

                # Write this chunk immediately to GCS
                if not transform_result.df.empty:
                    # Create chunk-specific output path
                    if chunks_processed == 1:
                        # First chunk - use original filename
                        blob_name = f"processed/{date_prefix}.ndjson.gz"
                    else:
                        # Subsequent chunks - add chunk number
                        blob_name = f"processed/{date_prefix}-chunk-{chunks_processed:03d}.ndjson.gz"

                    write_result = writer.write_dataframe_to_gcs(
                        transform_result.df,
                        blob_name
                    )

                    if write_result.output_path:
                        output_files.append(write_result.output_path)

                # Log progress
                self.logger.info(f"Chunk {chunks_processed} processed: {records_in_chunk} records")

        finally:
            # Clean up temp file
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        duration = time.time() - start_time

        # Determine success
        success = (
            total_records_out > 0 and
            (total_errors == 0 or total_errors / total_records_in < 0.1)
        )

        # If this was a chunk file from a split operation, mark it as processed
        if success and '/chunks/' in input_gcs_path:
            try:
                mark_result = mark_chunk_processed(
                    project_id=self.project_id,
                    landing_bucket=self.landing_bucket,
                    chunk_file=input_gcs_path,
                    logger=self.logger
                )
                self.logger.info(f"Chunk marked as processed: {input_gcs_path}")
            except Exception as mark_err:
                self.logger.warning(f"Failed to mark chunk as processed: {input_gcs_path}: {mark_err}")

        # Return result with multiple output files
        return FileProcessingResult(
            success=success,
            input_file=input_gcs_path,
            output_file=output_files[0] if output_files else None,
            output_files=output_files,
            records_in=total_records_in,
            records_out=total_records_out,
            errors=total_errors,
            warnings=total_warnings,
            duration_seconds=duration
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def create_processor(
    project_id: Optional[str] = None,
    landing_bucket: Optional[str] = None,
    staging_bucket: Optional[str] = None,
    chunksize: int = 100_000
) -> GitHubArchiveFileProcessor:
    """
    Create a configured file processor.

    Args:
        project_id: GCP project ID
        landing_bucket: Landing bucket name
        staging_bucket: Staging bucket name
        chunksize: Number of records per chunk

    Returns:
        Configured GitHubArchiveFileProcessor
    """
    return GitHubArchiveFileProcessor(
        project_id=project_id,
        landing_bucket=landing_bucket,
        staging_bucket=staging_bucket,
        chunksize=chunksize
    )
