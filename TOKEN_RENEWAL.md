# Automatic Instagram token renewal

The optional renewal setup uses two Cloud Run workloads built from the same
container image:

- the web service reads the current Instagram token from a Secret Manager volume;
- a private Cloud Run Job refreshes and validates the token, then adds the new
  value as a secret version; and
- Cloud Scheduler runs that job weekly.

The refresh code keeps the newest token and one rollback version. It never logs
the token value.

Complete the normal Cloud Run deployment first, then define these values in
Cloud Shell:

```bash
PROJECT_ID="your-google-cloud-project"
REGION="europe-west1"
SERVICE="your-service-name"
TOKEN_SECRET="instagram-access-token"
REFRESH_JOB="instagram-token-refresh"
SCHEDULER_JOB="instagram-token-refresh-weekly"
AUTOMATION_SA_NAME="instagram-token-automation"

AUTOMATION_SA="${AUTOMATION_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SECRET_RESOURCE="projects/${PROJECT_ID}/secrets/${TOKEN_SECRET}"

gcloud config set project "$PROJECT_ID"
```

## Mount the current token in the web service

Replace an environment-variable secret mapping with a latest-version secret
volume. The application reads this file for each publish request:

```bash
gcloud run services update "$SERVICE" \
  --region "$REGION" \
  --remove-secrets=INSTAGRAM_ACCESS_TOKEN \
  --update-secrets="/secrets/instagram/access-token=${TOKEN_SECRET}:latest" \
  --update-env-vars=INSTAGRAM_ACCESS_TOKEN_FILE=/secrets/instagram/access-token
```

## Create the private refresh job

Enable scheduling, create a dedicated service account, and grant it access only
to the token secret:

```bash
gcloud services enable cloudscheduler.googleapis.com secretmanager.googleapis.com

gcloud iam service-accounts create "$AUTOMATION_SA_NAME" \
  --display-name="Instagram token renewal"

gcloud secrets add-iam-policy-binding "$TOKEN_SECRET" \
  --member="serviceAccount:${AUTOMATION_SA}" \
  --role=roles/secretmanager.secretAccessor

gcloud secrets add-iam-policy-binding "$TOKEN_SECRET" \
  --member="serviceAccount:${AUTOMATION_SA}" \
  --role=roles/secretmanager.secretVersionAdder

gcloud secrets add-iam-policy-binding "$TOKEN_SECRET" \
  --member="serviceAccount:${AUTOMATION_SA}" \
  --role=roles/secretmanager.secretVersionManager
```

Reuse the image currently deployed to the web service:

```bash
IMAGE_URL="$(gcloud run services describe "$SERVICE" \
  --region "$REGION" \
  --format='value(spec.template.spec.containers[0].image)')"

gcloud run jobs deploy "$REFRESH_JOB" \
  --region "$REGION" \
  --image="$IMAGE_URL" \
  --service-account="$AUTOMATION_SA" \
  --command=python \
  --args=-m,poetry_app.token_refresh \
  --set-env-vars="INSTAGRAM_ACCESS_TOKEN_FILE=/secrets/instagram/access-token,INSTAGRAM_SECRET_RESOURCE=${SECRET_RESOURCE},INSTAGRAM_GRAPH_API_VERSION=v26.0,INSTAGRAM_GRAPH_BASE_URL=https://graph.instagram.com" \
  --set-secrets="/secrets/instagram/access-token=${TOKEN_SECRET}:latest" \
  --tasks=1 \
  --max-retries=1 \
  --task-timeout=120s
```

## Schedule and test the job

```bash
gcloud run jobs add-iam-policy-binding "$REFRESH_JOB" \
  --region "$REGION" \
  --member="serviceAccount:${AUTOMATION_SA}" \
  --role=roles/run.invoker

gcloud scheduler jobs create http "$SCHEDULER_JOB" \
  --location="$REGION" \
  --schedule="0 4 * * 1" \
  --time-zone="Europe/Istanbul" \
  --uri="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${REFRESH_JOB}:run" \
  --http-method=POST \
  --oauth-service-account-email="$AUTOMATION_SA"
```

A long-lived Instagram token must be old enough for Meta to refresh it. After at
least 24 hours, test the private job manually:

```bash
gcloud run jobs execute "$REFRESH_JOB" --region "$REGION" --wait
```

Successful output identifies the Instagram username, new Secret Manager version,
and lifetime in seconds. It does not print the credential.
