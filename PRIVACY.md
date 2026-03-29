# Privacy

## Purpose

This document explains the project-level privacy expectations for Echelon. It is not formal legal advice and is not a substitute for any site-specific privacy notice you may need for a public deployment.

## What Echelon Stores

Depending on configuration and use, Echelon may store:

- GitHub-linked user identity fields needed for authentication
- saved AOIs and alert preferences
- alert history
- signal records and raw source payloads
- evidence metadata and links
- operational logs

## What Echelon Does Not Intend To Store

Under the current intended flow, Echelon should not routinely persist:

- plaintext BYOK model provider keys
- private messages or private social-media content
- login-wall source content obtained through unauthorized access

If server-side encrypted BYOK storage is enabled, key handling must match the current feature and security documentation exactly.

## Third-Party Requests

Echelon communicates with third-party services such as:

- GitHub OAuth
- LLM providers in BYOK mode
- public data and imagery providers
- email delivery services such as Resend

Operators should assume those services receive the minimum request data necessary for the relevant feature.

## Self-Hosted Responsibility

If you run Echelon on your own infrastructure, you are responsible for:

- lawful handling of any user data you collect
- securing `.env` and deployment secrets
- configuring TLS and reverse proxies correctly
- setting retention and backup policies appropriate to your use case

## Logs

Operators should configure logging so that secrets, cookies, and BYOK headers are not stored. Logs should be useful for debugging without becoming a secondary database of sensitive material.

## Retention

Project defaults may trim some historical signal data, but retention behavior depends on deployment configuration and operational discipline. If you operate a public instance, define and publish your own retention policy for:

- user records
- saved AOIs
- alerts
- logs
- exports

## Sensitive Uses

Echelon is intended for lawful OSINT/GEOINT research and not for covert surveillance of private individuals. Operators and contributors should be cautious about feature work that expands personal-data collection or makes identification workflows easier without strong justification.
