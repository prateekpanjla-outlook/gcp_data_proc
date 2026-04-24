# Cloud Run Billing Optimization

## Problem

Billing analysis (March 1-15, 2026) showed Cloud Run as the #1 cost driver at ₹710/15 days (~₹1,420/month projected). The services were using **instance-based billing** (`cpu_idle = false`), meaning CPU and memory were charged even when idle.

### Cost breakdown (Cloud Run only):
| SKU | Usage | Cost (₹) |
|-----|-------|----------|
| Services CPU (Instance-based) | 321,191 seconds (~89 hrs) | 525.87 |
| Services Memory (Instance-based) | 615,110 GiB-seconds | 111.90 |
| Services CPU (Request-based) | 27,887 seconds | 60.88 |
| Jobs CPU | 17,220 seconds | 28.19 |
| Services Memory (Request-based) | 53,470 GiB-seconds | 12.16 |
| Jobs Memory | 8,610 GiB-seconds | 1.57 |

Instance-based billing accounted for ₹637.77 (90% of Cloud Run costs).

## Root Cause

The terraform config had `cpu_idle = false` for both Cloud Run services:
- **Phase 2 processor**: `cloud_run_service.tf` line 66 and `layers/03_operational/main.tf` line 121
- **Phase 4 dashboard**: `layers/03_operational/main.tf` — no `cpu_idle` set (defaults to `false`)

## Instance-based vs Request-based Billing

| Aspect | Instance-based (`cpu_idle = false`) | Request-based (`cpu_idle = true`) |
|--------|-------------------------------------|-----------------------------------|
| **CPU charging** | Always, even when idle | Only during request processing |
| **Memory charging** | Always, even when idle | Always (memory can't be throttled) |
| **Cold start** | None — instances always warm | 2-5 seconds after idle period |
| **Performance** | Consistent, no cold starts | Variable, depends on idle time |
| **Cost** | High for infrequent traffic | Low for infrequent traffic |
| **Best for** | High-traffic, latency-sensitive | Hourly batch jobs, dashboards |

## Fix

Changed `cpu_idle = false` → `cpu_idle = true` in 3 terraform files:
1. `infrastructure/github_archive/phase2_process_files/terraform/cloud_run_service.tf`
2. `infrastructure/github_archive/phase2_process_files/terraform/layers/03_operational/main.tf`
3. `infrastructure/github_archive/phase4_monitoring/terraform/layers/03_operational/main.tf`

## Impact Analysis

### Phase 2 Processor
- Pipeline runs hourly → 1 cold start per hour (2-5 seconds)
- Processing takes ~30 seconds per file → cold start adds <15% overhead
- Eventarc ack deadline is 600 seconds → plenty of margin for cold start
- **Memory-intensive processing**: `cpu_idle = true` still allocates full CPU during request. The `cpu_idle` flag only affects CPU between requests, not during.

### Phase 4 Dashboard
- Accessed infrequently (manual viewing)
- 2-5 second cold start is acceptable for a monitoring dashboard
- Scales to 0 when not in use → near-zero cost

## Cloud Run Free Tier (per month)
- 2 million requests
- 180,000 vCPU-seconds
- 360,000 GiB-seconds
- 1 GiB network egress (North America)

Our usage exceeded the free tier with instance-based billing but should stay within with request-based billing.

## Other Billing Observations

From the same billing report, services NOT from our pipeline:
- **Cloud SQL (₹34.60)**: PostgreSQL micro instance — likely from dev-dataprocessing project
- **Networking Intelligence Center (₹19.37)**: Resource monitoring — not from our pipeline
- **Compute Engine (₹34.10 charged, ₹34.10 discount)**: Free tier covers it
- **Gemini API (₹0.02)**: Minimal API usage

The billing CSV covers the **entire billing account** (all projects), not just the test project. Filter by project ID in the billing console for project-specific costs.
