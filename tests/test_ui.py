from io import StringIO

from rich.console import Console

from tvmgr.ui import Ui, error, make_ui, ok, warning


def _ui() -> tuple[Ui, StringIO, StringIO]:
    out = StringIO()
    err = StringIO()
    return (
        Ui(
            out=Console(file=out, force_terminal=False, width=80),
            err=Console(file=err, force_terminal=False, width=80),
        ),
        out,
        err,
    )


def test_ok_writes_to_stdout():
    ui, out, err = _ui()
    ok(ui, "created")
    assert "ok created" in out.getvalue()
    assert err.getvalue() == ""


def test_warning_writes_to_stderr():
    ui, out, err = _ui()
    warning(ui, "careful")
    assert "warning: careful" in err.getvalue()
    assert out.getvalue() == ""


def test_error_writes_to_stderr():
    ui, out, err = _ui()
    error(ui, "broken")
    assert "error: broken" in err.getvalue()
    assert out.getvalue() == ""


def test_make_ui_modes():
    assert make_ui("always").out.color_system is not None
    assert make_ui("never").out.color_system is None
    assert make_ui("auto").out.color_system is None
