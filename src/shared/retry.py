"""Retry logic with exponential backoff for transient errors.

Uses tenacity library for robust retry handling with configurable policies.
"""

import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type

from google.api_core import exceptions as gcp_exceptions
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    try_except,
)

logger = logging.getLogger(__name__)


# Transient errors that should trigger retries
TRANSIENT_ERRORS = (
    gcp_exceptions.InternalServerError,
    gcp_exceptions.ServiceUnavailable,
    gcp_exceptions.GatewayTimeout,
    gcp_exceptions.Aborted,
    gcp_exceptions.DeadlineExceeded,
    ConnectionError,
    TimeoutError,
)


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        wait_min: float = 1.0,
        wait_max: float = 10.0,
        multiplier: float = 2.0,
    ):
        """Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts
            wait_min: Minimum wait time between retries (seconds)
            wait_max: Maximum wait time between retries (seconds)
            multiplier: Exponential backoff multiplier
        """
        self.max_attempts = max_attempts
        self.wait_min = wait_min
        self.wait_max = wait_max
        self.multiplier = multiplier


# Default retry configuration
DEFAULT_RETRY = RetryConfig()

# Aggressive retry for high-throughput scenarios
AGGRESSIVE_RETRY = RetryConfig(
    max_attempts=5,
    wait_min=0.5,
    wait_max=5.0,
    multiplier=1.5,
)

# Conservative retry for critical operations
CONSERVATIVE_RETRY = RetryConfig(
    max_attempts=3,
    wait_min=2.0,
    wait_max=30.0,
    multiplier=3.0,
)


def retry_with_exponential_backoff(
    config: Optional[RetryConfig] = None,
    exception_types: Optional[tuple] = None,
    on_retry: Optional[Callable] = None,
):
    """Decorator for retrying functions with exponential backoff.

    Args:
        config: Retry configuration (uses DEFAULT_RETRY if not provided)
        exception_types: Tuple of exception types to retry on
        on_retry: Optional callback function called before each retry

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_exponential_backoff()
        def insert_data(data):
            # This will be retried on transient errors
            return bigquery_client.insert_rows(data)
    """
    if config is None:
        config = DEFAULT_RETRY

    if exception_types is None:
        exception_types = TRANSIENT_ERRORS

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            retrier = Retrying(
                stop=stop_after_attempt(config.max_attempts),
                wait=wait_exponential(
                    multiplier=config.multiplier,
                    min=config.wait_min,
                    max=config.wait_max,
                ),
                retry=retry_if_exception_type(exception_types),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            )

            try:
                return retrier.call(func, *args, **kwargs)
            except Exception as e:
                # Log final failure after all retries exhausted
                logger.error(
                    f"Function {func.__name__} failed after {config.max_attempts} attempts: {e}"
                )
                raise

        return wrapper

    return decorator


class RetryHandler:
    """Handler for retrying operations with context tracking."""

    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize retry handler.

        Args:
            config: Retry configuration
            context: Optional context dict for logging (e.g., file_name, table_id)
        """
        self.config = config or DEFAULT_RETRY
        self.context = context or {}
        self.attempt_count = 0

    def _log_retry(self, retry_state):
        """Log retry attempt with context."""
        self.attempt_count += 1
        context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
        logger.warning(
            f"Retry {self.attempt_count}/{self.config.max_attempts} "
            f"({context_str}): {retry_state.outcome.exception()}"
        )

    def execute_with_retry(
        self,
        func: Callable,
        *args,
        exception_types: Optional[tuple] = None,
        **kwargs,
    ) -> Any:
        """Execute a function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments for func
            exception_types: Custom exception types to retry on
            **kwargs: Keyword arguments for func

        Returns:
            Result of func(*args, **kwargs)

        Raises:
            Last exception if all retries are exhausted
        """
        if exception_types is None:
            exception_types = TRANSIENT_ERRORS

        retrier = Retrying(
            stop=stop_after_attempt(self.config.max_attempts),
            wait=wait_exponential(
                multiplier=self.config.multiplier,
                min=self.config.wait_min,
                max=self.config.wait_max,
            ),
            retry=retry_if_exception_type(exception_types),
            before_sleep=self._log_retry,
            reraise=True,
        )

        return retrier(func, *args, **kwargs)


class BigQueryRetryHandler(RetryHandler):
    """Specialized retry handler for BigQuery operations."""

    def __init__(
        self,
        project_id: str,
        dataset_id: str,
        table_id: Optional[str] = None,
        config: Optional[RetryConfig] = None,
    ):
        """Initialize BigQuery retry handler.

        Args:
            project_id: GCP project ID
            dataset_id: BigQuery dataset ID
            table_id: BigQuery table ID (optional)
            config: Retry configuration
        """
        context = {
            "project": project_id,
            "dataset": dataset_id,
        }
        if table_id:
            context["table"] = table_id

        super().__init__(config=config, context=context)

    @retry_with_exponential_backoff(config=DEFAULT_RETRY)
    def insert_rows(
        self,
        client,
        rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Insert rows with automatic retry.

        Args:
            client: BigQuery client
            rows: List of row dictionaries

        Returns:
            List of errors (empty if successful)
        """
        table_ref = f"{self.context['project']}.{self.context['dataset']}.{self.context['table']}"
        return client.insert_rows_json(table_ref, rows)

    @retry_with_exponential_backoff(config=CONSERVATIVE_RETRY)
    def load_dataframe(
        self,
        client,
        dataframe: "pd.DataFrame",
        schema: List,
    ) -> Dict[str, Any]:
        """Load DataFrame with automatic retry.

        Args:
            client: BigQuery client
            dataframe: Pandas DataFrame to load
            schema: BigQuery schema

        Returns:
            Load result dictionary
        """
        from google.cloud.bigquery import LoadJobConfig

        table_ref = f"{self.context['project']}.{self.context['dataset']}.{self.context['table']}"
        job_config = LoadJobConfig(schema=schema)

        job = client.load_table_from_dataframe(
            dataframe,
            table_ref,
            job_config=job_config,
        )

        # Wait for completion with timeout
        job.result(timeout=120)

        return {
            "job_id": job.job_id,
            "state": job.state,
            "output_rows": job.output_rows,
        }


# Convenience decorators for common use cases
def retry_bigquery_insert(func: Callable) -> Callable:
    """Decorator for BigQuery insert operations with standard retry."""
    return retry_with_exponential_backoff(
        config=DEFAULT_RETRY,
        exception_types=TRANSIENT_ERRORS + (
            gcp_exceptions.BadRequest,  # Some quota errors are transient
        ),
    )(func)


def retry_storage_read(func: Callable) -> Callable:
    """Decorator for Cloud Storage read operations with standard retry."""
    return retry_with_exponential_backoff(
        config=AGGRESSIVE_RETRY,  # More aggressive for storage reads
        exception_types=TRANSIENT_ERRORS,
    )(func)


def retry_pubsub_publish(func: Callable) -> Callable:
    """Decorator for Pub/Sub publish operations with standard retry."""
    return retry_with_exponential_backoff(
        config=AGGRESSIVE_RETRY,
        exception_types=TRANSIENT_ERRORS,
    )(func)
