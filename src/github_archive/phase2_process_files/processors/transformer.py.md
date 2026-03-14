## 1. Overview

`transformer.py` flattens the nested GitHub Archive JSON structure into a flat staging schema suitable for NDJSON output and downstream BigQuery loading. It extracts fields from nested objects (`actor`, `repo`, `payload`, `payload.issue`) into top-level columns, applies dtype coercion, and adds ETL metadata columns (`etl_create_ts`, `etl_create_id`).

The module exposes `transform_chunk()` as the public entry point and returns a `TransformationResult` dataclass.

## 2. Prerequisites

- **Python** >= 3.11
- **Packages**: `pandas` (via `requirements.txt`)
- **Schema definitions**: Imports `ACTOR_FIELD_MAPPING`, `REPO_FIELD_MAPPING`, and `ISSUE_FIELD_MAPPING` from `schemas/dtype_definitions.py`. The `PAYLOAD_FIELD_MAPPING` is defined locally because payload fields vary by event type.

## 3. Upstream & Downstream Dependencies

| Direction | Component | Relationship |
|-----------|-----------|-------------|
| Upstream | **`processors/file_processor.py`** | Calls `transform_chunk(working_df)` on each validated chunk. |
| Upstream | **`schemas/dtype_definitions.py`** | Provides `ACTOR_FIELD_MAPPING`, `REPO_FIELD_MAPPING`, `ISSUE_FIELD_MAPPING` -- the source-to-target field name mappings. |
| Downstream | **`writers/ndjson_writer.py`** | The flattened DataFrame from `TransformationResult.df` is passed to the writer. |

## 4. Code Walkthrough

1. **`TransformationResult` dataclass (lines 22-28)**: Holds the flattened `df`, `records_in`, `records_out`, and `error_count`.

2. **`PAYLOAD_FIELD_MAPPING` (lines 34-42)**: Maps raw payload keys (`ref`, `ref_type`, `push_id`, `size`, `distinct_size`, `head`, `before`) to prefixed output names (`payload_ref`, etc.). Defined here rather than in `dtype_definitions.py` because payload fields vary by event type.

3. **Helper functions**:
   - `_safe_get(obj, field, default)` (lines 48-52): Safely extracts a key from a dict, returning `default` if the object is not a dict.
   - `_merge_extracted(result, source_df, source_columns, field_mapping)` (lines 55-76): For each source column (e.g., `actor`), applies `_safe_get` per row to extract each mapped field into a new column on the result DataFrame. If the source column is missing, fills target columns with `None`.
   - `_merge_extracted_nested(result, source_df, path_parts, field_mapping)` (lines 79-111): Navigates multiple nesting levels (e.g., `['payload', 'issue']`) by chaining `.apply(_safe_get)` calls, then extracts mapped fields from the final nested object.

4. **`flatten_schema(df)` (lines 114-145)**: Orchestrates the flattening:
   - Creates a new empty DataFrame.
   - Maps core fields: `id` -> `event_id`, `type` -> `event_type`, `created_at`, `public`.
   - Calls `_merge_extracted` for `actor`, `repo`, and `payload` columns.
   - Calls `_merge_extracted_nested` for the two-level path `payload.issue` to extract `ISSUE_FIELD_MAPPING` (currently just `labels` -> `payload_issue_labels`).
   - Adds `etl_create_ts` (current UTC timestamp) and `etl_create_id` (`"GITHUB_PROCESSOR"`).

5. **`_ensure_dtypes(df)` (lines 148-182)**: Casts columns to their target pandas extension types: `string` for text, `Int64` (nullable) for integers, `boolean` for booleans. This ensures clean serialisation to NDJSON.

6. **`transform_chunk(df)` (lines 185-220)**: Public entry point. Calls `flatten_schema`, then `_ensure_dtypes`. On exception, returns an empty DataFrame with `error_count` equal to `records_in`.
