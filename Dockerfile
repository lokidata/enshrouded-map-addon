# syntax=docker/dockerfile:1
# The tag keeps Dependabot on Python 3.13; the digest pins the exact image.
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS build
WORKDIR /build
# Dependencies pinned and hash-checked (requirements.lock comes from `make lock`).
COPY requirements.lock .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.lock

FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
ENV PATH=/opt/venv/bin:$PATH PYTHONPATH=/srv/src PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
 && mkdir /data && chown app /data
COPY --from=build /opt/venv /opt/venv
# pip is only needed to install the dependencies (build stage): remove it from the final image.
RUN /opt/venv/bin/python -m pip uninstall -y pip && /usr/local/bin/python -m pip uninstall -y pip
WORKDIR /srv
COPY src ./src
USER app
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/addon/', timeout=3)"]
# Single worker: the SQLite store holds one shared connection.
CMD ["uvicorn", "addon.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
