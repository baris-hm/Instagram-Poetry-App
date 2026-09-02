FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    MEDIA_DIR=/tmp/poetry-media \
    MEDIA_SERVER_ENABLED=false \
    REQUIRE_AUTH_FOR_PUBLISH=true

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY poetry_app ./poetry_app

RUN addgroup --system poetry-app \
    && adduser --system --ingroup poetry-app poetry-app \
    && mkdir -p /tmp/poetry-media \
    && chown poetry-app:poetry-app /tmp/poetry-media

USER poetry-app

EXPOSE 8080

CMD ["python", "-m", "poetry_app", "--host", "0.0.0.0"]
