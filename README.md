# ResticDesk <img alt="Logo" src="https://files.qmax.us/vorta/vorta-512px.png" align="right" height="50">

ResticDesk is a desktop backup client for Linux and macOS, focused on making [Restic](https://restic.readthedocs.io/en/stable/) easier to use through a native GUI.

This project is a public fork/reboot of [Vorta](https://github.com/borgbase/vorta), migrated from Borg to Restic.

## Project Scope
- This project is primarily maintained for personal use. If it ends up being useful for other people, even better.
- Development is intentionally lightweight and done in a vibe-coding style, since maintainer time and long-term commitment are limited.

## Project Status
Current status: `alpha`.

Working today:
- Create backups with compression settings and profile-based sources.
- List snapshots and refresh metadata.
- Restore files/folders from selected snapshots.
- Retention and cleanup via `restic forget --prune`.
- Repository check via `restic check`.
- Repository mount/unmount.

Known limitations (in progress):
- Snapshot rename is not supported (Restic does not provide archive-style rename semantics).
- Snapshot diff in the legacy Vorta UI format is currently disabled.
- Some UI/internal names still use historical `Borg*` identifiers while the backend is already Restic.
- Translation catalogs still contain legacy Borg strings and need a full refresh.

## Known Issues
- GUI tests can fail in headless environments due to Qt initialization constraints.
- Some translated languages still display legacy Borg terminology until translation updates are completed.
- Snapshot `diff` and `rename` are intentionally unavailable with the current Restic backend implementation.

## Why ResticDesk
- Encrypted, deduplicated backups powered by Restic.
- No vendor lock-in: local disks or your own remote storage.
- Multiple backup profiles with scheduling and per-profile source selection.
- Point-in-time snapshot browsing and restore from one interface.
- Open source and auditable.

## Installation
No official release binaries are published yet for this fork.

For now, use the development setup below.

## Development Setup
This repository uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Install uv (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone your fork
git clone git@github.com:msambinelli/ResticDesk.git
cd ResticDesk

# Install dependencies
uv sync

# Run app
uv run vorta

# Run tests
uv run pytest
```

Notes:
- You need a working `restic` binary in your `PATH`.
- GUI tests may require a desktop/Qt-capable environment.

## Usage Notes
- Use repository URLs/paths compatible with Restic backends.
- Retention settings are applied through Restic forget/prune semantics.
- Mount currently targets full repository mount (not single-snapshot mount).

## Roadmap
Short term:
- Full UI terminology cleanup (`archive` vs `snapshot`, user-facing strings).
- Remove/rename remaining internal `Borg*` code identifiers.
- Refresh translation catalogs and regenerate compiled `.qm` files.
- Expand Restic-native integration tests.

Mid term:
- Improve snapshot diff UX with a Restic-compatible approach.
- Improve restore previews and mount navigation UX.
- Add release packaging for Linux/macOS.

## Contributing
Contributions are welcome.

Recommended contribution flow:
- Open an issue describing bug/feature and reproduction steps.
- Keep PRs focused and small.
- Include tests or clear manual validation notes.

For code style and tooling, follow project conventions already present in the repository.

## License and Attribution
- Licensed under [GPLv3](LICENSE.txt).
- This project is based on the Vorta codebase; see [CONTRIBUTORS.md](CONTRIBUTORS.md) for original and ongoing contributor credits.
- Original Vorta project: https://github.com/borgbase/vorta
