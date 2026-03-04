"""Dead Letter Queue handler for failed pipeline events.

Captures failed events from Cloud Run processors and publishes them to
Pub/Sub for later reprocessing or analysis.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from google.cloud import pubsub_v1
from google.api_core import exceptions as gcp_exceptions

from src.shared.retry import retry_pubsub_publish, RetryConfig

logger = logging.getLogger(__name__)


@dataclass
class DeadLetterMessage:
    """Structure for dead letter messages."""

    original_event: Dict[str, Any]
    error_message: str
    error_type: str
    source: str
    timestamp: str
    retry_count: int = 0
    max_retries: int = 3
    context: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(asdict(self), default=str)

    @classmethod
    def from_event(
        cls,
        original_event: Dict[str, Any],
        error: Exception,
        source: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> "DeadLetterMessage":
        """Create DeadLetterMessage from a failed event.

        Args:
            original_event: The original event that failed
            error: The exception that was raised
            source: Source identifier (e.g., "github-archive-processor")
            context: Additional context about the failure

        Returns:
            DeadLetterMessage instance
        """
        return cls(
            original_event=original_event,
            error_message=str(error),
            error_type=type(error).__name__,
            source=source,
            timestamp=datetime.now(timezone.utc).isoformat(),
            context=context or {},
        )


class DeadLetterQueueHandler:
    """Handle publishing failed events to Dead Letter Queue."""

    def __init__(
        self,
        project_id: str,
        dlq_topic_id: str = "pipeline-dlq",
        retry_config: Optional[RetryConfig] = None,
    ):
        """Initialize DLQ handler.

        Args:
            project_id: GCP project ID
            dlq_topic_id: Pub/Sub topic ID for dead letters
            retry_config: Retry configuration for publishing
        """
        self.project_id = project_id
        self.dlq_topic_id = dlq_topic_id
        self.topic_path = pubsub_v1.PublisherClient().topic_path(
            project_id, dlq_topic_id
        )

        self.publisher = pubsub_v1.PublisherClient()
        self._retry_config = retry_config

    @retry_pubsub_publish
    def publish(
        self,
        message: DeadLetterMessage,
    ) -> str:
        """Publish a message to the DLQ.

        Args:
            message: DeadLetterMessage to publish

        Returns:
            Message ID

        Raises:
            gcp_exceptions.GoogleAPIError: If publishing fails after retries
        """
        data = message.to_json().encode("utf-8")

        # Add attributes for filtering/routing
        attributes = {
            "source": message.source,
            "error_type": message.error_type,
            "retry_count": str(message.retry_count),
        }

        future = self.publisher.publish(
            self.topic_path,
            data,
            **attributes,
        )

        message_id = future.result()
        logger.info(
            f"Published to DLQ: source={message.source}, "
            f"error_type={message.error_type}, message_id={message_id}"
        )

        return message_id

    def publish_failure(
        self,
        original_event: Dict[str, Any],
        error: Exception,
        source: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Publish a failure event to the DLQ.

        Convenience method that creates DeadLetterMessage and publishes it.

        Args:
            original_event: The original event that failed
            error: The exception that was raised
            source: Source identifier
            context: Additional context about the failure

        Returns:
            Message ID if successful, None if error should not be published
        """
        # Don't publish certain errors that are not retryable
        if self._should_skip_dlq(error):
            logger.warning(f"Skipping DLQ for error type {type(error).__name__}")
            return None

        message = DeadLetterMessage.from_event(
            original_event=original_event,
            error=error,
            source=source,
            context=context,
        )

        try:
            return self.publish(message)
        except Exception as e:
            logger.error(f"Failed to publish to DLQ: {e}")
            # If we can't publish to DLQ, log to stderr as fallback
            print(f"DLQ FALLBACK: {message.to_json()}", file=__import__("sys").stderr)
            return None

    def _should_skip_dlq(self, error: Exception) -> bool:
        """Determine if an error should skip DLQ publishing.

        Args:
            error: The exception to check

        Returns:
            True if error should skip DLQ, False otherwise
        """
        # Skip validation errors - they won't succeed on retry
        non_retryable_errors = (
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        )

        return isinstance(error, non_retryable_errors)

    def publish_batch(
        self,
        messages: List[DeadLetterMessage],
    ) -> Dict[str, Any]:
        """Publish multiple messages to the DLQ.

        Args:
            messages: List of DeadLetterMessage instances

        Returns:
            Dictionary with success_count, failure_count, and any errors
        """
        results = {
            "success_count": 0,
            "failure_count": 0,
            "errors": [],
        }

        for message in messages:
            try:
                self.publish(message)
                results["success_count"] += 1
            except Exception as e:
                results["failure_count"] += 1
                results["errors"].append({
                    "message": message.to_json(),
                    "error": str(e),
                })

        return results


class DeadLetterQueueProcessor:
    """Process messages from the DLQ for retry or analysis."""

    def __init__(
        self,
        project_id: str,
        dlq_subscription_id: str = "pipeline-dlq-sub",
    ):
        """Initialize DLQ processor.

        Args:
            project_id: GCP project ID
            dlq_subscription_id: Pub/Sub subscription ID for the DLQ
        """
        self.project_id = project_id
        self.subscription_path = pubsub_v1.SubscriberClient().subscription_path(
            project_id, dlq_subscription_id
        )
        self.subscriber = pubsub_v1.SubscriberClient()

    def process_message(
        self,
        message: pubsub_v1 SubscriberMessage,
        retry_handler: Optional[callable] = None,
    ) -> bool:
        """Process a single DLQ message.

        Args:
            message: Pub/Sub message
            retry_handler: Optional function to call for retrying the original event

        Returns:
            True if message should be acked, False otherwise
        """
        try:
            data = json.loads(message.data.decode("utf-8"))
            dlq_message = DeadLetterMessage(**data)

            logger.info(
                f"Processing DLQ message: source={dlq_message.source}, "
                f"error_type={dlq_message.error_type}, "
                f"retry_count={dlq_message.retry_count}"
            )

            # Check if we've exceeded max retries
            if dlq_message.retry_count >= dlq_message.max_retries:
                logger.warning(
                    f"Max retries exceeded for message from {dlq_message.source}. "
                    f"Moving to dead storage."
                )
                # TODO: Store to GCS for manual inspection
                return True  # Ack to remove from DLQ

            # Retry the original operation
            if retry_handler:
                retry_handler(dlq_message.original_event)
            else:
                logger.warning("No retry handler provided, cannot retry")

            return True  # Ack the message

        except Exception as e:
            logger.error(f"Failed to process DLQ message: {e}")
            return False  # Nack to keep in DLQ

    def start_consuming(
        self,
        retry_handler: Optional[callable] = None,
        max_messages: int = 100,
        timeout: float = 60.0,
    ):
        """Start consuming messages from the DLQ.

        Args:
            retry_handler: Function to call for retrying failed events
            max_messages: Maximum number of messages to process
            timeout: Timeout in seconds
        """
        def callback(message):
            if self.process_message(message, retry_handler):
                message.ack()
            else:
                message.nack()

        streaming_pull_future = self.subscriber.subscribe(
            self.subscription_path,
            callback=callback,
        )

        logger.info(f"Listening for messages on {self.subscription_path}")

        try:
            streaming_pull_future.result(timeout=timeout)
        except TimeoutError:
            streaming_pull_future.cancel()
        except KeyboardInterrupt:
            streaming_pull_future.cancel()
        finally:
            streaming_pull_future.result()


class DeadLetterStorage:
    """Store permanently failed events to Cloud Storage for analysis."""

    def __init__(
        self,
        bucket_name: str,
        prefix: str = "dlq/permanent-failures",
    ):
        """Initialize DLQ storage.

        Args:
            bucket_name: Cloud Storage bucket name
            prefix: Prefix for stored objects
        """
        from google.cloud import storage

        self.bucket_name = bucket_name
        self.prefix = prefix
        self.client = storage.Client()

    def store_failure(
        self,
        message: DeadLetterMessage,
    ) -> str:
        """Store a permanently failed event to Cloud Storage.

        Args:
            message: DeadLetterMessage to store

        Returns:
            GCS object path
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d/%H%M%S")
        object_name = f"{self.prefix}/{message.source}/{timestamp}.json"

        bucket = self.client.bucket(self.bucket_name)
        blob = bucket.blob(object_name)
        blob.upload_from_string(message.to_json())

        logger.info(f"Stored permanent failure to gs://{self.bucket_name}/{object_name}")
        return f"gs://{self.bucket_name}/{object_name}"
