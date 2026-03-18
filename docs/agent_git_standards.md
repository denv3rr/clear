# Agent Git And Branch Standards

This document defines the mandatory git workflow for agents working in this
repo. It extends [docs/us_gov_standards.md](docs/us_gov_standards.md) with
branching, review, merge, and remote-operation rules.

If this document conflicts with a convenience workflow, this document wins.

## Mandatory Re-Skim Rule

Before any non-trivial code, test, data, docs, UI, or infrastructure update:

1. Re-skim [docs/us_gov_standards.md](docs/us_gov_standards.md).
2. Re-skim this file.
3. Confirm the planned git path matches the risk of the change.

## Branch Creation Rules

Create or move to a dedicated branch when the work is more than a tiny local
edit, touches multiple files, changes behavior, or may need review, rollback,
or parallel work.

Use these prefixes:

- `feature/<area>-<slug>` for user-visible features or capability expansion
- `bugfix/<area>-<slug>` for non-emergency defect fixes
- `hotfix/<area>-<slug>` for urgent production-facing fixes
- `refactor/<area>-<slug>` for structural cleanup without intended behavior change
- `docs/<area>-<slug>` for documentation-only work
- `test/<area>-<slug>` for test-only additions or repairs
- `research/<area>-<slug>` for bounded investigation that may produce notes or proof-of-cause work
- `chore/<area>-<slug>` for maintenance tasks that are not product features
- `release/<version-or-date>` for controlled release preparation when needed

Branch names must be plain, deterministic, and searchable. Do not use vague
names like `stuff`, `misc`, `temp`, or `try-this`.

## When Agents May Use Git Remote Operations

Agents may create branches, fetch, pull, push, open PRs, approve, merge, or
close branches when needed for the work and when repo permissions allow it.

Those actions are only allowed when all of the following are true:

1. The change follows [docs/us_gov_standards.md](docs/us_gov_standards.md).
2. The diff has been reviewed for secrets, local files, fabricated data paths,
   and unrelated changes.
3. The affected tests were run, or any blocker was recorded explicitly.
4. The remote action does not rewrite or discard user work without permission.

## Pull, Merge, And Push Rules

- Fetch or pull before pushing when the remote may have moved.
- Prefer short-lived branches and small merge surfaces.
- Resolve conflicts deliberately; never auto-resolve by dropping unknown code.
- Do not force-push, reset shared history, or amend published commits unless
  the user explicitly asks for that recovery action.
- Do not merge until the branch diff, test evidence, and standards checks have
  been reviewed together.
- If approvals are part of the repo workflow, approval means the agent checked
  the real diff and evidence, not just that automation was green.

## Sensitive Files And Commit Exclusions

Never commit, stage, push, or merge:

- `.env`, `.env.*`, `.envrc`, secrets, private keys, certificates, or tokens
- `AGENTS.md`, `GEMINI.md`, `agent.ps1`, `agents/`, `.codex/`, or other
  agent-only instructions/state
- local runtime state, caches, pid files, logs, screenshots, exports, reports,
  or generated personal data unless the change explicitly requires a reviewed fixture
- machine-specific settings or clearly sensitive local files

Before any commit or push:

1. Check `git status`.
2. Review the staged diff.
3. Confirm sensitive paths remain ignored or unstaged.
4. Remove accidental staging before proceeding.

## Commit And PR Standards

- Keep commits scoped to one logical change when practical.
- Commit messages should state the actual change, not a vague intention.
- PR descriptions or merge notes should include purpose, risk, tests, and any
  known follow-up work.
- If the work fixes a bug, record the verified root cause, not just the symptom.
- If the work is docs-only, say so and avoid claiming runtime validation that
  did not happen.

## Fail-Safe Git Behavior

- If branch state is unclear, stop and inspect before pushing.
- If unrelated local changes are present, work around them instead of reverting
  them unless the user explicitly asks.
- If a secret or sensitive file is accidentally staged, unstage it immediately
  and inspect the rest of the index before continuing.
- If a merge or rebase would risk data loss, pause and choose the safer path.

## Minimum Pre-Push Checklist

1. Correct branch name for the work type.
2. No secrets, env files, agent files, or local runtime artifacts in the diff.
3. No fabricated data, fake visuals, placeholder math, or silent hacks.
4. Root cause understood for bug fixes.
5. Affected tests run or blocker explicitly recorded.
6. Diff reviewed for unrelated changes.

## Default Branch Guidance

If the user does not specify a branch strategy:

- use the current branch for small local edits that are not being pushed yet
- create a dedicated branch before larger multi-file work or any remote push
- keep branch scope narrow so merge and rollback stay simple
