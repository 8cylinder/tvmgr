# Command reference

```{click} tvmgr.cli:main
:prog: tvmgr
:nested: full
```

## SYNOPSIS

`tvmgr [OPTIONS] COMMAND [ARGS]...`

## DESCRIPTION

`tvmgr` removes watched episodes and movies from Kodi media centers. It can
read watched state from Kodi's JSON-RPC API or from a local Kodi video
database, then list or delete the corresponding files over SMB or from a
mounted directory.

## FILES

`~/.config/tvmgr/config.toml`
    The per-user configuration file. Run `tvmgr --config` to print the exact
    path for the current platform.

## ENVIRONMENT

`NO_COLOR`
    Disable colored output when `--color=auto`.

`FORCE_COLOR`
    Enable colored output when `--color=auto`.

`TERM=dumb`
    Disable colored output when `--color=auto`.

`BASH_COMPLETION_USER_DIR`
    First non-empty colon-separated entry is used as the bash completion
    directory by `tvmgr --completions`.

`XDG_DATA_HOME`
    Used for bash completions when `BASH_COMPLETION_USER_DIR` is not set.

## SEE ALSO

Project home page: <https://github.com/8cylinder/tvmgr>
