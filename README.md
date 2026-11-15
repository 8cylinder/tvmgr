# tvmgr

Manage TV shows and movies on Kodi media centers. `tvmgr` deletes watched
episodes and movies from SMB shares or mounted directories to free up
storage, with a configurable keep list to protect specific shows.

[![License: GPL-2.0-only](https://img.shields.io/badge/license-GPL--2.0--only-blue.svg)](https://github.com/8cylinder/tvmgr/blob/main/LICENSE)

Repository: <https://github.com/8cylinder/tvmgr>

## Requirements

- Python 3.11 or newer.
- Linux or macOS.
- A C compiler, `pkg-config`, and the SMB client development libraries.
  `pysmbc` is a C extension and is compiled during installation.
- bash 4.4 or newer for bash completions.
- bash-completion 2.18 or newer for automatic completion loading.

### System dependencies

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install build-essential pkg-config libsmbclient-dev
```

**Fedora/RHEL:**

```bash
sudo dnf install gcc make pkgconf-pkg-config libsmbclient-devel
```

**macOS:**

```bash
xcode-select --install
brew install samba pkg-config
```

`make sync` uses `clang` when it is installed and falls back to `gcc`.
Override the choice with `make SMBC_CC=gcc sync`.

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for package
management.

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### From source

```bash
git clone https://github.com/8cylinder/tvmgr.git
cd tvmgr
make sync
make install
```

`make install` installs the `tvmgr` command, bash completions, and the man
page. All install targets are user-level and do not require `sudo`.

To install only the command with uv:

```bash
uv tool install --editable .
```

## Quick start

Scan the default networks for Kodi devices:

```bash
tvmgr discover
```

List the watched files on a Kodi device without deleting anything:

```bash
tvmgr viajson 192.168.1.100
```

Delete the files after confirming the list:

```bash
tvmgr viajson 192.168.1.100 --real
```

## Command reference

Show help for the root command or any subcommand:

```bash
tvmgr --help
tvmgr -h
tvmgr viadb --help
```

### Global options

| Option | Description |
| --- | --- |
| `-h`, `--help` | Show help and exit. |
| `--version` | Show the version and exit. |
| `--color [auto\|always\|never]` | Control colored output. Default: `auto`. |
| `--config` | Print the config file path and exit. |
| `--completions` | Write bash completions and exit. |

Global options must appear before the subcommand.

### `tvmgr discover`

Scan networks for Kodi devices and print system, library, player, and add-on
information.

| Option | Description |
| --- | --- |
| `--network CIDR` | Network to scan. Repeat for multiple networks. Default: `192.168.0.0/24` and `192.168.1.0/24`. |
| `--timeout SECONDS` | Connection timeout. Default: `0.5`. |

### `tvmgr viajson IP-ADDRESS`

Read watched media from Kodi's JSON-RPC API and delete the files over SMB.

| Option | Description |
| --- | --- |
| `--real` | Delete files instead of only listing them. |
| `-v`, `--verbose` | Print extra detail. |
| `--hide-deleted` | Do not print files that no longer exist. |
| `-t`, `--tv` | Process TV episodes. This is the default. |
| `-m`, `--movies` | Process movies. |

JSON-RPC must be enabled in Kodi. See
<https://kodi.wiki/view/JSON-RPC_API> for details.

### `tvmgr viadb KODI-DATABASE`

Read watched media from a local Kodi video database and delete the files.

| Option | Description |
| --- | --- |
| `--real` | Delete files instead of only listing them. |
| `-v`, `--verbose` | Print extra detail. |
| `--hide-deleted` | Do not print files that no longer exist. |
| `--smbc`, `--mount` | Access files over SMB (default) or through a mounted directory. |

Run Kodi's "Clean library" before reading the database so stale entries do
not produce "File does not exist" messages.

### `tvmgr cleanup ROOTS...`

List directories that do or do not contain video files.

| Option | Description |
| --- | --- |
| `-0`, `--null` | Separate output with NUL characters instead of newlines. |
| `-s`, `--show {e,f,b}` | Show (e)mpty directories, (f)ull directories, or (b)oth. Default: `e`. |

Supported video extensions: `.mp4`, `.mkv`, `.avi`, `.mpg`, `.mpeg`, `.mov`,
`.flv`, `.wmv`, `.iso`.

## Configuration

Run `tvmgr --config` to print the configuration path. On Linux this is
`~/.config/tvmgr/config.toml`; macOS uses the platform application-support
directory.

A missing file is not an error and built-in defaults are used. Invalid TOML
is an error and is reported with the file path. Unknown keys produce a
warning on stderr.

```toml
# ~/.config/tvmgr/config.toml
keep_list = ["Deadwood", "Rick and Morty"]

[kodi]
port = 8080
username = "kodi"
password = ""

[smb]
username = "sm"
password = "Password123"
workgroup = ""

[paths]
smbc_drive = "/Volume_1"
mount_base = "/home/sm/net1"

[discover]
networks = ["192.168.0.0/24", "192.168.1.0/24"]
timeout = 0.5
```

Precedence is command-line option, then configuration value, then built-in
default. Relative paths in the configuration are resolved against the
configuration file's directory. The configuration file may contain
credentials; restrict its permissions if needed.

## Bash completions

Generate the static completion script:

```bash
tvmgr --completions
```

The command prints the absolute path and writes the script to
`bash-completion/completions/tvmgr.bash` under `BASH_COMPLETION_USER_DIR`,
`XDG_DATA_HOME`, or `~/.local/share`, in that order. Source it in the current
shell with:

```bash
source ~/.local/share/bash-completion/completions/tvmgr.bash
```

The script requires bash 4.4 or newer. Automatic loading requires
bash-completion 2.18 or newer, which prefers the `.bash` suffix. macOS
`/bin/bash` is version 3.2; install a newer bash with
`brew install bash` or use `tvmgr --completions` from that shell. zsh is not
supported. Rerun `tvmgr --completions` after changing commands or options.

## Man page

Build the man page:

```bash
make man
```

View it without installing:

```bash
man -l docs/_build/man/tvmgr.1
```

`make install-man` installs it to
`$XDG_DATA_HOME/man/man1/tvmgr.1` (or `~/.local/share/man/man1`). If
`man tvmgr` cannot find the page, add that directory to `MANPATH`.

## Documentation website

Build the HTML documentation:

```bash
make docs
```

Serve it locally with live reload:

```bash
make docs-serve
```

The published site is <https://8cylinder.github.io/tvmgr/>. `README.md` is
the manually written landing page and is included in the Sphinx site.

## Development

```bash
make sync       # install dependencies
make fmt        # format
make lint       # lint and apply safe fixes
make type       # type-check
make test       # run tests
make check      # run all checks without changing files
make build      # build wheel and sdist into dist/
```

Run a single test:

```bash
uv run pytest tests/test_cli.py::test_version
```

`make check` runs formatting, linting, type checking, tests, and the Sphinx
documentation build without modifying source files.

## License

`tvmgr` is licensed under GPL-2.0-only. See [LICENSE](https://github.com/8cylinder/tvmgr/blob/main/LICENSE).

Copyright (C) 2026 Sheldon McGrandle

## Contributing and issues

Report issues at <https://github.com/8cylinder/tvmgr/issues>.

## Author

Sheldon McGrandle <developer@8cylinder.com>
