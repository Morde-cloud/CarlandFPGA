"""Build the B92 modelled A70-shape fixture.

The private nine-field producer payloads exist only in the evidence root for
source-shape validation. The transport projection contains counts, quality,
nominal times and hashes only. No Root, SourceLedger, admission, capture or
board authority is created or claimed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import raw4_adapter92 as adapter


REPO = Path(r"D:/pynq/CarlandFPGA")
SENSOR_SOURCE = REPO / (".local/deployment/node-b/main-handoff-20261029/successor-01/"
                        "successor-work/resume-74/source-inputs/A4dc-raw4-92/"
                        "competition/deepeye/integration/sensor_source.py")
ORIGIN_QPC_NS = 9007199254741085
EVALUATION_NOW_QPC_NS = ORIGIN_QPC_NS + 1_200_000_000
LIMITS = (
    (math.log10(0.2), math.log10(2000.0)),
    (-2.0, 2.0),
    (-2.0, 2.0),
    (0.0, 2.0),
)
EM_COUNT_BASE = (1000, 2000, 3000)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def value_for_count(channel, count):
    low, high = LIMITS[channel]
    return low + (count / 4095.0) * (high - low)


def load_pinned_validator():
    spec = importlib.util.spec_from_file_location("b92_pinned_sensor_source", SENSOR_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("pinned sensor source could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.validate_record


def record_shape(position):
    adc = position * 10
    segment = position // 5
    em = segment * 50
    held = em < adc
    c3_valid = position >= 9
    counts = [EM_COUNT_BASE[channel] + segment * 100 for channel in range(3)]
    counts.append(0 if c3_valid else None)
    quality = 0x0007 | (0x0008 if c3_valid else 0) | (0x0700 if held else 0)
    values = [value_for_count(channel, counts[channel]) for channel in range(3)]
    values.append(0.0 if c3_valid else None)
    return {
        "adc_tick_ms": adc,
        "em_tick_ms": em,
        "channel_values": values,
        "channel_counts": counts,
        "quality": quality,
    }


def private_payload(position):
    shape = record_shape(position)
    return {
        "profile_id": adapter.PROFILE_METADATA["profile_id"],
        "profile_status": adapter.PROFILE_METADATA["profile_status"],
        "profile_note": adapter.PROFILE_METADATA["profile_note"],
        "source_mode": adapter.PROFILE_METADATA["source_mode"],
        "adc_tick_ms": shape["adc_tick_ms"],
        "em_tick_ms": shape["em_tick_ms"],
        "channel_values": shape["channel_values"],
        "channel_counts": shape["channel_counts"],
        "quality": shape["quality"],
    }


def build_private_records():
    validate = load_pinned_validator()
    records = []
    for position in range(20):
        payload = private_payload(position)
        checked = validate(payload)
        if tuple(checked.channel_counts) != tuple(payload["channel_counts"]):
            raise RuntimeError("pinned validator changed modelled counts")
        records.append({
            "record_index": position,
            "payload": payload,
            "pinned_validation": {
                "adc_tick_ms": checked.adc_tick_ms,
                "em_tick_ms": checked.em_tick_ms,
                "channel_counts": list(checked.channel_counts),
                "quality": checked.quality,
            },
            "source_record_sha256": digest(payload),
        })
    return records


def fixture_identity():
    return {
        "kind": "B92_FIXTURE_TRANSPORT_IDENTITY_V1",
        "label": adapter.FIXTURE_KIND,
        "operation_id": "FIXTURE-RAW4-92-NOT-A-ROOT",
        "kernel_boot_id": "MODELLED_SHAPES_FROM_PINNED_PUBLIC_CONTRACTS",
        "session_id": "FIXTURE-SESSION-92",
        "clock_domain_id": "A_ORIGINAL_NOMINAL_QPC_NS-FIXTURE",
        "transport_receipt_id": "FIXTURE-TRANSPORT-92",
        "source_note": "not A Root/admission/capture/BOOT/action proof; modelled from pinned public contracts",
        "board": "not_run; A only",
    }


def build_projection(private_records=None):
    private_records = private_records or build_private_records()
    records = []
    for item in private_records:
        payload = item["payload"]
        records.append({
            "adc_tick_ms": payload["adc_tick_ms"],
            "em_tick_ms": payload["em_tick_ms"],
            "channel_counts": list(payload["channel_counts"]),
            "quality": payload["quality"],
            "source_record_sha256": item["source_record_sha256"],
        })
    return {
        "schema": adapter.SCHEMA,
        "fixture_kind": adapter.FIXTURE_KIND,
        "pinned_commit": adapter.PINNED_COMMIT,
        "pinned_tree": adapter.PINNED_TREE,
        "pinned_blob_count": adapter.PINNED_BLOB_COUNT,
        "time_basis": adapter.TIME_BASIS,
        "origin_qpc_ns": ORIGIN_QPC_NS,
        "evaluation_now_qpc_ns": EVALUATION_NOW_QPC_NS,
        "profile": dict(adapter.PROFILE_METADATA),
        "records": records,
        "fixture_transport_identity": fixture_identity(),
    }


def write_fixture(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    private_records = build_private_records()
    projection = build_projection(private_records)
    projection_raw = canonical(projection) + b"\n"
    (out / "PROJECTION_COUNTS_ONLY_92.json").write_bytes(projection_raw)
    private = {
        "schema": "B92_PRIVATE_SOURCE_FLOATS_NOT_TRANSPORT_V1",
        "note": "ROOT-PRIVATE MODELLED FIXTURE FLOATS; NOT TRANSPORT OR AI VIEW",
        "pinned_commit": adapter.PINNED_COMMIT,
        "records": private_records,
    }
    private_raw = canonical(private) + b"\n"
    (out / "PRIVATE_SOURCE_9FIELD_92.json").write_bytes(private_raw)
    notes = {
        "schema": "B92_FIXTURE_NOTES_V1",
        "label": adapter.FIXTURE_KIND,
        "not_original_A70": True,
        "not_live_root": True,
        "not_physical_adc": True,
        "not_current_fresh": True,
        "pinned_commit": adapter.PINNED_COMMIT,
        "pinned_tree": adapter.PINNED_TREE,
        "pinned_blob_count": adapter.PINNED_BLOB_COUNT,
        "origin_qpc_ns": ORIGIN_QPC_NS,
        "evaluation_now_qpc_ns": EVALUATION_NOW_QPC_NS,
        "adc_ticks_ms": [item["payload"]["adc_tick_ms"] for item in private_records],
        "em_ticks_ms": [item["payload"]["em_tick_ms"] for item in private_records],
        "global_quality_values": sorted({item["payload"]["quality"] for item in private_records}),
        "c3_null_record_indices": [i for i, item in enumerate(private_records)
                                   if item["payload"]["channel_counts"][3] is None],
        "c3_zero_record_indices": [i for i, item in enumerate(private_records)
                                   if item["payload"]["channel_counts"][3] == 0],
        "projection_sha256": hashlib.sha256(projection_raw).hexdigest(),
        "private_source_sha256": hashlib.sha256(private_raw).hexdigest(),
        "authority": {
            "actual_A_Root": "UNAVAILABLE",
            "native_em_receipt": "UNAVAILABLE",
            "admission": "UNAVAILABLE",
            "boot": "UNAVAILABLE",
            "physical_capture": "UNAVAILABLE",
            "action": "UNAVAILABLE",
            "current_source_eligible": False,
        },
    }
    (out / "FIXTURE_NOTES_92.json").write_bytes(canonical(notes) + b"\n")
    return projection, notes


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    projection, notes = write_fixture(args.out.resolve())
    print(json.dumps({
        "projection": str(args.out.resolve() / "PROJECTION_COUNTS_ONLY_92.json"),
        "records": len(projection["records"]),
        "quality": notes["global_quality_values"],
        "projection_sha256": notes["projection_sha256"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
