#!/bin/bash
#
# GitHub Archive Download Script for Cloud Run Job
# Downloads hourly GitHub Archive file to Cloud Storage or local filesystem
#
# Environment Variables:
#   ENVIRONMENT      - Environment: local|dev|prod (default: dev)
#   PROJECT_ID       - Google Cloud Project ID (required for dev/prod)
#   BUCKET_NAME      - Target Cloud Storage bucket name (optional, auto-derived)
#   HOURS_AGO        - Number of hours ago to download (default: 1)
#   LOCAL_OUTPUT_DIR - Local output directory for 'local' environment (default: ./tmp)
#
set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

ENVIRONMENT="${ENVIRONMENT:-dev}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
HOURS_AGO="${HOURS_AGO:-1}"
LOCAL_OUTPUT_DIR="${LOCAL_OUTPUT_DIR:-./tmp}"

# GitHub Archive base URL
GITHUB_ARCHIVE_BASE="https://data.gharchive.org"

# Validate environment
if [[ ! "${ENVIRONMENT}" =~ ^(local|dev|prod)$ ]]; then
  echo "Error: ENVIRONMENT must be 'local', 'dev', or 'prod', got: ${ENVIRONMENT}"
  exit 1
fi

# Derive bucket name for GCS environments
if [[ "${ENVIRONMENT}" == "local" ]]; then
  BUCKET_NAME="${BUCKET_NAME:-local-filesystem}"
  TARGET_BASE="${LOCAL_OUTPUT_DIR}"
else
  BUCKET_NAME="${BUCKET_NAME:-${PROJECT_ID}-${ENVIRONMENT}-github-archive-landing}"
  TARGET_BASE="gs://${BUCKET_NAME}"
fi

# ==============================================================================
# Calculate target filename (YYYY-MM-DD-H.json.gz)
# ==============================================================================

# Detect OS type for date command compatibility
if date +%s >/dev/null 2>&1; then
    # Linux/GNU date
    TARGET_TIME=$(date -u -d "${HOURS_AGO} hours ago" '+%Y-%m-%d %H')
    TARGET_HOUR=$(date -u -d "${HOURS_AGO} hours ago" '+%Y-%m-%d-%-H')
else
    # macOS/BSD date (pad hour to 2 digits for consistency)
    TARGET_TIME=$(date -u -v -${HOURS_AGO}H '+%Y-%m-%d %H')
    TARGET_HOUR=$(date -u -v -${HOURS_AGO}H '+%Y-%m-%d-%H')
fi

FILENAME="${TARGET_HOUR}.json.gz"
GCS_PATH="gs://${BUCKET_NAME}/github-archive/raw/${FILENAME}"
LOCAL_PATH="${LOCAL_OUTPUT_DIR}/github-archive/raw/${FILENAME}"
SOURCE_URL="${GITHUB_ARCHIVE_BASE}/${FILENAME}"

# Determine target path based on environment
if [[ "${ENVIRONMENT}" == "local" ]]; then
  TARGET_PATH="${LOCAL_PATH}"
else
  TARGET_PATH="${GCS_PATH}"
fi

# ==============================================================================
# Logging Functions (JSON format for Cloud Logging)
# ==============================================================================

log_info() {
    echo "{\"level\":\"info\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"message\":\"$1\"}"
}

log_error() {
    echo "{\"level\":\"error\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"message\":\"$1\"}" >&2
}

log_success() {
    echo "{\"level\":\"info\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"message\":\"$1\",\"status\":\"success\"}"
}

log_test() {
    echo "{\"level\":\"test\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"message\":\"$1\"}"
}

# ==============================================================================
# Header
# ==============================================================================

log_info "=== GitHub Archive Download Job ==="
log_info "Environment: ${ENVIRONMENT}"
log_info "Target time: ${TARGET_TIME}"
log_info "Filename: ${FILENAME}"
log_info "Source URL: ${SOURCE_URL}"
log_info "Target Path: ${TARGET_PATH}"

if [[ "${ENVIRONMENT}" == "local" ]]; then
  log_info "Mode: LOCAL (filesystem)"
else
  log_info "Bucket: ${BUCKET_NAME}"
  log_info "Project: ${PROJECT_ID}"
fi

# ==============================================================================
# Check if file already exists (idempotency)
# ==============================================================================

FILE_EXISTS=false
if [[ "${ENVIRONMENT}" == "local" ]]; then
  # Local filesystem check
  if [[ -f "${TARGET_PATH}" ]]; then
    FILE_EXISTS=true
  fi
else
  # GCS check
  if gsutil -q stat "${TARGET_PATH}" 2>/dev/null; then
    FILE_EXISTS=true
  fi
fi

if [[ "${FILE_EXISTS}" == "true" ]]; then
  log_success "File already exists, skipping download"
  echo "{\"action\":\"skip\",\"reason\":\"already_exists\",\"file\":\"${TARGET_PATH}\"}"
  exit 0
fi

log_info "File does not exist, proceeding with download"

# ==============================================================================
# Create directory for local mode
# ==============================================================================

if [[ "${ENVIRONMENT}" == "local" ]]; then
  LOCAL_DIR=$(dirname "${TARGET_PATH}")
  if [[ ! -d "${LOCAL_DIR}" ]]; then
    log_info "Creating local directory: ${LOCAL_DIR}"
    mkdir -p "${LOCAL_DIR}"
  fi
fi

# ==============================================================================
# Download based on environment
# ==============================================================================

log_info "Starting download from GitHub Archive..."

# Capture download metrics
START_TIME=$(date +%s)
DOWNLOAD_SUCCESS=false

if [[ "${ENVIRONMENT}" == "local" ]]; then
  # Local mode: Use curl to download to filesystem
  log_info "Using curl for local download"

  if curl -fsSL "${SOURCE_URL}" -o "${TARGET_PATH}"; then
    DOWNLOAD_SUCCESS=true
  else
    EXIT_CODE=$?
    log_error "curl failed with exit code: ${EXIT_CODE}"
  fi
else
  # GCS mode: Use gsutil for streaming download
  log_info "Using gsutil for GCS download"

  if gsutil cp "${SOURCE_URL}" "${TARGET_PATH}"; then
    DOWNLOAD_SUCCESS=true
  else
    EXIT_CODE=$?
    log_error "gsutil cp failed with exit code: ${EXIT_CODE}"
  fi
fi

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# ==============================================================================
# Result handling
# ==============================================================================

if [[ "${DOWNLOAD_SUCCESS}" == "true" ]]; then
  log_success "Download completed successfully"

  # Get file size for verification
  if [[ "${ENVIRONMENT}" == "local" ]]; then
    FILE_SIZE=$(stat -f%z "${TARGET_PATH}" 2>/dev/null || stat -c%s "${TARGET_PATH}" 2>/dev/null || echo "unknown")
  else
    FILE_SIZE=$(gsutil du "${TARGET_PATH}" | awk '{print $1}')
  fi

  log_info "=== Download Complete ==="
  log_info "Target: ${TARGET_PATH}"
  log_info "File Size: ${FILE_SIZE} bytes"
  log_info "Duration: ${DURATION} seconds"

  # Output success metrics (for Cloud Monitoring)
  echo "{\"action\":\"download_success\",\"environment\":\"${ENVIRONMENT}\",\"filename\":\"${FILENAME}\",\"file_size\":\"${FILE_SIZE}\",\"duration_seconds\":\"${DURATION}\"}"

  exit 0
else
  log_error "Download failed after ${DURATION} seconds"
  echo "{\"action\":\"download_failed\",\"environment\":\"${ENVIRONMENT}\",\"filename\":\"${FILENAME}\",\"duration_seconds\":\"${DURATION}\"}"
  exit 1
fi
