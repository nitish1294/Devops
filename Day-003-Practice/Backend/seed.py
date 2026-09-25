"""Seed demo data: run once after the stack is up.

    docker compose exec backend python seed.py
"""

import asyncio
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.enums import (
    EmploymentType,
    InterviewMode,
    InterviewStatus,
    JobStatus,
    OfferStatus,
    Role,
    Stage,
)
from app.core.security import hash_password
from app.db.mongo import init_mongo
from app.db.postgres import SessionLocal, init_postgres
from app.models.application import Application, StageEvent
from app.models.candidate import Candidate
from app.models.department import Department
from app.models.interview import Interview, InterviewPanelist
from app.models.job import Job
from app.models.offer import Offer
from app.models.user import User
from app.services import notifications, resume

USERS = [
    ("admin@hrms.co", "Nitish Sharma", Role.ADMIN, "IT & Systems Admin"),
    ("hr@hrms.co", "Meera Iyer", Role.HR_MANAGER, "Head of People"),
    ("recruiter@hrms.co", "Karan Patel", Role.RECRUITER, "Talent Acquisition"),
    ("manager@hrms.co", "Anjali Rao", Role.HIRING_MANAGER, "Engineering Manager"),
    ("dev1@hrms.co", "Rahul Desai", Role.INTERVIEWER, "Senior Engineer"),
    ("dev2@hrms.co", "Fatima Sheikh", Role.INTERVIEWER, "Staff Engineer"),
]

DEPARTMENTS = [
    ("Engineering", "Mumbai"),
    ("People & Culture", "Mumbai"),
    ("Sales", "Pune"),
    ("IT Operations", "Mumbai"),
]

JOBS = [
    ("Senior Backend Engineer", "Engineering", "Mumbai", 2, 4, 8,
     "python, fastapi, postgresql, docker, aws", JobStatus.OPEN, 1800000, 2800000),
    ("Angular Frontend Developer", "Engineering", "Mumbai", 1, 2, 5,
     "angular, typescript, rxjs, css, rest api", JobStatus.OPEN, 1200000, 1900000),
    ("DevOps Engineer", "IT Operations", "Mumbai", 1, 3, 7,
     "docker, kubernetes, jenkins, nginx, prometheus, linux", JobStatus.OPEN, 1500000, 2400000),
    ("HR Business Partner", "People & Culture", "Mumbai", 1, 5, 10,
     "recruitment, onboarding, payroll, hrms", JobStatus.OPEN, 900000, 1400000),
    ("Inside Sales Executive", "Sales", "Pune", 3, 1, 4,
     "sales, crm, excel", JobStatus.ON_HOLD, 500000, 800000),
    ("Data Analyst", "Engineering", "Mumbai", 1, 2, 5,
     "sql, python, pandas, power bi, tableau", JobStatus.DRAFT, 1000000, 1600000),
]

FIRST = ["Aarav", "Diya", "Vivaan", "Ananya", "Aditya", "Ishita", "Rohan", "Sneha",
         "Arjun", "Priya", "Kabir", "Neha", "Siddharth", "Tanvi", "Manav", "Riya",
         "Dev", "Kavya", "Yash", "Pooja", "Nikhil", "Shreya", "Omkar", "Isha"]
LAST = ["Sharma", "Patel", "Nair", "Reddy", "Gupta", "Joshi", "Menon", "Kulkarni",
        "Bose", "Chauhan", "Mehta", "Verma", "Pillai", "Sinha"]
COMPANIES = ["Infosys", "TCS", "Zoho", "Freshworks", "Razorpay", "Swiggy", "Paytm",
             "Wipro", "Tech Mahindra", "Zerodha", "PhonePe", "Cred"]
SOURCES = ["naukri", "linkedin", "referral", "careers_site", "campus"]
SKILL_POOL = [
    "python, fastapi, postgresql, docker",
    "angular, typescript, rxjs, css",
    "docker, kubernetes, jenkins, nginx, linux",
    "java, spring boot, mysql, rest api",
    "recruitment, onboarding, hrms, payroll",
    "sql, python, pandas, power bi",
    "react, javascript, node.js, mongodb",
    "aws, terraform, prometheus, grafana",
]


async def main() -> None:
    await init_postgres()
    await init_mongo()
    await notifications.seed_templates()
    rng = random.Random(42)

    async with SessionLocal() as db:
        if (await db.execute(select(func.count(User.id)))).scalar_one():
            print("Data already present - nothing seeded. Drop the volumes to reset.")
            return

        depts = {}
        for name, loc in DEPARTMENTS:
            d = Department(name=name, location=loc)
            db.add(d)
            depts[name] = d
        await db.flush()

        users = {}
        for email, name, role, title in USERS:
            u = User(
                email=email,
                full_name=name,
                role=role,
                title=title,
                password_hash=hash_password("Password@123"),
                department_id=depts["Engineering"].id if role == Role.INTERVIEWER else None,
            )
            db.add(u)
            users[email] = u
        await db.flush()

        jobs = []
        for i, (title, dept, loc, openings, exp_lo, exp_hi, skills, st, sal_lo, sal_hi) in enumerate(JOBS, 1):
            j = Job(
                code=f"REQ-2026-{i:04d}",
                title=title,
                description=f"We are hiring a {title} for the {dept} team in {loc}.",
                location=loc,
                employment_type=EmploymentType.FULL_TIME,
                status=st,
                openings=openings,
                experience_min=exp_lo,
                experience_max=exp_hi,
                salary_min=sal_lo,
                salary_max=sal_hi,
                skills=skills,
                target_close_date=date.today() + timedelta(days=45),
                department_id=depts[dept].id,
                hiring_manager_id=users["manager@hrms.co"].id,
                recruiter_id=users["recruiter@hrms.co"].id,
            )
            db.add(j)
            jobs.append(j)
        await db.flush()

        candidates = []
        used = set()
        for _ in range(40):
            fn, ln = rng.choice(FIRST), rng.choice(LAST)
            email = f"{fn.lower()}.{ln.lower()}{rng.randint(1, 999)}@example.com"
            if email in used:
                continue
            used.add(email)
            exp = round(rng.uniform(1, 12), 1)
            c = Candidate(
                full_name=f"{fn} {ln}",
                email=email,
                phone=f"9{rng.randint(100000000, 899999999)}",
                location=rng.choice(["Mumbai", "Pune", "Bengaluru", "Hyderabad", "Remote"]),
                current_company=rng.choice(COMPANIES),
                current_title=rng.choice(
                    ["Software Engineer", "Senior Engineer", "Analyst", "HR Executive", "SRE"]
                ),
                total_experience=exp,
                current_ctc=round(rng.uniform(6, 30)) * 100000,
                expected_ctc=round(rng.uniform(10, 40)) * 100000,
                notice_period_days=rng.choice([0, 30, 60, 90]),
                source=rng.choice(SOURCES),
                skills=rng.choice(SKILL_POOL),
            )
            db.add(c)
            candidates.append(c)
        await db.flush()

        open_jobs = [j for j in jobs if j.status == JobStatus.OPEN]
        weights = [Stage.SOURCED] * 6 + [Stage.SCREENING] * 5 + [Stage.INTERVIEW] * 5 + \
                  [Stage.ASSESSMENT] * 3 + [Stage.OFFER] * 2 + [Stage.HIRED] * 2 + [Stage.REJECTED] * 4
        applications = []
        for cand in candidates:
            for job in rng.sample(open_jobs, rng.choice([1, 1, 2])):
                stage = rng.choice(weights)
                created = datetime.now(timezone.utc) - timedelta(days=rng.randint(3, 120))
                app = Application(
                    job_id=job.id,
                    candidate_id=cand.id,
                    stage=stage,
                    owner_id=users["recruiter@hrms.co"].id,
                    board_position=len(applications) + 1,
                    match_score=resume.score_match(job.skill_list, cand.skill_list),
                    created_at=created,
                    updated_at=created + timedelta(days=rng.randint(0, 20)),
                    rejection_reason="Skills did not match the requirement"
                    if stage == Stage.REJECTED else None,
                    closed_at=created + timedelta(days=rng.randint(10, 40))
                    if stage in Stage.terminal() else None,
                )
                db.add(app)
                applications.append((app, created, stage))
        await db.flush()

        # Walk each application through the stages it passed, so metrics have real history.
        order = Stage.board_order()
        for app, created, stage in applications:
            path = order[: order.index(stage) + 1] if stage in order else [stage]
            if stage == Stage.REJECTED:
                path = [Stage.SOURCED, Stage.SCREENING, Stage.REJECTED]
            when = created
            prev = None
            for st in path:
                db.add(
                    StageEvent(
                        application_id=app.id,
                        from_stage=prev,
                        to_stage=st,
                        note="Seeded history",
                        moved_by_id=users["recruiter@hrms.co"].id,
                        created_at=when,
                    )
                )
                prev = st
                when = when + timedelta(days=rng.randint(2, 9))

        panel = [users["dev1@hrms.co"].id, users["dev2@hrms.co"].id,
                 users["manager@hrms.co"].id]
        slot = 0
        for app, _, stage in applications:
            if stage not in (Stage.INTERVIEW, Stage.ASSESSMENT, Stage.OFFER, Stage.HIRED):
                continue
            future = stage in (Stage.INTERVIEW, Stage.ASSESSMENT)
            slot += 1
            when = datetime.now(timezone.utc) + timedelta(days=slot % 9 + 1, hours=slot % 6) \
                if future else datetime.now(timezone.utc) - timedelta(days=slot % 30 + 2)
            iv = Interview(
                application_id=app.id,
                round_name=rng.choice(["Technical round 1", "Technical round 2",
                                       "System design", "Managerial round", "HR discussion"]),
                scheduled_at=when.replace(minute=0, second=0, microsecond=0),
                duration_minutes=rng.choice([30, 45, 60]),
                mode=rng.choice(list(InterviewMode)),
                location_or_link="https://meet.example.com/" + str(rng.randint(1000, 9999)),
                status=InterviewStatus.SCHEDULED if future else InterviewStatus.COMPLETED,
                overall_rating=None if future else rng.randint(2, 5),
                recommendation=None if future else rng.choice(["yes", "strong_yes", "no"]),
                feedback_summary=None if future else "Seeded feedback summary.",
                created_by_id=users["recruiter@hrms.co"].id,
            )
            db.add(iv)
            await db.flush()
            for uid in rng.sample(panel, 2):
                db.add(InterviewPanelist(interview_id=iv.id, user_id=uid))

        for app, _, stage in applications:
            if stage not in (Stage.OFFER, Stage.HIRED):
                continue
            ctc = round(rng.uniform(12, 32)) * 100000
            db.add(
                Offer(
                    application_id=app.id,
                    designation=rng.choice(["Senior Backend Engineer", "Frontend Developer",
                                            "DevOps Engineer", "HR Business Partner"]),
                    annual_ctc=ctc,
                    fixed_component=ctc * 0.85,
                    variable_component=ctc * 0.15,
                    joining_bonus=rng.choice([0, 50000, 100000]),
                    joining_date=date.today() + timedelta(days=rng.randint(15, 75)),
                    valid_till=date.today() + timedelta(days=10),
                    status=OfferStatus.ACCEPTED if stage == Stage.HIRED
                    else rng.choice([OfferStatus.DRAFT, OfferStatus.SENT]),
                    approved_by_id=users["hr@hrms.co"].id,
                )
            )

        await db.commit()

    print("Seeded:")
    print(f"  {len(DEPARTMENTS)} departments, {len(USERS)} users, {len(JOBS)} requisitions")
    print(f"  {len(candidates)} candidates, {len(applications)} applications")
    print("\nSign in with any of these (password: Password@123):")
    for email, name, role, _ in USERS:
        print(f"  {email:<26} {role:<16} {name}")


if __name__ == "__main__":
    asyncio.run(main())
