# Deploying DeploySmith on Google Cloud Run

Two Cloud Run services, built by Cloud Build into Artifact Registry:

| Service | Image | What it runs |
| --- | --- | --- |
| `deploysmith-api` | `deploy/docker/api.Dockerfile` | FastAPI + LangGraph pipeline. Real profiler (git shallow clones, static analysis only) and strategist; simulated provisioner and healer |
| `deploysmith-web` | `web.Dockerfile` | The Vite build served by nginx, with the API URL baked in |

The sandbox engine is **off** in the cloud: it builds apps in Docker, and Cloud Run has no
Docker daemon. Real deploys stay a local feature (`SANDBOX_ENGINE=1` on your machine).

## One-time setup

1. Install the gcloud CLI: <https://cloud.google.com/sdk/docs/install>, then `gcloud auth login`.
2. Create a project (or reuse one) and link a billing account. Cloud Run needs billing
   enabled even when usage stays inside the free tier.
3. Set a budget alert (Billing → Budgets & alerts, e.g. ₹100/month) so any unexpected
   usage emails you before it costs anything real.

## Deploy

```sh
GCP_PROJECT=your-project-id ./deploy/gcp/deploy.sh
# optional: GCP_REGION=asia-south1 (default us-central1)
```

The script enables the APIs, stores Smith's Groq key (from `GROQ_API_KEY` or the repo's
`.env`) in Secret Manager for the API to read at startup, creates the `deploysmith` Artifact Registry repository, builds
and deploys the API, builds the frontend against the API's URL, deploys it, and finally sets
the API's `CORS_ORIGINS` (the frontend's URLs) and `ALLOWED_HOSTS` (the API's own hostnames).
It prints the site URL at the end. Re-run it to ship a new version; images are tagged with
the git commit.

## Why these settings

- **API `--max-instances 1` and `--session-affinity`:** runs and their event streams live in
  the process's memory, so the POST that starts a run and the SSE stream that follows it
  must reach the same instance.
- **`--min-instances 0`:** both services scale to zero when idle, so an unvisited portfolio
  costs nothing; the first visit after a quiet period takes a second or two longer.
- **API `--timeout 900`:** SSE streams stay open for the length of a run.
- **Groq key in Secret Manager:** never in the image, the build upload (`.gcloudignore`
  excludes `.env`) or the service's plain environment. Without a key, Smith stays hidden.
- **API `--memory 1Gi`:** Cloud Run's filesystem is in memory, and the profiler clones repos
  of up to 200 MB into it.

## Cost

With scale-to-zero and these caps, portfolio-level traffic fits Cloud Run's monthly free
tier (2 million requests, 180,000 vCPU-seconds, 360,000 GiB-seconds), Cloud Build's free
build minutes and Artifact Registry's 0.5 GB of free storage. Prune old images
(`gcloud artifacts docker images list ...`) if you redeploy often. Free-tier terms change;
check <https://cloud.google.com/free> and keep the budget alert on.

## Test the images locally

```sh
docker build -f deploy/docker/api.Dockerfile -t deploysmith-api .
docker build -f deploy/gcp/web.Dockerfile --build-arg VITE_API_URL=http://localhost:8091 -t deploysmith-web .
docker run -p 8091:8080 -e CORS_ORIGINS=http://localhost:8092 -e ALLOWED_HOSTS=localhost deploysmith-api
docker run -p 8092:8080 deploysmith-web      # open http://localhost:8092
```
