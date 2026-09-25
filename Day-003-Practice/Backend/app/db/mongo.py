import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

log = logging.getLogger("hrms.mongo")

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.MONGO_URI,
            uuidRepresentation="standard",
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
    return _client


def get_mongo() -> AsyncIOMotorDatabase:
    return get_client()[settings.MONGO_DB]


async def init_mongo() -> None:
    """Indexes for the document-side collections.

    Index creation is idempotent, but a mismatched existing index raises. Each
    one is attempted independently so a single conflict from an older deployment
    cannot stop the app from starting.
    """
    db = get_mongo()
    wanted = [
        (db.resumes, dict(keys="candidate_id")),
        (db.resumes, dict(keys=[("candidate_id", 1), ("uploaded_at", -1)])),
        (db.resumes, dict(keys=[("parsed.skills", 1)])),
        (db.activity, dict(keys=[("created_at", -1)])),
        (db.activity, dict(keys=[("entity_type", 1), ("entity_id", 1), ("created_at", -1)])),
        (db.activity, dict(keys=[("actor_id", 1), ("created_at", -1)])),
        (db.scorecards, dict(keys=[("application_id", 1)])),
        (db.scorecards, dict(keys=[("interview_id", 1)], unique=True, sparse=True)),
        (db.notes, dict(keys=[("entity_type", 1), ("entity_id", 1), ("created_at", -1)])),
        (db.email_templates, dict(keys="code", unique=True)),
        (db.outbox, dict(keys=[("created_at", -1)])),
        (db.outbox, dict(keys=[("status", 1), ("created_at", 1)])),
        (db.form_schemas, dict(keys="job_id")),
    ]
    for collection, spec in wanted:
        keys = spec.pop("keys")
        try:
            await collection.create_index(keys, **spec)
        except Exception as exc:
            log.warning(
                "index not created",
                extra={"collection": collection.name, "error": str(exc)[:200]},
            )


async def ping() -> bool:
    try:
        await get_client().admin.command("ping")
        return True
    except Exception:
        return False


async def close_mongo() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
