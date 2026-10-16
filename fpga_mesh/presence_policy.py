"""Suppress legacy automatic presence reports without restarting a busy node.

Only the exact legacy event ID and generated text are matched. Original rows,
receipts, tasks, explicit human replies and other reports are preserved.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


TRIGGER_NAME = 'suppress_automatic_peer_presence_v1'


def _legacy_condition(prefix: str = '') -> str:
    op = prefix + 'operation_id'
    text = prefix + 'text'
    return f"""{prefix}role = 'astra'
        AND {prefix}sent_at IS NULL AND {prefix}cancelled_at IS NULL
        AND {op} GLOB 'peer:[ABC]:[ABC]:*' AND length({op}) = 41
        AND substr({op}, 10) NOT GLOB '*[^0-9a-f]*'
        AND {text} IN (
            'Astra-' || substr({op}, 6, 1) || ' 观察到 Astra-' || substr({op}, 8, 1) || ' 上线。可继续交换任务和实测结果。',
            'Astra-' || substr({op}, 6, 1) || ' 观察到 Astra-' || substr({op}, 8, 1) || ' 离线。本机继续独立推进；发给该节点的消息会排队补发。'
        )"""


def install_fence(path: Path) -> dict:
    """Atomically fence new legacy inserts and cancel only matching pending rows.

    A report already handed to the network before this transaction cannot be
    recalled. No second sender is started and no service/task is interrupted.
    """
    path = Path(path).resolve(strict=True)
    conn = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, timeout=10)
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute(f"""CREATE TRIGGER IF NOT EXISTS {TRIGGER_NAME}
            AFTER INSERT ON group_outbox
            WHEN {_legacy_condition('NEW.')}
            BEGIN
                UPDATE group_outbox
                SET cancelled_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE operation_id = NEW.operation_id;
            END""")
        cursor = conn.execute(f"""UPDATE group_outbox
            SET cancelled_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE {_legacy_condition()}""")
        count = cursor.rowcount
        conn.commit()
        return {'trigger': TRIGGER_NAME, 'installed': True, 'cancelled_pending': count}
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-db', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(install_fence(args.state_db)))


if __name__ == '__main__':
    main()
