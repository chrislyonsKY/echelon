# DL-004: GitHub OAuth Only — No Password Authentication

**Date:** 2025-03-25
**Status:** Accepted
**Author:** Chris Lyons

## Context

Echelon needs user identity for saved AOIs and alert subscriptions. A full email/password auth system requires password hashing, reset flows, email verification, and introduces a password storage attack surface.

## Decision

GitHub OAuth only. No passwords stored. HttpOnly, SameSite=Lax signed session cookies (itsdangerous). Anonymous users get full read access — auth is required only for saved AOIs and alerts.

## Alternatives Considered

- **Full email/password** — Rejected: unnecessary complexity and security surface for a personal open-source tool.
- **Magic links** — Considered: simpler than OAuth but requires reliable email delivery for auth itself.
- **No auth at all** — Rejected: alert subscriptions require user identity for delivery and AOI ownership.

## Consequences

- GitHub account required for authenticated features.
- Session expiry is 7 days. Users must re-authenticate after expiry.
- The `authlib` library handles the OAuth exchange cleanly with FastAPI.
