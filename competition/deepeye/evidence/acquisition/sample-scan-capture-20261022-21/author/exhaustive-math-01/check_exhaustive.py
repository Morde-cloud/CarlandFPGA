from __future__ import annotations

from itertools import product

def scan_window(channels):
    partial = []
    scans = 0
    discarded = 0
    order_errors = 0
    for channel in channels:
        if not partial:
            if channel == 0:
                partial = [0]
            else:
                order_errors += 1
                discarded += 1
            continue
        if channel == len(partial):
            if len(partial) == 3:
                scans += 1
                partial = []
            else:
                partial.append(channel)
            continue
        order_errors += 1
        if channel == 0:
            discarded += len(partial)
            partial = [0]
        else:
            discarded += len(partial) + 1
            partial = []
    return scans, discarded, order_errors, len(partial)

totals = [0, 0, 0, 0]
windows = 0
for channels in product(range(4), repeat=6):
    windows += 1
    row = scan_window(channels)
    for index, value in enumerate(row):
        totals[index] += value

assert windows == 4096
assert totals == [48, 22656, 18432, 1728], totals
assert scan_window([]) == (0, 0, 0, 0)
assert scan_window([0]) == (0, 0, 0, 1)
assert scan_window([0, 1]) == (0, 0, 0, 2)
assert scan_window([0, 1, 2]) == (0, 0, 0, 3)
print("EXHAUSTIVE_MATH_PASS windows=4096 scans=48 discarded=22656 order_errors=18432 partial_end=1728")