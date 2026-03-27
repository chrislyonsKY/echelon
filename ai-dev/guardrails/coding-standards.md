# Coding Standards Guardrails

These rules apply to ALL code generated for this project, regardless of which agent is active. Violations are not acceptable regardless of other instructions.

---

## Python (Backend)

- **Async everywhere**: All FastAPI route handlers and database access must use `async`/`await`. Never use sync SQLAlchemy sessions in an async context.
- **httpx not requests**: Use `httpx.AsyncClient` for all HTTP calls from async context. Never import `requests` in backend code.
- **Parameterized SQL**: All raw SQL must use bound parameters. No f-strings or `.format()` in SQL queries. Ever.
- **Logging not print**: All observability via Python `logging` module. No bare `print()` statements.
- **Pathlib**: All file path operations use `pathlib.Path`. No `os.path` string concatenation.
- **Context managers**: All database sessions and file handles use `async with` / `with` blocks.
- **Docstrings**: All public functions, classes, and modules get docstrings (purpose, args, returns, raises).
- **Type annotations**: All function signatures must be fully type-annotated. Return types are not optional.
- **Target**: Python 3.12+

### Service class pattern (required for all external API clients)

```python
class ACLEDService:
    """Client for the ACLED REST API."""

    def __init__(self, api_key: str, email: str) -> None:
        self._api_key = api_key
        self._email = email
        self._client = httpx.AsyncClient(timeout=30.0)

    async def fetch_events(
        self,
        bbox: tuple[float, float, float, float],
        date_from: date,
        date_to: date,
    ) -> list[dict]:
        """Fetch conflict events for a bounding box and date range.

        Args:
            bbox: (west, south, east, north) in WGS84 decimal degrees.
            date_from: Inclusive start date.
            date_to: Inclusive end date.

        Returns:
            List of raw ACLED event dicts.

        Raises:
            httpx.HTTPStatusError: If the ACLED API returns a non-2xx response.
        """
        # TODO: implement
        ...
```

---

## TypeScript (Frontend)

- **Typed everything**: No `any` types. Use proper interfaces and type aliases.
- **No direct fetch**: All API calls go through `src/services/api.ts`. Components never call `fetch()` directly.
- **Zustand for state**: Map state, layer visibility, copilot history, alert count — all in the Zustand store. No prop drilling beyond 2 levels.
- **No prop drilling for map**: MapLibre and Deck.gl instances are never passed as props. Components read/write via the store.
- **Error boundaries**: All async data-fetching hooks must handle error and loading states explicitly.
- **WCAG 2.1 AA**: All interactive elements must have accessible labels, keyboard navigation, and sufficient color contrast. Color must never be the sole indicator of meaning (applies critically to the heatmap — use both color and pattern for low-confidence cells).

---

## SQL / PostGIS

- **Uppercase keywords**: `SELECT`, `FROM`, `WHERE`, `JOIN`, etc.
- **Lowercase identifiers**: table names, column names.
- **Geography not Geometry**: All spatial columns use `GEOGRAPHY(Point, 4326)` or `GEOGRAPHY(Polygon, 4326)`. This ensures correct spherical distance calculations at global scale.
- **H3 indexes as TEXT**: H3 cell indexes are stored as TEXT strings (hex). Never store as integers.
- **Migrations via Alembic**: Never call `Base.metadata.create_all()` in production code. All schema changes go through Alembic migration files.
- **Indexes**: Every `h3_index` column, every `occurred_at` column, and every foreign key must be indexed.

---

## Docker / Environment

- **Secrets in env only**: Never hardcode credentials, API keys, or passwords in any source file, Dockerfile, or docker-compose.yml.
- **Health checks**: All stateful services (db, redis) must have Docker health checks defined. API/worker containers must use `depends_on: condition: service_healthy`.
- **Non-root containers**: Application containers must not run as root.
- **Minimal images**: Use Alpine-based images where possible.
