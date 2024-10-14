#!/bin/bash

# Function to display usage message
usage() {
    echo "Usage: $0 --project_id <project_id> --peo_access_key <peo_access_key>"
    exit 1
}

# Function to check the exit status of the last command
check_status() {
    if [ $? -ne 0 ]; then
        echo "Error: $1 failed. Exiting."
        exit 1
    fi
}

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --project_id) PROJECT_ID="$2"; shift ;;
        --peo_access_key) PEO_ACCESS_KEY="$2"; shift ;;
        *) usage ;;
    esac
    shift
done

# Check if both arguments are provided
if [ -z "$PROJECT_ID" ] || [ -z "$PEO_ACCESS_KEY" ]; then
    echo "Error: PROJECT_ID and peo_access_key must be provided."
    usage
fi

# Create directory and move into it
mkdir -p imagen3_bot_for_poe
cd imagen3_bot_for_poe || exit
check_status "Directory creation"

# Download required files
curl -O https://raw.githubusercontent.com/AmirMK/quora_sample_code/refs/heads/main/Dockerfile
check_status "Downloading Dockerfile"

curl -O https://raw.githubusercontent.com/AmirMK/quora_sample_code/refs/heads/main/imagen_bot_poe.py
check_status "Downloading imagen_bot_poe.py"

curl -O https://raw.githubusercontent.com/AmirMK/quora_sample_code/refs/heads/main/requirements.txt
check_status "Downloading requirements.txt"

# Build and push Docker image
IMAGE_NAME="${PROJECT_ID}-image3-bot-img"
docker build -t gcr.io/$PROJECT_ID/$IMAGE_NAME .
check_status "Docker build"

docker push gcr.io/$PROJECT_ID/$IMAGE_NAME
check_status "Docker push"

# Create service account and assign roles
SA_NAME="${PROJECT_ID}-image3-bot-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create $SA_NAME \
    --display-name="$SA_NAME" \
    --project=$PROJECT_ID
check_status "Service account creation"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/aiplatform.user"
check_status "Assigning IAM policy binding"

# Set Cloud Run service name
CLOUD_RUN_NAME="${PROJECT_ID}-image3-cloud-run"

# Deploy Cloud Run service
gcloud run deploy $CLOUD_RUN_NAME \
    --image gcr.io/$PROJECT_ID/$IMAGE_NAME \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --service-account $SA_EMAIL \
    --set-env-vars POE_ACCESS_KEY=$PEO_ACCESS_KEY,PROJECT_ID=$PROJECT_ID,LOCATION=us-central1
check_status "Cloud Run deployment"

# Change to the desired directory before exiting the script
cd imagen3_bot_for_poe
echo "Setup completed successfully!"
