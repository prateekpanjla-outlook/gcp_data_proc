"""Modular storage abstraction layer.

Supports multiple storage backends:
- LocalStorage: Direct file system access
- GcsEmulatorStorage: fake-gcs-server HTTP API
- GcsStorage: Production Google Cloud Storage

Usage:
    from src.shared.storage import get_storage_backend

    # Auto-detect based on environment
    storage = get_storage_backend()

    # Explicit backend selection
    storage = get_storage_backend('local', base_path='./data')
    storage = get_storage_backend('emulator', default_bucket='test-bucket')
    storage = get_storage_backend('gcs', bucket_name='my-bucket', project_id='my-project')

    # Read JSONL file
    for event in storage.read_jsonl_file('path/to/file.json.gz', compressed=True):
        process(event)
"""

from .backends import (
    StorageBackend,
    LocalStorage,
    GcsEmulatorStorage,
    GcsStorage,
    get_storage_backend,
)

__all__ = [
    'StorageBackend',
    'LocalStorage',
    'GcsEmulatorStorage',
    'GcsStorage',
    'get_storage_backend',
]
