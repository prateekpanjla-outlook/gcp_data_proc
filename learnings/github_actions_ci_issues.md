# GitHub Actions CI/CD — Issues & Fixes

## Issue 1: Workflow doesn't trigger on first push

**Problem**: Creating a new branch with workflow files and pushing doesn't trigger the workflow. GitHub requires the workflow file to already exist on the branch before a push triggers it.

**Fix**: Push the branch first (with workflow files), then make a second push (even an empty commit) to trigger.
```bash
git commit --allow-empty -m "trigger: test CI pipeline"
git push origin gh_archive_test
```

## Issue 2: GCP_SA_KEY_BASE64 secret — decode failure

**Problem**: The "Decode GCP credentials" step failed. The `google-github-actions/auth@v2` action expects raw JSON but was passed base64-encoded data.

**Fix**: Removed the `auth@v2` action. Instead, decode base64 to a file and use `gcloud auth activate-service-account --key-file`:
```yaml
- run: |
    echo "${{ secrets.GCP_SA_KEY_BASE64 }}" | base64 -d > /tmp/gcp-key.json
    echo "GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp-key.json" >> $GITHUB_ENV
- run: gcloud auth activate-service-account --key-file=/tmp/gcp-key.json
```

## Issue 3: Deploy script can't find key file

**Problem**: `deploy-all-phases.sh` looks for key at `infrastructure/test-terraform-deployer-key.json` but on GitHub runner the key is decoded to `/tmp/gcp-key.json`.

**Fix**: Added fallback to `GOOGLE_APPLICATION_CREDENTIALS` env var in both deploy and destroy scripts:
```bash
if [[ ! -f "${KEY_PATH}" && -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
  KEY_PATH="${GOOGLE_APPLICATION_CREDENTIALS}"
fi
```

## Issue 4: Scripts not executable

**Problem**: Bash scripts committed from Windows have `100644` permissions (not executable). GitHub runner can't execute them directly.

**Fix**: Set executable bit in git:
```bash
git update-index --chmod=+x infrastructure/scripts/deploy-all-phases.sh
```
Also, the workflow uses `chmod +x` as a safety measure before running.

## Issue 5: `gcloud beta` not installed on GitHub runner

**Problem**: Terraform `null_resource` runs `gcloud beta services identity create` which prompts for interactive install of the beta component. GitHub runners are non-interactive — the prompt causes exit code 1.

**Fix**: Added `--quiet` flag to all `gcloud beta` commands:
```bash
gcloud --quiet beta services identity create --service=storage.googleapis.com
```

## Issue 6: PowerShell not available on GitHub runner

**Problem**: All terraform `null_resource` provisioners used `interpreter = ["powershell", "-Command"]`. GitHub runners (ubuntu-latest) don't have PowerShell by default.

**Fix**: Converted all 6 PowerShell provisioners to bash using `interpreter = ["bash", "-c"]` and heredoc syntax. Affected files:
- Phase 1: `build.tf` (IAM propagation wait + downloader build)
- Phase 2: `build.tf` (processor build), `apis.tf` (service agent init), `ack_deadline.tf` (Pub/Sub ack)
- Phase 4: `main.tf` Layer 03 (dashboard build)

## Issue 7: Terraform state lost between CI runs

**Problem**: GitHub runners are ephemeral — `.terraform/` and `terraform.tfstate` are lost after each run. First CI run deployed resources but state was lost. Second run tried to create the same resources → "already exists" errors. Resources became orphaned (no state to manage/destroy them).

**Fix**: Switched from local backend to GCS remote backend:
```hcl
backend "gcs" {
  bucket = "beaming-glyph-489707-b8-terraform-state"
  prefix = "terraform/state/phase1-ingestion"
}
```
- Created GCS bucket with versioning enabled (protects against state corruption)
- Updated all 11 terraform configurations across Phases 1-4
- Deployer SA already has `roles/storage.admin` at project level
- State persists across ephemeral runners

**Cleanup**: Orphaned resources from failed CI runs had to be deleted manually via `gcloud` commands since no state existed to terraform destroy them.

## GitHub Secrets Required

| Secret | Value | Notes |
|--------|-------|-------|
| `GCP_PROJECT_ID` | `beaming-glyph-489707-b8` | Test project ID |
| `GCP_SA_KEY_BASE64` | `base64 -w0 key.json` | Base64-encoded SA key (3212 bytes) |

## GitHub Runner Environment

- OS: Ubuntu (latest)
- Python: pre-installed
- gcloud: installed via `google-github-actions/setup-gcloud@v2`
- terraform: installed via `hashicorp/setup-terraform@v3`
- PowerShell: **NOT available** by default
- `gcloud beta`: **NOT pre-installed** — needs `--quiet` flag for auto-install
- DNS: reliable (no timeout issues like local Windows)
- Network: full outbound internet access to GCP APIs
