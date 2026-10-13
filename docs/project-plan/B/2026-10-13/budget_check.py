"""Deterministic planning arithmetic, not RTL simulation or board measurements.

Run with Python 3.10+ from any directory. Inputs are proposed design assumptions.
The fixed frame overhead is a budget reservation, not a frozen wire protocol.
"""
import json
from fractions import Fraction as F


def scenario(name, baud, fs, mode, up_share=F(1), down_share=F(1)):
    # Four int16 channels, 16 time steps per block; UART 8N1.
    raw = 4 * 2 * 16
    period = F(16, fs)
    overhead = 16
    if mode == "conditional_4_to_1":
        payload = 32  # Includes codec descriptors, anchors and padding.
        data_bytes = payload + overhead
    elif mode == "conditional_8_to_1":
        payload = 16
        data_bytes = payload + overhead
    elif mode == "raw":
        # Four independently decodable raw subblocks: 4 times * 4ch * 2B.
        payload = raw + 4  # One descriptor per independent subblock.
        data_bytes = payload + 4 * overhead
    else:
        raise ValueError(mode)
    up_capacity = F(baud, 10) * up_share
    down_capacity = F(baud, 10) * down_share
    # 24B command/10s; 16B ACK/10s; 24B event/30s.
    up = F(data_bytes) / period + F(16, 10) + F(24, 30)
    down = F(24, 10)
    return dict(name=name, baud=baud, samples_per_channel_hz=fs, mode=mode,
                block_period_s=float(period), raw_block_bytes=raw,
                codec_bytes=payload, data_wire_bytes=data_bytes,
                up_capacity_Bps=float(up_capacity), up_demand_Bps=float(up),
                down_capacity_Bps=float(down_capacity), down_demand_Bps=float(down),
                up_utilization=float(up/up_capacity),
                average_budget_pass=up <= F(4,5)*up_capacity and down <= F(4,5)*down_capacity,
                queue_stability_proven=False,
                latency_proven=False)


def main():
    rows = [scenario("full_300_5hz_4to1",300,5,"conditional_4_to_1"),
            scenario("full_240_5hz_4to1",240,5,"conditional_4_to_1"),
            scenario("full_300_5hz_8to1",300,5,"conditional_8_to_1"),
            scenario("full_300_5hz_raw",300,5,"raw"),
            scenario("half_300_5hz_4to1",300,5,"conditional_4_to_1",F(7,10),F(2,10)),
            scenario("half_300_4hz_4to1",300,4,"conditional_4_to_1",F(7,10),F(2,10))]
    by_name = {r['name']: r for r in rows}
    # Independent rational expectations catch unit, framing and half-duplex mistakes.
    assert by_name['full_300_5hz_4to1']['up_demand_Bps'] == float(F(87,5))
    assert by_name['full_300_5hz_raw']['up_demand_Bps'] == float(F(1273,20))
    assert [r['average_budget_pass'] for r in rows] == [True,True,True,False,False,True]
    # 64B in-progress frame + 24B event + 24B command + 0.1s processing.
    conditional_path_300 = F((64+24+24)*10,300) + F(1,10)
    conditional_path_240 = F((64+24+24)*10,240) + F(1,10)
    assert conditional_path_300 == F(23,6)
    assert conditional_path_240 == F(143,30)
    # 32KiB cannot make an unstable full raw queue lossless indefinitely.
    overflow_s = F(32768) / (F(1273,20)-30)
    assert 973 < overflow_s < 974
    result = dict(kind="planning_arithmetic_only", assumptions_not_requirements=True,
                  scenarios=rows, checks_passed=True,
                  event_path_no_retry_no_extra_queue_s={"300":float(conditional_path_300),"240":float(conditional_path_240)},
                  raw_backlog_32KiB_overflow_s=float(overflow_s),
                  exclusions=["codec ratio not measured", "no bit-stuffing or escaping provisioned",
                              "no handshake or profile update traffic provisioned",
                              "no retransmission, burst or scheduling latency proof",
                              "no hardware, synthesis, implementation or RTL simulation"])
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
