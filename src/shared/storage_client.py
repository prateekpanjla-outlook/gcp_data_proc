"""Cloud Storage client wrapper with download and upload utilities."""

import gzip
import io
import json
import logging
from typing import Any, Dict, Generator, List, Optional

from google.cloud import storage
from google.api_core import exceptions as gcp_exceptions

logger = logging.getLogger(__name__)


class StorageClient:
    """Wrapper around Google Cloud Storage client with enhanced functionality."""

    def __init__(self, bucket_name: str, project_id: Optional[str] = None):
        """
        Initialize Storage client.

        Args:
            bucket_name: Name of the Cloud Storage bucket
            project_id: GCP project ID (optional)
        """
        self.bucket_name = bucket_name
        self.project_id = project_id

        try:
            self.client = storage.Client(project=project_id)
            self.bucket = self.client.bucket(bucket_name)
            logger.info(f"Storage client initialized for bucket: {bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Storage client: {e}")
            raise

    def read_jsonl_file(
        self,
        blob_name: str,
        compressed: bool = False
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Read a JSONL file from Cloud Storage.

        Args:
            blob_name: Name of the blob (file) in the bucket
            compressed: Whether the file is gzip compressed

        Yields:
            Dictionaries representing each JSON object
        """
        try:
            blob = self.bucket.blob(blob_name)
            content_bytes = blob.download_as_bytes()

            if compressed:
                content_bytes = gzip.decompress(content_bytes)

            # Parse JSONL (one JSON object per line)
            for line in content_bytes.decode('utf-8').split('\n'):
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON line: {e}")
                        continue

        except gcp_exceptions.NotFound:
            logger.error(f"Blob not found: {blob_name}")
            raise
        except Exception as e:
            logger.error(f"Error reading file {blob_name}: {e}")
            raise

    def read_json_file(
        self,
        blob_name: str,
        compressed: bool = False
    ) -> Dict[str, Any]:
        """
        Read a JSON file from Cloud Storage.

        Args:
            blob_name: Name of the blob (file) in the bucket
            compressed: Whether the file is gzip compressed

        Returns:
            Dictionary representing the JSON object
        """
        try:
            blob = self.bucket.blob(blob_name)
            content_bytes = blob.download_as_bytes()

            if compressed:
                content_bytes = gzip.decompress(content_bytes)

            return json.loads(content_bytes.decode('utf-8'))

        except gcp_exceptions.NotFound:
            logger.error(f"Blob not found: {blob_name}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {blob_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error reading file {blob_name}: {e}")
            raise

    def read_ndjson_file(
        self,
        blob_name: str,
        compressed: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Read an NDJSON (newline-delimited JSON) file from Cloud Storage.

        Args:
            blob_name: Name of the blob (file) in the bucket
            compressed: Whether the file is gzip compressed

        Returns:
            List of dictionaries representing each JSON object
        """
        return list(self.read_jsonl_file(blob_name, compressed))

    def write_json_file(
        self,
        blob_name: str,
        data: Dict[str, Any] | List[Dict[str, Any]],
        compressed: bool = False
    ) -> None:
        """
        Write a JSON file to Cloud Storage.

        Args:
            blob_name: Name of the blob (file) in the bucket
            data: Dictionary or list to write as JSON
            compressed: Whether to gzip compress the file
        """
        try:
            blob = self.bucket.blob(blob_name)
            content = json.dumps(data, ensure_ascii=False).encode('utf-8')

            if compressed:
                content = gzip.compress(content)

            blob.upload_from_string(content, content_type='application/json')
            logger.info(f"Successfully wrote {blob_name} ({len(content)} bytes)")

        except Exception as e:
            logger.error(f"Error writing file {blob_name}: {e}")
            raise

    def write_jsonl_file(
        self,
        blob_name: str,
        data: List[Dict[str, Any]],
        compressed: bool = False
    ) -> None:
        """
        Write a JSONL file to Cloud Storage.

        Args:
            blob_name: Name of the blob (file) in the bucket
            data: List of dictionaries to write as JSONL
            compressed: Whether to gzip compress the file
        """
        try:
            blob = self.bucket.blob(blob_name)
            lines = [json.dumps(item, ensure_ascii=False) for item in data]
            content = '\n'.join(lines).encode('utf-8')

            if compressed:
                content = gzip.compress(content)

            blob.upload_from_string(content, content_type='application/json')
            logger.info(f"Successfully wrote {blob_name} ({len(data)} records)")

        except Exception as e:
            logger.error(f"Error writing file {blob_name}: {e}")
            raise

    def move_file(
        self,
        source_blob: str,
        destination_blob: str,
        delete_source: bool = True
    ) -> None:
        """
        Move a file within the bucket.

        Args:
            source_blob: Source blob name
            destination_blob: Destination blob name
            delete_source: Whether to delete the source file after copying
        """
        try:
            source = self.bucket.blob(source_blob)
            destination = self.bucket.blob(destination_blob)

            # Copy to destination
            self.bucket.copy_blob(source, self.bucket, destination_blob)

            if delete_source:
                source.delete()

            logger.info(f"Moved {source_blob} to {destination_blob}")

        except Exception as e:
            logger.error(f"Error moving file: {e}")
            raise

    def delete_file(self, blob_name: str) -> None:
        """Delete a file from the bucket."""
        try:
            blob = self.bucket.blob(blob_name)
            blob.delete()
            logger.info(f"Deleted {blob_name}")
        except gcp_exceptions.NotFound:
            logger.warning(f"File not found for deletion: {blob_name}")
        except Exception as e:
            logger.error(f"Error deleting file {blob_name}: {e}")
            raise

    def list_files(
        self,
        prefix: str,
        file_extension: Optional[str] = None
    ) -> List[str]:
        """
        List files in the bucket with a given prefix.

        Args:
            prefix: Prefix to filter files
            file_extension: Optional file extension filter (e.g., '.json.gz')

        Returns:
            List of blob names
        """
        try:
            blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
            if file_extension:
                return [blob.name for blob in blobs if blob.name.endswith(file_extension)]
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Error listing files with prefix {prefix}: {e}")
            raise

    def file_exists(self, blob_name: str) -> bool:
        """Check if a file exists in the bucket."""
        try:
            blob = self.bucket.blob(blob_name)
            return blob.exists()
        except Exception as e:
            logger.error(f"Error checking file existence: {e}")
            return False

    def get_file_metadata(self, blob_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a file.

        Args:
            blob_name: Name of the blob

        Returns:
            Dictionary with metadata or None if not found
        """
        try:
            blob = self.bucket.blob(blob_name)
            blob.reload()
            return {
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_type,
                "updated": blob.updated,
                "metadata": blob.metadata
            }
        except gcp_exceptions.NotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting file metadata: {e}")
            raise
