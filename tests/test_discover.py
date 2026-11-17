from unittest.mock import Mock

from tvmgr import discover


class FakeSocket:
    instances: list["FakeSocket"] = []
    result = 0

    def __init__(self) -> None:
        self.timeout: float | None = None
        self.closed = False
        self.address: tuple[str, int] | None = None
        FakeSocket.instances.append(self)

    def settimeout(self, value: float) -> None:
        self.timeout = value

    def connect_ex(self, address: tuple[str, int]) -> int:
        self.address = address
        return FakeSocket.result

    def close(self) -> None:
        self.closed = True


def _pong(result="pong"):
    response = Mock()
    response.json.return_value = {"result": result}
    return response


def test_discover_kodi_finds_devices(monkeypatch):
    FakeSocket.instances = []
    FakeSocket.result = 0
    monkeypatch.setattr(discover.socket, "socket", lambda *_: FakeSocket())
    monkeypatch.setattr(discover.requests, "post", Mock(return_value=_pong()))

    result = discover.discover_kodi("192.168.0.0/30", timeout=0.25)

    assert set(result) == {
        "192.168.0.0",
        "192.168.0.1",
        "192.168.0.2",
        "192.168.0.3",
    }
    assert all(sock.closed for sock in FakeSocket.instances)
    assert all(sock.timeout == 0.25 for sock in FakeSocket.instances)
    address = FakeSocket.instances[0].address
    assert address is not None
    assert address[1] == 8080


def test_discover_kodi_ignores_closed_ports(monkeypatch):
    FakeSocket.instances = []
    FakeSocket.result = 1
    monkeypatch.setattr(discover.socket, "socket", lambda *_: FakeSocket())
    post = Mock()
    monkeypatch.setattr(discover.requests, "post", post)

    assert discover.discover_kodi(["192.168.0.0/30"]) == []
    post.assert_not_called()


def test_discover_kodi_requires_pong(monkeypatch):
    FakeSocket.instances = []
    FakeSocket.result = 0
    monkeypatch.setattr(discover.socket, "socket", lambda *_: FakeSocket())
    monkeypatch.setattr(
        discover.requests,
        "post",
        Mock(return_value=_pong("not-pong")),
    )

    assert discover.discover_kodi(["192.168.0.0/30"]) == []


def test_discover_kodi_ignores_http_errors(monkeypatch):
    FakeSocket.instances = []
    FakeSocket.result = 0
    monkeypatch.setattr(discover.socket, "socket", lambda *_: FakeSocket())
    monkeypatch.setattr(
        discover.requests,
        "post",
        Mock(side_effect=RuntimeError("network")),
    )

    assert discover.discover_kodi(["192.168.0.0/30"]) == []
    assert all(sock.closed for sock in FakeSocket.instances)
