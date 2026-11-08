"""Tests of the "Bookmarked queries" menu."""

from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.placeholder_type import PlaceholderType
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.ui.icons.toolbar_icons import ToolbarIcons
from querylean.ui.main.bookmarks_menu import BookmarksMenu
from querylean.ui.safe_text import SafeText


class TestBookmarksMenu:
    """Entries, empty state and signals."""

    BOOKMARKS = [
        QueryBookmark("Users", "SELECT *\nFROM users", "t"),
        QueryBookmark("Orders", "SELECT * FROM orders", "t"),
    ]

    def test_empty_menu(self, qtbot):
        menu = BookmarksMenu()
        actions = menu.actions()
        assert [a.text() for a in actions] == [
            BookmarksMenu.EMPTY_TEXT,
            "",
            BookmarksMenu.EXPORT_TEXT,
        ]
        assert not actions[0].isEnabled()
        assert actions[2] is menu.export_action
        assert menu.names() == []
        assert menu.delete_menu is None

    def test_entries_and_signals(self, qtbot):
        menu = BookmarksMenu()
        menu.set_bookmarks(self.BOOKMARKS)
        assert menu.names() == ["Users", "Orders"]
        assert menu.actions()[0].toolTip() == SafeText.tooltip(
            "SELECT * FROM users"
        )
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

    def test_plain_queries_and_masks_have_different_icons(self, qtbot):
        mask = QueryBookmark(
            "By year",
            "SELECT * FROM t WHERE y = ${Y}",
            "t",
            (Placeholder("Y", PlaceholderType.INTEGER, default="1"),),
        )
        menu = BookmarksMenu()
        menu.set_bookmarks([self.BOOKMARKS[0], mask])
        plain, masked = menu.actions()[:2]
        assert not plain.icon().isNull()
        assert not masked.icon().isNull()
        size = ToolbarIcons.SIZE
        plain_image = plain.icon().pixmap(size, size).toImage()
        mask_image = masked.icon().pixmap(size, size).toImage()
        assert plain_image != mask_image
        assert plain_image == ToolbarIcons.query().pixmap(size, size).toImage()

    def test_export_entry_survives_every_rebuild(self, qtbot):
        menu = BookmarksMenu()
        for bookmarks in ([], self.BOOKMARKS, []):
            menu.set_bookmarks(bookmarks)
            assert menu.actions()[-1] is menu.export_action
            assert menu.export_action.text() == BookmarksMenu.EXPORT_TEXT
            assert menu.export_action.isEnabled()
            with qtbot.waitSignal(menu.export_requested):
                menu.export_action.trigger()
        menu.set_bookmarks(self.BOOKMARKS)
        assert menu.names() == ["Users", "Orders"]
