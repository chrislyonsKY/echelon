# Echelon — Code Patterns

## Backend

### Celery task with async DB work
```python
@celery_app.task(bind=True, max_retries=3, acks_late=True)
def run(self):
    async def _run():
        async with AsyncSessionLocal() as session:
            ...
    try:
        asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=300)
```

### Bulk upsert (idempotent)
```python
stmt = pg_insert(Signal).values(rows)
stmt = stmt.on_conflict_do_nothing(index_elements=["dedup_hash"])
await session.execute(stmt)
await session.commit()
```

### H3 indexing at ingest
```python
h3_5 = h3.geo_to_h3(lat, lon, 5)
h3_7 = h3.geo_to_h3(lat, lon, 7)
h3_9 = h3.geo_to_h3(lat, lon, 9)
```

## Frontend

### API calls — always through api.ts
```typescript
const tiles = await convergenceApi.getTiles(resolution);  // CORRECT
const tiles = await fetch("/api/...").then(r => r.json()); // WRONG
```

### Zustand selectors
```typescript
const selectedCell = useEchelonStore(s => s.selectedCell);
```

### Deck.gl memoization
```typescript
const layer = useMemo(() => new H3HexagonLayer({
  id: "convergence",
  data: tiles,
  updateTriggers: { getFillColor: [tiles] },
}), [tiles]);
```

## Anti-Patterns
| Wrong | Right |
|-------|-------|
| `import requests` in async | `httpx.AsyncClient` |
| `Base.metadata.create_all()` | Alembic migrations |
| f-string SQL | Bound parameters |
| `fetch()` in component | `apiClient` from api.ts |
| Shared state in useState | Zustand store |
| Log the API key | Never — ever |
| Load full Sentinel-2 scene | rasterio windowed read |
