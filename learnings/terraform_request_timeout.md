# Terraform Provider Request Timeout

## Problem

Terraform deploy script failed silently during `terraform init` / `terraform plan` with DNS resolution errors:

```
dial tcp: lookup iam.googleapis.com: no such host
```

The machine's DNS was slow but eventually resolved (confirmed via `nslookup`). Terraform's default 30s timeout was too short, causing the script to fail before DNS could respond.

The error was initially invisible because `terraform init` output was redirected to `/dev/null`.

## Fix

1. Added `request_timeout = "120s"` to all `provider "google"` blocks across Phase 1, Phase 2, and Phase 3 terraform configs (8 files total).

2. Removed `/dev/null` redirect from `terraform init` in `deploy-all-phases.sh` so errors are visible.

## Notes

- Terraform has no built-in retry logic for API calls — adding retries would require `null_resource` wrappers around every resource, which is impractical.
- The right approach for transient failures is re-running the deploy script (terraform is idempotent).
- `request_timeout` doesn't add retries — it just waits longer before giving up on slow responses.

## Files Changed

- `infrastructure/github_archive/phase1_ingestion/terraform/main.tf`
- `infrastructure/github_archive/phase2_process_files/terraform/main.tf`
- `infrastructure/github_archive/phase2_process_files/terraform/layers/01_static/main.tf`
- `infrastructure/github_archive/phase2_process_files/terraform/layers/02_first_time/main.tf`
- `infrastructure/github_archive/phase2_process_files/terraform/layers/03_operational/main.tf`
- `infrastructure/github_archive/phase3_loadbigquery/terraform/layers/01_static/terraform.tf`
- `infrastructure/github_archive/phase3_loadbigquery/terraform/layers/02_first_time/terraform.tf`
- `infrastructure/github_archive/phase3_loadbigquery/terraform/layers/03_operational/terraform.tf`
- `infrastructure/scripts/deploy-all-phases.sh`
