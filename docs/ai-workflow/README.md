# How this lab was built: a human directs, an AI agent executes

This lab was built by one person directing an AI coding and research agent
([Claude Code](https://claude.com/claude-code)) under a written contract.

The starting point was a small v0.1 toolkit package that already contained the contract files described
below (see the pre-git section of the [`CHANGELOG`](../../CHANGELOG.md)). That package predates git, so
the history does not record how it was written. From the first commit onward, the agent wrote the code,
the tests, the research notes and the commit messages. The human set the scope, held
the credentials, approved or declined new data sources, and decided what, if anything, could be approved
for runtime use.

That is stated plainly because it changes how the work should be read. It is also arguably the part of
the repository most worth reusing: a small set of mechanical rules that let an agent run experiments
quickly **without** changing how its work is scored, touching anything dangerous, or quietly keeping a
flattering number.

Everything here is research-only and paper-only. No order was ever placed, and nothing in this repository
is betting or financial advice.

## The design problem

An agent that can edit the model, the evaluator, the data and the report can always find an improvement.
Most of those improvements are not real. The contract removes the easy ways to fool yourself:

| Rule | Where it lives | What it prevents |
|---|---|---|
| **A fixed evaluator.** Time-ordered folds, a composite objective (0.40 RPS + 0.25 log loss + 0.20 draw Brier + 0.15 draw calibration error; RPS is the ranked probability score, lower is better) and a pre-set minimum improvement of 0.002 (`minimum_relative_improvement`). | [`src/wcdrawlab/research/runner.py`](../../src/wcdrawlab/research/runner.py) (166 lines), [`configs/research.yaml`](../../configs/research.yaml) | Moving the goalposts after seeing a result. |
| **One editable file.** Autonomous experiments may change only the candidate model. | [`src/wcdrawlab/research/candidate.py`](../../src/wcdrawlab/research/candidate.py) (98 lines), [`program.md`](../../program.md) | "Improving" the score by editing the data, the folds or the metric. |
| **Forbidden columns are stripped before the candidate sees the data.** The evaluator drops the target and post-match columns named in the config, then passes only numeric columns to the model. This is leakage-tested, not a guarantee. The numeric-only filter is also the mechanism behind [ERRATA E1](../ERRATA.md#e1--the-v8-worse-than-b1-on-2026-result-was-a-bug): a script outside the evaluator handed it an all-text row, and every feature was silently zero-filled. | `leakage_safe_feature_frame()` in `runner.py`; [`tests/test_research_leakage.py`](../../tests/test_research_leakage.py) | Target leakage through a feature. |
| **Protected paths.** Trading, provider adapters, scraping policy, credentials, the two governance documents and the trading / Kalshi / in-play safety tests are off-limits. | [`program.md`](../../program.md), [`AGENTS.md`](../../AGENTS.md) | An experiment weakening a safety control. |
| **No credentials.** The agent may report only whether a variable is `SET` or `MISSING`, never its value. | [`CLAUDE_CODE_MASTER_PROMPT.md`](CLAUDE_CODE_MASTER_PROMPT.md) §1; the resulting [`setup_status.md`](../../notes/research/setup_status.md) | Secrets in notes, logs or commits. |
| **Data-request gating.** A new API, dataset or scraped domain is first a written request. No connector is written until the human approves it. | [`data_requests/`](../../data_requests/), [`DATA_SOURCE_GOVERNANCE.md`](../DATA_SOURCE_GOVERNANCE.md) | Silent scope creep, unlicensed data, surprise costs. |
| **Promotion is hard-coded off.** The evaluator always returns `promoted=False` with the reason "Research outputs require human review and explicit runtime approval." | `runner.py`; the registry in [`configs/approved_models.yaml`](../../configs/approved_models.yaml), enforced by [`src/wcdrawlab/runtime/model_registry.py`](../../src/wcdrawlab/runtime/model_registry.py) | A research result becoming a runtime model without a human decision. |
| **One experiment, one note, keep or revert.** Each hypothesis must be able to fail, and the outcome is written down either way. | [`program.md`](../../program.md); the `*cycle*` notes in [`notes/research/`](../../notes/research/). Cycles 4–6 of 2026-06-20 now carry correction banners: their early claims about the bookmaker market had no confidence intervals and were not confirmed ([ERRATA E4](../ERRATA.md#e4--early-beats-the-market-notes-were-never-confirmed)). | Unrecorded negative results. |

The reasoning behind the split between a research plane and an execution plane is in
[`AUTORESEARCH_GOVERNANCE.md`](../AUTORESEARCH_GOVERNANCE.md). The pattern is adapted from Karpathy's
`autoresearch` idea: a fixed harness, one small editable surface, a stable metric and an experiment log.

### Scope of the contract

`program.md` governs the **autonomous autoresearch loop**. It does not describe the whole repository.

Most of the code here — the in-play research lines, the data pipelines, the prospective collector, the
score harvester — was written by the agent outside that loop, in human-directed sprints. Each sprint has
its own runbook in [`docs/`](../README.md#research-line-runbooks) with its own "never touches" list (the
active collector, B1, the frozen models, `candidate.py`, the approved-model registry, trading, `.env`).

So "the agent may edit only `candidate.py`" is true of the loop, not of the lab.

## Did the contract hold?

This can be checked from git rather than taken on trust.

```bash
git diff --stat e78cde4 HEAD -- src/wcdrawlab/trading src/wcdrawlab/providers src/wcdrawlab/scraping \
  configs/trading.yaml .env.example tests/test_inplay.py tests/test_kalshi_safety.py tests/test_trading_risk.py \
  src/wcdrawlab/research/candidate.py src/wcdrawlab/research/runner.py program.md configs/research.yaml
```

`e78cde4` is the first commit (2026-06-20). As checked on 2026-09-20, the diff over those paths is
**140 added lines, 0 removed lines, in 5 files**:

| Path | Since the first commit |
|---|---|
| `runner.py`, `candidate.py`, `program.md`, `configs/research.yaml` | Unchanged. The evaluator code and its config stayed fixed, and the candidate was never replaced, because no experiment cleared the threshold. One addition sits beside them: `configs/research_dev.yaml` (2026-06-21) runs the same objective and threshold on development folds 2010 / 2014 / 2018 only, after the release-gate audit described below. |
| `configs/trading.yaml`, `.env.example`, `src/wcdrawlab/scraping/`, the three baseline safety test files | Unchanged. |
| Existing provider adapters and the Kalshi client | Unchanged. |
| `src/wcdrawlab/providers/` | Two new files added (a provider interface and a quota scheduler). |
| `src/wcdrawlab/trading/` | 13 lines added in one commit, binding the paper-trade risk gate to the approved-model registry. A tightening, but still an edit to a protected path. |
| `tests/test_inplay*.py` | Not part of the command above, which names only the three baseline test files. `program.md` protects this whole pattern, and four new files matching it were added beside the unchanged baseline `tests/test_inplay.py` (236 added lines, 0 removed). |

Three further points belong on the record:

- **A documented override before the first commit.** Real keys had been placed in `.env.example`. A human
  directive authorized a script to move them into the gitignored `.env` without printing them. They were
  never committed: `.env.example` has a single commit, every secret variable in it is blank, and
  [`tests/test_secret_hygiene.py`](../../tests/test_secret_hygiene.py) enforces that. See
  [`security_remediation.md`](../../notes/research/security_remediation.md).
- **The two governance documents.** As checked on 2026-09-20, their only change since the first commit was
  the removal of stray chat-citation markers during release preparation. Their rules were not changed.
- **The first day predates git.** The first commit already contains the V8 candidate, so the six
  experiment cycles of 2026-06-20 are traceable through their notes, not through per-experiment commits.

## Decision ledgers

Verdicts are written to machine-readable files, not only to prose. Each model in a ledger gets one label
from a small vocabulary: `reference_only`, `rejected`, `no_evidence_of_improvement`,
`data_insufficient`, `market_comparator_only`, `exploratory_underpowered`.

| Ledger or registry | What it records |
|---|---|
| [`prospective_model_decision_ledger.json`](../../data/reference/prospective_model_decision_ledger.json) | The 2026 prospective benchmark (34 scored fixtures, the lab's exploratory Tier C): `M1_B1` as `reference_only`, `M2_market` as `market_comparator_only`, the three fixed blends as `no_evidence_of_improvement`. The market here is an early line, not a closing line ([ERRATA E2](../ERRATA.md#e2--47-paid-odds-snapshots-never-reached-the-prediction-ledger)). |
| [`model_decision_ledger.json`](../../data/reference/model_decision_ledger.json), [`event_process_model_decision_ledger.json`](../../data/reference/event_process_model_decision_ledger.json), [`residual_goal_intensity_decision_ledger.json`](../../data/reference/residual_goal_intensity_decision_ledger.json), [`international_event_lake_model_decision_ledger.json`](../../data/reference/international_event_lake_model_decision_ledger.json) | Per-line in-play verdicts. None of them contains a promoted candidate. The event-lake ledger records 10 `reference_only` verdicts, while its completion report words the same outcome as `data_insufficient` ([ERRATA E6](../ERRATA.md#e6--two-vocabularies-for-the-same-event-lake-outcome)). |
| [`inplay_result_status_registry.yaml`](../../notes/research/inplay_result_status_registry.yaml) | Ten earlier in-play claims, each with one validity status, including `invalid_due_to_model_selection_on_test_set`. Prior reports were preserved rather than rewritten. |
| [`research_evidence_registry.json`](../../data/reference/research_evidence_registry.json), [`research_truth_registry.json`](../../data/reference/research_truth_registry.json) | Claims checked against files actually on disk; one of the lab's own claims is marked `contradicted`. |
| [`prospective_score_harvest_failure_matrix.json`](../../data/reference/prospective_score_harvest_failure_matrix.json) | Fourteen candidate causes of a silent scoring failure, each with a verdict and evidence. |
| [`approved_models.yaml`](../../configs/approved_models.yaml) | The runtime registry: B1 ternary Elo is the only approved model; everything else is shadow-only. Its `reason_not_approved` text for the V8 candidate still quotes figures that were produced by a bug ([ERRATA E1](../ERRATA.md#e1--the-v8-worse-than-b1-on-2026-result-was-a-bug)). The file is governance-protected and was deliberately left unedited; the valid reason stands: no significant improvement on the development folds. |

One ledger is missing. The hierarchical-transfer decision ledger was cleared during an unfinished repair and
never regenerated ([ERRATA E5](../ERRATA.md#e5--the-hierarchical-transfer-decision-ledger-is-missing)). It
was not reconstructed after the fact.

## Internal audits, and what they caught

The research notes record repeated read-only checks of the agent's own earlier work, sometimes run as
several agents in parallel, each examining a different aspect of a claim before it was trusted. The notes
sometimes call these "independent reviews". They are **internal agent audits, not third-party reviews**.

They did catch real problems:

| What was caught | What was done about it | Record |
|---|---|---|
| **Selection on the test set (in-play).** Model parameters were always fitted on training data only, but the "best" in-play model had been chosen after repeatedly looking at 2026 results. | A status registry relabelled the crowned-model claim `invalid_due_to_model_selection_on_test_set` and downgraded the other 2026-based rankings to exploratory. A nested leave-one-competition-out rerun on 302 StatsBomb men's internationals never selected that model. The frozen in-play model was re-frozen to the plain remaining-time Poisson reference (in-play M2: unfitted, with hand-set constants), and the first freeze was kept as an immutable record. No frozen in-play model was ever scored prospectively, so the freeze is governance machinery, not an evaluated result. | [`inplay_evaluation_reconciliation.md`](../../notes/research/inplay_evaluation_reconciliation.md), [`inplay_nested_evaluation.md`](../../notes/research/inplay_nested_evaluation.md), [`final_holdout_freeze_manifest_v2.json`](../../notes/research/final_holdout_freeze_manifest_v2.json) |
| **Release-gate contamination (pre-match).** The candidate's architecture and its 0.85 blend weight had been chosen with sweeps that touched the 2022 gate. | Selection was re-established on development folds only; 2022 is read once. | [`tier_2_existing_work_audit.md`](../../notes/research/tier_2_existing_work_audit.md) |
| **Two data bugs in the first table.** Group state accumulated across tournaments, and simultaneous final-matchday games leaked into each other. | Both fixed. The first evaluator score, computed on the corrupted table, was declared invalid rather than kept. | [`model_state_reconciliation.md`](../../notes/research/model_state_reconciliation.md) |
| **Own-goal inversion.** The provider's `team` field on an own goal is already the beneficiary; the code flipped it, so Canada 1–2 Morocco had been derived as 0–3. | A versioned, provider-aware event-semantics layer that fails closed when a provider's own-goal semantics are unknown. 48 of 48 cached 2022 group matches then reconciled (previously 47). The same bug later resurfaced in a second module and was fixed there too (12 of 120 mismatches, then none). | [`event_replay_2022_remediation.md`](../../notes/research/event_replay_2022_remediation.md), [`api_football_reconciliation_remediation.md`](../../notes/research/api_football_reconciliation_remediation.md) |
| **Over-reported coverage.** A backfill reported 2,000 of 2,000 fixtures, but only 1,940 were raw-backed in the canonical root. A cache audit claimed 258 files where about 60 were on disk. | Completion gates now measure raw-backed coverage, not list length. One sprint's git tag is literally `research-truth-full-corpus-xg-fusion-incomplete`. | [`RESEARCH_TRUTH_FUSION_OPERATIONS_LOG.md`](../../notes/research/RESEARCH_TRUTH_FUSION_OPERATIONS_LOG.md), [`corpus_coverage_ledger.json`](../../data/reference/corpus_coverage_ledger.json) |
| **A silent scorer failure.** The collector's score step returned success every five minutes and scored nothing: 0 of 680 predictions resolved a finished result. | Root-caused with a 14-candidate failure matrix, then bypassed with an independent, idempotent, append-only harvester. | [`prospective_score_harvest_root_cause_audit.md`](../../notes/research/prospective_score_harvest_root_cause_audit.md), [`SCORE_HARVEST_GUIDE.md`](../SCORE_HARVEST_GUIDE.md) |
| **Why so many results are null.** The match, not the snapshot, is the independent unit. Multiplying snapshots on the same 58 matches left power flat. | A match-level power analysis. On 231 matches, power to detect a 0.005 absolute RPS gain is only 0.28, and 0.80 is first reached at the 1,200-match grid point. An earlier 58-match projection used a more optimistic noise template and is superseded. | [`international_event_lake_power_analysis.md`](../../data/reference/international_event_lake_power_analysis.md), [`minimum_evidence_requirements.json`](../../data/reference/minimum_evidence_requirements.json) |

They also **missed** things. Two latent bugs survived every audit run during the research period and were
found only during the public-release review on 2026-09-20 — itself an internal agent audit:

- [ERRATA E1](../ERRATA.md#e1--the-v8-worse-than-b1-on-2026-result-was-a-bug): a recorded model
  comparison was the product of a dtype bug. An earlier audit had "reproduced" the number — it had
  reproduced the bug.
- [ERRATA E2](../ERRATA.md#e2--47-paid-odds-snapshots-never-reached-the-prediction-ledger): 47 odds
  snapshots were silently ignored because of a key mismatch. The earlier root-cause audit had listed
  snapshot parsing as a *false* cause.

## Who did what

| The human | The agent |
|---|---|
| Set the scope: research-only, paper-only, trading disarmed. | Wrote the code, tests, runbooks, notes and commit messages. |
| Opened the work with a written brief ([`CLAUDE_CODE_MASTER_PROMPT.md`](CLAUDE_CODE_MASTER_PROMPT.md)) and directed each later sprint. | Ran experiments against the fixed evaluator and recorded keep or revert. |
| Created the provider accounts and supplied the keys, which live only in a local, gitignored `.env`. | Reported configuration as `SET` or `MISSING` only. |
| Approved or declined data requests. football-data.org and The Odds API are recorded as approved with keys supplied on 2026-06-20, and StatsBomb Open Data as approved on 2026-06-22. An API-Football Pro plan was paid for. None of the five event-data vendors in the provider decision matrix was contacted, and nothing was bought from them. | Filed a request instead of writing a connector. The folder is named `pending/`, but it holds requests in every state. Each file records its own `status`, and some of those fields were not updated after a later decision. |
| Decided whether to switch collection on. The V1.5 collector's scheduler setup installs nothing automatically and stays in dry-run until `EXECUTE=1` is set; its checklist lists activation as the owner's decision. | Built the bounded, restart-safe collectors and their integrity checks. |
| Holds runtime approval by design. The only approval ever recorded is B1 ternary Elo, dated 2026-06-21. The registry entry itself was written by the agent during its reconciliation audit; the repository holds no separate record of the human sign-off. | Cannot promote: the evaluator returns `promoted=False`. |
| Decided to publish, with the errata attached. | Ran the audits, relabelled its own invalid claims, and drafted the public documentation — including this page — from a fact brief in which each number was re-checked against its source file. |

## Limits of this arrangement

- **Internal audits are not third-party review.** The auditor and the author are the same kind of system and
  can share blind spots. E1 and E2 show that they did. No statistician or outside reviewer has examined
  this work.
- **166 commits in a ten-day span** (2026-06-20 to 2026-06-29), 61 of them on one day (2026-06-26). That
  pace is possible only because an agent did the typing. Line-by-line human review of every diff should
  not be assumed; human oversight was exercised on scope, data approvals and decisions.
- **Commit subjects are long.** The median is roughly 170–180 characters and the longest is 690. They read
  as short reports rather than conventional subjects. History was left as it is rather than rewritten. As
  of the public release, every commit carries a `Co-Authored-By: Claude …` trailer under a single research
  git identity.
- **The contract covers the loop, not the lab** (see [Scope of the contract](#scope-of-the-contract)), and
  protected paths did receive a small number of additive edits.
- **Some safety statements are attestations.** Lines such as "collector untouched" or "no secret printed" in
  the notes are the agent's own reports. Tests back several of them
  ([`test_secret_hygiene.py`](../../tests/test_secret_hygiene.py),
  [`test_runtime_governance.py`](../../tests/test_runtime_governance.py), `tests/test_kalshi_safety.py`), but
  not all.
- **Pre-specification is self-attested.** The prospective snapshot-selection rule was written on
  2026-06-29, after the matches had been played but, according to the file's own statement, before any
  model-versus-outcome metric was computed. The rule depends only on timestamps and coverage, not on
  outcomes. Still, the rule, the script and the results share one commit, so the git history cannot
  establish the ordering.
- **One cycle is not sustained autonomy.** The 20-experiment autoresearch cycle ran in a single session.
  Its own report says a single agent turn cannot stay open for eight hours.

## Files in this folder

| File | What it is | Status |
|---|---|---|
| [`START_HERE_CLAUDE_CODE.md`](START_HERE_CLAUDE_CODE.md) | The six-step handoff checklist: create `.env`, keep trading disarmed, open the repository in Claude Code, paste the master prompt, run the tests and the `SET` / `MISSING` audit first. | Current |
| [`CLAUDE_CODE_MASTER_PROMPT.md`](CLAUDE_CODE_MASTER_PROMPT.md) | **The current first prompt.** It fixes the reading order, the configuration audit, the no-account data sources, the table rules, the development / gate / locked fold hierarchy, baselines B0–B7, the autoresearch loop and the data-request rule — all before any result existed. It also forbids calling the model "very good" without robust out-of-sample improvement over both the Elo and market baselines. | Current |
| [`CLAUDE_CODE_BOOTSTRAP_PROMPT.md`](CLAUDE_CODE_BOOTSTRAP_PROMPT.md) | The older, shorter first prompt: inspect, run the tests, list what is missing, propose a staged plan. Superseded by the master prompt and kept for the record. | Historical |

Related files outside this folder:

| File | What it is |
|---|---|
| [`../../program.md`](../../program.md) | The contract for the autoresearch loop: editable file, protected paths, objective, folds, allowed and forbidden hypothesis families. |
| [`../../AGENTS.md`](../../AGENTS.md), [`../../CLAUDE.md`](../../CLAUDE.md) | Short entry points that agent tools look for at the repository root; both point to `program.md`. |
| [`../AUTORESEARCH_GOVERNANCE.md`](../AUTORESEARCH_GOVERNANCE.md) | Why the research and execution planes are separated, and the promotion steps. |
| [`../../data_requests/TEMPLATE.yaml`](../../data_requests/TEMPLATE.yaml) | The template every new-source request starts from. |
| [`../../scripts/setup_claude_code.sh`](../../scripts/setup_claude_code.sh) | Optional convenience bootstrap, run from the repository root: creates `.venv`, installs the requirements and the package in editable mode, and runs `pytest -q`. It installs no scheduler, reads no credential and starts no collector. |

See also [`../GLOSSARY.md`](../GLOSSARY.md) for model names and [`../ERRATA.md`](../ERRATA.md) for every
known defect.
