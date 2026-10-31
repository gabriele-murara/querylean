"""Shared fixtures and helpers for tests that drive the main window."""

from __future__ import annotations

from abc import ABC

import pytest

from fakes.fake_connector import FakeConnector
from fakes.memory_keyring import MemoryKeyring
from querylean.config.config_manager import ConfigManager
from querylean.config.connection_config import ConnectionConfig
from querylean.database.connection.connection_manager import ConnectionManager
from querylean.security.keyring_secret_store import KeyringSecretStore
from querylean.ui.main.connection_state import ConnectionState
from querylean.ui.main.main_window import MainWindow
from querylean.ui.worker.db_thread import DbThread


class MainWindowTestBase(ABC):  # noqa: B024 (fixture holder, no abstract methods)
    """Builds a ``MainWindow`` backed by a fake driver, an in-memory keychain and a
    temporary configuration file. Not collected by pytest (no ``Test`` prefix)."""

    WAIT_MS = 5000

    @pytest.fixture
    def connector(self) -> FakeConnector:
        return FakeConnector()

    @pytest.fixture
    def window(self, qtbot, tmp_path, connector):
        win = MainWindow(
            ConfigManager(tmp_path / "config.json"),
            KeyringSecretStore(MemoryKeyring()),
            DbThread(ConnectionManager(connector)),
        )
        qtbot.addWidget(win)
        win.show()
        yield win
        if not win.closed:
            win.close()

    @staticmethod
    def configure(window: MainWindow, password: str = "pw") -> None:
        """Give the window a complete configuration and a password."""
        window.app_config.connection = ConnectionConfig(
            host="db", database="app", username="ro"
        )
        window.password = password

    @staticmethod
    def connect(qtbot, window: MainWindow) -> None:
        """Connect and wait for the connected state."""
        MainWindowTestBase.configure(window)
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.CONNECTED, timeout=MainWindowTestBase.WAIT_MS
        )

    @staticmethod
    def run(qtbot, window: MainWindow, sql: str) -> None:
        """Execute ``sql`` and wait for completion."""
        window.editor.setPlainText(sql)
        window.execute_query()
        qtbot.waitUntil(lambda: not window.running, timeout=MainWindowTestBase.WAIT_MS)
