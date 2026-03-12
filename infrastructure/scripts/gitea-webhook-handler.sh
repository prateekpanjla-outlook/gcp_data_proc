#!/bin/bash
# Gitea Webhook Handler for CI Test Pipeline
#
# This script is called by a Gitea webhook on push to the 'test' branch.
# It pulls the latest code and runs the full CI test pipeline.
#
# Setup (Gitea):
#   1. Go to your repo Settings -> Webhooks -> Add Webhook -> Gitea
#   2. Target URL: http://localhost:9090/webhook (or wherever this listener runs)
#   3. Trigger on: Push Events
#   4. Branch filter: test
#
# Setup (listener):
#   Option A: Use a simple webhook listener like 'webhook' (https://github.com/adnanh/webhook)
#     brew install webhook  # or download from GitHub releases
#     Create hooks.json:
#       [{
#         "id": "ci-test",
#         "execute-command": "/path/to/gitea-webhook-handler.sh",
#         "command-working-directory": "/c/Users/prateek/Desktop/gcp/gcp_data_processing",
#         "pass-arguments-to-command": [
#           { "source": "payload", "name": "ref" }
#         ],
#         "trigger-rule": {
#           "match": { "type": "value", "value": "refs/heads/test", "parameter": { "source": "payload", "name": "ref" } }
#         }
#       }]
#     webhook -hooks hooks.json -port 9090 -verbose
#
#   Option B: Run manually after pushing to test branch
#     git push origin test && ./infrastructure/scripts/gitea-webhook-handler.sh refs/heads/test
#
#   Option C: Use as a git post-push hook

set -euo pipefail

REF="${1:-}"
BRANCH="${REF##*/}"

# Only run for test branch
if [[ "${BRANCH}" != "test" && "${REF}" != "refs/heads/test" ]]; then
  echo "Skipping: not a push to test branch (ref: ${REF})"
  exit 0
fi

# =============================================================================
# Config
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PROJECT_ID="beaming-glyph-489707-b8"
ENVIRONMENT="test"
REGION="us-central1"

echo "========================================="
echo "Gitea CI Trigger"
echo "========================================="
echo "Branch: ${BRANCH}"
echo "Time:   $(date)"
echo ""

# Pull latest
cd "${REPO_ROOT}"
git fetch origin test
git checkout test
git pull origin test

# Export Python for gcloud
export CLOUDSDK_PYTHON="/c/Python314/python.exe"

# Run the CI pipeline
echo "Starting CI test pipeline..."
"${SCRIPT_DIR}/ci-test-pipeline.sh" "${PROJECT_ID}" "${ENVIRONMENT}" "${REGION}"

EXIT_CODE=$?
if [[ ${EXIT_CODE} -eq 0 ]]; then
  echo "CI PASSED"
else
  echo "CI FAILED (exit code: ${EXIT_CODE})"
fi

exit ${EXIT_CODE}
