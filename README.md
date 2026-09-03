# Şiirden Karelere

Şiirden Karelere is a small, single-user web application that I built for my 
grandpa who is a turkish-bulgarian poet and was afraid to use Instagram. 

He had been posting in text format on Facebook for a long time, so the idea was
to automate the formatting and publishing side of things so that he could publish
here too by using the exact same workflow.

The app turns a poem or other line-based text into an Instagram-ready image carousel. 
It provides an editable preview, renders the final 1080 × 1350 JPEGs on the server, 
and can publish a single image or carousel through Instagram's API.

The interface is in Turkish. The source and deployment documentation are in
English so the project can be reused and hosted independently.

> **Project status:** this is a focused personal publishing tool, not a
> multi-user SaaS application. Previewing works without Instagram credentials.
> Publishing requires a professional Instagram account, a Meta developer app,
> and a valid access token.

## Features

- Exact, server-rendered previews using the same renderer as the published JPEGs
- Word-boundary wrapping for long Turkish, Bulgarian, and other Unicode lines
- Dörtlük (quatrain), Beyit (couplet), and Bent (other stanzas up to 7) layout choices
- Automatic and fixed 5-, 6-, or 7-line Bent grouping
- Up to 63 logical lines across at most nine text slides
- Optional uncropped photograph as the final, tenth slide
- Manual movement of boundary lines between neighboring slides
- Optional title, description/caption, and Instagram handle
- Single-image and carousel publishing through Instagram API with Instagram Login
- Password protection for a hosted single-user installation
- Installable Progressive Web App for Windows and other supported platforms
- Automatic cleanup of temporary preview and publishing files

## How it works

1. The browser sends the poem and selected layout to the Python server.
2. The server preserves line order, divides the text into slides, and renders
   baseline RGB JPEG previews at Instagram's portrait size (1080 × 1350).
3. The user can change layouts or move a slide's first/last line to a neighbor.
   Every change is rendered again, so wrapping and vertical fit are checked on
   the real output rather than approximated in HTML.
4. On publish, the server creates fresh JPEGs and exposes them temporarily at
   randomized HTTPS `/media/<id>.jpg` URLs.
5. Instagram downloads those files, processes the media containers, and creates
   the post. Successfully published temporary files are then removed.

The browser never receives the Instagram access token. Unused previews and
files left after a failed publish are removed by a later render after 24 hours.

## Layout rules and limits

This publishing client is capped at ten carousel images, so the application
reserves up to nine slides for text and one for an optional photograph.

- **Dörtlük:** preserves blank-line stanza boundaries and groups non-empty lines
  in fours. It is unavailable from 37 lines onward.
- **Beyit:** preserves stanza boundaries and groups non-empty lines in pairs. It
  is available only when the result fits in the ten-slide carousel.
- **Bent / Otomatik:** balances all lines over nine slides. If the total is not
  divisible by nine, the extra lines are placed on the final slides.
- **Bent / 5'lik, 6'lık, 7'lik:** fills slides with the chosen number and places
  the remainder on the last text slide. A fixed mode is disabled above 45, 54,
  or 63 lines respectively.

Text longer than the available width wraps automatically. If all wrapped text
cannot fit vertically even at the minimum font size, the preview reports that
specific slide; move one or more logical lines to another slide or shorten the
input. A successful rendered preview is the publishing contract.

## Requirements

- Python 3.11 or newer for local use
- Pillow (installed from `requirements.txt`)
- A modern browser
- For publishing: a professional Instagram account and a Meta access token with
  the permissions required for basic account access and content publishing
- A public HTTPS origin from which Instagram can download the temporary JPEGs

Meta's current Instagram Login setup uses the
[`instagram_business_basic` and `instagram_business_content_publish` scopes](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login).
The application does not perform the OAuth onboarding flow; the operator supplies
the resulting token through local configuration or the hosting platform's secret
manager.

## Run locally

Clone the repository, create an isolated Python environment, and install the
dependencies:

```bash
git clone https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
python -m venv .venv
```

Activate the environment:

```bash
# Linux or macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Then install and start the application:

```bash
python -m pip install -r requirements.txt
cp .env.example .env        # Windows: Copy-Item .env.example .env
python -m poetry_app
```

Open <http://127.0.0.1:8000>. With the example values unchanged, previewing is
available and the real publish button remains disabled.

### Enable local Instagram publishing

Edit `.env` and set at least:

```dotenv
INSTAGRAM_ACCESS_TOKEN=your-long-lived-token
INSTAGRAM_HANDLE=@your_handle
PUBLIC_MEDIA_BASE_URL=https://your-public-media-origin.example
```

Instagram must fetch the generated JPEGs through public HTTPS. During local
development, expose **only the media server on port 8001** through an HTTPS
tunnel; keep the composer and token-bearing application on port 8000 private.
For example:

```bash
cloudflared tunnel --url http://127.0.0.1:8001
```

Put the tunnel's HTTPS URL in `PUBLIC_MEDIA_BASE_URL`, restart the application,
and create a new preview. A changing quick-tunnel address must be copied into
`.env` after every change.

## Configuration

All configuration is read from environment variables; a local `.env` file is
loaded automatically.

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_PASSWORD` | Password for the hosted single-user login | empty |
| `APP_SESSION_SECRET` | Secret used to sign login sessions | empty |
| `SESSION_MAX_AGE_SECONDS` | Login lifetime | `2592000` (30 days) |
| `REQUIRE_AUTH_FOR_PUBLISH` | Refuse publishing unless login protection is complete | `false` locally; `true` in the container |
| `INSTAGRAM_ACCESS_TOKEN` | Instagram user access token | empty |
| `INSTAGRAM_ACCESS_TOKEN_FILE` | Optional mounted token file; preferred over the variable above | empty |
| `INSTAGRAM_USER_ID` | Optional account ID; resolved from `/me` when blank | empty |
| `INSTAGRAM_HANDLE` | Handle printed on text slides | `@handle-` |
| `PUBLIC_MEDIA_BASE_URL` | Public HTTPS origin used in Instagram media URLs | empty |
| `INSTAGRAM_GRAPH_API_VERSION` | Graph API version used by the client | `v26.0` |
| `INSTAGRAM_GRAPH_BASE_URL` | Instagram Graph base URL | `https://graph.instagram.com` |
| `MEDIA_DIR` | Temporary JPEG directory | `instance/media` |
| `MEDIA_SERVER_ENABLED` | Start the separate local media server | `true` locally; `false` in the container |
| `MEDIA_HOST` / `MEDIA_PORT` | Local media server binding | `127.0.0.1` / `8001` |

`APP_PASSWORD` and `APP_SESSION_SECRET` must always be configured together.
Never commit `.env`, tokens, passwords, secret files, or rendered personal media.

## Deploy to Google Cloud Run

The included `Dockerfile` is ready for Cloud Run. These commands use Cloud Shell,
so no local Docker installation is required. Replace the three values first:

```bash
PROJECT_ID="your-google-cloud-project"
REGION="europe-west1"
SERVICE="your-service-name"
```

Select the project, enable the required services, and deploy from the repository
root:

```bash
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

Cloud Run [builds and deploys directly from source](https://cloud.google.com/run/docs/deploying-source-code).
The first deployment is deliberately preview-only: the container requires login
protection before it will enable publishing.

### Add login and Instagram secrets

In Google Cloud Secret Manager, create these three secrets and give each an
initial version:

| Secret name | Value |
| --- | --- |
| `poetry-app-password` | A strong password chosen for the app user |
| `poetry-session-secret` | A long random value used only for signing sessions |
| `instagram-access-token` | The long-lived Instagram access token |

Using Secret Manager avoids placing credentials in the repository or deployment
command. Google documents both [creating secrets](https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets)
and [attaching them to Cloud Run](https://cloud.google.com/run/docs/configuring/services/secrets).

After the secrets exist, attach them and set the public service URL:

```bash
SERVICE_URL="$(gcloud run services describe "$SERVICE" \
  --region "$REGION" \
  --format='value(status.url)')"

gcloud run services update "$SERVICE" \
  --region "$REGION" \
  --update-secrets=APP_PASSWORD=poetry-app-password:latest,APP_SESSION_SECRET=poetry-session-secret:latest,INSTAGRAM_ACCESS_TOKEN=instagram-access-token:latest \
  --update-env-vars=PUBLIC_MEDIA_BASE_URL="$SERVICE_URL",INSTAGRAM_HANDLE="@your_handle"
```

If prompted, allow the Cloud Run service identity to access those secrets. Open
`$SERVICE_URL`, sign in with the application password, render a test preview,
and publish only when the preview is correct. The health endpoint is available at
`/health`.

### Important Cloud Run limitation

Keep `--max-instances 1`. Generated media lives on one instance's temporary disk;
with multiple instances, Instagram's download request could reach a different
instance and receive a 404. The current design is appropriate for a small
single-user deployment. Use shared object storage before scaling horizontally.

To deploy an update later, pull the new source and run the same `gcloud run deploy`
command. Existing environment variables and secrets remain attached unless the
deployment command explicitly replaces them.

Optional long-lived token rotation support is implemented in
`poetry_app/token_refresh.py`; see [TOKEN_RENEWAL.md](TOKEN_RENEWAL.md) for the
Cloud Run Job and Cloud Scheduler setup.

## Install as a desktop app

After deployment, open the HTTPS service in Microsoft Edge and select the
in-app **Bilgisayara yükle** action. The installed PWA opens in its own window
and follows future server deployments automatically. Only the static application
shell and icons are cached; poems, photos, rendered media, login responses, and
API responses are not cached. See [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md).

## Tests

The test suite renders real JPEGs and uses a fake Instagram transport. It does
not read the configured token and does not create a live post.

```bash
python -m unittest discover -s tests -v
```

## Repository structure

```text
poetry_app/
├── __main__.py          # Command-line entry point
├── auth.py              # Signed single-user sessions
├── instagram_client.py  # Instagram API and media-container polling
├── media_server.py      # Local read-only media origin
├── poem_divider.py      # Dörtlük, Beyit, and Bent grouping
├── publisher.py         # Validation and publish orchestration
├── renderer.py          # Exact 1080 × 1350 JPEG renderer
├── server.py            # HTTP routes and JSON endpoints
├── settings.py          # Environment-backed configuration
├── token_refresh.py     # Optional token rotation job
└── static/              # Turkish UI, PWA manifest, icons, and offline shell
scripts/                 # Asset-generation helpers
tests/                   # Unit and integration tests
Dockerfile               # Cloud Run container
.env.example             # Safe configuration template
```

## Security and privacy notes

- Treat the Instagram token like a password. Rotate it immediately if it has
  ever been committed or placed in a public build artifact.
- `/media/<random-id>.jpg` must be publicly reachable so Instagram can download
  it. The URLs are unlisted and temporary, but they are not authenticated.
- `/health` remains public for platform health checks. With app protection
  enabled, the composer and API endpoints require a signed, secure, HTTP-only
  session cookie.
- The application has no database or user accounts. Do not expose an unprotected
  deployment containing a usable Instagram credential.

