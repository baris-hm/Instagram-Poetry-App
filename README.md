# Şiirden Karelere

A small Python application that turns a Turkish poem into an editable Instagram
carousel and publishes the finished images through the Instagram API.

## Included

- Large poem input with optional title, description, and photograph
- Replaceable Turkish stanza divider in `poetry_app/poem_divider.py`
- Touch/swipe carousel preview with dörtlük, beyit, and Bent layouts
- Automatic and fixed 5-, 6-, or 7-line Bent grouping for poems up to 63 lines
- Order-safe line movement with a layout-aware four- or seven-line capacity
- Dynamic 10-slide validation that counts the optional photograph
- Configurable Instagram handle on every poem slide
- Complete, uncropped photograph as the final slide, without text or filters
- Server-side 1080 × 1350 baseline RGB JPEG rendering
- Single-image and carousel publishing through Instagram Business Login
- A separate media-only server, so the access token and control endpoints stay local

The browser preview is only an approximation. Publishing creates fresh JPEGs on
the Python server, then gives Instagram short-lived public HTTPS URLs from which
to fetch them. Temporary files are deleted after a successful publish. Failed
publish files expire during a later render after 24 hours.

## First-time setup

Python 3.11 or newer is recommended.

```bash
cd instagram-poetry-prototype
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

Open `.env` and set:

```dotenv
INSTAGRAM_ACCESS_TOKEN=your-token-here
INSTAGRAM_HANDLE=@your-handle
PUBLIC_MEDIA_BASE_URL=https://your-public-media-host
```

`INSTAGRAM_USER_ID` is optional. When it is blank, the app resolves the account
from Instagram's `/me` endpoint. Never put the token in JavaScript, commit it to
Git, or send it to the public media host.

### Give Instagram access to the rendered JPEGs

Instagram downloads every publish image from a public HTTPS URL. For local
development, expose **only port 8001**, using an HTTPS tunnel such as
Cloudflare Tunnel or ngrok. Keep the application on port 8000 local.

One Cloudflare quick-tunnel workflow is:

```bash
cloudflared tunnel --url http://127.0.0.1:8001
```

Copy the generated `https://...trycloudflare.com` address into
`PUBLIC_MEDIA_BASE_URL`. The tunnel may be started before the Python server; if
it initially reports that the local origin is unavailable, leave it running and
start the app next. Restart the Python app whenever `.env` changes.

For a stable setup, use an HTTPS host or a named tunnel whose public address does
not change between restarts.

### Deploy to Google Cloud Run

The repository includes a `Dockerfile` for Cloud Run. The hosted service serves
temporary randomized JPEG URLs from the same public port and disables the
second local media server. See `CLOUD_RUN.md` for the browser-based deployment
steps and required single-instance configuration.

Do not configure the real Instagram access token on a public deployment until
user authentication has been added. Without it, anyone who discovers the
service URL could call the publishing endpoint.

Hosted deployments can set `APP_PASSWORD` and `APP_SESSION_SECRET` together to
enable the single-user login. Cloud Run should inject both from Secret Manager.
The signed login is remembered for 30 days by default; health checks and
randomized temporary media URLs remain public.

For a hosted app that does not require manual token replacement, mount the
Instagram token as a latest-version Secret Manager file and schedule the included
refresh job. See `TOKEN_RENEWAL.md` for the deployment and least-privilege IAM
steps.

## Run and publish

```bash
python -m poetry_app
```

Open <http://127.0.0.1:8000>, create the preview, arrange the lines, and select
**Instagram'da yayınla**. The browser asks for confirmation immediately before
the real API call. There is no dry-run publish: a successful click creates a
live Instagram post.

At startup the terminal should show both local origins:

```text
Public media origin: http://127.0.0.1:8001
Şiirden Karelere: http://127.0.0.1:8000
```

If the button remains disabled, its note identifies the missing `.env` value.
Instagram API errors are shown in the preview without exposing the token.
Publishing errors also identify whether a particular carousel item failed while
its container was being created, processed, or published.

To use another local app address or port:

```bash
python -m poetry_app --host 127.0.0.1 --port 8080
```

## Test

The tests render real JPEGs and exercise the publishing flow with a fake
Instagram transport; they never use the token or create a post.

```bash
python -m unittest discover -s tests -v
```

## Project structure

```text
poetry_app/
├── __main__.py          # Local CLI
├── instagram_client.py  # Instagram API calls and container polling
├── media_server.py      # Read-only public JPEG origin
├── poem_divider.py      # Replaceable poem-splitting policy
├── publisher.py         # Validation and publishing orchestration
├── renderer.py          # 1080 × 1350 JPEG rendering
├── server.py            # Local app and JSON endpoints
├── settings.py          # .env configuration
└── static/
    ├── app.js           # Composer, carousel, and publishing UI
    ├── index.html       # Accessible application shell
    └── styles.css       # Responsive editorial interface
tests/                   # Divider, server, renderer, settings and API tests
```

## Current layout policy

The divider normalizes line endings. Dörtlük and beyit views preserve blank-line
stanza boundaries and chunk each stanza into groups of four or two non-empty
lines. Bent view preserves line order while distributing all lines across the
poem slides.

The preview starts in Dörtlük view through 36 lines and switches to automatic
Bent view at 37 lines. Dörtlük is then unavailable. Automatic Bent view balances
up to 63 lines across nine poem slides, placing extra lines on the final slides.
The 5'lik, 6'lık, and 7'lik modes fill each slide to that size and leave the
remainder on the final poem slide; each fixed mode is unavailable above nine
full slides. Bent editing permits up to seven lines per slide, while Dörtlük and
Beyit editing permits up to four. Only the first line can move backward and only
the last line can move forward. Switching layouts rebuilds the grouping from
the original poem and resets manual moves.

The final photograph slide preserves the whole image and has no overlay, crop,
or filter. To satisfy Instagram's JPEG publishing and consistent carousel
dimensions, non-4:5 photographs are centered on a dark 1080 × 1350 canvas.

## Troubleshooting

If Instagram returns error `9004` with subcode `2207052`, verify the tunnel URL
still matches `PUBLIC_MEDIA_BASE_URL`, restart Python after changing `.env`, and
create a fresh preview. This version writes baseline RGB JPEGs rather than
progressive JPEGs so Meta's asynchronous media processor receives the most
interoperable form of the file.
