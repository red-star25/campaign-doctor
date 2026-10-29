"""FastAPI app. Routes call the existing engine and do not send email."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from campaign_doctor.api.catalog import ScenarioNotFound
from campaign_doctor.api.schemas import (
    CompareRequest,
    CompareResponse,
    HealthResponse,
    ReportResponse,
    ScenarioListResponse,
)
from campaign_doctor.api.service import (
    UnknownFollowUp,
    build_scenario_report,
    compare_scenario,
    health,
    list_scenarios,
)

logger = logging.getLogger("campaign_doctor.api")

# Used only when CORS_ORIGINS is unset, so a local UI still works.
_LOCAL_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
_PUBLIC_ERROR = "The request could not be completed."


def allowed_origins() -> list[str]:
    """Browser origins allowed to call the API.

    CORS_ORIGINS is a comma-separated list, read when the process starts.
    An empty or missing value keeps the local development origins.
    """
    raw = os.environ.get("CORS_ORIGINS", "")
    configured = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
    if not configured:
        return list(_LOCAL_ORIGINS)
    unique: list[str] = []
    for origin in configured:
        if origin not in unique:
            unique.append(origin)
    return unique


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cardinal Campaign Doctor",
        version="0.1.0",
        debug=False,
        summary="Synthetic campaign replay API.",
        description=(
            "Reads made-up campaign logs and explains them. "
            "It does not send email and it is not connected to Cardinal."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def hide_internal_errors(_request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, HTTPException):
            detail = exc.detail if isinstance(exc.detail, str) else _PUBLIC_ERROR
            return JSONResponse(status_code=exc.status_code, content={"detail": detail})
        logger.exception("request failed")
        return JSONResponse(status_code=500, content={"detail": _PUBLIC_ERROR})

    @app.get("/api/health", response_model=HealthResponse)
    def get_health() -> HealthResponse:
        return health()

    @app.get("/api/scenarios", response_model=ScenarioListResponse)
    def get_scenarios() -> ScenarioListResponse:
        return list_scenarios()

    @app.get("/api/scenarios/{scenario_id}/report", response_model=ReportResponse)
    def get_report(scenario_id: str) -> ReportResponse:
        try:
            return build_scenario_report(scenario_id)
        except ScenarioNotFound:
            raise HTTPException(status_code=404, detail="Unknown scenario.") from None

    @app.post("/api/scenarios/{scenario_id}/compare", response_model=CompareResponse)
    def post_compare(scenario_id: str, body: CompareRequest) -> CompareResponse:
        try:
            return compare_scenario(scenario_id, body.provider_condition, body.followup_event_id)
        except ScenarioNotFound:
            raise HTTPException(status_code=404, detail="Unknown scenario.") from None
        except UnknownFollowUp:
            raise HTTPException(status_code=422, detail="Unknown follow-up event.") from None

    return app


app = create_app()
