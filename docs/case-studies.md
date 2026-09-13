# Case studies: how published numbers go wrong

Every case below is a claim that was published in one of this author's repositories, found by
a read-only audit, and fixed. They are grouped by failure mode, because the mode determines
which check catches it. Commit references point at the fix.

The audit covered 16 repositories and 553 checkable claims: **about 100 did not stand up**
(18%). The distribution is not uniform — it is concentrated in six modes, and five of the six
are mechanical enough to put behind a gate.

## 1. A hand-written number that the data stopped producing

The number was true when written. Nothing failed as the data moved.

| Where | Claimed | Truth |
|---|---|---|
| `foodmap/docs/screenshot.png` | 264 restaurants / 285 visits (rendered in the image) | 252 / 281 for that blogger, 283 / 312 shipped (`b2ffe6b`) |
| `codeblast` README, SKILL.md, LAUNCH.md, site, `llms.txt` (8 places) | "tRPC, 950 files" | its own sample run says 957 (`88de49f`) |
| `alloevil` profile card | "Eugeny/tabby (60k★)" | 74,442★ — and the string was hardcoded *inside the generator that re-renders the card daily*, so the daily job could never correct it (`4a54009`) |

**Catch it with**: `equals` / `contains` on a command that recounts the figure from committed
data. For the card case the fix was stronger than a check: the generator now reads the star
count from an environment variable the workflow fills with `gh api`, and omits the number when
it cannot fetch it.

```jsonc
"check": { "cmd": "python3 -c \"import json;print(len(json.load(open('data/x.json'))))\"",
           "expect": { "equals": "283" } }
```

## 2. A number attributed to the wrong upstream

Not stale — wrong from the start, usually because it was recalled rather than read.

| Where | Claimed | Upstream actually says |
|---|---|---|
| `coding-agent-internals/agents/omp.md` | 32 tools · 13 LSP ops · 27 DAP ops · 40+ providers · ~27K lines of Rust | 31 · 14 · 28 · 60+ · ~80k (`34fb157`) |
| `coding-agent-internals/agents/hermes.md` | TypeScript, 15+ smart-routing providers, mem0 memory | Python, "any OpenAI-compatible / 300+ models via Nous Portal", built-in `MEMORY.md`/`USER.md` |
| `agent-tool-benchmark` PDF suite | "pymupdf4llm 0.65 s/doc" | its own `results.json` mean is 1.073 s (`b629659`) |

**Catch it with**: a check that recomputes from *your* committed data (`equals` against
`results.json`), plus — for claims about someone else's project — a source URL next to the
number and a scheduled re-check. `verify-claims` deliberately does not fetch upstream pages;
that part stays a human read, which is why this repo's own pages now carry the upstream link
beside each figure.

## 3. A feature that does not exist

The most expensive mode, because a reader plans around it.

| Where | Claimed | Code |
|---|---|---|
| `agent-changelog` README, hero, site meta | "a daily cron job syncs the latest releases" | no `schedule:` anywhere in the repo; the workflow is `workflow_dispatch` only (`a6851ab`) |
| `agent-changelog/scripts/sync.mjs` | it rewrote a `CHANGELOG_DATA` block in `index.html` | `index.html` contains no such block — the script printed "not found" and did nothing; the site loads `openclaw_data.js` |
| `coding-agent-internals/benchmarks` | quickstart step 2 runs `./search-bench.sh` | only `edit-bench.sh` existed (`34fb157` — the script was then written) |
| `TabCraft` README/USAGE | "390+ built-in rules, fully editable, import/export" | `seed-rules.json` has exactly 390; the Rules view edits only custom rules; import/export lives in Settings (`e8fe347`) |

**Catch it with**: run the documented command. A check whose `cmd` is the instruction from the
README turns "does this exist?" into an exit code:

```jsonc
"check": { "cmd": "test -f benchmarks/search-bench.sh && echo present",
           "expect": { "contains": ["present"] } }
```

## 4. A gate that does not gate

Worse than no gate: it produces the feeling of verification.

| Where | What it did | Why it could not work |
|---|---|---|
| `llm-benchmarks-tracker` `build.py --check` | compares rendered README against the committed one, in CI | the stats line carried `date.today()`, so the check failed on **every day without a rebuild** (`4d576a2`) |
| `agent-engineering-book` link check | ran lychee over the repo | `--exclude-path references`, i.e. it skipped the one directory that held a broken citation (`4beb88d`) |
| `agent-tool-benchmark` smoke job | "task sets match across tools" | the step only warned while the workflow header claimed it enforced; a tool with a different task set passed (`b629659`) |
| `paired-eval` `tests/test_site.py` | asserts the README header references a repo-local logo | the assertion pinned one specific asset, so replacing the logo with a hero broke CI and nobody noticed for days |

**Catch it with**: prove the gate can fail. Both `verify-claims` and the repos wired to it run
a step that deliberately breaks a number and requires the run to fail. A check that has never
been red is a hypothesis.

## 5. A measurement that was an estimate

These are the hardest to see, because the number is plausible and was probably right on the
author's machine.

| Where | Claimed | Measured |
|---|---|---|
| `paired-eval` README | `required_pairs(0.15, 0.30)` "~20 s" | 71 s (0.4.1 retraction in `docs/corrections.md`) |
| `codeblast` README | "full build of tRPC … in ~20s" | the repo's only recorded sample is 5.2 s, and `claims.json` explicitly declines wall-clock claims |
| `foodmap` Known Limitations | "measured hit rate about 18% (1131/6129)" | cannot be recomputed: the raw input is gitignored; the only committed probe reads 13/25 (≈52%) (`b2ffe6b`) |
| `deepresearch-arms-lab` boundary table | "↓ faith. −0.18" | −0.13 against the row above, −0.23 against the same batch (`a9aa400`) |

**Catch it with**: label every figure as *measured* (with the command), *derived* (with the
inputs it was computed from) or *estimate* (with the reason it cannot be measured). Then put
the measured ones behind `check` and the rest behind `check.manual` — visible on every run,
never silently implied.

## 6. Two places that disagree with each other

| Where | The two numbers |
|---|---|
| `coding-agent-internals` site | star counts for the same project appear as 28K in one place and 237K in another (both wrong; the live values are different) |
| `alloevil` profile | badge "Secondary TypeScript" while the generated language table on the same page ranks JavaScript above TypeScript |
| `AI-Paper-Daily` | README advertised LLM filtering while all 19 archived digests record `本期筛选方式：热度回退（未配置 LLM）` — including the site's meta description, which the first pass missed (`8f20e0a`) |
| `llm-benchmarks-tracker` | the "top score" cell for two benchmarks was not the highest figure on a page the repo already cites as a source (`b288fd8`) |

**Catch it with**: assert on one copy from the other (`not_contains` on the stale wording after
the fix; a generated artifact plus a drift check for anything rendered twice), and make numbers
carry an as-of date so "which one is newer" is answerable without archaeology.

## The checks I wrote wrongly

Worth recording, because it happened in the first hour of using this tool — on checks written
by the same person who wrote the audit:

| My check | What it did wrong | Caught by |
|---|---|---|
| foodmap geography | counted `continent == 亚洲` for a claim that says "in China" (`country == 中国`) | the gate printing `got '3 8 95 272'` against the expected `262` |
| arms-lab deltas (3 checks) | computed the difference of *unrounded* means while the published figure subtracts the **rounded** arm values (0.66 − 0.42, not 0.6581 − 0.4231) | three failures listing `+0.23` vs the claimed `+0.24` |
| codeblast ablation | pointed at the plain n=15 run instead of the channel-ablation run | `9/15 (60%)` against the claimed `2/14 (14%)` |
| paired-eval dependency check | `grep '^dependencies = \[\]$'` — the manifest line has a trailing comment | exit 1 with zero matches |
| this repo's own example | `check.dir` is relative to `--root`, so the example looked for `example/example` | `example-passes` failing on the first dogfood run |

**Expect your check to be the first thing that fails.** That is the cheapest possible version
of the bug it is meant to catch.

## What this cannot catch

- A number with no committed computation behind it (a vendor's figure, a dashboard you do not
  own). Use `check.manual` with the reason, and re-read the source when it matters.
- Human judgements (review scores, ratings). Same treatment.
- A third-party page that silently changes. The `alloevil` card solved the class that is
  solvable — fetch the number at render time instead of hardcoding it.
- Whether a claim is *worth* publishing. The tool checks the receipt, not the taste.
