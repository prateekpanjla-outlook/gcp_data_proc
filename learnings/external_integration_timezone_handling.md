# Timezone and Time Rationalization for External Integrations

This document captures learnings about handling time and timezone when integrating with external APIs.

## The Issue

When integrating with external APIs like GitHub Archive (`https://data.gharchive.org/`), proper timezone handling is critical. A timezone mismatch can cause your system to look for files that don't exist yet (future) or files that have already been processed (past).

---

## Key Learnings

### 1. Always Use UTC for Time Calculations

External APIs typically use UTC as their canonical timezone. Your system should:

- **Store and calculate all times in UTC**
- **Configure schedulers to use UTC**
- **Use UTC flags in date commands**

**Example - Cloud Scheduler:**
```hcl
resource "google_cloud_scheduler_job" "github_archive_download" {
  schedule    = "30 * * * *"  # 30 minutes past each hour
  time_zone   = "UTC"         # Always specify UTC
  # ...
}
```

**Example - Bash date command:**
```bash
# Use -u flag for UTC
TARGET_HOUR=$(date -u -d "${HOURS_AGO} hours ago" '+%Y-%m-%d-%-H')
```

---

### 2. Hour Precision Matters

Many external data sources provide hourly files. The hour must be included in the filename:

| Format | Example | Correct? |
|--------|---------|----------|
| `{YYYY}-{MM}-{DD}.json.gz` | `2026-03-05.json.gz` | ❌ Missing hour |
| `{YYYY}-{MM}-{DD}-{HH}.json.gz` | `2026-03-05-12.json.gz` | ✅ Correct |

**GitHub Archive filename format:**
```
https://data.gharchive.org/2026-03-05-12.json.gz
                      ^^^^^^^^ ^^^
                        Date   Hour (0-23)
```

---

### 3. Date Format String Bugs Are Subtle

A missing format specifier can produce seemingly valid but incorrect filenames:

**The Bug:**
```bash
# WRONG - Missing %d (day) in format string
TARGET_HOUR=$(date -u -d "1 hour ago" '+%Y-%m-%-H')
# Produces: 2026-03-12.json.gz (hour 12 interpreted as day!)
# Actual file: 2026-03-05-12.json.gz
```

**The Fix:**
```bash
# CORRECT - Include %d for day
TARGET_HOUR=$(date -u -d "1 hour ago" '+%Y-%m-%d-%-H')
# Produces: 2026-03-05-12.json.gz ✓
```

**Always verify date format strings produce expected output:**
```bash
# Test before deploying
date -u -d "1 hour ago" '+%Y-%m-%d-%-H'
```

---

### 4. File Availability Timing

Files from external APIs may not be immediately available:

| Scenario | File Status | Action |
|----------|-------------|--------|
| Current hour (in progress) | 404 Not Found | Wait, use `HOURS_AGO=1` |
| Previous hour | Usually available | Safe to download |
| 2+ hours ago | Always available | Safe to download |

**Real-world verification for 2026-03-05 at ~13:12 UTC:**
```
✓ Hours 0-12: Available (HTTP 200)
✗ Hours 13-23: Not Found (HTTP 404) - Not yet generated
```

**Best Practice:** Scheduler should run at least 30-60 minutes after the hour ends to allow file generation.

```bash
# GitHub Archive typically makes files available 1-2 hours after the hour ends
# Schedule at minute 30 of each hour
schedule: "30 * * * *"  # :30 past each hour in UTC
```

---

### 5. Cross-Platform Date Compatibility

Date commands differ between Linux and macOS:

| Platform | Date Command | Hour Format |
|----------|--------------|-------------|
| Linux (GNU) | `date -d "1 hour ago"` | `%-H` (no leading zero) |
| macOS (BSD) | `date -v-1H` | `%H` (leading zero) |

**Cross-platform script:**
```bash
if date +%s >/dev/null 2>&1; then
    # Linux/GNU date
    TARGET_HOUR=$(date -u -d "${HOURS_AGO} hours ago" '+%Y-%m-%d-%-H')
else
    # macOS/BSD date (use %H for 2-digit hour)
    TARGET_HOUR=$(date -u -v -${HOURS_AGO}H '+%Y-%m-%d-%H')
fi
```

---

## Testing Checklist

Before deploying an external integration:

- [ ] All times use UTC (no local timezone conversion)
- [ ] Date format strings include all components (year, month, day, hour)
- [ ] Scheduler timezone is explicitly set to UTC
- [ ] Test with `HOURS_AGO=0` verifies current hour handling
- [ ] Test with `HOURS_AGO=24` verifies day boundary handling
- [ ] Verify generated filenames match external API format

---

## Quick Reference: Verify File Exists

Before attempting download, verify the file exists:

```bash
# Check if file exists (returns 200 if exists, 404 if not)
curl -sI "https://data.gharchive.org/2026-03-05-12.json.gz" | head -1

# Example output:
# HTTP/2 200     = file exists, safe to download
# HTTP/2 404     = file not found (not yet available or wrong URL)
```

---

## Real-World Example

**Scenario:** GitHub Archive download at 2026-03-05 13:12 UTC

| HOURS_AGO | Generated Filename | File Status | Reason |
|-----------|-------------------|-------------|--------|
| 0 | `2026-03-05-13.json.gz` | 404 | Current hour still in progress |
| 1 | `2026-03-05-12.json.gz` | 200 | Previous hour, available |
| 24 | `2026-03-04-13.json.gz` | 200 | Same time yesterday |

**Recommendation:** Use `HOURS_AGO=1` (or higher) as default to avoid downloading incomplete current-hour files.

---

## References

- [GitHub Archive - Data Format](https://www.gharchive.org/)
- [Google Cloud Scheduler - Time Zones](https://cloud.google.com/scheduler/docs/configuring/cron-job-schedules#time_zones)
- [GNU date command](https://www.gnu.org/software/coreutils/manual/html_node/date-invocation.html)
