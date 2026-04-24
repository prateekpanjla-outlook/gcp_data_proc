# Use the official Google Cloud SDK image as a base.
# This image includes gcloud, gsutil, curl, and other necessary tools.
FROM gcr.io/google.com/cloudsdktool/google-cloud-cli:slim

# Set the working directory inside the container
WORKDIR /app

# --- THE FIX ---
# Copy the download script from its full path within the build context.
# The build context is 'src/github_archive/', so the script is located at
# 'phase1_ingestion/scripts/download.sh' relative to that context root.
COPY phase1_ingestion/scripts/download.sh .

# Make the script executable
RUN chmod +x download.sh

# Set the entrypoint for the container to run the download script
ENTRYPOINT ["./download.sh"]