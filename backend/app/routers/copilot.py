"""
Copilot router — BYOK Anthropic agent proxy.

The user's Anthropic API key is received in the X-Anthropic-Key header.
It is held in memory for the duration of this request only.
It is NEVER logged, NEVER persisted, and NEVER included in error messages.

See ai-dev/guardrails/data-handling.md for full BYOK key handling policy.
"""
import json
import logging
from datetime import date

import anthropic
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter()

MODEL = "claude-sonnet-4-6-20250514"

SYSTEM_PROMPT = """You are the Echelon GEOINT copilot — an expert analyst for the Echelon conflict and maritime monitoring dashboard.

You have access to tools that query live data from the Echelon database:
- Convergence Z-scores (pre-computed multi-source anomaly fusion per H3 cell)
- Signal events (GDELT conflict events, GFW vessel anomalies, news articles)
- News articles from NewsData, NewsAPI, and GNews

When answering:
- Be concise and analytical. Lead with findings, not process.
- Reference specific Z-scores, event counts, and signal types.
- When you identify a geographic area of interest, include a map_action in your response to fly the map there and highlight relevant cells.
- Always specify which signal sources contributed to your assessment.

Current map context:
- Viewport center: {center}
- Zoom level: {zoom}
- Date range: {date_from} to {date_to}
- Selected cell: {selected_cell}
"""

TOOL_MANIFEST = [
    {
        "name": "get_convergence_scores",
        "description": "Get pre-computed convergence Z-scores for H3 cells. High Z-scores indicate multiple independent signals elevated simultaneously above their historical baseline. Returns cells sorted by Z-score descending.",
        "input_schema": {
            "type": "object",
            "properties": {
                "resolution": {
                    "type": "integer",
                    "enum": [5, 7, 9],
                    "description": "H3 resolution: 5 (global ~252km²), 7 (regional ~5km²), 9 (tactical ~0.1km²)",
                },
                "min_z_score": {
                    "type": "number",
                    "description": "Minimum Z-score threshold. Default 1.0. Use 2.0+ for significant anomalies.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max cells to return. Default 20.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_signals_for_cell",
        "description": "Get individual signal events (GDELT conflicts, GFW vessel anomalies, news articles) for a specific H3 cell. Use this to drill into what's driving a convergence score.",
        "input_schema": {
            "type": "object",
            "properties": {
                "h3_index": {
                    "type": "string",
                    "description": "H3 cell index (hex string).",
                },
                "source": {
                    "type": "string",
                    "description": "Filter by source: 'gdelt', 'gfw', or 'newsdata'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max events. Default 20.",
                },
            },
            "required": ["h3_index"],
        },
    },
    {
        "name": "search_signals_by_area",
        "description": "Search for signal events within a geographic bounding box. Use this for regional queries like 'what's happening near the Strait of Hormuz'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bbox": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": "[west, south, east, north] in decimal degrees.",
                },
                "source": {
                    "type": "string",
                    "description": "Filter by source: 'gdelt', 'gfw', or 'newsdata'.",
                },
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD."},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD."},
                "limit": {"type": "integer", "description": "Max events. Default 30."},
            },
            "required": ["bbox"],
        },
    },
    {
        "name": "get_vessel_events",
        "description": "Query GFW vessel anomaly events — AIS gaps (dark vessels) and loitering. AIS gaps carry the highest signal weight (0.35) because they indicate vessels deliberately disabling tracking.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bbox": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": "[west, south, east, north].",
                },
                "event_type": {
                    "type": "string",
                    "enum": ["gfw_ais_gap", "gfw_loitering"],
                    "description": "Filter by vessel event type.",
                },
                "limit": {"type": "integer", "description": "Max events. Default 20."},
            },
            "required": ["bbox"],
        },
    },
    {
        "name": "get_news",
        "description": "Get recent conflict-related news articles ingested from NewsData, NewsAPI, and GNews. Useful for providing narrative context alongside quantitative signals.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bbox": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": "[west, south, east, north].",
                },
                "limit": {"type": "integer", "description": "Max articles. Default 10."},
            },
            "required": ["bbox"],
        },
    },
    {
        "name": "get_signal_summary",
        "description": "Get a statistical summary of all signals in the database grouped by source and signal type. Useful for overview questions like 'what data do you have'.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


class CopilotRequest(BaseModel):
    """Incoming copilot chat request."""
    messages: list[dict]
    map_context: dict


class CopilotResponse(BaseModel):
    """Copilot response with optional tool call summaries and map actions."""
    content: str
    toolCallsSummary: list[dict] | None = None
    mapAction: dict | None = None


@router.post("/chat")
async def copilot_chat(
    request: CopilotRequest,
    x_anthropic_key: str = Header(alias="X-Anthropic-Key"),
    session: AsyncSession = Depends(get_session),
) -> CopilotResponse:
    """Proxy a copilot chat request to the Anthropic API using the user's BYOK key.

    The key is received in X-Anthropic-Key header, used for this request only,
    and never logged or persisted.
    """
    # SECURITY: BYOK key — do not log, do not persist beyond this scope
    if not x_anthropic_key or not x_anthropic_key.startswith("sk-ant-"):
        raise HTTPException(status_code=401, detail="Invalid or missing Anthropic API key")

    # Build system prompt with map context
    ctx = request.map_context
    viewport = ctx.get("viewport", {})
    date_range = ctx.get("dateRange", {})
    system = SYSTEM_PROMPT.format(
        center=viewport.get("center", [0, 20]),
        zoom=viewport.get("zoom", 2),
        date_from=date_range.get("from", ""),
        date_to=date_range.get("to", ""),
        selected_cell=ctx.get("selectedCell", "none"),
    )

    # Initialize Anthropic client with user's key
    client = anthropic.AsyncAnthropic(api_key=x_anthropic_key)

    # Build messages
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in request.messages
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]

    tool_call_summaries: list[dict] = []

    try:
        # Agentic loop — handle tool calls until we get a final text response
        for _ in range(6):  # Max 6 tool call rounds to prevent runaway
            response = await client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=system,
                messages=messages,
                tools=TOOL_MANIFEST,
            )

            # Check if the response contains tool use
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            if not tool_use_blocks:
                # No tool calls — return the text response
                final_text = "\n".join(b.text for b in text_blocks)
                break

            # Process tool calls
            assistant_content = []
            tool_results = []

            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

                    # Execute the tool
                    result = await _dispatch_tool(block.name, block.input, session)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    })
                    tool_call_summaries.append({
                        "toolName": block.name,
                        "resultSummary": f"{len(result) if isinstance(result, list) else 1} results",
                    })

            # Add assistant message with tool use + tool results for next round
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

        else:
            final_text = "\n".join(b.text for b in text_blocks) if text_blocks else "I completed the analysis but ran out of tool call rounds."

    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid Anthropic API key")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Anthropic rate limit exceeded")
    except Exception:
        logger.exception("Copilot request failed")
        raise HTTPException(status_code=502, detail="Copilot request failed")

    # Extract map_action if the model included one (look for JSON in the response)
    map_action = _extract_map_action(final_text)

    return CopilotResponse(
        content=final_text,
        toolCallsSummary=tool_call_summaries or None,
        mapAction=map_action,
    )


async def _dispatch_tool(
    tool_name: str,
    tool_input: dict,
    session: AsyncSession,
) -> list[dict] | dict:
    """Execute a copilot tool call against the database.

    Args:
        tool_name: Name of the tool to execute.
        tool_input: Tool input parameters.
        session: Database session.

    Returns:
        Tool result (list of dicts or single dict).
    """
    if tool_name == "get_convergence_scores":
        return await _tool_convergence_scores(session, tool_input)
    elif tool_name == "get_signals_for_cell":
        return await _tool_signals_for_cell(session, tool_input)
    elif tool_name == "search_signals_by_area":
        return await _tool_signals_by_area(session, tool_input)
    elif tool_name == "get_vessel_events":
        return await _tool_vessel_events(session, tool_input)
    elif tool_name == "get_news":
        return await _tool_news(session, tool_input)
    elif tool_name == "get_signal_summary":
        return await _tool_signal_summary(session)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


async def _tool_convergence_scores(session: AsyncSession, params: dict) -> list[dict]:
    """Get top convergence Z-scores."""
    resolution = params.get("resolution", 7)
    min_z = params.get("min_z_score", 1.0)
    limit = min(params.get("limit", 20), 50)

    result = await session.execute(
        text("""
            SELECT h3_index, resolution, z_score, raw_score,
                   signal_breakdown, low_confidence
            FROM h3_convergence_scores
            WHERE resolution = :resolution AND z_score >= :min_z
            ORDER BY z_score DESC LIMIT :limit
        """),
        {"resolution": resolution, "min_z": min_z, "limit": limit},
    )
    return [
        {
            "h3_index": r.h3_index, "z_score": round(r.z_score, 2),
            "raw_score": round(r.raw_score, 4),
            "signal_breakdown": r.signal_breakdown,
            "low_confidence": r.low_confidence,
        }
        for r in result.fetchall()
    ]


async def _tool_signals_for_cell(session: AsyncSession, params: dict) -> list[dict]:
    """Get signals for a specific H3 cell."""
    h3_index = params["h3_index"]
    limit = min(params.get("limit", 20), 50)

    conditions = "(h3_index_5 = :h3 OR h3_index_7 = :h3 OR h3_index_9 = :h3)"
    bind = {"h3": h3_index, "limit": limit}

    if params.get("source"):
        conditions += " AND source = :source"
        bind["source"] = params["source"]

    result = await session.execute(
        text(f"""
            SELECT source, signal_type, occurred_at,
                   ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lon,
                   weight, raw_payload, source_id
            FROM signals WHERE {conditions}
            ORDER BY occurred_at DESC LIMIT :limit
        """),
        bind,
    )
    return [
        {
            "source": r.source, "signal_type": r.signal_type,
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "lat": r.lat, "lon": r.lon, "weight": r.weight,
            "details": _summarize_payload(r.raw_payload),
            "source_id": r.source_id,
        }
        for r in result.fetchall()
    ]


async def _tool_signals_by_area(session: AsyncSession, params: dict) -> list[dict]:
    """Search signals within a bounding box."""
    bbox = params["bbox"]
    limit = min(params.get("limit", 30), 50)
    bind: dict = {"west": bbox[0], "south": bbox[1], "east": bbox[2], "north": bbox[3], "limit": limit}

    conditions = "ST_Intersects(location, ST_MakeEnvelope(:west, :south, :east, :north, 4326))"
    if params.get("source"):
        conditions += " AND source = :source"
        bind["source"] = params["source"]
    if params.get("date_from"):
        conditions += " AND occurred_at >= :date_from"
        bind["date_from"] = params["date_from"]
    if params.get("date_to"):
        conditions += " AND occurred_at <= :date_to"
        bind["date_to"] = params["date_to"]

    result = await session.execute(
        text(f"""
            SELECT source, signal_type, occurred_at,
                   ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lon,
                   weight, raw_payload, source_id
            FROM signals WHERE {conditions}
            ORDER BY occurred_at DESC LIMIT :limit
        """),
        bind,
    )
    return [
        {
            "source": r.source, "signal_type": r.signal_type,
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "lat": r.lat, "lon": r.lon, "weight": r.weight,
            "details": _summarize_payload(r.raw_payload),
        }
        for r in result.fetchall()
    ]


async def _tool_vessel_events(session: AsyncSession, params: dict) -> list[dict]:
    """Get GFW vessel events within a bbox."""
    bbox = params["bbox"]
    limit = min(params.get("limit", 20), 50)
    bind: dict = {"west": bbox[0], "south": bbox[1], "east": bbox[2], "north": bbox[3], "limit": limit}

    conditions = "source = 'gfw' AND ST_Intersects(location, ST_MakeEnvelope(:west, :south, :east, :north, 4326))"
    if params.get("event_type"):
        conditions += " AND signal_type = :event_type"
        bind["event_type"] = params["event_type"]

    result = await session.execute(
        text(f"""
            SELECT signal_type, occurred_at,
                   ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lon,
                   weight, raw_payload, source_id
            FROM signals WHERE {conditions}
            ORDER BY occurred_at DESC LIMIT :limit
        """),
        bind,
    )
    return [
        {
            "signal_type": r.signal_type,
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "lat": r.lat, "lon": r.lon,
            "details": _summarize_payload(r.raw_payload),
        }
        for r in result.fetchall()
    ]


async def _tool_news(session: AsyncSession, params: dict) -> list[dict]:
    """Get news articles within a bbox."""
    bbox = params["bbox"]
    limit = min(params.get("limit", 10), 30)

    result = await session.execute(
        text("""
            SELECT occurred_at, raw_payload, source_id
            FROM signals
            WHERE source = 'newsdata'
              AND ST_Intersects(location, ST_MakeEnvelope(:west, :south, :east, :north, 4326))
            ORDER BY occurred_at DESC LIMIT :limit
        """),
        {"west": bbox[0], "south": bbox[1], "east": bbox[2], "north": bbox[3], "limit": limit},
    )
    return [
        {
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "title": (r.raw_payload or {}).get("title", ""),
            "description": (r.raw_payload or {}).get("description", "")[:200],
            "url": (r.raw_payload or {}).get("url", ""),
            "source": (r.raw_payload or {}).get("source", ""),
        }
        for r in result.fetchall()
    ]


async def _tool_signal_summary(session: AsyncSession) -> list[dict]:
    """Get aggregate signal counts by source and type."""
    result = await session.execute(text("""
        SELECT source, signal_type, count(*) as cnt,
               min(occurred_at) as earliest, max(occurred_at) as latest
        FROM signals
        GROUP BY source, signal_type
        ORDER BY cnt DESC
    """))
    return [
        {
            "source": r.source, "signal_type": r.signal_type,
            "count": r.cnt,
            "earliest": r.earliest.isoformat() if r.earliest else None,
            "latest": r.latest.isoformat() if r.latest else None,
        }
        for r in result.fetchall()
    ]


def _summarize_payload(payload: dict | None) -> dict:
    """Extract key fields from raw_payload for the copilot context.

    Keeps payloads concise to avoid flooding the Claude context window.
    """
    if not payload:
        return {}

    summary = {}
    # GDELT fields
    for key in ("EventCode", "GoldsteinScale", "NumArticles", "SOURCEURL", "themes", "tone"):
        if key in payload:
            summary[key] = payload[key]
    # GFW fields
    for key in ("type", "vessel", "durationHours", "distanceKm"):
        if key in payload:
            val = payload[key]
            if key == "vessel" and isinstance(val, dict):
                summary["vessel"] = {k: val[k] for k in ("name", "flag", "id") if k in val}
            else:
                summary[key] = val
    # News fields
    for key in ("title", "url", "source"):
        if key in payload:
            summary[key] = payload[key]

    return summary


def _extract_map_action(text_content: str) -> dict | None:
    """Try to extract a map_action JSON block from the response text.

    The model may include map actions as a JSON code block.
    """
    import re
    match = re.search(r'```(?:json)?\s*(\{[^`]*"type"\s*:\s*"fly_to"[^`]*\})\s*```', text_content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None
