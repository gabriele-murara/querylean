"""GUI tests of the page buttons of the result table."""

from querylean.ui.results.results_pager import ResultsPager


class TestResultsPager:
    """Visibility, bounds, buttons and the ``page_changed`` signal."""

    def test_single_page_is_hidden(self, qtbot):
        pager = ResultsPager()
        qtbot.addWidget(pager)
        pager.show()
        pager.set_page_count(1)
        assert pager.isHidden()
        pager.set_page_count(0)
        assert pager.page_count == 1

    def test_buttons_and_signal(self, qtbot):
        pager = ResultsPager()
        qtbot.addWidget(pager)
        pager.show()
        pages = []
        pager.page_changed.connect(pages.append)
        pager.set_page_count(4)
        assert pager.isVisible()
        assert pager.label.text() == "Page 1 of 4"
        assert not pager.first_button.isEnabled()
        assert not pager.previous_button.isEnabled()
        pager.next_button.click()
        pager.last_button.click()
        assert pager.label.text() == "Page 4 of 4"
        assert not pager.next_button.isEnabled()
        pager.previous_button.click()
        pager.first_button.click()
        pager.set_page(-5)
        pager.set_page(99)
        assert pages == [1, 3, 2, 0, 3]
        pager.set_page_count(2)
        assert pager.page == 0
        assert pages == [1, 3, 2, 0, 3]

    def test_counting_and_silent_page(self, qtbot):
        pager = ResultsPager()
        qtbot.addWidget(pager)
        pages = []
        pager.page_changed.connect(pages.append)
        pager.show_counting()
        assert pager.isVisible()
        assert pager.label.text() == ResultsPager.COUNTING
        assert not pager.next_button.isEnabled()
        pager.set_page_count(1000, 1_000_000)
        assert pager.label.text() == "Page 1 of 1,000"
        assert pager.label.toolTip() == "1,000,000 rows"
        pager.show_page(5)
        assert pager.page == 5
        assert pages == []
