from datetime import datetime, timezone

from bson import ObjectId

from app.db.mongo import get_mongo


async def add(entity_type: str, entity_id: int, body: str, author_id: int, author_name: str) -> dict:
    doc = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "body": body,
        "author_id": author_id,
        "author_name": author_name,
        "created_at": datetime.now(timezone.utc),
    }
    res = await get_mongo().notes.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    return doc


async def list_for(entity_type: str, entity_id: int) -> list[dict]:
    cursor = (
        get_mongo()
        .notes.find({"entity_type": entity_type, "entity_id": entity_id})
        .sort("created_at", -1)
    )
    out = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        out.append(doc)
    return out


async def delete(note_id: str) -> bool:
    if not ObjectId.is_valid(note_id):
        return False
    res = await get_mongo().notes.delete_one({"_id": ObjectId(note_id)})
    return res.deleted_count == 1
