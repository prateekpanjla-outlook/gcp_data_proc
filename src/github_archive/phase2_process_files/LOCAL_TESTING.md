# Local Testing Guide

Test Phase 2 processing locally without Docker or GCP infrastructure.

## Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt
```

## Running the Local Test

### Basic Usage

```bash
cd src/github_archive/phase2_process_files
python test_local.py --input path/to/input.json.gz --output /tmp/output
```

### Arguments

| Argument | Short | Required | Default | Description |
|----------|-------|----------|---------|-------------|
| `--input` | `-i` | Yes | - | Input file path (JSON or JSON.gz) |
| `--output` | `-o` | No | `/tmp/github_events_processed` | Output directory |
| `--chunksize` | - | No | 100000 | Records per chunk |
| `--no-validate` | - | No | - | Skip validation step |

### Examples

```bash
# Process a gzipped GitHub Archive file
python test_local.py -i data/github_archive/2026-03-05-12.json.gz -o /tmp/output

# Process with custom chunk size
python test_local.py -i input.json.gz --chunksize 50000

# Process without validation (faster)
python test_local.py -i input.json.gz --no-validate

# Process uncompressed JSON
python test_local.py -i data/events.json -o /tmp/events
```

## What It Does

1. **Reads** input file (JSON or gzipped JSON)
2. **Converts** to pandas DataFrame
3. **Transforms** nested JSON to flattened schema
4. **Validates** data (required fields, timestamps, IDs)
5. **Writes** output as NDJSON (optionally gzipped)

## Input Format

Input files should be newline-delimited JSON (NDJSON):

```json
{"id": "123", "type": "PushEvent", "actor": {...}, "repo": {...}, "payload": {...}}
{"id": "124", "type": "IssuesEvent", "actor": {...}, "repo": {...}, "payload": {...}}
```

## Output Format

Output is flattened NDJSON ready for BigQuery loading:

```json
{"event_id": "123", "event_type": "PushEvent", "actor_id": 1, "actor_login": "user", ...}
{"event_id": "124", "event_type": "IssuesEvent", "actor_id": 2, "actor_login": "dev", ...}
```

## Output Schema

The output matches the BigQuery schema defined in `schemas/dtype_definitions.py`:

- Event identifiers: event_id, event_type, created_at
- Actor fields: actor_id, actor_login, actor_display_login, etc.
- Repository fields: repo_id, repo_name, repo_url
- Payload fields: payload_ref, payload_ref_type, payload_push_id, etc.
- Issue labels: payload_issue_labels (JSON array)

## Troubleshooting

### Import Error: No module named 'google.cloud.bigquery'

The local test script uses the transformer which imports the schema. The schema now requires `google-cloud-bigquery` as a dependency. Install it:

```bash
pip install google-cloud-bigquery>=3.0.0
```

### Memory Issues with Large Files

Reduce the chunk size:

```bash
python test_local.py -i large_file.json.gz --chunksize 10000
```

### File Not Found

Use absolute paths or ensure you're in the correct directory:

```bash
# From project root
python src/github_archive/phase2_process_files/test_local.py -i data/file.json.gz

# Or use absolute path
python test_local.py -i /full/path/to/file.json.gz
```
