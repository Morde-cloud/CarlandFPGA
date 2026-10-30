"""B92 pure adapter negative controls; each expected refusal exits 2."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import raw4_adapter92 as adapter
import prepare_fixture92 as fixture


EXPECTED = {
    "unknown_key": "projection keys",
    "bool_int": "adc_tick_ms",
    "nonfinite": "plain JSON types only",
    "duplicate_json": "duplicate JSON key",
    "gap": "ADC ticks",
    "backfill": "EM time cannot reverse or backfill",
    "em_partial": "EM validity must be all-or-none",
    "held_mismatch": "held bits must match original EM time",
    "invalid_count": "invalid channel must carry null count",
    "valid_count_none": "channel count",
    "sat_invalid": "invalid channel cannot be saturated",
    "quality_bit11": "bit 11",
    "quality_high_bits": "record quality",
    "fault_mismatch": "source_fault must match invalid EM",
    "c3_early": "C3 cannot be valid",
    "too_many": "record count 1..20",
    "u63_overflow": "evaluation margin",
    "duplicate_record": "duplicate source record",
    "invalid_em_hold": "invalid EM cannot be held",
    "source_hash_bad": "original source-record hash",
    "counts_tuple": "plain JSON types only",
}


def mutate(case):
    projection = copy.deepcopy(fixture.build_projection())
    records = projection["records"]
    if case == "unknown_key":
        projection["truth"] = 1
    elif case == "bool_int":
        records[0]["adc_tick_ms"] = True
    elif case == "nonfinite":
        projection["origin_qpc_ns"] = float("inf")
    elif case == "gap":
        del records[1]
    elif case == "backfill":
        records[6]["em_tick_ms"] = 0
    elif case == "em_partial":
        records[0]["quality"] = 0x0001
        records[0]["channel_counts"] = [1000, None, None, None]
        records[0]["em_tick_ms"] = None
    elif case == "held_mismatch":
        records[1]["quality"] = records[1]["quality"] & ~0x0700
    elif case == "invalid_count":
        records[0]["channel_counts"][3] = 0
    elif case == "valid_count_none":
        records[9]["channel_counts"][3] = None
    elif case == "sat_invalid":
        records[0]["quality"] = records[0]["quality"] | 0x0080
    elif case == "quality_bit11":
        records[1]["quality"] = records[1]["quality"] | 0x0800
    elif case == "quality_high_bits":
        records[1]["quality"] = records[1]["quality"] | 0x2000
    elif case == "fault_mismatch":
        records[1]["quality"] = records[1]["quality"] | 0x1000
    elif case == "c3_early":
        records[0]["quality"] = records[0]["quality"] | 0x0008
        records[0]["channel_counts"][3] = 0
    elif case == "too_many":
        extra = copy.deepcopy(records[-1])
        extra["adc_tick_ms"] = 200
        extra["source_record_sha256"] = "f" * 64
        records.append(extra)
    elif case == "u63_overflow":
        projection["origin_qpc_ns"] = adapter.U63 - 190_000_000
        projection["evaluation_now_qpc_ns"] = adapter.U63
    elif case == "duplicate_record":
        records[1]["source_record_sha256"] = records[0]["source_record_sha256"]
    elif case == "invalid_em_hold":
        records[0]["quality"] = 0x1700
        records[0]["em_tick_ms"] = None
        records[0]["channel_counts"][0:3] = [None, None, None]
    elif case == "source_hash_bad":
        records[0]["source_record_sha256"] = "A" * 64
    elif case == "counts_tuple":
        records[0]["channel_counts"] = tuple(records[0]["channel_counts"])
    else:
        raise KeyError(case)
    return projection


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=sorted(EXPECTED))
    args = parser.parse_args(argv)
    try:
        if args.case == "duplicate_json":
            adapter.load_json_strict(b'{"schema":"a","schema":"b"}')
        else:
            projection = mutate(args.case)
            adapter.validate_projection(projection)
    except adapter.Rejected as exc:
        reason = str(exc)
        if EXPECTED[args.case] not in reason:
            print(json.dumps({"unexpected_rejection": args.case, "reason": reason},
                             ensure_ascii=False, sort_keys=True))
            return 3
        print(json.dumps({"expected_rejection": args.case,
                          "error_type": type(exc).__name__, "reason": reason},
                         ensure_ascii=False, sort_keys=True))
        return 2
    except Exception as exc:
        print(json.dumps({"unexpected_exception": args.case,
                          "error_type": type(exc).__name__, "reason": str(exc)},
                         ensure_ascii=False, sort_keys=True))
        return 3
    print(json.dumps({"FALSE_ACCEPT": args.case}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
