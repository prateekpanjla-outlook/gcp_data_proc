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

## GitHub Actions Concurrency Control — Deep Dive

### What it does

```yaml
concurrency:
  group: gh-archive-deploy-${{ github.ref }}
  cancel-in-progress: true
```

This tells GitHub Actions: "Only one workflow run from this `group` can be active at a time."

### How it works

1. **Group key**: `gh-archive-deploy-${{ github.ref }}` — `github.ref` is the branch name (e.g., `refs/heads/gh_archive_test`). So all pushes to the same branch share the same concurrency group.

2. **When a new push arrives while a run is active**:
   - GitHub sees the new run belongs to the same concurrency group
   - `cancel-in-progress: true` → GitHub **cancels the currently running** workflow and starts the new one
   - Without `cancel-in-progress`, the new run would **queue** and wait for the old one to finish

3. **Why cancel the old run** (not queue):
   - The old run is deploying infrastructure based on **old code** — the new push has fixes/changes that supersede it
   - Terraform state locks would block the new run if the old one is still holding them
   - Saves CI minutes (free tier: 2,000 min/month) — no point running stale code
   - The old run's partial deploy is idempotent — the new run will pick up where it left off (terraform detects existing resources)

4. **What happens to the cancelled run**:
   - GitHub sends SIGTERM to all running processes
   - The run shows as "cancelled" (grey icon) in the Actions tab
   - Any terraform apply that was mid-execution gets interrupted — but terraform state is consistent because GCS backend uses locking (writes are atomic)
   - Resources created before cancellation stay deployed — the new run will detect them via state

### When NOT to use `cancel-in-progress`

- **Destroy workflows**: Never cancel a destroy mid-way — could leave partial state. Our destroy workflow doesn't use concurrency control.
- **Prod deployments**: May want to queue instead of cancel, to avoid interrupting a live deployment.

### Alternative: Queue instead of cancel

```yaml
concurrency:
  group: gh-archive-deploy-${{ github.ref }}
  cancel-in-progress: false  # default
```

This queues the new run until the old one finishes. Safer but slower — and wastes CI minutes if the old run is deploying outdated code.

## Terraform null_resource — Phantom Additions/Deletions

**Observation**: Terraform output shows `1 added, 0 changed, 1 destroyed` even when no real GCP infrastructure changed. This can be confusing in CI logs.

**Why it happens**: `null_resource` has no real GCP resource — it only exists as an ID in terraform state. When its `triggers` value changes, terraform "destroys" the old state entry and "creates" a new one (re-running the provisioner script). The `always_run = timestamp()` trigger guarantees this happens every apply.

**What "1 added, 1 destroyed" actually means**:
- Destroyed: removed old state entry (no GCP API call)
- Added: ran the script, recorded new state ID (no GCP resource created)
- Net effect on GCP: zero changes

**Where you'll see this**:
- `cleanup_stale_sa_bindings` (Phase 4 Layer 02) — always re-runs stale SA check
- `verify_dashboard_iam` (Phase 4 Layer 02) — always re-runs IAM verification
- Any `null_resource` with `triggers = { always_run = timestamp() }`

**How to distinguish from real changes**: Look at the resource type in the plan output. If it's `null_resource.*`, no GCP infrastructure is changing. Real changes show as `google_*` resources.

## Issue 8: schema.json not in git (gitignored by *.json)

**Problem**: Phase 3 Layer 01 terraform failed with `no file exists at "./schema.json"`. The `*.json` rule in `.gitignore` excluded all JSON files including the BQ table schema definition.

**Fix**: Added exceptions to `.gitignore`:
```
!**/schema.json
!**/.terraform.lock.hcl
```

## Issue 9: Terraform state lock conflict from parallel runs

**Problem**: Multiple pushes triggered parallel workflow runs. Both tried to acquire the same GCS state lock → second run failed with lock conflict.

**Fix**: Added `concurrency` control to the workflow:
```yaml
concurrency:
  group: gh-archive-deploy-${{ github.ref }}
  cancel-in-progress: true
```
This cancels the older run when a new push arrives.

## Issue 10: `data.terraform_remote_state` still using local backend

**Problem**: After switching terraform `backend` blocks to GCS, the `data.terraform_remote_state` references in Phase 2 Layer 03 and Phase 3 Layers 02/03 still pointed to `backend = "local"` with `path = "../01_static/terraform.tfstate"`. The local state file doesn't exist on the GitHub runner.

**Fix**: Updated all `data.terraform_remote_state` blocks to use GCS:
```hcl
data "terraform_remote_state" "static" {
  backend = "gcs"
  config = {
    bucket = "beaming-glyph-489707-b8-terraform-state"
    prefix = "terraform/state/phase3-static"
  }
}
```
Affected files:
- `phase2_process_files/terraform/layers/03_operational/main.tf` (2 references)
- `phase3_loadbigquery/terraform/layers/02_first_time/main.tf` (1 reference)
- `phase3_loadbigquery/terraform/layers/03_operational/main.tf` (2 references)

## GitHub Runner Environment

- OS: Ubuntu (latest)
- Python: pre-installed
- gcloud: installed via `google-github-actions/setup-gcloud@v2`
- terraform: installed via `hashicorp/setup-terraform@v3`
- PowerShell: **NOT available** by default
- `gcloud beta`: **NOT pre-installed** — needs `--quiet` flag for auto-install
- DNS: reliable (no timeout issues like local Windows)
- Network: full outbound internet access to GCP APIs
