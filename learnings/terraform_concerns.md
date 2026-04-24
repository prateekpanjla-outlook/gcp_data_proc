# Terraform Concerns: Provisioning vs Orchestration Gap

## The Problem

Terraform is a **declarative provisioning tool** — you describe the desired state, it converges infrastructure to match. But it has a fundamental blind spot: it conflates **infrastructure existence** with **operational readiness**.

When Terraform says "resource created," it means the API call returned 200. It does **not** mean:
- The resource is ready to serve traffic
- IAM bindings have propagated
- Dependent services can reach it
- The resource should be active right now

This creates the **"Day 1 vs Day 2" problem**: configuration that's correct for initial deployment becomes harmful on subsequent applies.

## How We Hit This

### The Scheduler Pause Bug

Our pipeline deploys in phases:
```
Phase 1: Cloud Scheduler + Cloud Run Job (download)
Phase 2: Eventarc trigger + Cloud Run Service (processor)
Phase 3: Cloud Function (BigQuery loader)
```

The scheduler fires immediately on creation — but Phase 2 (Eventarc trigger) doesn't exist yet. Files land in the bucket with nothing listening.

**Our fix:** Set `paused = true` in Terraform, resume via deploy script after all phases complete.

**The problem with this fix:** On every subsequent `terraform apply`, Terraform sees the scheduler is ENABLED (because the deploy script resumed it) and forces it back to PAUSED. Then the deploy script resumes it again. This creates a brief window where no files are downloaded.

```
terraform apply:  ENABLED → PAUSED    (Terraform enforces declared state)
deploy script:    PAUSED → ENABLED    (script resumes it)
```

On a fresh deploy this is correct. On every subsequent deploy, it's unnecessary churn.

## GCP Services Affected by This Pattern

### 1. Resources with Enabled/Disabled State
Terraform manages both the resource definition and its active/inactive state as a single unit.

| Service | Attribute | Day 1 Need | Day 2 Reality |
|---------|-----------|------------|---------------|
| Cloud Scheduler | `paused` | Create paused, resume after dependencies | Already running, don't touch |
| Cloud Build Triggers | `disabled` | May need disabled until IAM propagates | Should stay enabled |
| BigQuery Scheduled Queries | `disabled` | May need disabled until tables exist | Should stay enabled |
| Cloud Composer DAGs | paused state | Pause until connections configured | Should stay active |
| Alerting Policies | `enabled` | May disable during initial setup noise | Should stay enabled |

**Our application:** Cloud Scheduler (`scheduler.tf` line 13: `paused = true`).

### 2. Eventual Consistency — Terraform Says "Done" But It's Not
Terraform returns success as soon as the API responds, but enforcement may lag.

| Service | Propagation Delay | Impact |
|---------|------------------|--------|
| **IAM bindings** | 60s typical, up to 7 min | Our biggest pain point. `build.tf` has a 180s polling loop with `testIamPermissions` because Terraform says the binding exists but Cloud Build can't use it yet |
| **Service API enabling** | 30–60s | `google_project_service` returns, but API calls fail with "API not enabled" |
| **VPC Service Controls** | Minutes | Perimeter changes not enforced immediately |
| **DNS records** | Minutes to hours | Record visible in console but not resolving |
| **Organization Policies** | Minutes | Policy set but not enforced on child resources |

**Our application:** `build.tf` uses `null_resource` + `local-exec` with `testIamPermissions` polling loop to wait for IAM propagation before triggering Cloud Build. This is a workaround for Terraform not understanding eventual consistency.

### 3. Resources That Need Dependents "Ready," Not Just "Existing"
Terraform's `depends_on` ensures creation order, but not readiness.

| Service | What Terraform Knows | What It Doesn't Know |
|---------|---------------------|---------------------|
| **Eventarc triggers** | Trigger resource exists | Target Cloud Run service is healthy and serving |
| **Pub/Sub push subscriptions** | Subscription created | Endpoint is responding to push requests |
| **Load Balancer backends** | Backend registered | Health checks are passing |
| **Cloud CDN** | CDN enabled on backend | Cache is warm |
| **Cloud Tasks queues** | Queue exists | Target handler is deployed and ready |

**Our application:** Eventarc trigger (Phase 2) depends on Cloud Run processor being deployed, but Terraform only checks the resource exists — not that the container has booted and passed health checks.

### 4. Resources with Initialization/Boot Time
Some resources take minutes to become usable after creation.

| Service | Boot Time | Terraform Behavior |
|---------|-----------|-------------------|
| **Data Fusion** | 15–25 min (tenant project creation) | Returns "created" immediately, instance unusable. We hit Error 10 and needed a `null_resource` with `sleep 60` |
| **Cloud SQL** | 5–10 min | Returns before instance is connectable |
| **GKE clusters** | 5–15 min | Control plane provisioning in progress |
| **Dataproc clusters** | 2–5 min | Node bootstrapping |
| **Memorystore (Redis)** | 3–5 min | Instance provisioning |

**Our application:** Data Fusion instance (`cloud_datafusion_test` branch) required explicit sleep after creation. Terraform reported success but the instance couldn't accept pipeline submissions.

### 5. Runtime State That Terraform Shouldn't Own
Some attributes change constantly at runtime and shouldn't be part of infrastructure-as-code.

| Service | Attribute | Why Terraform Shouldn't Manage It |
|---------|-----------|----------------------------------|
| **Cloud Run** | Traffic splitting (% to revisions) | Canary/rollout is an operational concern |
| **GKE** | Current node count | Autoscaler manages this |
| **Compute Engine** | RUNNING/STOPPED status | Operational state, not infrastructure |
| **Cloud Storage** | Object retention locks | Applied per-object at runtime |
| **Pub/Sub** | Ack deadline tuning | Tuned based on consumer performance |

## Suggestions for Our Application

### Fix 1: Reorder Deploy Phases (Recommended)

The cleanest fix — no Terraform hacks needed. Deploy downstream consumers first, scheduler last:

```bash
# deploy-all-phases.sh — new order
Phase 2: Eventarc + processor (consumer ready first)
Phase 3: BigQuery loader (consumer ready)
Phase 1: Scheduler + download job (producer last)
Phase 4: Monitoring dashboard
Step 5: Resume scheduler (only needed if paused=true kept)
```

**Change required:**
- `deploy-all-phases.sh`: swap Phase 1 and Phase 2 order
- `scheduler.tf`: remove `paused = true` (scheduler created last, all consumers ready)
- Remove Step 5 (scheduler resume) from deploy script

**Trade-off:** Phase 2 Terraform references the landing bucket created by Phase 1. We'd need to either:
- Create the bucket in a shared "Phase 0" or as a standalone resource
- Pass the bucket name as a variable (already done: `var.landing_bucket_name`)
- Use `terraform_remote_state` data source

Since Phase 2 already takes `landing_bucket_name` as a variable and only needs the bucket to exist for Eventarc triggers (not for Phase 2 Terraform to create it), this may work if we split bucket creation from scheduler creation.

### Fix 2: lifecycle ignore_changes (Quick Fix)

```hcl
# scheduler.tf
resource "google_cloud_scheduler_job" "github_archive_download" {
  paused = true  # Only applies on creation

  lifecycle {
    ignore_changes = [paused]  # Don't enforce on updates
  }
}
```

**Pros:** One-line fix, no deploy script changes.
**Cons:** Punches a hole in the declarative model. If someone manually pauses the scheduler, Terraform won't restore it. You've lost visibility into this attribute.

### Fix 3: Variable Toggle for First Deploy

```hcl
variable "initial_deploy" {
  description = "Set to true only on first deployment"
  type        = bool
  default     = false
}

resource "google_cloud_scheduler_job" "github_archive_download" {
  paused = var.initial_deploy  # Only paused on first run
}
```

**Pros:** Explicit, no hidden behavior.
**Cons:** Requires human judgment (remembering to set the variable). Error-prone.

### Fix 4: IAM Propagation — Replace Polling with Dependency Chain

Current approach in `build.tf`:
```hcl
# null_resource with local-exec that polls testIamPermissions every 10s for 180s
```

Better approach:
```hcl
resource "time_sleep" "iam_propagation" {
  depends_on      = [google_project_iam_member.cloudbuild_roles]
  create_duration = "120s"
}

resource "null_resource" "trigger_build" {
  depends_on = [time_sleep.iam_propagation]
  # ...
}
```

**Pros:** Simpler than polling loop, no impersonation/tokenCreator needed.
**Cons:** Always waits 120s even if propagation finished in 10s. But it's predictable and removes the testIamPermissions complexity (and its tokenCreator dependency).

### Fix 5: Move Scheduler to Phase 2

Instead of reordering the entire deploy, move the scheduler resource from Phase 1 Terraform to Phase 2 Terraform. Phase 2 already creates the Eventarc trigger, so by the time the scheduler is created in the same `terraform apply`, the trigger is guaranteed to exist.

**Change required:**
- Move `scheduler.tf` from `phase1_ingestion/terraform/` to `phase2_process_files/terraform/`
- Move scheduler SA and IAM bindings along with it
- Remove `paused = true` and the resume step

**Pros:** Terraform's own dependency graph handles ordering. No deploy script orchestration needed.
**Cons:** Conceptually, the scheduler belongs to ingestion (Phase 1), not processing (Phase 2). Mixing concerns.

## Recommendation

**Short term:** Apply Fix 2 (`lifecycle ignore_changes`) — it's a one-line change that stops the pause/resume churn on every deploy.

**Medium term:** Apply Fix 1 (reorder phases) or Fix 5 (move scheduler to Phase 2) — architecturally cleaner, solves the root cause.

**For IAM propagation:** Keep the current `testIamPermissions` polling approach. It's more complex than `time_sleep` but gives faster feedback and catches real permission issues rather than blindly waiting.

## The Broader Lesson

Terraform is a **provisioning** tool, not an **orchestration** tool. When you need ordering, readiness checks, or runtime state management, that logic belongs in your **deploy script** (or a proper orchestrator like Argo CD, Temporal, or Cloud Deploy) — not in Terraform's HCL.

The deploy script (`deploy-all-phases.sh`) is architecturally correct as our orchestration layer. The issue was putting orchestration logic (`paused = true`) inside Terraform instead of keeping it in the orchestrator.
