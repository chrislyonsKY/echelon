# Echelon — Prompt Templates

## Implement Service Client Method
```
Read ai-dev/agents/geoint_data_expert.md.
Read ai-dev/field-schema.md for expected data shapes.

Implement [MethodName] in app/services/[service].py.
- Use httpx.AsyncClient (initialized in __init__)
- Handle pagination, retry on 429/503
- Full docstring with Args, Returns, Raises
- Never log API keys
Show implementation only.
```

## Implement Celery Task
```
Read ai-dev/agents/architect.md.
Read ai-dev/patterns.md — Celery task with async DB work pattern.

Implement [TaskName] in app/workers/tasks/[file].py.
- asyncio.run() wrapper for async DB work
- ON CONFLICT DO NOTHING with dedup_hash (idempotent)
- Track last_run in Redis at echelon:ingest:[source]:last_run
- Return {'inserted': N, 'skipped': M}
Show implementation only.
```

## Implement Frontend Hook
```
Read ai-dev/agents/frontend_expert.md.

Implement use[HookName] in frontend/src/hooks/[file].ts.
- Use apiClient from src/services/api.ts
- Handle loading / error / empty states
- No `any` types
- Clean up intervals in useEffect return
Show hook only.
```

## Security Review
```
Read ai-dev/agents/qa_reviewer.md.
Read ai-dev/guardrails/data-handling.md.

Review for: BYOK key exposure, SQL injection, session token handling, input validation.
[PASTE CODE]
Return numbered issues: BLOCKER / WARNING / SUGGESTION.
```
