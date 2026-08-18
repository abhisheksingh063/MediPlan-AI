"""FastAPI application entry point for MediPlan AI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.facilities import router as facilities_router
from app.api.ml import router as ml_router
from app.api.patients import router as patients_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API for a clinician-reviewed decision-support prototype.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Provide a dependency-free liveness check for local development."""
    return {"status": "ok"}


app.include_router(patients_router, prefix="/api/v1")
app.include_router(facilities_router, prefix="/api/v1")
app.include_router(ml_router, prefix="/api/v1")