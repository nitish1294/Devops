# HRMS Recruit

An applicant tracking and recruitment management system: requisitions, a candidate
database with resume parsing, a drag-and-drop hiring pipeline, interview scheduling
with panel conflict detection, offer management with generated PDF letters, and
hiring analytics.

**Angular 18 · FastAPI · PostgreSQL · MongoDB**

---

## Running it on Windows with databases in WSL

This is the setup these instructions assume: you edit and run the code on Windows
(VS Code, PowerShell), and PostgreSQL and MongoDB run inside WSL Ubuntu.

WSL2 forwards `localhost`, so Windows can reach both databases at `127.0.0.1` —
but only once Postgres is listening on more than its own loopback. That is the
step people miss.

### Prerequisites

| | Version | Why |
|---|---|---|
| Python | **3.12** | Newer versions have no prebuilt wheels for the pinned packages and pip tries to compile them |
| Node.js | 18.19+ or 20+ | Angular 18 requires it |
| PostgreSQL | 14+ | In WSL |
| MongoDB | 6+ | In WSL |

Check what you have:

```powershell
python --version
node --version
```

If Python is 3.13 or newer, install 3.12 alongside it:

```powershell
winget install Python.Python.3.12
```

Reopen the terminal afterwards, then use `py -3.12` when creating the virtual
environment.

---

### 1. Prepare the databases (in WSL)

```bash
sudo systemctl start postgresql mongod
```

Create the database and a user for the app:

```bash
sudo -u postgres psql <<'SQL'
CREATE USER hrms WITH PASSWORD 'hrms';
CREATE DATABASE hrms OWNER hrms;
SQL
```

The `OWNER` matters — migrations create tables, so the user needs ownership,
not just login rights.

**Now make Postgres reachable from Windows.** By default it listens only on
WSL's own loopback, and nothing outside WSL can connect.

Find your version:

```bash
ls /etc/postgresql/
```

Edit `/etc/postgresql/<version>/main/postgresql.conf`:

```
listen_addresses = '*'
```

Add to the end of `/etc/postgresql/<version>/main/pg_hba.conf`:

```
host    all    all    0.0.0.0/0    scram-sha-256
```

For MongoDB, edit `/etc/mongod.conf`:

```yaml
net:
  bindIp: 0.0.0.0
```

Restart both and verify:

```bash
sudo systemctl restart postgresql mongod
sudo ss -tlnp | grep -E '5432|27017'
```

You want `0.0.0.0:5432`, not `127.0.0.1:5432`. If it still shows the loopback
address, the config edit did not take effect.

> `0.0.0.0` is fine on a development laptop — WSL sits behind a NAT and is not
> exposed to your network. Do not carry this setting to a server.

### 2. Check for a second PostgreSQL on Windows

This is worth thirty seconds now and can cost you an evening later. If you have
ever installed PostgreSQL on Windows, it is holding port 5432 and your app will
connect to *that* instance instead of the one in WSL — with different
credentials and no `hrms` database.

```powershell
Get-Service | Where-Object {$_.Name -like "*postgres*"}
```

If anything comes back, stop it from an **Administrator** PowerShell:

```powershell
Stop-Service postgresql-x64-18          # match your version
Set-Service postgresql-x64-18 -StartupType Manual
```

A port test like `Test-NetConnection 127.0.0.1 -Port 5432` will say the port is
open either way. It proves something is listening, not *which* thing.

### 3. Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If activation is blocked by execution policy, run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Create the environment file:

```powershell
copy .env.example .env
```

Then open **`.env`** — not `.env.example`, which is only a template and is never
read — and set:

```
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_USER=hrms
POSTGRES_PASSWORD=hrms
POSTGRES_DB=hrms

MONGO_URI=mongodb://127.0.0.1:27017
MONGO_DB=hrms_docs

JWT_SECRET=replace-with-a-long-random-string
```

No quotes around values — `POSTGRES_PASSWORD="hrms"` makes the quotes part of
the password.

Confirm the app sees what you expect:

```powershell
python -c "from app.core.config import settings; print(settings.postgres_dsn)"
```

Then create the schema, load demo data, and start the server:

```powershell
alembic upgrade head
python seed.py
uvicorn app.main:app --reload --port 8000
```

`alembic upgrade head` is not optional. The app checks the schema on boot and
refuses to start against a database that has never been migrated, rather than
creating tables behind your back and drifting from the migration history.

Check **http://localhost:8000/health** — both `postgres` and `mongo` should
report `up`.

### 4. Frontend

In a **second terminal**, leaving the backend running:

```powershell
cd frontend
npm install
npm start
```

Open **http://localhost:4200**.

`proxy.conf.json` forwards `/api` to port 8000, so the browser only ever talks
to one origin and CORS never enters the picture.

### 5. Sign in

| Email | Role | What they can do |
|---|---|---|
| `admin@hrms.co` | Admin | Everything, including managing the team |
| `hr@hrms.co` | HR manager | Everything except team management; approves offers |
| `recruiter@hrms.co` | Recruiter | Requisitions, candidates, pipeline, interviews |
| `manager@hrms.co` | Hiring manager | Moves candidates through the pipeline |
| `dev1@hrms.co` | Interviewer | Own panels and feedback only |

Password for all of them: `Password@123`

Signing in as different roles is the fastest way to see the permission model —
the interviewer account gets a much smaller navigation rail, and the API returns
403 rather than hiding buttons and hoping.

---

## Troubleshooting

**`password authentication failed for user "postgres"`**
You are almost certainly hitting a Windows PostgreSQL rather than the one in
WSL. See step 2.

**`ConnectionRefusedError: [WinError 1225]`**
Nothing is listening on that port. Either the WSL service is stopped
(`sudo systemctl start postgresql`) or it is bound to `127.0.0.1` only — check
with `sudo ss -tlnp | grep 5432` and see step 1.

**`Failed building wheel for pydantic-core / asyncpg / greenlet`**
Your Python is newer than the pinned packages support, so pip is trying to
compile from source. Use 3.12.

**`No suitable Python runtime found` from `py -3.12`**
3.12 is not installed. `winget install Python.Python.3.12`, then reopen the
terminal.

**`ReadTimeoutError` during `pip install`**
A slow or filtered connection, not a problem with the project:

```powershell
pip install -r requirements.txt --timeout 120 --retries 10
```

pip keeps partial progress, so rerunning resumes rather than restarting.

**Login says the email or password is wrong**
`python seed.py` never ran, so there are no accounts. Stop the server, run it,
start again.

**The app starts but every page errors**
The backend is not running, or is on a port other than 8000.

---

## Why two databases

They hold different shapes of data, and forcing either one to do the other's
job is where this kind of system usually goes wrong.

**PostgreSQL** holds records that need constraints, joins and transactions:
users, departments, jobs, candidates, applications, stage events, interviews and
offers. A candidate cannot be on the same requisition twice, an offer cannot
exist without an application, and moving someone through the pipeline has to be
atomic with writing its history row. Those are foreign keys and unique
constraints, not application-level hope.

**MongoDB** holds documents whose shape varies per record:

| Collection | Why it isn't relational |
|---|---|
| `resumes` | Parsed output differs per CV — skills, education and dates are all optional and multi-valued |
| `scorecards` | Criteria differ per role; a backend interview rates system design, a sales interview does not |
| `notes` | Free text, arbitrary volume per candidate |
| `activity` | Append-only audit trail; every entity type logs a different payload |
| `email_templates`, `outbox` | Templates and rendered messages |

Both are checked by `/health`, so a half-up stack reports itself as degraded
instead of failing later on a request.

---

## What the system does

**Requisitions** get codes generated as `REQ-2026-0001`. Closing one keeps its
applications intact.

**Candidates** are deduplicated on normalised email. Uploading a resume extracts
text from PDF, DOCX or plain text, pulls out skills, phone, years of experience
and degrees, and merges the discovered skills into the profile. The original
file is kept and can be downloaded exactly as it was uploaded.

**Resume search** matches substrings, so "kuber" finds "kubernetes" — which is
what a recruiter typing half a technology name expects.

**The pipeline** has seven stages: sourced → screening → interview → assessment
→ offer → hired, with rejected as the other terminal state. Every move goes
through one endpoint which appends to the stage history in the same transaction,
so the history cannot drift from the current stage. Rejecting without a reason
is refused — a pipeline full of unexplained rejections is useless three months
later. Batches can be moved together.

**Interviews** reject a panelist who is already booked in an overlapping slot,
naming the person in the error. Scheduling advances the application to the
interview stage and attaches a calendar invite, so the round lands in the
candidate's diary rather than as a date they have to copy out.

**Offers** are a state machine: draft → sent → accepted / declined / withdrawn.
Accepting marks the candidate hired; declining rejects them. Terminal offers are
immutable. Releasing one attaches a generated PDF letter.

**Emails** are rendered from templates and written to an outbox; a background
worker hands them to SMTP. With `SMTP_HOST` empty nothing is sent and messages
stay queued, which is the right behaviour on a machine that should not mail real
candidates. Failures back off and retry.

**Exports** produce CSV honouring whatever filters are on screen, with formula
injection neutralised — a candidate named `=SUM(A1:A9)` exports as text.

---

## Tests

```powershell
cd backend
pip install -r requirements-dev.txt
alembic upgrade head
python tests_core.py        # 75 assertions
python tests_features.py    # 103 assertions
```

Both drive the application over HTTP against a real PostgreSQL — not unit tests
with mocked repositories. The document side runs against an in-memory Mongo, so
no Mongo server is needed to run them.

---

## Project layout

```
backend/
├── app/
│   ├── main.py       app, lifespan, health probes, error handlers
│   ├── core/         settings, JWT + bcrypt, enums, logging, rate limiting
│   ├── db/           async engine and Motor client, index creation
│   ├── models/       SQLAlchemy tables
│   ├── schemas/      Pydantic request/response models
│   ├── services/     resume parsing, scorecards, email, iCalendar, PDF, CSV
│   └── api/v1/       auth, users, jobs, candidates, applications,
│                     interviews, offers, dashboard, comms
├── migrations/       Alembic revisions
└── seed.py           demo data

frontend/
├── src/app/
│   ├── core/         ApiService, AuthService, interceptor, guard
│   ├── layout/       app shell and navigation rail
│   └── features/     login, dashboard, pipeline, jobs, candidates,
│                     interviews, offers, people, settings
├── nginx.conf        for a server deployment
└── proxy.conf.json   for `npm start`
```

63 endpoints under `/api/v1`. Browse them at **http://localhost:8000/docs**.

---

## Before this goes anywhere real

1. Set a generated `JWT_SECRET`. The default is a placeholder.
2. Put TLS in front of it.
3. Move resume files to object storage. They currently live in Mongo alongside
   their parsed text, which works but will not stay pleasant as it grows.
4. Move the login rate-limit counters to Redis if you run more than one uvicorn
   worker — they live in process memory, so today the allowance is per worker.
5. Add frontend tests. There are none.
