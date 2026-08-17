from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, interrupt

from resilient_agent.models import WorkflowState
from resilient_agent.tools import DeterministicEvidenceTool, EvidenceTool, TransientCollectionError


def build_graph(
    tool: EvidenceTool | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    evidence_tool = tool or DeterministicEvidenceTool()

    def collect(state: WorkflowState) -> WorkflowState:
        evidence = evidence_tool.collect(
            tenant_id=state["tenant_id"],
            query=state["query"],
            sources=state["sources"],
        )
        return {"evidence": evidence, "status": "collecting"}

    def normalize(state: WorkflowState) -> WorkflowState:
        normalized = [
            {"source": item["source"].strip(), "content": " ".join(item["content"].split())}
            for item in state["evidence"]
            if item["content"].strip()
        ]
        return {"normalized_evidence": normalized, "status": "normalizing"}

    def analyze(state: WorkflowState) -> WorkflowState:
        evidence = state["normalized_evidence"]
        source_count = len({item["source"] for item in evidence})
        confidence = min(0.99, 0.55 + source_count * 0.15)
        insights = [f"{item['source']}: {item['content'][:120]}" for item in evidence]
        return {
            "insights": insights,
            "confidence": confidence,
            "status": "analyzing",
        }

    def review(state: WorkflowState) -> WorkflowState:
        decision = interrupt(
            {
                "type": "human_review",
                "run_id": state["run_id"],
                "confidence": state["confidence"],
                "insights": state["insights"],
            }
        )
        approved = bool(decision.get("approved", False))
        return {
            "approved": approved,
            "review_feedback": str(decision.get("feedback", "")),
            "status": "reviewed" if approved else "rejected",
        }

    def report(state: WorkflowState) -> WorkflowState:
        evidence_lines = "\n".join(f"- {insight}" for insight in state["insights"])
        report_text = (
            f"# Evidence Report\n\n"
            f"Query: {state['query']}\n\n"
            f"Confidence: {state['confidence']:.2f}\n\n"
            f"## Findings\n{evidence_lines}\n"
        )
        return {"report": report_text, "status": "completed"}

    def route_after_analysis(state: WorkflowState) -> str:
        return "review" if state["require_review"] or state["confidence"] < 0.75 else "report"

    def route_after_review(state: WorkflowState) -> str:
        return "report" if state["approved"] else END

    graph = StateGraph(WorkflowState)
    graph.add_node(
        "collect",
        collect,
        retry_policy=RetryPolicy(max_attempts=3, retry_on=TransientCollectionError),
    )
    graph.add_node("normalize", normalize)
    graph.add_node("analyze", analyze)
    graph.add_node("review", review)
    graph.add_node("report", report)
    graph.add_edge(START, "collect")
    graph.add_edge("collect", "normalize")
    graph.add_edge("normalize", "analyze")
    graph.add_conditional_edges("analyze", route_after_analysis, ["review", "report"])
    graph.add_conditional_edges("review", route_after_review, ["report", END])
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer or InMemorySaver())
