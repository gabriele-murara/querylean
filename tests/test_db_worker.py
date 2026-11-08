"""Tests of the database worker, called in the test thread."""

import pytest

from fakes.fake_connector import FakeConnector
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.connection_config import ConnectionConfig
from querylean.database.connection.connection_manager import ConnectionManager
from querylean.ui.worker.db_worker import DbWorker


class TestDbWorker:
    """Bookmarked queries run only on a session for their target."""

    CFG = ConnectionConfig(host="db", database="app", username="ro")
    SQL = "SELECT id FROM users"

    @pytest.fixture
    def connector(self) -> FakeConnector:
        return FakeConnector()

    @pytest.fixture
    def worker(self, qtbot, connector) -> DbWorker:
        worker = DbWorker(ConnectionManager(connector))
        worker.manager.connect(self.CFG, "pw")
        return worker

    def executed(self, connector) -> list[str]:
        return [sql for conn in connector.connections for sql in conn.executed]

    def test_bookmark_runs_on_its_target(self, worker, connector):
        finished = []
        worker.query_finished.connect(finished.append)
        target = QueryBookmark.target_of(self.CFG)
        worker.bookmark_requested.emit(self.SQL, target, 100, 30)
        assert len(finished) == 1
        assert self.SQL in self.executed(connector)

    @pytest.mark.parametrize(
        "target", ["ro@db:3306/other", "rw@db:3306/app", "ro@db2:3306/app", ""]
    )
    def test_bookmark_for_another_target_is_refused(
        self, worker, connector, target
    ):
        failed = []
        worker.query_failed.connect(lambda m, k: failed.append((m, k)))
        worker.bookmark_requested.emit(self.SQL, target, 100, 30)
        assert failed == [(DbWorker.WRONG_TARGET, DbWorker.WRONG_TARGET_KIND)]
        assert self.SQL not in self.executed(connector)

    def test_bookmark_without_session_is_not_connected(self, worker):
        worker.manager.disconnect()
        failed = []
        worker.query_failed.connect(lambda m, k: failed.append(k))
        target = QueryBookmark.target_of(self.CFG)
        worker.bookmark_requested.emit(self.SQL, target, 100, 30)
        assert failed == ["not_connected"]

    def test_count_and_page_run_through_the_validator(self, worker, connector):
        counted, pages = [], []
        worker.count_finished.connect(lambda s, n: counted.append((s, n)))
        worker.page_finished.connect(lambda s, p, r: pages.append((p, r)))
        connector.connections[-1].handler = lambda sql: (["c"], [(7,)])
        target = QueryBookmark.target_of(self.CFG)
        worker.count_requested.emit(self.SQL, target, 30)
        assert counted == [(self.SQL, 7)]
        worker.page_requested.emit(self.SQL, target, 2, 50, 30)
        assert pages[0][0] == 2
        assert pages[0][1].statement.endswith("LIMIT 50 OFFSET 100")

    def test_count_and_page_for_another_target_are_refused(
        self, worker, connector
    ):
        failed = []
        worker.count_failed.connect(lambda s, m, k: failed.append(m))
        worker.page_failed.connect(lambda s, p, m, k: failed.append(m))
        worker.count_requested.emit(self.SQL, "ro@db2:3306/app", 30)
        worker.page_requested.emit(self.SQL, "ro@db2:3306/app", 1, 50, 30)
        assert failed == [DbWorker.PAGES_TARGET] * 2
        assert not any("COUNT" in sql for sql in self.executed(connector))
        assert not any("OFFSET" in sql for sql in self.executed(connector))

    def test_built_statements_are_still_validated(self, worker, connector):
        failed = []
        worker.count_failed.connect(lambda s, m, k: failed.append(k))
        target = QueryBookmark.target_of(self.CFG)
        worker.count_requested.emit(
            "SELECT 1) AS x; DROP TABLE t; (", target, 30
        )
        assert failed == ["rejected"]
        assert not any("DROP" in sql for sql in self.executed(connector))
