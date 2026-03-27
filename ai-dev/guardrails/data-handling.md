# Data Handling Guardrails

---

## API Keys & Credentials

- **NEVER** hardcode API keys, passwords, tokens, or connection strings in any source file
- All secrets come from environment variables loaded via `app/config.py` (pydantic-settings)
- `.env` is always in `.gitignore` — never committed
- BYOK Anthropic keys are **never** written to logs, database (without explicit encrypted opt-in), or any persistent store

## BYOK Key Handling (Critical)

The user's Anthropic API key requires special handling:

```
Opt 1 (default): Browser localStorage only
  → Key never reaches the server
  → Frontend sends key in X-Anthropic-Key header per copilot request
  → FastAPI holds key in memory for request duration only
  → Key is never logged, never persisted

Opt 2 (user-initiated): Server-side encrypted storage
  → User explicitly enables this in Settings
  → Key is encrypted with Fernet (AES-256) using BYOK_ENCRYPTION_KEY env var
  → Stored in users.byok_key_enc column
  → Decrypted in memory only when a copilot request is processed
  → Still never logged
```

Any code that handles the BYOK key must include the comment:
```python
# SECURITY: BYOK key — do not log, do not persist beyond this scope
```

## User Data

- Do not write user email addresses to application logs
- Do not write GitHub usernames to application logs at INFO level or below (DEBUG only)
- Session tokens are HttpOnly cookies — they must never appear in JavaScript-accessible storage

## External Data Attribution

ACLED data requires attribution per their End User License Agreement. All UI surfaces displaying ACLED-derived data must include:
> "Data sourced from ACLED (Armed Conflict Location & Event Data Project) — acleddata.com"

GFW data:
> "Vessel data from Global Fishing Watch — globalfishingwatch.org"

## Signal Deduplication

The `dedup_hash` column on the `signals` table is `UNIQUE`. All ingestion tasks must compute:
```python
dedup_hash = sha256(f"{source}:{source_id}:{occurred_at.isoformat()}".encode()).hexdigest()
```

Ingestion tasks must use `INSERT ... ON CONFLICT (dedup_hash) DO NOTHING` — never blindly insert.

## Rate Limiting

All external API clients must implement backoff on 429/503 responses:
```python
# Minimum: exponential backoff with jitter, max 3 retries
# ACLED: 1 request/second max
# GFW: respect X-RateLimit-Remaining headers
# Overpass: 1 request per 60s for large queries; use area-based QL
# NewsData: respect daily credit limits — log remaining credits each call
```

## Data Retention

- Signals older than 365 days are eligible for deletion (the `trim_old_signals` Celery task)
- The `h3_cell_baseline` table is NOT trimmed — it accumulates statistics
- Alert records are retained indefinitely (users may want to review history)
- Celery task result backend (Redis) expires results after 24 hours
