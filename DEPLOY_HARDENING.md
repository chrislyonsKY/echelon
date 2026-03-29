# Deployment Hardening

## Purpose

This guide covers baseline hardening for self-hosted Echelon deployments, especially Docker-based VPS deployments such as DigitalOcean droplets.

It is not a complete ops manual. It is a minimum baseline.

## Network Exposure

Only expose what must be public.

Recommended public exposure:

- reverse proxy on `80/443`

Do not expose these directly to the internet:

- Postgres
- Redis
- Flower
- internal backend container ports

Use host firewall rules and verify Docker is not publishing internal services accidentally.

## TLS and Proxying

- Use HTTPS end to end where possible
- Set the correct proxy headers so secure cookies and redirect behavior are preserved
- If Cloudflare or another CDN is in front, do not downgrade origin security carelessly
- Validate GitHub OAuth callback URLs against the public production hostname

## Secrets

- Never commit `.env`
- Use strong unique values for `SECRET_KEY`, database passwords, and `BYOK_ENCRYPTION_KEY`
- Store secrets with restrictive file permissions
- Rotate secrets if host compromise is suspected
- Remove unused API keys from the environment

## Host Baseline

- Keep the host OS updated
- Keep Docker and Compose updated
- Disable password SSH logins where practical
- Prefer SSH keys
- Restrict SSH access by source IP when possible
- Use non-root administration for normal operations

## Containers and Services

- Run only the required services
- Restart containers after secret rotation or base-image security updates
- Pin dependency versions in images where practical
- Watch container logs for repetitive failures that may leak sensitive input

## Database and Redis

- Bind services to private interfaces only
- Require authentication where supported and used
- Back up Postgres regularly
- Treat Redis as sensitive internal infrastructure, not a public cache

## Flower

If Flower is enabled:

- protect it with authentication
- avoid exposing it publicly unless there is a strong operational reason
- prefer VPN, SSH tunnel, or restricted admin access

## Logging

- Do not log API keys, cookies, or BYOK headers
- Review reverse-proxy logs for header leakage
- Keep enough logs for diagnosis without storing unnecessary sensitive content

## Backups and Recovery

At minimum:

- back up the Postgres database
- document how to restore the stack on a fresh host
- test restore procedures periodically
- keep backups separate from the running host

## Update Workflow

For production updates:

1. Pull reviewed code
2. Rebuild containers
3. Run migrations
4. Verify health endpoints
5. Verify auth, workers, and source ingestion

After major updates, confirm:

- secure cookies still behave correctly behind the proxy
- task workers can reach required upstream providers
- no internal service ports became public

## Recommended Future Hardening

- dependency and container-image vulnerability scanning in CI
- basic rate limiting on public routes
- monitoring and alerting for worker failure and disk growth
- periodic secret rotation
- separate production and staging environments
