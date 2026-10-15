# Deploying DeploySmith on Azure

| Part | Azure service | Notes |
| --- | --- | --- |
| API (FastAPI, LangGraph, Smith) | **Container Apps**, Consumption plan | Image from ghcr.io, scale 0–1 replicas, no Log Analytics |
| Site (React build) | **Static Web Apps**, Free plan | SPA routing and headers from `frontend/public/staticwebapp.config.json` |
| Image | **GitHub Container Registry** | Built and pushed by `.github/workflows/publish-api.yml` on every push |
| Groq key | Container Apps **secret** | Read from `.env`, never printed or baked into the image |

The sandbox engine needs a Docker daemon, which Container Apps does not provide, so the hosted
Deployer profiles and plans for real and simulates the final deploy step, as on Cloud Run.

## One-time setup

1. **Azure for Students**: <https://azure.microsoft.com/free/students> with your university
   email ($100 credit, no card). Set a budget alert under Cost Management → Budgets.
2. `brew install azure-cli`, then `az login`.
3. Push to `main` once so the **Publish API image** workflow builds the image, then make it
   public: GitHub → your profile → Packages → `deploysmith-api` → Package settings → Change
   visibility → Public. (Container Apps then pulls it without registry credentials.)

## Deploy

```sh
./deploy/azure/deploy.sh
# options: AZ_LOCATION=eastus (Container Apps region, default centralindia)
#          AZ_SWA_LOCATION=eastus2 (Static Web Apps region, default eastasia)
```

It creates the resource group, the Container Apps environment, the Static Web App and the API
(or updates them), builds the site against the API's URL, uploads it, and wires
`CORS_ORIGINS` and `ALLOWED_HOSTS`. Re-run it to ship a new version after the image workflow
finishes. If your subscription limits regions, pick an allowed one with the variables above.

## Why these settings

- **max 1 replica:** deployment runs, their event streams and Smith's cache live in one
  process's memory, so every request must reach the same instance.
- **min 0 replicas:** scales to zero when idle; the first visit after a quiet spell takes a
  few seconds longer.
- **No Log Analytics, no Azure Container Registry:** both are billed; logs stay available
  live with `az containerapp logs show -n deploysmith-api -g deploysmith --follow`.

## Cost

Container Apps' monthly free grant (180,000 vCPU-seconds, 360,000 GiB-seconds, 2 million
requests) covers portfolio traffic at 0.5 vCPU / 1 GiB with scale to zero; Static Web Apps'
Free plan and ghcr.io public images cost nothing. Keep the budget alert on; free allowances
change, so check <https://azure.microsoft.com/pricing/details/container-apps/>.
