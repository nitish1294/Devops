"""Audit trail. Every mutation drops a document here so the timeline is queryable."""

from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_mongo


async def log(
    action: str,
    entity_type: str,
    entity_id: int | None,
    summary: str,
    actor_id: int | None = None,
    actor_name: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    await get_mongo().activity.insert_one(
        {
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "summary": summary,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "meta": meta or {},
            "created_at": datetime.now(timezone.utc),
        }
    )


async def feed(
    entity_type: str | None = None,
    entity_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    query: dict[str, Any] = {}
    if entity_type:
        query["entity_type"] = entity_type
    if entity_id is not None:
        query["entity_id"] = entity_id
    cursor = get_mongo().activity.find(query).sort("created_at", -1).limit(min(limit, 200))
    out = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        out.append(doc)
    return out
