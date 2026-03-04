"""Modular storage backends for data pipeline.

Supports multiple storage backends via a common interface:
- LocalStorage: Direct file system access
- GcsEmulatorStorage: fake-gcs-server HTTP API
- GcsStorage: Production Google Cloud Storage
"""

import os
import json
import gzip
from typing import Generator, Dict, Any, Optional
from abc import ABC, abstractmethod
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import ssl


# =============================================================================
# Abstract Base Class
# =============================================================================

class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def read_jsonl_file(
        self,
        blob_name: str,
        compressed: bool = False
    ) -> Generator[Dict[str, Any], None, None]:
        """Read a JSONL file, yielding one event at a time (memory efficient)."""
        pass

    @abstractmethod
    def write_jsonl_file(
        self,
        blob_name: str,
        data: list,
        compressed: bool = False
    ) -> None:
        """Write data as a JSONL file."""
        pass

    @abstractmethod
    def get_file_size(self, blob_name: str) -> Optional[int]:
        """Get file size in bytes."""
        pass

    @abstractmethod
    def file_exists(self, blob_name: str) -> bool:
        """Check if file exists."""
        pass


# =============================================================================
# Local Storage Implementation
# =============================================================================

class LocalStorage(StorageBackend):
    """Local filesystem storage backend.

    Reads files directly from the local filesystem.
    Useful for local development and testing.
    """

    def __init__(self, base_path: str = "."):
        """Initialize LocalStorage with a base path.

        Args:
            base_path: Base directory for file operations. Defaults to current directory.
        """
        self.base_path = os.path.abspath(base_path)

    def _resolve_path(self, blob_name: str) -> str:
        """Resolve blob name to absolute file path."""
        if os.path.isabs(blob_name):
            return blob_name
        return os.path.join(self.base_path, blob_name)

    def _ensure_dir(self, file_path: str) -> None:
        """Ensure directory exists for file path."""
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def read_jsonl_file(
        self,
        blob_name: str,
        compressed: bool = False
    ) -> Generator[Dict[str, Any], None, None]:
        """Read a JSONL file, yielding one event at a time."""
        file_path = self._resolve_path(blob_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        open_func = gzip.open if compressed else open
        mode = 'rt' if compressed else 'r'

        with open_func(file_path, mode, encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"Warning: Invalid JSON at line {line_num}: {e}")
                    continue

    def write_jsonl_file(
        self,
        blob_name: str,
        data: list,
        compressed: bool = False
    ) -> None:
        """Write data as a JSONL file."""
        file_path = self._resolve_path(blob_name)
        self._ensure_dir(file_path)

        lines = [json.dumps(item, ensure_ascii=False) for item in data]
        content = '\n'.join(lines).encode('utf-8')

        if compressed:
            content = gzip.compress(content)

        open_func = gzip.open if compressed else open
        mode = 'wb' if compressed else 'w'

        with open_func(file_path, mode) as f:
            if compressed:
                f.write(content)
            else:
                f.write(content.decode('utf-8'))

    def get_file_size(self, blob_name: str) -> Optional[int]:
        """Get file size in bytes."""
        file_path = self._resolve_path(blob_name)
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
        return None

    def file_exists(self, blob_name: str) -> bool:
        """Check if file exists."""
        file_path = self._resolve_path(blob_name)
        return os.path.exists(file_path)


# =============================================================================
# GCS Emulator Storage Implementation
# =============================================================================

class GcsEmulatorStorage(StorageBackend):
    """GCS Emulator storage backend.

    Connects to fake-gcs-server HTTP API for local development.

    Upload endpoint:
        POST /upload/storage/v1/b/{bucket}/o?uploadType=media&name={path}

    Download endpoint:
        GET /download/storage/v1/b/{bucket}/o/{path}?alt=media
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 4443,
        use_ssl: bool = False,
        default_bucket: str = None
    ):
        """Initialize GcsEmulatorStorage.

        Args:
            host: Emulator host address
            port: Emulator port (default 4443 for fake-gcs-server)
            use_ssl: Whether to use HTTPS (usually False for local emulator)
            default_bucket: Default bucket name if not included in blob_name
        """
        protocol = "https" if use_ssl else "http"
        self.base_url = f"{protocol}://{host}:{port}"
        self.default_bucket = default_bucket
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    def _parse_blob_name(self, blob_name: str) -> tuple:
        """Parse blob name into (bucket, object_path)."""
        parts = blob_name.split('/', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        if self.default_bucket:
            return self.default_bucket, parts[0]
        raise ValueError(
            f"blob_name must include bucket or default_bucket must be set. Got: {blob_name}"
        )

    def _build_url(self, bucket: str, blob_name: str = None, download: bool = False) -> str:
        """Build URL for GCS API."""
        if download:
            base = f"{self.base_url}/download/storage/v1/b/{bucket}/o"
        else:
            base = f"{self.base_url}/storage/v1/b/{bucket}/o"
        if blob_name:
            encoded_name = blob_name.replace('/', '%2F')
            base = f"{base}/{encoded_name}"
        return base

    def _make_request(self, url: str, method: str = "GET", body: bytes = None, headers: dict = None) -> tuple:
        """Make HTTP request to emulator."""
        if headers is None:
            headers = {}

        req = Request(url, method=method, data=body, headers=headers)

        try:
            with urlopen(req, context=self._ssl_context) as response:
                resp_body = response.read()
                return resp_body, response.status, dict(response.headers)
        except HTTPError as e:
            return e.read(), e.code, dict(e.headers)
        except URLError as e:
            raise ConnectionError(
                f"Failed to connect to GCS emulator at {self.base_url}. "
                f"Is it running? Error: {e.reason}"
            )

    def read_jsonl_file(
        self,
        blob_name: str,
        compressed: bool = False
    ) -> Generator[Dict[str, Any], None, None]:
        """Read a JSONL file from GCS emulator."""
        bucket, object_path = self._parse_blob_name(blob_name)
        url = f"{self._build_url(bucket, object_path, download=True)}?alt=media"
        body, status, headers = self._make_request(url)

        if status == 404:
            raise FileNotFoundError(f"Blob not found: {blob_name}")
        elif status != 200:
            raise RuntimeError(f"Failed to read blob: status {status}")

        content = body.decode('utf-8') if not compressed else gzip.decompress(body).decode('utf-8')

        for line_num, line in enumerate(content.split('\n'), 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Warning: Invalid JSON at line {line_num}: {e}")
                continue

    def write_jsonl_file(
        self,
        blob_name: str,
        data: list,
        compressed: bool = False
    ) -> None:
        """Write data as a JSONL file to GCS emulator."""
        bucket, object_path = self._parse_blob_name(blob_name)

        lines = [json.dumps(item, ensure_ascii=False) for item in data]
        content = '\n'.join(lines).encode('utf-8')

        if compressed:
            content = gzip.compress(content)

        # Use upload endpoint for media uploads
        url = f"{self.base_url}/upload/storage/v1/b/{bucket}/o?uploadType=media&name={object_path}"
        content_type = "application/octet-stream" if compressed else "application/json"

        body, status, headers = self._make_request(url, method="POST", body=content, headers={"Content-Type": content_type})

        if status not in (200, 201):
            raise RuntimeError(f"Failed to write blob: status {status}, response: {body.decode()}")

    def get_file_size(self, blob_name: str) -> Optional[int]:
        """Get file size from GCS emulator."""
        bucket, object_path = self._parse_blob_name(blob_name)
        url = self._build_url(bucket, object_path)
        req = Request(url, method="GET", headers={"Accept": "application/json"})

        try:
            with urlopen(req, context=self._ssl_context) as response:
                data = json.loads(response.read().decode())
                return int(data.get('size', 0))
        except HTTPError as e:
            if e.code == 404:
                return None
            return None
        except URLError:
            return None

    def file_exists(self, blob_name: str) -> bool:
        """Check if blob exists in GCS emulator."""
        return self.get_file_size(blob_name) is not None


# =============================================================================
# Production GCS Storage Implementation
# =============================================================================

class GcsStorage(StorageBackend):
    """Production Google Cloud Storage backend.

    Wraps the google-cloud-storage client for production use.
    """

    def __init__(self, bucket_name: str, project_id: Optional[str] = None):
        """Initialize GcsStorage.

        Args:
            bucket_name: Name of the Cloud Storage bucket
            project_id: GCP project ID (optional)
        """
        from google.cloud import storage
        from google.api_core import exceptions as gcp_exceptions

        self.bucket_name = bucket_name
        self.project_id = project_id
        self.client = storage.Client(project=project_id)
        self.bucket = self.client.bucket(bucket_name)
        self._gcp_exceptions = gcp_exceptions

    def read_jsonl_file(
        self,
        blob_name: str,
        compressed: bool = False
    ) -> Generator[Dict[str, Any], None, None]:
        """Read a JSONL file from Cloud Storage."""
        try:
            blob = self.bucket.blob(blob_name)
            content_bytes = blob.download_as_bytes()

            if compressed:
                content_bytes = gzip.decompress(content_bytes)

            for line in content_bytes.decode('utf-8').split('\n'):
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as e:
                        print(f"Warning: Failed to parse JSON line: {e}")
                        continue

        except self._gcp_exceptions.NotFound:
            raise FileNotFoundError(f"Blob not found: {blob_name}")
        except Exception as e:
            raise RuntimeError(f"Error reading file {blob_name}: {e}")

    def write_jsonl_file(
        self,
        blob_name: str,
        data: list,
        compressed: bool = False
    ) -> None:
        """Write data as a JSONL file to Cloud Storage."""
        try:
            blob = self.bucket.blob(blob_name)
            lines = [json.dumps(item, ensure_ascii=False) for item in data]
            content = '\n'.join(lines).encode('utf-8')

            if compressed:
                content = gzip.compress(content)

            blob.upload_from_string(content, content_type='application/json')
        except Exception as e:
            raise RuntimeError(f"Error writing file {blob_name}: {e}")

    def get_file_size(self, blob_name: str) -> Optional[int]:
        """Get file size from Cloud Storage."""
        try:
            blob = self.bucket.blob(blob_name)
            blob.reload()
            return blob.size
        except self._gcp_exceptions.NotFound:
            return None
        except Exception:
            return None

    def file_exists(self, blob_name: str) -> bool:
        """Check if blob exists in Cloud Storage."""
        try:
            blob = self.bucket.blob(blob_name)
            return blob.exists()
        except Exception:
            return False


# =============================================================================
# Factory Function
# =============================================================================

def get_storage_backend(
    backend_type: str = None,
    **kwargs
) -> StorageBackend:
    """Factory function to get the appropriate storage backend.

    The backend type can be specified via:
    1. The `backend_type` parameter
    2. The `STORAGE_BACKEND` environment variable
    3. Inferred from other settings (e.g., BIGQUERY_EMULATOR_HOST)

    Args:
        backend_type: One of 'local', 'emulator', 'gcs', or 'auto'
        **kwargs: Additional arguments passed to the backend constructor:
            - For 'local': base_path (default: ".")
            - For 'emulator': host, port, use_ssl, default_bucket
            - For 'gcs': bucket_name, project_id

    Returns:
        A StorageBackend instance

    Raises:
        ValueError: If backend_type is invalid

    Examples:
        # Auto-detect based on environment
        storage = get_storage_backend()

        # Explicitly use local storage
        storage = get_storage_backend('local', base_path='./data')

        # Explicitly use emulator
        storage = get_storage_backend('emulator', default_bucket='test-bucket')

        # Explicitly use production GCS
        storage = get_storage_backend('gcs', bucket_name='my-bucket', project_id='my-project')
    """
    # Determine backend type
    if backend_type is None:
        backend_type = os.environ.get('STORAGE_BACKEND', 'auto')

    if backend_type == 'auto':
        # Auto-detect based on environment
        if os.environ.get('BIGQUERY_EMULATOR_HOST'):
            backend_type = 'emulator'
        elif os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            backend_type = 'gcs'
        else:
            backend_type = 'local'

    backend_type = backend_type.lower()

    # Create appropriate backend
    if backend_type == 'local':
        base_path = kwargs.get('base_path', os.environ.get('STORAGE_LOCAL_PATH', '.'))
        return LocalStorage(base_path=base_path)

    elif backend_type == 'emulator':
        host = kwargs.get('host', os.environ.get('STORAGE_EMULATOR_HOST', 'localhost'))
        port = kwargs.get('port', int(os.environ.get('STORAGE_EMULATOR_PORT', '4443')))
        use_ssl = kwargs.get('use_ssl', os.environ.get('STORAGE_EMULATOR_SSL', 'false').lower() == 'true')
        default_bucket = kwargs.get('default_bucket', os.environ.get('STORAGE_DEFAULT_BUCKET'))
        return GcsEmulatorStorage(
            host=host,
            port=port,
            use_ssl=use_ssl,
            default_bucket=default_bucket
        )

    elif backend_type in ('gcs', 'production', 'prod'):
        bucket_name = kwargs.get('bucket_name')
        if not bucket_name:
            bucket_name = os.environ.get('STORAGE_BUCKET_NAME')
        if not bucket_name:
            raise ValueError("bucket_name must be provided for 'gcs' backend")
        project_id = kwargs.get('project_id', os.environ.get('PROJECT_ID'))
        return GcsStorage(bucket_name=bucket_name, project_id=project_id)

    else:
        raise ValueError(
            f"Invalid backend_type: {backend_type}. "
            f"Must be one of: 'local', 'emulator', 'gcs', or 'auto'"
        )
