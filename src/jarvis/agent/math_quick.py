"""Deterministic arithmetic for agent + tools (no LLM)."""

from __future__ import annotations

import ast
import re
from typing import Optional

_MATH_CHARS_ONLY = re.compile(r"^[0-9+\-*/().\s]+$")
_ARITH_PREFIX = re.compile(
    r"(?i)^(?:sum|calculate|compute)\s+(.+)$",
)
_WHAT_IS = re.compile(r"(?i)^what\s+is\s+(.+)$")
_HOW_MUCH = re.compile(r"(?i)^how\s+much\s+is\s+(.+)$")


def _is_plain_arithmetic_fragment(s: str) -> bool:
    t = (s or "").strip().rstrip("=").strip()
    if len(t) < 1:
        return False
    return bool(_MATH_CHARS_ONLY.fullmatch(t))


def _safe_ast_eval(expr: str) -> float:
    tree = ast.parse(expr, mode="eval")

    def eval_node(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return eval_node(node.body)
        if isinstance(node, ast.Constant):
            v = node.value
            if isinstance(v, bool) or v is None:
                raise ValueError("disallowed constant")
            if isinstance(v, (int, float)):
                return float(v)
            raise ValueError("disallowed constant type")
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.UAdd):
                return +eval_node(node.operand)
            if isinstance(node.op, ast.USub):
                return -eval_node(node.operand)
            raise ValueError("disallowed unary op")
        if isinstance(node, ast.BinOp):
            left = eval_node(node.left)
            right = eval_node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
            if isinstance(node.op, ast.Mod):
                return left % right
            if isinstance(node.op, ast.Pow):
                if abs(right) > 64:
                    raise ValueError("exponent too large")
                return left ** right
            raise ValueError("disallowed binary op")
        raise ValueError("disallowed syntax")

    return eval_node(tree)


def try_answer_arithmetic(text: str) -> Optional[str]:
    """If input is a simple arithmetic request, return a short answer; else None."""
    raw = (text or "").strip()
    if not raw:
        return None

    expr = None
    m = _ARITH_PREFIX.match(raw)
    if m:
        expr = m.group(1).strip().rstrip("=").strip()
    if expr is None:
        m = _WHAT_IS.match(raw)
        if m and _is_plain_arithmetic_fragment(m.group(1)):
            expr = m.group(1).strip().rstrip("=").strip()
    if expr is None:
        m = _HOW_MUCH.match(raw)
        if m and _is_plain_arithmetic_fragment(m.group(1)):
            expr = m.group(1).strip().rstrip("=").strip()
    if expr is None and _is_plain_arithmetic_fragment(raw):
        expr = raw.rstrip("=").strip()

    if not expr:
        return None

    expr = expr.replace("×", "*").replace("÷", "/")
    if not _is_plain_arithmetic_fragment(expr):
        return None

    try:
        val = _safe_ast_eval(expr)
    except Exception:
        return None

    if val != val:
        return None
    if abs(val) > 1e15:
        return None

    if abs(val - round(val)) < 1e-9:
        out = str(int(round(val)))
    else:
        out = f"{val:.12g}"
    return f"{out}, sir."


def calculator_tool_expr(expr: str) -> str:
    """Tool entry: evaluate a plain arithmetic expr string."""
    e = (expr or "").strip().replace("×", "*").replace("÷", "/")
    if not _is_plain_arithmetic_fragment(e):
        return "Error: expression must use only digits and + - * / ( ) ."
    try:
        val = _safe_ast_eval(e)
    except Exception as exc:
        return f"Error: {exc}"
    if abs(val - round(val)) < 1e-9:
        return str(int(round(val)))
    return f"{val:.12g}"
