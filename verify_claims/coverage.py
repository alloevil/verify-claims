"""Coverage: which numbers in a README are not covered by any claim.

This is a **heuristic report, not a verdict**. `verify-claims run` decides whether a claim is
true; this decides whether a number was ever written down as a claim at all. It exists because
the gate can only defend the numbers somebody remembered to claim — the rest are invisible by
construction, and "we gated everything" is exactly the kind of unexamined statement this project
is about.

What it does: pull number-like tokens out of the prose (skipping fenced code, links and tables
that are generated), normalise them, and look for each one in the claims file's `claim` / `value`
/ `metric` text. Numbers that nothing claims are printed as candidates, most prominent first.

What it does not do: tell you the number is wrong, decide whether a number *should* be claimed, or
understand context well enough to avoid missing things. Expect false positives (version numbers,
dates, years, thresholds) and false negatives (a claim worded without its digits).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# A number we care about: has a unit, a percent sign, a ratio, or is the kind of bare count that
# appears in a stats line. Deliberately noisy — the report is a to-do list, not a gate.
NUMBER = re.compile(
    # Boundaries are ASCII-only on purpose: Python counts CJK characters as \w, so a plain
    # (?<!\w) would reject "共 72 条" and silently hide every number in a Chinese README.
    r"""(?<![A-Za-z0-9_.])(
          \d+(?:[.,]\d+)?\s*%                     # 42%
        | \d+\s*/\s*\d+                           # 28/28
        | \d[\d,]*\s*(?:files|records|tests|releases|versions|repos|rows|benchmarks|evaluators|pages|posts|arms|commands|rules|platforms|models|harnesses|lines|stars)\b
        | \d[\d,\.]*\s*(?:s|ms|KB|MB|GB|k|K)\b   # 5.2 s, 1.07 s/doc, 74k
        | \d[\d,\.]*\s*(?:条|个|项|次|行|款|篇|章|家|位|名|台|种|份|组|场|页|张|人|天|小时|分钟|秒|毫秒|万|亿)   # CJK units
        | \b\d{3,}\b                              # bare counts of three digits or more
    )(?![A-Za-z0-9_])""",
    re.VERBOSE,
)

# Lines that are not prose we should hold to a claim: links, images, HTML, fences, badges, tables.
SKIP_LINE = re.compile(
    r"""(^\s*(?:\#|>)|\]\(|src=|href=|^\s*[-*]\s*\[|^```|^\s{4,}\S|img\.shields\.io|
         https?://|\bversion\b\s*[:=]|^\s*[-*]\s*`?[a-z_]+\s*[:=])""",
    re.VERBOSE | re.IGNORECASE,
)

SCOPE = ("README.md", "README.zh-CN.md", "README.zh.md")


@dataclass
class Mention:
    number: str
    line: int
    text: str


def strip_noise(text: str) -> str:
    """Remove fenced code blocks; they are examples, not claims about the repository."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        out.append("" if fenced else line)
    return "\n".join(out)


def mentions(readme: Path, limit_lines: int | None = None) -> list[Mention]:
    """Number-like tokens in the README's prose, in file order."""
    text = strip_noise(readme.read_text(encoding="utf-8"))
    found: list[Mention] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if limit_lines is not None and i > limit_lines:
            break
        if SKIP_LINE.search(line):
            continue
        for m in NUMBER.finditer(line):
            token = " ".join(m.group(1).split())
            found.append(Mention(token, i, line.strip()[:120]))
    return found


def _numeric_core(token: str) -> str:
    """The digits in a mention, without its unit: '283 家' and '283' are the same number.

    Matching the whole token (unit included) made every repo whose prose carries a unit look
    uncovered, because a claim states the number, not the sentence around it.
    """
    m = re.match(r"[\d][\d,\.]*", token)
    return re.sub(r"[,\s]+", "", m.group(0)) if m else re.sub(r"[,\s]+", "", token).lower()


def _claims_numbers(claims: Iterable[dict]) -> set[str]:
    """Every number the claims mention, in any of their free-text or command fields."""
    return {_numeric_core(m.group(0)) for m in re.finditer(r"\d[\d,\.]*", claims_text(claims))}


def claims_text(claims: Iterable[dict]) -> str:
    """Everything a claim says about its number, for the coverage match."""
    parts: list[str] = []
    for c in claims:
        for key in ("claim", "value", "metric", "method"):
            v = c.get(key)
            if isinstance(v, str):
                parts.append(v)
        check = c.get("check") or {}
        cmd = check.get("cmd")
        if isinstance(cmd, str):
            parts.append(cmd)
        elif isinstance(cmd, list):
            parts.extend(str(x) for x in cmd)
    return "\n".join(parts)


def report(readme: Path, claims: list[dict], limit_lines: int | None = None) -> tuple[list[Mention], list[Mention]]:
    """(covered, uncovered) mentions for one README."""
    claimed = _claims_numbers(claims)
    covered, uncovered = [], []
    seen: set[str] = set()
    for m in mentions(readme, limit_lines):
        key = _numeric_core(m.number)
        if key in seen:
            continue
        seen.add(key)
        (covered if key in claimed else uncovered).append(m)
    return covered, uncovered
