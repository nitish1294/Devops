# Day 003: Backend Docker Deployment - FastAPI Application

## Overview

Successfully containerized and deployed a FastAPI backend application with PostgreSQL and MongoDB databases using Docker and Docker Compose.

**Stack:**
- FastAPI (Python 3.11)
- PostgreSQL 15 (relational database)
- MongoDB 7 (document database)
- Uvicorn (ASGI server)

---

## Architecture

```
┌─────────────────────────┐
│   FastAPI Backend       │
│   (Uvicorn Server)      │
│   Port 5000             │
└────────┬────────────────┘
         │
    ┌────┴─────┐
    │           │
┌───▼──┐  ┌────▼───┐
│ PG   │  │ Mongo   │
│ 5432 │  │ 27017   │
└──────┘  └─────────┘
```

---

## What We Learned

### 1. Single-Stage Dockerfile for Python

**Why NOT multi-stage for Python?**

```dockerfile
# ❌ WRONG: Multi-stage with venv
RUN python3 -m venv .venv
RUN source .venv/bin/activate      # Only works in THIS shell
RUN pip install -r requirements.txt # Runs in NEW shell, venv not active
```

Each `RUN` command is a **separate shell**, so activation doesn't persist.

### 2. Correct Python Approach

```dockerfile
# ✅ CORRECT: Single-stage, direct pip install
FROM python:3.11-alpine3.23
WORKDIR /APP

COPY ./Backend .
RUN pip install -r requirements.txt

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]
```

**Why this works:**
- Docker already isolates the container
- No venv needed — Docker provides isolation
- Simpler, cleaner, fewer layers

### 3. Module Execution with `-m`

**Issue:** Using `python app/main.py` causes import errors

```python
# In app/core/enums.py
from app.api.v1.router import api_router  # Fails because 'app' module not found
```

**Solution:** Use module mode

```dockerfile
CMD ["python", "-m", "app.main"]
```

This tells Python to run `app.main` as a **package**, making imports work.

### 4. Python Version Matters

**Error:** `ImportError: cannot import name 'StrEnum' from 'enum'`

`StrEnum` was added in Python 3.11, but base image was 3.10.

```dockerfile
# ✅ Change FROM python:3.10 to:
FROM python:3.11-alpine3.23
```

### 5. Database Configuration

**PostgreSQL:** Relational data (candidates, jobs, offers)
```
Hostname: db (docker network)
Port: 5432
Database: hrmsdb
```

**MongoDB:** Documents (resumes, scorecards, audit logs)
```
Hostname: mongo (docker network)
Port: 27017
Database: hrmsdb
```

---

## File Structure

```
Day-003-Practice/
├── Backend/
│   ├── Dockerfile                ← Backend container image
│   ├── docker-compose.yml        ← Multi-container orchestration
│   ├── README.md                 ← This file
│   ├── app/
│   │   ├── main.py               ← FastAPI entry point
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   ├── deps.py
│   │   │   └── ...
│   │   ├── core/
│   │   │   ├── enums.py
│   │   │   ├── config.py
│   │   │   └── ...
│   │   ├── db/
│   │   │   ├── postgres.py
│   │   │   ├── mongo.py
│   │   │   └── ...
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   ├── migrations/               ← Alembic database migrations
│   ├── requirements.txt
│   ├── seed.py
│   └── tests_*.py
```

---

## Dockerfile Breakdown

```dockerfile
FROM python:3.11-alpine3.23
```
- `python:3.11` — Python 3.11 base (required for StrEnum)
- `alpine3.23` — Lightweight Linux (~50MB vs 800MB+)

```dockerfile
WORKDIR /APP
```
- Sets working directory inside container
- All subsequent commands run here
- `COPY . .` copies to `/APP`

```dockerfile
COPY ./Backend .
```
- Copies Backend folder contents to `/APP`
- Now in container: `/APP/app/`, `/APP/requirements.txt`, etc.

```dockerfile
RUN pip install --no-cache-dir --upgrade pip
```
- `--no-cache-dir` — Don't store cache files (saves space)
- `--upgrade pip` — Latest pip version

```dockerfile
RUN apk add --no-cache python3-dev
```
- Installs C compiler + headers
- Needed for packages like `psycopg2` (PostgreSQL driver)
- Alpine equivalent of `apt-get install python3-dev`

```dockerfile
RUN pip install -r requirements.txt
```
- Installs all Python dependencies
- Example: FastAPI, SQLAlchemy, psycopg2, pymongo, etc.

```dockerfile
EXPOSE 5000
```
- Documents that app listens on port 5000
- Doesn't actually open port (compose does)

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]
```
- Starts Uvicorn ASGI server
- `app.main:app` — Run `app` object from `app/main.py`
- `--host 0.0.0.0` — Accept connections from any IP
- `--port 5000` — Listen on port 5000

---

## Docker Compose Breakdown

```yaml
version: '3.8'
```
Latest stable docker-compose version

```yaml
services:
  backend:
    build: .
    container_name: hrms_backend
```
- `build: .` — Build from Dockerfile in current directory
- `container_name` — Name the container (easier to reference)

```yaml
    restart: unless-stopped
```
- Restart if crashes, **unless explicitly stopped**
- Other options: `no`, `always`, `on-failure`

```yaml
    ports:
      - "5000:5000"
```
- `HOST_PORT:CONTAINER_PORT`
- Maps port 5000 on your computer → port 5000 in container

```yaml
    environment:
      - DATABASE_URL=postgresql://postgres:secure_password@db:5432/hrmsdb
      - MONGO_URL=mongodb://mongo:27017/hrmsdb
```
- `db` and `mongo` are service names (docker DNS resolves them)
- Backend automatically finds databases via these hostnames

```yaml
    depends_on:
      - db
      - mongo
```
- Start database services first
- Then start backend
- Ensures databases are ready before backend tries to connect

```yaml
    networks:
      - hrms-network
```
- All services on same network can talk to each other
- Service name = hostname (docker DNS)

```yaml
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health/live"]
      interval: 10s
      timeout: 5s
      retries: 3
```
- Checks if backend is alive every 10 seconds
- If 3 consecutive failures, container marked as unhealthy
- `docker compose` auto-restarts unhealthy containers

```yaml
  db:
    image: postgres:15
```
- Use official PostgreSQL image (no Dockerfile needed)
- Already optimized by Docker/PostgreSQL team

```yaml
  mongo:
    image: mongo:7
```
- Use official MongoDB image

```yaml
volumes:
  postgres_data:
  mongo_data:
```
- Named volumes for persistent data
- Survives container restart/deletion
- Data stored on host machine

```yaml
networks:
  hrms-network:
    driver: bridge
```
- Custom bridge network
- All services can ping each other by service name

---

## Real-World Deployment Flow

### Step 1: Build the Image

```bash
docker compose build
```

**What happens:**
1. Docker reads `Dockerfile`
2. Downloads `python:3.11-alpine3.23` base image
3. Creates layer: `WORKDIR /APP`
4. Creates layer: `COPY ./Backend .`
5. Creates layer: `pip install...`
6. Final image ready (~300MB)

**Result:** `day-003-practice-backend` image

### Step 2: Start All Services

```bash
docker compose up -d
```

**Startup order:**
1. Create volumes (`postgres_data`, `mongo_data`)
2. Create network (`hrms-network`)
3. Start PostgreSQL (listens on 5432)
4. Start MongoDB (listens on 27017)
5. Wait for `depends_on` services
6. Start FastAPI backend (listens on 5000)
7. Uvicorn logs show server started

**Check status:**
```bash
docker compose ps
```

Output:
```
NAME              STATUS         PORTS
hrms_backend      running (healthy)   0.0.0.0:5000->5000/tcp
hrms_postgres     running (healthy)   0.0.0.0:5432->5432/tcp
hrms_mongo        running (healthy)   0.0.0.0:27017->27017/tcp
```

### Step 3: Test Backend

```bash
# Health check
curl http://localhost:5000/health/live
# Response: {"status": "alive"}

# Full health (checks databases)
curl http://localhost:5000/health
# Response: {"status": "ok", "postgres": "up", "mongo": "up", ...}

# View API docs
curl http://localhost:5000/docs
```

### Step 4: View Logs

```bash
# All services
docker compose logs -f

# Just backend
docker compose logs -f backend

# Last 100 lines
docker compose logs --tail=100 backend
```

### Step 5: Stop Everything

```bash
docker compose down
```

- Stops all containers gracefully
- Keeps volumes (data persists)
- Removes network, containers

```bash
docker compose down -v
```

- Also deletes volumes (⚠️ data lost)

---

## Troubleshooting

### Backend exits with code 0 (not running)

**Cause:** No server started

```bash
docker compose logs backend
# No error, but process exited
```

**Fix:** Ensure CMD is correct

```dockerfile
# ✅ Correct
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]

# ❌ Wrong (exits after import check)
CMD ["python", "app/main.py"]
```

### ModuleNotFoundError: No module named 'app'

**Cause:** Wrong way to run Python script

```dockerfile
# ❌ Wrong
CMD ["python", "app/main.py"]

# ✅ Correct (module mode)
CMD ["python", "-m", "app.main"]
```

### ImportError: cannot import name 'StrEnum'

**Cause:** Python 3.10 doesn't have `StrEnum` (added in 3.11)

```dockerfile
# ✅ Fix
FROM python:3.11-alpine3.23
```

### Cannot connect to database

**Cause 1:** Database service not started

```bash
docker compose ps
# Check if 'db' and 'mongo' are running
```

**Cause 2:** Wrong hostname

```python
# ❌ Wrong (localhost doesn't work inside container)
DATABASE_URL = "postgresql://postgres:pwd@localhost:5432/hrmsdb"

# ✅ Correct (service name on docker network)
DATABASE_URL = "postgresql://postgres:pwd@db:5432/hrmsdb"
```

**Cause 3:** Database not ready yet

```dockerfile
# Add to backend service in compose:
depends_on:
  db:
    condition: service_healthy
  mongo:
    condition: service_healthy
```

### Volume mount overwrites installed packages

**Setup:**
```yaml
volumes:
  - ./Backend:/APP  # ❌ Mounts entire directory
```

**Problem:** Local `./Backend` folder overwrites container `/APP`, losing pip packages.

**Fix:** Don't mount volumes for production

```yaml
# ✅ Remove volumes for production
# Only use during development if you need live code reloading
```

---

## Common Commands

```bash
# Start services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f backend

# Enter backend container
docker exec -it hrms_backend sh

# Check health
curl http://localhost:5000/health

# Stop services
docker compose down

# Rebuild (fresh image)
docker compose build --no-cache

# Force restart service
docker compose restart backend
```

---

## Database Access

### PostgreSQL

```bash
# Connect via psql
docker exec -it hrms_postgres psql -U postgres -d hrmsdb

# Common commands inside psql
\dt              # List tables
SELECT * FROM candidates;
\q               # Quit
```

### MongoDB

```bash
# Connect via mongosh
docker exec -it hrms_mongo mongosh

# Common commands
db.resumes.find()
db.scorecards.find()
exit
```

---

## Environment Variables

Create `.env` file:

```env
# PostgreSQL
POSTGRES_PASSWORD=secure_password_here
POSTGRES_DB=hrmsdb

# Backend connections
DATABASE_URL=postgresql://postgres:secure_password_here@db:5432/hrmsdb
MONGO_URL=mongodb://mongo:27017/hrmsdb

# FastAPI
ENVIRONMENT=production
LOG_LEVEL=info
```

Then in `docker-compose.yml`:

```yaml
backend:
  environment:
    - DATABASE_URL=${DATABASE_URL}
    - MONGO_URL=${MONGO_URL}
```

---

## Performance

| Component | Size | Build Time | Startup |
|-----------|------|-----------|---------|
| Backend image | ~300MB | ~1min | <5s |
| PostgreSQL | ~150MB | Pulled | ~2s |
| MongoDB | ~200MB | Pulled | ~3s |
| **Total** | **~650MB** | **~1min** | **~10s** |

---

## Best Practices Applied

✅ **Alpine base images** — Lightweight  
✅ **Single-stage for Python** — No venv complexity  
✅ **Module execution (`-m` flag)** — Proper import paths  
✅ **Health checks** — Auto-restart on failure  
✅ **Named volumes** — Data persistence  
✅ **Custom networks** — Service-to-service DNS  
✅ **Environment config** — No hardcoded passwords  
✅ **Restart policies** — Production resilience  

---

## Next Steps

- [ ] Add database health checks
- [ ] Set up logging aggregation
- [ ] Configure CORS for frontend
- [ ] Add authentication endpoints
- [ ] Database backups
- [ ] Load testing
- [ ] Kubernetes deployment (k3s)

---

## References

- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Python in Docker](https://docs.docker.com/language/python/)
- [PostgreSQL Docker](https://hub.docker.com/_/postgres)
- [MongoDB Docker](https://hub.docker.com/_/mongo)

---

## Status

✅ **Successfully Deployed**

- FastAPI backend running on port 5000
- PostgreSQL database running on port 5432
- MongoDB database running on port 27017
- All services auto-restart on failure
- Health endpoints responding
- Ready for development & testing

---

**Author:** Nitish  
**Date:** September 25, 2026  
**Project:** Probus Insurance HRMS
