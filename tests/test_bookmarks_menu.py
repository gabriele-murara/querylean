"""Tests of the "Bookmarked queries" menu."""

from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.ui.main.bookmarks_menu import BookmarksMenu


class TestBookmarksMenu:
    """Entries, empty state and signals."""

    BOOKMARKS = [
        QueryBookmark("Users", "SELECT *\nFROM users", "t"),
        QueryBookmark("Orders", "SELECT * FROM orders", "t"),
    ]

    def test_empty_menu(self, qtbot):
        menu = BookmarksMenu()
        actions = menu.actions()
        assert [a.text() for a in actions] == [BookmarksMenu.EMPTY_TEXT]
        assert not actions[0].isEnabled()
        assert menu.names() == []
        assert menu.delete_menu is None

    def test_entries_and_signals(self, qtbot):
        menu = BookmarksMenu()
        menu.set_bookmarks(self.BOOKMARKS)
        assert menu.names() == ["Users", "Orders"]
        assert menu.actions()[0].toolTip() == "SELECT * FROM users"
        deletable = [a.text() for a in menu.delete_menu.actions()]
        assert deletable == ["Users", "Orders"]
        with qtbot.waitSignal(menu.run_requested) as run:
            menu.actions()[1].trigger()
        assert run.args == ["Orders"]
        with qtbot.waitSignal(menu.delete_requested) as delete:
            menu.delete_menu.actions()[0].trigger()
        assert delete.args == ["Users"]
        menu.set_bookmarks([])
        assert menu.names() == []
