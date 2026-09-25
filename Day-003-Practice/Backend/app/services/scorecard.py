"""Interview scorecards live in MongoDB: criteria differ per role, so no fixed columns."""

from datetime import datetime, timezone

from app.db.mongo import get_mongo


async def upsert(
    application_id: int,
    interview_id: int,
    criteria: dict[str, int],
    strengths: list[str],
    concerns: list[str],
    overall_rating: int | None,
    recommendation: str | None,
    submitted_by: int | None,
) -> dict:
    doc = {
        "application_id": application_id,
        "interview_id": interview_id,
        "criteria": criteria,
        "strengths": strengths,
        "concerns": concerns,
        "overall_rating": overall_rating,
        "recommendation": recommendation,
        "submitted_by": submitted_by,
        "submitted_at": datetime.now(timezone.utc),
    }
    await get_mongo().scorecards.update_one(
        {"interview_id": interview_id}, {"$set": doc}, upsert=True
    )
    saved = await get_mongo().scorecards.find_one({"interview_id": interview_id})
    saved["id"] = str(saved.pop("_id"))
    return saved


async def for_application(application_id: int) -> list[dict]:
    cursor = get_mongo().scorecards.find({"application_id": application_id}).sort("submitted_at", 1)
    out = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        out.append(doc)
    return out
