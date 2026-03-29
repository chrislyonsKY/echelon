# Security Policy

## Supported Versions

Security fixes are provided for the current `main` branch and the latest tagged `0.1.x` release line.

| Version | Supported |
|---------|-----------|
| `main` | Yes |
| Latest `0.1.x` | Yes |
| Older versions | No |

If you are running a self-hosted deployment, especially on a VPS or DigitalOcean droplet, you are responsible for pulling updates promptly and rebuilding containers after a fix is released.

## Reporting a Vulnerability

Do not report security vulnerabilities in public GitHub issues, discussions, or pull requests.

Report vulnerabilities by email to **security@chrislyons.dev** with a subject like:

`[Security] Echelon - brief description`

Please include:

- A clear description of the issue
- Affected component or file path if known
- Steps to reproduce
- Expected impact
- Whether the issue is confirmed locally, in Docker, or on a live deployment
- Any proof-of-concept details needed to reproduce safely
- Suggested mitigation, if you have one

Expected response targets:

- Acknowledgment within **72 hours**
- Triage response within **7 days**
- Status updates as material information changes

## Coordinated Disclosure

Please give maintainers a reasonable opportunity to validate and patch the issue before public disclosure. If a fix is accepted, we may coordinate timing for release notes, attribution, and disclosure language.

## Scope

### In Scope

The following are generally in scope for this repository and its default deployment model:

- Authentication and session management flaws
- BYOK key handling, leakage, or unintended persistence
- Authorization issues affecting saved AOIs, alerts, or user data
- SQL injection, command injection, template injection, or deserialization flaws
- SSRF, open redirect, or unsafe remote fetch behavior introduced by project code
- CORS, cookie, or proxy-related security flaws caused by project configuration
- Sensitive data exposure in logs, API responses, exports, or task payloads
- Vulnerabilities in the FastAPI backend, frontend, Celery tasks, or Docker configuration that are caused by this project

### Out of Scope

The following are generally out of scope unless Echelon introduces the issue directly:

- Bugs in upstream providers such as GitHub, OpenSky, Global Fishing Watch, Capella, Maxar, Anthropic, OpenAI, Google, Redis, PostgreSQL, Docker, or Cloudflare
- Weaknesses that require privileged access you already control on your own server
- Rate limits, data quality issues, incomplete source coverage, or stale third-party data
- Social engineering, phishing, or physical access attacks
- Denial-of-service testing against production infrastructure without prior written approval
- Automated internet-wide scanning of infrastructure not explicitly owned for testing

## Safe Harbor for Researchers

If you act in good faith and stay within this policy, we will not pursue claims for your research. In return, you must:

- Avoid violating privacy or exfiltrating data beyond what is necessary to prove the issue
- Avoid degrading service availability
- Avoid destroying or modifying production data
- Stop testing and contact us if you access data that is clearly sensitive or not yours

## Project-Specific Security Notes

Echelon has a few security-sensitive areas that deserve extra care:

- **BYOK model keys**: provider keys should be passed only as intended by the app flow and should never be committed, logged, or persisted unexpectedly.
- **Open-source intelligence and imagery inputs**: many sources are remote, public, and untrusted. Treat all fetched content and metadata as hostile input.
- **Exports and evidence**: exported GeoJSON, KML, CSV, linked evidence, and analyst notes should not leak internal secrets, cookies, or credentials.
- **Self-hosted production**: if you run Echelon behind Cloudflare, Nginx, or another reverse proxy, ensure HTTPS is configured correctly and cookies remain protected end to end.
- **Task workers**: Celery and scheduled ingest tasks should not expose credentials in logs, retries, or tracebacks.

## Preferred Report Quality

High-quality reports usually include:

- Exact endpoint, route, or component affected
- Minimal reproducible request or payload
- Whether the issue depends on environment variables or deployment topology
- Concrete impact, not just a theoretical class of bug
- Clear separation between confirmed behavior and speculation

## What Not To Send

To keep handling safe and efficient, please do not send:

- Large database dumps
- Real user credentials
- Malware samples unrelated to proving the issue
- Mass-scanned vulnerability output with no project-specific validation

If credentials or tokens were accidentally exposed, rotate them first if possible and then send only the minimum details needed to investigate.

## Security Fixes and Release Notes

Accepted security fixes may be documented in [CHANGELOG.md](CHANGELOG.md). In some cases, details may be delayed or summarized briefly until a patch is broadly available.
