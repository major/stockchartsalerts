"""Default test-suite socket policy behavior."""

from __future__ import annotations

import socket

import pytest
from pytest_socket import SocketConnectBlockedError


def test_local_loopback_server_connections_are_allowed() -> None:
    """Allow test sockets to connect to a loopback server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.connect(server.getsockname())
            with server.accept()[0] as accepted:
                assert accepted.getpeername()[0] == "127.0.0.1"


def test_external_socket_connections_are_blocked_before_connecting() -> None:
    """Block test sockets from connecting to external hosts."""
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client,
        pytest.raises(SocketConnectBlockedError),
        pytest.warns(UserWarning, match="socket.socket.connect"),
    ):
        client.connect(("203.0.113.1", 80))
