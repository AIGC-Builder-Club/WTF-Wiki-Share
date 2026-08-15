---
name: mac-storage-audit
description: >-
  Perform a read-only macOS disk-space audit and triage cleanup candidates by
  evidence, reversibility, and ownership. Use when a user asks what consumes
  Mac storage, why a disk is full, what can be cleaned, or how developer,
  Codex, package-manager, and Multica data contribute to disk use. Produce a
  JSON or Markdown inventory without deleting, moving, truncating, uninstalling,
  or changing permissions.
---

# Mac Storage Audit

Audit first. Treat cleanup as a separate, explicitly approved task.

## Safety contract

- Run only read/stat/list/size commands. Never use `rm`, `mv`, `rmdir`, trash
  APIs, cache-cleaning commands, uninstallers, or permission changes.
- A report file explicitly requested with `--output` is the only write the
  bundled script performs.
- Do not use `sudo` merely to improve scan coverage. Record protected paths as
  blind spots and explain how Full Disk Access changes coverage.
- Never classify an application-support directory, container, session history,
  database, repository, or Multica task directory as disposable from age or
  size alone.
- Do not expose serial numbers, device UUIDs, tokens, secrets, or unrelated
  filenames in the report.

## Workflow

1. Read [references/classification.md](references/classification.md).
2. Run the scanner. Add project roots that matter on this machine:

```bash
python3 scripts/audit.py --format json \
  --project-root "$HOME/Projects" \
  --project-root "$HOME/work"
```

3. If the first pass identifies other large project roots, rerun with those
   exact roots. Use `--deep` only when container detail is necessary; it can be
   slow and incomplete without Full Disk Access.
4. Cross-check physical free space against category totals. APFS clones, hard
   links, purgeable blocks, and separate `du` calls can make category totals
   non-additive.
5. Present three decision groups:
   - `recreatable`: caches and generated output with a verified source of truth.
   - `review`: backups, sessions, dependencies, extensions, downloads, and user data.
   - `managed`: macOS, applications, containers, and Multica runtime data that
     must be handled through their owning system or application.
6. State coverage gaps and give a prioritized review order. Report candidate
   sizes as estimates, never as guaranteed reclaimed space.

## Useful invocations

Human-readable report:

```bash
python3 scripts/audit.py --format markdown
```

Broader project scan with a report file:

```bash
python3 scripts/audit.py --format markdown --deep \
  --project-root "$HOME/Projects" --output ./mac-storage-audit.md
```

Pure in-memory script checks:

```bash
python3 scripts/audit.py --self-test
```

## Interpretation rules

- Prefer application-native or package-manager dry runs when validating a
  candidate, for example `brew cleanup --dry-run` or `mole clean --dry-run`.
- Treat `.next` and similar build output as recreatable only for inactive
  projects. Treat `node_modules` as conditional on a valid lockfile and virtual
  environments as conditional on a dependency manifest.
- Treat Codex `backup-*`, `sessions`, and SQLite files as history or recovery
  data. Verify migration success, export needs, and retention intent first.
- For Multica, use `multica daemon disk-usage --output json` as the authoritative
  inventory. Never manually delete active or completed task directories.
- Keep system updates, `/private/var`, APFS snapshots, app containers, and
  application-support data out of direct-delete recommendations.

## Deliverable

Lead with disk health and urgency. Then report measured candidates, risk,
confidence, owner-approved cleanup route, and scan blind spots. Separate
logical candidate size from expected physical reclamation.
