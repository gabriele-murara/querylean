"""Tests of the blinking Stop button of the result panel."""

from PySide6.QtGui import QAction

from querylean.ui.main.stop_button import StopButton


class TestStopButton:
    """Delayed appearance, blinking, hiding, click."""

    def make(self, qtbot, delay=50) -> StopButton:
        action = QAction("Stop")
        button = StopButton(action)
        button.appear_delay_ms = delay
        qtbot.addWidget(button)
        # Keep the action alive as long as the button.
        button.setProperty("test_action", action)
        return button

    def test_hidden_until_the_delay(self, qtbot):
        button = self.make(qtbot)
        assert button.isHidden() and not button.pending
        button.start()
        assert button.pending and button.isHidden()
        qtbot.waitUntil(button.isVisible, timeout=2000)
        assert button.blinking

    def test_blinks(self, qtbot):
        button = self.make(qtbot, delay=0)
        button.start()
        qtbot.waitUntil(button.isVisible, timeout=2000)
        assert button.opacity == 1.0
        qtbot.waitUntil(
            lambda: button.opacity == StopButton.DIM_OPACITY, timeout=2000
        )
        qtbot.waitUntil(lambda: button.opacity == 1.0, timeout=2000)

    def test_quick_query_never_shows_it(self, qtbot):
        button = self.make(qtbot, delay=200)
        button.start()
        button.finish()
        qtbot.wait(300)
        assert button.isHidden()
        assert not button.pending and not button.blinking

    def test_finish_hides_and_resets(self, qtbot):
        button = self.make(qtbot, delay=0)
        button.start()
        qtbot.waitUntil(
            lambda: button.opacity == StopButton.DIM_OPACITY, timeout=2000
        )
        button.finish()
        assert button.isHidden() and button.opacity == 1.0

    def test_click_triggers_the_action(self, qtbot):
        button = self.make(qtbot, delay=0)
        button.start()
        qtbot.waitUntil(button.isVisible, timeout=2000)
        with qtbot.waitSignal(button.defaultAction().triggered):
            button.click()

    def test_icon_and_text_come_from_the_action(self, qtbot):
        button = self.make(qtbot)
        assert button.text() == "Stop"
        button.appear_delay_ms = -5
        assert button.appear_delay_ms == 0
