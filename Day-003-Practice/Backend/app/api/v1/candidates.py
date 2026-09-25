from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, Db, ManageJobs
from app.core.enums import Stage
from app.models.application import Application
from app.models.candidate import Candidate
from app.schemas.candidate import CandidateCreate, CandidateOut, CandidateUpdate
from app.schemas.common import Message, Page
from app.schemas.docs import NoteOut, ResumeOut
from app.core.config import settings
from app.services import activity, export, notes, resume

router = APIRouter(prefix="/candidates", tags=["candidates"])

MAX_RESUME_BYTES = settings.MAX_RESUME_BYTES
ALLOWED_SUFFIXES = (".pdf", ".docx", ".txt", ".md")


async def _decorate(db, cand: Candidate) -> CandidateOut:
    open_apps = (
        await db.execute(
            select(func.count(Application.id)).where(
                Application.candidate_id == cand.id,
                Application.stage.notin_(list(Stage.terminal())),
            )
        )
    ).scalar_one()
    out = CandidateOut.model_validate(cand)
    out.open_applications = open_apps
    return out


@router.get("", response_model=Page[CandidateOut])
async def list_candidates(
    db: Db,
    _: CurrentUser,
    q: str | None = None,
    skill: str | None = None,
    source: str | None = None,
    min_experience: float | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stmt = select(Candidate)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(Candidate.full_name).like(like)
            | func.lower(Candidate.email).like(like)
            | func.lower(func.coalesce(Candidate.current_company, "")).like(like)
        )
    if skill:
        stmt = stmt.where(func.lower(func.coalesce(Candidate.skills, "")).like(f"%{skill.lower()}%"))
    if source:
        stmt = stmt.where(Candidate.source == source)
    if min_experience is not None:
        stmt = stmt.where(Candidate.total_experience >= min_experience)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                stmt.order_by(Candidate.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .unique()
        .scalars()
        .all()
    )
    return Page[CandidateOut](
        items=[await _decorate(db, r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.post("", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    payload: CandidateCreate, db: Db, actor: ManageJobs
):
    exists = (
        await db.execute(select(Candidate.id).where(Candidate.email == payload.email.lower()))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This candidate is already in the database. Open their profile to add an application.",
        )
    cand = Candidate(**payload.model_dump(exclude={"email"}), email=payload.email.lower())
    db.add(cand)
    await db.commit()
    await db.refresh(cand)
    await activity.log(
        "candidate.create", "candidate", cand.id, f"Added candidate {cand.full_name}", actor.id, actor.full_name
    )
    return await _decorate(db, cand)


@router.get("/{candidate_id}", response_model=CandidateOut)
async def get_candidate(candidate_id: int, db: Db, _: CurrentUser):
    cand = (
        (await db.execute(select(Candidate).where(Candidate.id == candidate_id)))
        .unique()
        .scalar_one_or_none()
    )
    if not cand:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    return await _decorate(db, cand)


@router.patch("/{candidate_id}", response_model=CandidateOut)
async def update_candidate(
    candidate_id: int, payload: CandidateUpdate, db: Db, actor: ManageJobs
):
    cand = (
        (await db.execute(select(Candidate).where(Candidate.id == candidate_id)))
        .unique()
        .scalar_one_or_none()
    )
    if not cand:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cand, field, value)
    db.add(cand)
    await db.commit()
    await db.refresh(cand)
    await activity.log(
        "candidate.update", "candidate", cand.id, f"Updated {cand.full_name}", actor.id, actor.full_name
    )
    return await _decorate(db, cand)


@router.post("/{candidate_id}/resume", response_model=ResumeOut)
async def upload_resume(
    candidate_id: int,
    db: Db,
    actor: ManageJobs,
    file: UploadFile = File(...),
):
    """Stores the resume document in MongoDB and pulls skills back into Postgres."""
    cand = (
        (await db.execute(select(Candidate).where(Candidate.id == candidate_id)))
        .unique()
        .scalar_one_or_none()
    )
    if not cand:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")

    filename = file.filename or "resume"
    if not filename.lower().endswith(ALLOWED_SUFFIXES):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload a PDF, DOCX, TXT or MD file"
        )
    content = await file.read()
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Resume must be under {MAX_RESUME_BYTES // (1024 * 1024)} MB",
        )
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That file is empty")

    doc = await resume.store_resume(candidate_id, filename, file.content_type or "", content)

    cand.resume_doc_id = doc["id"]
    parsed_skills = doc["parsed"].get("skills") or []
    if parsed_skills:
        merged = sorted({*cand.skill_list, *parsed_skills})
        cand.skills = ", ".join(merged)
    if not cand.total_experience and doc["parsed"].get("years_experience"):
        cand.total_experience = doc["parsed"]["years_experience"]
    db.add(cand)
    await db.commit()

    await activity.log(
        "candidate.resume",
        "candidate",
        cand.id,
        f"Parsed resume for {cand.full_name}",
        actor.id,
        actor.full_name,
        {"skills_found": len(parsed_skills)},
    )
    return ResumeOut(
        id=doc["id"],
        candidate_id=candidate_id,
        filename=doc["filename"],
        content_type=doc["content_type"],
        size_bytes=doc["size_bytes"],
        uploaded_at=doc["uploaded_at"],
        parsed=doc["parsed"],
        raw_text_preview=(doc.get("raw_text") or "")[:400],
    )


@router.get("/{candidate_id}/resume", response_model=ResumeOut)
async def get_resume(candidate_id: int, db: Db, _: CurrentUser):
    cand = (
        (await db.execute(select(Candidate).where(Candidate.id == candidate_id)))
        .unique()
        .scalar_one_or_none()
    )
    if not cand or not cand.resume_doc_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No resume on file for this candidate")
    doc = await resume.get_resume(cand.resume_doc_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume document is missing")
    return ResumeOut(
        id=doc["id"],
        candidate_id=candidate_id,
        filename=doc["filename"],
        content_type=doc["content_type"],
        size_bytes=doc["size_bytes"],
        uploaded_at=doc["uploaded_at"],
        parsed=doc["parsed"],
        raw_text_preview=(doc.get("raw_text") or "")[:400],
    )


@router.get("/{candidate_id}/notes", response_model=list[NoteOut])
async def candidate_notes(candidate_id: int, _: CurrentUser):
    return [NoteOut(**n) for n in await notes.list_for("candidate", candidate_id)]


@router.post("/{candidate_id}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
async def add_candidate_note(candidate_id: int, body: dict, actor: CurrentUser):
    text = (body.get("body") or "").strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Write something before saving the note")
    doc = await notes.add("candidate", candidate_id, text, actor.id, actor.full_name)
    return NoteOut(**doc)


@router.delete("/notes/{note_id}", response_model=Message)
async def delete_note(note_id: str, _: CurrentUser):
    if not await notes.delete(note_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return Message(detail="Note deleted")


@router.get("/search/resumes", response_model=list[dict])
async def full_text_resume_search(_: CurrentUser, term: str = Query(min_length=2)):
    """Full-text search across stored resume text - this is the MongoDB text index at work."""
    results = await resume.search_resumes(term)
    for r in results:
        r.pop("raw_text", None)
    return results


@router.get("/{candidate_id}/resume/download", response_class=Response)
async def download_resume(candidate_id: int, db: Db, _: CurrentUser):
    """Hand back the original file exactly as it was uploaded.

    Recruiters forward the real CV to hiring managers; a parsed text dump is no
    substitute, so the bytes are kept alongside the extracted text.
    """
    cand = (
        (await db.execute(select(Candidate).where(Candidate.id == candidate_id)))
        .unique()
        .scalar_one_or_none()
    )
    if not cand:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")

    doc = await resume.latest_resume_for(candidate_id, with_content=True)
    if not doc or not doc.get("content"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No resume file stored for this candidate")

    stored = doc.get("filename") or "resume"
    suffix = stored.rsplit(".", 1)[-1] if "." in stored else "pdf"
    safe_name = "".join(
        ch if ch.isalnum() or ch in " -_" else "-" for ch in cand.full_name
    ).strip() or f"candidate-{candidate_id}"

    return Response(
        content=bytes(doc["content"]),
        media_type=doc.get("content_type") or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name} resume.{suffix}"'
        },
    )


@router.get("/export/csv", response_class=Response)
async def export_candidates(
    db: Db,
    _: CurrentUser,
    q: str | None = None,
    source: str | None = None,
    min_experience: float | None = None,
):
    """The current candidate list as a spreadsheet, honouring the same filters."""
    stmt = select(Candidate).order_by(Candidate.created_at.desc())
    if q:
        term = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(Candidate.full_name).like(term)
            | func.lower(Candidate.email).like(term)
            | func.lower(func.coalesce(Candidate.current_company, "")).like(term)
        )
    if source:
        stmt = stmt.where(Candidate.source == source)
    if min_experience is not None:
        stmt = stmt.where(Candidate.total_experience >= min_experience)

    rows = (await db.execute(stmt)).unique().scalars().all()
    headers = [
        "Name", "Email", "Phone", "Current title", "Current company", "Location",
        "Experience (yrs)", "Current CTC", "Expected CTC", "Notice (days)",
        "Skills", "Source", "Referred by", "Added on",
    ]
    data = [
        [
            c.full_name, c.email, c.phone, c.current_title, c.current_company,
            c.location, c.total_experience, c.current_ctc, c.expected_ctc,
            c.notice_period_days, c.skills, c.source, c.referred_by, c.created_at,
        ]
        for c in rows
    ]
    return Response(
        content=export.to_csv(headers, data),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{export.filename("candidates")}"'
        },
    )
