# Phase 2: Null Handling in Validation

## Problem

The original dtype validation counted ALL nulls after dtype coercion as errors, without distinguishing between:

1. **Source nulls** - Null values present in the original JSON data (e.g., `"actor_id": null`)
2. **Coercion nulls** - New nulls introduced when dtype coercion fails (e.g., string `"invalid"` → boolean)

This led to false positive errors for legitimate null values in the source data.

## Root Cause

**Original code** ([`dtype_validator.py:79-82`](../src/github_archive/phase2_process_files/validators/dtype_validator.py#L79-L82)):

```python
# Count nulls after coercion
null_count = result_df[col].isna().sum()
if null_count > 0:
    null_counts[col] = int(null_count)  # ← ALL nulls counted as errors
```

This happened AFTER dtype coercion, so there was no way to tell the difference.

## Solution

Check nulls **before** and **after** coercion to differentiate:

```python
# Count source nulls BEFORE coercion
source_nulls = result_df[col].isna().sum()

# Coerce to expected dtype
result_df[col] = result_df[col].astype(dtype)

# Count nulls AFTER coercion
nulls_after = result_df[col].isna().sum()

# Calculate new nulls introduced by coercion
coercion_nulls = int(nulls_after - source_nulls)

# Only count coercion failures as errors
if coercion_nulls > 0:
    coercion_null_counts[col] = coercion_nulls
```

## Files Changed

| File | Change |
|------|--------|
| [`validators/dtype_validator.py`](../src/github_archive/phase2_process_files/validators/dtype_validator.py) | Added `coercion_null_counts` field, track before/after coercion |
| [`processors/file_processor.py`](../src/github_archive/phase2_process_files/processors/file_processor.py) | Use `coercion_null_counts` for error counting |

## Example Behavior

### Input Data (JSON)
```json
{"id": "123", "type": "PushEvent", "public": null}          ← source null
{"id": null, "type": "PushEvent", "public": true}            ← source null
{"id": "456", "type": "PushEvent", "public": "invalid_type"}    ← will coerce to null
```

### Before Fix
| Column | Source Nulls | After Coercion | Error Count |
|-------|-------------|----------------|-------------|
| `id` | 1 | 0 | 0 |
| `public` | 1 | 2 (source + "invalid_type") | **2** (both counted) |

### After Fix
| Column | Source Nulls | Coercion Nulls | Error Count |
|-------|-------------|----------------|-------------|
| `id` | 1 | 0 | 0 |
| `public` | 1 | 1 (from "invalid_type") | **1** (only coercion) |

## Key Insight

> **Source nulls are valid JSON** - they represent missing data in the original event. We should NOT treat them as errors. Only dtype coercion failures (bad data that couldn't be converted) should be errors.

## Implementation Details

**Updated `DtypeValidationResult`:**
```python
@dataclass
class DtypeValidationResult:
    is_valid: bool
    coerced_df: Optional[pd.DataFrame]
    errors: List[str]
    null_counts: Dict[str, int]              # Source nulls (informational only)
    coercion_null_counts: Dict[str, int]     # Coercion failures (actual errors)
```

**Error counting:**
- `null_counts` → tracked but NOT added to `total_errors`
- `coercion_null_counts` → added to `total_errors`

This allows monitoring source nulls (for data quality analysis) without treating them as errors.
