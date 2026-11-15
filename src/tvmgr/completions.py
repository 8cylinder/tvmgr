"""Static bash completion generation for tvmgr."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import click

MINIMUM_BASH = (4, 4)


def _function_name(prog_name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", prog_name)
    return f"_{sanitized}_complete"


def _command_functions(
    group: click.Group,
    parent_path: tuple[str, ...] = (),
) -> list[tuple[tuple[str, ...], click.Command, int]]:
    commands: list[tuple[tuple[str, ...], click.Command, int]] = [
        (parent_path, group, 0)
    ]
    counter = 1
    for name in sorted(group.commands):
        command = group.commands[name]
        if command.hidden:
            continue
        commands.append((parent_path + (name,), command, counter))
        counter += 1
    return commands


def _option_names(option: click.Option) -> list[str]:
    return [*option.opts, *option.secondary_opts]


def _value_kind(parameter: click.Parameter) -> tuple[str, Any] | None:
    parameter_type = parameter.type
    if isinstance(parameter_type, click.Choice):
        return ("choices", list(parameter_type.choices))
    if isinstance(parameter_type, click.Path):
        return (
            ("dirs", None)
            if parameter_type.file_okay is False
            else ("files", None)
        )
    if isinstance(parameter_type, click.File):
        return ("files", None)
    if isinstance(parameter_type, click.DateTime):
        return None
    return None


def _bash_case_pattern(name: str) -> str:
    return name


def _option_value_cases(
    command: click.Command,
    indent: str = "        ",
) -> list[str]:
    lines: list[str] = []
    for parameter in command.params:
        if not isinstance(parameter, click.Option) or parameter.hidden:
            continue
        if parameter.is_flag or parameter.secondary_opts:
            continue
        kind = _value_kind(parameter)
        for name in _option_names(parameter):
            pattern = _bash_case_pattern(name)
            lines.append(f"{indent}{pattern})")
            if kind is None:
                lines.append(f"{indent}    COMPREPLY=()")
            elif kind[0] == "choices":
                choices = " ".join(shlex.quote(str(c)) for c in kind[1])
                lines.append(
                    f"{indent}    COMPREPLY=( $(compgen -W {shlex.quote(choices)}"
                    ' -- "$cur") )'
                )
            elif kind[0] == "files":
                lines.append(f"{indent}    _tvmgr_filedir")
            elif kind[0] == "dirs":
                lines.append(f"{indent}    _tvmgr_filedir_dirs")
            lines.append(f"{indent}    return 0")
            lines.append(f"{indent}    ;;")
    return lines


def _equals_cases(
    command: click.Command, indent: str = "        "
) -> list[str]:
    lines: list[str] = []
    for parameter in command.params:
        if not isinstance(parameter, click.Option) or parameter.hidden:
            continue
        if parameter.is_flag or parameter.secondary_opts:
            continue
        kind = _value_kind(parameter)
        for name in parameter.opts:
            if not name.startswith("--"):
                continue
            lines.append(f"{indent}{name})")
            if kind is None:
                lines.append(f"{indent}    COMPREPLY=()")
            elif kind[0] == "choices":
                choices = " ".join(shlex.quote(str(c)) for c in kind[1])
                lines.append(
                    f"{indent}    COMPREPLY=( $(compgen -W {shlex.quote(choices)}"
                    ' -- "$val") )'
                )
                lines.append(f"{indent}    compopt -o nospace")
            elif kind[0] == "files":
                lines.append(f'{indent}    cur="$val"')
                lines.append(f"{indent}    _tvmgr_filedir")
            elif kind[0] == "dirs":
                lines.append(f'{indent}    cur="$val"')
                lines.append(f"{indent}    _tvmgr_filedir_dirs")
            lines.append(f"{indent}    return 0")
            lines.append(f"{indent}    ;;")
    return lines


def _positional_lines(
    command: click.Command, indent: str = "    "
) -> list[str]:
    arguments = [
        parameter
        for parameter in command.params
        if isinstance(parameter, click.Argument)
    ]
    if not arguments:
        return []
    argument = arguments[0]
    kind = _value_kind(argument)
    if kind is None:
        return []
    lines: list[str] = []
    if kind[0] == "choices":
        choices = " ".join(shlex.quote(str(c)) for c in kind[1])
        lines.append(
            f"{indent}COMPREPLY=( $(compgen -W {shlex.quote(choices)}"
            ' -- "$cur") )'
        )
    elif kind[0] == "files":
        lines.append(f"{indent}_tvmgr_filedir")
    elif kind[0] == "dirs":
        lines.append(f"{indent}_tvmgr_filedir_dirs")
    return lines


def _command_function(
    path: tuple[str, ...],
    command: click.Command,
    identifier: int,
    function_name: str,
) -> str:
    lines: list[str] = [f"{function_name}_{identifier}() {{"]
    lines.append("    local cur prev words cword")
    lines.append('    cur="${COMP_WORDS[COMP_CWORD]}"')
    lines.append('    prev="${COMP_WORDS[COMP_CWORD-1]}"')
    lines.append('    words=("${COMP_WORDS[@]}")')
    lines.append("    cword=$COMP_CWORD")
    lines.append("")

    options = ["-h", "--help"]
    for parameter in command.params:
        if isinstance(parameter, click.Option) and not parameter.hidden:
            options.extend(_option_names(parameter))
    option_words = " ".join(
        shlex.quote(name) for name in dict.fromkeys(options)
    )
    child_names = []
    if isinstance(command, click.Group):
        child_names = sorted(
            name for name, child in command.commands.items() if not child.hidden
        )

    lines.append('    if [[ "$cur" == --*=* ]]; then')
    lines.append('        local opt="${cur%%=*}"')
    lines.append('        local val="${cur#*=}"')
    lines.append('        case "$opt" in')
    lines.extend(_equals_cases(command, indent="            "))
    lines.append("        esac")
    lines.append("        COMPREPLY=()")
    lines.append("        return 0")
    lines.append("    fi")
    lines.append("")
    lines.append('    case "$prev" in')
    lines.extend(_option_value_cases(command))
    lines.append("    esac")
    lines.append("")
    lines.append("    local dashdash=0 i")
    lines.append("    for ((i=1; i<cword; i++)); do")
    lines.append('        if [[ "${words[i]}" == "--" ]]; then dashdash=1; fi')
    lines.append("    done")
    lines.append("")
    lines.append('    if (( ! dashdash )) && [[ "$cur" == -* ]]; then')
    lines.append(
        f"        COMPREPLY=( $(compgen -W {shlex.quote(option_words)}"
        ' -- "$cur") )'
    )
    lines.append("        return 0")
    lines.append("    fi")
    lines.append("")

    if child_names:
        lines.append("    local subcommands=(")
        for name in child_names:
            lines.append(f"        {shlex.quote(name)}")
        lines.append("    )")
        lines.append(
            '    COMPREPLY=( $(compgen -W "${subcommands[*]}" -- "$cur") )'
        )
        lines.append("    return 0")
    else:
        positional = _positional_lines(command)
        if positional:
            lines.extend(positional)
        else:
            lines.append("    COMPREPLY=()")
    lines.append("}")
    return "\n".join(lines)


def generate_bash(group: click.Group, prog_name: str, version: str) -> str:
    """Return the complete bash completion script."""
    function_name = _function_name(prog_name)
    commands = _command_functions(group)

    lines: list[str] = [
        f"# {prog_name} {version} bash completions",
        "# Generated by the application; do not edit.",
        "# Rerun the completions command after changing commands or options.",
        "",
        "_tvmgr_filedir() {",
        "    if declare -F _filedir >/dev/null; then",
        "        _filedir",
        "    else",
        '        mapfile -t COMPREPLY < <(compgen -f -- "$cur")',
        "    fi",
        "}",
        "",
        "_tvmgr_filedir_dirs() {",
        "    if declare -F _filedir >/dev/null; then",
        "        _filedir -d",
        "    else",
        '        mapfile -t COMPREPLY < <(compgen -d -- "$cur")',
        "    fi",
        "}",
        "",
        f"{function_name}() {{",
        "    local cur words cword",
        '    cur="${COMP_WORDS[COMP_CWORD]}"',
        '    words=("${COMP_WORDS[@]}")',
        "    cword=$COMP_CWORD",
        "    local cmd='' skip=0 i w",
        "    for ((i=1; i<cword; i++)); do",
        '        w="${words[i]}"',
        "        if ((skip)); then skip=0; continue; fi",
        '        case "$w" in',
        "            --color) skip=1 ;;",
        "            --config|--completions|--version|-h|--help) ;;",
        "            --*) ;;",
        "            -*) ;;",
        '            *) cmd="$w"; break ;;',
        "        esac",
        "    done",
        '    case "$cmd" in',
    ]

    for path, _command, identifier in commands:
        dispatched = path[0] if path else ""
        lines.append(
            f"        {shlex.quote(dispatched)}) {function_name}_{identifier} ;;"
        )
    lines.append("    esac")
    lines.append("}")
    lines.append("")

    for path, command, identifier in commands:
        lines.append(
            _command_function(path, command, identifier, function_name)
        )
        lines.append("")

    lines.append(
        f"complete -o nosort -o bashdefault -o default -F {function_name}"
        f" {shlex.quote(prog_name)}"
    )
    lines.append("")
    return "\n".join(lines)


def completion_dir() -> Path:
    """Return the bash-completion directory for the current user."""
    user_dir = os.environ.get("BASH_COMPLETION_USER_DIR")
    if user_dir:
        first = next(
            (entry for entry in user_dir.split(os.pathsep) if entry), None
        )
        if first:
            return Path(first).expanduser()

    data_home = os.environ.get("XDG_DATA_HOME")
    base = (
        Path(data_home).expanduser()
        if data_home
        else Path.home() / ".local" / "share"
    )
    return base / "bash-completion" / "completions"


def _warn_bash_version() -> None:
    bash = shutil.which("bash")
    if bash is None:
        print(
            "warning: bash was not found; the completion file was still written.",
            file=sys.stderr,
        )
        return

    try:
        result = subprocess.run(
            [
                bash,
                "-c",
                'printf "%s.%s" "${BASH_VERSINFO[0]}" "${BASH_VERSINFO[1]}"',
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        major_text, minor_text = result.stdout.split(".", 1)
        version = (int(major_text), int(minor_text))
    except (OSError, ValueError):
        return

    if version < MINIMUM_BASH:
        print(
            "warning: bash "
            f"{version[0]}.{version[1]} is older than "
            f"{MINIMUM_BASH[0]}.{MINIMUM_BASH[1]}; completions may not work.",
            file=sys.stderr,
        )


def install_bash_completion(
    group: click.Group,
    prog_name: str,
    version: str,
) -> Path:
    """Write the script, print its path, and return the path."""
    script = generate_bash(group, prog_name, version)
    destination = completion_dir() / f"{prog_name}.bash"
    destination.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{prog_name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(script)
        temporary.chmod(0o644)
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise

    _warn_bash_version()
    print(destination)
    print(
        f"To use it in this shell:\n  source {destination}",
        file=sys.stderr,
    )
    return destination
