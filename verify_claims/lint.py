"""Advisory checks for claims that may rot as generated data grows.

This is intentionally a report, not a gate. A literal number is not automatically wrong: versions,
protocol constants, historical figures and test expectations can all be stable. The linter only marks
claims whose prose/check look both numeric and data-backed, so a human can decide whether to replace a
pinned value with a relation ("page == data") or a dated snapshot.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

DYNAMIC_VALUE = re.compile(
    r"^\s*(?:~?\d[\d,]*(?:\.\d+)?(?:%|\s*(?:records?|entries|releases?|versions?|papers?|days?|"
    r"tests?|rows?|files?|stars?|repos?|recommendations?|cards?|benchmarks?|models?|harnesses?))|"
    r"\d[\d,]*(?:\.\d+)?\s*/\s*\d[\d,]*)",
    re.I,
)
DYNAMIC_WORDS = re.compile(
    r"\b(?:latest|today|current|generated|snapshot|data|report|statistics?|coverage|updated|"
    r"release|sync|daily|weekly|site|card|README|file|page)\b", re.I)
STABLE_VALUE = re.compile(r"(?:runtime dependencies|subcommands|exit [012]|modes|points|bonus|version)", re.I)
ABSOLUTE_EXPECT = re.compile(r"(?:^|\D)\d[\d,]*(?:\.\d+)?(?:%|\s|$)")
RELATIONAL_WORDS = re.compile(r"\b(?:equals?|match(?:es)?|same|set|sum|recomput|derive|each|every|all|against|from|versus|vs\.?)\b", re.I)
IMMUTABLE_CONTEXT = re.compile(r"\b(?:snapshot|point[- ]in[- ]time|upstream|source|release notes?|technical report|historical|as_of|dated capture|committed capture)\b", re.I)


@dataclass
class Finding:
    claim_id: str
    value: str
    reason: str
    suggestion: str


def _text(claim: dict) -> str:
    check = claim.get("check") or {}
    cmd = check.get("cmd", "")
    if isinstance(cmd, list):
        cmd = " ".join(str(x) for x in cmd)
    return " ".join(str(claim.get(k, "")) for k in ("claim", "value", "metric", "method", "repro") if claim.get(k)) + " " + str(cmd)


def lint(claims: Iterable[dict]) -> list[Finding]:
    """Return advisory findings; manual claims are skipped because they already name their gap."""
    findings: list[Finding] = []
    for claim in claims:
        check = claim.get("check") or {}
        if "manual" in check:
            continue
        text = _text(claim)
        value = str(claim.get("value", ""))
        if not DYNAMIC_VALUE.search(value):
            continue
        if STABLE_VALUE.search(value):
            continue
        # A dated/upstream snapshot is intentionally fixed; its freshness is a separate question.
        if IMMUTABLE_CONTEXT.search(text):
            continue
        if not DYNAMIC_WORDS.search(text):
            continue
        if RELATIONAL_WORDS.search(text) and re.search(r"(?:data|file|snapshot|page|source)", text, re.I):
            continue
        findings.append(Finding(
            claim_id=str(claim.get("id", "?")),
            value=value,
            reason="numeric claim mentions data that may grow or be regenerated",
            suggestion="replace a pinned count with a relation check, or attach a dated snapshot",
        ))
    return findings


def render(findings: list[Finding]) -> str:
    lines = [f"dynamic-claim candidates: {len(findings)}"]
    for f in findings:
        lines.append(f"  {f.claim_id}: {f.value} — {f.reason}; {f.suggestion}")
    if not findings:
        lines.append("  none")
    return "\n".join(lines)
