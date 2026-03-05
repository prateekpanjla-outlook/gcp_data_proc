# Cloud Run Job: GitHub Archive Downloader
# Uses google-cloud-sdk base image with gsutil for streaming downloads

FROM gcr.io/google.com/cloudsdktool/google-cloud-cli:slim

# Install additional utilities if needed
# Coreutils includes date with -d option for time calculations
RUN apt-get update && apt-get install -y \
    coreutils \
    && rm -rf /var/lib/apt/lists/*

# Copy download script
COPY scripts/download.sh /scripts/download.sh
RUN chmod +x /scripts/download.sh

# Set environment variables (can be overridden at runtime)
ENV BUCKET_NAME=""
ENV PROJECT_ID=""
ENV HOURS_AGO="1"
ENV GOOGLE_APPLICATION_CREDENTIALS=""

# Set entrypoint
ENTRYPOINT ["/scripts/download.sh"]

# Labels
LABEL description="GitHub Archive hourly downloader using gsutil"
LABEL version="1.0"
LABEL component="github-archive-ingestion"
