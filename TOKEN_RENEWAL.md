# Automatic Instagram token renewal

The hosted app uses two Cloud Run workloads built from the same container image:

- The web service reads the current Instagram token from a Secret Manager volume.
- A private Cloud Run job refreshes the token with Meta, validates it with `/me`,
  and adds the replacement as the latest Secret Manager version.
- The job retains the newest token and one rollback version, then destroys only
  older token versions so rotation remains within Secret Manager's free allowance.
- Cloud Scheduler runs the private job every Monday at 04:00 Europe/Istanbul.

The web service reads the mounted file for every publish request. Cloud Run fetches
the latest secret version when the volume is read, so a token rotation does not
require a new service revision.

## Deploy the renewal-capable image

Deploy the source as the existing service, preserving the single-instance settings:

```bash
gcloud run deploy siirden-karelere \
  --source . \
  --project=siirden-karelere \
  --region=europe-west1 \
  --allow-unauthenticated \
  --cpu=1 \
  --memory=512Mi \
  --concurrency=20 \
  --timeout=300 \
  --max-instances=1 \
  --min-instances=0
```

Replace the pinned token environment variable with a latest-version secret volume:

```bash
gcloud run services update siirden-karelere \
  --project=siirden-karelere \
  --region=europe-west1 \
  --remove-secrets=INSTAGRAM_ACCESS_TOKEN \
  --update-secrets=/secrets/instagram/access-token=instagram-access-token:latest \
  --update-env-vars=INSTAGRAM_ACCESS_TOKEN_FILE=/secrets/instagram/access-token
```

## Create the private refresh job

Enable scheduling and create one narrowly scoped service account:

```bash
gcloud services enable cloudscheduler.googleapis.com secretmanager.googleapis.com \
  --project=siirden-karelere

gcloud iam service-accounts create instagram-token-automation \
  --project=siirden-karelere \
  --display-name="Instagram token renewal"

TOKEN_AUTOMATION_SA="instagram-token-automation@siirden-karelere.iam.gserviceaccount.com"
```

Allow that identity to read and add versions of only the Instagram token secret:

```bash
gcloud secrets add-iam-policy-binding instagram-access-token \
  --project=siirden-karelere \
  --member="serviceAccount:${TOKEN_AUTOMATION_SA}" \
  --role=roles/secretmanager.secretAccessor

gcloud secrets add-iam-policy-binding instagram-access-token \
  --project=siirden-karelere \
  --member="serviceAccount:${TOKEN_AUTOMATION_SA}" \
  --role=roles/secretmanager.secretVersionAdder

gcloud secrets add-iam-policy-binding instagram-access-token \
  --project=siirden-karelere \
  --member="serviceAccount:${TOKEN_AUTOMATION_SA}" \
  --role=roles/secretmanager.secretVersionManager
```

Use the image deployed to the web service for the private job:

```bash
IMAGE_URL="$(gcloud run services describe siirden-karelere \
  --project=siirden-karelere \
  --region=europe-west1 \
  --format='value(spec.template.spec.containers[0].image)')"

gcloud run jobs deploy instagram-token-refresh \
  --project=siirden-karelere \
  --region=europe-west1 \
  --image="${IMAGE_URL}" \
  --service-account="${TOKEN_AUTOMATION_SA}" \
  --command=python \
  --args=-m,poetry_app.token_refresh \
  --set-env-vars=INSTAGRAM_ACCESS_TOKEN_FILE=/secrets/instagram/access-token,INSTAGRAM_SECRET_RESOURCE=projects/siirden-karelere/secrets/instagram-access-token,INSTAGRAM_GRAPH_API_VERSION=v26.0,INSTAGRAM_GRAPH_BASE_URL=https://graph.instagram.com \
  --set-secrets=/secrets/instagram/access-token=instagram-access-token:latest \
  --tasks=1 \
  --max-retries=1 \
  --task-timeout=120s
```

## Schedule the job

Grant the automation identity permission to execute only this job, then create the
weekly schedule:

```bash
gcloud run jobs add-iam-policy-binding instagram-token-refresh \
  --project=siirden-karelere \
  --region=europe-west1 \
  --member="serviceAccount:${TOKEN_AUTOMATION_SA}" \
  --role=roles/run.invoker

gcloud scheduler jobs create http instagram-token-refresh-weekly \
  --project=siirden-karelere \
  --location=europe-west1 \
  --schedule="0 4 * * 1" \
  --time-zone="Europe/Istanbul" \
  --uri="https://run.googleapis.com/v2/projects/siirden-karelere/locations/europe-west1/jobs/instagram-token-refresh:run" \
  --http-method=POST \
  --oauth-service-account-email="${TOKEN_AUTOMATION_SA}"
```

Long-lived Instagram tokens must be at least 24 hours old before Meta will refresh
them. After that point, test the job manually:

```bash
gcloud run jobs execute instagram-token-refresh \
  --project=siirden-karelere \
  --region=europe-west1 \
  --wait
```

Successful output and logs identify the Instagram username, the new Secret Manager
version number, and the lifetime in seconds. They never print the token.
