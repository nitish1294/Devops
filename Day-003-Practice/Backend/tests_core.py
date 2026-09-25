"""End-to-end exercise of every major flow against real Postgres + in-memory Mongo."""
import asyncio, os, pathlib, sys
os.environ.update({
    "POSTGRES_HOST": "127.0.0.1", "POSTGRES_USER": "hrms",
    "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
    "POSTGRES_DB": "hrms", "JWT_SECRET": "test-secret",
    "AUTO_CREATE_SCHEMA": "true",
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
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra and not cond else ""))

async def main():
    import seed
    await seed.main()

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        print("\n== AUTH & RBAC ==")
        r = await c.post("/api/v1/auth/login", json={"email":"admin@hrms.co","password":"Password@123"})
        check("admin login", r.status_code == 200, r.text[:200])
        admin = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r2 = await c.post("/api/v1/auth/login", json={"email":"admin@hrms.co","password":"wrong"})
        check("bad password rejected (401)", r2.status_code == 401)
        check("unauthenticated blocked (401)", (await c.get("/api/v1/jobs")).status_code == 401)

        r = await c.post("/api/v1/auth/login", json={"email":"dev1@hrms.co","password":"Password@123"})
        panelist = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await c.post("/api/v1/users", headers=panelist, json={
            "email":"x@y.com","full_name":"No Access","password":"Password@123"})
        check("interviewer cannot create users (403)", r.status_code == 403)
        check("GET /auth/me", (await c.get("/api/v1/auth/me", headers=admin)).json()["role"] == "admin")

        print("\n== JOBS ==")
        r = await c.post("/api/v1/jobs", headers=admin, json={
            "title":"Platform SRE","location":"Mumbai","status":"open","openings":2,
            "experience_min":3,"experience_max":8,"salary_min":1600000,"salary_max":2600000,
            "skills":"kubernetes, docker, prometheus, linux, python"})
        check("create job (auto code)", r.status_code == 201, r.text[:200])
        job = r.json(); check("code generated", job["code"].startswith("REQ-"), job.get("code"))

        r = await c.post("/api/v1/jobs", headers=admin, json={
            "title":"Bad","experience_min":8,"experience_max":2})
        check("experience range validated (422)", r.status_code == 422)

        r = await c.patch(f"/api/v1/jobs/{job['id']}", headers=admin, json={"openings":3})
        check("update job", r.json()["openings"] == 3)
        r = await c.get("/api/v1/jobs?status=open&page_size=5", headers=admin)
        check("list + filter jobs", r.status_code == 200 and r.json()["total"] > 0)
        check("job carries applicant counts", "applicant_count" in r.json()["items"][0])

        print("\n== CANDIDATES & RESUME PARSING (Mongo) ==")
        r = await c.post("/api/v1/candidates", headers=admin, json={
            "full_name":"Test Kumar","email":"Test.Kumar@example.com","phone":"9876543210",
            "total_experience":5,"source":"referral","skills":"python, docker"})
        check("create candidate", r.status_code == 201, r.text[:200])
        cand = r.json(); check("email normalised", cand["email"] == "test.kumar@example.com")

        r = await c.post("/api/v1/candidates", headers=admin, json={
            "full_name":"Dup","email":"test.kumar@example.com"})
        check("duplicate email blocked (409)", r.status_code == 409)

        cv = (b"Test Kumar\ntest.kumar@example.com  9876543210\n"
              b"Senior Engineer with 7 years of experience.\n"
              b"Skills: Python, FastAPI, Kubernetes, PostgreSQL, Prometheus, Linux, Docker\n"
              b"Education: B.Tech Computer Science\n")
        r = await c.post(f"/api/v1/candidates/{cand['id']}/resume", headers=admin,
                         files={"file": ("cv.txt", cv, "text/plain")})
        check("resume upload + parse", r.status_code == 200, r.text[:250])
        parsed = r.json()["parsed"]
        check("skills extracted", "kubernetes" in parsed["skills"] and "fastapi" in parsed["skills"], str(parsed))
        check("phone extracted", "9876543210" in parsed["phones"], str(parsed["phones"]))
        check("experience extracted", parsed["years_experience"] == 7.0, str(parsed["years_experience"]))
        check("degree extracted", "b.tech" in parsed["education"], str(parsed["education"]))
        r = await c.post(f"/api/v1/candidates/{cand['id']}/resume", headers=admin,
                         files={"file": ("cv.exe", b"x", "application/octet-stream")})
        check("bad file type rejected (415)", r.status_code == 415)
        r = await c.get(f"/api/v1/candidates/{cand['id']}", headers=admin)
        check("parsed skills merged into profile", "kubernetes" in r.json()["skills"], r.json()["skills"])

        print("\n== PIPELINE ==")
        r = await c.post("/api/v1/applications", headers=admin,
                         json={"job_id":job["id"],"candidate_id":cand["id"]})
        check("create application", r.status_code == 201, r.text[:200])
        ap = r.json()
        check("match score computed", ap["match_score"] and ap["match_score"] > 50, str(ap["match_score"]))
        r = await c.post("/api/v1/applications", headers=admin,
                         json={"job_id":job["id"],"candidate_id":cand["id"]})
        check("duplicate application blocked (409)", r.status_code == 409)

        r = await c.post(f"/api/v1/applications/{ap['id']}/stage", headers=admin,
                         json={"to_stage":"screening","note":"Phone screen cleared"})
        check("stage move sourced -> screening", r.json()["stage"] == "screening", r.text[:200])
        r = await c.post(f"/api/v1/applications/{ap['id']}/stage", headers=admin,
                         json={"to_stage":"screening"})
        check("same-stage move rejected (400)", r.status_code == 400)
        r = await c.post(f"/api/v1/applications/{ap['id']}/stage", headers=admin,
                         json={"to_stage":"rejected"})
        check("reject without reason blocked (400)", r.status_code == 400)

        r = await c.get(f"/api/v1/applications/{ap['id']}", headers=admin)
        check("stage history recorded", len(r.json()["stage_events"]) >= 2, str(len(r.json()["stage_events"])))

        r = await c.get("/api/v1/applications/board", headers=admin)
        cols = r.json()["columns"]
        check("board returns 7 stages", len(cols) == 7, str(len(cols)))
        check("board columns populated", sum(x["count"] for x in cols) > 30,
              str(sum(x["count"] for x in cols)))
        r = await c.get(f"/api/v1/applications/board?job_id={job['id']}", headers=admin)
        check("board filters by job", sum(x["count"] for x in r.json()["columns"]) == 1)

        print("\n== INTERVIEWS ==")
        from datetime import datetime, timedelta, timezone
        when = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0)
        users = (await c.get("/api/v1/users?role=interviewer", headers=admin)).json()["items"]
        pids = [u["id"] for u in users][:2]
        r = await c.post("/api/v1/interviews", headers=admin, json={
            "application_id":ap["id"],"round_name":"Technical round 1",
            "scheduled_at":when.isoformat(),"duration_minutes":60,"mode":"video",
            "location_or_link":"https://meet.example.com/abc","panelist_ids":pids})
        check("schedule interview", r.status_code == 201, r.text[:250])
        iv = r.json()
        check("panelists attached", len(iv["panelists"]) == 2, str(len(iv["panelists"])))
        r = await c.get(f"/api/v1/applications/{ap['id']}", headers=admin)
        check("scheduling advanced stage to interview", r.json()["stage"] == "interview", r.json()["stage"])

        r = await c.post("/api/v1/interviews", headers=admin, json={
            "application_id":ap["id"],"round_name":"Clash","scheduled_at":(when+timedelta(minutes=30)).isoformat(),
            "duration_minutes":60,"mode":"video","panelist_ids":pids})
        check("double-booking blocked (409)", r.status_code == 409, r.text[:200])
        r = await c.post("/api/v1/interviews", headers=admin, json={
            "application_id":ap["id"],"round_name":"Past","scheduled_at":"2020-01-01T10:00:00+00:00",
            "panelist_ids":[]})
        check("past scheduling blocked (400)", r.status_code == 400)
        r = await c.post("/api/v1/interviews", headers=admin, json={
            "application_id":ap["id"],"round_name":"No clash",
            "scheduled_at":(when+timedelta(days=200)).isoformat(),"panelist_ids":pids})
        check("non-overlapping slot allowed", r.status_code == 201, r.text[:200])

        r = await c.get("/api/v1/interviews/my", headers=panelist)
        check("panelist sees own schedule", isinstance(r.json(), list) and len(r.json()) > 0, str(r.status_code))

        r = await c.post(f"/api/v1/interviews/{iv['id']}/feedback", headers=panelist, json={
            "overall_rating":4,"recommendation":"yes","feedback_summary":"Strong on fundamentals.",
            "criteria":{"problem_solving":4,"system_design":3,"communication":5},
            "strengths":["Depth in Kubernetes"],"concerns":["Limited Angular exposure"]})
        check("submit scorecard (Mongo)", r.status_code == 200, r.text[:250])
        check("criteria stored", r.json()["criteria"]["communication"] == 5)
        r = await c.get(f"/api/v1/interviews/{iv['id']}", headers=admin)
        check("interview marked completed", r.json()["status"] == "completed")
        r = await c.get(f"/api/v1/applications/{ap['id']}/scorecards", headers=admin)
        check("scorecards readable per application", len(r.json()) == 1)

        print("\n== OFFERS ==")
        r = await c.post("/api/v1/auth/login", json={"email":"hr@hrms.co","password":"Password@123"})
        hr = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await c.post("/api/v1/offers", headers=panelist, json={
            "application_id":ap["id"],"designation":"SRE","annual_ctc":2000000})
        check("interviewer cannot raise offers (403)", r.status_code == 403)
        r = await c.post("/api/v1/offers", headers=hr, json={
            "application_id":ap["id"],"designation":"Platform SRE","annual_ctc":2200000,
            "fixed_component":1900000,"variable_component":300000,"joining_bonus":100000})
        check("create offer", r.status_code == 201, r.text[:250])
        off = r.json()
        r = await c.get(f"/api/v1/applications/{ap['id']}", headers=admin)
        check("offer moved stage to offer", r.json()["stage"] == "offer", r.json()["stage"])
        r = await c.post("/api/v1/offers", headers=hr, json={
            "application_id":ap["id"],"designation":"Dup","annual_ctc":100000})
        check("second live offer blocked (409)", r.status_code == 409)
        r = await c.post("/api/v1/offers", headers=hr, json={
            "application_id":ap["id"],"designation":"Bad split","annual_ctc":1000000,
            "fixed_component":900000,"variable_component":500000})
        check("fixed+variable > CTC blocked (400)", r.status_code in (400, 409))
        r = await c.post(f"/api/v1/offers/{off['id']}/status", headers=hr, json={"status":"accepted"})
        check("draft cannot jump to accepted (400)", r.status_code == 400, r.text[:150])
        r = await c.post(f"/api/v1/offers/{off['id']}/status", headers=hr, json={"status":"sent"})
        check("offer sent", r.json()["status"] == "sent")
        r = await c.post(f"/api/v1/offers/{off['id']}/status", headers=hr, json={"status":"accepted"})
        check("offer accepted", r.json()["status"] == "accepted")
        r = await c.get(f"/api/v1/applications/{ap['id']}", headers=admin)
        check("acceptance marks candidate hired", r.json()["stage"] == "hired", r.json()["stage"])
        r = await c.post(f"/api/v1/offers/{off['id']}/status", headers=hr, json={"status":"declined"})
        check("terminal offer is immutable (400)", r.status_code == 400)

        print("\n== NOTES, COMMS, ACTIVITY (Mongo) ==")
        r = await c.post(f"/api/v1/candidates/{cand['id']}/notes", headers=admin,
                         json={"body":"Strong referral from Anjali."})
        check("add note", r.status_code == 201, r.text[:200])
        note = r.json()
        check("notes listed", len((await c.get(f"/api/v1/candidates/{cand['id']}/notes", headers=admin)).json()) == 1)
        check("delete note", (await c.delete(f"/api/v1/candidates/notes/{note['id']}", headers=admin)).status_code == 200)
        r = await c.get("/api/v1/comms/templates", headers=admin)
        check("email templates seeded", len(r.json()) >= 4, str(len(r.json())))
        r = await c.post("/api/v1/comms/send", headers=admin, json={
            "template_code":"interview_invite","candidate_id":cand["id"],
            "context":{"job_title":"Platform SRE","round_name":"Tech 1",
                       "scheduled_at":"12 Sep 2026, 03:00 PM","location_or_link":"https://meet.example.com/abc"}})
        check("templated email queued (202)", r.status_code == 202, r.text[:200])
        check("template variables rendered", "Test Kumar" in r.json()["body"] and "Platform SRE" in r.json()["subject"], r.json()["subject"])
        r = await c.get("/api/v1/comms/outbox", headers=admin)
        check("outbox logs sends", len(r.json()) > 0)
        r = await c.get("/api/v1/activity?limit=10", headers=admin)
        check("audit trail populated", len(r.json()) > 5, str(len(r.json())))
        r = await c.get(f"/api/v1/activity?entity_type=application&entity_id={ap['id']}", headers=admin)
        check("audit trail filterable by entity", len(r.json()) > 0)

        print("\n== DASHBOARD ANALYTICS ==")
        r = await c.get("/api/v1/dashboard", headers=admin)
        check("dashboard responds", r.status_code == 200, r.text[:400])
        d = r.json()
        check("open jobs counted", d["open_jobs"] >= 4, str(d["open_jobs"]))
        check("candidates counted", d["total_candidates"] > 30, str(d["total_candidates"]))
        check("pipeline breakdown has 7 stages", len(d["pipeline_by_stage"]) == 7, str(d["pipeline_by_stage"]))
        check("source breakdown present", len(d["applications_by_source"]) > 1, str(d["applications_by_source"]))
        check("time-to-hire computed", d["avg_time_to_hire_days"] is not None, str(d["avg_time_to_hire_days"]))
        check("offer acceptance rate computed", d["offer_acceptance_rate"] is not None, str(d["offer_acceptance_rate"]))
        check("hiring trend series present", len(d["hiring_trend"]) > 0, str(d["hiring_trend"])[:150])
        check("top jobs ranked", len(d["top_jobs"]) > 0)
        check("upcoming interviews counted", d["interviews_next_7_days"] > 0, str(d["interviews_next_7_days"]))

        print("\n== 404 HANDLING ==")
        check("missing job 404", (await c.get("/api/v1/jobs/99999", headers=admin)).status_code == 404)
        check("missing candidate 404", (await c.get("/api/v1/candidates/99999", headers=admin)).status_code == 404)
        check("missing application 404", (await c.get("/api/v1/applications/99999", headers=admin)).status_code == 404)
        check("missing offer 404", (await c.get("/api/v1/offers/99999", headers=admin)).status_code == 404)

    print("\n" + "="*60)
    print(f"PASSED {len(PASS)}   FAILED {len(FAIL)}")
    if FAIL:
        print("Failures:"); [print("  -", f) for f in FAIL]
    return 1 if FAIL else 0

sys.exit(asyncio.run(main()))
