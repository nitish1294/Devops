"""Resume ingestion: extract text, pull structured fields, store the document in MongoDB.

Deliberately dependency-light. Swap `parse_text` for an NLP/LLM parser later without
touching the storage contract.
"""

import io
import re
from datetime import datetime, timezone

from bson import Binary, ObjectId

from app.db.mongo import get_mongo

SKILL_VOCAB = [
    "python", "java", "javascript", "typescript", "angular", "react", "vue", "node.js",
    "fastapi", "django", "flask", "spring boot", "hibernate", "sql", "postgresql",
    "mysql", "mongodb", "redis", "docker", "kubernetes", "jenkins", "git", "linux",
    "aws", "azure", "gcp", "terraform", "ansible", "nginx", "kafka", "rabbitmq",
    "graphql", "rest api", "microservices", "ci/cd", "prometheus", "grafana",
    "html", "css", "sass", "tailwind", "power bi", "excel", "tableau", "sap",
    "recruitment", "payroll", "onboarding", "hrms", "talent acquisition",
    "machine learning", "pandas", "numpy", "pytest", "selenium", "jira",
]

DEGREE_VOCAB = [
    "b.tech", "btech", "b.e.", "be", "bca", "bsc", "b.sc", "bcom", "b.com", "bba",
    "m.tech", "mtech", "mca", "msc", "m.sc", "mba", "mcom", "phd", "diploma",
]

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+91[-\s]?)?\b[6-9]\d{9}\b")
EXP_RE = re.compile(r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)", re.I)


def extract_text(filename: str, content: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            return ""
    if lower.endswith(".docx"):
        try:
            import docx

            document = docx.Document(io.BytesIO(content))
            return "\n".join(p.text for p in document.paragraphs)
        except Exception:
            return ""
    try:
        return content.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def parse_text(text: str) -> dict:
    low = text.lower()
    skills = sorted({s for s in SKILL_VOCAB if s in low})
    degrees = sorted({d for d in DEGREE_VOCAB if d in low})
    years = [float(m) for m in EXP_RE.findall(text)]
    return {
        "emails": sorted(set(EMAIL_RE.findall(text)))[:5],
        "phones": sorted(set(PHONE_RE.findall(text)))[:5],
        "skills": skills,
        "education": degrees,
        "years_experience": max(years) if years else None,
        "word_count": len(text.split()),
    }


async def store_resume(
    candidate_id: int, filename: str, content_type: str, content: bytes
) -> dict:
    text = extract_text(filename, content)
    parsed = parse_text(text)
    doc = {
        "candidate_id": candidate_id,
        "filename": filename,
        "content_type": content_type or "application/octet-stream",
        "size_bytes": len(content),
        "raw_text": text,
        # Lowercased copy so search does not depend on a case-insensitive regex,
        # which cannot use an index.
        "search_text": text.lower(),
        "parsed": parsed,
        # The original file, so a recruiter can download exactly what was sent.
        "content": Binary(content),
        "uploaded_at": datetime.now(timezone.utc),
    }
    result = await get_mongo().resumes.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


async def get_resume(doc_id: str, with_content: bool = False) -> dict | None:
    """Fetch a resume. The file bytes are excluded unless asked for."""
    if not ObjectId.is_valid(doc_id):
        return None
    projection = None if with_content else {"content": 0, "search_text": 0}
    doc = await get_mongo().resumes.find_one({"_id": ObjectId(doc_id)}, projection)
    if doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


async def latest_resume_for(candidate_id: int, with_content: bool = False) -> dict | None:
    projection = None if with_content else {"content": 0, "search_text": 0}
    doc = await get_mongo().resumes.find_one(
        {"candidate_id": candidate_id}, projection, sort=[("uploaded_at", -1)]
    )
    if doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


def _snippet(text: str, terms: list[str], width: int = 260) -> str:
    """A window of the resume around the first match, so results explain themselves."""
    if not text:
        return ""
    low = text.lower()
    hit = min((low.find(t) for t in terms if low.find(t) >= 0), default=-1)
    if hit < 0:
        return text[:width].strip()
    start = max(0, hit - width // 3)
    end = min(len(text), start + width)
    return ("…" if start else "") + text[start:end].strip() + ("…" if end < len(text) else "")


async def search_resumes(term: str, limit: int = 25) -> list[dict]:
    """Find resumes containing every word in `term`.

    Substring matching on a pre-lowercased field rather than a `$text` index:
    `$text` only matches whole stemmed words, so a search for "kuber" would miss
    "kubernetes", and a recruiter typing half a technology name expects a hit.
    The trade is that this scans rather than seeks; at resume-database scale that
    is fine, and the compound index on candidate_id keeps the common lookups fast.
    """
    terms = [t.strip().lower() for t in re.split(r"[\s,]+", term) if t.strip()]
    if not terms:
        return []

    query = {"$and": [{"search_text": {"$regex": re.escape(t)}} for t in terms]}
    cursor = (
        get_mongo()
        .resumes.find(query, {"content": 0})
        .sort("uploaded_at", -1)
        .limit(limit * 3)
    )

    out = []
    async for doc in cursor:
        raw = doc.pop("raw_text", "") or ""
        low = doc.pop("search_text", "") or raw.lower()
        doc["id"] = str(doc.pop("_id"))
        # Rank by how often the terms appear, so the strongest match leads.
        doc["score"] = sum(low.count(t) for t in terms)
        doc["raw_text_preview"] = _snippet(raw, terms)
        doc["matched_terms"] = [t for t in terms if t in low]
        out.append(doc)

    out.sort(key=lambda d: d["score"], reverse=True)
    return out[:limit]


def score_match(job_skills: list[str], candidate_skills: list[str]) -> int:
    """Naive overlap score, 0-100. Good enough to sort a pipeline by."""
    if not job_skills:
        return 0
    wanted = {s.lower().strip() for s in job_skills if s.strip()}
    have = {s.lower().strip() for s in candidate_skills if s.strip()}
    if not wanted:
        return 0
    return round(len(wanted & have) / len(wanted) * 100)
