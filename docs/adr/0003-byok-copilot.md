# ADR-0003: BYOK (Bring Your Own Key) for AI Copilot

**Status:** Accepted
**Date:** 2024-12-20

## Context

Echelon includes an AI copilot that helps analysts query conflict data, explain convergence scores, and generate situation reports. The copilot calls the Anthropic Claude API with tool use (6 tools: ACLED query, STAC search, Overpass query, GFW search, convergence lookup, event timeline).

The project is open-source and self-hosted. Funding API costs for all users is not viable. We need a model where users can access the copilot without the project bearing per-token costs.

Alternatives evaluated:

| Option | Pros | Cons |
|--------|------|------|
| **BYOK (user provides key)** | Zero project cost, user controls spend | UX friction, key management responsibility on user |
| Server-side project key | Seamless UX | Unsustainable cost, abuse risk, key liability |
| Freemium with usage caps | Good UX for light users | Requires billing infra, still costs money |
| Local LLM (Ollama) | No API cost, offline capable | Poor tool-use support, high hardware requirements |

## Decision

We will use a **BYOK model** where users provide their own Anthropic API key. The key is:

1. Stored in the browser's `localStorage` by default (anonymous users)
2. Sent to the backend via the `X-Anthropic-Key` request header on each copilot request
3. Held in server memory only for the duration of the request -- never written to disk or database
4. Optionally stored server-side with encryption for authenticated users who explicitly opt in

All copilot API calls are proxied through the FastAPI `/copilot` router. The frontend never calls the Anthropic API directly.

## Rationale

- **Zero operational cost:** The project incurs no per-token charges. Users pay Anthropic directly for their usage.
- **User controls spend:** Users can set their own usage limits in the Anthropic console. No surprise bills from the project.
- **No API key liability:** The project never holds a master API key that could be leaked or abused.
- **Privacy:** User queries go through our backend (for tool augmentation) but the API key is ephemeral. We log request metadata (timestamp, tool calls made) but never the key itself.
- **Opt-in server storage:** Authenticated users who want persistence across devices can opt into encrypted server-side storage, but this is never the default.

## Consequences

- **UX friction for new users:** Users must obtain an Anthropic API key before using the copilot. The UI includes a setup guide with a direct link to the Anthropic console.
- **Key security is critical:** The API key must never appear in server logs, error messages, database records, or Celery task arguments. The `X-Anthropic-Key` header is stripped from all logging middleware.
- **Rate limiting required:** Even though users pay for their own API usage, the copilot tool calls (ACLED, STAC, Overpass, GFW) hit external APIs from our server. Rate limiting per-user is enforced to prevent abuse of these shared resources.
- **No usage analytics:** Since we don't control the API key, we cannot track per-user token consumption server-side. Users must check their own Anthropic dashboard.
- **Frontend must handle key absence:** The copilot UI must gracefully degrade when no API key is configured, showing a setup prompt instead of an error.
