from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, Field


class Evidence(TypedDict):
    source: str
    content: str


class WorkflowState(TypedDict, total=False):
    run_id: str
    tenant_id: str
    query: str
    sources: list[str]
    evidence: list[Evidence]
    normalized_evidence: list[Evidence]
    insights: list[str]
    confidence: float
    require_review: bool
    approved: bool
    review_feedback: str
    report: str
    status: str


class RunRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    query: str = Field(min_length=3, max_length=500)
    sources: list[str] = Field(min_length=1, max_length=20)
    require_review: bool = False


class ResumeRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    approved: bool
    feedback: str = Field(default="", max_length=500)


class RunResponse(BaseModel):
    run_id: str
    status: Literal["completed", "waiting_for_review", "rejected"]
    confidence: float = 0.0
    report: str | None = None
    interrupt: dict[str, object] | None = None
