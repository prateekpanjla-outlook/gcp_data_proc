#!/usr/bin/env python3
"""
Validate GitHub Archive file format and schema.

Checks:
1. File decompression works
2. File is valid JSON
3. Records are newline-delimited (NDJSON)
4. Data types match expected schema
"""

import gzip
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Any
from collections import Counter

# Expected schema from dtype_definitions.py
EXPECTED_SCHEMA = {
    'id': 'string',
    'type': 'string',
    'public': 'boolean',
    'created_at': 'string',
    'actor': 'object',
    'repo': 'object',
    'payload': 'object',
    'org': 'object',
    'other': 'object',
}


def analyze_file(file_path: str, sample_size: int = 100) -> Dict[str, Any]:
    """
    Analyze a GitHub Archive file.

    Args:
        file_path: Path to the .json.gz file
        sample_size: Number of records to analyze

    Returns:
        Analysis results dictionary
    """
    print(f"{'='*70}")
    print(f"GITHUB ARCHIVE FILE VALIDATION")
    print(f"{'='*70}")
    print(f"File: {file_path}")
    print(f"Sample size: {sample_size} records")
    print(f"{'='*70}\n")

    results = {
        'file_exists': False,
        'decompression_works': False,
        'is_ndjson': False,
        'valid_json_records': 0,
        'invalid_records': 0,
        'total_lines': 0,
        'columns_found': set(),
        'column_types': {},
        'nested_actor_fields': set(),
        'nested_repo_fields': set(),
        'sample_records': [],
        'missing_expected_columns': [],
        'unexpected_columns': [],
    }

    # Check file exists
    if not Path(file_path).exists():
        print(f"ERROR: File does not exist: {file_path}")
        return results

    results['file_exists'] = True
    print("1. File exists")

    # Try to decompress and read
    try:
        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
            lines = f.readlines()
        results['decompression_works'] = True
        results['total_lines'] = len(lines)
        print(f"2. Decompression: SUCCESS")
        print(f"   Total lines in file: {len(lines):,}")
    except Exception as e:
        print(f"2. Decompression: FAILED - {e}")
        return results

    # Analyze sample records
    print(f"\n3. Analyzing format and structure...")

    for i, line in enumerate(lines[:sample_size]):
        line = line.strip()
        if not line:
            continue

        try:
            record = json.loads(line)
            results['valid_json_records'] += 1

            # Collect column names
            for key in record.keys():
                results['columns_found'].add(key)

                # Track the type of value for each key
                if key not in results['column_types']:
                    results['column_types'][key] = type(record[key]).__name__
                # Verify type consistency
                elif results['column_types'][key] != type(record[key]).__name__:
                    results['column_types'][key] = f"mixed ({results['column_types'][key]}, {type(record[key]).__name__})"

            # Collect nested actor fields
            if 'actor' in record and isinstance(record['actor'], dict):
                for key in record['actor'].keys():
                    results['nested_actor_fields'].add(key)

            # Collect nested repo fields
            if 'repo' in record and isinstance(record['repo'], dict):
                for key in record['repo'].keys():
                    results['nested_repo_fields'].add(key)

            # Store first 3 sample records
            if len(results['sample_records']) < 3:
                results['sample_records'].append(record)

        except json.JSONDecodeError as e:
            results['invalid_records'] += 1
            print(f"   WARNING: Invalid JSON on line {i+1}: {e}")

    # Check if it's NDJSON (one JSON object per line)
    results['is_ndjson'] = results['valid_json_records'] > 0 and results['invalid_records'] == 0

    print(f"   Format: {'NDJSON (newline-delimited JSON)' if results['is_ndjson'] else 'UNKNOWN'}")
    print(f"   Valid JSON records: {results['valid_json_records']}")
    print(f"   Invalid records: {results['invalid_records']}")

    # Compare with expected schema
    print(f"\n4. Schema Comparison:")
    print(f"   Expected columns: {len(EXPECTED_SCHEMA)}")
    print(f"   Found columns: {len(results['columns_found'])}")

    results['missing_expected_columns'] = set(EXPECTED_SCHEMA.keys()) - results['columns_found']
    results['unexpected_columns'] = results['columns_found'] - set(EXPECTED_SCHEMA.keys())

    if results['missing_expected_columns']:
        print(f"\n   MISSING expected columns: {results['missing_expected_columns']}")
    else:
        print(f"\n   All expected columns present!")

    if results['unexpected_columns']:
        print(f"   UNEXPECTED columns found: {results['unexpected_columns']}")
    else:
        print(f"   No unexpected columns")

    # Print column types
    print(f"\n5. Column Data Types:")
    for col in sorted(results['columns_found']):
        expected_type = EXPECTED_SCHEMA.get(col, 'N/A')
        actual_type = results['column_types'][col]
        match = "MATCH" if expected_type != 'N/A' else "N/A"
        print(f"   {col:20s} | Expected: {expected_type:10s} | Actual: {actual_type:20s} | {match}")

    # Print nested actor fields
    if results['nested_actor_fields']:
        print(f"\n6. Nested 'actor' object fields ({len(results['nested_actor_fields'])}):")
        for field in sorted(results['nested_actor_fields']):
            print(f"   - actor.{field}")

    # Print nested repo fields
    if results['nested_repo_fields']:
        print(f"\n7. Nested 'repo' object fields ({len(results['nested_repo_fields'])}):")
        for field in sorted(results['nested_repo_fields']):
            print(f"   - repo.{field}")

    # Print sample record
    if results['sample_records']:
        print(f"\n8. Sample Record (first record):")
        print(f"   {'-'*68}")
        sample = results['sample_records'][0]
        for key, value in sample.items():
            value_preview = str(value)[:100]
            if len(value_preview) >= 100:
                value_preview += "..."
            print(f"   {key:15s}: {value_preview}")

    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")

    issues = []
    if not results['decompression_works']:
        issues.append("Decompression failed")
    if not results['is_ndjson']:
        issues.append("Not valid NDJSON format")
    if results['missing_expected_columns']:
        issues.append(f"Missing columns: {results['missing_expected_columns']}")
    if results['invalid_records'] > 0:
        issues.append(f"Invalid JSON records: {results['invalid_records']}")

    if issues:
        print(f"STATUS: ISSUES FOUND")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print(f"STATUS: ALL CHECKS PASSED")

    print(f"{'='*70}\n")

    return results


def main():
    """Main entry point."""
    # Try to find the test file
    possible_paths = [
        '/home/vagrant/Desktop/claude-code-zai/cloud_storage_run_bigquery_data_project/data/github_archive/test-10k.json.gz',
        '/home/vagrant/Desktop/claude-code-zai/cloud_storage_run_bigquery_data_project/data/github_archive/2025-01-01-0.json.gz',
        './data/github_archive/test-10k.json.gz',
    ]

    file_path = None
    for path in possible_paths:
        if Path(path).exists():
            file_path = path
            break

    if not file_path:
        print("ERROR: Could not find test file")
        print("Tried paths:")
        for path in possible_paths:
            print(f"  - {path}")
        sys.exit(1)

    results = analyze_file(file_path, sample_size=100)

    # Exit with appropriate code
    if not results['is_ndjson'] or results['invalid_records'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
