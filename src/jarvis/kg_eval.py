#!/usr/bin/env python3
"""
Lightweight offline checks for the knowledge graph retrieval path.

Run:
  python -m jarvis.kg_eval
"""

from __future__ import annotations

import statistics
import time
from typing import List

from jarvis.graph.work_partner import WorkPartner, confidence_from_evidence


CASES = [
    "What is JARVIS built with?",
    "Summarize my tech stack preferences",
    "What commands are available?",
]


def main() -> int:
    partner = WorkPartner()
    if not partner.is_available():
        print(partner.status())
        return 1

    partner.bootstrap_schema()

    latencies: List[float] = []
    confidences: List[float] = []

    for question in CASES:
        t0 = time.perf_counter()
        evidence, timings = partner.hybrid_retrieve(question, top_k=6)
        latencies.append((time.perf_counter() - t0) * 1000)
        confidences.append(confidence_from_evidence(evidence))
        print(f"Q: {question}")
        print(f"  hits={len(evidence)} conf={confidences[-1]:.2f} total_ms={latencies[-1]:.1f} detail={timings}")

    if latencies:
        print(f"\nP95 latency (ms): {statistics.quantiles(latencies, n=20)[18]:.1f}")
    if confidences:
        print(f"Avg confidence: {statistics.mean(confidences):.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
