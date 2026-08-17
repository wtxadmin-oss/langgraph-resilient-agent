from __future__ import annotations

import pytest

from resilient_agent.graph import build_graph
from resilient_agent.models import ResumeRequest, RunRequest
from resilient_agent.service import TenantAccessError, WorkflowService
from resilient_agent.tools import DeterministicEvidenceTool, TransientCollectionError


@pytest.mark.asyncio
async def test_happy_path_completes_without_review() -> None:
    service = WorkflowService()
    response = await service.start(
        RunRequest(
            tenant_id="brand-a",
            query="Compare product positioning",
            sources=["catalog", "marketplace"],
        )
    )

    assert response.status == "completed"
    assert response.confidence == pytest.approx(0.85)
    assert response.report and "Evidence Report" in response.report


@pytest.mark.asyncio
async def test_interrupt_can_resume_after_human_approval() -> None:
    service = WorkflowService()
    paused = await service.start(
        RunRequest(
            tenant_id="brand-a",
            query="Review a high-impact catalog change",
            sources=["catalog"],
            require_review=True,
        )
    )

    assert paused.status == "waiting_for_review"
    assert paused.interrupt and paused.interrupt["type"] == "human_review"

    fetched = await service.get(paused.run_id, "brand-a")
    assert fetched.status == "waiting_for_review"
    assert fetched.interrupt and fetched.interrupt["run_id"] == paused.run_id

    completed = await service.resume(
        paused.run_id,
        ResumeRequest(tenant_id="brand-a", approved=True, feedback="evidence checked"),
    )
    assert completed.status == "completed"
    assert completed.report


@pytest.mark.asyncio
async def test_tenant_context_blocks_cross_tenant_resume() -> None:
    service = WorkflowService()
    paused = await service.start(
        RunRequest(
            tenant_id="brand-a",
            query="Review tenant-specific pricing",
            sources=["pricing"],
            require_review=True,
        )
    )

    with pytest.raises(TenantAccessError):
        await service.resume(
            paused.run_id,
            ResumeRequest(tenant_id="brand-b", approved=True),
        )


class FlakyEvidenceTool(DeterministicEvidenceTool):
    def __init__(self) -> None:
        self.attempts = 0

    def collect(self, *, tenant_id, query, sources):
        self.attempts += 1
        if self.attempts == 1:
            raise TransientCollectionError("temporary upstream failure")
        return super().collect(tenant_id=tenant_id, query=query, sources=sources)


@pytest.mark.asyncio
async def test_collection_node_retries_transient_failure() -> None:
    tool = FlakyEvidenceTool()
    service = WorkflowService(build_graph(tool=tool))

    response = await service.start(
        RunRequest(
            tenant_id="brand-a",
            query="Collect resilient evidence",
            sources=["catalog", "marketplace"],
        )
    )

    assert response.status == "completed"
    assert tool.attempts == 2
