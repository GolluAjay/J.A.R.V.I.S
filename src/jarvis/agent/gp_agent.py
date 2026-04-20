#!/usr/bin/env python3
"""
JARVIS General-Purpose Agent
Combines the brain, orchestrator, and skills into a single user-facing agent.
"""

import re
import shlex
import os
import time
from datetime import datetime
from typing import Optional, Tuple

from jarvis.llm import JARVISBrain
from jarvis.retrieval import maybe_expand_query_for_retrieval
from jarvis.core.settings import get_settings
from jarvis.runtime import Orchestrator, SkillsManager
from jarvis.tools import execute_tool_json

from .grounding import answer_covers_evidence_ids, append_citation_retry_instruction
from .math_quick import try_answer_arithmetic
from jarvis.graph.work_partner import (
    WorkPartner,
    build_grounded_prompt,
    confidence_from_evidence,
    detect_conflicts,
    suggest_actions,
)

TOOL_COMMAND_PATTERN = re.compile(r'execute_command:\s*(.+)', re.IGNORECASE)

USER_PREFERENCES_FILENAME = "user_preferences.txt"

_MEMORY_PATTERNS = (
    re.compile(r"^remember\s+(?:that\s+)?(.+)$", re.I),
    re.compile(r"^please\s+remember\s+(?:that\s+)?(.+)$", re.I),
    re.compile(r"^don'?t\s+forget\s+(?:that\s+)?(.+)$", re.I),
    re.compile(r"^save\s+this:?\s*(.+)$", re.I),
    re.compile(r"^note\s+to\s+self:?\s*(.+)$", re.I),
)


def extract_user_memory_fact(text: str) -> Optional[str]:
    """If the user is asking JARVIS to store a personal fact, return the fact string."""
    t = (text or "").strip()
    if len(t) < 8:
        return None
    for pat in _MEMORY_PATTERNS:
        m = pat.match(t)
        if m:
            fact = (m.group(1) or "").strip()
            if fact:
                return fact
    return None


def _strip_execute_commands(text: str) -> str:
    """Remove accidental tool protocol lines from model output."""
    if not text:
        return text
    cleaned = []
    for line in str(text).splitlines():
        if line.strip().lower().startswith("execute_command:"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


class GeneralPurposeAgent:
    def __init__(self, brain=None, orchestrator=None, skills=None, work_partner=None):
        self.brain = brain if brain else JARVISBrain()
        self.orchestrator = orchestrator if orchestrator else Orchestrator()
        self.skills = skills if skills else SkillsManager()
        self.work_partner = work_partner if work_partner else WorkPartner()
        self._kg_bootstrapped = False
        self._last_memory_write_ms = 0.0

    def _persist_user_memory_fact(self, raw_input: str, fact: str) -> Tuple[str, Optional[str]]:
        """Append to knowledge/user_preferences.txt and re-index for retrieval. Returns (reply, error)."""
        _t0 = time.perf_counter()
        from jarvis.core.paths import knowledge_dir as _knowledge_dir

        knowledge_dir = str(_knowledge_dir())
        os.makedirs(knowledge_dir, exist_ok=True)
        path = os.path.join(knowledge_dir, USER_PREFERENCES_FILENAME)
        stamp = datetime.now().isoformat(timespec="seconds")
        line = f"- {stamp}: {fact}\n"

        existing = ""
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                existing = handle.read()
        if not existing.strip():
            existing = (
                "## User-stated preferences\n"
                "(Saved when you say things like \"remember that ...\")\n\n"
            )
        new_content = existing + line
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(new_content)
        except OSError as exc:
            return (
                f"I could not write your preference to disk, sir: {exc}",
                str(exc),
            )

        index_note = None
        try:
            from jarvis.rag import KnowledgeBase

            kb = KnowledgeBase(
                knowledge_dir=knowledge_dir,
                work_partner=self.work_partner if self.work_partner.is_available() else None,
            )
            kb.add_document(USER_PREFERENCES_FILENAME, content=new_content)
        except Exception as exc:  # pragma: no cover - optional Neo4j / embeddings
            index_note = str(exc)

        reply = (
            f"Understood, sir. I've recorded: {fact}\n"
            "I'll treat this as a durable preference for future grounded answers."
        )
        if index_note:
            reply += f"\n(Local file saved; knowledge graph refresh reported: {index_note})"
        self._last_memory_write_ms = round((time.perf_counter() - _t0) * 1000.0, 2)
        return reply, index_note

    def _ensure_kg(self):
        if self._kg_bootstrapped:
            return
        if self.work_partner.is_available():
            try:
                self.work_partner.bootstrap_schema()
                self._kg_bootstrapped = True
            except Exception:
                # Schema creation is best-effort; queries will surface errors if needed.
                self._kg_bootstrapped = False

    def _extract_tool_commands(self, text):
        """Extract tool command directives from model output."""
        return TOOL_COMMAND_PATTERN.findall(text or "")

    def _run_tool_command(self, command, cwd=None):
        """Run a shell command via the orchestrator and return the output."""
        if not command:
            return "No command to execute."

        if cwd:
            self.orchestrator.set_cwd(cwd)

        return self.orchestrator.run_cmd(command.strip())

    def _process_tool_loop(self, user_input, cwd=None, max_iterations=2):
        """Run the brain and execute any tool commands it returns."""
        context = None
        for iteration in range(max_iterations):
            response = self.brain.think(user_input, context=context, cwd=cwd)
            commands = self._extract_tool_commands(response)
            if not commands:
                return response

            outputs = []
            for command in commands:
                output = self._run_tool_command(command, cwd=cwd)
                outputs.append(f"Command: {command}\nResult:\n{output}")

            context = "\n".join(outputs)

        return response

    def process(self, user_input, cwd=None):
        """Process a user request using skills, orchestrator, or the brain."""
        user_input = user_input.strip()
        if not user_input:
            return "Please say something, sir."

        # Direct skill execution
        skill_name = self.skills.match_skill(user_input)
        if skill_name:
            parts = user_input.split(None, 1)
            args = [parts[1]] if len(parts) > 1 else []
            result = self.skills.execute(skill_name, *args)
            self.brain.remember('user', user_input)
            self.brain.remember('assistant', result)
            return result

        mem_fact = extract_user_memory_fact(user_input)
        if mem_fact:
            reply, _err = self._persist_user_memory_fact(user_input, mem_fact)
            self.brain.remember("user", user_input)
            self.brain.remember("assistant", reply)
            return reply

        tool_out = execute_tool_json(user_input)
        if tool_out is not None:
            self.brain.remember("user", user_input)
            self.brain.remember("assistant", tool_out)
            return tool_out

        arith = try_answer_arithmetic(user_input)
        if arith is not None:
            self.brain.remember("user", user_input)
            self.brain.remember("assistant", arith)
            return arith

        intent = self.brain.detect_intent(user_input)

        # If the user asked for a command/action, try orchestrator first
        if intent in ('command', 'action'):
            result = self.orchestrator.process_command(user_input)
            if result is not None:
                self.brain.remember('user', user_input)
                self.brain.remember('assistant', result)
                return result

        # Fallback to brain with optional tool execution loop
        response = self._process_tool_loop(user_input, cwd=cwd)
        self.brain.remember('user', user_input)
        self.brain.remember('assistant', response)
        return response

    def process_grounded(self, user_input, cwd=None, stream=False, force_retrieval=False):
        """Grounded path: hybrid retrieval + citation-aware generation + safe actions."""
        user_input = user_input.strip()
        if not user_input:
            return {
                "answer": "Please say something, sir.",
                "citations": [],
                "confidence": 0.0,
                "conflicts": [],
                "suggested_actions": [],
                "evidence": [],
                "timings_ms": {},
            }

        skill_name = self.skills.match_skill(user_input)
        if skill_name:
            parts = user_input.split(None, 1)
            args = [parts[1]] if len(parts) > 1 else []
            result = self.skills.execute(skill_name, *args)
            self.brain.remember("user", user_input)
            self.brain.remember("assistant", result)
            return {
                "answer": str(result),
                "citations": [],
                "confidence": 1.0,
                "conflicts": [],
                "suggested_actions": [],
                "evidence": [],
                "timings_ms": {},
            }

        mem_fact = extract_user_memory_fact(user_input)
        if mem_fact:
            reply, _err = self._persist_user_memory_fact(user_input, mem_fact)
            self.brain.remember("user", user_input)
            self.brain.remember("assistant", reply)
            return {
                "answer": reply,
                "citations": [
                    {
                        "id": "M1",
                        "source": USER_PREFERENCES_FILENAME,
                        "chunk": 0,
                        "score": 1.0,
                    }
                ],
                "confidence": 1.0,
                "conflicts": [],
                "suggested_actions": [],
                "evidence": [],
                "timings_ms": {"memory_write_ms": getattr(self, "_last_memory_write_ms", 0.0)},
            }

        tool_out = execute_tool_json(user_input)
        if tool_out is not None:
            self.brain.remember("user", user_input)
            self.brain.remember("assistant", tool_out)
            return {
                "answer": tool_out,
                "citations": [],
                "confidence": 1.0,
                "conflicts": [],
                "suggested_actions": [],
                "evidence": [],
                "timings_ms": {},
            }

        t_arith = time.perf_counter()
        arith = try_answer_arithmetic(user_input)
        if arith is not None:
            self.brain.remember("user", user_input)
            self.brain.remember("assistant", arith)
            return {
                "answer": arith,
                "citations": [],
                "confidence": 1.0,
                "conflicts": [],
                "suggested_actions": [],
                "evidence": [],
                "timings_ms": {
                    "arithmetic_ms": round((time.perf_counter() - t_arith) * 1000.0, 3),
                },
            }

        intent = self.brain.detect_intent(user_input)
        use_retrieval = force_retrieval or intent in ("query", "chat")

        if intent in ("command", "action"):
            result = self.orchestrator.process_command(user_input)
            if result is not None:
                self.brain.remember("user", user_input)
                self.brain.remember("assistant", str(result))
                return {
                    "answer": str(result),
                    "citations": [],
                    "confidence": 0.9 if result else 0.2,
                    "conflicts": [],
                    "suggested_actions": [],
                    "evidence": [],
                    "timings_ms": {},
                }

        if not self.work_partner.is_available() or not use_retrieval:
            response = self._process_tool_loop(user_input, cwd=cwd)
            self.brain.remember("user", user_input)
            self.brain.remember("assistant", response)
            return {
                "answer": response,
                "citations": [],
                "confidence": 0.55,
                "conflicts": [],
                "suggested_actions": suggest_actions(user_input, []),
                "evidence": [],
                "timings_ms": {},
            }

        self._ensure_kg()
        settings = get_settings()
        t_expand = time.perf_counter()
        retrieve_query = maybe_expand_query_for_retrieval(
            user_input, settings.retrieval_query_expand
        )
        timings_pre: dict = {
            "query_expand_ms": round((time.perf_counter() - t_expand) * 1000.0, 2),
        }
        if retrieve_query.strip() != user_input.strip():
            timings_pre["retrieval_query"] = retrieve_query

        evidence, timings = self.work_partner.hybrid_retrieve(retrieve_query, top_k=8)
        timings = {**timings_pre, **timings}
        conf = confidence_from_evidence(evidence)
        conflicts = detect_conflicts(evidence)
        actions = suggest_actions(user_input, evidence)

        if conf < 0.35:
            answer = (
                "Insufficient grounded evidence in the knowledge graph, sir.\n"
                "Ingest documents with `ingest <path>` or ask a narrower question."
            )
            if conflicts:
                answer += "\nPotential conflicts in existing evidence:\n- " + "\n- ".join(conflicts)
            self.brain.remember("user", user_input)
            self.brain.remember("assistant", answer)
            return {
                "answer": answer,
                "citations": [],
                "confidence": conf,
                "conflicts": conflicts,
                "suggested_actions": actions,
                "evidence": evidence,
                "timings_ms": timings,
            }

        prompt = build_grounded_prompt(user_input, evidence)
        if stream:
            answer = self.brain.think_stream(prompt, cwd=cwd, enable_tools=False, memory_user_text=user_input)
        else:
            answer = self.brain.think(prompt, cwd=cwd, enable_tools=False, memory_user_text=user_input)
            answer = _strip_execute_commands(answer)
            if (
                settings.grounded_reflect_retry
                and evidence
                and not answer_covers_evidence_ids(answer, evidence)
            ):
                t_retry = time.perf_counter()
                retry_prompt = append_citation_retry_instruction(prompt)
                answer = self.brain.think(
                    retry_prompt, cwd=cwd, enable_tools=False, memory_user_text=user_input
                )
                answer = _strip_execute_commands(answer)
                timings["reflect_retry_ms"] = round((time.perf_counter() - t_retry) * 1000.0, 2)
        if stream:
            answer = _strip_execute_commands(answer)

        citations = [
            {
                "id": ev.evidence_id,
                "source": ev.source_id,
                "chunk": ev.chunk_index,
                "score": ev.score,
            }
            for ev in evidence
        ]

        self.brain.remember("user", user_input)
        self.brain.remember("assistant", answer)

        return {
            "answer": answer,
            "citations": citations,
            "confidence": conf,
            "conflicts": conflicts,
            "suggested_actions": actions,
            "evidence": evidence,
            "timings_ms": timings,
        }

    def chat(self, prompt, cwd=None):
        """Simple chat interface using the agent."""
        return self.process(prompt, cwd=cwd)


def test():
    agent = GeneralPurposeAgent()
    print("=== General Purpose Agent Test ===")
    print("1. Query time:", agent.process('What time is it?'))
    print("2. List current directory:", agent.process('ls'))
    print("3. Run a simple skill:", agent.process('time'))


if __name__ == '__main__':
    test()
