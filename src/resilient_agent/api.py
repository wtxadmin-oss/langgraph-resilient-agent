from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, status

from resilient_agent.models import ResumeRequest, RunRequest, RunResponse
from resilient_agent.service import RunNotFoundError, TenantAccessError, WorkflowService

app = FastAPI(
    title="Resilient LangGraph Agent",
    version="0.1.0",
    description="Checkpointed, resumable evidence workflow with human review.",
)
service = WorkflowService()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(request: RunRequest) -> RunResponse:
    return await service.start(request)


@app.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, x_tenant_id: str = Header()) -> RunResponse:
    try:
        return await service.get(run_id, x_tenant_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    except TenantAccessError as exc:
        raise HTTPException(status_code=403, detail="tenant access denied") from exc


@app.post("/runs/{run_id}/resume", response_model=RunResponse)
async def resume_run(run_id: str, request: ResumeRequest) -> RunResponse:
    try:
        return await service.resume(run_id, request)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    except TenantAccessError as exc:
        raise HTTPException(status_code=403, detail="tenant access denied") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
