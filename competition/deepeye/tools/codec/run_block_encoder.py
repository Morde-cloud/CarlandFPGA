#!/usr/bin/env python3
"""Portable fail-closed ModelSim runner for the B block-encoder candidate.

Work: B-BLOCK-ENCODER-RTL-20261018-08-v1
Task: DEEPEYE-IMPLEMENTATION-20261014/v1; operation
B-DEEPEYE-BLOCK-ENCODER-20261018-08.  Contract DEEPEYE-HUMAN-LOCK-20261014/
revision1 (H01-H15), requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
Frozen design 1011259415a0916054eb580687612580bc1e5f09.

The runner:
  * refuses a pre-existing --output directory before creating anything;
  * requires explicit --modelsim-home, --rtl, --tb, --golden and --output,
    so a flat export whose paths contain spaces needs no node-private file;
  * verifies the pinned golden/known-vector SHA256 values;
  * derives every expected fixture by importing the pinned golden reference
    read-only (including the pinned known-vector fixtures);
  * builds a legal matrix (N=1..128 x E=0,1,2,4,8), the pinned known vectors,
    targeted k-tie/RAW-tie/floor-negative/padding cases and fixed-seed random
    blocks; directed protocol/reset/cancel cases live in the testbench;
  * runs vlib/vlog/vsim with argument arrays (no shell), bounded timeouts and
    a real .do macro with onerror/onbreak quit codes (ModelSim 10.7 ignores
    those inside inline -do strings);
  * is fail-closed: requires the exact TB_DONE/TB_SUMMARY/TB_END markers, a
    zero-error transcript, every expected case, exact per-case handshake
    counts, byte-exact payloads and a 20000-clock last-sample-to-metadata
    bound, and rejects any TB_CHECK_FAIL.

Exit codes: 0 = all checks passed; 1 = a simulation/check failure;
2 = usage or environment error before simulation.
"""

import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
WORK_ID = "B-BLOCK-ENCODER-RTL-20261018-08-v1"
OPERATION_ID = "B-DEEPEYE-BLOCK-ENCODER-20261018-08"
CONTRACT = {
    "contract": "DEEPEYE-HUMAN-LOCK-20261014",
    "revision": 1,
    "requirements_ids": ["H%02d" % i for i in range(1, 16)],
    "requirements_sha256": "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
    "contract_commit": "f5989cd5defce561f9ba98e6b18fc2682945f0a2",
    "design_commit": "1011259415a0916054eb580687612580bc1e5f09",
}
PINNED_GOLDEN_SHA256 = "2e24e01c7e8cc9a010f9c0f26d94091b33676b7394f0f7344ca5bf938fefbfd5"
PINNED_RULES_SHA256 = "275525f2cf951d196d333171cb777c41aaeeedd5239689fe096f40055b7dbeb8"
PINNED_VECTORS_SHA256 = "c1eee67b73b8cdd449ac72b2a77c78f714eaf448b1216b16296488881ac10e99"
PINNED_SPEC_SHA256 = "e31bbe3a115bb37581c81e6ac15c23175c6f251c2b290505f71f0fbc2ec1d601"
MAX_CYCLES_LAST_TO_META = 20000
DEFAULT_TIMEOUT_SECONDS = 3600
MAX_TIMEOUT_SECONDS = 14400
E_VALUES = (0, 1, 2, 4, 8)
MAX_SAMPLES = 128
MAX_BYTES = 256


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_golden(path):
    spec = importlib.util.spec_from_file_location(
        "deepeye_codec_reference_pinned", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import golden reference: %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_view(fixture):
    return {
        "mode": fixture["mode"],
        "e": fixture["e"],
        "k": fixture["k"],
        "sample_count": fixture["sample_count"],
        "valid_bit_count": fixture["valid_bit_count"],
        "payload_hex": fixture["payload_hex"],
    }


def make_fixture(golden, samples, e):
    values = golden.check_samples(list(samples))
    e = golden.check_e(e)
    fixture = golden.encode_block(values, e)
    payload = bytes.fromhex(fixture["payload_hex"])
    if fixture["sample_count"] != len(values):
        raise RuntimeError("golden sample_count mismatch")
    if len(payload) != (fixture["valid_bit_count"] + 7) // 8:
        raise RuntimeError("golden payload byte accounting mismatch")
    if fixture["valid_bit_count"] > 4095:
        raise RuntimeError("valid_bit_count does not fit the 12-bit port")
    if len(payload) > MAX_BYTES:
        raise RuntimeError("payload exceeds the 256-byte port bound")
    # Strict re-parse of the fixture; raises on any golden invariant violation.
    golden.decode_block(fixture)
    if fixture["mode"] == "raw":
        if fixture["k"] is not None:
            raise RuntimeError("golden RAW fixture carried a non-null k")
        raw = 1
        k = 0
    elif fixture["mode"] == "rice":
        raw = 0
        k = fixture["k"]
    else:
        raise RuntimeError("unexpected golden mode")
    return {
        "mode": fixture["mode"],
        "e": e,
        "k": k,
        "k_fixture": fixture["k"],
        "raw": raw,
        "valid_bits": fixture["valid_bit_count"],
        "bytes": len(payload),
        "payload": payload,
        "payload_hex": payload.hex(),
        "sample_count": len(values),
    }


def make_pattern(pattern, n, e):
    if pattern == 0:
        value = (e * 4099 + n * 251) & 0xFFFF
        return [value] * n
    if pattern == 1:
        step = 1 + ((n * 13 + e * 7) % 31)
        start = (n * 97 + e * 1009) & 0xFFFF
        return [(start + i * step) & 0xFFFF for i in range(n)]
    if pattern == 2:
        step = 1 + ((n * 11 + e * 5) % 29)
        start = (50000 + n * 31 + e * 17) & 0xFFFF
        return [(start - i * step) & 0xFFFF for i in range(n)]
    if pattern == 3:
        return [65535 if (i % 2) else 0 for i in range(n)]
    if pattern == 4:
        cycle = (0, 1, 65534, 65535, 32768, 32767, 2, 65533)
        return [cycle[i % len(cycle)] for i in range(n)]
    if pattern == 5:
        state = (0x2026101808 + n * 7919 + e * 104729) & ((1 << 64) - 1)
        out = []
        for _ in range(n):
            state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
            out.append((state >> 16) & 0xFFFF)
        return out
    base = (n * 1234 + e * 5678) & 0xFFFF
    out = []
    for i in range(n):
        if i % 11 == 0:
            out.append(0 if ((i // 11) % 2 == 0) else 65535)
        elif i % 5 == 0:
            out.append((base + 5000 * (1 + ((i // 5) % 3))) & 0xFFFF)
        else:
            out.append(base)
    return out


def random_samples(seed, n):
    state = seed & ((1 << 64) - 1)
    out = []
    for _ in range(n):
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        out.append((state >> 24) & 0xFFFF)
    return out


def rice_totals(golden, samples, e):
    """Annotate k ties only; expected payloads always come from golden.encode_block."""
    values = golden.check_samples(list(samples))
    e = golden.check_e(e)
    previous = values[0]
    z_values = []
    for x in values[1:]:
        q = golden.quantize(x, previous, e)
        z_values.append(golden.zigzag(q))
        previous = golden.reconstruct(previous, q, e)
    totals = []
    for k in range(16):
        if all((z >> k) <= 31 for z in z_values):
            totals.append((k, sum(z >> k for z in z_values) + len(z_values) * (k + 1)))
        else:
            totals.append((k, None))
    legal = [(k, total) for k, total in totals if total is not None]
    if not legal:
        return {"best_rice_bits": None, "tie_ks": []}
    best = min(total for _, total in legal)
    return {"best_rice_bits": best, "tie_ks": [k for k, total in legal if total == best]}


def add_case(cases, golden, case_id, e, samples, stall, tags):
    fixture = make_fixture(golden, samples, e)
    if len(samples) < 1 or len(samples) > MAX_SAMPLES:
        raise RuntimeError("case %s has illegal sample count" % case_id)
    annotation = rice_totals(golden, samples, e)
    if fixture["mode"] == "rice":
        if fixture["k"] not in annotation["tie_ks"]:
            raise RuntimeError("case %s selected k outside tied minima" % case_id)
    cases.append({
        "id": case_id,
        "kind": "vector",
        "e": e,
        "samples": list(samples),
        "stall": stall % 4,
        "tags": list(tags),
        "fixture": fixture,
        "k_ties": annotation["tie_ks"],
        "best_rice_bits": annotation["best_rice_bits"],
    })


def build_vector_cases(golden, vectors):
    cases = []
    for ei, e in enumerate(E_VALUES):
        for n in range(1, MAX_SAMPLES + 1):
            pattern = (n + ei * 3) % 7
            samples = make_pattern(pattern, n, e)
            add_case(cases, golden, "legal_e%d_n%d_p%d" % (e, n, pattern),
                     e, samples, n + ei, ["matrix", "pattern%d" % pattern])

    if vectors is not None:
        for section in ("hand_vectors", "raw_step_examples", "raw_noisy_examples"):
            for entry in vectors.get(section, []):
                expected = fixture_view(entry["fixture"])
                actual = fixture_view(golden.encode_block(entry["samples"], entry["e"]))
                if actual != expected:
                    raise RuntimeError(
                        "pinned known vector %s disagrees with golden: %r != %r"
                        % (entry["id"], actual, expected))
                add_case(cases, golden, "known_%s_%s" % (section, entry["id"]),
                         entry["e"], entry["samples"], len(cases),
                         ["known", section, entry["id"]])
        for entry in vectors.get("next_block_recovery", {}).get("blocks", []):
            expected = fixture_view(entry["fixture"])
            actual = fixture_view(golden.encode_block(entry["samples"], entry["e"]))
            if actual != expected:
                raise RuntimeError(
                    "pinned recovery block %s disagrees with golden" % entry["id"])
            add_case(cases, golden, "known_recovery_%s" % entry["id"],
                     entry["e"], entry["samples"], len(cases),
                     ["known", "next_block_recovery", entry["id"]])

    targeted = [
        ("targeted_tie_012_e0", 0, [0, 1, 2]),
        ("targeted_tie_0123_e0", 0, [0, 1, 2, 3]),
        ("targeted_tie_024_e0", 0, [0, 2, 4]),
        ("targeted_tie_0101_e0", 0, [0, 1, 0, 1]),
        ("targeted_raw_tie_0max_e2", 2, [0, 65535]),
        ("targeted_rice_boundary_0max_e4", 4, [0, 65535]),
        ("targeted_floor_neg_small_e0", 0, [10, 9, 8, 7, 6, 5]),
        ("targeted_floor_neg_mid_e1", 1, [100, 90, 80, 70, 60]),
        ("targeted_floor_neg_extreme_e2", 2, [65535, 1000, 0, 65535, 0]),
        ("targeted_pad_n1_e0", 0, [1]),
        ("targeted_pad_0123_e0", 0, [0, 1, 2, 3]),
        ("targeted_pad_100_101_e0", 0, [100, 101]),
        ("targeted_max_extrema_e0", 0, [65535, 0] * 64),
        ("targeted_max_noise_e8", 8, random_samples(0x2026101808E8, 128)),
    ]
    for case_id, e, samples in targeted:
        add_case(cases, golden, case_id, e, samples, len(cases), ["targeted"])

    # Main BE01 regression: sparse steps force long unary fields at the
    # selected k; dense random data often switches to RAW and misses this.
    for k in range(13):
        for quotient in (17, 18, 30, 31):
            z = quotient << k
            anchor = 65535 if z % 2 else 0
            target = anchor - (z + 1) // 2 if z % 2 else z // 2
            samples = [anchor] * 64 + [target] * 64
            add_case(cases, golden, "main_be01_k%d_q%d" % (k, quotient),
                     0, samples, len(cases), ["main_be01_long_unary"])
            fixture = cases[-1]["fixture"]
            assert fixture["mode"] == "rice" and fixture["k"] == k

    for index in range(48):
        n = 1 + ((index * 37 + 11) % MAX_SAMPLES)
        e = E_VALUES[(index * 3) % len(E_VALUES)]
        samples = random_samples(0x202610180000 + index * 104729, n)
        add_case(cases, golden, "random_%02d_e%d_n%d" % (index, e, n),
                 e, samples, index, ["random"])

    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate case ids generated")
    return cases


def write_stimulus(path, cases):
    lines = ["%d" % len(cases)]
    for index, case in enumerate(cases):
        fixture = case["fixture"]
        lines.append("%d %d %d %d %d %d %d %d" % (
            index, case["e"], len(case["samples"]), fixture["raw"],
            fixture["k"], fixture["valid_bits"], fixture["bytes"], case["stall"]))
        for sample in case["samples"]:
            lines.append("%d" % sample)
        for byte in fixture["payload"]:
            lines.append("%d" % byte)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


V_A = {"e": 0, "samples": [0, 1, 2], "label": "V_A"}
V_B = {"e": 1, "samples": [65535, 65534, 0, 65535], "label": "V_B"}
V_N1 = {"e": 8, "samples": [5], "label": "V_N1"}

DIRECTED_SPECS = [
    {"id": "D_startup_idle", "kind": "idle", "cfg": 0, "sample": 0, "meta": 0, "data": 0},
    {"id": "D_invalid_count0", "kind": "error", "cfg": 1, "sample": 0, "meta": 1, "data": 0, "error": 1},
    {"id": "R_after_invalid_count0", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_invalid_count129", "kind": "error", "cfg": 1, "sample": 0, "meta": 1, "data": 0, "error": 1},
    {"id": "R_after_invalid_count129", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_invalid_count255", "kind": "error", "cfg": 1, "sample": 0, "meta": 1, "data": 0, "error": 1},
    {"id": "R_after_invalid_count255", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_invalid_e3", "kind": "error", "cfg": 1, "sample": 0, "meta": 1, "data": 0, "error": 1},
    {"id": "R_after_invalid_e3", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_invalid_e15", "kind": "error", "cfg": 1, "sample": 0, "meta": 1, "data": 0, "error": 1},
    {"id": "R_after_invalid_e15", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_length_missing_last", "kind": "error", "cfg": 1, "sample": 3, "meta": 1, "data": 0, "error": 2},
    {"id": "R_after_length_missing_last", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_length_early_last", "kind": "error", "cfg": 1, "sample": 1, "meta": 1, "data": 0, "error": 2},
    {"id": "R_after_length_early_last", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_n1_raw_tie", "kind": "legal", "vec": V_N1, "cfg": 1, "sample": 1, "meta": 1, "data": "payload"},
    {"id": "D_consecutive_A", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_consecutive_B", "kind": "legal", "vec": V_B, "cfg": 1, "sample": 4, "meta": 1, "data": "payload"},
    {"id": "D_input_gaps_meta_stall", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_extra_sample_ignored", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_long_backpressure", "kind": "legal", "vec": V_B, "cfg": 1, "sample": 4, "meta": 1, "data": "payload"},
    {"id": "D_reset_load", "kind": "abort", "cfg": 1, "sample": 2, "meta": 0, "data": 0},
    {"id": "R_after_reset_load", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_cancel_load", "kind": "abort", "cfg": 1, "sample": 2, "meta": 0, "data": 0},
    {"id": "R_after_cancel_load", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_reset_div", "kind": "abort", "cfg": 1, "sample": 8, "meta": 0, "data": 0},
    {"id": "R_after_reset_div", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_cancel_div", "kind": "abort", "cfg": 1, "sample": 8, "meta": 0, "data": 0},
    {"id": "R_after_cancel_div", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_reset_sel", "kind": "abort", "cfg": 1, "sample": 8, "meta": 0, "data": 0},
    {"id": "R_after_reset_sel", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_cancel_sel", "kind": "abort", "cfg": 1, "sample": 8, "meta": 0, "data": 0},
    {"id": "R_after_cancel_sel", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_reset_meta", "kind": "abort", "cfg": 1, "sample": 3, "meta": 0, "data": 0},
    {"id": "R_after_reset_meta", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_cancel_meta", "kind": "abort", "cfg": 1, "sample": 3, "meta": 0, "data": 0},
    {"id": "R_after_cancel_meta", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_reset_data", "kind": "abort", "cfg": 1, "sample": 3, "meta": 1, "data": 0, "meta_vec": V_A},
    {"id": "R_after_reset_data", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
    {"id": "D_cancel_data", "kind": "abort", "cfg": 1, "sample": 3, "meta": 1, "data": 0, "meta_vec": V_A},
    {"id": "R_after_cancel_data", "kind": "legal", "vec": V_A, "cfg": 1, "sample": 3, "meta": 1, "data": "payload"},
]


def resolve_directed(golden):
    resolved = []
    for spec in DIRECTED_SPECS:
        item = dict(spec)
        if "vec" in spec:
            fixture = make_fixture(golden, spec["vec"]["samples"], spec["vec"]["e"])
            item["fixture"] = fixture
            if spec["data"] == "payload":
                item["data"] = fixture["bytes"]
        if "meta_vec" in spec:
            item["meta_fixture"] = make_fixture(
                golden, spec["meta_vec"]["samples"], spec["meta_vec"]["e"])
        resolved.append(item)
    return resolved


RE_RUNNER_END = re.compile(rb"^(?:# )?RUNNER_REACHED_END\r?$", re.M)
RE_TB_DONE = re.compile(rb"^(?:# )?TB_DONE\r?$", re.M)
RE_TB_END = re.compile(rb"^(?:# )?TB_END (pass|fail)\r?$", re.M)
RE_TB_STIMULUS = re.compile(rb"^(?:# )?TB_STIMULUS cases=(\d+)\r?$", re.M)
RE_TB_SUMMARY = re.compile(
    rb"^(?:# )?TB_SUMMARY cases=(\d+) pass=(\d+) fail=(\d+) cfg_hs=(\d+) "
    rb"sample_hs=(\d+) meta_hs=(\d+) data_hs=(\d+) error_meta=(\d+) "
    rb"resets=(\d+) cancels=(\d+)\r?$", re.M)
RE_TB_CASE = re.compile(
    rb"^(?:# )?TB_CASE (\S+) pass=(\d) cfg=(\d+) sample=(\d+) meta=(\d+) "
    rb"data=(\d+)\r?$", re.M)
RE_TB_META = re.compile(
    rb"^(?:# )?TB_META case=(\S+) error=(\d+) count=(\d+) e=(\d+) raw=(\d+) "
    rb"k=(\d+) bits=(\d+) bytes=(\d+) cycles=(\d+)\r?$", re.M)
RE_TB_PAYLOAD = re.compile(
    rb"^(?:# )?TB_PAYLOAD case=(\S+) n=(\d+)((?:\s+\d+)*)\r?$", re.M)
RE_TB_CHK = re.compile(
    rb"^(?:# )?TB_CHK case=(\S+) token=(\S+) ok=(\d)\r?$", re.M)
RE_VLOG_ERRORS = re.compile(rb"Errors:\s*(\d+),\s*Warnings:\s*(\d+)")


def parse_transcript(stdout):
    parsed = {
        "done": len(RE_TB_DONE.findall(stdout)),
        "end": [match.decode() for match in RE_TB_END.findall(stdout)],
        "stimulus": [int(value) for value in RE_TB_STIMULUS.findall(stdout)],
        "summary": [tuple(int(value) for value in match)
                    for match in RE_TB_SUMMARY.findall(stdout)],
        "cases": {},
        "meta": {},
        "payload": {},
        "checks": {},
    }
    for match in RE_TB_CASE.finditer(stdout):
        name = match.group(1).decode()
        parsed["cases"][name] = {
            "pass": int(match.group(2)),
            "cfg": int(match.group(3)),
            "sample": int(match.group(4)),
            "meta": int(match.group(5)),
            "data": int(match.group(6)),
        }
    for match in RE_TB_META.finditer(stdout):
        name = match.group(1).decode()
        parsed["meta"].setdefault(name, []).append({
            "error": int(match.group(2)),
            "count": int(match.group(3)),
            "e": int(match.group(4)),
            "raw": int(match.group(5)),
            "k": int(match.group(6)),
            "bits": int(match.group(7)),
            "bytes": int(match.group(8)),
            "cycles": int(match.group(9)),
        })
    for match in RE_TB_PAYLOAD.finditer(stdout):
        name = match.group(1).decode()
        nbytes = int(match.group(2))
        values = [int(value) for value in match.group(3).split()]
        parsed["payload"].setdefault(name, []).append({
            "n": nbytes,
            "bytes": values,
        })
    for match in RE_TB_CHK.finditer(stdout):
        name = match.group(1).decode()
        parsed["checks"].setdefault(name, []).append({
            "token": match.group(2).decode(),
            "ok": int(match.group(3)),
        })
    return parsed


class Runner:
    def __init__(self, out_dir, timeout):
        self.out = out_dir
        self.timeout = timeout
        self.records = []
        self.checks = []
        self.failures = []

    def check(self, run_name, name, ok, detail=""):
        entry = {"run": run_name, "check": name, "ok": bool(ok), "detail": detail}
        self.checks.append(entry)
        if not ok:
            self.failures.append("%s: %s %s" % (run_name, name, detail))
        return bool(ok)

    def run_command(self, name, argv, cwd):
        argv = [str(part) for part in argv]
        started = time.monotonic()
        timed_out = False
        try:
            process = subprocess.run(
                argv, cwd=str(cwd), capture_output=True, timeout=self.timeout)
            code = process.returncode
            stdout = process.stdout
            stderr = process.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            code = None
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
        wall = time.monotonic() - started
        (self.out / (name + ".stdout.txt")).write_bytes(stdout)
        (self.out / (name + ".stderr.txt")).write_bytes(stderr)
        record = {
            "name": name,
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": code,
            "timed_out": timed_out,
            "wall_seconds": round(wall, 3),
            "at_utc": utc_now(),
            "stdout_sha256": sha256_bytes(stdout),
            "stderr_sha256": sha256_bytes(stderr),
        }
        (self.out / (name + ".command.json")).write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8")
        self.records.append(record)
        print("[run] %-24s exit=%s timed_out=%s wall=%.2fs"
              % (name, code, timed_out, wall))
        return record, stdout, stderr


def expected_meta(fixture):
    return {
        "error": 0,
        "count": fixture["sample_count"],
        "e": fixture["e"],
        "raw": fixture["raw"],
        "k": fixture["k"],
        "bits": fixture["valid_bits"],
        "bytes": fixture["bytes"],
    }


def error_meta(code):
    return {
        "error": code,
        "count": 0,
        "e": 0,
        "raw": 1,
        "k": 0,
        "bits": 0,
        "bytes": 0,
    }


def meta_matches(observed, expected):
    for key in ("error", "count", "e", "raw", "k", "bits", "bytes"):
        if observed[key] != expected[key]:
            return False, key, observed[key], expected[key]
    return True, None, None, None


def validate_case(report_id, record_id, expected, cfg, sample, meta, data,
                  parsed, runner, records):
    case_record = parsed["cases"].get(report_id)
    if case_record is None:
        runner.check("case_%s" % report_id, "reported", False, "missing TB_CASE")
        return
    runner.check("case_%s" % report_id, "pass", case_record["pass"] == 1,
                 "pass=%d" % case_record["pass"])
    for key, wanted in (("cfg", cfg), ("sample", sample),
                        ("meta", meta), ("data", data)):
        runner.check("case_%s" % report_id, "count_" + key,
                     case_record[key] == wanted,
                     "observed=%d expected=%d" % (case_record[key], wanted))

    observed_meta = None
    if expected["meta"] is None:
        runner.check("case_%s" % report_id, "no_meta",
                     not parsed["meta"].get(report_id), "unexpected TB_META")
    else:
        metas = parsed["meta"].get(report_id, [])
        if len(metas) != 1:
            runner.check("case_%s" % report_id, "single_meta", False,
                         "found=%d" % len(metas))
        else:
            observed_meta = metas[0]
            ok, key, seen, wanted = meta_matches(observed_meta, expected["meta"])
            runner.check("case_%s" % report_id, "meta_" + str(key), ok,
                         "observed=%r expected=%r" % (seen, wanted))
            if expected["meta"]["error"] == 0:
                runner.check("case_%s" % report_id, "meta_within_20000",
                             observed_meta["cycles"] <= MAX_CYCLES_LAST_TO_META,
                             "cycles=%d" % observed_meta["cycles"])

    observed_payload = None
    if expected["payload"] is None:
        runner.check("case_%s" % report_id, "no_payload",
                     not parsed["payload"].get(report_id), "unexpected TB_PAYLOAD")
    else:
        payloads = parsed["payload"].get(report_id, [])
        if len(payloads) != 1:
            runner.check("case_%s" % report_id, "single_payload", False,
                         "found=%d" % len(payloads))
        else:
            observed_payload = payloads[0]
            wanted = list(expected["payload"])
            runner.check("case_%s" % report_id, "payload_length",
                         observed_payload["n"] == len(wanted),
                         "observed=%d expected=%d"
                         % (observed_payload["n"], len(wanted)))
            runner.check("case_%s" % report_id, "payload_bytes",
                         observed_payload["bytes"] == wanted,
                         "observed=%s" % observed_payload["bytes"][:16])

    records.append({
        "id": record_id,
        "kind": expected["kind"],
        "e": expected.get("e"),
        "samples": expected.get("samples"),
        "tags": expected.get("tags", []),
        "expected_meta": expected["meta"],
        "expected_payload_hex": (None if expected["payload"] is None
                                 else bytes(expected["payload"]).hex()),
        "observed_meta": observed_meta,
        "observed_payload_hex": (None if observed_payload is None
                                 else bytes(observed_payload["bytes"]).hex()),
        "counts": case_record,
        "checks": parsed["checks"].get(report_id, []),
        "pass": case_record["pass"] == 1,
    })


def validate_results(cases, directed, parsed, runner):
    records = []
    all_ids = (["V%d" % index for index in range(len(cases))]
               + [item["id"] for item in directed])
    if len(all_ids) != len(set(all_ids)):
        runner.check("plan", "unique_case_ids", False, "duplicate ids in plan")

    for index, case in enumerate(cases):
        validate_case(
            "V%d" % index, case["id"],
            {"kind": "vector", "e": case["e"], "samples": case["samples"],
             "tags": case["tags"], "meta": expected_meta(case["fixture"]),
             "payload": case["fixture"]["payload"]},
            1, len(case["samples"]), 1, case["fixture"]["bytes"],
            parsed, runner, records)

    for item in directed:
        if item["kind"] == "legal":
            fixture = item["fixture"]
            expected = {"kind": "legal", "e": item["vec"]["e"],
                        "samples": item["vec"]["samples"], "tags": ["directed"],
                        "meta": expected_meta(fixture),
                        "payload": fixture["payload"]}
        elif item["kind"] == "error":
            expected = {"kind": "error", "e": None, "samples": None,
                        "tags": ["directed", "error"], "meta": error_meta(item["error"]),
                        "payload": None}
        elif item["kind"] == "abort":
            if "meta_vec" in item:
                expected = {"kind": "abort", "e": item["meta_vec"]["e"],
                            "samples": item["meta_vec"]["samples"],
                            "tags": ["directed", "abort"],
                            "meta": expected_meta(item["meta_fixture"]),
                            "payload": None}
            else:
                expected = {"kind": "abort", "e": None, "samples": None,
                            "tags": ["directed", "abort"], "meta": None,
                            "payload": None}
        else:
            expected = {"kind": "idle", "e": None, "samples": None,
                        "tags": ["directed", "idle"], "meta": None,
                        "payload": None}
        validate_case(item["id"], item["id"], expected, item["cfg"], item["sample"],
                      item["meta"], item["data"], parsed, runner, records)

    for name in parsed["cases"]:
        if name not in all_ids:
            runner.check("transcript", "unexpected_case_%s" % name, False,
                         "TB reported a case not present in the plan")
    for name in parsed["checks"]:
        if name not in all_ids:
            runner.check("transcript", "unexpected_checks_%s" % name, False,
                         "checks for an unknown case")

    expected_cfg = sum(item["cfg"] for item in directed) + sum(
        1 for _ in cases)
    expected_sample = sum(item["sample"] for item in directed) + sum(
        len(case["samples"]) for case in cases)
    expected_meta_hs = sum(item["meta"] for item in directed) + len(cases)
    expected_data_hs = sum(item["data"] for item in directed) + sum(
        case["fixture"]["bytes"] for case in cases)
    expected_errors = sum(1 for item in directed if item["kind"] == "error")
    expected_resets = sum(1 for item in directed if item["id"].startswith("D_reset"))
    expected_cancels = sum(1 for item in directed if item["id"].startswith("D_cancel"))
    expected_total = len(cases) + len(directed)
    expected_summary = (
        expected_total, expected_total, 0, expected_cfg, expected_sample,
        expected_meta_hs, expected_data_hs, expected_errors,
        expected_resets, expected_cancels)

    runner.check("transcript", "single_tb_summary", len(parsed["summary"]) == 1,
                 "found=%d" % len(parsed["summary"]))
    if len(parsed["summary"]) == 1:
        runner.check("transcript", "summary_exact", parsed["summary"][0] == expected_summary,
                     "observed=%r expected=%r"
                     % (parsed["summary"][0], expected_summary))
    runner.check("transcript", "stimulus_count", parsed["stimulus"] == [len(cases)],
                 "observed=%r expected=%d" % (parsed["stimulus"], len(cases)))
    runner.check("transcript", "single_done", parsed["done"] == 1,
                 "found=%d" % parsed["done"])
    runner.check("transcript", "end_pass", parsed["end"] == ["pass"],
                 "end=%r" % (parsed["end"],))
    runner.check("transcript", "all_cases_reported",
                 len(parsed["cases"]) == expected_total,
                 "reported=%d expected=%d" % (len(parsed["cases"]), expected_total))
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="fail-closed ModelSim runner for the B block-encoder candidate")
    parser.add_argument("--modelsim-home", required=True,
                        help="directory containing vlib.exe, vlog.exe and vsim.exe")
    parser.add_argument("--rtl", required=True, help="deepeye_block_encoder.sv")
    parser.add_argument("--tb", required=True, help="tb_block_encoder.sv")
    parser.add_argument("--golden", required=True,
                        help="pinned codec_reference.py or its directory")
    parser.add_argument("--output", required=True,
                        help="fresh output directory; must not exist yet")
    parser.add_argument("--known-vectors", default=None,
                        help="pinned known_vectors.json (default: sibling of golden)")
    parser.add_argument("--spec", default=None,
                        help="optional main design spec to hash and verify")
    parser.add_argument("--timeout-seconds", type=int,
                        default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)

    if not 1 <= args.timeout_seconds <= MAX_TIMEOUT_SECONDS:
        print("usage error: --timeout-seconds must be within 1..%d"
              % MAX_TIMEOUT_SECONDS, file=sys.stderr)
        return 2

    output = pathlib.Path(args.output).resolve()
    if output.exists():
        print("refusing pre-existing --output directory: %s" % output,
              file=sys.stderr)
        return 2

    home = pathlib.Path(args.modelsim_home).resolve()
    tools = {stem: home / (stem + ".exe") for stem in ("vlib", "vlog", "vsim")}
    rtl = pathlib.Path(args.rtl).resolve()
    tb = pathlib.Path(args.tb).resolve()
    golden = pathlib.Path(args.golden).resolve()
    if golden.is_dir():
        golden = golden / "codec_reference.py"
    if args.known_vectors:
        vectors_path = pathlib.Path(args.known_vectors).resolve()
    else:
        candidate = golden.parent / "known_vectors.json"
        vectors_path = candidate if candidate.is_file() else None
    spec_path = pathlib.Path(args.spec).resolve() if args.spec else None

    required = [("rtl", rtl), ("tb", tb), ("golden", golden)]
    required += [(stem, tools[stem]) for stem in tools]
    if vectors_path is not None:
        required.append(("known-vectors", vectors_path))
    if spec_path is not None:
        required.append(("spec", spec_path))
    for label, path in required:
        if not path.is_file():
            print("environment error: missing %s: %s" % (label, path),
                  file=sys.stderr)
            return 2

    golden_sha = sha256_file(golden)
    if golden_sha != PINNED_GOLDEN_SHA256:
        print("environment error: golden SHA256 %s is not the pinned %s"
              % (golden_sha, PINNED_GOLDEN_SHA256), file=sys.stderr)
        return 2
    vectors_sha = None
    if vectors_path is not None:
        vectors_sha = sha256_file(vectors_path)
        if vectors_sha != PINNED_VECTORS_SHA256:
            print("environment error: known-vector SHA256 %s is not the pinned %s"
                  % (vectors_sha, PINNED_VECTORS_SHA256), file=sys.stderr)
            return 2
    spec_sha = None
    if spec_path is not None:
        spec_sha = sha256_file(spec_path)
        if spec_sha != PINNED_SPEC_SHA256:
            print("environment error: spec SHA256 %s is not the expected %s"
                  % (spec_sha, PINNED_SPEC_SHA256), file=sys.stderr)
            return 2
    rules_path = golden.parent / "integer_candidate_rules.json"
    rules_sha = sha256_file(rules_path) if rules_path.is_file() else None

    output.mkdir(parents=True)
    runner = Runner(output, args.timeout_seconds)
    print("fresh output directory: %s" % output)

    golden_module = load_golden(golden)
    vectors = None
    if vectors_path is not None:
        vectors = json.loads(vectors_path.read_text(encoding="utf-8"))
    cases = build_vector_cases(golden_module, vectors)
    directed = resolve_directed(golden_module)
    write_stimulus(output / "stimulus.vec", cases)

    cases_doc = []
    for case in cases:
        fixture = case["fixture"]
        cases_doc.append({
            "id": case["id"], "kind": "vector", "e": case["e"],
            "samples": case["samples"], "stall": case["stall"],
            "tags": case["tags"], "k_ties": case["k_ties"],
            "best_rice_bits": case["best_rice_bits"],
            "expected": {
                "mode": fixture["mode"], "k": fixture["k_fixture"],
                "sample_count": fixture["sample_count"],
                "valid_bit_count": fixture["valid_bits"],
                "payload_hex": fixture["payload_hex"],
            },
        })
    (output / "cases.json").write_text(
        json.dumps(cases_doc, indent=2) + "\n", encoding="utf-8")

    tool_hashes = {stem: sha256_file(path) for stem, path in tools.items()}
    start_record = {
        "task_id": TASK_ID, "task_version": TASK_VERSION, "work_id": WORK_ID,
        "operation_id": OPERATION_ID, "contract": CONTRACT, "at_utc": utc_now(),
        "output_dir": str(output), "output_created_fresh": True,
        "sources": {
            "rtl": {"path": str(rtl), "sha256": sha256_file(rtl)},
            "tb": {"path": str(tb), "sha256": sha256_file(tb)},
            "runner": {"path": str(pathlib.Path(__file__).resolve()),
                       "sha256": sha256_file(pathlib.Path(__file__).resolve())},
            "golden": {"path": str(golden), "sha256": golden_sha},
            "known_vectors": (None if vectors_path is None else
                              {"path": str(vectors_path), "sha256": vectors_sha}),
            "rules": (None if rules_path is None else
                      {"path": str(rules_path), "sha256": rules_sha}),
            "spec": (None if spec_path is None else
                     {"path": str(spec_path), "sha256": spec_sha}),
        },
        "modelsim_home": str(home), "tool_hashes": tool_hashes,
        "timeout_seconds": args.timeout_seconds,
        "vector_cases": len(cases), "directed_cases": len(directed),
        "total_cases": len(cases) + len(directed),
        "max_cycles_last_to_meta": MAX_CYCLES_LAST_TO_META,
    }
    (output / "runner-start.json").write_text(
        json.dumps(start_record, indent=2) + "\n", encoding="utf-8")

    version_records = {}
    for stem in ("vlog", "vsim"):
        record, stdout, _ = runner.run_command(
            stem + "-version", [tools[stem], "-version"], output)
        runner.check(stem + "-version", "exit_code_zero",
                     record["exit_code"] == 0, "exit=%r" % (record["exit_code"],))
        version_records[stem] = stdout.decode("utf-8", "replace").strip()
    (output / "tool-versions.json").write_text(
        json.dumps(version_records, indent=2) + "\n", encoding="utf-8")

    record, _, _ = runner.run_command("vlib-work", [tools["vlib"], "work"], output)
    runner.check("vlib-work", "exit_code_zero",
                 record["exit_code"] == 0, "exit=%r" % (record["exit_code"],))
    runner.check("vlib-work", "work_created", (output / "work").is_dir())

    record, stdout, stderr = runner.run_command(
        "vlog-compile",
        [tools["vlog"], "-sv", "-work", "work", str(rtl), str(tb)], output)
    runner.check("vlog-compile", "exit_code_zero",
                 record["exit_code"] == 0, "exit=%r" % (record["exit_code"],))
    errors_match = RE_VLOG_ERRORS.search(stdout)
    runner.check("vlog-compile", "zero_compile_errors",
                 errors_match is not None and int(errors_match.group(1)) == 0,
                 "matches=%r" % (errors_match.groups() if errors_match else None,))
    runner.check("vlog-compile", "no_error_marker",
                 b"** Error" not in stdout and b"** Error" not in stderr)
    runner.check("vlog-compile", "no_fatal_marker",
                 b"** Fatal:" not in stdout and b"** Fatal:" not in stderr)
    runner.check("vlog-compile", "tb_top_listed",
                 b"Top level modules:" in stdout and b"tb_block_encoder" in stdout)

    do_path = output / "run_sim.do"
    do_path.write_text(
        "onerror {quit -force -code 8}\n"
        "onbreak {quit -force -code 7}\n"
        "run 30000000 ns\n"
        'puts "RUNNER_REACHED_END"\n'
        "quit -force -code 0\n", encoding="ascii")
    record, stdout, stderr = runner.run_command(
        "vsim-run",
        [tools["vsim"], "-c", "-onfinish", "stop", "-do", str(do_path),
         "work.tb_block_encoder"], output)
    runner.check("vsim-run", "exit_code_zero",
                 record["exit_code"] == 0, "exit=%r" % (record["exit_code"],))
    runner.check("vsim-run", "not_timed_out", not record["timed_out"])
    for channel, data in (("stdout", stdout), ("stderr", stderr)):
        runner.check("vsim-run", channel + "_no_error_marker", b"** Error:" not in data)
        runner.check("vsim-run", channel + "_no_fatal_marker", b"** Fatal:" not in data)
    runner.check("vsim-run", "runner_reached_end",
                 bool(RE_RUNNER_END.search(stdout)))

    parsed = parse_transcript(stdout)
    records = validate_results(cases, directed, parsed, runner)

    port_log_path = output / "ports_raw.log"
    port_counts = {"cfg": 0, "sample": 0, "meta": 0, "data": 0,
                   "reset": 0, "cancel": 0}
    port_lines = 0
    if port_log_path.is_file():
        for line in port_log_path.read_text(encoding="ascii", errors="replace").splitlines():
            token = line.split(" ", 1)[0] if line else ""
            if token in port_counts:
                port_counts[token] += 1
            port_lines += 1
        port_sha = sha256_file(port_log_path)
    else:
        port_sha = None
    runner.check("vsim-run", "ports_raw_exists", port_log_path.is_file())
    for kind in ("cfg", "sample", "meta", "data", "reset", "cancel"):
        wanted = sum(record["counts"][kind] for record in records) if kind in (
            "cfg", "sample", "meta", "data") else sum(
                1 for item in directed if item["id"].startswith(
                    "D_" + kind))
        runner.check("vsim-run", "ports_raw_" + kind,
                     port_counts[kind] == wanted,
                     "observed=%d expected=%d"
                     % (port_counts[kind], wanted))

    status = "PASS" if not runner.failures else "FAIL"
    cycle_values = [record["observed_meta"]["cycles"] for record in records
                    if record["observed_meta"] is not None
                    and record["expected_meta"] is not None
                    and record["expected_meta"]["error"] == 0]
    raw_cases = sum(1 for case in cases if case["fixture"]["mode"] == "raw")
    rice_cases = len(cases) - raw_cases
    tie_cases = sum(1 for case in cases if len(case["k_ties"]) > 1)
    raw_tie_cases = sum(
        1 for case in cases
        if case["fixture"]["mode"] == "raw"
        and case["best_rice_bits"] == 16 * (len(case["samples"]) - 1))
    n_covered = sorted(set(len(case["samples"]) for case in cases))
    e_covered = sorted(set(case["e"] for case in cases))
    summary = {
        "status": status,
        "task_id": TASK_ID, "task_version": TASK_VERSION,
        "work_id": WORK_ID, "operation_id": OPERATION_ID,
        "contract": CONTRACT, "at_utc": utc_now(),
        "output_dir": str(output),
        "sources": start_record["sources"],
        "modelsim": {"home": str(home), "versions": version_records,
                     "tool_hashes": tool_hashes},
        "cases": {
            "vector": len(cases), "directed": len(directed),
            "total": len(cases) + len(directed),
            "pass": sum(1 for record in records if record["pass"]),
            "fail": sum(1 for record in records if not record["pass"]),
            "raw": raw_cases, "rice": rice_cases,
            "k_tie_cases": tie_cases, "raw_tie_cases": raw_tie_cases,
            "padding_cases": sum(
                1 for case in cases
                if case["fixture"]["valid_bits"] % 8 != 0),
            "max_payload_bytes": max(
                case["fixture"]["bytes"] for case in cases),
            "max_valid_bits": max(
                case["fixture"]["valid_bits"] for case in cases),
            "n1_cases": sum(1 for case in cases if len(case["samples"]) == 1),
            "n128_cases": sum(1 for case in cases if len(case["samples"]) == 128),
            "n_values_covered": n_covered,
            "e_values_covered": e_covered,
        },
        "ports_raw": {
            "path": str(port_log_path), "sha256": port_sha,
            "lines": port_lines, "counts": port_counts,
        },
        "timing": {
            "max_cycles_last_to_meta": (max(cycle_values) if cycle_values else None),
            "min_cycles_last_to_meta": (min(cycle_values) if cycle_values else None),
            "bound": MAX_CYCLES_LAST_TO_META,
            "cases_over_bound": sum(1 for value in cycle_values
                                    if value > MAX_CYCLES_LAST_TO_META),
        },
        "handshake_counts": {
            "cfg": sum(record["counts"]["cfg"] for record in records),
            "sample": sum(record["counts"]["sample"] for record in records),
            "meta": sum(record["counts"]["meta"] for record in records),
            "data": sum(record["counts"]["data"] for record in records),
            "error_meta": sum(1 for item in directed if item["kind"] == "error"),
            "resets": sum(1 for item in directed if item["id"].startswith("D_reset")),
            "cancels": sum(1 for item in directed if item["id"].startswith("D_cancel")),
        },
        "run_records": runner.records,
        "checks": runner.checks,
        "failures": runner.failures,
        "limitations": [
            "digital RTL simulation only; no synthesis, implementation, timing, resource or board result",
            "one-block inner-codec candidate only; this is not TRACE, not a public ABI and not B01/B03/system acceptance",
            "expected payloads are produced by the pinned golden reference; arithmetic is not independently re-derived beyond the k-tie/RAW-tie annotation helper",
            "reset/cancel are synchronous; integration must synchronize their sources and discard partially emitted frames",
            "throughput and resource claims are intentionally not made",
        ],
    }
    (output / "records.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8")
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    artifact_hashes = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name not in ("SHA256SUMS.txt",):
            artifact_hashes[path.relative_to(output).as_posix()] = sha256_file(path)
    (output / "artifact_hashes.json").write_text(
        json.dumps(artifact_hashes, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    lines = ["%s  %s" % (digest, name)
             for name, digest in sorted(artifact_hashes.items())]
    (output / "SHA256SUMS.txt").write_text(
        "\n".join(lines) + "\n", encoding="ascii")

    print("status=%s cases=%d checks=%d failures=%d"
          % (status, len(records), len(runner.checks), len(runner.failures)))
    print("records=%s" % (output / "records.json"))
    print("summary=%s" % (output / "summary.json"))
    for failure in runner.failures:
        print("FAIL: %s" % failure)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
