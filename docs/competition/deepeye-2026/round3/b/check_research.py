"""Pure research arithmetic; no FPGA/model/engine/product execution.

python docs/competition/deepeye-2026/round3/b/check_research.py
prints deterministic JSON for comparison with checks.json.
"""
import json
import math
from fractions import Fraction as F


def curvature(speed, yaw_code, pitch_code, unit_deg):
    return math.hypot(yaw_code, pitch_code) * unit_deg * math.pi / 180 / speed


def calculate():
    overhead = sum([2, 1, 1, 1, 1, 2, 4, 2])
    fields = {
        'telem': [8, 8, 2],
        'event': [2, 1, 1, 2],
        'control3d': [4, 2, 1, 2, 2, 1, 2, 2],
        'ack3d': [4, 2, 1, 1, 2, 2, 1, 2, 1, 2, 1, 1],
        'state3d': [4, 2, 2, 2, 1, 1, 2, 2, 2, 1, 1],
        'config': [4, 1, 1, 1, 2, 1],
        'config_ack': [4, 2, 1, 1, 1, 1, 1, 2, 1, 1, 1, 2],
        'boot': [4, 1, 16, 2, 2, 2],
    }
    sizes = {name: overhead + sum(parts) for name, parts in fields.items()}
    assert overhead == 14
    assert sizes == dict(telem=32, event=20, control3d=30, ack3d=34,
                         state3d=34, config=24, config_ack=32, boot=41)
    normal = sum(sizes[name] for name in ['telem', 'event', 'control3d', 'ack3d', 'state3d'])
    windows = dict(normal_hil=normal, config_hil=normal+24+32,
                   control_retry_hil=normal+30+34, event_retry_hil=normal+20,
                   gain_normal=140, pc_direct_normal=32+32+20)
    budgets = {}
    for name, byte_count in windows.items():
        modes = {}
        for mode, baud, duration, guard in [('stress_300', 300, F(8), F(1, 5)),
                                            ('fast_9600', 9600, F(1, 2), F(1, 25))]:
            if name == 'gain_normal' and mode == 'fast_9600':
                continue  # Not specified by A's table; do not silently invent it.
            wire = F(byte_count * 10, baud)
            modes[mode] = dict(wire_seconds=float(wire),
                              wire_plus_guard_seconds=float(wire+guard),
                              occupied_percent=float((wire+guard)/duration*100))
        budgets[name] = dict(bytes=byte_count, profiles=modes)
    gap = F(210) - (F(35) + F(32*10*1000, 9600))
    vectors = []
    for speed, y, p, expected in [(.002, 57, 0, True), (.002, 58, 0, False),
                                 (.002, 40, 40, True), (.002, 41, 41, False),
                                 (.0001, 2, 0, True), (.0001, 3, 0, False),
                                 (.0001, 2, 2, True), (.25, 5064, 5064, True),
                                 (.25, 5065, 5065, False)]:
        k = curvature(speed, y, p, .001)
        allowed = k <= .5
        assert allowed == expected, (speed, y, p, k)
        vectors.append(dict(speed_m_s=speed, yaw_code=y, pitch_code=p,
                            curvature_per_m=k, allowed=allowed))
    old = curvature(.002, 1, 0, .1)
    assert old > .5
    return {
        'scope': 'research arithmetic only; product_not_run',
        'a_source_head': '74c854d74baf817beafcbd1d4d52a8dd4450bbca',
        'frame_bytes': sizes, 'budget': budgets,
        'fast_telem_end_ms': float(F(35)+F(32*10*1000,9600)),
        'fast_telem_to_primary_gap_ms': float(gap),
        'compute_150ms_lateness_before_other_overheads_ms': float(F(150)-gap),
        'compute_250ms_lateness_before_other_overheads_ms': float(F(250)-gap),
        'next_window_ack_end_ms_ignoring_other_overheads': float(F(755)+F(34*10*1000,9600)),
        'old_stress_min_nonzero_curvature_per_m': old,
        'old_stress_max_turn_radius_m': 1/old,
        'stress_permitted_rate_at_max_speed_deg_s': .002/2 * 180/math.pi,
        'proposed_rate_unit_deg_s': .001,
        'quantized_boundary_vectors': vectors,
        'rotation_point_displacement_bound_mm_at_r081_angle025': 2*.81*math.sin(math.radians(.25)/2)*1000,
        'ring_radial_clearance_mm': (.30-.24)/2*1000,
        'three_20Hz_samples_first_to_third_ms': 2/20*1000,
        'three_20Hz_samples_phase_wait_upper_ms': 3/20*1000,
    }


if __name__ == '__main__':
    print(json.dumps(calculate(), ensure_ascii=False, indent=2))
