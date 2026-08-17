"""FastAPI application entry point for the MediPlan AI foundation."""

from fastapi import FastAPI

app = FastAPI(
    title="MediPlan AI API",
    version="0.1.0",
    description="Foundation API for a clinician-reviewed decision-support prototype.",
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Provide a dependency-free liveness check for local development."""
    return {"status": "ok"}
