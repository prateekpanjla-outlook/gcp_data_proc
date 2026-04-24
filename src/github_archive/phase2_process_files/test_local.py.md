## 1. Overview

`test_local.py` is a standalone CLI script for testing Phase 2 processing locally without GCP infrastructure. It reads a GitHub Archive `.json.gz` (or `.json`) file from local disk, runs the transformer and validator, writes the output as NDJSON to a local directory, and prints a summary with record counts, validation results, and a sample of the BigQuery schema.

**Note**: This script references `GitHubEventTransformer` (a class-based API) that has since been refactored into the function-based `transform_chunk()`. It may require updates to run against the current codebase.

## 2. Prerequisites

- **Python** >= 3.11
- **Packages**: `pandas`, `google-cloud-bigquery` (for schema display; via `requirements.txt`)
- **Input data**: A GitHub Archive file in NDJSON format (optionally gzipped), e.g., `2026-03-05-12.json.gz`.
- **No GCP credentials required** -- all I/O is local filesystem.

## 3. Upstream & Downstream Dependencies

| Direction | Component | Relationship |
|-----------|-----------|-------------|
| Upstream | **User / developer** | Invoked manually from the command line for local testing. |
| Downstream | **`processors/transformer.py`** | Calls the transformer to flatten nested JSON (currently references the old `GitHubEventTransformer` class). |
| Downstream | **`validators/file_validator.py`** | Calls `validate_chunk()` on the transformed DataFrame. |
| Downstream | **`schemas/dtype_definitions.py`** | Imports `BIGQUERY_SCHEMA` and `get_bigquery_schema_json()` to display the schema after processing. |
| Downstream | **Local filesystem** | Writes `.ndjson` or `.ndjson.gz` output files to the specified output directory. |

## 4. Code Walkthrough

1. **`read_json_file(file_path)` (lines 34-66)**: Reads a JSON or gzipped JSON file line by line, parsing each line as a JSON object. Handles both `.gz` and plain files. Skips lines with invalid JSON and prints a warning.

2. **`process_file(input_path, output_path, chunksize, validate)` (lines 69-236)**: Main processing function:
   - **Step 1**: Reads input file into a list of dicts using `read_json_file()`.
   - **Step 2**: Converts records to a Pandas DataFrame.
   - **Step 3**: Transforms using `GitHubEventTransformer().transform_chunk(df)` -- flattens nested fields.
   - **Step 4** (optional): Validates the transformed DataFrame with `validate_chunk()`. Prints error and warning counts per field.
   - **Step 5**: Writes output in chunks. Uses gzip compression if the input was gzipped. Supports splitting into multiple part files for very large outputs.
   - **Summary**: Prints a summary table with input/output file paths, record counts, and validation status.
   - **Known issue** (line 216): References an undefined `stats` variable -- this script may not run to completion without fixes.

3. **`main()` (lines 239-295)**: Argument parser with four options:
   - `--input` / `-i`: Required. Path to the input file.
   - `--output` / `-o`: Optional. Output directory (default `/tmp/github_events_processed`).
   - `--chunksize`: Optional. Records per chunk (default 100,000).
   - `--no-validate`: Optional. Skip the validation step.
