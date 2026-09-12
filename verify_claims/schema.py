"""Shape validation for a claims document.

The shape is taken from the claims files that already exist in this author's
repositories (codeblast, paired-eval, foodmap, deepresearch-arms-lab,
github-discovery, agent-harness-evals, llm-benchmarks-tracker), so it accepts
what those files already contain: `verified` and `as_of` are both accepted as
the date the claim was last checked, and unknown keys are tolerated (a standard
that rejects harmless extras does not get adopted).

The one rule that is enforced beyond shape: **a claim must say how it can be
checked** — either a `check` block (a command plus what its output must contain)
or `check.manual` with a reason why no command can do it. A claim with neither
is an error, because that is exactly the "receipt that cannot run" this tool
exists to catch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_CLAIM_FIELDS = ("id", "claim", "value", "metric", "method", "repro", "evidence")
DATE_FIELDS = ("as_of", "verified", "updated")
CHECK_KEYS = {"cmd", "expect", "manual", "timeout", "dir", "note"}
EXPECT_KEYS = {"equals", "contains", "not_contains", "regex", "exit_code"}

# A claim whose value carries a number is the interesting case: it is the kind of
# figure that rots silently in prose. It may still be manual, but the reason has to
# be written down, and the report marks it.
DIGITS = tuple("0123456789")


def _is_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def validate_check(claim_id: str, check: Any, errors: list[str]) -> None:
    where = f"claim {claim_id!r} check"
    if not isinstance(check, dict):
        errors.append(f"{where}: must be an object")
        return
    unknown = set(check) - CHECK_KEYS
    if unknown:
        errors.append(f"{where}: unknown key(s) {sorted(unknown)}; known: {sorted(CHECK_KEYS)}")

    manual = check.get("manual")
    cmd = check.get("cmd")
    if manual is not None and cmd is not None:
        errors.append(f"{where}: has both 'manual' and 'cmd' — a claim is either machine-checked or manual")
    if manual is None and cmd is None:
        errors.append(f"{where}: needs 'cmd' (machine-checked) or 'manual' (a reason it cannot be)")
    if manual is not None and not _is_str(manual):
        errors.append(f"{where}: 'manual' must be a non-empty reason string")
    if cmd is not None and not (_is_str(cmd) or (isinstance(cmd, list) and all(_is_str(c) for c in cmd))):
        errors.append(f"{where}: 'cmd' must be a string or a list of strings")
    if "timeout" in check and not (isinstance(check["timeout"], (int, float)) and check["timeout"] > 0):
        errors.append(f"{where}: 'timeout' must be a positive number of seconds")
    if "dir" in check and not _is_str(check["dir"]):
        errors.append(f"{where}: 'dir' must be a non-empty path string")

    expect = check.get("expect")
    if expect is None:
        return
    if not isinstance(expect, dict):
        errors.append(f"{where}.expect: must be an object")
        return
    unknown = set(expect) - EXPECT_KEYS
    if unknown:
        errors.append(f"{where}.expect: unknown key(s) {sorted(unknown)}; known: {sorted(EXPECT_KEYS)}")
    for key in ("equals", "regex"):
        if key in expect and not _is_str(expect[key]):
            errors.append(f"{where}.expect.{key}: must be a non-empty string")
    for key in ("contains", "not_contains"):
        if key in expect:
            v = expect[key]
            if not (isinstance(v, list) and v and all(_is_str(x) for x in v)):
                errors.append(f"{where}.expect.{key}: must be a non-empty list of strings")
    if "exit_code" in expect and not isinstance(expect["exit_code"], int):
        errors.append(f"{where}.expect.exit_code: must be an integer")


def validate_claim(index: int, claim: Any, errors: list[str]) -> None:
    if not isinstance(claim, dict):
        errors.append(f"claims[{index}]: must be an object")
        return
    cid = claim.get("id") if _is_str(claim.get("id")) else f"claims[{index}]"
    for field in REQUIRED_CLAIM_FIELDS:
        if not _is_str(claim.get(field)):
            errors.append(f"claim {cid!r}: missing or empty {field!r}")
    if not any(_is_str(claim.get(f)) for f in DATE_FIELDS):
        errors.append(f"claim {cid!r}: needs one of {list(DATE_FIELDS)} — that is the date the value was last true for")
    if "check" not in claim:
        errors.append(
            f"claim {cid!r}: no 'check' — add 'check.cmd' + 'check.expect', "
            "or 'check.manual' with the reason it cannot be checked by a command"
        )
    else:
        validate_check(cid, claim["check"], errors)


def validate_document(doc: Any, path: Path) -> list[str]:
    """Return a list of human-readable problems; empty means the shape is valid."""
    errors: list[str] = []
    if not isinstance(doc, dict):
        return [f"{path}: top level must be an object"]
    claims = doc.get("claims")
    if not isinstance(claims, list) or not claims:
        return [f"{path}: 'claims' must be a non-empty list"]
    if not any(_is_str(doc.get(f)) for f in DATE_FIELDS):
        errors.append(f"{path}: document needs one of {list(DATE_FIELDS)}")
    seen: set[str] = set()
    for i, claim in enumerate(claims):
        validate_claim(i, claim, errors)
        if isinstance(claim, dict) and _is_str(claim.get("id")):
            if claim["id"] in seen:
                errors.append(f"claim {claim['id']!r}: duplicate id")
            seen.add(claim["id"])
    return errors


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
