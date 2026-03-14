## 1. Overview

`dtype_definitions.py` is the single source of truth for all schema-related constants used in Phase 2 processing. It defines:

- **Input schema** (`GITHUB_EVENT_DTYPES`): Expected pandas dtypes for raw GitHub Archive JSON fields.
- **Output schema** (`OUTPUT_SCHEMA`): Flattened staging schema with prefixed field names.
- **Field mappings** (`ACTOR_FIELD_MAPPING`, `REPO_FIELD_MAPPING`, `ISSUE_FIELD_MAPPING`): Nested-to-flat field name translations used by the transformer.
- **Validation rules** (`REQUIRED_FIELDS`, `VALIDATION_RULES`): Required fields and per-field validation constraints.
- **BigQuery schema** (`BIGQUERY_SCHEMA`): List of `google.cloud.bigquery.SchemaField` objects for table creation, including the nested `RECORD` type for `payload_issue_labels`.
- **Known event types** (`VALID_EVENT_TYPES`): Reference set of GitHub event types (informational only; the pipeline uses pass-through mode).

## 2. Prerequisites

- **Python** >= 3.11
- **Packages**: `google-cloud-bigquery` (for `SchemaField` class, via `requirements.txt`)

## 3. Upstream & Downstream Dependencies

| Direction | Component | Relationship |
|-----------|-----------|-------------|
| Downstream | **`validators/file_validator.py`** | Imports `GITHUB_EVENT_DTYPES` for dtype coercion and `REQUIRED_FIELDS` for null/empty checks. |
| Downstream | **`processors/transformer.py`** | Imports `ACTOR_FIELD_MAPPING`, `REPO_FIELD_MAPPING`, `ISSUE_FIELD_MAPPING` for flattening nested objects. |
| Downstream | **`test_local.py`** | Imports `BIGQUERY_SCHEMA` and `get_bigquery_schema_json()` to display the schema during local test runs. |
| Downstream | **Phase 3 BigQuery loader** | Uses `BIGQUERY_SCHEMA` / `get_bigquery_schema_fields()` when creating or verifying the BigQuery table schema. |

## 4. Code Walkthrough

1. **`VALID_EVENT_TYPES` (lines 20-40)**: A `Set[str]` of known GitHub event types (e.g., `PushEvent`, `IssuesEvent`). Used for documentation only -- the pipeline accepts any event type string.

2. **`GITHUB_EVENT_DTYPES` (lines 51-64)**: Dict mapping raw column names to pandas extension types. Core fields (`id`, `type`, `public`, `created_at`) are typed as `string`/`boolean`. Nested objects (`actor`, `repo`, `payload`, `org`, `other`) are typed as `object`.

3. **`ACTOR_FIELDS` / `REPO_FIELDS` (lines 73-93)**: Dicts mapping flattened output column names to their pandas dtypes. Used for reference and dtype enforcement.

4. **`OUTPUT_SCHEMA` (lines 104-140)**: Complete flattened output schema with all columns and their pandas dtypes. Includes event identifiers, actor fields, repo fields, payload fields, issue labels (`object` type), and ETL metadata.

5. **`OPTIONAL_PAYLOAD_FIELDS` (lines 146-163)**: Dict mapping event types to their specific optional payload fields. Used for documentation of which fields are expected per event type.

6. **`REQUIRED_FIELDS` (lines 169-175)**: List of fields that must be present and non-null in every record: `id`, `type`, `created_at`, `actor`, `repo`.

7. **Field mappings (lines 181-207)**:
   - `ACTOR_FIELD_MAPPING`: Maps nested `actor.{field}` keys to `actor_{field}` output columns (8 fields including optional `type` and `site_admin`).
   - `REPO_FIELD_MAPPING`: Maps `repo.{field}` to `repo_{field}` (3 fields).
   - `ISSUE_FIELD_MAPPING`: Maps `payload.issue.labels` to `payload_issue_labels`.

8. **`ValidationRule` dataclass and `VALIDATION_RULES` (lines 213-246)**: Defines per-field validation constraints including dtype, nullability, allowed values, and min/max ranges. Used by `validate_output_schema()` for record-level validation.

9. **`BIGQUERY_SCHEMA` (lines 273-327)**: List of `SchemaField` objects defining the BigQuery table schema. Notable: `payload_issue_labels` is a `REPEATED RECORD` with sub-fields (`id`, `node_id`, `url`, `name`, `color`, `default`, `description`). ETL metadata fields (`etl_create_ts`, `etl_create_id`) are included.

10. **Helper functions**:
    - `_schema_field_to_dict()` (lines 330-343): Recursively converts `SchemaField` to a dict for JSON serialisation.
    - `get_bigquery_schema_json()` (lines 346-360): Returns the schema as a JSON string for use with `bq load --schema_file`.
    - `get_bigquery_schema_fields()` (lines 363-383): Returns a copy of `BIGQUERY_SCHEMA` for direct use with the BigQuery Python API.
    - `is_valid_event_type()` (lines 389-396): Checks if an event type is in `VALID_EVENT_TYPES` (informational only).
    - `get_optional_fields_for_event()` (lines 399-401): Returns optional payload fields for a given event type.
    - `validate_output_schema()` (lines 404-451): Validates a single record dict against `VALIDATION_RULES`, checking nullability, dtype, allowed values, and min/max.
