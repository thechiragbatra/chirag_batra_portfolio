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

echo "==> Enabling Cloud Run, Cloud Build, Artifact Registry and Secret Manager"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com

# Smith's Groq key: from the environment, or the repo's .env. It goes into Secret Manager
# (free tier: 6 secret versions, 10,000 reads a month) and is never printed or baked in.
GROQ_KEY="${GROQ_API_KEY:-}"
if [[ -z "$GROQ_KEY" && -f .env ]]; then
  # Last GROQ_API_KEY= line, with any quotes and spaces removed.
  GROQ_KEY=$(sed -n 's/^GROQ_API_KEY=//p' .env | tail -1 | tr -d "\"' ")
fi
SECRET_FLAGS=()
if [[ -n "$GROQ_KEY" ]]; then
  echo "==> Storing the Groq key in Secret Manager (groq-api-key)"
  if ! gcloud secrets describe groq-api-key >/dev/null 2>&1; then
    gcloud secrets create groq-api-key --replication-policy automatic >/dev/null
  fi
  printf '%s' "$GROQ_KEY" | gcloud secrets versions add groq-api-key --data-file=- >/dev/null
  NUMBER=$(gcloud projects describe "$PROJECT" --format 'value(projectNumber)')
  gcloud secrets add-iam-policy-binding groq-api-key \
    --member "serviceAccount:${NUMBER}-compute@developer.gserviceaccount.com" \
    --role roles/secretmanager.secretAccessor >/dev/null
  SECRET_FLAGS=(--set-secrets "GROQ_API_KEY=groq-api-key:latest")
else
  echo "==> No GROQ_API_KEY found: deploying without Smith (its button stays hidden)"
fi
unset GROQ_KEY

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
  --session-affinity --cpu-boost "${SECRET_FLAGS[@]}"
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
