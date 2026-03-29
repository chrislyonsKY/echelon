# Copilot Model Policy

**Last Updated:** 2026-03-29

This document defines the acceptable use policy, security constraints, and operational boundaries for the Echelon AI copilot.

---

## Overview

The Echelon copilot is a multi-provider BYOK (Bring Your Own Key) AI assistant embedded in the investigation sidebar. It supports Anthropic, OpenAI, Google, and self-hosted Ollama models. The copilot has access to structured tool calls that query the Echelon database and external APIs on behalf of the user.

---

## Acceptable Use

The copilot is designed exclusively for GEOINT/OSINT analysis tasks within the Echelon platform. Acceptable uses include:

- Querying convergence scores and signal data for specific regions or H3 cells
- Requesting vessel event summaries from Global Fishing Watch data
- Searching for recent news and conflict events in an area of interest
- Asking for explanations of Z-score anomalies and signal breakdowns
- Requesting nearby infrastructure context from OpenStreetMap data
- Generating analytical summaries of multi-source signal convergence

The copilot must not be used for purposes unrelated to geospatial intelligence analysis. The system prompt and guardrails restrict the copilot to Echelon-relevant queries.

---

## Hallucination Caveats

**Copilot outputs are not intelligence products.** Large language models generate plausible text that may contain factual errors, fabricated details, or incorrect analytical conclusions. Users must treat copilot responses as preliminary analysis aids, not authoritative assessments.

Specific risks:

- **Fabricated coordinates or event details.** The copilot may generate plausible-sounding locations, dates, or entity names that do not correspond to real data. Always cross-reference with the map and signal cards.
- **Incorrect causal reasoning.** The copilot may attribute convergence anomalies to causes that are not supported by the underlying data. Convergence scores reflect statistical co-occurrence, not causation.
- **Outdated information.** The copilot's base model has a knowledge cutoff. It may not be aware of recent geopolitical developments unless they are reflected in Echelon's ingested signals.
- **Confident but wrong.** LLMs do not express genuine uncertainty. A response that sounds authoritative may still be incorrect.

**All copilot outputs should be independently verified** against primary sources, the Echelon signal database, and established analytical methods before being used in any decision-making process.

---

## BYOK Key Handling

The copilot operates on a Bring Your Own Key model. Key handling follows strict security requirements:

### Default Mode (Browser-Only)

- The API key is stored in the browser's localStorage
- The key is sent to the backend in the `X-Anthropic-Key` request header for each copilot request
- The backend holds the key in memory for the duration of the request only
- The key is **never logged** at any log level
- The key is **never written** to the database, filesystem, or any persistent store
- The key is **never included** in error reports, stack traces, or monitoring data

### Server-Side Storage (Opt-In Only)

- Users may explicitly opt into encrypted server-side key storage via the Settings panel
- The key is encrypted using Fernet (AES-256) with the `BYOK_ENCRYPTION_KEY` environment variable
- The encrypted key is stored in the `users.byok_key_enc` database column
- The key is decrypted in memory only when processing a copilot request
- The key is **still never logged**, even in its encrypted form
- Users can delete their stored key at any time from the Settings panel

### Code Annotations

Any backend code that handles BYOK keys must include the comment:
```
# SECURITY: BYOK key -- do not log, do not persist beyond this scope
```

---

## Ollama Self-Hosted Option

Echelon includes an Ollama container in the Docker Compose stack for users who prefer fully local inference with no external API calls.

When using Ollama:

- No API key is required
- No data leaves the local network
- Model quality depends on the locally available model (smaller models will produce lower-quality analysis)
- Tool call support depends on the specific Ollama model; not all models support structured tool use
- The Ollama container runs on the internal Docker network at `http://ollama:11434`

This option is appropriate for air-gapped environments, sensitive analysis contexts, or users who do not want to send queries to third-party API providers.

---

## Rate Limiting on Tool Calls

Copilot tool calls that trigger live external API requests are rate-limited to prevent abuse and protect API quotas:

- **ACLED queries:** Maximum 1 request per second
- **GFW queries:** Respect `X-RateLimit-Remaining` response headers
- **Overpass (OSM) queries:** Maximum 1 request per 60 seconds for large spatial queries
- **NewsData.io queries:** Track and respect daily credit limits; log remaining credits on each call
- **Internal database queries** (convergence scores, signals): Rate-limited to prevent excessive database load from rapid copilot interactions

If rate limits are exceeded, the copilot returns a clear message to the user indicating the limit and when the next request can be made.

---

## Scope Restrictions

The copilot operates within defined guardrails that cannot be overridden by user prompts:

### What the Copilot CAN Do

- Query pre-computed convergence scores and Z-score breakdowns
- Retrieve signal records for specific H3 cells, bounding boxes, or time ranges
- Fetch vessel event data from ingested GFW records
- Search ingested news articles and GDELT events
- Summarize signal distributions and trends for a geographic area
- Identify nearby infrastructure using ingested OSM data
- Issue map control actions (fly to location, toggle layers, highlight cells)

### What the Copilot CANNOT Do

- Access, modify, or delete user account data
- Read or modify other users' saved AOIs or alert configurations
- Execute arbitrary database queries or raw SQL
- Access the filesystem, execute shell commands, or modify server configuration
- Make API calls to services not in its defined tool manifest
- Bypass rate limits or API quotas
- Access or reveal other users' BYOK keys
- Provide legally actionable intelligence assessments
- Perform attribution of attacks, conflicts, or incidents to specific actors with claimed certainty

---

## Disclaimer

The Echelon copilot is an analytical aid. Its outputs do not constitute intelligence products, legal advice, or operational recommendations. Users are solely responsible for verifying copilot outputs against primary sources and applying appropriate analytical tradecraft before acting on any information. The copilot's responses reflect statistical patterns in ingested open-source data and the probabilistic text generation of the underlying language model. Neither the Echelon project nor its contributors accept liability for decisions made based on copilot outputs.
