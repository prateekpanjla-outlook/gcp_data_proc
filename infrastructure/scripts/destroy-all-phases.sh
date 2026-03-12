#!/bin/bash
# Destroy All Phases of GitHub Archive Pipeline
# Usage: ./destroy-all-phases.sh <PROJECT_ID> <ENVIRONMENT> [REGION]
#
# Destroys in reverse order: Phase 3 (L03 -> L02 -> L01) -> Phase 2 -> Phase 1
# Empties buckets before destroying Phase 1 (force_destroy workaround).
#
# Example:
#   ./destroy-all-phases.sh beaming-glyph-489707-b8 test us-central1

set -euo pipefail

# =============================================================================
# Arguments & Defaults
# =============================================================================
PROJECT_ID="${1:?Error: PROJECT_ID required. Usage: $0 <PROJECT_ID> <ENVIRONMENT> [REGION]}"
ENVIRONMENT="${2:?Error: ENVIRONMENT required (dev/test/prod)}"
REGION="${3:-us-central1}"

# =============================================================================
# Paths
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BASE="${REPO_ROOT}/infrastructure/github_archive"
KEY_PATH="${REPO_ROOT}/infrastructure/${ENVIRONMENT}-terraform-deployer-key.json"

if [[ ! -f "${KEY_PATH}" ]]; then
  KEY_PATH="${REPO_ROOT}/infrastructure/test-terraform-deployer-key.json"
fi

# =============================================================================
# Logging
# =============================================================================
LOG_DIR="${REPO_ROOT}/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/destroy-all-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "${LOG_FILE}") 2>&1

# =============================================================================
# Derived Names
# =============================================================================
LANDING_BUCKET="${PROJECT_ID}-${ENVIRONMENT}-github-archive-landing"
STAGING_BUCKET="${PROJECT_ID}-${ENVIRONMENT}-github-archive-staging"

echo "========================================="
echo "GitHub Archive Pipeline - Full Destroy"
echo "========================================="
echo "Project:     ${PROJECT_ID}"
echo "Environment: ${ENVIRONMENT}"
echo "Region:      ${REGION}"
echo "Started:     $(date)"
echo "========================================="
echo ""

if [[ ! -f "${KEY_PATH}" ]]; then
  echo "ERROR: Service account key not found: ${KEY_PATH}"
  exit 1
fi

export GOOGLE_APPLICATION_CREDENTIALS="${KEY_PATH}"

# Helper function for terraform destroy
tf_destroy() {
  local dir="$1"
  shift
  echo "  terraform init..."
  terraform -chdir="${dir}" init -input=false -no-color > /dev/null 2>&1
  echo "  terraform destroy..."
  terraform -chdir="${dir}" destroy -auto-approve -input=false "$@"
}

DESTROY_START=$(date +%s)

# =============================================================================
# Phase 3: BigQuery Loader (reverse layer order)
# =============================================================================
echo ""
echo "========================================="
echo "Phase 3: BigQuery Loader (destroying)"
echo "========================================="
PHASE3_BASE="${BASE}/phase3_loadbigquery/terraform/layers"

# Layer 03: Operational
echo ""
echo "--- Layer 03: Operational ---"
tf_destroy "${PHASE3_BASE}/03_operational" \
  -var="project_id=${PROJECT_ID}" \
  -var="environment=${ENVIRONMENT}" \
  -var="staging_bucket_name=${STAGING_BUCKET}" || true

# Layer 02: First-time
echo ""
echo "--- Layer 02: First-time ---"
tf_destroy "${PHASE3_BASE}/02_first_time" \
  -var="project_id=${PROJECT_ID}" \
  -var="environment=${ENVIRONMENT}" \
  -var="region=${REGION}" \
  -var="staging_bucket_name=${STAGING_BUCKET}" || true

# Layer 01: Static
echo ""
echo "--- Layer 01: Static ---"
tf_destroy "${PHASE3_BASE}/01_static" \
  -var="project_id=${PROJECT_ID}" \
  -var="environment=${ENVIRONMENT}" \
  -var="region=${REGION}" || true

# =============================================================================
# Phase 2: Process Files
# =============================================================================
echo ""
echo "========================================="
echo "Phase 2: Process Files (destroying)"
echo "========================================="
PHASE2_DIR="${BASE}/phase2_process_files/terraform"

tf_destroy "${PHASE2_DIR}" \
  -var="project_id=${PROJECT_ID}" \
  -var="environment=${ENVIRONMENT}" \
  -var="landing_bucket_name=${LANDING_BUCKET}" \
  -var="deployer_sa_key_path=${KEY_PATH}" || true

# =============================================================================
# Phase 1: Ingestion (empty buckets first)
# =============================================================================
echo ""
echo "========================================="
echo "Phase 1: Ingestion (destroying)"
echo "========================================="

# Empty buckets before destroy (force_destroy may be false for non-dev)
echo "  Emptying landing bucket..."
gcloud storage rm "gs://${LANDING_BUCKET}/**" 2>/dev/null || true

echo "  Emptying staging bucket..."
gcloud storage rm "gs://${STAGING_BUCKET}/**" 2>/dev/null || true

PHASE1_DIR="${BASE}/phase1_ingestion/terraform"

tf_destroy "${PHASE1_DIR}" \
  -var="project_id=${PROJECT_ID}" \
  -var="environment=${ENVIRONMENT}" \
  -var="force_destroy=true" \
  -var="deployer_sa_key_path=${KEY_PATH}" || true

# =============================================================================
# Summary
# =============================================================================
DESTROY_END=$(date +%s)
DESTROY_DURATION=$((DESTROY_END - DESTROY_START))

echo ""
echo "========================================="
echo "Destroy Complete"
echo "========================================="
echo "Duration:  ${DESTROY_DURATION}s"
echo "Log:       ${LOG_FILE}"
echo "Finished:  $(date)"
echo "========================================="
