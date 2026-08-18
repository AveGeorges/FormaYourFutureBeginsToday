from fastapi import APIRouter

from app.presentation import ai_planning, bff, identity, planning, scheduling, tasks, time_tracking

api_router = APIRouter()
api_router.include_router(identity.router, prefix="/workspaces", tags=["identity"])
api_router.include_router(planning.router, tags=["planning"])
api_router.include_router(tasks.router, tags=["tasks"])
api_router.include_router(scheduling.router, tags=["scheduling"])
api_router.include_router(time_tracking.router, tags=["time-tracking"])
api_router.include_router(ai_planning.router, tags=["ai-planning"])
api_router.include_router(bff.router, prefix="/bff", tags=["web-bff"])
