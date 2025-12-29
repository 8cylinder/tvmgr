# tvmgr

A Python CLI tool for managing TV shows and movies on Kodi media
centers. Automatically deletes watched episodes and movies from SMB
shares or mounted directories to free up storage space.

## Features

- **Network Discovery**: Scan your network to find Kodi devices
- **Multiple Access Modes**: Connect via JSON-RPC API or local database
- **Smart Deletion**: Only removes watched content, preserves unwatched
- **Keep Lists**: Protect specific shows from deletion
- **Flexible Storage**: Works with SMB shares or mounted directories
- **Directory Cleanup**: Find and clean up empty media directories

## Requirements

### System Dependencies

Before installing, you need the SMB client development libraries:

**Ubuntu/Debian:**
```bash
sudo apt-get install libsmbclient-dev
```

**Fedora/RHEL:**
```bash
sudo dnf install libsmbclient-devel
```

**macOS:**
```bash
brew install samba
```

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for package
management.

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install Dependencies

```bash
uv sync
```

This will install all required dependencies including click, pysmbc,
and requests.

## Build

To build a distributable package:

```bash
uv build
```

This creates wheel and source distributions in the `dist/` directory.

## Usage

Run commands using `uv run`:

```bash
uv run tvmgr --help
```

Or install and use the `tvmgr` command directly:

```bash
uv tool install -e .
tvmgr --help
```

### Commands

#### Discover Kodi Devices

Scan your network to find Kodi devices:

```bash
# Scan default networks (192.168.0.0/24 and 192.168.1.0/24)
uv run tvmgr discover

# Scan custom network
uv run tvmgr discover --network 10.0.0.0/24

# Scan multiple networks
uv run tvmgr discover --network 192.168.0.0/24 --network 10.0.0.0/24
```

Displays detailed information about each Kodi device found:
- Device name and version
- Library statistics (shows, episodes, movies)
- Current playback status
- System capabilities

#### Delete via JSON-RPC API

Connect to a Kodi device and delete watched content via its JSON-RPC
API:

```bash
uv run tvmgr viajson 192.168.1.100
```

This command:
1. Connects to Kodi at the specified IP address (port 8080)
2. Queries for watched episodes and movies
3. Deletes the files via SMB protocol

#### Delete via Database

Use a local Kodi database file to identify watched content:

```bash
uv run tvmgr viadb /path/to/MyVideos119.db
```

This command:
1. Reads the Kodi SQLite database directly
2. Identifies watched content
3. Deletes files via SMB or mounted directory

#### Clean Up Directories

Find and optionally clean up empty media directories:

```bash
# Scan one or more root directories
uv run tvmgr cleanup /home/sm/net1/TV /home/sm/net1/Movies
```

Lists directories that:
- Have video files (preserved)
- Don't have video files (candidates for removal)

Supported video formats: .mp4, .mkv, .avi, .mpg, .mpeg, .mov, .flv,
.wmv, .iso

## Configuration

### Kodi Connection

Default connection settings for JSON-RPC:
- Port: 8080
- Username: kodi
- Password: (none)

### SMB Authentication

Default SMB credentials are hard-coded in `tv_manager.py`:
- Username: sm
- Password: Password123

Edit the `auth_fn()` function to change these credentials.

### Keep List

Protect specific shows from deletion by editing the `keep_list` in
`tv_manager.py`:

```python
keep_list = [
    "Show Name",
    "Another Show",
]
```

Show names are normalized (spaces/underscores removed, lowercased) for
matching.

### Path Mapping

For mounted directories instead of SMB, configure path translation in
`ShowFile.__init__()` in `tv_manager.py`:

```python
smbc://server/Volume_1/...  →  /home/sm/net1/...
```

## Development

### Project Structure

- `src/tvmgr/cli.py` - Click-based CLI interface
- `src/tvmgr/tv_manager.py` - Core deletion and file management logic
- `src/tvmgr/discover.py` - Network scanning and Kodi discovery

### Running Tests

```bash
uv run pytest
```

## License

See LICENSE file for details.

## Author

Sheldon McGrandle <developer@8cylinder.com>
