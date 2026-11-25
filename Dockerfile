# syntax=docker/dockerfile:1
# The UI is built here and only the static files travel on: the final image has no Node.
FROM node:24-slim@sha256:dc26ae92c9fb15cf6b1d63e20f0944b2efe0f115b20e00be48fb23fceb061c54 AS web
ENV NG_CLI_ANALYTICS=false
WORKDIR /web/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts
COPY frontend ./
RUN npm run build

# The tag keeps Dependabot on Python 3.13; the digest pins the exact image.
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS build
WORKDIR /build
# Dependencies pinned and hash-checked (requirements.lock comes from `make lock`).
COPY requirements.lock .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.lock

FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928
ENV PATH=/opt/venv/bin:$PATH PYTHONPATH=/srv/src PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# Fixed packages that the pinned base image does not have yet (apt); Dependabot moves the base forward.
RUN apt-get update && apt-get install -y --no-install-recommends --only-upgrade libc6 libc-bin libzstd1 zlib1g \
 && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
 && mkdir /data && chown app /data
COPY --from=build /opt/venv /opt/venv
# pip is only needed to install the dependencies (build stage): remove it from the final image.
RUN /opt/venv/bin/python -m pip uninstall -y pip && /usr/local/bin/python -m pip uninstall -y pip
WORKDIR /srv
COPY src ./src
COPY pyproject.toml ./
COPY --from=web /web/frontend/dist/browser ./frontend/dist/browser
USER app
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/addon/main.js', timeout=3)"]
# Single worker: the SQLite store holds one shared connection.
CMD ["uvicorn", "addon.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
