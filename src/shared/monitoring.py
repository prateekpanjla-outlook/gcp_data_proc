"""Monitoring and observability for the data pipeline.

Provides structured logging, metrics collection, and distributed tracing.
"""

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

import opencensus
from opencensus.trace import tracer as tracer_module
from opencensus.trace.samplers import AlwaysOnSampler
from opencensus.trace.propagation import text_format
from opencensus.trace.span import Span

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class Metric:
    """A metric data point."""

    name: str
    value: float
    type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "type": self.type.value,
            "labels": self.labels,
            "timestamp": self.timestamp,
        }


@dataclass
class ProcessingMetrics:
    """Metrics collected during pipeline processing."""

    source: str
    file_name: Optional[str] = None
    table_name: Optional[str] = None

    # Counters
    rows_processed: int = 0
    rows_succeeded: int = 0
    rows_failed: int = 0
    rows_retried: int = 0

    # Timing
    processing_time_ms: float = 0
    bigquery_insert_time_ms: float = 0
    storage_read_time_ms: float = 0

    # Status
    status: str = "in_progress"
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source": self.source,
            "file_name": self.file_name,
            "table_name": self.table_name,
            "rows_processed": self.rows_processed,
            "rows_succeeded": self.rows_succeeded,
            "rows_failed": self.rows_failed,
            "rows_retried": self.rows_retried,
            "processing_time_ms": self.processing_time_ms,
            "bigquery_insert_time_ms": self.bigquery_insert_time_ms,
            "storage_read_time_ms": self.storage_read_time_ms,
            "status": self.status,
            "errors": self.errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def add_error(self, error: str):
        """Add an error message."""
        self.errors.append(error)
        self.rows_failed += 1


class MetricsCollector:
    """Collect and manage metrics for the pipeline."""

    def __init__(self, project_id: str, enable_export: bool = False):
        """Initialize metrics collector.

        Args:
            project_id: GCP project ID
            enable_export: Whether to export metrics to Cloud Monitoring
        """
        self.project_id = project_id
        self.enable_export = enable_export
        self.metrics: List[Metric] = []

        # Initialize tracer if export is enabled
        self.tracer = None
        if enable_export:
            try:
                from opencensus.trace.exporters import stackdriver_exporter

                exporter = stackdriver_exporter.StackdriverExporter(
                    project_id=project_id,
                    transport=stackdriver_exporter.StackdriverExporter.make_export_transport(),
                )
                self.tracer = tracer_module.Tracer(
                    exporter=exporter, sampler=AlwaysOnSampler()
                )
            except ImportError:
                logger.warning("OpenCensus StackDriver exporter not available")
                self.tracer = tracer_module.Tracer(sampler=AlwaysOnSampler())

    def record(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Record a metric.

        Args:
            name: Metric name
            value: Metric value
            metric_type: Type of metric
            labels: Optional labels for the metric
        """
        metric = Metric(
            name=name,
            value=value,
            type=metric_type,
            labels=labels or {},
        )
        self.metrics.append(metric)

        # Log metric for local development
        logger.debug(f"Metric: {metric.to_dict()}")

        # Export to Cloud Monitoring if enabled
        if self.enable_export:
            self._export_metric(metric)

    def increment_counter(self, name: str, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric.

        Args:
            name: Counter name
            labels: Optional labels
        """
        self.record(name, 1, MetricType.COUNTER, labels)

    def record_timing(self, name: str, duration_ms: float, labels: Optional[Dict[str, str]] = None):
        """Record a timing metric.

        Args:
            name: Timer name
            duration_ms: Duration in milliseconds
            labels: Optional labels
        """
        self.record(name, duration_ms, MetricType.TIMER, labels)

    def _export_metric(self, metric: Metric):
        """Export metric to Cloud Monitoring.

        Note: This is a simplified implementation. For production,
        use google-cloud-monitoring library directly.
        """
        # TODO: Implement Cloud Monitoring API integration
        pass

    def get_metrics(self) -> List[Dict[str, Any]]:
        """Get all collected metrics.

        Returns:
            List of metric dictionaries
        """
        return [m.to_dict() for m in self.metrics]

    def clear(self):
        """Clear all collected metrics."""
        self.metrics.clear()


class StructuredLogger:
    """Structured logger with context."""

    def __init__(self, name: str, context: Optional[Dict[str, Any]] = None):
        """Initialize structured logger.

        Args:
            name: Logger name
            context: Default context for all log entries
        """
        self.logger = logging.getLogger(name)
        self.context = context or {}

    def _format(self, message: str, **kwargs) -> Dict[str, Any]:
        """Format log entry with context.

        Args:
            message: Log message
            **kwargs: Additional fields

        Returns:
            Formatted log dictionary
        """
        log_entry = {
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **self.context,
            **kwargs,
        }
        return log_entry

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(self._format(message, **kwargs))

    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(self._format(message, **kwargs))

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(self._format(message, **kwargs))

    def error(self, message: str, **kwargs):
        """Log error message."""
        self.logger.error(self._format(message, **kwargs))

    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self.logger.critical(self._format(message, **kwargs))

    def with_context(self, **kwargs) -> "StructuredLogger":
        """Return a new logger with additional context.

        Args:
            **kwargs: Additional context fields

        Returns:
            New StructuredLogger with merged context
        """
        new_context = {**self.context, **kwargs}
        return StructuredLogger(self.logger.name, new_context)


@contextmanager
def trace_operation(
    name: str,
    tracer: Optional[tracer_module.Tracer] = None,
    labels: Optional[Dict[str, str]] = None,
):
    """Context manager for tracing an operation.

    Args:
        name: Operation name
        tracer: Optional tracer (creates new if not provided)
        labels: Optional labels for the span

    Yields:
        Span object for adding attributes

    Example:
        with trace_operation("process_file", labels={"file": "data.json"}) as span:
            # Do work
            span.add_attribute("rows_processed", 100)
    """
    if tracer is None:
        tracer = tracer_module.Tracer(sampler=AlwaysOnSampler())

    with tracer.span(name=name) as span:
        if labels:
            for key, value in labels.items():
                span.add_attribute(key, value)
        yield span


@contextmanager
def measure_time(
    metrics_collector: MetricsCollector,
    metric_name: str,
    labels: Optional[Dict[str, str]] = None,
):
    """Context manager for measuring operation time.

    Args:
        metrics_collector: MetricsCollector instance
        metric_name: Name for the timing metric
        labels: Optional labels for the metric

    Yields:
        None

    Example:
        with measure_time(metrics, "file_processing", {"source": "github"}):
            process_file()
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration_ms = (time.time() - start_time) * 1000
        metrics_collector.record_timing(metric_name, duration_ms, labels)


class PipelineMonitor:
    """High-level monitoring interface for the pipeline."""

    def __init__(
        self,
        project_id: str,
        source: str,
        enable_export: bool = False,
    ):
        """Initialize pipeline monitor.

        Args:
            project_id: GCP project ID
            source: Source identifier (e.g., "github-archive-processor")
            enable_export: Whether to export metrics
        """
        self.project_id = project_id
        self.source = source
        self.enable_export = enable_export

        self.metrics = MetricsCollector(project_id, enable_export)
        self.logger = StructuredLogger("pipeline", {"source": source})

        self.current_processing: Optional[ProcessingMetrics] = None

    def start_processing(
        self,
        file_name: Optional[str] = None,
        table_name: Optional[str] = None,
    ) -> ProcessingMetrics:
        """Start tracking a processing operation.

        Args:
            file_name: Optional file being processed
            table_name: Optional target table

        Returns:
            ProcessingMetrics object
        """
        self.current_processing = ProcessingMetrics(
            source=self.source,
            file_name=file_name,
            table_name=table_name,
        )

        self.logger.info(
            "Processing started",
            file_name=file_name,
            table_name=table_name,
        )

        return self.current_processing

    def finish_processing(self, success: bool = True):
        """Finish current processing operation.

        Args:
            success: Whether processing was successful
        """
        if self.current_processing:
            self.current_processing.status = "success" if success else "failed"
            self.current_processing.processing_time_ms = (
                time.time() * 1000
            )  # Simplified

            self.logger.info(
                "Processing completed",
                **self.current_processing.to_dict(),
            )

            # Record metrics
            self.metrics.record(
                "rows_processed",
                self.current_processing.rows_processed,
                MetricType.COUNTER,
                {"source": self.source},
            )

            if self.current_processing.rows_failed > 0:
                self.metrics.record(
                    "rows_failed",
                    self.current_processing.rows_failed,
                    MetricType.COUNTER,
                    {"source": self.source},
                )

    def record_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """Record an error.

        Args:
            error: The exception
            context: Additional context
        """
        self.logger.error(
            str(error),
            error_type=type(error).__name__,
            **(context or {}),
        )

        self.metrics.increment_counter(
            "errors",
            {"source": self.source, "error_type": type(error).__name__},
        )

        if self.current_processing:
            self.current_processing.add_error(str(error))
