"""Epic 4 anonymization pipeline package.

The reusable orchestrator that ties Epic 2 detection + Epic 3 substitution/store
into one programmatically-callable flow (inbound pseudonymize / outbound
de-pseudonymize), consumed by the chat endpoint and later epics.
"""

from __future__ import annotations

from .anonymization_pipeline import AnonymizationPipeline, Replacement, get_pipeline

__all__ = ["AnonymizationPipeline", "Replacement", "get_pipeline"]
