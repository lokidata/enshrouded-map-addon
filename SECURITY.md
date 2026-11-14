# Security policy

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's private reporting:
**[Report a vulnerability](https://github.com/lokidata/enshrouded-map-addon/security/advisories/new)** (Security tab of this repository). You will get an answer within a few days, and a fix and advisory once the problem is confirmed.

## Supported versions

Only the latest release (and `main`) receives security fixes.

## What is in place

- Supply chain: pinned GitHub Actions, locked Python dependencies (`uv.lock`), Dependabot, CodeQL, dependency review, secret scanning, Trivy, zizmor.
- Containers (once the image exists): pinned base image, non-root, read-only filesystem.
