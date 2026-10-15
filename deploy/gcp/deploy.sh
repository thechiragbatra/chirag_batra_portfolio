#!/usr/bin/env bash
# Deploy DeploySmith to Google Cloud Run: the API, then the frontend built against it.
#
#   GCP_PROJECT=my-project ./deploy/gcp/deploy.sh            # region defaults to us-central1
#   GCP_PROJECT=my-project GCP_REGION=asia-south1 ./deploy/gcp/deploy.sh
#
# Needs the gcloud CLI, logged in (gcloud auth login) to a project with billing enabled.
# Cloud Run, Cloud Build and Artifact Registry all have monthly free tiers; the limits
# below keep a portfolio's traffic inside them (see deploy/gcp/README.md).
set -euo pipefail

PROJECT="${GCP_PROJECT:?set GCP_PROJECT to your Google Cloud project id}"
REGION="${GCP_REGION:-us-central1}"
REPO="${GCP_ARTIFACT_REPO:-deploysmith}"
API="deploysmith-api"
WEB="deploysmith-web"
TAG="$(git rev-parse --short HEAD 2>/dev/null || date +%s)"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}"

cd "$(dirname "$0")/../.."
gcloud config set project "$PROJECT" >/dev/null

echo "==> Enabling Cloud Run, Cloud Build and Artifact Registry"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

if ! gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1; then
  echo "==> Creating Artifact Registry repository $REPO"
  gcloud artifacts repositories create "$REPO" --repository-format docker --location "$REGION"
fi

build() { # build <dockerfile> <image> [build-arg]
  gcloud builds submit . --config deploy/gcp/cloudbuild.yaml \
    --substitutions "_DOCKERFILE=$1,_IMAGE=$2,_BUILD_ARG=${3:-UNUSED=1}"
}

# Every URL a service answers on (the project-number URL and the legacy hash URL).
service_urls() {
  gcloud run services describe "$1" --region "$REGION" \
    --format 'value(metadata.annotations."run.googleapis.com/urls")' | tr -d '[]" ' | tr ',' ' '
}
hosts_of() { for url in "$@"; do echo -n "${url#https://},"; done | sed 's/,$//'; }

echo "==> Building and deploying the API"
build deploy/gcp/api.Dockerfile "$REGISTRY/$API:$TAG"
# max-instances=1: deployment runs and their SSE streams live in one process's memory,
# so every request must reach the same instance. min-instances=0 scales to zero.
gcloud run deploy "$API" --image "$REGISTRY/$API:$TAG" --region "$REGION" \
  --allow-unauthenticated --port 8080 --cpu 1 --memory 1Gi \
  --min-instances 0 --max-instances 1 --concurrency 40 --timeout 900 \
  --session-affinity --cpu-boost
API_URLS=$(service_urls "$API")
API_URL=$(gcloud run services describe "$API" --region "$REGION" --format 'value(status.url)')

echo "==> Building and deploying the frontend against $API_URL"
build deploy/gcp/web.Dockerfile "$REGISTRY/$WEB:$TAG" "VITE_API_URL=$API_URL"
gcloud run deploy "$WEB" --image "$REGISTRY/$WEB:$TAG" --region "$REGION" \
  --allow-unauthenticated --port 8080 --cpu 1 --memory 256Mi \
  --min-instances 0 --max-instances 2 --concurrency 200
WEB_URLS=$(service_urls "$WEB")
WEB_URL=$(gcloud run services describe "$WEB" --region "$REGION" --format 'value(status.url)')

echo "==> Allowing the frontend's origins and the API's own hostnames"
# shellcheck disable=SC2086
gcloud run services update "$API" --region "$REGION" \
  --update-env-vars "^@^CORS_ORIGINS=$(echo $WEB_URLS | tr ' ' ',')@ALLOWED_HOSTS=$(hosts_of $API_URLS)"

echo
echo "Done."
echo "  Site: $WEB_URL"
echo "  API:  $API_URL/api/health"
