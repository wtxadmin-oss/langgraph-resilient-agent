from __future__ import annotations

from uuid import uuid4

from langgraph.types import Command

from resilient_agent.graph import build_graph
from resilient_agent.models import ResumeRequest, RunRequest, RunResponse, WorkflowState


class RunNotFoundError(LookupError):
    pass


class TenantAccessError(PermissionError):
    pass


class WorkflowService:
    def __init__(self, graph=None):
        self.graph = graph or build_graph()

    @staticmethod
    def _config(run_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": run_id}}

    async def start(self, request: RunRequest) -> RunResponse:
        run_id = uuid4().hex
        initial_state: WorkflowState = {
            "run_id": run_id,
            "tenant_id": request.tenant_id,
            "query": request.query,
            "sources": request.sources,
            "require_review": request.require_review,
            "status": "created",
        }
        result = await self.graph.ainvoke(initial_state, self._config(run_id))
        return self._response(run_id, result)

    async def resume(self, run_id: str, request: ResumeRequest) -> RunResponse:
        state = await self._authorized_state(run_id, request.tenant_id)
        if state.get("status") not in {"analyzing", "reviewed"}:
            raise ValueError("run is not waiting for review")
        result = await self.graph.ainvoke(
            Command(resume={"approved": request.approved, "feedback": request.feedback}),
            self._config(run_id),
        )
        return self._response(run_id, result)

    async def get(self, run_id: str, tenant_id: str) -> RunResponse:
        state = await self._authorized_state(run_id, tenant_id)
        return self._response(run_id, state)

    async def _authorized_state(self, run_id: str, tenant_id: str) -> WorkflowState:
        snapshot = await self.graph.aget_state(self._config(run_id))
        if not snapshot.values:
            raise RunNotFoundError(run_id)
        state = dict(snapshot.values)
        interrupts = tuple(
            interrupt
            for task in snapshot.tasks
            for interrupt in getattr(task, "interrupts", ())
        )
        if interrupts:
            state["__interrupt__"] = interrupts
        if state.get("tenant_id") != tenant_id:
            raise TenantAccessError(run_id)
        return state

    @staticmethod
    def _response(run_id: str, state: WorkflowState) -> RunResponse:
        interrupts = state.get("__interrupt__", ())
        if interrupts:
            interrupt_value = interrupts[0].value
            return RunResponse(
                run_id=run_id,
                status="waiting_for_review",
                confidence=float(state.get("confidence", 0.0)),
                interrupt=interrupt_value,
            )
        status = "rejected" if state.get("status") == "rejected" else "completed"
        return RunResponse(
            run_id=run_id,
            status=status,
            confidence=float(state.get("confidence", 0.0)),
            report=state.get("report"),
        )
