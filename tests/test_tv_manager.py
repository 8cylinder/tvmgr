from io import StringIO
from types import SimpleNamespace

import pytest
from rich.console import Console

from tvmgr.config import Config, PathsConfig, SmbConfig
from tvmgr.tv_manager import (
    ShowFile,
    SmbUnavailableError,
    delete_files,
    humanize,
    make_auth_fn,
    walk_bottom_up,
)
from tvmgr.ui import Ui


class FakeNoEntry(Exception):
    pass


class FakePermission(Exception):
    pass


class FakeContext:
    last: "FakeContext | None" = None
    stat_values: dict[str, object] = {}
    stat_exception: Exception | None = None

    def __init__(self) -> None:
        self.optionNoAutoAnonymousLogin = False
        self.functionAuthData = None
        self.files = dict(type(self).stat_values)
        self.unlinked: list[str] = []
        FakeContext.last = self

    def stat(self, filename: str):
        value = self.files.get(filename, type(self).stat_exception)
        if value is None:
            raise KeyError(filename)
        if isinstance(value, Exception):
            raise value
        return (0, 0, 0, 0, 0, 0, value, 0, 0, 0)

    def unlink(self, filename: str) -> None:
        self.unlinked.append(filename)


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


def _fake_smbc() -> SimpleNamespace:
    return SimpleNamespace(
        Context=FakeContext,
        NoEntryError=FakeNoEntry,
        PermissionError=FakePermission,
    )


@pytest.fixture(autouse=True)
def _reset_fake_context():
    FakeContext.last = None
    FakeContext.stat_values = {}
    FakeContext.stat_exception = None


def test_humanize_boundaries():
    assert humanize(0) == "0 Bytes"
    assert humanize(1023) == "1023 Bytes"
    assert humanize(1024) == "1 Kb"
    assert humanize(1048576) == "1 Mb"
    assert humanize(1073741824) == "1 Gb"


def test_show_file_maps_and_operates(tmp_path):
    target = tmp_path / "episode.mkv"
    target.write_text("data")
    show_file = ShowFile(
        "smbc://server/Volume_1/episode.mkv",
        PathsConfig(smbc_drive="/Volume_1", mount_base=str(tmp_path)),
    )
    assert show_file.stat("anything").st_size == 4
    show_file.unlink("anything")
    assert not target.exists()


def test_make_auth_fn_uses_config():
    auth = make_auth_fn(
        SmbConfig(username="user", password="pass", workgroup="WORK")
    )
    assert auth("server", "share", "CALLBACK", "ignored", "ignored") == (
        "WORK",
        "user",
        "pass",
    )


def test_make_auth_fn_uses_callback_workgroup_when_unset():
    auth = make_auth_fn(SmbConfig())
    assert (
        auth("server", "share", "CALLBACK", "ignored", "ignored")[0]
        == "CALLBACK"
    )


def test_delete_files_requires_smbc(monkeypatch):
    monkeypatch.setattr("tvmgr.tv_manager.smbc", None)
    ui, _, _ = _ui()
    with pytest.raises(SmbUnavailableError, match="pysmbc"):
        delete_files([], False, False, True, False, Config(), ui)


def test_delete_files_lists_and_deletes(monkeypatch):
    monkeypatch.setattr("tvmgr.tv_manager.smbc", _fake_smbc())
    ui, out, err = _ui()
    filename = "smb://server/Volume_1/Show/episode.mkv"
    FakeContext.stat_values = {filename: 123}

    delete_files(
        [(filename, "Show")],
        hide_deleted=False,
        real=True,
        use_smbc=True,
        verbose=True,
        config=Config(),
        ui=ui,
    )

    context = FakeContext.last
    assert context is not None
    assert context.unlinked == [filename]
    assert context.optionNoAutoAnonymousLogin is True
    assert context.functionAuthData is not None
    assert "episode.mkv" in out.getvalue()
    assert "123 Bytes" in out.getvalue()
    assert "deleted:" in out.getvalue()
    assert err.getvalue() == ""


def test_delete_files_keep_list_verbose(monkeypatch):
    monkeypatch.setattr("tvmgr.tv_manager.smbc", _fake_smbc())
    ui, out, _ = _ui()
    delete_files(
        [("smb://server/Volume_1/Deadwood/e.mkv", "Dead_Wood")],
        hide_deleted=False,
        real=False,
        use_smbc=True,
        verbose=True,
        config=Config(keep_list=("Deadwood",)),
        ui=ui,
    )
    assert "skipping:" in out.getvalue()
    assert FakeContext.last is not None
    assert FakeContext.last.unlinked == []


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (ValueError("bad"), "Not an smb file"),
        (FakeNoEntry(), "(A) File does not exist"),
        (TypeError(), "(B) File does not exist"),
        (FileNotFoundError(), "(C) File does not exist"),
    ],
)
def test_delete_files_missing_variants(monkeypatch, exception, message):
    monkeypatch.setattr("tvmgr.tv_manager.smbc", _fake_smbc())
    ui, _, err = _ui()
    filename = "smb://server/Volume_1/Show/missing.mkv"
    FakeContext.stat_exception = exception
    delete_files(
        [(filename, "Show")],
        hide_deleted=False,
        real=False,
        use_smbc=True,
        verbose=False,
        config=Config(),
        ui=ui,
    )
    assert message in err.getvalue()


def test_delete_files_hides_missing(monkeypatch):
    monkeypatch.setattr("tvmgr.tv_manager.smbc", _fake_smbc())
    ui, _, err = _ui()
    filename = "smb://server/Volume_1/Show/missing.mkv"
    FakeContext.stat_exception = FakeNoEntry()
    delete_files(
        [(filename, "Show")],
        hide_deleted=True,
        real=False,
        use_smbc=True,
        verbose=False,
        config=Config(),
        ui=ui,
    )
    assert "(A)" not in err.getvalue()


def test_delete_files_permission_stops(monkeypatch):
    monkeypatch.setattr("tvmgr.tv_manager.smbc", _fake_smbc())
    ui, _, err = _ui()
    FakeContext.stat_exception = FakePermission()
    delete_files(
        [
            ("smb://server/Volume_1/Show/a.mkv", "Show"),
            ("smb://server/Volume_1/Show/b.mkv", "Show"),
        ],
        hide_deleted=False,
        real=False,
        use_smbc=True,
        verbose=False,
        config=Config(),
        ui=ui,
    )
    assert "permission" in err.getvalue()


def test_delete_files_mount_mode(tmp_path):
    target = tmp_path / "sub" / "episode.mkv"
    target.parent.mkdir()
    target.write_text("12345")
    ui, out, _ = _ui()
    config = Config(
        paths=PathsConfig(smbc_drive="/Volume_1", mount_base=str(tmp_path))
    )

    delete_files(
        [("smbc://server/Volume_1/sub/episode.mkv", "Show")],
        hide_deleted=False,
        real=True,
        use_smbc=False,
        verbose=True,
        config=config,
        ui=ui,
    )

    assert not target.exists()
    assert "5 Bytes" in out.getvalue()
    assert "deleted:" in out.getvalue()


def test_walk_bottom_up(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert walk_bottom_up(str(empty), {".mkv"}) is True

    video = tmp_path / "video"
    video.mkdir()
    (video / "episode.mkv").write_text("x")
    assert walk_bottom_up(str(video), {".mkv"}) is False

    text = tmp_path / "text"
    text.mkdir()
    (text / "notes.txt").write_text("x")
    assert walk_bottom_up(str(text), {".mkv"}) is True


def test_delete_files_mount_mode_missing_without_smbc(monkeypatch, tmp_path):
    monkeypatch.setattr("tvmgr.tv_manager.smbc", None)
    ui, _, err = _ui()
    config = Config(
        paths=PathsConfig(smbc_drive="/Volume_1", mount_base=str(tmp_path))
    )

    delete_files(
        [("smbc://server/Volume_1/sub/missing.mkv", "Show")],
        hide_deleted=False,
        real=False,
        use_smbc=False,
        verbose=False,
        config=config,
        ui=ui,
    )

    assert "(C) File does not exist" in err.getvalue()
