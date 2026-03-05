#!/bin/bash
#
# GitHub Archive Download Script for Cloud Run Job
# Downloads hourly GitHub Archive file to Cloud Storage using gsutil
#
# Environment Variables:
#   PROJECT_ID      - Google Cloud Project ID
#   BUCKET_NAME      - Target Cloud Storage bucket name
#   HOURS_AGO        - Number of hours ago to download (default: 1)
#
set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
BUCKET_NAME="${BUCKET_NAME:-${PROJECT_ID}-github-archive-landing}"
GITHUB_ARCHIVE_BASE="https://data.gharchive.org"
HOURS_AGO="${HOURS_AGO:-1}"

# ==============================================================================
# Calculate target filename (YYYY-MM-DD-H.json.gz)
# ==============================================================================

# Detect OS type for date command compatibility
if date +%s >/dev/null 2>&1; then
    # Linux/GNU date
    TARGET_TIME=$(date -u -d "${HOURS_AGO} hours ago" '+%Y-%m-%d %H')
    TARGET_HOUR=$(date -u -d "${HOURS_AGO} hours ago" '+%Y-%m-%-H')
else
    # macOS/BSD date
    TARGET_TIME=$(date -u -v -${HOURS_AGO}H '+%Y-%m-%d %H')
    TARGET_HOUR=$(date -u -v -${HOURS_AGO}H '+%Y-%m-%-H')
fi

FILENAME="${TARGET_HOUR}.json.gz"
GCS_PATH="gs://${BUCKET_NAME}/github-archive/raw/${FILENAME}"
SOURCE_URL="${GITHUB_ARCHIVE_BASE}/${FILENAME}"

# ==============================================================================
# Logging
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

log_info "=== GitHub Archive Download Job ==="
log_info "Target time: ${TARGET_TIME}"
log_info "Filename: ${FILENAME}"
log_info "Source URL: ${SOURCE_URL}"
log_info "GCS Path: ${GCS_PATH}"
log_info "Bucket: ${BUCKET_NAME}"

# ==============================================================================
# Check if file already exists (idempotency)
# ==============================================================================

if gsutil -q stat "${GCS_PATH}" 2>/dev/null; then
    log_success "File already exists in GCS, skipping download"
    echo "{\"action\":\"skip\",\"reason\":\"already_exists\",\"file\":\"${GCS_PATH}\"}"
    exit 0
fi

log_info "File does not exist in GCS, proceeding with download"

# ==============================================================================
# Download using gsutil (streams automatically - memory efficient)
# ==============================================================================

log_info "Starting download from GitHub Archive..."

# Capture download metrics
START_TIME=$(date +%s)

# Run gsutil cp
if gsutil cp "${SOURCE_URL}" "${GCS_PATH}"; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    log_success "Download completed successfully"

    # Get file size for verification
    FILE_SIZE=$(gsutil du "${GCS_PATH}" | awk '{print $1}')

    log_info "=== Download Complete ==="
    log_info "GCS Path: ${GCS_PATH}"
    log_info "File Size: ${FILE_SIZE} bytes"
    log_info "Duration: ${DURATION} seconds"

    # Output success metrics (for Cloud Monitoring)
    echo "{\"action\":\"download_success\",\"filename\":\"${FILENAME}\",\"file_size\":\"${FILE_SIZE}\",\"duration_seconds\":\"${DURATION}\"}"

    exit 0
else
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    log_error "Download failed after ${DURATION} seconds"
    echo "{\"action\":\"download_failed\",\"filename\":\"${FILENAME}\",\"duration_seconds\":\"${DURATION}\"}"
    exit 1
fi
