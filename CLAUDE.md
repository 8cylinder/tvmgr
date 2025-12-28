# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when
working with code in this repository.

## Project Overview

`tvmgr` is a Python CLI tool for managing TV shows and movies on Kodi
media centers. It deletes watched episodes/movies from SMB shares or
mounted directories to free up storage space, with configurable
keep-lists to preserve specific shows.

## Development Commands

**Install dependencies:**
```bash
uv sync
```

**Run the CLI:**
```bash
# Via the installed script
tvmgr --help

# Or directly with Python
python -m tvmgr
```

**Available CLI commands:**
- `tvmgr discover` - Scan network to find Kodi devices and display detailed info
  - Default: scans 192.168.0.0/24 and 192.168.1.0/24
  - Custom: `--network 10.0.0.0/24` (can specify multiple times)
- `tvmgr viajson <ip-address>` - Delete using Kodi's JSON-RPC API and SMBC
- `tvmgr viadb <kodi-database>` - Delete using local Kodi database and SMBC
- `tvmgr cleanup <roots...>` - List directories with/without video files

**Note:** The project uses `uv` as the build system (specified in pyproject.toml).
All commands must be run with `uv run` (e.g., `uv run tvmgr discover`).

## Architecture

### Entry Point Flow

The unusual entry point structure is important to understand:
- `src/tvmgr/__init__.py` imports and immediately calls `main()` from `cli.py`
- The CLI is exposed via `[project.scripts]` as `tvmgr = "tvmgr:main"`
- This means the main function runs on import (unconventional but intentional)

### Core Components

**CLI (cli.py):**
- Click-based CLI interface with four main commands: `discover`, `viajson`, `viadb`, and `cleanup`
- All Click decorators, command routing, and UI formatting are here
- Imports business logic from `tv_manager.py` and `discover.py`

**TV Manager (tv_manager.py):**
- Business logic for file operations and deletion
- `delete_files()` - Core deletion logic that works with both SMBC and local files
- `ShowFile` class - Adapter that mimics SMBC's API for local filesystem operations
- Note: Still imports `click` because `delete_files()` uses `click.echo()` for output

**Discovery (discover.py):**
- Network scanning to find Kodi devices (port 8080 detection)
- JSON-RPC communication to verify and query Kodi instances
- `discover_kodi()` - Scans network(s) in parallel using ThreadPoolExecutor
  - Accepts single network string, list of networks, or None for defaults
  - Default networks: ["192.168.0.0/24", "192.168.1.0/24"]
  - Uses parallel scanning with 100 worker threads for performance
- `get_kodi_info()` - Gathers comprehensive device information via JSON-RPC API
  - System info (name, version, volume, capabilities)
  - Library statistics (TV shows, episodes, movies)
  - Current player status
  - Add-on counts

**Data Sources:**
1. **JSON-RPC API** (`viajson` command) - Queries Kodi directly over
   HTTP for watched media
2. **SQLite Database** (`viadb` command) - Reads Kodi's local video
   database directly
3. Both sources feed the same `delete_files()` function

**File Access Modes:**
- SMBC mode: Direct SMB protocol access via `pysmbc` library
- Mount mode: Local filesystem access via `ShowFile` adapter class
- Path translation in `ShowFile.__init__`:
  `smbc://server/Volume_1/...` → `/home/sm/net1/...`

### Keep List Mechanism

The `keep_list` global variable (tv_manager.py:37-40) protects
specific shows from deletion:
- Strings are normalized (spaces/underscores removed, lowercased) for matching
- Applied in `delete_files()` before deletion (tv_manager.py:112-116)

### Authentication

Hard-coded credentials in `auth_fn()` (tv_manager.py:86-91):
- SMB username: "sm"
- SMB password: "Password123"
- This is intentional for local network use but should be noted for security

## Dependencies

- `click` - CLI framework
- `pysmbc` - SMB/CIFS protocol support (requires system libraries: libsmbclient-dev)
- `requests` - HTTP requests for Kodi JSON-RPC API

The `pysmbc` dependency requires system packages to be installed first
(see error message in tv_manager.py:15-19).

## Configuration Points

**Kodi Connection (JSON-RPC):**
- Default port: 8080
- Default credentials: username "kodi", no password
- Endpoint format: `http://{ip}:8080/jsonrpc`

**Path Mapping:**
- SMB drive: `/Volume_1` (tv_manager.py:63)
- Local mount: `/home/sm/net1` (tv_manager.py:64)

**Video File Extensions:** Defined in `cleanup` command
(tv_manager.py:409-419): .mp4, .mkv, .avi, .mpg, .mpeg, .mov, .flv,
.wmv, .iso
