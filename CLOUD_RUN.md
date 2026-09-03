# Google Cloud Run deployment

The full deployment walkthrough is in the
[README](README.md#deploy-to-google-cloud-run). This page records the runtime
decisions that should remain true when the service is updated.

## Required runtime configuration

The container:

- listens on Cloud Run's `PORT`;
- writes temporary JPEGs under `/tmp/poetry-media`;
- serves randomized `/media/<id>.jpg` paths on the service's public port;
- disables the second, local-only media server; and
- requires application login protection before publishing is enabled.

Use these service settings:

| Setting | Value |
| --- | --- |
| Public access | Allowed |
| CPU | 1 |
| Memory | 512 MiB |
| Minimum instances | 0 |
| Maximum instances | **1** |
| Concurrency | 20 |
| Request timeout | 300 seconds |

The one-instance limit is important. Media is stored on the instance that
rendered it; without shared object storage, a second instance may not have the
file that Instagram requests.

## Deploy from a clone

Run this from the repository root in Cloud Shell:

```bash
PROJECT_ID="your-google-cloud-project"
REGION="europe-west1"
SERVICE="your-service-name"

gcloud config set project "$PROJECT_ID"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com

gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --cpu 1 \
  --memory 512Mi \
  --concurrency 20 \
  --timeout 300 \
  --max-instances 1 \
  --min-instances 0
```

The first deployment supports previews but deliberately leaves publishing
disabled. Follow the README to add `APP_PASSWORD`, `APP_SESSION_SECRET`, and the
Instagram token through Secret Manager, then set `PUBLIC_MEDIA_BASE_URL` to the
Cloud Run service URL.

Application pages and JSON endpoints are protected after login is configured.
`/health` and randomized temporary media URLs remain public so Cloud Run and
Instagram can reach them.

## Deploy updates

From an updated clone, run the same `gcloud run deploy` command. Settings and
secrets already attached to the service are preserved unless a deployment
command explicitly changes them.

For automatic token renewal, continue with [TOKEN_RENEWAL.md](TOKEN_RENEWAL.md).
For installing the deployed site as a Windows app, see
[WINDOWS_INSTALL.md](WINDOWS_INSTALL.md).
