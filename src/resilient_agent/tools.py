from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from resilient_agent.models import Evidence


class TransientCollectionError(ConnectionError):
    """A retryable failure raised by an evidence adapter."""


class EvidenceTool(Protocol):
    def collect(self, *, tenant_id: str, query: str, sources: Sequence[str]) -> list[Evidence]: ...


class DeterministicEvidenceTool:
    """Offline adapter used by the sample service and tests.

    Replace this boundary with Crawl4AI, an MCP client, RPA, or an internal API.
    The tenant identifier is mandatory so every adapter call keeps isolation context.
    """

    def collect(self, *, tenant_id: str, query: str, sources: Sequence[str]) -> list[Evidence]:
        return [
            {
                "source": source,
                "content": f"[{tenant_id}] Evidence from {source} for: {query}",
            }
            for source in sources
        ]
