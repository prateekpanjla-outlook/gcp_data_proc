## 1. Overview

`file_validator.py` provides two levels of validation for Phase 2 processing:

1. **File name validation** (`validate_file`): Checks that the file name matches the GitHub Archive naming convention `YYYY-MM-DD-H.json.gz` with valid date/time components.
2. **Chunk data validation** (`validate_chunk`): Validates a Pandas DataFrame chunk by coercing dtypes, checking required fields, verifying ID ranges, and filtering out rows with future timestamps. Returns only the valid rows.

## 2. Prerequisites

- **Python** >= 3.11
- **Packages**: `pandas` (via `requirements.txt`)
- **Schema definitions**: Imports `GITHUB_EVENT_DTYPES` and `REQUIRED_FIELDS` from `schemas/dtype_definitions.py`.

## 3. Upstream & Downstream Dependencies

| Direction | Component | Relationship |
|-----------|-----------|-------------|
| Upstream | **`processors/file_processor.py`** | Calls `validate_file(file_name)` before processing and `validate_chunk(chunk_df)` on each chunk. |
| Upstream | **`schemas/dtype_definitions.py`** | Provides `GITHUB_EVENT_DTYPES` (expected column dtypes) and `REQUIRED_FIELDS` (columns that must be present and non-null). |
| Downstream | **`processors/file_processor.py`** | Returns `ChunkValidationResult.valid_df` which is passed to the transformer. |

## 4. Code Walkthrough

1. **`FILE_NAME_PATTERN` (line 21)**: Compiled regex `^\d{4}-\d{2}-\d{2}-\d{1,2}\.json\.gz$`. GitHub Archive uses single-digit hours (0-9) for hours 0-9, so the hour group is `\d{1,2}`.

2. **Result dataclasses (lines 27-43)**:
   - `ValidationResult`: Boolean `is_valid` plus lists of `errors` and `warnings` (for file name validation).
   - `ChunkValidationResult`: Boolean `is_valid`, the filtered `valid_df`, `records_in`/`records_out` counts, and dicts of `errors`/`warnings` keyed by field name with occurrence counts.

3. **`validate_file(file_name)` (lines 49-105)**:
   - Checks `.gz` extension, then `.json.gz` extension.
   - Matches against `FILE_NAME_PATTERN`.
   - Parses year, month, day, hour and validates ranges (year 2011-2100, month 1-12, day 1-31, hour 0-23).
   - Returns `ValidationResult`.

4. **`validate_chunk(df)` (lines 111-217)**: Single-pass validation with three phases:
   - **Phase 1 -- Dtype coercion (lines 129-141)**: Iterates over `GITHUB_EVENT_DTYPES` and casts columns in-place. Tracks coercion-induced nulls as errors.
   - **Phase 2 -- Boolean mask construction (lines 143-204)**:
     - Required fields (`id`, `type`, `created_at`, `actor`, `repo`): marks rows as invalid if any required field is null or empty.
     - ID fields (`actor_id`, `repo_id`): marks rows invalid if null or negative.
     - `event_id`: marks rows invalid if null or empty.
     - Future timestamps: parses `created_at` and marks rows invalid if the timestamp is in the future.
   - **Phase 3 -- Single filter (lines 206-217)**: Applies the accumulated boolean mask once with `df[mask]` to produce `valid_df`, avoiding multiple copy operations. Returns `ChunkValidationResult` with the filtered DataFrame and all error/warning counts.
