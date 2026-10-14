"""Reproduce proposal arithmetic only; no product, network or board operation.

Run: python docs/competition/deepeye-2026/reviews/v5/b/check_planning.py
Checks the committed planning_checks.json without changing any file.
"""
import json
import math
from pathlib import Path


def calculate():
    header = sum([2, 1, 1, 2, 2, 8, 4, 2, 2, 8])
    overhead = header + 4
    obs = sum([4, 8, 4, 2, 2]) + 64 * sum([2, 1, 1])
    cmd = sum([4, 4, 2, 2, 2, 2, 1, 1, 2, 8])
    ack = sum([4, 4, 8, 2, 2, 2, 2, 1, 1, 2, 4])
    pose = sum([4, 4, 8, 12, 16, 12, 2, 2, 2, 2])
    assert (header, overhead, obs, cmd, ack, pose) == (32, 36, 276, 28, 32, 64)
    assert sum([8, 2, 4, 2, 2, 2, 2, 2]) == 24  # IO loopback proposal
    streams = []
    for name, payload, hz, scope in [
        ('obs_in', obs, 10, 'to_board'),
        ('obs_out', obs, 10, 'from_board'),
        ('cmd', cmd, 20, 'to_board'),
        ('ack', ack, 20, 'from_board'),
        ('heartbeat', ack, 2, 'from_board'),
        ('world_apply', cmd, 20, 'world'),
        ('self_pose', pose, 20, 'world'),
        ('plan_view', 256, 5, 'world'),
    ]:
        raw = payload + overhead
        cobs = raw + raw // 254 + 2
        eth = raw + 28 + 14 + 4 + 8 + 12
        streams.append(dict(name=name, payload=payload, raw=raw,
                            cobs_bound=cobs, ethernet_wire=eth, hz=hz, scope=scope,
                            ethernet_Bps=eth * hz, cobs_Bps=cobs * hz))
    board = [row for row in streams if row['scope'] != 'world']
    total = sum(row['ethernet_Bps'] for row in streams)
    uart_bytes = sum(row['cobs_Bps'] for row in board)
    assert uart_bytes == 9160
    uart = {}
    for baud in [300, 9600, 115200, 230400]:
        uart[str(baud)] = dict(
            half_duplex_nominal_percent=uart_bytes * 10 / baud * 100,
            half_duplex_retry_and_guard_percent=(uart_bytes * 10 / baud * 1.2
                                                 + 64 * 1.2 * 0.002) * 100,
            obs_packet_ms=streams[0]['cobs_bound'] * 10 / baud * 1000,
        )
    return dict(
        frame_overhead=overhead, streams=streams,
        board_ethernet_Bps=sum(row['ethernet_Bps'] for row in board),
        all_ethernet_Bps=total, all_packets_per_second=sum(row['hz'] for row in streams),
        all_ethernet_bps=total * 8, all_plus_20_percent_retry_bps=total * 8 * 1.2,
        one_Mbps_percent=total * 8 * 1.2 / 1_000_000 * 100,
        uart_board_segment_only=uart,
    )


def compare(actual, saved, path='root'):
    if isinstance(actual, dict):
        for key, value in actual.items():
            compare(value, saved[key], f'{path}.{key}')
    elif isinstance(actual, list):
        assert len(actual) == len(saved), path
        for index, value in enumerate(actual):
            compare(value, saved[index], f'{path}[{index}]')
    elif isinstance(actual, (int, float)):
        assert math.isclose(actual, saved, rel_tol=1e-12, abs_tol=1e-9), (path, actual, saved)
    else:
        assert actual == saved, (path, actual, saved)


if __name__ == '__main__':
    evidence = json.loads(Path(__file__).with_name('planning_checks.json').read_text('utf-8'))
    result = calculate()
    compare(result, evidence)
    print(json.dumps({'status': 'planning_arithmetic_passed',
                      'product_tests': 'not_run',
                      'all_ethernet_Bps': result['all_ethernet_Bps'],
                      'one_Mbps_percent': result['one_Mbps_percent'],
                      'half_duplex_115200_passes': False,
                      'half_duplex_230400_capacity_only_passes': True}, indent=2))
