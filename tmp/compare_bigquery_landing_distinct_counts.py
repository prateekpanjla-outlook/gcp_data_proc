#!/usr/bin/env python3
"""
Compare distinct column counts between BigQuery and Landing Bucket files.

This script:
1. Queries BigQuery for COUNT(DISTINCT column) for each column
2. Samples files from the landing bucket and computes distinct counts
3. Compares results and reports discrepancies

Usage:
    python compare_bigquery_landing_distinct_counts.py
"""

import os
import json
import gzip
import logging
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict
from datetime import datetime, timedelta, timezone

try:
    from google.cloud import bigquery
    from google.cloud import storage
    import pandas as pd
except ImportError as e:
    print(f"Missing required library: {e}")
    print("Install with: pip install google-cloud-bigquery google-cloud-storage pandas")
    exit(1)

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/distinct_count_comparison.log')
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================
PROJECT_ID = "dev-dataprocessing-489305"
DATASET_ID = "github_archive_test"  # Using test dataset
TABLE_ID = "events_2026_03_07_7"  # Test table
LANDING_BUCKET = "dev-dataprocessing-489305-dev-github-archive-landing"

# Field mapping: Landing bucket (nested JSON) -> BigQuery (flattened)
LANDING_TO_BQ_FIELD_MAPPING = {
    # Core fields
    "id": "event_id",
    "type": "event_type",
    "created_at": "created_at",
    "public": "public",

    # Actor fields (nested)
    "actor.id": "actor_id",
    "actor.login": "actor_login",
    "actor.display_login": "actor_display_login",
    "actor.gravatar_id": "actor_gravatar_id",
    "actor.url": "actor_url",
    "actor.avatar_url": "actor_avatar_url",
    "actor.type": "actor_type",
    "actor.site_admin": "actor_site_admin",

    # Repo fields (nested)
    "repo.id": "repo_id",
    "repo.name": "repo_name",
    "repo.url": "repo_url",

    # Payload fields (nested)
    "payload.ref": "payload_ref",
    "payload.ref_type": "payload_ref_type",
    "payload.push_id": "payload_push_id",
    "payload.size": "payload_size",
    "payload.distinct_size": "payload_distinct_size",
    "payload.head": "payload_head",
    "payload.before": "payload_before",
}

# Fields to analyze (both landing and BQ)
FIELDS_TO_ANALYZE = [
    # Core
    ("event_id", "id"),
    ("event_type", "type"),
    ("created_at", "created_at"),
    ("public", "public"),

    # Actor
    ("actor_id", "actor.id"),
    ("actor_login", "actor.login"),
    ("actor_display_login", "actor.display_login"),
    ("actor_gravatar_id", "actor.gravatar_id"),
    ("actor_url", "actor.url"),
    ("actor_avatar_url", "actor.avatar_url"),
    ("actor_type", "actor.type"),
    ("actor_site_admin", "actor.site_admin"),

    # Repo
    ("repo_id", "repo.id"),
    ("repo_name", "repo.name"),
    ("repo_url", "repo.url"),

    # Payload
    ("payload_ref", "payload.ref"),
    ("payload_ref_type", "payload.ref_type"),
    ("payload_push_id", "payload.push_id"),
    ("payload_size", "payload.size"),
    ("payload_distinct_size", "payload.distinct_size"),
    ("payload_head", "payload.head"),
    ("payload_before", "payload.before"),
]

# =============================================================================
# BIGQUERY FUNCTIONS
# =============================================================================
def get_bq_client() -> bigquery.Client:
    """Get BigQuery client."""
    logger.info("Creating BigQuery client...")
    return bigquery.Client(project=PROJECT_ID)


def get_table_schema(client: bigquery.Client) -> List[bigquery.SchemaField]:
    """Get table schema from BigQuery."""
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    try:
        table = client.get_table(table_ref)
        return table.schema
    except Exception as e:
        logger.error(f"Could not get table schema: {e}")
        return []


def get_bq_distinct_counts(client: bigquery.Client) -> Dict[str, int]:
    """
    Get COUNT(DISTINCT column) for all columns in BigQuery table.

    Returns:
        Dict mapping column name to distinct count
    """
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    logger.info(f"Querying BigQuery table: {table_ref}")

    # First get the schema
    try:
        table = client.get_table(table_ref)
        columns = [field.name for field in table.schema]
    except Exception as e:
        logger.error(f"Error getting BigQuery table: {e}")
        logger.error(f"Table {table_ref} may not exist yet.")
        return {}

    logger.info(f"Found {len(columns)} columns in BigQuery table")

    distinct_counts = {}

    # Query distinct counts for each column
    for col in columns:
        try:
            query = f"""
            SELECT COUNT(DISTINCT {col}) as distinct_count
            FROM `{table_ref}`
            """

            # Skip REPEATED RECORD fields
            if col == "payload_issue_labels":
                logger.info(f"Skipping REPEATED RECORD field: {col}")
                continue

            logger.debug(f"Querying distinct count for column: {col}")
            job = client.query(query)
            result = job.result()

            for row in result:
                distinct_counts[col] = row.distinct_count
                logger.info(f"  {col}: {row.distinct_count:,} distinct values")

        except Exception as e:
            logger.error(f"Error querying column {col}: {e}")
            distinct_counts[col] = None

    logger.info(f"Completed BigQuery distinct count query: {len([v for v in distinct_counts.values() if v is not None])} columns processed")
    return distinct_counts


def list_bq_datasets(client: bigquery.Client) -> List[str]:
    """List all datasets in the project."""
    datasets = list(client.list_datasets())
    return [d.dataset_id for d in datasets]


def list_bq_tables(client: bigquery.Client, dataset_id: str) -> List[str]:
    """List all tables in a dataset."""
    tables = list(client.list_tables(f"{PROJECT_ID}.{dataset_id}"))
    return [t.table_id for t in tables]


# =============================================================================
# LANDING BUCKET FUNCTIONS
# =============================================================================
def get_gcs_client() -> storage.Client:
    """Get GCS client."""
    logger.info("Creating GCS client...")
    return storage.Client(project=PROJECT_ID)


def list_landing_bucket_files(client: storage.Client, prefix: str = "", max_files: int = 10) -> List[storage.Blob]:
    """
    List files in the landing bucket.

    Args:
        client: GCS client
        prefix: Optional prefix to filter files
        max_files: Maximum number of files to return

    Returns:
        List of GCS blobs
    """
    logger.info(f"Listing files in bucket: {LANDING_BUCKET} with prefix: '{prefix}'")
    bucket = client.bucket(LANDING_BUCKET)
    blobs = list(bucket.list_blobs(prefix=prefix, max_results=max_files))
    logger.info(f"Found {len(blobs)} files")
    return blobs


def extract_nested_value(obj: Any, path: str) -> Any:
    """
    Extract a value from a nested dict using dot notation.

    Args:
        obj: The object (dict) to extract from
        path: Dot-notation path (e.g., "actor.id")

    Returns:
        The value at the path, or None if not found
    """
    if not isinstance(obj, dict):
        return None

    parts = path.split(".")
    current = obj

    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current


def read_blob_content(blob: storage.Blob) -> str:
    """
    Read blob content, handling gzip compression.

    Args:
        blob: GCS blob to read

    Returns:
        Content as string
    """
    logger.debug(f"Downloading blob: {blob.name}")
    content = blob.download_as_bytes()
    logger.debug(f"Downloaded {len(content)} bytes")

    # Check if it's gzipped
    if content[:2] == b'\x1f\x8b':
        try:
            decompressed = gzip.decompress(content).decode('utf-8')
            logger.debug(f"Decompressed to {len(decompressed)} characters")
            return decompressed
        except Exception as e:
            logger.error(f"Error decompressing gzip: {e}")
            return ""
    else:
        decoded = content.decode('utf-8')
        logger.debug(f"Decoded to {len(decoded)} characters (not gzipped)")
        return decoded


def get_landing_distinct_counts(client: storage.Client, max_files: int = 10, prefix: str = "") -> Dict[str, int]:
    """
    Get distinct counts from landing bucket files.

    Samples files from the landing bucket and computes distinct counts
    for comparable fields.

    Args:
        client: GCS client
        max_files: Maximum number of files to sample
        prefix: Optional prefix to filter files (e.g., "github-archive/raw/")

    Returns:
        Dict mapping field path to distinct count
    """
    blobs = list_landing_bucket_files(client, prefix=prefix, max_files=max_files)

    # Filter to only include JSON/NDJSON files
    json_blobs = [b for b in blobs if b.name.endswith(('.json', '.ndjson', '.json.gz', '.ndjson.gz'))]

    if not json_blobs:
        logger.warning(f"No JSON files found in landing bucket: {LANDING_BUCKET} (prefix: '{prefix}')")
        return {}

    logger.info(f"Sampling {len(json_blobs)} JSON files from landing bucket")

    # Storage for distinct value sets
    distinct_values = defaultdict(set)
    total_records = 0

    for blob in json_blobs:
        logger.info(f"Processing: {blob.name} (size: {blob.size} bytes)")

        try:
            # Download and parse JSON lines
            content = read_blob_content(blob)
            lines = content.strip().split("\n")
            logger.info(f"  Read {len(lines):,} lines from file")

            for line in lines:
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)
                    total_records += 1

                    # Extract each field
                    for bq_field, landing_path in FIELDS_TO_ANALYZE:
                        value = extract_nested_value(record, landing_path)

                        # Convert to string for counting (but preserve None)
                        if value is None:
                            value = "__NULL__"
                        else:
                            value = str(value)

                        distinct_values[bq_field].add(value)

                except json.JSONDecodeError:
                    continue

        except Exception as e:
            logger.error(f"  Error processing file {blob.name}: {e}")

    logger.info(f"Total records processed: {total_records:,}")

    # Convert sets to counts
    distinct_counts = {}
    for field, values in distinct_values.items():
        # Count __NULL__ separately
        null_count = values.discard("__NULL__") or 0
        distinct_counts[field] = len(values)
        logger.info(f"  {field}: {len(values):,} distinct values (from landing bucket)")

    return distinct_counts


# =============================================================================
# COMPARISON FUNCTIONS
# =============================================================================
def compare_distinct_counts(bq_counts: Dict[str, int], landing_counts: Dict[str, int]) -> List[Dict[str, Any]]:
    """
    Compare distinct counts between BigQuery and landing bucket.

    Args:
        bq_counts: Dict of BigQuery distinct counts
        landing_counts: Dict of landing bucket distinct counts

    Returns:
        List of comparison result dicts
    """
    results = []

    # Get all unique field names
    all_fields = set(bq_counts.keys()) | set(landing_counts.keys())

    for field in sorted(all_fields):
        bq_count = bq_counts.get(field)
        landing_count = landing_counts.get(field)

        result = {
            "field": field,
            "bq_distinct": bq_count,
            "landing_distinct": landing_count,
        }

        # Calculate comparison if both values exist
        if bq_count is not None and landing_count is not None:
            # Check for match (allowing for sampling differences)
            if bq_count == landing_count:
                result["status"] = "MATCH"
                result["diff"] = 0
                result["diff_percent"] = 0.0
            elif bq_count > landing_count:
                result["status"] = "BQ_HIGHER"
                result["diff"] = bq_count - landing_count
                result["diff_percent"] = ((bq_count - landing_count) / landing_count * 100) if landing_count > 0 else 0
            else:
                result["status"] = "LANDING_HIGHER"
                result["diff"] = landing_count - bq_count
                result["diff_percent"] = ((landing_count - bq_count) / bq_count * 100) if bq_count > 0 else 0
        else:
            result["status"] = "MISSING_DATA"
            result["diff"] = None
            result["diff_percent"] = None

        results.append(result)

    return results


def print_comparison_report(results: List[Dict[str, Any]]):
    """Print comparison report."""
    print("\n" + "="*80)
    print("DISTINCT COUNT COMPARISON REPORT")
    print("="*80)
    print(f"BigQuery Project: {PROJECT_ID}")
    print(f"BigQuery Table: {DATASET_ID}.{TABLE_ID}")
    print(f"Landing Bucket: {LANDING_BUCKET}")
    print(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    print("="*80 + "\n")

    # Group by status
    matches = [r for r in results if r["status"] == "MATCH"]
    bq_higher = [r for r in results if r["status"] == "BQ_HIGHER"]
    landing_higher = [r for r in results if r["status"] == "LANDING_HIGHER"]
    missing = [r for r in results if r["status"] == "MISSING_DATA"]

    print(f"Summary:")
    print(f"  Total fields compared: {len(results)}")
    print(f"  Exact matches: {len(matches)}")
    print(f"  BQ has more distinct values: {len(bq_higher)}")
    print(f"  Landing has more distinct values: {len(landing_higher)}")
    print(f"  Missing data for comparison: {len(missing)}")
    print()

    # Print exact matches
    if matches:
        print("EXACT MATCHES:")
        for r in matches:
            print(f"  ✓ {r['field']}: {r['bq_distinct']:,} distinct values")
        print()

    # Print BQ higher
    if bq_higher:
        print("BQ HAS MORE DISTINCT VALUES (Expected - more data in BQ):")
        for r in sorted(bq_higher, key=lambda x: x["diff_percent"], reverse=True):
            print(f"  • {r['field']}:")
            print(f"      BQ: {r['bq_distinct']:,} | Landing: {r['landing_distinct']:,} | Diff: +{r['diff']:,} (+{r['diff_percent']:.1f}%)")
        print()

    # Print landing higher
    if landing_higher:
        print("LANDING HAS MORE DISTINCT VALUES (Investigate - data loss?):")
        for r in sorted(landing_higher, key=lambda x: x["diff_percent"], reverse=True):
            print(f"  ⚠ {r['field']}:")
            print(f"      BQ: {r['bq_distinct']:,} | Landing: {r['landing_distinct']:,} | Diff: -{r['diff']:,} (-{r['diff_percent']:.1f}%)")
        print()

    # Print missing
    if missing:
        print("MISSING DATA (Cannot compare):")
        for r in missing:
            print(f"  ? {r['field']}: BQ={r['bq_distinct']}, Landing={r['landing_distinct']}")
        print()

    print("="*80)


# =============================================================================
# MAIN
# =============================================================================
def main():
    """Main function."""
    logger.info("="*80)
    logger.info("Starting distinct count comparison between BigQuery and Landing Bucket")
    logger.info(f"Project: {PROJECT_ID}")
    logger.info(f"Landing Bucket: {LANDING_BUCKET}")
    logger.info(f"BigQuery Table: {DATASET_ID}.{TABLE_ID}")
    logger.info("="*80)
    print()

    bq_client = get_bq_client()

    # Check if BQ table exists
    logger.info("Checking BigQuery setup...")
    datasets = list_bq_datasets(bq_client)
    logger.info(f"Available datasets: {datasets}")

    if DATASET_ID in datasets:
        tables = list_bq_tables(bq_client, DATASET_ID)
        logger.info(f"Tables in {DATASET_ID}: {tables}")
    else:
        logger.warning(f"Dataset {DATASET_ID} does not exist yet.")

    # Step 1: Get BigQuery distinct counts
    logger.info("Step 1: Getting distinct counts from BigQuery...")
    bq_counts = get_bq_distinct_counts(bq_client)

    # Step 2: Get landing bucket distinct counts
    logger.info("Step 2: Getting distinct counts from landing bucket...")
    gcs_client = get_gcs_client()

    # Extract the file number from the table name (e.g., events_2026_03_07_7 -> 2026-03-07-7)
    # to compare the same file between landing and BQ
    if "_" in TABLE_ID:
        parts = TABLE_ID.split("_")
        # Format: events_YYYY_MM_DD_N
        if len(parts) >= 5:
            year, month, day, num = parts[-4], parts[-3], parts[-2], parts[-1]
            landing_file_prefix = f"github-archive/raw/{year}-{month}-{day}-{num}"
            logger.info(f"Comparing with matching landing file: {landing_file_prefix}.json.gz")
            landing_counts = get_landing_distinct_counts(gcs_client, max_files=1, prefix=landing_file_prefix)
        else:
            # Fallback to raw files
            landing_counts = get_landing_distinct_counts(gcs_client, max_files=1, prefix="github-archive/raw/")
    else:
        landing_counts = get_landing_distinct_counts(gcs_client, max_files=1, prefix="github-archive/raw/")

    # Step 3: Compare
    logger.info("Step 3: Comparing results...")
    results = compare_distinct_counts(bq_counts, landing_counts)

    # Step 4: Print report
    print_comparison_report(results)

    # Save results to JSON
    output_file = "/tmp/distinct_count_comparison.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Results saved to: {output_file}")
    logger.info("="*80)
    logger.info("Comparison complete")
    logger.info("="*80)


if __name__ == "__main__":
    main()
