from fastapi import APIRouter

from app.api.v1 import applications, auth, candidates, comms, dashboard, interviews, jobs, offers, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(jobs.router)
api_router.include_router(candidates.router)
api_router.include_router(applications.router)
api_router.include_router(interviews.router)
api_router.include_router(offers.router)
api_router.include_router(dashboard.router)
api_router.include_router(comms.router)
