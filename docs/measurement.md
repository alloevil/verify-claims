# What the audit found: 131 of 553 published claims did not stand up

This is the measurement behind `verify-claims`. Between 2026-09-11 and 2026-09-13 every
public repository of this account was audited read-only, claim by claim, against the artefacts the
repository itself commits (and against upstream primary sources where a claim is about another
project). 16 repositories, **553 checkable claims, 131 of which did not stand up — 24%**.

That number is the reason the tool exists, so it is stated with its own arithmetic: the per-repo
table below is summed by a command in this repository's `claims.json` (`measurement-totals`), so a
typo in this file fails the gate rather than ageing here.

## The per-repo table

| repository | claims checked | contradicted | unsupported | the worst finding, and where it landed |
|---|---:|---:|---:|---|
| llm-benchmarks-tracker | 18 | 0 | 0 | 5 imprecise claims; the `--check` drift guard failed every day without a rebuild (`4d576a2`) |
| agent-harness-evals | 20 | 6 | 1 | "~5,500 records / 83 benchmarks" — the commit said 6,395 / 89 (`1f15850`) |
| codeblast | 35 | 0 | 2 | "950 files" in eight places where the tool's own output says 957 (`88de49f`) |
| paired-eval | 24 | 2 | 0 | `Status: 0.4.0` while the checkout was 0.4.1 — and PyPI served the older one (`2f879f4`) |
| foodmap | 45 | 3 | 1 | the screenshot showed 264/285 while the shipped data held 252/281 (`b2ffe6b`) |
| deepresearch-arms-lab | 31 | 6 | 2 | the README dropped its own explicit negative arm while claiming to keep negatives (`a9aa400`) |
| AI-Paper-Daily | 40 | 10 | 1 | the site said "LLM-filtered" while every archived digest recorded the no-key fallback (`263c026`, `8f20e0a`) |
| agent-changelog | 22 | 12 | 1 | "a daily cron syncs automatically" — no `schedule:` existed anywhere (`a6851ab`) |
| agent-tool-benchmark | 63 | 15 | 3 | a headline latency contradicted its own `results.json`; a cold row duplicated the warm range (`b629659`) |
| dsh-xray | 43 | 2 | 9 | the flagship `deps` sample had no committed input; it is a real capture whose counts drifted (`b500068`) |
| coding-agent-internals | 37 | 20 | 4 | every headline number on the omp page was wrong: 32/13/27/40+ against upstream's 31/14/28/60+ (`34fb157`) |
| github-discovery | 42 | 3 | 1 | the "7-day backtest" measured about one day (`47f439d`) |
| TabCraft | 37 | 4 | 2 | "390+ rules, fully editable, import/export" against a Rules view that edits only custom rules (`e8fe347`) |
| alloevil | 24 | 4 | 3 | the Tabby star count was hardcoded inside the generator that re-renders the card daily (`4a54009`) |
| agent-engineering-book | 29 | 7 | 2 | a 14-chapter book advertised with exercises and code, of which two chapters are written (`4beb88d`) |
| AgentXRay | 43 | 4 | 1 | two documented log locations that no adapter implements; a "only outbound traffic" claim (`32f9422`) |
| **16 repositories** | **553** | **98** | **33** | **131 defective claims, 24%** |

Sources for the tallies: the audits' own verdict records. The ten audits from 2026-09-12 onward are
quoted per repository in `CHANGELOG-2026-09.md` (§D–§G); the six earlier ones are the audit
summaries recorded during that session — their transcript artefacts have since expired, which is
itself the argument for committing receipts instead of chat logs.

**A correction to my own reporting.** While assembling this table I found that the figure I had
been repeating — "about 100 claims, 18%" — was wrong twice over: it summed only `contradicted`,
only for the later batches, and never added the `unsupported` column. The audit's own records give
98 contradicted plus 33 unsupported, i.e. **131 of 553 (24%)**. The smaller number was the more
comfortable one and it went unchallenged for two days, in a project whose entire subject is
numbers that go unchallenged.

## What "did not stand up" looked like

Six modes accounted for all of them, and five are mechanical enough to gate:

1. **A hand-written number the data stopped producing** — the screenshot at 264/285, "950 files",
   the star count inside a daily generator. The number was true when written; nothing failed as the
   data moved. *(caught by a command that recounts it)*
2. **A number attributed to the wrong upstream** — the omp headline figures, a language stated as
   TypeScript when the project is Python. Recalled rather than read. *(caught by reading upstream,
   then pinning the reading date)*
3. **A feature that does not exist** — the "daily cron", a quickstart step naming a script nobody
   wrote, a rules editor documented with import/export that lives in another screen. *(caught by
   running the documented command)*
4. **A gate that does not gate** — four cases: a `--check` red every day because its stamp came from
   `date.today()`; a link checker excluding the one directory holding a broken link; a smoke step
   that warned while the file claimed it enforced; an assertion pinned to one specific asset name.
   *(caught by making the gate fail on purpose)*
5. **A measurement that was an estimate** — "~20 s" against a measured 71 s, "~20s" against a
   recorded 5.2 s, an 18% hit rate with no reproducible input, a delta that matched neither the
   table nor the batch. *(caught by separating measured / derived / estimate, and dating each)*
6. **Two places disagreeing with each other** — one project shown as 28K stars in one place and
   237K in another; a "Secondary TypeScript" badge above a language table ranking JavaScript higher;
   a site saying "LLM-filtered" over an archive that says otherwise. *(caught by asserting one copy
   from the other)*

## What changed as a result

- **`verify-claims`** (this repository): `claims.json` + `check`, the offline runner, `--strict`,
  the GitHub Action, `v0.1.0` → `v0.1.1`.
- **22 repositories now run that gate** in CI, on push, on PRs and weekly, over **≈300 machine-checked
  claims** (the rest are `manual` with a written reason — model-dependent findings, upstream-quoted
  figures, third-party pages).
- **`docs/case-studies.md`** collects the fixes with their commit references, so the examples are
  checkable rather than anecdotal.
- The audits themselves corrected 131 claims, and several structural fixes came out of them that no
  claim audit would have asked for: a daily-red CI gate, a generator whose output drifted on every
  rebuild, a syncer writing to a file the site does not load, three workflows whose token scope or
  action pinning was wrong.

## The checks I wrote wrongly

Worth recording, because it happened repeatedly — to the same person who wrote the audit, using a
tool designed to catch exactly this:

| my check | what was wrong | how it surfaced |
|---|---|---|
| foodmap geography | counted `continent == 亚洲` for a claim about China (`country == 中国`) | `got '3 8 95 272'` against the expected `262` |
| arms-lab deltas (×3) | differenced *unrounded* means while the published figure subtracts rounded ones | three failures showing `+0.23` against the claimed `+0.24` |
| codeblast ablation | pointed at the plain n=15 run instead of the channel-ablation run | `9/15 (60%)` against the claimed `2/14 (14%)` |
| paired-eval dependency check | a `grep` anchored to end-of-line on a line with a trailing comment | exit 1 with zero matches |
| the tool's own example | `check.dir` is relative to `--root`, so it looked for `example/example` | the first dogfood run |
| dsh-xray panel address | the CLI needs its `yaml` dependency; the job installed nothing | gate red on its first CI run |
| dsh-xray test count | 70 here (a real `~/.dsh` present) versus 62 on a bare runner | gate red on its second CI run |
| the site repo's page count | counted every tracked `.md`, which now includes the README | gate red on its first run |
| the site repo's `llms.txt` claim | asserted it indexes the posts; it is a project summary | gate red on its first run |
| three workflows' permissions | gave `contents: read` to workflows that write (a snake, a README block, an HTML file) | caught before pushing; two of the three had already been committed |

Ten wrong checks against 131 wrong claims: about one in thirteen. **Expect the check to be the
first thing that fails** — it is the cheapest version of the bug it is meant to catch.

## Limitations

- **One auditor, and it is me.** The verdicts were produced by me (with read-only agents doing the
  first pass); for every `contradicted` verdict I re-derived the figure myself before editing, and
  two of my own early alarms were wrong. There is no independent second opinion.
- **Not a random sample.** These are repositories I maintain, audited by their author's own tooling,
  with a bias toward the claim-dense ones. 24% is this portfolio's rate, not a base rate for
  documentation in general.
- **Softer verdicts count as defects here.** `imprecise` (true but mis-scoped) and `derived`
  (correct arithmetic, wrongly presented) are not counted in the 131; they are the majority of the
  remaining findings, and a stricter standard would call more of them defects.
- **`manual` is a to-do, not a resolution.** A claim no command can check is visible on every run,
  but it is not verified — the ≈300 machine-checked claims are the only ones this measurement can
  speak for.

---

## Coverage: how much was never claimed at all

The audit above measures claims that exist. It cannot see figures nobody ever wrote down, and a
gate is silent about exactly those. `verify-claims coverage` (added with `0.1.2`) reads a README's
prose, extracts number-like tokens, and lists the ones no claim mentions.

Run across the 22 repositories this tool guards on 2026-09-14, it reports **176 mentions covered by
a claim and 78 with none** (69% covered). The 48% it reported a day earlier was not a change in the
repositories' honesty but in the claims: converting manual claims to snapshot-backed ones put the
figures those claims describe into the checkable text for the first time. The figure is **not** a
defect count and should not be quoted as one:

- it is a **heuristic over prose**, and its own first two runs were wrong in ways that flattered the
  tool: it matched the whole token (unit included), so `283 家` never matched a claim that says
  `283`, and it treated CJK characters as word characters, which silently hid *every* number in a
  Chinese README — a `0% covered` that was a regex artefact, not a finding;
- many candidates are **not figures at all**: an example's `50MB`, an HTTP `503`, a `24 小时`
  statement, a CSS `width="100%"`, an `img width="100%"`. Reviewing four repositories by hand, the
  majority of candidates were of this kind;
- numbers written as words (`seven platforms`, `七种日志格式`) are invisible to it in **both**
  directions — they are neither claimed nor flagged, which is the one error that makes the
  repository look better than it is;
- it says nothing about whether a claimed number is **true**, which is `run`'s job alone.

What it is good for: a triage list, ordered by where a reader looks first, for the repositories
whose claims are thinnest. Acting on the first version of that list is what took the portfolio from
48% to 69%: `foodmap`, `weibo-chat-auto` and `github-discovery` each had a handful of claims against
a README full of figures, and each gained the receipts that made sense — machine checks where the
data is committed, manual entries naming the missing artifact where it is not. The remaining 78
candidates are mostly the decorative kind above; the honest next target is not the count but the
individual number that turns out to be a real figure with nothing behind it.
