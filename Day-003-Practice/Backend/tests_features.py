"""Exercises everything added in the hardening pass."""
import asyncio, io, os, pathlib, sys
os.environ.update({
    "POSTGRES_HOST": "127.0.0.1", "POSTGRES_USER": "hrms",
    "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
    "POSTGRES_DB": "hrms", "JWT_SECRET": "test-secret",
    "AUTO_CREATE_SCHEMA": "true",
    "LOG_LEVEL": "ERROR", "MAIL_WORKER_ENABLED": "false",
    "LOGIN_MAX_ATTEMPTS": "4", "LOGIN_LOCKOUT_SECONDS": "60",
})
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from mongomock_motor import AsyncMongoMockClient
import app.db.mongo as mongomod
_mock = AsyncMongoMockClient()
mongomod.get_client = lambda: _mock
mongomod.get_mongo = lambda: _mock["hrms_docs"]

import httpx
from app.main import app as fastapi_app

PASS, FAIL = [], []
def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   -> {extra}" if extra and not cond else ""))

AUTH = lambda t: {"Authorization": f"Bearer {t}"}

async def main():
    # The ASGI transport does not run the lifespan, so do the startup work here.
    from app.services import notifications as notif
    await notif.seed_templates()

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60) as c:

        print("\n== HEALTH PROBES ==")
        r = await c.get("/health/live")
        check("liveness is cheap and always 200", r.status_code == 200 and r.json()["status"] == "alive")
        r = await c.get("/health/ready")
        check("readiness reports both databases", r.status_code == 200 and r.json()["postgres"] is True)
        r = await c.get("/health")
        body = r.json()
        check("health reports version and uptime", "version" in body and "uptime_seconds" in body)
        check("health names mail delivery mode", body["checks"]["mail"] == "queue only")

        print("\n== REQUEST TRACING ==")
        r = await c.get("/health/ready")
        check("every response carries X-Request-ID", bool(r.headers.get("X-Request-ID")))
        r = await c.get("/health/ready", headers={"X-Request-ID": "trace-me-123"})
        check("caller-supplied request id is honoured", r.headers.get("X-Request-ID") == "trace-me-123")

        print("\n== TOKENS ==")
        r = await c.post("/api/v1/auth/login", json={"email":"admin@hrms.co","password":"Password@123"})
        check("login returns an access token", r.status_code == 200 and "access_token" in r.json())
        check("login returns a refresh token", "refresh_token" in r.json())
        tokens = r.json()
        admin = AUTH(tokens["access_token"])
        check("access token expires in an hour", tokens["expires_in"] == 3600)

        r = await c.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        check("refresh returns a new pair", r.status_code == 200 and "access_token" in r.json())
        new_access = r.json()["access_token"]
        r = await c.get("/api/v1/auth/me", headers=AUTH(new_access))
        check("refreshed access token works", r.status_code == 200)

        r = await c.get("/api/v1/auth/me", headers=AUTH(tokens["refresh_token"]))
        check("refresh token rejected as a bearer credential", r.status_code == 401, r.text[:120])
        r = await c.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
        check("access token rejected at the refresh endpoint", r.status_code == 401)
        r = await c.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt"})
        check("garbage refresh token rejected", r.status_code == 401)

        print("\n== LOGIN THROTTLING ==")
        from app.core.ratelimit import login_limiter
        login_limiter.clear()
        codes = []
        for _ in range(6):
            rr = await c.post("/api/v1/auth/login", json={"email":"hr@hrms.co","password":"nope"})
            codes.append(rr.status_code)
        check("repeated failures eventually return 429", 429 in codes, str(codes))
        check("throttle kicks in after the configured attempts", codes[:3] == [401,401,401], str(codes))
        r = await c.post("/api/v1/auth/login", json={"email":"hr@hrms.co","password":"Password@123"})
        check("correct password still blocked while locked", r.status_code == 429)
        check("lockout sends Retry-After", bool(r.headers.get("Retry-After")))
        login_limiter.clear()
        r = await c.post("/api/v1/auth/login", json={"email":"hr@hrms.co","password":"Password@123"})
        check("login works again once the window clears", r.status_code == 200)
        hr = AUTH(r.json()["access_token"])

        print("\n== PASSWORD RULES ==")
        r = await c.post("/api/v1/auth/change-password", headers=hr,
                         json={"current_password":"Password@123","new_password":"Password@123"})
        check("new password must differ from the old", r.status_code == 400)
        r = await c.post("/api/v1/auth/change-password", headers=hr,
                         json={"current_password":"Password@123","new_password":"12345678"})
        check("all-digit password rejected", r.status_code == 400)
        r = await c.post("/api/v1/auth/change-password", headers=hr,
                         json={"current_password":"Password@123","new_password":"password"})
        check("common password rejected", r.status_code == 400)
        r = await c.post("/api/v1/auth/change-password", headers=hr,
                         json={"current_password":"wrong-one","new_password":"Str0ng!Pass9"})
        check("wrong current password rejected", r.status_code == 400)
        r = await c.post("/api/v1/auth/change-password", headers=hr,
                         json={"current_password":"Password@123","new_password":"Str0ng!Pass9"})
        check("a strong password is accepted", r.status_code == 200, r.text[:150])
        r = await c.post("/api/v1/auth/login", json={"email":"hr@hrms.co","password":"Str0ng!Pass9"})
        check("the new password actually works", r.status_code == 200)
        await c.post("/api/v1/auth/change-password", headers=AUTH(r.json()["access_token"]),
                     json={"current_password":"Str0ng!Pass9","new_password":"Password@123"})

        print("\n== ERROR CONTRACT ==")
        r = await c.get("/api/v1/jobs/99999", headers=admin)
        check("404 body carries a request id", r.status_code == 404 and "request_id" in r.json())
        r = await c.post("/api/v1/jobs", headers=admin, json={"title":"x"})
        check("422 lists per-field problems", r.status_code == 422 and isinstance(r.json().get("problems"), list))

        print("\n== RESUME: STORAGE, DOWNLOAD, SEARCH ==")
        r = await c.post("/api/v1/candidates", headers=admin, json={
            "full_name":"Rhea Kulkarni","email":"rhea.k@example.com","phone":"9876500011",
            "total_experience":6,"source":"referral"})
        cid = r.json()["id"]
        cv = (b"Rhea Kulkarni\nSenior Platform Engineer\n9876500011\n"
              b"B.Tech Computer Science, 2017\n"
              b"Skills: Python, Kubernetes, Terraform, PostgreSQL, Prometheus, Grafana\n"
              b"7 years building deployment pipelines. Ran Kubernetes in production at scale.\n")
        r = await c.post(f"/api/v1/candidates/{cid}/resume", headers=admin,
                         files={"file": ("rhea_cv.txt", io.BytesIO(cv), "text/plain")})
        check("resume uploads and parses", r.status_code == 200, r.text[:200])
        parsed = r.json()["parsed"]
        check("skills extracted from the CV", "kubernetes" in parsed["skills"])

        r = await c.get(f"/api/v1/candidates/{cid}/resume/download", headers=admin)
        check("original file downloads", r.status_code == 200, r.text[:150])
        check("downloaded bytes are byte-identical to the upload", r.content == cv)
        check("download sets an attachment filename",
              "attachment" in r.headers.get("content-disposition","").lower())
        r = await c.get("/api/v1/candidates/1/resume/download", headers=admin)
        check("candidate with no resume gets 404", r.status_code == 404)

        r = await c.get("/api/v1/candidates/search/resumes", headers=admin, params={"term":"kubernetes"})
        check("resume search finds a whole word", r.status_code == 200 and len(r.json()) >= 1, r.text[:150])
        r = await c.get("/api/v1/candidates/search/resumes", headers=admin, params={"term":"kuber"})
        check("resume search matches a partial word (what $text could not do)", len(r.json()) >= 1)
        r = await c.get("/api/v1/candidates/search/resumes", headers=admin, params={"term":"KUBERNETES"})
        check("resume search is case-insensitive", len(r.json()) >= 1)
        r = await c.get("/api/v1/candidates/search/resumes", headers=admin, params={"term":"terraform prometheus"})
        check("multiple terms are ANDed", len(r.json()) >= 1)
        r = await c.get("/api/v1/candidates/search/resumes", headers=admin, params={"term":"terraform cobol"})
        check("a term that matches nothing excludes the row", len(r.json()) == 0)
        r = await c.get("/api/v1/candidates/search/resumes", headers=admin, params={"term":"kubernetes"})
        hit = r.json()[0]
        check("results carry a relevance score", hit.get("score", 0) > 0)
        check("results carry a context snippet", "kubernetes" in hit["raw_text_preview"].lower())
        check("results say which terms matched", hit.get("matched_terms") == ["kubernetes"])
        check("search never leaks the raw file bytes", "content" not in hit)

        print("\n== CSV EXPORTS ==")
        r = await c.get("/api/v1/candidates/export/csv", headers=admin)
        check("candidate export returns CSV", r.status_code == 200 and "text/csv" in r.headers["content-type"])
        check("export starts with a UTF-8 BOM for Excel", r.content.startswith(b"\xef\xbb\xbf"))
        text = r.content.decode("utf-8-sig")
        check("export has a header row", text.splitlines()[0].startswith("Name,Email"))
        check("exported rows include the new candidate", "Rhea Kulkarni" in text)
        r2 = await c.get("/api/v1/candidates/export/csv", headers=admin, params={"q":"Rhea"})
        check("export honours the same filters as the list",
              len(r2.content.decode("utf-8-sig").strip().splitlines()) == 2)
        r = await c.get("/api/v1/applications/export/csv", headers=admin)
        check("pipeline export returns CSV", r.status_code == 200)
        check("pipeline export names the stage in words", "Screening" in r.content.decode("utf-8-sig"))

        # A candidate whose name looks like a spreadsheet formula must not become one.
        await c.post("/api/v1/candidates", headers=admin, json={
            "full_name":"=SUM(A1:A9)","email":"formula@example.com"})
        r = await c.get("/api/v1/candidates/export/csv", headers=admin, params={"q":"SUM"})
        check("formula-looking cells are neutralised", "'=SUM" in r.content.decode("utf-8-sig"))

        print("\n== BULK PIPELINE MOVES ==")
        r = await c.get("/api/v1/applications", headers=admin, params={"stage":"sourced","page_size":5})
        ids = [a["id"] for a in r.json()["items"]][:3]
        check("found sourced applications to move", len(ids) == 3)
        r = await c.post("/api/v1/applications/bulk/stage", headers=admin,
                         json={"application_ids": ids, "to_stage":"screening","note":"Batch screen"})
        check("bulk move succeeds", r.status_code == 200 and r.json()["moved"] == 3, r.text[:200])
        r = await c.post("/api/v1/applications/bulk/stage", headers=admin,
                         json={"application_ids": ids, "to_stage":"screening"})
        check("re-moving to the same stage is skipped, not an error",
              r.status_code == 200 and r.json()["moved"] == 0 and len(r.json()["skipped"]) == 3)
        check("skip entries explain themselves", "Already in" in r.json()["skipped"][0]["reason"])
        r = await c.post("/api/v1/applications/bulk/stage", headers=admin,
                         json={"application_ids": ids + [999999], "to_stage":"interview"})
        check("a missing id is reported but the rest still move",
              r.json()["moved"] == 3 and any(s.get("reason")=="Not found" for s in r.json()["skipped"]))
        r = await c.post("/api/v1/applications/bulk/stage", headers=admin,
                         json={"application_ids": ids, "to_stage":"rejected"})
        check("bulk rejection without a reason is refused", r.status_code == 400)
        r = await c.post("/api/v1/applications/bulk/stage", headers=admin,
                         json={"application_ids": ids, "to_stage":"rejected","rejection_reason":"Batch closed"})
        check("bulk rejection with a reason works", r.json()["moved"] == 3)
        r = await c.get(f"/api/v1/applications/{ids[0]}", headers=admin)
        check("bulk moves write real stage history", len(r.json()["stage_events"]) >= 3)

        print("\n== OFFER LETTER PDF ==")
        r = await c.get("/api/v1/offers", headers=admin, params={"page_size":5})
        offers = r.json()["items"]
        check("offers exist to render", len(offers) > 0)
        oid = offers[0]["id"]
        r = await c.get(f"/api/v1/offers/{oid}/letter.pdf", headers=admin)
        check("offer letter renders", r.status_code == 200, r.text[:200])
        check("it is a real PDF", r.content.startswith(b"%PDF"))
        check("PDF is substantial, not an empty page", len(r.content) > 2000)
        check("PDF served with the right content type", r.headers["content-type"] == "application/pdf")
        import pypdf
        page = pypdf.PdfReader(io.BytesIO(r.content)).pages[0].extract_text()
        check("letter names the candidate", offers[0]["candidate"]["full_name"] in page)
        check("letter states the designation", offers[0]["designation"][:20] in page)
        check("letter shows Indian digit grouping", "Rs." in page)
        r = await c.get(f"/api/v1/offers/{oid}/letter.pdf", headers=AUTH(""))
        check("offer letter requires authentication", r.status_code == 401)

        print("\n== CALENDAR INVITES ==")
        r = await c.get("/api/v1/interviews", headers=admin, params={"page_size":5})
        ivs = r.json()["items"]
        check("interviews exist", len(ivs) > 0)
        iid = ivs[0]["id"]
        r = await c.get(f"/api/v1/interviews/{iid}/invite.ics", headers=admin)
        check("ics invite generates", r.status_code == 200, r.text[:200])
        ics = r.content.decode()
        check("ics is well formed", ics.startswith("BEGIN:VCALENDAR") and ics.rstrip().endswith("END:VCALENDAR"))
        check("ics uses CRLF line endings as the RFC requires", "\r\n" in ics)
        check("ics carries METHOD:REQUEST so clients show Accept/Decline", "METHOD:REQUEST" in ics)
        check("ics has a stable UID", f"UID:interview-{iid}@hrms" in ics)
        check("ics lists attendees", ics.count("ATTENDEE") >= 1)
        check("ics includes a reminder alarm", "BEGIN:VALARM" in ics)
        check("no unfolded line exceeds 75 octets",
              all(len(l.encode()) <= 75 for l in ics.split("\r\n")))
        r = await c.post(f"/api/v1/interviews/{iid}/cancel", headers=admin)
        r = await c.get(f"/api/v1/interviews/{iid}/invite.ics", headers=admin)
        check("cancelled interview yields a CANCEL invite", "METHOD:CANCEL" in r.text and "STATUS:CANCELLED" in r.text)

        print("\n== MAIL PIPELINE ==")
        r = await c.get("/api/v1/comms/mail-status", headers=admin)
        st = r.json()
        check("mail status reports configuration", r.status_code == 200 and st["smtp_configured"] is False)
        check("mail status says delivery is queue-only", st["delivery"] == "queue only")
        check("mail status counts queued messages", st["counts"]["queued"] > 0)
        r = await c.post("/api/v1/comms/outbox/flush", headers=admin)
        check("flush is a no-op without SMTP and says so", "skipped" in r.json())
        r = await c.get("/api/v1/comms/templates", headers=admin)
        tpls = r.json()
        check("templates expose their placeholders", any(t["placeholders"] for t in tpls))
        invite_tpl = next(t for t in tpls if t["code"]=="interview_invite")
        check("placeholder list is accurate", "round_name" in invite_tpl["placeholders"])
        r = await c.post("/api/v1/comms/preview", headers=admin,
                         json={"template_code":"regret","candidate_id":cid,"context":{"job_title":"Platform Engineer"}})
        check("preview renders without queueing", r.status_code == 200 and "Rhea" in r.json()["body"])
        check("preview reports nothing unresolved when context is complete", r.json()["unresolved"] == [])
        r = await c.post("/api/v1/comms/preview", headers=admin,
                         json={"template_code":"interview_invite","candidate_id":cid,"context":{}})
        check("preview flags placeholders that would render blank",
              "round_name" in r.json()["unresolved"])
        before = (await c.get("/api/v1/comms/mail-status", headers=admin)).json()["counts"]["queued"]
        await c.post("/api/v1/comms/preview", headers=admin,
                     json={"template_code":"regret","candidate_id":cid,"context":{}})
        after = (await c.get("/api/v1/comms/mail-status", headers=admin)).json()["counts"]["queued"]
        check("preview really does not queue anything", before == after)
        r = await c.get("/api/v1/comms/outbox", headers=admin, params={"status":"queued","limit":5})
        check("outbox filters by status", r.status_code == 200 and all(m["status"]=="queued" for m in r.json()))
        check("outbox never returns attachment bytes",
              all(all("content" not in a for a in m.get("attachments",[])) for m in r.json()))
        r = await c.post("/api/v1/comms/outbox/000000000000000000000000/retry", headers=admin)
        check("retrying an unknown message 404s", r.status_code == 404)

        print("\n== ATTACHMENTS ON REAL EVENTS ==")
        # Drive the real flows rather than inspecting rows another run left behind.
        from datetime import datetime, timedelta, timezone
        job_id = (await c.get("/api/v1/jobs", headers=admin, params={"page_size":1})).json()["items"][0]["id"]
        r = await c.post("/api/v1/applications", headers=admin,
                         json={"candidate_id": cid, "job_id": job_id})
        check("application created for the attachment flow", r.status_code == 201, r.text[:200])
        app_id = r.json()["id"]

        when = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0)
        panel_id = (await c.get("/api/v1/users", headers=admin,
                                params={"role":"interviewer","page_size":1})).json()["items"][0]["id"]
        r = await c.post("/api/v1/interviews", headers=admin, json={
            "application_id": app_id, "round_name": "Technical round 1",
            "scheduled_at": when.isoformat(), "duration_minutes": 45,
            "mode": "video", "location_or_link": "https://meet.example.com/abc",
            "panelist_ids": [panel_id]})
        check("interview scheduled", r.status_code == 201, r.text[:250])

        rows = [m async for m in _mock["hrms_docs"].outbox.find({"template_code":"interview_invite"})]
        atts = [a for m in rows for a in m.get("attachments", [])]
        check("scheduling attaches a calendar invite to the candidate email",
              any(a.get("filename","").endswith(".ics") for a in atts))
        ics_att = next(a for a in atts if a.get("filename","").endswith(".ics"))
        check("attached invite has the calendar mime type", ics_att["mime"] == "text/calendar")
        body = bytes(ics_att["content"])
        check("attached invite is a real VCALENDAR", body.startswith(b"BEGIN:VCALENDAR"))
        check("attached invite names the panelist as an attendee", body.count(b"ATTENDEE") >= 2)

        await c.post(f"/api/v1/applications/{app_id}/stage", headers=admin,
                     json={"to_stage":"interview"})
        r = await c.post("/api/v1/offers", headers=admin, json={
            "application_id": app_id, "designation": "Senior Platform Engineer",
            "annual_ctc": 2400000, "fixed_component": 2000000,
            "variable_component": 400000, "joining_bonus": 100000})
        check("offer created", r.status_code == 201, r.text[:250])
        offer_id = r.json()["id"]

        r = await c.post(f"/api/v1/offers/{offer_id}/status", headers=admin, json={"status":"sent"})
        check("offer released", r.status_code == 200, r.text[:200])

        rows = [m async for m in _mock["hrms_docs"].outbox.find({"template_code":"offer_released"})]
        atts = [a for m in rows for a in m.get("attachments", [])]
        check("releasing an offer attaches the letter", any(a.get("mime")=="application/pdf" for a in atts))
        pdf_att = next(a for a in atts if a.get("mime")=="application/pdf")
        check("attached letter is a real PDF", bytes(pdf_att["content"]).startswith(b"%PDF"))
        check("attached letter is named for the candidate", "Rhea" in pdf_att["filename"])

        print("\n== MAIL FAILURES DO NOT BREAK OPERATIONS ==")
        # A missing template used to 500 a request whose database work had committed.
        await _mock["hrms_docs"].email_templates.delete_one({"code": "regret"})
        r = await c.post(f"/api/v1/applications/{app_id}/stage", headers=admin,
                         json={"to_stage":"rejected","rejection_reason":"Went with another candidate"})
        check("rejection still succeeds when its email template is missing",
              r.status_code == 200, r.text[:200])
        check("and the stage change really was persisted",
              (await c.get(f"/api/v1/applications/{app_id}", headers=admin)).json()["stage"] == "rejected")
        await notif.seed_templates()

    print("\n" + "="*62)
    print(f"PASSED {len(PASS)}   FAILED {len(FAIL)}")
    if FAIL:
        print("\nFailures:")
        for f in FAIL: print("  -", f)
    return 1 if FAIL else 0

sys.exit(asyncio.run(main()))
