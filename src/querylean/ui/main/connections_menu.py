"""Menu of the "Connections" toolbar button."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QWidget

from querylean.config.connection_profile import ConnectionProfile


class ConnectionsMenu(QMenu):
    """ "New connection…", then one sub-menu per saved connection with
    "Connect", "Edit…" and "Delete…". The active connection is checked.

    Signals carry the connection identifier; the menu holds no logic.
    """

    new_requested = Signal()
    connect_requested = Signal(str)
    edit_requested = Signal(str)
    delete_requested = Signal(str)

    NEW_TEXT = "New connection…"
    CONNECT_TEXT = "Connect"
    EDIT_TEXT = "Edit…"
    DELETE_TEXT = "Delete…"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Connections", parent)
        self.__submenus: dict[str, QMenu] = {}
        self.set_connections([], "", connected=False)

    def submenu(self, profile_id: str) -> QMenu:
        """Sub-menu of the connection ``profile_id``."""
        return self.__submenus[profile_id]

    def set_connections(
        self,
        profiles: list[ConnectionProfile],
        active_id: str,
        *,
        connected: bool,
    ) -> None:
        """Rebuild the entries. "Connect" is disabled for the active
        connection while it is connected."""
        self.clear()
        self.__submenus = {}
        new_action = self.addAction(ConnectionsMenu.NEW_TEXT)
        new_action.triggered.connect(lambda: self.new_requested.emit())
        if profiles:
            self.addSeparator()
        for profile in profiles:
            pid = profile.profile_id
            submenu = self.addMenu(profile.display_name)
            submenu.setToolTipsVisible(True)
            entry = submenu.menuAction()
            # Only the active connection shows a check mark.
            entry.setCheckable(pid == active_id)
            entry.setChecked(pid == active_id)
            entry.setToolTip(profile.config.default_name())
            connect = submenu.addAction(ConnectionsMenu.CONNECT_TEXT)
            connect.setEnabled(not (connected and pid == active_id))
            connect.triggered.connect(
                lambda _c=False, p=pid: self.connect_requested.emit(p)
            )
            edit = submenu.addAction(ConnectionsMenu.EDIT_TEXT)
            edit.triggered.connect(
                lambda _c=False, p=pid: self.edit_requested.emit(p)
            )
            submenu.addSeparator()
            delete = submenu.addAction(ConnectionsMenu.DELETE_TEXT)
            delete.triggered.connect(
                lambda _c=False, p=pid: self.delete_requested.emit(p)
            )
            self.__submenus[pid] = submenu
