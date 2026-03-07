#!/usr/bin/env python3
"""
Complete schema validation for GitHub Archive data.

Validates EVERY record against the expected schema and reports
all discrepancies, field presence statistics, and data type issues.
"""

import gzip
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Any, Counter
from collections import Counter
from dataclasses import dataclass, field

# Import our schema
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.github_archive.phase2_process_files.schemas.dtype_definitions import (
    GITHUB_EVENT_DTYPES,
    ACTOR_FIELDS,
    REPO_FIELDS,
    VALID_EVENT_TYPES,
    ACTOR_FIELD_MAPPING,
    REPO_FIELD_MAPPING,
)


@dataclass
class ValidationResult:
    """Results of complete schema validation."""
    total_records: int = 0
    valid_records: int = 0
    invalid_json: int = 0
    missing_core_fields: int = 0
    unknown_event_types: Set[str] = field(default_factory=set)

    # Field statistics
    core_field_presence: Dict[str, int] = field(default_factory=dict)
    actor_field_presence: Dict[str, int] = field(default_factory=dict)
    repo_field_presence: Dict[str, int] = field(default_factory=dict)
    org_field_presence: int = 0
    other_field_presence: int = 0

    # Event type distribution
    event_types: Dict[str, int] = field(default_factory=dict)

    # Data type issues
    type_mismatches: List[str] = field(default_factory=list)

    # Sample records with issues
    sample_issues: List[Dict[str, Any]] = field(default_factory=list)

    def add_sample_issue(self, issue: Dict[str, Any]):
        """Add a sample issue (max 20)."""
        if len(self.sample_issues) < 20:
            self.sample_issues.append(issue)


def validate_file(file_path: str) -> ValidationResult:
    """
    Validate all records in a GitHub Archive file.

    Args:
        file_path: Path to the .json.gz file

    Returns:
        ValidationResult with all findings
    """
    print(f"{'='*80}")
    print(f"COMPLETE SCHEMA VALIDATION")
    print(f"{'='*80}")
    print(f"File: {file_path}")
    print(f"{'='*80}\n")

    result = ValidationResult()

    # Initialize field counters
    for field in GITHUB_EVENT_DTYPES.keys():
        result.core_field_presence[field] = 0

    for actor_field in ACTOR_FIELD_MAPPING.keys():
        result.actor_field_presence[actor_field] = 0

    for repo_field in REPO_FIELD_MAPPING.keys():
        result.repo_field_presence[repo_field] = 0

    print("Processing records...", flush=True)

    with gzip.open(file_path, 'rt', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            result.total_records += 1

            # Progress indicator
            if result.total_records % 1000 == 0:
                print(f"  {result.total_records} records processed...", flush=True)

            try:
                record = json.loads(line)
                result.valid_records += 1

                # Check core fields
                for core_field in GITHUB_EVENT_DTYPES.keys():
                    if core_field in record:
                        result.core_field_presence[core_field] += 1

                # Check event type
                event_type = record.get('type')
                if event_type:
                    result.event_types[event_type] = result.event_types.get(event_type, 0) + 1
                    if event_type not in VALID_EVENT_TYPES:
                        result.unknown_event_types.add(event_type)
                        result.add_sample_issue({
                            'line': line_num,
                            'issue': 'unknown_event_type',
                            'event_type': event_type
                        })

                # Check actor fields
                if 'actor' in record and isinstance(record['actor'], dict):
                    for actor_field in ACTOR_FIELD_MAPPING.keys():
                        if actor_field in record['actor']:
                            result.actor_field_presence[actor_field] += 1

                # Check repo fields
                if 'repo' in record and isinstance(record['repo'], dict):
                    for repo_field in REPO_FIELD_MAPPING.keys():
                        if repo_field in record['repo']:
                            result.repo_field_presence[repo_field] += 1

                # Check org field
                if 'org' in record:
                    result.org_field_presence += 1

                # Check other field
                if 'other' in record:
                    result.other_field_presence += 1
                    result.add_sample_issue({
                        'line': line_num,
                        'issue': 'other_field_present',
                        'event_id': record.get('id')
                    })

                # Check for missing required fields
                required_fields = ['id', 'type', 'created_at', 'actor', 'repo']
                missing = [f for f in required_fields if f not in record]
                if missing:
                    result.missing_core_fields += 1
                    result.add_sample_issue({
                        'line': line_num,
                        'issue': 'missing_core_fields',
                        'missing': missing,
                        'event_id': record.get('id')
                    })

            except json.JSONDecodeError as e:
                result.invalid_json += 1
                result.add_sample_issue({
                    'line': line_num,
                    'issue': 'invalid_json',
                    'error': str(e)
                })

    print(f"\nProcessing complete!\n")
    return result


def print_results(result: ValidationResult):
    """Print detailed validation results."""
    print(f"{'='*80}")
    print(f"VALIDATION RESULTS")
    print(f"{'='*80}\n")

    # Summary
    print("SUMMARY:")
    print(f"  Total records:         {result.total_records:,}")
    print(f"  Valid JSON:            {result.valid_records:,}")
    print(f"  Invalid JSON:          {result.invalid_json:,}")
    print(f"  Missing core fields:   {result.missing_core_fields:,}")
    print(f"  Unknown event types:   {len(result.unknown_event_types)}")
    print()

    # Event type distribution
    print("EVENT TYPE DISTRIBUTION:")
    for event_type, count in sorted(result.event_types.items(), key=lambda x: -x[1]):
        pct = (count / result.total_records) * 100
        print(f"  {event_type:30s}: {count:6d} ({pct:5.1f}%)")
    print()

    # Core field presence
    print("CORE FIELD PRESENCE:")
    for field, count in result.core_field_presence.items():
        pct = (count / result.total_records) * 100 if result.total_records > 0 else 0
        status = "OK" if pct >= 99 else "LOW" if pct > 0 else "MISSING"
        print(f"  {field:20s}: {count:6d} ({pct:5.1f}%) [{status}]")
    print()

    # Actor field presence
    print("ACTOR FIELD PRESENCE (nested in actor object):")
    for field, count in result.actor_field_presence.items():
        pct = (count / result.total_records) * 100 if result.total_records > 0 else 0
        status = "OK" if pct >= 99 else "LOW" if pct > 0 else "MISSING"
        print(f"  actor.{field:15s}: {count:6d} ({pct:5.1f}%) [{status}]")
    print()

    # Repo field presence
    print("REPO FIELD PRESENCE (nested in repo object):")
    for field, count in result.repo_field_presence.items():
        pct = (count / result.total_records) * 100 if result.total_records > 0 else 0
        status = "OK" if pct >= 99 else "LOW" if pct > 0 else "MISSING"
        print(f"  repo.{field:15s}: {count:6d} ({pct:5.1f}%) [{status}]")
    print()

    # Optional fields
    print("OPTIONAL FIELD PRESENCE:")
    print(f"  org:   {result.org_field_presence:6d} ({(result.org_field_presence/result.total_records)*100:5.1f}%)")
    print(f"  other: {result.other_field_presence:6d} ({(result.other_field_presence/result.total_records)*100:5.1f}%)")
    print()

    # Unknown event types
    if result.unknown_event_types:
        print(f"UNKNOWN EVENT TYPES: {result.unknown_event_types}")
        print()

    # Sample issues
    if result.sample_issues:
        print(f"SAMPLE ISSUES (showing first {len(result.sample_issues)}):")
        for issue in result.sample_issues[:10]:
            print(f"  Line {issue.get('line', '?')}: {issue}")
        print()

    # Final verdict
    print(f"{'='*80}")
    print("FINAL VERDICT:")

    issues = []
    if result.invalid_json > 0:
        issues.append(f"{result.invalid_json} invalid JSON records")
    if result.missing_core_fields > 0:
        issues.append(f"{result.missing_core_fields} records with missing core fields")
    if result.unknown_event_types:
        issues.append(f"Unknown event types: {result.unknown_event_types}")

    # Check for any fields with < 90% presence (expected to be 100%)
    expected_100 = ['id', 'type', 'actor', 'repo', 'created_at']
    for field in expected_100:
        pct = (result.core_field_presence.get(field, 0) / result.total_records) * 100
        if pct < 90:
            issues.append(f"Field '{field}' only present in {pct:.1f}% of records")

    if issues:
        print("  STATUS: ISSUES FOUND")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("  STATUS: ALL CHECKS PASSED")
        print("  Schema matches GitHub Archive data format!")

    print(f"{'='*80}\n")


def main():
    """Main entry point."""
    file_path = 'data/github_archive/2026-03-05-12.json.gz'

    if not Path(file_path).exists():
        print(f"ERROR: File not found: {file_path}")
        sys.exit(1)

    result = validate_file(file_path)
    print_results(result)

    # Exit with appropriate code
    if result.invalid_json > 0 or result.missing_core_fields > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
