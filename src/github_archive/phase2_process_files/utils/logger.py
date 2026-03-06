"""
Cloud Logging utilities for Phase 2 processing.

Provides structured logging to Google Cloud Logging with proper error tracking.
"""

import json
import os
import sys
import logging
from typing import Any, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, asdict


# =============================================================================
# LOG ENTRY
# =============================================================================
@dataclass
class LogEntry:
    """Structured log entry for Cloud Logging."""
    severity: str
    message: str
    component: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'severity': self.severity,
            'message': self.message,
            'component': self.component,
            'timestamp': self.timestamp,
            **(self.metadata or {})
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


# =============================================================================
# PHASE 2 LOGGER
# =============================================================================
class Phase2Logger:
    """
    Structured logger for Phase 2 processing.

    Logs to stdout (for Cloud Run) with structured JSON format.
    Compatible with Google Cloud Logging.
    """

    SEVERITY_LEVELS = {
        'DEBUG': 'DEBUG',
        'INFO': 'INFO',
        'WARNING': 'WARNING',
        'ERROR': 'ERROR',
        'CRITICAL': 'CRITICAL'
    }

    def __init__(
        self,
        component: str = 'phase2-processor',
        project_id: Optional[str] = None
    ):
        """
        Initialize the Phase 2 logger.

        Args:
            component: Component name for log attribution
            project_id: GCP project ID
        """
        self.component = component
        self.project_id = project_id or os.getenv('PROJECT_ID')

        # Configure Python logging to use our handler
        self.logger = logging.getLogger(component)
        self.logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        self.logger.handlers.clear()

        # Add structured handler
        handler = StructuredLogHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)

    def debug(self, message: str, **metadata) -> None:
        """Log a debug message."""
        self._log('DEBUG', message, metadata)

    def info(self, message: str, **metadata) -> None:
        """Log an info message."""
        self._log('INFO', message, metadata)

    def warning(self, message: str, **metadata) -> None:
        """Log a warning message."""
        self._log('WARNING', message, metadata)

    def error(self, message: str, **metadata) -> None:
        """Log an error message."""
        self._log('ERROR', message, metadata)

    def critical(self, message: str, **metadata) -> None:
        """Log a critical message."""
        self._log('CRITICAL', message, metadata)

    def _log(self, severity: str, message: str, metadata: Dict[str, Any]) -> None:
        """Internal logging method."""
        entry = LogEntry(
            severity=severity,
            message=message,
            component=self.component,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            metadata=metadata if metadata else None
        )

        # Map to Python logging levels
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }

        self.logger.log(level_map.get(severity, logging.INFO), entry.to_json())

    def log_file_start(
        self,
        file_name: str,
        file_size: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log the start of file processing."""
        meta = {
            'file_name': file_name,
            'file_size': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'event': 'file_processing_start',
            **(metadata or {})
        }
        self.info(f"Processing file: {file_name}", **meta)

    def log_file_complete(
        self,
        file_name: str,
        records_in: int,
        records_out: int,
        errors: int,
        duration_seconds: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log the completion of file processing."""
        meta = {
            'file_name': file_name,
            'records_in': records_in,
            'records_out': records_out,
            'errors': errors,
            'duration_seconds': round(duration_seconds, 2),
            'error_rate': round(errors / records_in, 4) if records_in > 0 else 0,
            'event': 'file_processing_complete',
            **(metadata or {})
        }
        self.info(f"Completed processing: {file_name}", **meta)

    def log_file_error(
        self,
        file_name: str,
        error: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a file processing error."""
        meta = {
            'file_name': file_name,
            'error': error,
            'event': 'file_processing_error',
            **(metadata or {})
        }
        self.error(f"Error processing file: {file_name} - {error}", **meta)

    def log_validation_error(
        self,
        file_name: str,
        error_type: str,
        error_count: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a validation error."""
        meta = {
            'file_name': file_name,
            'error_type': error_type,
            'error_count': error_count,
            'event': 'validation_error',
            **(metadata or {})
        }
        self.warning(f"Validation error in {file_name}: {error_type} ({error_count} records)", **meta)

    def log_chunk_progress(
        self,
        file_name: str,
        chunk_num: int,
        total_chunks: int,
        records_processed: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log chunk processing progress."""
        meta = {
            'file_name': file_name,
            'chunk_num': chunk_num,
            'total_chunks': total_chunks,
            'records_processed': records_processed,
            'event': 'chunk_progress',
            **(metadata or {})
        }
        self.info(f"Chunk {chunk_num}/{total_chunks} processed: {records_processed} records", **meta)


# =============================================================================
# STRUCTURED LOG HANDLER
# =============================================================================
class StructuredLogHandler(logging.Handler):
    """Custom logging handler that outputs structured JSON."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record."""
        try:
            msg = self.format(record)
            print(msg, flush=True)
        except Exception:
            self.handleError(record)


# =============================================================================
# PROCESSING METRICS
# =============================================================================
@dataclass
class ProcessingMetrics:
    """Metrics collected during file processing."""
    files_processed: int = 0
    files_failed: int = 0
    total_records_in: int = 0
    total_records_out: int = 0
    total_errors: int = 0
    total_duration_seconds: float = 0.0
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def log_summary(self, logger: Phase2Logger) -> None:
        """Log a summary of metrics."""
        logger.info(
            "Processing summary",
            files_processed=self.files_processed,
            files_failed=self.files_failed,
            total_records_in=self.total_records_in,
            total_records_out=self.total_records_out,
            total_errors=self.total_errors,
            total_duration_seconds=round(self.total_duration_seconds, 2),
            avg_records_per_second=round(
                self.total_records_in / self.total_duration_seconds, 2
            ) if self.total_duration_seconds > 0 else 0,
            event='processing_summary'
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def get_logger(
    component: str = 'phase2-processor',
    project_id: Optional[str] = None
) -> Phase2Logger:
    """
    Get a configured Phase 2 logger instance.

    Args:
        component: Component name for log attribution
        project_id: GCP project ID

    Returns:
        Phase2Logger instance
    """
    return Phase2Logger(component=component, project_id=project_id)


def log_structured(
    severity: str,
    message: str,
    component: str = 'phase2-processor',
    **metadata
) -> None:
    """
    Log a structured message without creating a logger instance.

    Args:
        severity: Log severity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: Log message
        component: Component name
        **metadata: Additional metadata fields
    """
    entry = LogEntry(
        severity=severity,
        message=message,
        component=component,
        timestamp=datetime.utcnow().isoformat() + 'Z',
        metadata=metadata if metadata else None
    )
    print(entry.to_json(), flush=True)
