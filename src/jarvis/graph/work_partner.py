#!/usr/bin/env python3
"""
Knowledge-graph backed work partner (Neo4j + Ollama embeddings).

Design goals:
- Fast hybrid retrieval (graph neighborhood + lexical + vector)
- Grounded answers with explicit citations
- Confidence gating + safe suggested actions (never auto-execute)
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from neo4j import GraphDatabase  # type: ignore
except Exception:  # pragma: no cover - optional dependency at import time
    GraphDatabase = None


OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_EMBED_MODEL = os.environ.get("JARVIS_EMBED_MODEL", "nomic-embed-text")

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")


@dataclass
class EvidenceItem:
    evidence_id: str
    source_id: str
    source_type: str
    chunk_index: int
    text: str
    score: float
    entity_ids: List[str] = field(default_factory=list)
    relation_ids: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None


@dataclass
class SuggestedAction:
    title: str
    command: str
    risk_level: str  # low|medium|high
    why: str
    requires_confirmation: bool = True


@dataclass
class GroundedResponse:
    answer: str
    citations: List[Dict[str, Any]]
    confidence: float
    conflicts: List[str]
    suggested_actions: List[SuggestedAction]
    evidence: List[EvidenceItem]
    timings_ms: Dict[str, float]


class WorkPartner:
    """Neo4j-backed knowledge graph + retrieval."""

    VECTOR_INDEX_NAME = "chunk_embeddings"

    def __init__(
        self,
        uri: str = NEO4J_URI,
        user: str = NEO4J_USER,
        password: str = NEO4J_PASSWORD,
        embed_model: str = DEFAULT_EMBED_MODEL,
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.embed_model = embed_model
        self._driver = None
        self._available = False
        self._last_error: Optional[str] = None
        self._vector_index_ready: Optional[bool] = None
        self._vector_search_disabled_reason: Optional[str] = None

        if GraphDatabase is None:
            self._last_error = "neo4j python driver not installed"
            return

        try:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self._driver.verify_connectivity()
            self._available = True
        except Exception as exc:
            self._last_error = str(exc)
            self._available = False

    def is_available(self) -> bool:
        return bool(self._available and self._driver)

    def status(self) -> str:
        if self.is_available():
            return f"Neo4j online ({self.uri})"
        return f"Neo4j offline: {self._last_error or 'unknown error'}"

    def close(self):
        if self._driver:
            try:
                self._driver.close()
            except Exception:
                pass

    def bootstrap_schema(self) -> None:
        """Create constraints + vector index (Neo5+)."""
        if not self.is_available():
            raise RuntimeError(self.status())

        self._ensure_constraints()
        self._ensure_vector_index_internal()

    def _ensure_constraints(self) -> None:
        stmts = [
            "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT rel_id IF NOT EXISTS FOR ()-[r:RELATES]-() REQUIRE r.id IS UNIQUE",
        ]
        with self._driver.session() as session:
            for stmt in stmts:
                session.run(stmt)

    def _ensure_vector_index_internal(self) -> None:
        """Create vector index if supported by this Neo4j edition."""
        if not self.is_available():
            return
        with self._driver.session() as session:
            # Neo4j versions differ in how indexConfig maps are parsed. Try a few compatible forms.
            candidates = [
                # Neo4j 5.x (map keys are property-key-like identifiers)
                """
                CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
                FOR (c:Chunk) ON (c.embedding)
                OPTIONS {indexConfig: {
                  `vector.dimensions`: 768,
                  `vector.similarity_function`: 'cosine'
                }}
                """,
                # Alternate quoting style some deployments accept
                """
                CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
                FOR (c:Chunk) ON (c.embedding)
                OPTIONS {indexConfig: {
                  vector.dimensions: 768,
                  vector.similarity_function: 'cosine'
                }}
                """,
            ]

            last_exc: Optional[Exception] = None
            for cypher in candidates:
                try:
                    session.run(cypher)
                    self._vector_index_ready = True
                    self._vector_search_disabled_reason = None
                    return
                except Exception as exc:
                    last_exc = exc
                    continue

            self._vector_index_ready = False
            self._vector_search_disabled_reason = f"vector index unavailable: {last_exc}"

    def _vector_index_exists(self) -> bool:
        if not self.is_available():
            return False
        try:
            with self._driver.session() as session:
                res = session.run(
                    "SHOW INDEXES YIELD name WHERE name = $name RETURN name LIMIT 1",
                    name=self.VECTOR_INDEX_NAME,
                )
                return res.peek() is not None
        except Exception:
            return False

    def ensure_vector_index(self) -> None:
        """Best-effort: create vector index if missing."""
        if not self.is_available():
            return
        if self._vector_index_ready is True and self._vector_index_exists():
            return
        if self._vector_index_exists():
            self._vector_index_ready = True
            self._vector_search_disabled_reason = None
            return
        # Try creating constraints + vector index (idempotent)
        try:
            self._ensure_constraints()
            self._ensure_vector_index_internal()
        except Exception:
            pass

    # --- Embeddings (Ollama) ---

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            try:
                vectors.append(self._embed_one(text))
            except (urllib.error.URLError, TimeoutError, ValueError, urllib.error.HTTPError) as exc:
                raise RuntimeError(f"Embedding failed ({self.embed_model}): {exc}") from exc
        return vectors

    def _embed_one(self, text: str) -> List[float]:
        """Support both Ollama embedding endpoints across versions."""
        # Legacy endpoint (works on older Ollama)
        legacy_payload = {"model": self.embed_model, "prompt": text}
        try:
            obj = self._post_json("/api/embeddings", legacy_payload)
            vec = obj.get("embedding")
            if isinstance(vec, list):
                return vec
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise

        # New endpoint (Ollama recent builds)
        new_payload = {"model": self.embed_model, "input": text}
        obj = self._post_json("/api/embed", new_payload)
        embeddings = obj.get("embeddings")
        if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
            return embeddings[0]

        vec = obj.get("embedding")
        if isinstance(vec, list):
            return vec

        raise ValueError("missing embedding in Ollama response")

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            OLLAMA_HOST + path,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # --- Ingestion ---

    def index_document_from_text(
        self,
        source_id: str,
        text: str,
        source_type: str = "doc",
        chunks: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        if not self.is_available():
            raise RuntimeError(self.status())

        if chunks is None:
            chunks = _chunk_words(text, chunk_size=120)

        embeddings = self.embed_texts(chunks)
        now = datetime.now(timezone.utc).isoformat()

        with self._driver.session() as session:
            session.run(
                """
                MERGE (s:Source {id: $source_id})
                ON CREATE SET s.created_at = datetime($now)
                SET s.source_type = $source_type,
                    s.updated_at = datetime($now)
                """,
                source_id=source_id,
                source_type=source_type,
                now=now,
            )

            triples = _extract_triples(text)
            for subj, rel, obj in triples:
                e1 = _stable_id("ent", subj)
                e2 = _stable_id("ent", obj)
                rid = _stable_id("rel", subj, rel, obj)
                session.run(
                    """
                    MERGE (a:Entity {id: $e1})
                    SET a.name = $subj, a.kind = 'auto'
                    MERGE (b:Entity {id: $e2})
                    SET b.name = $obj, b.kind = 'auto'
                    MERGE (a)-[r:RELATES {id: $rid}]->(b)
                    ON CREATE SET r.created_at = datetime($now)
                    SET r.type = $rel,
                        r.updated_at = datetime($now)
                    """,
                    e1=e1,
                    e2=e2,
                    rid=rid,
                    subj=subj,
                    obj=obj,
                    rel=rel,
                    now=now,
                )

            for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                chunk_id = _stable_id("chunk", source_id, str(idx), chunk[:64])
                ev_id = f"E{chunk_id}"
                session.run(
                    """
                    MATCH (s:Source {id: $source_id})
                    MERGE (c:Chunk {id: $chunk_id})
                    ON CREATE SET c.created_at = datetime($now)
                    SET c.text = $text,
                        c.chunk_index = $index,
                        c.embedding = $emb,
                        c.updated_at = datetime($now)
                    MERGE (c)-[:FROM_SOURCE]->(s)
                    WITH c
                    UNWIND $mentions AS mention
                    MERGE (e:Entity {id: mention.id})
                    ON CREATE SET e.created_at = datetime($now)
                    SET e.name = mention.name,
                        e.kind = coalesce(e.kind, 'mention'),
                        e.updated_at = datetime($now)
                    MERGE (c)-[:MENTIONS]->(e)
                    """,
                    source_id=source_id,
                    chunk_id=chunk_id,
                    text=chunk,
                    index=idx,
                    emb=emb,
                    mentions=_mention_nodes(chunk),
                    now=now,
                )

        return {"source_id": source_id, "chunks": len(chunks)}

    # --- Retrieval ---

    def hybrid_retrieve(
        self,
        question: str,
        top_k: int = 8,
        graph_limit: int = 12,
    ) -> Tuple[List[EvidenceItem], Dict[str, float]]:
        if not self.is_available():
            raise RuntimeError(self.status())

        # Ensure schema objects exist before vector queries (first-run friendly).
        self.ensure_vector_index()

        t0 = time.perf_counter()
        q_emb = self.embed_texts([question])[0]
        t_embed = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        graph_hits = self._graph_neighborhood(question, limit=graph_limit)
        t_graph = (time.perf_counter() - t1) * 1000

        t2 = time.perf_counter()
        vector_hits: List[EvidenceItem] = []
        if self._vector_index_ready is not False and self._vector_index_exists():
            vector_hits = self._vector_search(q_emb, limit=max(20, top_k * 4))
        t_vec = (time.perf_counter() - t2) * 1000

        t3 = time.perf_counter()
        lexical_hits = self._lexical_search(question, limit=max(20, top_k * 4))
        t_lex = (time.perf_counter() - t3) * 1000

        merged = _merge_hits(graph_hits, vector_hits, lexical_hits, top_k=top_k)
        merged = assign_simple_evidence_ids(merged)
        t_merge = (time.perf_counter() - t3) * 1000

        timings = {
            "embed_ms": round(t_embed, 2),
            "graph_ms": round(t_graph, 2),
            "vector_ms": round(t_vec, 2),
            "lexical_ms": round(t_lex, 2),
            "merge_ms": round(t_merge, 2),
        }
        if self._vector_search_disabled_reason:
            timings["vector_note"] = self._vector_search_disabled_reason
        return merged, timings

    def _graph_neighborhood(self, question: str, limit: int) -> List[EvidenceItem]:
        tokens = [t for t in re.findall(r"[A-Za-z0-9_]{3,}", question.lower())]
        if not tokens:
            return []

        cypher = """
        UNWIND $tokens AS tok
        MATCH (e:Entity)
        WHERE toLower(e.name) CONTAINS tok
        WITH DISTINCT e
        LIMIT 25
        OPTIONAL MATCH (c:Chunk)-[:MENTIONS]->(e)
        OPTIONAL MATCH (e)-[r:RELATES]-()
        WITH DISTINCT c, collect(DISTINCT elementId(r)) AS relation_ids, collect(DISTINCT e.id) AS entity_ids
        WHERE c IS NOT NULL
        RETURN DISTINCT c.id AS chunk_id,
               coalesce(c.text, '') AS text,
               toInteger(coalesce(c.chunk_index, 0)) AS idx,
               head([(c)-[:FROM_SOURCE]->(s) | s.id]) AS source_id,
               head([(c)-[:FROM_SOURCE]->(s) | coalesce(s.source_type, 'doc')]) AS source_type,
               entity_ids,
               relation_ids
        LIMIT $limit
        """
        items: List[EvidenceItem] = []
        with self._driver.session() as session:
            res = session.run(cypher, tokens=tokens, limit=limit)
            for record in res:
                items.append(
                    EvidenceItem(
                        evidence_id=f"E{record['chunk_id']}",
                        source_id=record["source_id"] or "unknown",
                        source_type=record["source_type"] or "doc",
                        chunk_index=int(record["idx"] or 0),
                        text=record["text"] or "",
                        score=0.55,
                        entity_ids=list(record["entity_ids"] or []),
                        relation_ids=list(record["relation_ids"] or []),
                    )
                )
        return items

    def _vector_search(self, embedding: Sequence[float], limit: int) -> List[EvidenceItem]:
        cypher = """
        CALL db.index.vector.queryNodes('chunk_embeddings', $k, $embedding)
        YIELD node, score
        OPTIONAL MATCH (node)-[:FROM_SOURCE]->(s:Source)
        OPTIONAL MATCH (node)-[:MENTIONS]->(e:Entity)
        WITH node, score, s, collect(DISTINCT e.id) AS ents
        RETURN node.id AS chunk_id,
               coalesce(node.text, '') AS text,
               toInteger(coalesce(node.chunk_index, 0)) AS idx,
               coalesce(s.id, 'unknown') AS source_id,
               coalesce(s.source_type, 'doc') AS source_type,
               score AS vec_score,
               ents AS entity_ids
        """
        items: List[EvidenceItem] = []
        try:
            with self._driver.session() as session:
                res = session.run(cypher, k=limit, embedding=list(embedding))
                for record in res:
                    vec_score = float(record["vec_score"] or 0.0)
                    items.append(
                        EvidenceItem(
                            evidence_id=f"E{record['chunk_id']}",
                            source_id=record["source_id"] or "unknown",
                            source_type=record["source_type"] or "doc",
                            chunk_index=int(record["idx"] or 0),
                            text=record["text"] or "",
                            score=_clamp(vec_score, 0.0, 1.0),
                            entity_ids=list(record["entity_ids"] or []),
                        )
                    )
        except Exception as exc:
            # Missing index / unsupported procedure / transient Neo4j issues
            self._vector_index_ready = False
            self._vector_search_disabled_reason = f"vector search disabled: {exc}"
            return []
        return items

    def _lexical_search(self, question: str, limit: int) -> List[EvidenceItem]:
        tokens = [t for t in re.findall(r"[A-Za-z0-9_]{3,}", question.lower())]
        if not tokens:
            return []

        cypher = """
        UNWIND $tokens AS tok
        MATCH (c:Chunk)
        WHERE toLower(coalesce(c.text, '')) CONTAINS tok
        WITH c, count(*) AS hits
        ORDER BY hits DESC
        LIMIT $limit
        OPTIONAL MATCH (c)-[:FROM_SOURCE]->(s:Source)
        WITH c, hits, s
        RETURN c.id AS chunk_id,
               coalesce(c.text, '') AS text,
               toInteger(coalesce(c.chunk_index, 0)) AS idx,
               coalesce(s.id, 'unknown') AS source_id,
               coalesce(s.source_type, 'doc') AS source_type,
               hits
        """
        items: List[EvidenceItem] = []
        with self._driver.session() as session:
            res = session.run(cypher, tokens=tokens, limit=limit)
            for record in res:
                hits = int(record["hits"] or 0)
                score = _clamp(math.log1p(hits) / 5.0, 0.0, 1.0)
                items.append(
                    EvidenceItem(
                        evidence_id=f"E{record['chunk_id']}",
                        source_id=record["source_id"] or "unknown",
                        source_type=record["source_type"] or "doc",
                        chunk_index=int(record["idx"] or 0),
                        text=record["text"] or "",
                        score=score,
                    )
                )
        return items


def assign_simple_evidence_ids(evidence: Sequence[EvidenceItem]) -> List[EvidenceItem]:
    """Renumber evidence IDs to E1..En for human-friendly citations."""
    out: List[EvidenceItem] = []
    for i, ev in enumerate(evidence, 1):
        out.append(
            EvidenceItem(
                evidence_id=f"E{i}",
                source_id=ev.source_id,
                source_type=ev.source_type,
                chunk_index=ev.chunk_index,
                text=ev.text,
                score=ev.score,
                entity_ids=list(ev.entity_ids),
                relation_ids=list(ev.relation_ids),
                timestamp=ev.timestamp,
            )
        )
    return out


def build_grounded_prompt(question: str, evidence: Sequence[EvidenceItem]) -> str:
    lines = [
        "You are JARVIS, a grounded work partner.",
        "Rules:",
        "- Use ONLY the evidence blocks below for factual claims.",
        "- If evidence is insufficient, say you do not have enough information and ask a clarifying question.",
        "- Every factual sentence must end with a bracket citation like [E1] matching Evidence IDs.",
        "- Do not invent entities, numbers, dates, or commands not supported by evidence.",
        "- Do NOT output 'execute_command:' lines. Evidence already contains the text you need.",
        "- Do NOT echo the evidence header lines (the lines that look like: [E1] source=...).",
        "- Do NOT invent extra citation tags beyond the evidence IDs provided.",
        "- Do NOT open with time-of-day salutations (Good morning / afternoon / evening); answer the question directly.",
        "",
        f"User question: {question}",
        "",
        "Evidence:",
    ]
    for ev in evidence:
        lines.append(f"[{ev.evidence_id}] source={ev.source_id} type={ev.source_type} idx={ev.chunk_index}")
        lines.append(ev.text.strip())
        lines.append("")
    lines.append("Answer:")
    return "\n".join(lines)


def confidence_from_evidence(evidence: Sequence[EvidenceItem]) -> float:
    if not evidence:
        return 0.0
    top = sorted((e.score for e in evidence), reverse=True)[:3]
    base = sum(top) / len(top)
    diversity = min(1.0, len({e.source_id for e in evidence}) / 3.0)
    return _clamp(0.65 * base + 0.35 * diversity, 0.0, 1.0)


def detect_conflicts(evidence: Sequence[EvidenceItem]) -> List[str]:
    """Very lightweight contradiction heuristic for Phase-1."""
    lowered = [e.text.lower() for e in evidence]
    conflicts: List[str] = []
    pairs = [
        ("not ", " is "),
        ("won't", "will"),
        ("cannot", "can "),
    ]
    for a, b in pairs:
        hits_a = sum(1 for t in lowered if a in t)
        hits_b = sum(1 for t in lowered if b in t)
        if hits_a and hits_b:
            conflicts.append(f"Possible conflict: mixed signals around '{a.strip()}' vs '{b.strip()}' in evidence.")
    return conflicts


def suggest_actions(question: str, evidence: Sequence[EvidenceItem]) -> List[SuggestedAction]:
    """Evidence-bounded suggestions (never auto-run)."""
    q = question.lower()
    actions: List[SuggestedAction] = []

    if "docker" in q:
        actions.append(
            SuggestedAction(
                title="List containers (read-only)",
                command="docker ps -a",
                risk_level="low",
                why="Docker appears relevant; confirm live container state from the daemon.",
            )
        )
    if any("cpu" in e.text.lower() for e in evidence) or "cpu" in q:
        actions.append(
            SuggestedAction(
                title="Sample CPU snapshot",
                command="top -l 1 -n 0 | grep 'CPU usage'",
                risk_level="low",
                why="CPU context detected in evidence or question.",
            )
        )
    if "disk" in q or any("disk" in e.text.lower() for e in evidence):
        actions.append(
            SuggestedAction(
                title="Check disk usage",
                command="df -h /",
                risk_level="low",
                why="Disk context detected in evidence or question.",
            )
        )

    # Cap suggestions
    return actions[:3]


def run_grounded_answer(
    brain,
    question: str,
    evidence: Sequence[EvidenceItem],
    stream: bool = False,
    cwd: Optional[str] = None,
) -> str:
    conf = confidence_from_evidence(evidence)
    conflicts = detect_conflicts(evidence)
    prompt = build_grounded_prompt(question, evidence)

    if conf < 0.35:
        msg = (
            "I do not have enough grounded evidence to answer confidently, sir.\n"
            "Try: ingest a doc, or ask a narrower question, or run a read-only command and pipe it to analysis."
        )
        if conflicts:
            msg += "\nAlso: " + " ".join(conflicts)
        return msg

    if stream:
        return brain.think_stream(prompt, cwd=cwd)
    return brain.think(prompt, cwd=cwd)


def _chunk_words(text: str, chunk_size: int = 120) -> List[str]:
    words = text.split()
    chunks: List[str] = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i : i + chunk_size]))
    return chunks or [text]


def _stable_id(prefix: str, *parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", errors="ignore"))
        h.update(b"|")
    return f"{prefix}_{h.hexdigest()[:16]}"


def _mention_nodes(text: str) -> List[Dict[str, str]]:
    caps = re.findall(r"\b([A-Z][a-zA-Z0-9]{2,})\b", text)
    mentions = []
    for name in sorted(set(caps)):
        mentions.append({"id": _stable_id("ent", name), "name": name})
    return mentions[:25]


_TRIPLE_RE = re.compile(
    r"(?P<a>[A-Za-z0-9][A-Za-z0-9 _]{1,40}?)\s+(?P<rel>uses|built with|depends on|owns|works on|runs on)\s+(?P<b>[A-Za-z0-9][A-Za-z0-9 _]{1,40}?)(?:[.\n]|$)",
    re.IGNORECASE,
)


def _extract_triples(text: str) -> List[Tuple[str, str, str]]:
    triples: List[Tuple[str, str, str]] = []
    for match in _TRIPLE_RE.finditer(text):
        a = match.group("a").strip()
        rel = match.group("rel").strip().lower().replace(" ", "_")
        b = match.group("b").strip()
        if a and b:
            triples.append((a, rel, b))
    return triples[:50]


def _merge_hits(
    graph_hits: Sequence[EvidenceItem],
    vector_hits: Sequence[EvidenceItem],
    lexical_hits: Sequence[EvidenceItem],
    top_k: int,
) -> List[EvidenceItem]:
    scores: Dict[str, float] = {}
    items: Dict[str, EvidenceItem] = {}

    def add(hit: EvidenceItem, weight: float):
        key = hit.evidence_id
        score = _clamp(hit.score * weight, 0.0, 1.0)
        if key not in scores or score > scores[key]:
            scores[key] = score
            hit.score = score
            items[key] = hit

    for h in graph_hits:
        add(h, 1.15)
    for h in vector_hits:
        add(h, 1.0)
    for h in lexical_hits:
        add(h, 0.85)

    ordered = sorted(items.values(), key=lambda e: e.score, reverse=True)
    return ordered[:top_k]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def bootstrap_cli() -> int:
    """CLI helper: python -m work_partner bootstrap"""
    partner = WorkPartner()
    partner.bootstrap_schema()
    print(partner.status())
    return 0


if __name__ == "__main__":
    raise SystemExit(bootstrap_cli())
