# ack_deadline.tf Documentation

## 1. Overview

Overrides the default Pub/Sub acknowledgement deadline on the subscription that Eventarc creates for the storage trigger. Eventarc sets a 10-second ack deadline by default, but Phase 2 file processing can take several minutes. Without this override, Pub/Sub redelivers the message before processing completes, causing duplicate processing (documented as "Error 16" in project learnings).

This resource increases the ack deadline to 600 seconds (the Pub/Sub maximum).

## 2. Prerequisites

- The Eventarc trigger `google_eventarc_trigger.main_file_processor` must already exist (created in the same flat config or a prior apply).
- `gcloud` CLI must be available.
- `var.deployer_sa_key_path` must be a valid SA key.
- The `pubsub.googleapis.com` API must be enabled (done by `apis.tf`).

## 3. Upstream & Downstream Dependencies

**Upstream:**
- `google_eventarc_trigger.main_file_processor` -- this resource depends on the trigger to extract the auto-created Pub/Sub subscription name.
- `apis.tf` -- Pub/Sub API must be enabled.

**Downstream:**
- No other Terraform resources depend on this. It is a terminal configuration step that affects runtime behavior (preventing duplicate message delivery).

## 4. Code Walkthrough

1. **`depends_on` (line 7):** Ensures the Eventarc trigger exists before attempting to modify its subscription.

2. **`triggers` block (lines 9-11):** Re-runs the provisioner if the trigger name changes (e.g., after a destroy/recreate of the Eventarc trigger).

3. **`local-exec` provisioner (lines 13-23):**
   - Authenticates with the deployer SA.
   - Uses `gcloud eventarc triggers describe` with `--format='value(transport.pubsub.subscription)'` to extract the Pub/Sub subscription name that Eventarc auto-created.
   - Runs `gcloud pubsub subscriptions update` to set `--ack-deadline=600` on that subscription.
   - This is a workaround because Terraform's `google_eventarc_trigger` resource does not expose the ack deadline as a configurable attribute.
