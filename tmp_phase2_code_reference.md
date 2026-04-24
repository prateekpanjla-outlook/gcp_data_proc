# Phase 2 Code Reference (as of 2026-03-14)

| # | File | Lines | Purpose | Status |
|---|------|------:|---------|--------|
| 1 | [main.py](src/github_archive/phase2_process_files/main.py) | 170 | Flask app, Eventarc handler, health endpoint, size gate | refactored |
| 2 | [file_processor.py](src/github_archive/phase2_process_files/processors/file_processor.py) | 263 | Core processing: download → validate → transform → write | refactored |
| 3 | [transformer.py](src/github_archive/phase2_process_files/processors/transformer.py) | 233 | Flattens nested JSON (actor/repo/payload → flat cols) | refactored |
| 4 | [dtype_definitions.py](src/github_archive/phase2_process_files/schemas/dtype_definitions.py) | 474 | Schema definitions, BQ schema, field mappings, validation rules | untouched |
| 5 | [test_local.py](src/github_archive/phase2_process_files/test_local.py) | 295 | Local testing script for end-to-end validation | refactored |
| 6 | [file_validator.py](src/github_archive/phase2_process_files/validators/file_validator.py) | 219 | All validation: filename format + chunk data (dtypes, fields, IDs, timestamps) | merged |
| 7 | [ndjson_writer.py](src/github_archive/phase2_process_files/writers/ndjson_writer.py) | 488 | Writes DataFrames as NDJSON to GCS (gzipped) | untouched |
| | `__init__.py` (x4) | 0 | empty | — |
| | **Total** | **2,142** | | |

## Deleted Files

| File | Lines | Reason |
|------|------:|--------|
| file_splitter.py | 552 | Removed split-then-re-trigger pattern (race condition, debugging complexity) |
| dtype_validator.py | 125 | Merged into file_data_validator.py |
| value_validator.py | 407 | Merged into file_data_validator.py |
| file_data_validator.py | 133 | Merged into file_validator.py |
| logger.py | 11 | Inlined into main.py and file_processor.py (stdlib logging) |
| gcs_client.py | 447 | Inlined into main.py and file_processor.py (google.cloud.storage SDK) |

## Processing Flow

```
Eventarc event (file landed in GCS)
  → main.py (POST /)
    → storage_client.bucket().blob().reload()  # size check → 413 if >50MB
    → file_processor.process_file()
      → file_validator.validate_file()           # check filename format
      → blob.download_to_filename() + gzip       # download + decompress
      → pd.read_json(chunksize=100K)             # chunked reading
        per chunk:
          → file_validator.validate_chunk()        # dtypes + value checks (single mask)
          → transformer.transform_chunk()          # flatten nested JSON
          → ndjson_writer.write_dataframe_to_gcs() # write to staging
```
