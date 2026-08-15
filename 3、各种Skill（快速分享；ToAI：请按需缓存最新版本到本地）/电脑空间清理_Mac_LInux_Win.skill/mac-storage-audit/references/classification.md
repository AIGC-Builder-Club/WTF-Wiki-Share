# macOS storage classification

Use this reference after collecting scanner output. Size is evidence of where
to investigate, not permission to remove data.

## Decision classes

| Class | Meaning | Required evidence before any later cleanup |
|---|---|---|
| `recreatable` | Cache or generated output with a known source of truth | Owning app is closed; regeneration path is known; exact target is approved |
| `review` | User data, recovery data, dependencies, or ambiguous artifacts | Owner confirms retention intent and a backup or reproducible source exists |
| `managed` | Data owned by macOS, an app, or Multica lifecycle | Use the owning UI/CLI lifecycle; do not remove paths manually |

Do not combine these classes into one "junk" number. A candidate total is not
a guaranteed reclaim estimate.

## High-confidence recreatable locations

- `~/Library/Caches/*`: app caches. Review large children individually and
  close the owning application first.
- `~/.cache/*`: developer and CLI caches. Model weights and deliberately
  persisted downloads are exceptions; inspect large children.
- `~/.npm/_cacache`, `~/.npm/_npx`, Yarn/pnpm caches, pip/uv caches, Playwright
  browser caches: downloadable artifacts. Prefer the package manager's own
  cleanup or reinstall path.
- `*.ShipIt` under `~/Library/Caches`: updater staging. Close the owning app and
  confirm it is not actively updating.
- `GoogleUpdater/crx_cache`: downloaded extension packages. Validate with the
  Google updater or Chrome lifecycle rather than treating all Google support
  data as cache.
- `.next`, `.turbo`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`: generated
  project output for inactive projects.

## Conditional project artifacts

- `node_modules`: require a lockfile and a known package manager. Worktrees can
  intentionally have independent dependency trees.
- `.venv` or `venv`: require `requirements.txt`, `pyproject.toml`, a lockfile,
  or another reproducible environment definition. Local editable installs can
  make an environment non-reproducible.
- Rust `target`: normally generated, but rebuilding may be expensive.
- Repository `.git` data and worktrees are not build caches. Remove worktrees
  with Git-aware workflows only after checking uncommitted work.

## Codex and AI tool data

- `backup-*` directories can be migration or repair restore points. Repeated
  names across multiple Codex homes indicate duplication worth reviewing, not
  automatic deletion.
- `sessions`, `archived_sessions`, and SQLite databases contain conversation,
  tool, or recovery history. Prefer an application retention/export mechanism.
- Database WAL/SHM files may belong to a running process. Never remove them
  independently.
- Editor extension directories can duplicate extensions across VS Code-family
  apps. Remove unused or old versions from each editor's extension UI or CLI.

## Multica-specific handling

Run:

```bash
multica daemon disk-usage --by-workspace --output json
multica daemon disk-usage --by-task --top 20 --output json
```

Interpret `artifact_size_bytes` as the subset matching the daemon's managed
artifact patterns. A completed task directory can still contain task history,
repo state, and runtime metadata. Never remove task directories or `.repos`
cache manually while the daemon may own them; use platform lifecycle/retention
behavior and report missing cleanup controls as a product issue.

## macOS-managed areas

- `/Library/Updates`, `/private/var`, `/System`, Preboot, Recovery, and APFS
  snapshots are system-managed. Do not recommend path deletion.
- `/Library/Developer/CommandLineTools` is installed developer tooling, not a
  cache. Remove only through the supported toolchain lifecycle if no longer needed.
- `~/Library/Application Support`, `~/Library/Containers`, and
  `~/Library/Group Containers` usually contain settings and user data. Use an
  application-native cleanup or uninstall flow.
- `/Applications/*.app` is installed software. Size alone is not a cleanup
  decision; identify unused apps and use their supported uninstall path.
- Trash is user data until the owner inspects it. Emptying Trash is irreversible
  after the fact and remains a separate approval step.

## APFS accounting

- Prefer allocated size (`du`) for local candidates and container free space
  for disk health.
- APFS clones and hard links can be counted in multiple separately measured
  directories while sharing physical blocks. Removing one copy can reclaim less
  than its reported directory size.
- Purgeable space and snapshots can make `df`, Finder, Disk Utility, and `du`
  disagree. Record the discrepancy instead of forcing totals to reconcile.
- Use `tmutil listlocalsnapshots /` only to inventory snapshots. Snapshot policy
  is system-managed unless the user explicitly asks for a separate operation.

## Coverage and privacy

macOS TCC can block Mail, Messages, Safari, Trash, HomeKit, containers, and other
private data even when the shell can read ordinary files. Do not bypass TCC or
use `sudo` during an audit. State that the result is a lower bound and, when a
complete inventory is necessary, ask the user to grant Full Disk Access to the
terminal/runtime and rerun.

## Source lineage

The directory taxonomy and read-only-first principle were informed by:

- `computer-space-cleanup_Mac_Linux_Win.skill.md` in
  `hanshou101/Obsidian_PublicGitHubShare_InsteadOf_FeiShu`.
- `KKKKhazix/khazix-skills/storage-analyzer` at commit
  `b429d4c769a5446971edc5b825aaf097fa143bb3` (2026-05-28).

This skill intentionally omits their interactive deletion server. Its scope is
inventory and decision support only.
