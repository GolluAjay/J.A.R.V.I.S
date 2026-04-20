"""Grounded answer quality checks (citation coverage, retry prompt)."""

from __future__ import annotations

from typing import Sequence

from jarvis.graph.work_partner import EvidenceItem


def answer_covers_evidence_ids(answer: str, evidence: Sequence[EvidenceItem]) -> bool:
    """True if at least one retrieved evidence id appears in the answer text."""
    if not evidence:
        return True
    text = answer or ""
    for ev in evidence:
        eid = getattr(ev, "evidence_id", "") or ""
        if eid and eid in text:
            return True
    return False


def append_citation_retry_instruction(base_prompt: str) -> str:
    return (
        base_prompt
        + "\n\nREMINDER: Your last draft did not cite the evidence IDs. "
        "Every factual statement must end with a bracket tag like [E1] or [E2] "
        "matching the Evidence blocks above. If you cannot support a claim, omit it."
    )
