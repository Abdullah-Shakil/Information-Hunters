"""HTTP tick endpoint for Cloud Run, Cloud Functions, or a scheduler."""

import hmac

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from information_hunters.config import get_settings
from information_hunters.db import init_db
from information_hunters.pipeline import process_job
from information_hunters.worker import claim_next_job, worker_identity


def create_app() -> FastAPI:
    app = FastAPI(title="Information Hunters worker tick")

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    def authorised(authorization: str | None = Header(default=None)) -> None:
        # Optional gate for a public /tick URL (Cloud Run). Desk API has no auth.
        expected = get_settings().worker_token
        if not expected:
            return
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Missing token")
        token = authorization.split(" ", 1)[1].strip()
        if not hmac.compare_digest(token, expected):
            raise HTTPException(401, "Invalid token")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    class Tick(BaseModel):
        max_jobs: int = Field(default=1, ge=1, le=20)

    @app.post("/tick")
    def tick(body: Tick, _: None = Depends(authorised)) -> dict:
        worker_id = worker_identity()
        ran: list[str] = []
        for _ in range(body.max_jobs):
            job_id = claim_next_job(worker_id)
            if not job_id:
                break
            process_job(job_id, worker_id)
            ran.append(job_id)
        return {"processed": ran}

    return app
