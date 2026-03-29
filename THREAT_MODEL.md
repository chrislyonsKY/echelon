# Threat Model

## Purpose

This document defines the main trust boundaries, protected assets, likely threat actors, and highest-value failure modes for Echelon.

Echelon is not a generic SaaS application. It is a GEOINT/OSINT platform that:

- fetches large amounts of untrusted third-party data
- proxies user-selected LLM traffic in BYOK mode
- runs scheduled ingest workers
- exposes mapping, export, and evidence workflows
- is commonly self-hosted on a VPS or single-node Docker deployment

That combination creates a different security profile from a normal CRUD dashboard.

## Security Objectives

The primary security goals are:

- protect user sessions and saved AOI data
- avoid leaking BYOK model credentials
- prevent malicious remote content from turning into code execution, SSRF expansion, or stored injection
- protect infrastructure secrets used by workers and scheduled ingest tasks
- preserve evidence provenance and avoid misleading confidence or attribution
- keep self-hosted deployments from exposing Redis, Postgres, or Flower publicly

## Protected Assets

High-value assets in this project include:

- session cookies and OAuth-linked user accounts
- BYOK model provider keys
- API tokens for data providers such as GFW, AISStream, NewsData, GNews, and Resend
- saved AOIs, alert metadata, and notification destinations
- raw source payloads and evidence links stored in the database
- export outputs generated for analysts
- deployment secrets on the host, in containers, and in CI

## Trust Boundaries

### Browser to Frontend

The browser is user-controlled and untrusted. Query strings, uploaded material, and all client-side inputs must be treated as hostile.

### Frontend to Backend

The backend is trusted to enforce authentication, authorization, validation, and output shaping. The frontend must not be treated as a security boundary.

### Backend to External Sources

Remote data providers, social feeds, RSS, imagery catalogs, and evidence URLs are all untrusted input sources. They may be malformed, hostile, stale, misleading, or serve unexpectedly large payloads.

### API to Worker Boundary

Celery workers operate with database and network access and often run unattended. They must be treated as privileged components. Retry logs, tracebacks, and task payloads can leak secrets if not handled carefully.

### Host and Reverse Proxy

Self-hosted deployments often run behind Cloudflare, Nginx, Caddy, or a DigitalOcean load balancer. Misconfigured proxy headers, TLS termination, or public exposure of internal services can undermine otherwise-correct application code.

## Likely Threat Actors

The most realistic threat actors for Echelon are:

- opportunistic internet attackers probing exposed Docker stacks
- researchers or users accidentally leaking tokens or session data
- malicious or compromised upstream content providers
- abusive users attempting to repurpose the tool for surveillance or unlawful targeting
- scrapers or bots abusing public routes for resource exhaustion
- contributors or dependency changes introducing supply-chain risk

## Key Attack Surfaces

### Authentication and Session Handling

Relevant risks:

- weak or inconsistent cookie settings
- OAuth callback or redirect misuse
- CSRF on state-changing routes
- insufficient separation between authenticated and unauthenticated features

### BYOK Proxy Flow

Relevant risks:

- API keys logged by backend, worker, or reverse proxy
- accidental persistence of keys server-side when browser-only handling is expected
- header forwarding bugs
- model prompt injection via hostile source content

### Third-Party Source Fetching

Relevant risks:

- SSRF expansion through user-supplied URLs or remote metadata
- ingestion of hostile HTML, XML, JSON, or imagery metadata
- parser failure leading to service degradation
- oversized payloads or slow upstreams exhausting worker capacity

### Evidence and Export Features

Relevant risks:

- reflected or stored XSS via titles, descriptions, or source metadata
- unsafe export content
- evidence links exposing users to malicious third-party destinations
- provenance confusion where unverified material appears authoritative

### Self-Hosted Infrastructure

Relevant risks:

- Redis, Postgres, or Flower exposed on the public internet
- stale container images or host packages
- secrets in `.env` files with weak file permissions
- missing backups and recovery plans

## Highest-Priority Abuse Cases

These are the failures that matter most:

1. BYOK keys exposed in logs, traces, exports, or database rows.
2. Session cookies misconfigured so an attacker can hijack or replay them.
3. Remote fetch pathways turned into SSRF or internal-network probing.
4. Hostile source content rendered into the UI without proper escaping.
5. Public Docker services exposed directly from the VPS.
6. Unverified OSINT or imagery presented in a way that overstates confidence.

## Existing Controls

Current controls in the project include:

- parameterized SQL access
- HttpOnly session cookies
- source-health telemetry for ingest visibility
- BYOK handling intended to avoid routine server-side persistence
- analyst-visible provenance and confirmation fields
- Docker-based deployment isolation

These reduce risk, but they do not eliminate the need for careful proxy configuration, secret handling, and defensive parsing.

## Recommended Controls

The following controls should remain in scope for future hardening work:

- strict output encoding and sanitized rendering for all remote metadata
- explicit allowlists for remote fetch destinations where practical
- timeouts, response-size limits, and content-type checks on remote fetches
- rate limiting on expensive public routes
- least-privilege container networking and no public Redis/Postgres exposure
- secret rotation guidance and incident response drills
- CI checks for dependency and container-image vulnerability scanning
- documented provenance labeling throughout analyst-facing UI

## Non-Goals

This threat model does not attempt to:

- solve upstream data quality or source bias
- guarantee correctness of third-party OSINT feeds
- describe every theoretical cloud or kernel-level attack
- authorize offensive or invasive use cases

It is meant to support practical engineering decisions for the codebase and the default self-hosted deployment model.
