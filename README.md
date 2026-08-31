# Şiirden Karelere

A small Python application that turns a Turkish poem into an editable Instagram
carousel and publishes the finished images through the Instagram API.

## Included

- Large poem input with optional title, description, and photograph
- Replaceable Turkish stanza divider in `poetry_app/poem_divider.py`
- Touch/swipe carousel preview with preview-only dörtlük and beyit layouts
- Order-safe line movement with a four-line capacity on every poem slide
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

The divider normalizes line endings, separates stanzas at blank lines, and
chunks each stanza into groups of two or four non-empty lines. It does not
combine separate stanzas.

The preview starts in dörtlük view. Beyit view initially groups two lines per
slide, while the editor still permits up to four. Only the first line can move
backward and only the last line can move forward. Switching layouts rebuilds
the grouping from the original poem and resets manual moves. Beyit view is
unavailable when its poem slides plus the optional photo exceed 10 slides.

The final photograph slide preserves the whole image and has no overlay, crop,
or filter. To satisfy Instagram's JPEG publishing and consistent carousel
dimensions, non-4:5 photographs are centered on a dark 1080 × 1350 canvas.

## Troubleshooting

If Instagram returns error `9004` with subcode `2207052`, verify the tunnel URL
still matches `PUBLIC_MEDIA_BASE_URL`, restart Python after changing `.env`, and
create a fresh preview. This version writes baseline RGB JPEGs rather than
progressive JPEGs so Meta's asynchronous media processor receives the most
interoperable form of the file.
