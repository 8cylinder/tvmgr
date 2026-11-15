# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

## Project overview

`tvmgr` is a Python CLI tool for managing TV shows and movies on Kodi
media centers. It deletes watched episodes and movies from SMB shares or
mounted directories to free up storage space, with a configurable keep
list to preserve specific shows.

## Development commands

Dependencies are managed with `uv`. Use the Makefile for routine work:

```bash
make sync       # install dependencies
make fmt        # format
make lint       # lint and apply safe fixes
make type       # type-check
make test       # run tests
make check      # all checks without changing files
make build      # wheel and sdist
```

`make sync` selects `clang` when it is installed and falls back to `gcc`
for building the `pysmbc` C extension. Override it with
`make SMBC_CC=gcc sync`.

Run the CLI with `uv run tvmgr ...` or, after `make install`, `tvmgr ...`.

## Architecture

### Entry point

- `pyproject.toml` maps `tvmgr = "tvmgr.cli:main"`.
- `src/tvmgr/__init__.py` contains only the package docstring.
- `src/tvmgr/__main__.py` supports `python -m tvmgr`.

### Modules

- `cli.py` — Click command tree, global options, and command dispatch.
  Keep this layer thin.
- `config.py` — TOML configuration loading, validation, and defaults.
- `kodi.py` — Kodi JSON-RPC queries (`viajson` data and `discover` info).
- `discover.py` — parallel network scanning for Kodi devices.
- `tv_manager.py` — deletion logic, SMB/local file adapters, and cleanup
  helpers.
- `completions.py` — static bash completion generation and installation.
- `ui.py` — Rich consoles and status helpers.

### Command flow

- `viajson` calls `kodi.get_watched_media()`, then
  `tv_manager.delete_files()`.
- `viadb` reads the Kodi SQLite database (using `tv_manager.sql`) and passes
  the cursor to `delete_files()`.
- `cleanup` walks directory trees with `walk_bottom_up()`.
- `discover` scans networks and calls `kodi.get_kodi_info()`.

### Configuration

`config.load_config()` reads `~/.config/tvmgr/config.toml` (platform
dependent) and returns a frozen `Config` object. Precedence is command-line
option, then config value, then built-in default. The root callback loads it
once and stores `AppContext(config, ui)` on `ctx.obj`.

The SMB credentials, keep list, path mapping, Kodi connection settings, and
discover defaults are all configurable. Defaults match the original
hard-coded behavior.

### Output

All human-facing output goes through the Rich consoles in `ui.py`. Machine
output (`--version`, `--config`, `--completions`, and `cleanup --null`) must
stay plain and free of ANSI escapes. Escape dynamic values with
`rich.markup.escape()` before interpolating them into markup.

## Testing

Tests live in `tests/` and use pytest. They must not touch the real home
directory, network, SMB shares, or system configuration. Use `tmp_path` and
`monkeypatch`; mock Kodi HTTP calls and SMB contexts. Branch coverage must
stay at or above 90%.

## Dependencies

- `click` — CLI framework
- `rich` — terminal output
- `platformdirs` — per-user config and data paths
- `pysmbc` — SMB/CIFS support (requires `libsmbclient-dev`)
- `requests` — Kodi JSON-RPC HTTP requests

`pysmbc` has no wheels; it is compiled during installation and needs a C
compiler, `pkg-config`, and the SMB client development headers.

## License

GPL-2.0-only. See `LICENSE`.
