# Google Cloud Run deployment

This deployment intentionally starts without the Instagram access token. The
current application does not yet authenticate users, so adding the real token
would expose the publishing endpoint to the public internet.

## Runtime configuration

The container listens on Cloud Run's `PORT`, writes temporary JPEGs under
`/tmp/poetry-media`, and serves randomized `/media/<id>.jpg` paths from the same
service. Deploy this prototype with exactly one maximum instance so Instagram's
media requests reach the instance that rendered the temporary files.

Recommended first-deployment settings:

- Region: `europe-west1` (Belgium)
- Authentication: allow public access
- CPU: 1
- Memory: 512 MiB
- Minimum instances: 0
- Maximum instances: 1
- Concurrency: 20
- Request timeout: 300 seconds

## Browser-based deployment

1. Create a Google Cloud project with billing enabled.
2. Open Cloud Shell in the Google Cloud Console.
3. Upload `cloud-run-source.zip` and extract it.
4. Select the project and enable the required services.
5. Deploy from source.

Replace `YOUR_PROJECT_ID` in these commands:

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
unzip cloud-run-source.zip -d instagram-poetry-app
cd instagram-poetry-app
gcloud run deploy siirden-karelere --source . --region europe-west1 --allow-unauthenticated --cpu 1 --memory 512Mi --concurrency 20 --timeout 300 --max-instances 1 --min-instances 0
```

The command prints a permanent HTTPS service URL when deployment succeeds. At
this stage previewing should work and publishing should remain disabled.

## Protect the hosted application

Before attaching the Instagram token, create two Secret Manager secrets: a
family-chosen application password and a random session-signing secret. Attach
them to Cloud Run as `APP_PASSWORD` and `APP_SESSION_SECRET`. The hosted
container also sets `REQUIRE_AUTH_FOR_PUBLISH=true`, so publishing cannot be
enabled unless both secrets are present.

The application remembers a successful login for 30 days using a signed,
HTTP-only, secure cookie. `/health` and randomized `/media/<id>.jpg` files remain
public so Google and Instagram can access them; the composer and every API
endpoint require the signed session.

## Before enabling real publishing

After application authentication is active, set the permanent service URL as
`PUBLIC_MEDIA_BASE_URL`, set `INSTAGRAM_HANDLE`, and attach the Instagram token
through Google Secret Manager rather than a plain environment variable.

The one-instance temporary-storage design is suitable for this single-user
prototype. Moving media to object storage is the appropriate later step if the
service needs multiple instances or stronger resilience during instance
restarts.

## Automatic token renewal

After a live publish succeeds, follow `TOKEN_RENEWAL.md` to move the token from a
pinned environment variable to a latest-version Secret Manager volume and create
the private weekly refresh job. The job validates the refreshed token before
adding a secret version and never logs the credential.
