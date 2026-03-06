"""
Schema definitions for GitHub Archive event processing.

Defines expected dtypes, validation rules, and output schema for
GitHub Archive events processed from Phase 1 landing zone to Phase 2 staging.
"""

from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass
from datetime import datetime


# =============================================================================
# VALID EVENT TYPES (GitHub Archive)
# =============================================================================
VALID_EVENT_TYPES: Set[str] = {
    'PushEvent',
    'CreateEvent',
    'DeleteEvent',
    'WatchEvent',
    'IssuesEvent',
    'IssueCommentEvent',
    'PullRequestEvent',
    'PullRequestReviewEvent',
    'PullRequestReviewCommentEvent',
    'ForkEvent',
    'ReleaseEvent',
    'MemberEvent',
    'GollumEvent',
    'CommitCommentEvent',
    'TeamAddEvent',
    'ProtectBranchEvent',
}


# =============================================================================
# INPUT SCHEMA (GitHub Archive - Nested JSON)
# =============================================================================
GITHUB_EVENT_DTYPES: Dict[str, str] = {
    # Core fields
    'id': 'string',
    'type': 'string',
    'public': 'boolean',
    'created_at': 'string',
    # Nested objects (will be extracted)
    'actor': 'object',
    'repo': 'object',
    'payload': 'object',
    # Optional fields
    'org': 'object',
    'other': 'object',
}


# =============================================================================
# ACTOR FIELD DEFINITIONS
# =============================================================================
ACTOR_FIELDS: Dict[str, str] = {
    'actor_id': 'int64',
    'actor_login': 'string',
    'actor_avatar_url': 'string',
    'actor_gravatar_id': 'string',
    'actor_type': 'string',
    'actor_url': 'string',
    'actor_site_admin': 'boolean',
}


# =============================================================================
# REPO FIELD DEFINITIONS
# =============================================================================
REPO_FIELDS: Dict[str, str] = {
    'repo_id': 'int64',
    'repo_name': 'string',
    'repo_url': 'string',
}


# =============================================================================
# OUTPUT SCHEMA (Flattened for Staging - NDJSON)
# =============================================================================
OUTPUT_SCHEMA: Dict[str, str] = {
    # Event identifiers
    'event_id': 'string',
    'event_type': 'string',
    'created_at': 'string',

    # Actor fields
    'actor_id': 'int64',
    'actor_login': 'string',
    'actor_avatar_url': 'string',
    'actor_gravatar_id': 'string',
    'actor_type': 'string',
    'actor_url': 'string',
    'actor_site_admin': 'boolean',

    # Repository fields
    'repo_id': 'int64',
    'repo_name': 'string',
    'repo_url': 'string',

    # Event metadata
    'public': 'boolean',

    # Payload fields (common across event types)
    'payload_ref': 'string',
    'payload_ref_type': 'string',
    'payload_push_id': 'int64',
    'payload_size': 'int64',
    'payload_distinct_size': 'int64',
    'payload_head': 'string',
    'payload_before': 'string',
}


# =============================================================================
# OPTIONAL PAYLOAD FIELDS (for specific event types)
# =============================================================================
OPTIONAL_PAYLOAD_FIELDS: Dict[str, List[str]] = {
    'PushEvent': ['ref', 'ref_type', 'push_id', 'size', 'distinct_size', 'head', 'before'],
    'CreateEvent': ['ref', 'ref_type', 'master_branch', 'description'],
    'DeleteEvent': ['ref', 'ref_type', 'pusher_type'],
    'WatchEvent': [],
    'IssuesEvent': ['action', 'issue'],
    'IssueCommentEvent': ['action', 'issue', 'comment'],
    'PullRequestEvent': ['action', 'pull_request'],
    'PullRequestReviewEvent': ['action', 'review', 'pull_request'],
    'PullRequestReviewCommentEvent': ['action', 'comment', 'pull_request'],
    'ForkEvent': ['forkee'],
    'ReleaseEvent': ['action', 'release'],
    'MemberEvent': ['action', 'member'],
    'GollumEvent': ['pages'],
    'CommitCommentEvent': ['comment'],
    'TeamAddEvent': ['team', 'repo'],
    'ProtectBranchEvent': ['protected_branch'],
}


# =============================================================================
# REQUIRED FIELDS (validation)
# =============================================================================
REQUIRED_FIELDS: List[str] = [
    'id',
    'type',
    'created_at',
    'actor',
    'repo',
]


# =============================================================================
# FIELD MAPPINGS (nested -> flattened)
# =============================================================================
ACTOR_FIELD_MAPPING: Dict[str, str] = {
    'id': 'actor_id',
    'login': 'actor_login',
    'avatar_url': 'actor_avatar_url',
    'gravatar_id': 'actor_gravatar_id',
    'type': 'actor_type',
    'url': 'actor_url',
    'site_admin': 'actor_site_admin',
}


REPO_FIELD_MAPPING: Dict[str, str] = {
    'id': 'repo_id',
    'name': 'repo_name',
    'url': 'repo_url',
}


# =============================================================================
# VALIDATION RULES
# =============================================================================
@dataclass
class ValidationRule:
    """Defines a validation rule for a field."""
    field: str
    dtype: str
    nullable: bool = False
    allowed_values: Optional[Set[Any]] = None
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    pattern: Optional[str] = None


VALIDATION_RULES: List[ValidationRule] = [
    # Event ID validation
    ValidationRule(field='event_id', dtype='string', nullable=False),

    # Event type validation
    ValidationRule(
        field='event_type',
        dtype='string',
        nullable=False,
        allowed_values=VALID_EVENT_TYPES
    ),

    # Timestamp validation (ISO 8601 format)
    ValidationRule(field='created_at', dtype='string', nullable=False),

    # Actor fields
    ValidationRule(field='actor_id', dtype='int64', nullable=False, min_value=1),
    ValidationRule(field='actor_login', dtype='string', nullable=False),

    # Repo fields
    ValidationRule(field='repo_id', dtype='int64', nullable=False, min_value=1),
    ValidationRule(field='repo_name', dtype='string', nullable=False),

    # Public flag
    ValidationRule(field='public', dtype='boolean', nullable=True),
]


# =============================================================================
# PROCESSING CONFIGURATION
# =============================================================================
@dataclass
class ProcessingConfig:
    """Configuration for event processing."""
    # Chunked processing
    chunksize: int = 100_000

    # File size threshold (MB) - above this, split the file
    file_size_threshold_mb: int = 500

    # Validation
    strict_mode: bool = False  # If True, abort on any validation error
    max_error_rate: float = 0.10  # Max 10% errors before aborting

    # Output
    output_compression: bool = True
    output_format: str = 'ndjson'  # ndjson or json


# Default configuration
DEFAULT_CONFIG = ProcessingConfig()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def is_valid_event_type(event_type: str) -> bool:
    """Check if an event type is valid."""
    return event_type in VALID_EVENT_TYPES


def get_optional_fields_for_event(event_type: str) -> List[str]:
    """Get optional payload fields for a specific event type."""
    return OPTIONAL_PAYLOAD_FIELDS.get(event_type, [])


def validate_output_schema(record: Dict[str, Any]) -> List[str]:
    """
    Validate a record against the output schema.

    Returns a list of validation errors (empty if valid).
    """
    errors: List[str] = []

    for rule in VALIDATION_RULES:
        value = record.get(rule.field)

        # Check nullability
        if value is None:
            if not rule.nullable:
                errors.append(f"Field '{rule.field}' is required but is null")
            continue

        # Check dtype (basic check)
        expected_type = rule.dtype
        if expected_type == 'int64':
            if not isinstance(value, int):
                errors.append(f"Field '{rule.field}' should be int64, got {type(value).__name__}")
        elif expected_type == 'string':
            if not isinstance(value, str):
                errors.append(f"Field '{rule.field}' should be string, got {type(value).__name__}")
        elif expected_type == 'boolean':
            if not isinstance(value, bool):
                errors.append(f"Field '{rule.field}' should be boolean, got {type(value).__name__}")

        # Check allowed values
        if rule.allowed_values is not None and value not in rule.allowed_values:
            errors.append(
                f"Field '{rule.field}' value '{value}' not in allowed values: {rule.allowed_values}"
            )

        # Check min/max for numeric values
        if rule.min_value is not None and isinstance(value, (int, float)):
            if value < rule.min_value:
                errors.append(f"Field '{rule.field}' value {value} below minimum {rule.min_value}")

        if rule.max_value is not None and isinstance(value, (int, float)):
            if value > rule.max_value:
                errors.append(f"Field '{rule.field}' value {value} above maximum {rule.max_value}")

    return errors
