#!/usr/bin/env bash
# Deploy DeploySmith to Azure: the API on Container Apps, the site on Static Web Apps.
#
#   ./deploy/azure/deploy.sh                          # defaults below
#   AZ_LOCATION=eastus AZ_SWA_LOCATION=eastus2 ./deploy/azure/deploy.sh
#
# Needs: the Azure CLI, logged in (az login) to a subscription such as Azure for Students;
# Node (to build the site); and the API image published to ghcr.io by GitHub Actions
# (.github/workflows/publish-api.yml), set to public once. Safe to re-run: it creates what
# is missing and updates the rest. Costs stay inside the free allowances (see README).
set -euo pipefail

RG="${AZ_RESOURCE_GROUP:-deploysmith}"
LOCATION="${AZ_LOCATION:-centralindia}"
SWA_LOCATION="${AZ_SWA_LOCATION:-eastasia}" # Static Web Apps run in a few regions only
ENV_NAME="deploysmith-env"
API="deploysmith-api"
WEB="deploysmith-web"
IMAGE="${API_IMAGE:-ghcr.io/thechiragbatra/deploysmith-api:latest}"
SWA_CLI="@azure/static-web-apps-cli@2.0.10"

cd "$(dirname "$0")/../.."
az account show --query "{subscription: name, user: user.name}" -o tsv >/dev/null \
  || { echo "Run 'az login' first."; exit 1; }
echo "==> Subscription: $(az account show --query name -o tsv)"

echo "==> Checking the API image is public on ghcr.io"
repo="${IMAGE#ghcr.io/}"
repo="${repo%%:*}"
token=$(curl -fsS "https://ghcr.io/token?scope=repository:${repo}:pull" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p' || true)
if ! curl -fsS -o /dev/null -H "Authorization: Bearer ${token}" \
  -H "Accept: application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.v2+json" \
  "https://ghcr.io/v2/${repo}/manifests/${IMAGE##*:}"; then
  echo "Cannot pull $IMAGE anonymously. Run the 'Publish API image' workflow, then make the"
  echo "package public: GitHub -> your profile -> Packages -> deploysmith-api -> Package"
  echo "settings -> Change visibility -> Public."
  exit 1
fi

echo "==> Registering resource providers (first run only takes a minute)"
az provider register -n Microsoft.App --wait >/dev/null
az provider register -n Microsoft.Web --wait >/dev/null
az extension add --name containerapp --upgrade --yes --only-show-errors >/dev/null

az group create -n "$RG" -l "$LOCATION" -o none

if ! az containerapp env show -n "$ENV_NAME" -g "$RG" -o none 2>/dev/null; then
  echo "==> Creating the Container Apps environment (no Log Analytics: it is billed)"
  az containerapp env create -n "$ENV_NAME" -g "$RG" -l "$LOCATION" --logs-destination none -o none
fi
DOMAIN=$(az containerapp env show -n "$ENV_NAME" -g "$RG" --query properties.defaultDomain -o tsv)
API_HOST="$API.$DOMAIN"

if ! az staticwebapp show -n "$WEB" -g "$RG" -o none 2>/dev/null; then
  echo "==> Creating the Static Web App (Free plan)"
  az staticwebapp create -n "$WEB" -g "$RG" -l "$SWA_LOCATION" --sku Free -o none
fi
WEB_HOST=$(az staticwebapp show -n "$WEB" -g "$RG" --query defaultHostname -o tsv)

# Smith's Groq key: from the environment or the repo's .env, never printed. It becomes a
# Container Apps secret, read by the app as GROQ_API_KEY.
GROQ_KEY="${GROQ_API_KEY:-}"
if [[ -z "$GROQ_KEY" && -f .env ]]; then
  GROQ_KEY=$(sed -n 's/^GROQ_API_KEY=//p' .env | tail -1 | tr -d "\"' ")
fi

ENV_VARS=("CORS_ORIGINS=https://$WEB_HOST" "ALLOWED_HOSTS=$API_HOST")
if [[ -n "$GROQ_KEY" ]]; then ENV_VARS+=("GROQ_API_KEY=secretref:groq-api-key"); fi

# max-replicas 1: runs, their event streams and Smith's cache live in one process's memory.
# min-replicas 0: scales to zero when idle, so an unvisited portfolio costs nothing.
if az containerapp show -n "$API" -g "$RG" -o none 2>/dev/null; then
  echo "==> Updating the API"
  if [[ -n "$GROQ_KEY" ]]; then
    az containerapp secret set -n "$API" -g "$RG" --secrets "groq-api-key=$GROQ_KEY" -o none
  fi
  az containerapp update -n "$API" -g "$RG" --image "$IMAGE" \
    --min-replicas 0 --max-replicas 1 --set-env-vars "${ENV_VARS[@]}" -o none
else
  echo "==> Creating the API"
  SECRETS=()
  if [[ -n "$GROQ_KEY" ]]; then SECRETS=(--secrets "groq-api-key=$GROQ_KEY"); fi
  az containerapp create -n "$API" -g "$RG" --environment "$ENV_NAME" --image "$IMAGE" \
    --ingress external --target-port 8080 --cpu 0.5 --memory 1.0Gi \
    --min-replicas 0 --max-replicas 1 ${SECRETS[@]+"${SECRETS[@]}"} --env-vars "${ENV_VARS[@]}" -o none
fi
unset GROQ_KEY

echo "==> Building the site against https://$API_HOST"
(cd frontend && npm ci --no-audit --no-fund >/dev/null && VITE_API_URL="https://$API_HOST" npm run build >/dev/null)

echo "==> Uploading the site"
SWA_CLI_DEPLOYMENT_TOKEN=$(az staticwebapp secrets list -n "$WEB" -g "$RG" --query properties.apiKey -o tsv) \
  npx --yes "$SWA_CLI" deploy frontend/dist --env production >/dev/null

echo
echo "Done."
echo "  Site: https://$WEB_HOST"
echo "  API:  https://$API_HOST/api/health"
