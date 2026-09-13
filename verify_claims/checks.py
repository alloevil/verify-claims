"""Assertion evaluation: does a command's output still back the published value?"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    claim_id: str
    status: str  # ok | fail | manual | error
    detail: str = ""
    cmd: str = ""
    exit_code: int | None = None
    duration_s: float = 0.0
    stdout: str = ""
    stderr: str = ""
    failures: list[str] = field(default_factory=list)


def _snippet(text: str, limit: int = 300) -> str:
    """First non-empty lines of a command's output, for the failure message."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    joined = " ⏎ ".join(lines[:6])
    return joined if len(joined) <= limit else joined[: limit - 1] + "…"


def evaluate(stdout: str, exit_code: int, expect: dict[str, Any] | None) -> list[str]:
    """Return the list of failed assertions (empty = the check passed).

    `equals` compares the stripped stdout, because most receipts here are a single
    line printed by a script. Everything else searches the raw stdout, so a
    multi-line report can be matched without post-processing it.

    Every failure carries what the command actually printed. Without it a red CI run
    says "not found in output" and the reader has to reproduce the command locally to
    learn why — which is the round trip this tool exists to remove.
    """
    expect = expect or {}
    failures: list[str] = []
    text = stdout.strip()
    seen = f" · output: {_snippet(stdout)!r}" if stdout.strip() else " · output: (empty)"

    wanted_code = expect.get("exit_code", 0)
    if exit_code != wanted_code:
        failures.append(f"exit_code: expected {wanted_code}, got {exit_code}{seen}")

    if "equals" in expect:
        want = expect["equals"].strip()
        if text != want:
            failures.append(f"equals: expected {want!r}, got {text[:400]!r}")
    for needle in expect.get("contains", []) or []:
        if needle not in stdout:
            failures.append(f"contains: {needle!r} not found in output{seen}")
    for needle in expect.get("not_contains", []) or []:
        if needle in stdout:
            failures.append(f"not_contains: {needle!r} found in output{seen}")
    if "regex" in expect:
        if re.search(expect["regex"], stdout, re.MULTILINE) is None:
            failures.append(f"regex: {expect['regex']!r} did not match output{seen}")
    return failures


def summarise(results: list[CheckResult]) -> dict[str, int]:
    counts = {"ok": 0, "fail": 0, "error": 0, "manual": 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    counts["checked"] = counts["ok"] + counts["fail"] + counts["error"]
    return counts


def exit_code_for(results: list[CheckResult], strict: bool) -> int:
    """0 when every machine check passed; 1 otherwise. In strict mode an unchecked
    (manual) claim is a failure too — that is how a repository tightens over time."""
    if any(r.status in ("fail", "error") for r in results):
        return 1
    if strict and any(r.status == "manual" for r in results):
        return 1
    return 0
