# Instagram Poetry To Slides App

An accessible, dependency-free prototype that I'm building for my grandpa who's a turkish poet. The app turns a poem into an editable Instagram carousel preview.

## What is included

- A large poem input with optional title, description, and photograph
- A Python preview API backed by an isolated Turkish stanza divider
- A touch/swipe carousel preview
- Preview-only four-line and beyit  two-line reflow controls
- Live 10-slide validation that counts the optional photograph
- An untouched optional photograph as the final carousel slide
- A configurable `@handle-` mark on every poem slide
- Order-safe controls for moving only boundary lines between slides
- A deliberately inactive Instagram publishing button
- No database, uploads, credentials, or third-party runtime dependencies

The chosen photograph stays in the browser. It is never uploaded to the local
Python server in this prototype. Its final-slide preview uses the complete,
unedited image; poem slides continue to use the darkened photograph as a
readable background.

## Run

Python 3.11 or newer is recommended.

```bash
cd instagram-poetry-prototype
python -m poetry_app
```

Then open <http://127.0.0.1:8000>.

To use a different address or port:

```bash
python -m poetry_app --host 127.0.0.1 --port 8080
```

## Test

```bash
python -m unittest discover -s tests -v
```

## Project structure

```text
poetry_app/
├── __main__.py          # CLI entry point
├── poem_divider.py      # Replaceable poem-splitting policy
├── server.py            # Small HTTP server and JSON API
└── static/
    ├── app.js           # Composer, carousel, and line-moving behavior
    ├── index.html       # Accessible application shell
    └── styles.css       # Responsive editorial interface
tests/
├── test_poem_divider.py
└── test_server.py
```

## Current dividing policy

The divider normalizes line endings, separates stanzas at blank lines, and
chunks each stanza into groups of two or four non-empty lines. It intentionally
does not combine separate stanzas. That conservative rule is easy to replace
later without changing the web interface or server route.

The preview starts in four-lines (dörtlük) view. Beyit view initially groups two lines (beyit) per
slide, but the line editor still allows up to four lines on every slide. To
preserve poem order, only the first line can move backward and only the last
line can move forward. Switching views rebuilds the grouping from the original
poem, so prior manual moves are reset. Beyit view is unavailable when its poem
slides plus the optional photo would exceed the 10-slide carousel limit. Change
the temporary Instagram handle in `poetry_app/static/app.js` when the real
handle is known.

## Natural next steps

1. Improve line grouping using typography measurements and Turkish-language
   heuristics.
2. Render export-ready 1080 × 1350 images on the server.
3. Persist drafts and provide reusable visual themes.
4. Add Meta authentication and Instagram Graph API publishing.
