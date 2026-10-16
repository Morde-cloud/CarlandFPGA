import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from fpga_mesh.store import SQLiteStore
from fpga_mesh.presence_policy import install_fence


class PresencePolicyTests(unittest.TestCase):
    def test_live_old_writer_is_suppressed_without_losing_other_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.sqlite'
            store = SQLiteStore(path)
            try:
                old = 'peer:A:B:' + '1' * 32
                sent = 'peer:A:C:' + '2' * 32
                store.enqueue_group_report(old, 'Astra-A 观察到 Astra-B 离线。本机继续独立推进；发给该节点的消息会排队补发。')
                store.enqueue_group_report(sent, 'Astra-A 观察到 Astra-C 上线。可继续交换任务和实测结果。')
                store.ack_group_report(sent, 'original-receipt')
                store.enqueue_group_report('human-query', 'Astra-B 当前离线')
                store.enqueue_group_report('board-result', 'Measured board result')
                first = install_fence(path)
                self.assertEqual(first['cancelled_pending'], 1)
                self.assertEqual(store.group_report_status(old), 'cancelled')
                self.assertEqual(store.group_report_status(sent), 'sent')
                live = 'peer:B:C:' + 'a' * 32
                store.enqueue_group_report(live, 'Astra-B 观察到 Astra-C 上线。可继续交换任务和实测结果。')
                self.assertEqual(store.group_report_status(live), 'cancelled')
                # Similar IDs/text are not enough: only the legacy auto event matches.
                store.enqueue_group_report('peer:A:C:' + 'b' * 32, 'Explicit human-requested report')
                store.enqueue_group_report('peer:A:B:manual', 'Astra-A 观察到 Astra-B 上线。可继续交换任务和实测结果。')
                self.assertEqual(len(store.pending_group_messages()), 4)
                self.assertEqual(install_fence(path)['cancelled_pending'], 0)
                with closing(sqlite3.connect(path)) as conn:
                    self.assertEqual(conn.execute('SELECT count(*) FROM group_outbox').fetchone()[0], 7)
                    self.assertEqual(conn.execute('SELECT platform_message_id FROM group_outbox WHERE operation_id=?', (sent,)).fetchone()[0], 'original-receipt')
            finally:
                store.close()

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'missing.sqlite'
            with self.assertRaises((FileNotFoundError, sqlite3.OperationalError)):
                install_fence(path)
            self.assertFalse(path.exists())
