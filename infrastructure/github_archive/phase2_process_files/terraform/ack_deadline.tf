# Phase 2: Eventarc Pub/Sub Ack Deadline Override
# Eventarc creates Pub/Sub subscriptions with 10s ack deadline by default.
# File processing can take minutes, so we increase to 600s (max) to prevent
# duplicate message delivery (Error 16 in learnings).

resource "null_resource" "update_trigger_ack_deadline" {
  depends_on = [google_eventarc_trigger.main_file_processor]

  triggers = {
    trigger_name = google_eventarc_trigger.main_file_processor.name
  }

  provisioner "local-exec" {
    command = format(
      "gcloud auth activate-service-account --key-file=%s; $sub = (gcloud eventarc triggers describe %s --location %s --project=%s --format='value(transport.pubsub.subscription)'); gcloud pubsub subscriptions update $sub --ack-deadline=600 --project=%s",
      var.deployer_sa_key_path,
      google_eventarc_trigger.main_file_processor.name,
      var.region,
      var.project_id,
      var.project_id
    )

    interpreter = ["powershell", "-Command"]
  }
}
