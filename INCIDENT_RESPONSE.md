# Incident Response

## Purpose

This document describes the expected first-response workflow for security or safety incidents affecting Echelon code, infrastructure, secrets, or data handling.

## What Counts as an Incident

Examples include:

- exposed API keys, BYOK keys, OAuth secrets, or session secrets
- suspicious account access or session hijacking
- public exposure of Redis, Postgres, Flower, or admin tooling
- hostile remote content triggering unexpected application behavior
- unauthorized changes to production containers or host configuration
- accidental disclosure of user data, exports, or evidence metadata
- evidence that a deployment is being used for harmful or unlawful activity

## Response Priorities

Handle incidents in this order:

1. Contain the issue
2. Preserve only the logs and facts needed for diagnosis
3. Rotate secrets if exposure is plausible
4. Restore safe service
5. Document root cause and follow-up actions

## Immediate Containment Checklist

### If a Secret May Be Exposed

- Rotate the affected key or secret immediately
- Invalidate sessions if session material may be exposed
- Rebuild or restart affected containers after secret rotation
- Check reverse-proxy and application logs for additional leakage

### If Infrastructure Is Exposed

- Restrict public access at the firewall or load balancer first
- Confirm Redis, Postgres, and Flower are not reachable from the public internet
- Review Docker published ports and proxy configuration
- Snapshot the host only if needed for forensic review and safe to do so

### If Application Behavior Is Suspicious

- Disable the affected route, worker, or feature flag if possible
- Preserve relevant logs
- Identify whether the issue is active exploitation, malformed upstream content, or operator error

## DigitalOcean / VPS-Specific Actions

For the default self-hosted model:

- verify firewall rules and exposed ports
- inspect Docker container port mappings
- review reverse-proxy config and TLS settings
- rotate `.env` secrets if host compromise is plausible
- confirm backups exist before destructive remediation

## Communication

Use private channels for incident coordination. Do not post active incident details in public issues until containment and risk assessment are complete.

When public communication is necessary, include:

- what was affected
- what users should do
- whether secrets or user data may have been exposed
- whether a patch or mitigation is available

## Post-Incident Review

After containment, capture:

- incident timeline
- root cause
- affected components
- what data or secrets were at risk
- what controls failed
- what follow-up work is required

If the incident involved a vulnerability, cross-reference the report process in [SECURITY.md](SECURITY.md).
