#!/usr/bin/env python3
"""Bounded ModelSim runner for deepeye_raw_scan_queue.

The runner snapshots the queue, the unchanged op21 collector, the new
testbench and the selected ModelSim configuration into each fresh case
directory.  It invokes hidden command-line simulator processes only and keeps
the complete raw streams.  Large trace-bearing streams are stored gzip-compressed
with both compressed and expanded hashes and byte counts.

This tool is an author-side bounded check.  It does not claim independent main
acceptance, synthesis, implementation, timing, CDC/RDC, board or system results.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Any


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TOOL_VERSION = "ModelSim SE-64 10.7/2017.12"
RTL_RELATIVE = Path(
    "competition/deepeye/fpga/acquisition/deepeye_raw_scan_queue.sv"
)
TB_RELATIVE = Path(
    "competition/deepeye/tests/rtl/acquisition/tb_raw_scan_queue.sv"
)
COLLECTOR_RELATIVE = Path(
    "competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv"
)
EXPECTED_COLLECTOR_SHA256 = (
    "fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d"
)

QUEUE_TOP = "tb_raw_scan_queue"
COMPOSITION_TOP = "tb_raw_scan_queue_composition"

PASS_RE = re.compile(r"^(?:# )?RAW_SCAN_PASS[ \t]*$", re.MULTILINE)
COMP_PASS_RE = re.compile(r"^(?:# )?RAW_SCAN_COMP_PASS[ \t]*$", re.MULTILINE)
QUEUE_STATS_RE = re.compile(
    r"^(?:# )?RAW_SCAN_STATS[ \t]+([^\r\n]*)$", re.MULTILINE
)
COMP_STATS_RE = re.compile(
    r"^(?:# )?RAW_SCAN_COMP_STATS[ \t]+([^\r\n]*)$", re.MULTILINE
)
SUMMARY_RE = re.compile(
    r"^(?:# )?Errors: (0|[1-9][0-9]*), Warnings: (0|[1-9][0-9]*)[ \t]*$",
    re.MULTILINE,
)
TOKEN_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=([^ \t\r\n]+)")
DUT_FATAL_RE = re.compile(
    r"^(?:# )?\*\* Fatal: "
    r"(deepeye_raw_scan_queue: (?:DEPTH|SEQ_W|TICK_W|TAG_W|STAT_W) out of range)"
    r"[ \t]*$",
    re.MULTILINE,
)
MISMATCH_RE = re.compile(
    r"^(?:# )?RAW_SCAN_(?:COMP_)?MISMATCH[ \t]+([^\r\n]*)$", re.MULTILINE
)

QUEUE_STATS_KEYS = {
    "case", "depth", "seq_w", "tick_w", "tag_w", "stat_w", "checks",
    "errors", "level", "accepted", "retired", "aborted", "true_accepted",
    "true_retired", "true_aborted", "cycles", "resets", "cancels",
    "stalls", "wrap_writes", "wrap_reads",
}
COMP_STATS_KEYS = {
    "case", "depth", "seq_w", "tick_w", "tag_w", "stat_w", "checks",
    "errors", "q_level", "q_accepted", "q_retired", "q_aborted",
    "q_true_accepted", "q_true_retired", "q_true_aborted", "c_events",
    "c_scans", "c_retired", "c_discarded", "c_order_errors", "c_overruns",
    "c_true_events", "c_true_scans", "c_true_retired", "c_true_discarded",
    "c_true_order_errors", "c_true_overruns", "c_armed", "c_partial_len",
    "c_exhausted", "c_occupied", "cycles",
}
QUEUE_NUMERIC_KEYS = QUEUE_STATS_KEYS - {"case"}
COMP_NUMERIC_KEYS = COMP_STATS_KEYS - {"case"}
MISMATCH_FIELDS = {
    "data", "ticks", "quality", "first_seq", "last_seq", "tag", "level",
    "stat_accepted", "stat_retired", "stat_aborted", "in_ready", "out_valid",
    "capacity_level", "capacity_ready", "capacity_valid", "full_bubble_level",
    "refill_level", "drain_level", "drain_valid", "empty_offer_level",
    "simultaneous_level", "combo_final_level", "held_cancel_level",
    "held_cancel_valid", "held_reset_level", "held_reset_accepted",
    "held_reset_retired", "held_reset_aborted", "stale_cancel_level",
    "stale_cancel_valid", "oldlevel8_accepted_before_cancel",
    "oldlevel8_cancel_aborted", "oldlevel8_cancel_level",
    "oldlevel8_cancel_accepted_preserved",
    "oldlevel8_cancel_retired_preserved", "abort_saturated",
    "wrap_writes_min", "wrap_reads_min", "abort_saturated_final",
    "final_level", "final_valid", "true_balance", "accepted_saturated",
    "retired_saturated", "drain_stuck", "guard_healthy_level",
    "c_out_valid", "q_in_ready", "q_out_valid", "q_cancel", "c_armed",
    "c_partial_len", "c_next_seq", "c_exhausted", "c_order_event",
    "c_overrun_event", "c_exhaust_event", "c_events", "c_scans",
    "c_retired", "c_discarded", "c_order_errors", "c_overruns", "q_level",
    "q_accepted", "q_retired", "q_aborted", "basic_overrun_present",
    "basic_stop_q_level", "basic_stop_abort_present", "exhaust_armed",
    "exhaust_flag", "exhaust_q_level", "exhaust_scans",
    "exhaust_ignored_events", "exhaust_partial_armed",
    "exhaust_partial_flag", "exhaust_partial_scans",
    "exhaust_partial_events", "exhaust_partial_discarded",
    "exhaust_partial_order_errors", "exhaust_stop_q_level",
    "exhaust_stop_abort_present", "drain_slot_valid",
}

FATAL_MESSAGES = {
    "DEPTH": "deepeye_raw_scan_queue: DEPTH out of range",
    "SEQ_W": "deepeye_raw_scan_queue: SEQ_W out of range",
    "TICK_W": "deepeye_raw_scan_queue: TICK_W out of range",
    "TAG_W": "deepeye_raw_scan_queue: TAG_W out of range",
    "STAT_W": "deepeye_raw_scan_queue: STAT_W out of range",
}

PARAM_DEFAULTS = {
    "DEPTH": 4, "SEQ_W": 32, "TICK_W": 64, "TAG_W": 32, "STAT_W": 32,
}
PARAM_LIMITS = {
    "DEPTH": (1, 8), "SEQ_W": (2, 32), "TICK_W": (1, 64),
    "TAG_W": (1, 64), "STAT_W": (2, 32),
}


def _result(ok: bool, reasons: list[str] | None = None, **extra: Any):
    payload: dict[str, Any] = {"ok": ok, "reasons": list(reasons or [])}
    payload.update(extra)
    return payload


def _params(**overrides: int) -> dict[str, int]:
    result = dict(PARAM_DEFAULTS)
    result.update(overrides)
    return result


def _sim(
    name: str,
    case_arg: str,
    module: str,
    *,
    timeout: int = 600,
    **overrides: int,
) -> dict[str, Any]:
    return {
        "name": name, "kind": "simulation", "suite": "core",
        "case_arg": case_arg, "module": module, "params": _params(**overrides),
        "timeout": timeout,
    }


def _guard(name: str, family: str, **overrides: int) -> dict[str, Any]:
    params = _params(**overrides)
    return {
        "name": name, "kind": "guard", "suite": "guards",
        "case_arg": None, "module": None, "params": params,
        "timeout": 180, "expected_family": family,
    }


def _healthy_guard() -> dict[str, Any]:
    return {
        "name": "guard_healthy", "kind": "healthy", "suite": "guards",
        "case_arg": "guard_healthy",
        "module": QUEUE_TOP,
        "params": _params(DEPTH=1, SEQ_W=2, TICK_W=1, TAG_W=1, STAT_W=2),
        "timeout": 180,
    }


def _mutant(
    name: str,
    case_arg: str,
    old: str,
    new: str,
    required: list[tuple[str, int, int]],
    **overrides: int,
) -> dict[str, Any]:
    return {
        "name": name, "kind": "mutant", "suite": "mutants",
        "case_arg": case_arg, "module": QUEUE_TOP,
        "params": _params(**overrides), "timeout": 600,
        "mutation_old": old, "mutation_new": new,
        "required_mismatches": required,
    }


CASES: list[dict[str, Any]] = [
    _sim("queue_d1", "queue_directed", QUEUE_TOP,
         DEPTH=1, SEQ_W=2, TICK_W=1, TAG_W=1, STAT_W=2),
    _sim("queue_d2", "queue_directed", QUEUE_TOP,
         DEPTH=2, SEQ_W=32, TICK_W=16, TAG_W=64, STAT_W=3),
    _sim("queue_d3", "queue_directed", QUEUE_TOP,
         DEPTH=3, SEQ_W=7, TICK_W=1, TAG_W=1, STAT_W=3),
    _sim("queue_d4_defaults", "queue_directed", QUEUE_TOP),
    _sim("queue_d5", "queue_directed", QUEUE_TOP,
         DEPTH=5, SEQ_W=5, TICK_W=7, TAG_W=9, STAT_W=4),
    _sim("queue_d6", "queue_directed", QUEUE_TOP,
         DEPTH=6, SEQ_W=32, TICK_W=32, TAG_W=64, STAT_W=3),
    _sim("queue_d7", "queue_directed", QUEUE_TOP,
         DEPTH=7, SEQ_W=2, TICK_W=64, TAG_W=1, STAT_W=32),
    _sim("queue_d8_stat2", "queue_directed", QUEUE_TOP,
         DEPTH=8, SEQ_W=32, TICK_W=64, TAG_W=64, STAT_W=2),
    _sim("comp_d1", "comp_basic", COMPOSITION_TOP,
         DEPTH=1, SEQ_W=5, TICK_W=1, TAG_W=1, STAT_W=2),
    _sim("comp_d3", "comp_basic", COMPOSITION_TOP,
         DEPTH=3, SEQ_W=5, TICK_W=16, TAG_W=64, STAT_W=3),
    _sim("comp_d4_defaults", "comp_basic", COMPOSITION_TOP),
    _sim("comp_d5", "comp_basic", COMPOSITION_TOP,
         DEPTH=5, SEQ_W=5, TICK_W=7, TAG_W=9, STAT_W=4),
    _sim("comp_exhaust", "comp_exhaust", COMPOSITION_TOP,
         DEPTH=4, SEQ_W=2, TICK_W=64, TAG_W=64, STAT_W=2),
    _guard("guard_depth_0", "DEPTH", DEPTH=0),
    _guard("guard_depth_9", "DEPTH", DEPTH=9),
    _guard("guard_seq_w_1", "SEQ_W", SEQ_W=1),
    _guard("guard_seq_w_33", "SEQ_W", SEQ_W=33),
    _guard("guard_tick_w_0", "TICK_W", TICK_W=0),
    _guard("guard_tick_w_65", "TICK_W", TICK_W=65),
    _guard("guard_tag_w_0", "TAG_W", TAG_W=0),
    _guard("guard_tag_w_65", "TAG_W", TAG_W=65),
    _guard("guard_stat_w_1", "STAT_W", STAT_W=1),
    _guard("guard_stat_w_33", "STAT_W", STAT_W=33),
    _guard("guard_priority_depth", "DEPTH",
           DEPTH=0, SEQ_W=1, TICK_W=0, TAG_W=0, STAT_W=1),
    _healthy_guard(),
    _mutant(
        "mutant_wrap_depth5", "queue_directed",
        "        if (p == PTR_LAST) begin\n"
        "            next_wr_ptr = '0;",
        "        if (p == (PTR_LAST - 1'b1)) begin\n"
        "            next_wr_ptr = '0;",
        [("data", 4096, 4100)],
        DEPTH=5, SEQ_W=5, TICK_W=7, TAG_W=9, STAT_W=4,
    ),
    _mutant(
        "mutant_cancel_depth5", "queue_directed",
        "            stat_aborted_q <= sat_abort(stat_aborted_q, level_q);\n"
        "            level_q         <= {LEVEL_W{1'b0}};",
        "            stat_aborted_q <= sat_abort(stat_aborted_q, level_q);\n"
        "            level_q         <= level_q;",
        [("level", 0, 5)],
        DEPTH=5, SEQ_W=5, TICK_W=7, TAG_W=9, STAT_W=4,
    ),
]
CASE_BY_NAME = {entry["name"]: entry for entry in CASES}
SUITES = ("all", "core", "guards", "mutants")


def _normal_lines(text: str):
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if line.startswith("# "):
            line = line[2:].strip()
        if line:
            yield line


def _strict_diagnostics(
    stdout: str,
    stderr: str,
    *,
    own_fatal: str | None = None,
) -> list[str]:
    reasons: list[str] = []
    summaries: list[tuple[int, int]] = []
    own_fatals: list[str] = []
    for origin, text in (("stdout", stdout), ("stderr", stderr)):
        for line in _normal_lines(text):
            summary = SUMMARY_RE.fullmatch(line)
            if summary:
                if origin != "stdout":
                    reasons.append("diagnostic summary on stderr")
                summaries.append((int(summary.group(1)), int(summary.group(2))))
                continue
            if own_fatal is not None and line == f"** Fatal: {own_fatal}":
                if origin != "stdout":
                    reasons.append("own fatal on stderr")
                own_fatals.append(line)
                continue
            if line.startswith((
                "RAW_SCAN_STATS ", "RAW_SCAN_COMP_STATS ",
                "RAW_SCAN_MISMATCH ", "RAW_SCAN_COMP_MISMATCH ",
                "RAW_SCAN_TRACE ", "RAW_SCAN_COMP_TRACE ",
            )) or line in (
                "RAW_SCAN_PASS", "RAW_SCAN_COMP_PASS", "RAW_SCAN_GUARD_ALIVE",
            ):
                continue
            if re.search(r"\b(?:error|errors|warning|warnings|fatal)\b",
                         line, flags=re.IGNORECASE | re.ASCII):
                reasons.append(f"unexpected diagnostic: {line}")
    expected_summary = (1, 0) if own_fatal is not None else (0, 0)
    if summaries != [expected_summary]:
        reasons.append(
            "nonunique/inconsistent error-warning summary: "
            f"expected {[expected_summary]} actual {summaries}"
        )
    if own_fatal is not None and len(own_fatals) != 1:
        reasons.append("exact own fatal line is not unique")
    return reasons


def _structured_rows(stdout: str, stderr: str):
    keys = (
        "RAW_SCAN_PASS", "RAW_SCAN_COMP_PASS", "RAW_SCAN_STATS",
        "RAW_SCAN_COMP_STATS", "RAW_SCAN_MISMATCH",
        "RAW_SCAN_COMP_MISMATCH", "RAW_SCAN_TRACE",
        "RAW_SCAN_COMP_TRACE", "RAW_SCAN_GUARD_ALIVE",
    )
    rows = {key: [] for key in keys}
    bad: list[str] = []
    exact = {"RAW_SCAN_PASS", "RAW_SCAN_COMP_PASS", "RAW_SCAN_GUARD_ALIVE"}
    for origin, text in (("stdout", stdout), ("stderr", stderr)):
        for line in _normal_lines(text):
            for key in keys:
                if key not in line:
                    continue
                if origin != "stdout":
                    bad.append(f"structured marker on stderr: {line}")
                if key in exact:
                    valid = line == key
                else:
                    valid = line.startswith(key + " ")
                if valid:
                    rows[key].append(line)
                else:
                    bad.append(f"malformed structured marker: {line}")
    return rows, bad


def _parse_stats(
    stdout: str,
    regex: re.Pattern[str],
    expected_keys: set[str],
    numeric_keys: set[str],
    label: str,
) -> dict[str, Any]:
    stdout = stdout.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(regex.finditer(stdout))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {label} line, found {len(matches)}")
    body = matches[0].group(1).strip()
    pairs = TOKEN_RE.findall(body)
    reconstructed = " ".join(f"{key}={value}" for key, value in pairs)
    if " ".join(body.split()) != reconstructed:
        raise ValueError(f"{label} contains malformed key=value text")
    values: dict[str, str] = {}
    for key, value in pairs:
        if key in values:
            raise ValueError(f"duplicate {label} key {key}")
        values[key] = value
    if set(values) != expected_keys:
        missing = sorted(expected_keys - set(values))
        extra = sorted(set(values) - expected_keys)
        raise ValueError(f"{label} key mismatch missing={missing} extra={extra}")
    parsed: dict[str, Any] = {"case": values["case"]}
    for key in numeric_keys:
        if not re.fullmatch(r"[0-9]+", values[key]):
            raise ValueError(f"non-negative decimal required for {key}")
        parsed[key] = int(values[key])
    return parsed


def parse_queue_stats(stdout: str, *, require_wrap: bool = True) -> dict[str, Any]:
    stats = _parse_stats(
        stdout, QUEUE_STATS_RE, QUEUE_STATS_KEYS, QUEUE_NUMERIC_KEYS,
        "RAW_SCAN_STATS",
    )
    if stats["checks"] <= 0:
        raise ValueError("checks must be positive")
    if require_wrap and (stats["wrap_writes"] < 1000 or stats["wrap_reads"] < 1000):
        raise ValueError("reported wrap circuits below 1000")
    return stats


def parse_comp_stats(stdout: str) -> dict[str, Any]:
    stats = _parse_stats(
        stdout, COMP_STATS_RE, COMP_STATS_KEYS, COMP_NUMERIC_KEYS,
        "RAW_SCAN_COMP_STATS",
    )
    if stats["checks"] <= 0:
        raise ValueError("checks must be positive")
    for key in ("c_armed", "c_exhausted", "c_occupied"):
        if stats[key] not in (0, 1):
            raise ValueError(f"{key} outside 0..1")
    if not 0 <= stats["c_partial_len"] <= 3:
        raise ValueError("c_partial_len outside 0..3")
    return stats


def _mismatch_rows(stdout: str) -> list[dict[str, str]]:
    stdout = stdout.replace("\r\n", "\n").replace("\r", "\n")
    result: list[dict[str, str]] = []
    for match in MISMATCH_RE.finditer(stdout):
        pairs = TOKEN_RE.findall(match.group(1))
        row: dict[str, str] = {}
        for key, value in pairs:
            if key in row:
                continue
            row[key] = value
        result.append(row)
    return result


def _params_match(stats: dict[str, Any], params: dict[str, int]) -> list[str]:
    reasons: list[str] = []
    key_map = {
        "DEPTH": "depth", "SEQ_W": "seq_w", "TICK_W": "tick_w",
        "TAG_W": "tag_w", "STAT_W": "stat_w",
    }
    for param, key in key_map.items():
        if stats.get(key) != params[param]:
            reasons.append(
                f"stats identity {key}={stats.get(key)!r} expected {params[param]}"
            )
    return reasons


def _sat_identity(prefix: str, stat_key: str, true_key: str,
                  stat_w: int, stats: dict[str, Any]) -> list[str]:
    maximum = (1 << stat_w) - 1
    public = stats[stat_key]
    expected = min(stats[true_key], maximum)
    if public != expected:
        return [
            f"{prefix} saturation mismatch: public={public} "
            f"true={stats[true_key]} max={maximum}"
        ]
    return []


# Main-authored repair02. This code is copied into the self-contained public
# runner; it imports neither the frozen independent oracle nor private files.
_Q_TRACE_FIELDS = "side case cycle rst cancel in_valid in_ready in_data in_ticks in_quality in_first_seq in_last_seq in_tag out_valid out_ready out_data out_ticks out_quality out_first_seq out_last_seq out_tag level stat_accepted stat_retired stat_aborted ref_level ref_accepted ref_retired ref_aborted".split()
_C_TRACE_FIELDS = "side case cycle rst stop rearm rearm_tag sample_strobe sample_channel sample_data sample_tick sample_quality consumer_ready c_out_valid c_out_data c_out_ticks c_out_quality c_out_first_seq c_out_last_seq c_out_tag c_armed c_partial_len c_next_seq c_exhausted c_order_event c_overrun_event c_exhaust_event c_events c_scans c_retired c_discarded c_order_errors c_overruns q_in_ready q_out_valid q_out_ready q_out_data q_out_ticks q_out_quality q_out_first_seq q_out_last_seq q_out_tag q_level q_accepted q_retired q_aborted ref_partial ref_slot ref_q_level ref_q_accepted ref_q_retired ref_q_aborted".split()
_RECORD_FIELDS = ("data", "ticks", "quality", "first_seq", "last_seq", "tag")
_C_COUNT_FIELDS = ("events", "scans", "retired", "discarded", "order_errors", "overruns")


def _trace_schema(params: dict[str, int], composition: bool):
    limits = {"DEPTH": (1, 8), "SEQ_W": (2, 32), "TICK_W": (1, 64),
              "TAG_W": (1, 64), "STAT_W": (2, 32)}
    if set(params) != set(limits) or any(
        type(params[k]) is not int or not lo <= params[k] <= hi
        for k, (lo, hi) in limits.items()
    ):
        raise ValueError("invalid trace parameter identity")
    schema = {k: (10, None) for k in (_C_TRACE_FIELDS if composition else _Q_TRACE_FIELDS)}
    for k in ("side", "case"):
        schema[k] = (0, None)
    controls = ("rst stop rearm sample_strobe consumer_ready c_out_valid c_armed c_exhausted c_order_event c_overrun_event c_exhaust_event q_in_ready q_out_valid q_out_ready ref_slot" if composition else "rst cancel in_valid in_ready out_valid out_ready").split()
    for k in controls:
        schema[k] = (2, 1)
    payload = {"data": 64, "ticks": 4 * params["TICK_W"], "quality": 32,
               "first_seq": params["SEQ_W"], "last_seq": params["SEQ_W"],
               "tag": params["TAG_W"]}
    for prefix in (("c_out_", "q_out_") if composition else ("in_", "out_")):
        for k, width in payload.items():
            schema[prefix + k] = (16, width)
    lw = max(1, params["DEPTH"].bit_length())
    if composition:
        schema.update(rearm_tag=(16, params["TAG_W"]), sample_data=(16, 16),
                      sample_tick=(16, params["TICK_W"]), sample_quality=(16, 8),
                      sample_channel=(10, 2), c_partial_len=(10, 3),
                      c_next_seq=(10, params["SEQ_W"]), q_level=(10, lw))
        for k in _C_COUNT_FIELDS:
            schema["c_" + k] = (10, params["STAT_W"])
        for k in ("accepted", "retired", "aborted"):
            schema["q_" + k] = (10, params["STAT_W"])
    else:
        schema["level"] = (10, lw)
        for k in ("accepted", "retired", "aborted"):
            schema["stat_" + k] = (10, params["STAT_W"])
    return schema


def _parse_trace_row(line: str, marker: str, schema: dict, case: str):
    # Unknown spellings are retained, never converted to zero. Whether a value
    # must be known is decided by the semantic bootstrap/validity policy.
    body = line[len(marker) + 1:]
    pairs = body.split()
    if " ".join(pairs) != body or len(pairs) != len(schema):
        raise ValueError("malformed trace field count/spacing")
    row = {}
    for token in pairs:
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=([^\s=]+)", token, re.ASCII)
        if not match:
            raise ValueError("malformed trace token")
        key, word = match.groups()
        if key not in schema or key in row:
            raise ValueError("unknown/duplicate trace field " + key)
        base, width = schema[key]
        if base == 0:
            value = word
        elif re.fullmatch(r"[xXzZ]+" if base != 16 else r"[0-9a-fA-FxXzZ]+", word, re.ASCII) and re.search("[xXzZ]", word):
            if width is not None and len(word) > ((width + 3) // 4 if base == 16 else width):
                raise ValueError("oversized unknown trace word " + key)
            if base == 16 and width is not None:
                # The minimum value checks known padding bits only; keep X/Z
                # symbolic below so inactive/bootstrap semantics are unchanged.
                known_bits = int(re.sub(r"[xXzZ]", "0", word), 16)
                if known_bits >= 1 << width:
                    raise ValueError("out-of-width known trace bits " + key)
            value = word.lower()
        else:
            pattern = {2: r"[01]+", 10: r"[0-9]+", 16: r"[0-9a-fA-F]+"}[base]
            if not re.fullmatch(pattern, word, re.ASCII):
                raise ValueError("invalid numeric trace field " + key)
            if width is not None and base in (2, 16) and len(word) > (width if base == 2 else (width + 3) // 4):
                raise ValueError("oversized trace encoding " + key)
            value = int(word, base)
            if width is not None and value >= 1 << width:
                raise ValueError("out-of-width trace field " + key)
        row[key] = value
    if set(row) != set(schema) or row["case"] != case:
        raise ValueError("trace field/case identity mismatch")
    return row


def _known(row: dict, keys):
    for key in keys:
        if type(row[key]) is not int:
            raise ValueError("unknown driven field " + key)


def _new_collector(armed=0, tag=0):
    return {"armed": armed, "tag": tag, "next_seq": 0, "exhausted": 0,
            "partial": [], "slot": None, "counts": dict.fromkeys(_C_COUNT_FIELDS, 0),
            "order_event": 0, "overrun_event": 0, "exhaust_event": 0}


def _advance_collector(c: dict, row: dict, retire: bool, params: dict):
    if row["rst"] or row["stop"] or row["rearm"]:
        return _new_collector(int(not row["rst"] and not row["stop"] and row["rearm"]), row["rearm_tag"] if not row["rst"] and not row["stop"] and row["rearm"] else 0)
    # Retire the old slot independently of a possible new completed scan.
    old_slot = c["slot"]
    if retire:
        c["slot"] = None
        c["counts"]["retired"] += 1
    for key in ("order_event", "overrun_event", "exhaust_event"):
        c[key] = 0
    if not (c["armed"] and row["sample_strobe"]):
        return c
    _known(row, ("sample_data", "sample_tick", "sample_quality", "sample_channel"))
    counts = c["counts"]
    counts["events"] += 1
    ordinal = c["next_seq"]
    event = (row["sample_data"], row["sample_tick"], row["sample_quality"], ordinal)
    channel = row["sample_channel"]
    if channel == len(c["partial"]):
        c["partial"].append(event)
    else:
        c["order_event"] = 1
        counts["order_errors"] += 1
        counts["discarded"] += len(c["partial"]) + (0 if channel == 0 else 1)
        c["partial"] = [event] if channel == 0 else []
    if len(c["partial"]) == 4:
        counts["scans"] += 1
        record = tuple(sum(e[lane] << (i * width) for i, e in enumerate(c["partial"])) for lane, width in ((0, 16), (1, params["TICK_W"]), (2, 8)))
        record += (c["partial"][0][3], ordinal, c["tag"])
        if old_slot is not None and not retire:
            counts["overruns"] += 1
            counts["discarded"] += 4
            c["overrun_event"] = 1
        else:
            c["slot"] = record
        c["partial"] = []
    if ordinal == (1 << params["SEQ_W"]) - 1:
        c["exhaust_event"] = 1
        c["armed"] = 0
        c["exhausted"] = 1
        counts["discarded"] += len(c["partial"])
        c["partial"] = []
    else:
        c["next_seq"] += 1
    return c


def _trace_history(rows: dict, marker: str, stats: dict, params: dict, *, mutant=False):
    result = {"reasons": [], "differences": [], "difference_count": 0,
              "numeric_counterexamples": set(), "metrics": {}, "source": "parsed input/control history; ref_* ignored"}
    reasons = result["reasons"]
    composition = marker == "RAW_SCAN_COMP_TRACE"
    try:
        schema = _trace_schema(params, composition)
        trace = rows[marker]
        if type(stats["cycles"]) is not int or stats["cycles"] <= 0 or len(trace) != 2 * stats["cycles"]:
            raise ValueError("trace row multiplicity/cycle mismatch")
        inputs = (("rst", "stop", "rearm", "rearm_tag", "sample_strobe", "sample_channel", "sample_data", "sample_tick", "sample_quality", "consumer_ready") if composition else ("rst", "cancel", "in_valid", "out_ready") + tuple("in_" + k for k in _RECORD_FIELDS))
        controls = ("rst", "stop", "rearm", "sample_strobe", "sample_channel", "consumer_ready") if composition else ("rst", "cancel", "in_valid", "out_ready")
        q = []
        counts = dict.fromkeys(("accepted", "retired", "aborted"), 0)
        c = _new_collector()
        initialized = False
        sat = (1 << params["STAT_W"]) - 1
        resets = cancels = 0
        hold = hold_best = 0
        segment = segment_best = (0, 0, 0)  # length, admissions, retirements

        def compare(row, key, expected, cycle, side):
            actual = row[key]
            if actual == expected:
                return
            result["difference_count"] += 1
            if len(result["differences"]) < 32:
                result["differences"].append({"cycle": cycle, "side": side, "field": key, "expected": expected, "actual": actual})
            if type(actual) is int:
                result["numeric_counterexamples"].add((key, expected, actual))

        def observe(row, cycle, side):
            abort = bool(row["rst"] or (row["stop"] or row["rearm"] if composition else row["cancel"]))
            if not initialized:
                if abort:
                    for k in (("q_in_ready", "q_out_valid", "c_out_valid") if composition else ("in_ready", "out_valid")):
                        compare(row, k, 0, cycle, side)
                return
            qp = "q_" if composition else ""
            compare(row, "q_in_ready" if composition else "in_ready", int(not abort and len(q) < params["DEPTH"]), cycle, side)
            compare(row, qp + "out_valid", int(not abort and bool(q)), cycle, side)
            compare(row, qp + "level", len(q), cycle, side)
            for key in counts:
                compare(row, ("q_" if composition else "stat_") + key, min(counts[key], sat), cycle, side)
            if q and not abort:
                for key, value in zip(_RECORD_FIELDS, q[0]):
                    compare(row, qp + "out_" + key, value, cycle, side)
            if composition:
                compare(row, "q_out_ready", row["consumer_ready"], cycle, side)
                compare(row, "c_out_valid", int(not abort and c["slot"] is not None), cycle, side)
                for key in ("armed", "next_seq", "exhausted", "order_event", "overrun_event", "exhaust_event"):
                    compare(row, "c_" + key, c[key], cycle, side)
                compare(row, "c_partial_len", len(c["partial"]), cycle, side)
                for key in _C_COUNT_FIELDS:
                    compare(row, "c_" + key, min(c["counts"][key], sat), cycle, side)
                if c["slot"] is not None and not abort:
                    for key, value in zip(_RECORD_FIELDS, c["slot"]):
                        compare(row, "c_out_" + key, value, cycle, side)

        def final_stat(key, expected):
            if stats[key] != expected:
                reasons.append(f"history stat {key}: expected {expected!r}, actual {stats[key]!r}")

        for index in range(stats["cycles"]):
            pre, post = [_parse_trace_row(trace[2 * index + offset], marker, schema, stats["case"]) for offset in (0, 1)]
            if (pre["side"], pre["cycle"], post["side"], post["cycle"]) != ("pre", index, "post", index + 1):
                raise ValueError("trace phase/cycle ordering mismatch")
            if any(pre[k] != post[k] for k in inputs):
                raise ValueError("driven input changed within edge pair")
            _known(pre, controls)
            if composition and pre["rearm"] and not (pre["rst"] or pre["stop"]):
                _known(pre, ("rearm_tag",))
            abort = bool(pre["rst"] or (pre["stop"] or pre["rearm"] if composition else pre["cancel"]))
            if not composition and pre["in_valid"] and not abort:
                _known(pre, tuple("in_" + k for k in _RECORD_FIELDS))
            observe(pre, index, "pre")
            resets += pre["rst"]
            if not composition:
                cancels += pre["cancel"]
            if pre["rst"]:
                q = []
                counts = dict.fromkeys(counts, 0)
                c = _new_collector()
                initialized = True
                hold = 0
                segment = (0, 0, 0)
            elif initialized:
                if abort:
                    counts["aborted"] += len(q)
                    q = []
                    hold = 0
                    segment = (0, 0, 0)
                else:
                    oldlevel = len(q)
                    incoming = c["slot"] if composition else tuple(pre["in_" + k] for k in _RECORD_FIELDS)
                    offer = incoming is not None if composition else bool(pre["in_valid"])
                    push = offer and oldlevel < params["DEPTH"]
                    pop = oldlevel > 0 and bool(pre["consumer_ready"] if composition else pre["out_ready"])
                    if pop:
                        q.pop(0)
                        counts["retired"] += 1
                    if push:
                        q.append(incoming)
                        counts["accepted"] += 1
                    if not composition:
                        eligible = not pre["in_valid"] and not pre["out_ready"] and oldlevel > 0
                        hold = hold + 1 if eligible else 0
                        hold_best = max(hold_best, hold)
                        if pre["in_valid"] and pre["out_ready"]:
                            segment = (segment[0] + 1, segment[1] + int(push), segment[2] + int(pop))
                            if segment[0] > segment_best[0]:
                                segment_best = segment
                        else:
                            segment = (0, 0, 0)
                if composition:
                    # The queue transfer was decided from the old slot and old
                    # occupancy. Abort clears its window before any sample.
                    c = _advance_collector(c, pre, False if abort else push, params)
            observe(post, index + 1, "post")
        if not initialized:
            raise ValueError("trace has no applied reset anchor")
        if not composition:
            for key in counts:
                final_stat("true_" + key, counts[key])
                final_stat(key, post["stat_" + key] if mutant else min(counts[key], sat))
            final_stat("level", post["level"] if mutant else len(q))
            metrics = {"resets": resets, "cancels": cancels, "stalls": hold_best,
                       "wrap_writes": segment_best[1] // params["DEPTH"],
                       "wrap_reads": segment_best[2] // params["DEPTH"]}
            for key, value in metrics.items():
                final_stat(key, value)
            result["metrics"] = dict(metrics, selected_transfer_segment=segment_best)
            if stats["case"] != "guard_healthy" and (hold_best < 4096 or min(metrics["wrap_writes"], metrics["wrap_reads"]) < 1000):
                reasons.append("derived coverage below directed-suite minimum")
        else:
            for key in counts:
                final_stat("q_true_" + key, counts[key])
                final_stat("q_" + key, min(counts[key], sat))
            final_stat("q_level", len(q))
            for key in _C_COUNT_FIELDS:
                final_stat("c_true_" + key, c["counts"][key])
                final_stat("c_" + key, min(c["counts"][key], sat))
            for key in ("armed", "exhausted"):
                final_stat("c_" + key, c[key])
            final_stat("c_partial_len", len(c["partial"]))
            final_stat("c_occupied", int(c["slot"] is not None))
        if result["difference_count"] and not mutant:
            reasons.append(f"public history mismatch: {result['difference_count']} observations")
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        reasons.append("invalid trace/history: " + str(exc))
    return result


def _history_report(history):
    # Keep an auditable bounded example list; full raw traces remain in receipts.
    report = dict(history)
    values = sorted(report.pop("numeric_counterexamples"))
    report["numeric_counterexample_count"] = len(values)
    report["numeric_counterexamples_sha256"] = hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()
    report["numeric_counterexample_samples"] = values[:32]
    return report


def classify_queue_output(
    sim_exit: int | None,
    stdout: str,
    stderr: str,
    expected_case: str,
    params: dict[str, int],
    *,
    healthy: bool = False,
) -> dict[str, Any]:
    rows, reasons = _structured_rows(stdout, stderr)
    reasons += _strict_diagnostics(stdout, stderr)
    if type(sim_exit) is not int or sim_exit != 0:
        reasons.append(f"simulation exit must be 0, got {sim_exit!r}")
    if len(rows["RAW_SCAN_PASS"]) != 1:
        reasons.append("RAW_SCAN_PASS marker not unique")
    if len(rows["RAW_SCAN_STATS"]) != 1:
        reasons.append("RAW_SCAN_STATS marker not unique")
    for key in ("RAW_SCAN_COMP_PASS", "RAW_SCAN_COMP_STATS"):
        if rows[key]:
            reasons.append(f"unexpected {key} marker")
    if rows["RAW_SCAN_MISMATCH"] or rows["RAW_SCAN_COMP_MISMATCH"]:
        reasons.append("unexpected mismatch marker")
    if rows["RAW_SCAN_COMP_TRACE"]:
        reasons.append("unexpected composition trace")
    if healthy and len(rows["RAW_SCAN_GUARD_ALIVE"]) != 1:
        reasons.append("healthy guard marker not unique")
    if not healthy and rows["RAW_SCAN_GUARD_ALIVE"]:
        reasons.append("unexpected healthy guard marker")
    stats = None
    history = None
    try:
        stats = parse_queue_stats(stdout, require_wrap=not healthy)
        if stats["case"] != expected_case:
            reasons.append(
                f"stats case {stats['case']!r} expected {expected_case!r}"
            )
        reasons += _params_match(stats, params)
        if stats["errors"] != 0:
            reasons.append(f"testbench errors={stats['errors']}")
        if stats["cycles"] <= 0 or stats["level"] != 0:
            reasons.append("invalid final cycle/level state")
        if stats["true_accepted"] != (
            stats["true_retired"] + stats["true_aborted"] + stats["level"]
        ):
            reasons.append("true record balance failed")
        for stat_key, true_key in (
            ("accepted", "true_accepted"), ("retired", "true_retired"),
            ("aborted", "true_aborted"),
        ):
            reasons += _sat_identity(
                "queue", stat_key, true_key, params["STAT_W"], stats
            )
        history = _trace_history(rows, "RAW_SCAN_TRACE", stats, params, mutant=False)
        reasons += history["reasons"]
        if healthy:
            if stats["case"] != "guard_healthy":
                reasons.append("healthy control wrong case")
        else:
            if stats["resets"] <= 0 or stats["cancels"] <= 0:
                reasons.append("reset/cancel coverage missing")
            if stats["stalls"] < 4096:
                reasons.append("nonempty stall coverage below 4096 cycles")
            if stats["wrap_writes"] < 1000 or stats["wrap_reads"] < 1000:
                reasons.append("wrap circuit coverage below 1000")
    except (ValueError, KeyError, TypeError) as exc:
        reasons.append(f"invalid queue stats: {exc}")
    return _result(not reasons, reasons, stats=stats,
                   classification="healthy" if healthy else "pass",
                   trace_rows=len(rows["RAW_SCAN_TRACE"]),
                   trace_history=None if history is None else _history_report(history))


def classify_composition_output(
    sim_exit: int | None,
    stdout: str,
    stderr: str,
    expected_case: str,
    params: dict[str, int],
) -> dict[str, Any]:
    rows, reasons = _structured_rows(stdout, stderr)
    reasons += _strict_diagnostics(stdout, stderr)
    if type(sim_exit) is not int or sim_exit != 0:
        reasons.append(f"simulation exit must be 0, got {sim_exit!r}")
    if len(rows["RAW_SCAN_COMP_PASS"]) != 1:
        reasons.append("RAW_SCAN_COMP_PASS marker not unique")
    if len(rows["RAW_SCAN_COMP_STATS"]) != 1:
        reasons.append("RAW_SCAN_COMP_STATS marker not unique")
    for key in ("RAW_SCAN_PASS", "RAW_SCAN_STATS"):
        if rows[key]:
            reasons.append(f"unexpected {key} marker")
    if rows["RAW_SCAN_MISMATCH"] or rows["RAW_SCAN_COMP_MISMATCH"]:
        reasons.append("unexpected mismatch marker")
    if rows["RAW_SCAN_TRACE"] or rows["RAW_SCAN_GUARD_ALIVE"]:
        reasons.append("unexpected queue-only marker")
    stats = None
    history = None
    try:
        stats = parse_comp_stats(stdout)
        if stats["case"] != expected_case:
            reasons.append(
                f"stats case {stats['case']!r} expected {expected_case!r}"
            )
        reasons += _params_match(stats, params)
        if stats["errors"] != 0:
            reasons.append(f"testbench errors={stats['errors']}")
        if stats["cycles"] <= 0:
            reasons.append("invalid final cycle count")
        if stats["q_level"] != 0 or stats["c_occupied"] != 0:
            reasons.append("composition did not finish drained")
        if stats["q_true_accepted"] != (
            stats["q_true_retired"] + stats["q_true_aborted"]
            + stats["q_level"]
        ):
            reasons.append("queue true record balance failed")
        for stat_key, true_key in (
            ("q_accepted", "q_true_accepted"),
            ("q_retired", "q_true_retired"),
            ("q_aborted", "q_true_aborted"),
        ):
            reasons += _sat_identity(
                "queue", stat_key, true_key, params["STAT_W"], stats
            )
        for stat_key, true_key in (
            ("c_events", "c_true_events"), ("c_scans", "c_true_scans"),
            ("c_retired", "c_true_retired"),
            ("c_discarded", "c_true_discarded"),
            ("c_order_errors", "c_true_order_errors"),
            ("c_overruns", "c_true_overruns"),
        ):
            reasons += _sat_identity(
                "collector", stat_key, true_key, params["STAT_W"], stats
            )
        event_rhs = (
            4 * (stats["c_true_retired"] + stats["c_occupied"])
            + stats["c_partial_len"] + stats["c_true_discarded"]
        )
        scan_rhs = (
            stats["c_true_retired"] + stats["c_occupied"]
            + stats["c_true_overruns"]
        )
        if stats["c_true_events"] != event_rhs:
            reasons.append("collector event conservation failed")
        if stats["c_true_scans"] != scan_rhs:
            reasons.append("collector scan conservation failed")
        history = _trace_history(rows, "RAW_SCAN_COMP_TRACE", stats, params, mutant=False)
        reasons += history["reasons"]
        if expected_case == "comp_basic":
            if stats["q_true_accepted"] <= 0 or stats["q_true_aborted"] <= 0:
                reasons.append("basic composition abort coverage missing")
        elif expected_case == "comp_exhaust":
            if stats["c_armed"] != 0 or stats["c_exhausted"] != 1:
                reasons.append("exhaustion/unarmed-drain coverage missing")
    except (ValueError, KeyError, TypeError) as exc:
        reasons.append(f"invalid composition stats: {exc}")
    return _result(not reasons, reasons, stats=stats, classification="pass",
                   trace_rows=len(rows["RAW_SCAN_COMP_TRACE"]),
                   trace_history=None if history is None else _history_report(history))


def _compile_ok(exit_code: int | None, stdout: str, stderr: str) -> dict[str, Any]:
    reasons = _strict_diagnostics(stdout, stderr)
    if type(exit_code) is not int or exit_code != 0:
        reasons.append(f"compile exit must be 0, got {exit_code!r}")
    return _result(not reasons, reasons)


def classify_guard_output(
    compile_exit: int | None,
    compile_stdout: str,
    compile_stderr: str,
    sim_exit: int | None,
    stdout: str,
    stderr: str,
    family: str,
    message: str,
) -> dict[str, Any]:
    reasons = _compile_ok(
        compile_exit, compile_stdout, compile_stderr
    )["reasons"]
    rows, bad = _structured_rows(stdout, stderr)
    reasons += bad
    if type(sim_exit) is not int or sim_exit != 0:
        reasons.append(f"guard simulation process exit must be 0, got {sim_exit!r}")
    reasons += _strict_diagnostics(stdout, stderr, own_fatal=message)
    normalized_stdout = stdout.replace("\r\n", "\n").replace("\r", "\n")
    fatals = DUT_FATAL_RE.findall(normalized_stdout)
    if fatals != [message]:
        reasons.append(
            f"own fatal body not exact and unique: expected {[message]} actual {fatals}"
        )
    for key, values in rows.items():
        if values:
            reasons.append(f"unexpected guard structured marker {key}")
    for line in _normal_lines(stdout + "\n" + stderr):
        if "RAW_SCAN_GUARD_SHELL" in line or "RAW_SCAN_GUARD_MISSING" in line:
            reasons.append("guard shell executed instead of DUT fatal")
    if family not in FATAL_MESSAGES:
        reasons.append(f"unknown guard family {family}")
    return _result(not reasons, reasons, classification="dut_guard_rejected")


def classify_mutant_output(
    compile_exit: int | None,
    compile_stdout: str,
    compile_stderr: str,
    sim_exit: int | None,
    stdout: str,
    stderr: str,
    expected_case: str,
    params: dict[str, int],
    required: list[tuple[str, int, int]],
) -> dict[str, Any]:
    reasons = _compile_ok(
        compile_exit, compile_stdout, compile_stderr
    )["reasons"]
    rows, bad = _structured_rows(stdout, stderr)
    reasons += bad
    reasons += _strict_diagnostics(stdout, stderr)
    if type(sim_exit) is not int or sim_exit != 0:
        reasons.append(f"mutant process exit must be 0, got {sim_exit!r}")
    if rows["RAW_SCAN_PASS"] or rows["RAW_SCAN_COMP_PASS"]:
        reasons.append("mutant unexpectedly printed a pass marker")
    if rows["RAW_SCAN_COMP_STATS"] or rows["RAW_SCAN_COMP_TRACE"]:
        reasons.append("mutant emitted composition-only markers")
    if rows["RAW_SCAN_GUARD_ALIVE"]:
        reasons.append("mutant emitted healthy-guard marker")
    if len(rows["RAW_SCAN_STATS"]) != 1:
        reasons.append("mutant stats not unique")
    if not rows["RAW_SCAN_MISMATCH"]:
        reasons.append("numeric mutant mismatch absent")
    stats = None
    history = None
    observed: list[tuple[str, int, int]] = []
    malformed_samples: list[str] = []
    nonnumeric_count = 0
    unknown_fields: set[str] = set()
    try:
        stats = parse_queue_stats(stdout)
        if stats["case"] != expected_case:
            reasons.append("mutant stats case mismatch")
        reasons += _params_match(stats, params)
        if stats["checks"] <= 0 or stats["errors"] <= 0:
            reasons.append("mutant stats do not show a nonempty failure")
        if stats["errors"] != len(rows["RAW_SCAN_MISMATCH"]):
            reasons.append("mutant stats errors differ from mismatch rows")
        history = _trace_history(rows, "RAW_SCAN_TRACE", stats, params, mutant=True)
        reasons += history["reasons"]
    except (ValueError, KeyError, TypeError) as exc:
        reasons.append(f"invalid mutant stats: {exc}")
    for line in rows["RAW_SCAN_MISMATCH"]:
        match = re.fullmatch(
            r"RAW_SCAN_MISMATCH field=([A-Za-z_][A-Za-z0-9_]*) "
            r"expected=([0-9]+) actual=([0-9]+)",
            line,
            flags=re.ASCII,
        )
        if not match:
            nonnumeric_count += 1
            if len(malformed_samples) < 8:
                malformed_samples.append(line)
            continue
        field, expected_text, actual_text = match.groups()
        expected_value = int(expected_text)
        actual_value = int(actual_text)
        if field not in MISMATCH_FIELDS:
            unknown_fields.add(field)
        if expected_value == actual_value:
            reasons.append("equal mutant values do not demonstrate a mismatch")
        observed.append((field, expected_value, actual_value))
    if not observed:
        reasons.append("no finite numeric public-port mutant counterexample")
    for field in sorted(unknown_fields):
        reasons.append(f"unknown numeric mutant mismatch field {field}")
    for required_tuple in required:
        if required_tuple not in observed:
            reasons.append(
                f"required public-port counterexample absent: {required_tuple}"
            )
    # check_rec uses payload names without the public out_ prefix. Map only
    # those six declared labels; values and all other port names stay exact.
    def trace_tuple(item):
        field, expected_value, actual_value = item
        return (("out_" + field) if field in _RECORD_FIELDS else field,
                expected_value, actual_value)
    if history is None or not history["numeric_counterexamples"].intersection(trace_tuple(item) for item in observed):
        reasons.append("reported mutant mismatch lacks numeric trace corroboration")
    if history is not None:
        for required_tuple in required:
            if trace_tuple(required_tuple) not in history["numeric_counterexamples"]:
                reasons.append(f"required mutant counterexample absent in trace: {required_tuple}")
    return _result(
        not reasons, reasons, stats=stats, mismatches=observed,
        nonnumeric_mismatch_count=nonnumeric_count,
        malformed_mismatch_samples=malformed_samples,
        classification="mutant_rejected",
        trace_history=None if history is None else _history_report(history),
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fsync_write(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _run_hidden(
    argv: list[str],
    cwd: Path,
    timeout: int | float,
    env: dict[str, str],
) -> dict[str, Any]:
    started_at = _utc_now()
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            creationflags=CREATE_NO_WINDOW,
        )
        stdout_bytes = completed.stdout
        stderr_bytes = completed.stderr
        exit_code: int | None = completed.returncode
        timed_out = False
        exception_type = None
        exception_message = None
    except subprocess.TimeoutExpired as exc:
        stdout_bytes = exc.stdout or b""
        stderr_bytes = exc.stderr or b""
        if isinstance(stdout_bytes, str):
            stdout_bytes = stdout_bytes.encode("utf-8", errors="replace")
        if isinstance(stderr_bytes, str):
            stderr_bytes = stderr_bytes.encode("utf-8", errors="replace")
        exit_code = None
        timed_out = True
        exception_type = type(exc).__name__
        exception_message = str(exc)
    except OSError as exc:
        stdout_bytes = b""
        stderr_bytes = b""
        exit_code = None
        timed_out = False
        exception_type = type(exc).__name__
        exception_message = str(exc)
    elapsed = time.monotonic() - started
    return {
        "argv": argv,
        "cwd": str(cwd),
        "exit": exit_code,
        "timed_out": timed_out,
        "elapsed_seconds": round(elapsed, 6),
        "started_at_utc": started_at,
        "ended_at_utc": _utc_now(),
        "exception_type": exception_type,
        "exception_message": exception_message,
        "stdout_bytes": stdout_bytes,
        "stderr_bytes": stderr_bytes,
    }


def _selected_env(env: dict[str, str]) -> dict[str, str]:
    keys = (
        "TMP", "TEMP", "TMPDIR", "PYTHONDONTWRITEBYTECODE",
        "PYTHONPYCACHEPREFIX", "MODELSIM", "MODELSIM_TMP",
    )
    return {key: env[key] for key in keys if key in env}


def _pending_invocation(
    case_dir: Path, tag: str, invocation: dict[str, Any], env: dict[str, str]
) -> None:
    _write_json(
        case_dir / f"{tag}.pending.json",
        {
            "argv": invocation["argv"],
            "cwd": invocation["cwd"],
            "environment": _selected_env(env),
            "timeout_seconds": invocation.get("timeout_seconds"),
            "created_at_utc": _utc_now(),
        },
    )


def _persist_invocation(
    case_dir: Path, tag: str, invocation: dict[str, Any], env: dict[str, str]
) -> dict[str, Any]:
    stdout_bytes = invocation.pop("stdout_bytes")
    stderr_bytes = invocation.pop("stderr_bytes")
    streams: dict[str, Any] = {}
    for stream_name, data in (("stdout", stdout_bytes), ("stderr", stderr_bytes)):
        plain_path = case_dir / f"{tag}.{stream_name}.bin"
        if len(data) >= 1024 * 1024:
            path = case_dir / f"{tag}.{stream_name}.bin.gz"
            compressed = gzip.compress(data, compresslevel=9, mtime=0)
            _fsync_write(path, compressed)
            streams[stream_name] = {
                "path": path.name,
                "compressed": True,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
                "line_count": (
                    0 if not data else
                    data.count(b"\n") + (0 if data.endswith(b"\n") else 1)
                ),
                "compressed_bytes": len(compressed),
                "compressed_sha256": sha256_bytes(compressed),
            }
        else:
            _fsync_write(plain_path, data)
            streams[stream_name] = {
                "path": plain_path.name,
                "compressed": False,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
                "line_count": (
                    0 if not data else
                    data.count(b"\n") + (0 if data.endswith(b"\n") else 1)
                ),
            }
    invocation["streams"] = streams
    invocation["environment"] = _selected_env(env)
    invocation["tempfile_gettempdir"] = tempfile.gettempdir()
    _write_json(case_dir / f"{tag}.invocation.json", invocation)
    invocation["stdout_text"] = stdout_bytes.decode("utf-8", errors="replace")
    invocation["stderr_text"] = stderr_bytes.decode("utf-8", errors="replace")
    return invocation


def _invoke(
    case_dir: Path,
    tag: str,
    argv: list[str],
    cwd: Path,
    timeout: int | float,
    env: dict[str, str],
) -> dict[str, Any]:
    intended = {
        "argv": argv, "cwd": str(cwd), "timeout_seconds": timeout,
    }
    _pending_invocation(case_dir, tag, intended, env)
    invocation = _run_hidden(argv, cwd, timeout, env)
    invocation["timeout_seconds"] = timeout
    return _persist_invocation(case_dir, tag, invocation, env)


def _version_check(
    modelsim_dir: Path, out: Path, env_base: dict[str, str]
) -> tuple[dict[str, Any], list[str]]:
    version_dir = out / "tool-check"
    version_dir.mkdir()
    temp_dir = version_dir / "tmp"
    cache_dir = version_dir / "cache"
    temp_dir.mkdir()
    cache_dir.mkdir()
    env = dict(env_base)
    env.update({
        "TMP": str(temp_dir), "TEMP": str(temp_dir), "TMPDIR": str(temp_dir),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": str(cache_dir / "pycache"),
    })
    versions: dict[str, Any] = {}
    reasons: list[str] = []
    banners = {
        "vlog": re.compile(
            r"Model Technology ModelSim SE-64 vlog 10\.7 Compiler "
            r"2017\.12 Dec  7 2017"
        ),
        "vsim": re.compile(
            r"Model Technology ModelSim SE-64 vsim 10\.7 Simulator "
            r"2017\.12 Dec  7 2017"
        ),
    }
    for tool in ("vlog", "vsim"):
        executable = modelsim_dir / f"{tool}.exe"
        invocation = _invoke(
            version_dir, tool, [str(executable), "-version"],
            version_dir, 30, env,
        )
        lines = list(_normal_lines(invocation["stdout_text"]))
        stderr_lines = list(_normal_lines(invocation["stderr_text"]))
        tool_reasons: list[str] = []
        if type(invocation["exit"]) is not int or invocation["exit"] != 0:
            tool_reasons.append(f"{tool} -version did not exit 0")
        if invocation["timed_out"]:
            tool_reasons.append(f"{tool} -version timed out")
        if len(lines) != 1 or not banners[tool].fullmatch(lines[0]):
            tool_reasons.append(f"{tool} version banner is not exact and unique")
        if stderr_lines:
            tool_reasons.append(f"{tool} version wrote stderr")
        versions[tool] = {
            "path": str(executable), "sha256": sha256_file(executable),
            "exit": invocation["exit"], "timed_out": invocation["timed_out"],
            "streams": invocation["streams"], "standard_output": lines,
            "ok": not tool_reasons, "reasons": tool_reasons,
        }
        reasons += tool_reasons
    return versions, reasons


def select_cases(suites: list[str], names: list[str]) -> list[dict[str, Any]]:
    unknown_names = sorted(set(names) - set(CASE_BY_NAME))
    if unknown_names:
        raise ValueError(f"unknown cases: {unknown_names}")
    unknown_suites = sorted(set(suites) - set(SUITES))
    if unknown_suites:
        raise ValueError(f"unknown suites: {unknown_suites}")
    if len(names) != len(set(names)):
        raise ValueError("duplicate --case selections are not allowed")
    chosen_suites = {"core", "guards", "mutants"} if "all" in suites else set(suites)
    selected: list[dict[str, Any]] = []
    for entry in CASES:
        if names and entry["name"] not in names:
            continue
        if names and entry["suite"] not in chosen_suites:
            raise ValueError(
                f"case {entry['name']} belongs to unselected suite {entry['suite']}"
            )
        if not names and entry["suite"] not in chosen_suites:
            continue
        selected.append(entry)
    if names and sorted(names) != sorted(entry["name"] for entry in selected):
        raise ValueError("not all requested cases were selected")
    if not selected:
        raise ValueError("case selection is empty")
    return selected


def _snapshot_inputs(
    root: Path, case_dir: Path, entry: dict[str, Any], ini: Path
) -> tuple[Path, Path, Path, Path, dict[str, Any]]:
    inputs = case_dir / "inputs"
    inputs.mkdir()
    rtl_source = (root / RTL_RELATIVE).resolve()
    tb_source = (root / TB_RELATIVE).resolve()
    collector_source = (root / COLLECTOR_RELATIVE).resolve()
    for path in (rtl_source, tb_source, collector_source, ini):
        if not path.is_file():
            raise FileNotFoundError(f"required input is missing: {path}")
    collector_hash = sha256_file(collector_source)
    if collector_hash != EXPECTED_COLLECTOR_SHA256:
        raise ValueError(
            "pinned collector hash mismatch: "
            f"{collector_hash} != {EXPECTED_COLLECTOR_SHA256}"
        )
    rtl_target = inputs / rtl_source.name
    tb_target = inputs / tb_source.name
    collector_target = inputs / collector_source.name
    shutil.copyfile(tb_source, tb_target)
    shutil.copyfile(collector_source, collector_target)
    original_text = rtl_source.read_text(encoding="utf-8")
    if entry["kind"] == "mutant":
        old = entry["mutation_old"]
        new = entry["mutation_new"]
        count = original_text.count(old)
        if count != 1:
            raise ValueError(f"mutation anchor count expected 1 actual {count}")
        mutated_text = original_text.replace(old, new, 1)
        rtl_target.write_text(mutated_text, encoding="utf-8", newline="\n")
        (case_dir / "mutation.patch.json").write_text(
            json.dumps(
                {"old": old, "new": new, "replacement_count": 1},
                ensure_ascii=False, indent=2, sort_keys=True,
            ) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    else:
        shutil.copyfile(rtl_source, rtl_target)
    config_target = case_dir / "modelsim.ini"
    shutil.copyfile(ini, config_target)
    report = {
        "root": str(root),
        "rtl_source": {"path": str(rtl_source), "sha256": sha256_file(rtl_source)},
        "rtl_input": {"path": str(rtl_target), "sha256": sha256_file(rtl_target)},
        "tb_source": {"path": str(tb_source), "sha256": sha256_file(tb_source)},
        "tb_input": {"path": str(tb_target), "sha256": sha256_file(tb_target)},
        "collector_source": {
            "path": str(collector_source), "sha256": collector_hash,
            "pinned": True,
        },
        "collector_input": {
            "path": str(collector_target), "sha256": sha256_file(collector_target),
        },
        "modelsim_ini_source": {"path": str(ini.resolve()), "sha256": sha256_file(ini)},
        "modelsim_ini_input": {
            "path": str(config_target), "sha256": sha256_file(config_target),
        },
        "mutation": entry["kind"] == "mutant",
    }
    return rtl_target, tb_target, collector_target, config_target, report


def _case_env(case_dir: Path, config: Path, env_base: dict[str, str]) -> dict[str, str]:
    temp_dir = case_dir / "tmp"
    cache_dir = case_dir / "cache"
    temp_dir.mkdir()
    cache_dir.mkdir()
    env = dict(env_base)
    env.update({
        "TMP": str(temp_dir), "TEMP": str(temp_dir), "TMPDIR": str(temp_dir),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": str(cache_dir / "pycache"),
        "MODELSIM": str(config),
        "MODELSIM_TMP": str(temp_dir),
    })
    return env


def run_case(
    root: Path,
    out: Path,
    modelsim_dir: Path,
    ini: Path,
    env_base: dict[str, str],
    entry: dict[str, Any],
) -> dict[str, Any]:
    name = entry["name"]
    case_dir = out / "cases" / name
    case_dir.mkdir(parents=True)
    try:
        rtl, tb, collector, config, inputs = _snapshot_inputs(
            root, case_dir, entry, ini
        )
        _write_json(case_dir / "inputs.json", inputs)
        env = _case_env(case_dir, config, env_base)
        vlib = modelsim_dir / "vlib.exe"
        vlog = modelsim_dir / "vlog.exe"
        vsim = modelsim_dir / "vsim.exe"
        vlib_run = _invoke(case_dir, "vlib", [str(vlib), "work"],
                           case_dir, 120, env)
        compile_run = _invoke(
            case_dir, "vlog",
            [
                str(vlog), "-sv", "-modelsimini", config.as_posix(),
                "-work", "work", str(rtl), str(collector), str(tb),
            ],
            case_dir, 240, env,
        )
        compile_result = _compile_ok(
            compile_run["exit"], compile_run["stdout_text"],
            compile_run["stderr_text"],
        )
        if vlib_run["timed_out"] or vlib_run["exit"] != 0:
            compile_result["ok"] = False
            compile_result["reasons"].append("vlib did not complete successfully")

        result: dict[str, Any]
        sim_run: dict[str, Any] | None = None
        if not compile_result["ok"]:
            result = _result(
                False,
                [f"compile: {reason}" for reason in compile_result["reasons"]],
                classification="compile_failed",
            )
        else:
            sim_argv = [
                str(vsim), "-c", "-modelsimini", config.as_posix(),
                "-lib", "work", "-do", "run -all; quit -f",
            ]
            for param_name, value in entry["params"].items():
                if entry["kind"] != "guard":
                    sim_argv.append(f"-g{param_name}={value}")
            if entry["kind"] == "guard":
                for param_name, value in entry["params"].items():
                    sim_argv.append(f"-g{param_name}={value}")
                sim_argv.append(QUEUE_TOP)
            else:
                sim_argv.extend([entry["module"], f"+CASE={entry['case_arg']}",
                                 "+TRACE"])
            sim_run = _invoke(
                case_dir, "vsim", sim_argv, case_dir, entry["timeout"], env
            )
            sim_exit = sim_run["exit"]
            if sim_run["timed_out"]:
                result = _result(
                    False, ["simulation timed out"], classification="timeout"
                )
            elif entry["kind"] == "guard":
                message = FATAL_MESSAGES[entry["expected_family"]]
                result = classify_guard_output(
                    compile_run["exit"], compile_run["stdout_text"],
                    compile_run["stderr_text"], sim_exit,
                    sim_run["stdout_text"], sim_run["stderr_text"],
                    entry["expected_family"], message,
                )
            elif entry["kind"] == "healthy":
                result = classify_queue_output(
                    sim_exit, sim_run["stdout_text"], sim_run["stderr_text"],
                    entry["case_arg"], entry["params"], healthy=True,
                )
            elif entry["kind"] == "mutant":
                result = classify_mutant_output(
                    compile_run["exit"], compile_run["stdout_text"],
                    compile_run["stderr_text"], sim_exit,
                    sim_run["stdout_text"], sim_run["stderr_text"],
                    entry["case_arg"], entry["params"],
                    entry["required_mismatches"],
                )
            elif entry["module"] == COMPOSITION_TOP:
                result = classify_composition_output(
                    sim_exit, sim_run["stdout_text"], sim_run["stderr_text"],
                    entry["case_arg"], entry["params"],
                )
            else:
                result = classify_queue_output(
                    sim_exit, sim_run["stdout_text"], sim_run["stderr_text"],
                    entry["case_arg"], entry["params"],
                )

        case_report = {
            "schema": 1,
            "name": name,
            "kind": entry["kind"],
            "case_arg": entry["case_arg"],
            "params": entry["params"],
            "inputs": inputs,
            "processes": {
                "vlib": _process_summary(vlib_run),
                "vlog": _process_summary(compile_run),
                "vsim": None if sim_run is None else _process_summary(sim_run),
            },
            "result": result,
        }
        _write_json(case_dir / "case.json", case_report)
        _write_json(case_dir / "result.json", result)
        return result
    except Exception as exc:
        result = _result(
            False,
            [f"runner exception: {type(exc).__name__}: {exc}"],
            classification="runner_exception",
        )
        _write_json(case_dir / "result.json", result)
        return result


def _process_summary(invocation: dict[str, Any]) -> dict[str, Any]:
    return {
        key: invocation.get(key)
        for key in (
            "argv", "cwd", "exit", "timed_out", "elapsed_seconds",
            "started_at_utc", "ended_at_utc", "exception_type",
            "exception_message", "timeout_seconds", "environment",
            "tempfile_gettempdir", "streams",
        )
    }


def aggregate_results(
    selected_names: list[str], results: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    reasons: list[str] = []
    if not selected_names or len(selected_names) != len(set(selected_names)):
        reasons.append("empty or duplicate selected case set")
    missing = [name for name in selected_names if name not in results]
    unexpected = [name for name in results if name not in selected_names]
    failed = [
        name for name in selected_names
        if name in results and results[name].get("ok") is not True
    ]
    if missing or unexpected or failed:
        reasons.append("missing, extra or nonpassing selected results")
    return _result(
        not reasons, reasons, selected=selected_names, missing=missing,
        unexpected=unexpected, failed=failed,
    )


def _validate_containment(root: Path, out: Path, env: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    try:
        out.resolve().relative_to(root.resolve())
    except ValueError:
        reasons.append("output is outside the containment root")
    for key in ("TMP", "TEMP", "TMPDIR"):
        value = env.get(key)
        if not value or not Path(value).is_absolute():
            reasons.append(f"{key} must be an absolute path")
            continue
        try:
            Path(value).resolve().relative_to(root.resolve())
        except ValueError:
            reasons.append(f"{key} is outside the containment root")
    if env.get("PYTHONDONTWRITEBYTECODE") != "1":
        reasons.append("PYTHONDONTWRITEBYTECODE must be 1")
    return reasons


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--modelsim", type=Path)
    parser.add_argument("--modelsim-ini", type=Path)
    parser.add_argument("--containment-root", type=Path)
    parser.add_argument("--suite", action="append", choices=SUITES)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--list-cases", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--self-test-out", type=Path)
    parser.add_argument("--verify-transcript", type=Path)
    parser.add_argument("--self-test-timeout-child", action="store_true")
    parser.add_argument("--self-test-nonzero-child", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.self_test_timeout_child:
        print("RAW_SCAN_PASS", flush=True)
        time.sleep(5)
        return 0
    if args.self_test_nonzero_child:
        print(_valid_queue_transcript(), end="")
        return 9
    if args.verify_transcript is not None:
        return _verify_transcript(args.verify_transcript)
    if args.self_test:
        if args.self_test_out is None:
            print("error: --self-test-out is required", file=sys.stderr)
            return 2
        return _run_self_test(args.self_test_out)
    if args.list_cases:
        for entry in CASES:
            params = ",".join(f"{key}={value}" for key, value in entry["params"].items())
            print(
                f"{entry['name']} suite={entry['suite']} kind={entry['kind']} "
                f"params={params}"
            )
        return 0

    required = [
        ("--root", args.root), ("--out", args.out),
        ("--modelsim", args.modelsim), ("--modelsim-ini", args.modelsim_ini),
        ("--containment-root", args.containment_root),
    ]
    missing = [name for name, value in required if value is None]
    if missing:
        print(f"error: missing required arguments: {missing}", file=sys.stderr)
        return 2
    root = args.root.resolve()
    out = args.out.resolve()
    modelsim_dir = args.modelsim.resolve()
    ini = args.modelsim_ini.resolve()
    containment = args.containment_root.resolve()
    env = os.environ.copy()
    reasons = _validate_containment(containment, out, env)
    if not (modelsim_dir / "vlog.exe").is_file() or not (
        modelsim_dir / "vsim.exe"
    ).is_file() or not (modelsim_dir / "vlib.exe").is_file():
        reasons.append("--modelsim must contain vlib.exe, vlog.exe and vsim.exe")
    if out.exists():
        reasons.append("--out must be a fresh absent directory")
    if not out.parent.is_dir():
        reasons.append("--out parent must exist")
    if not ini.is_file():
        reasons.append("--modelsim-ini is missing")
    if reasons:
        for reason in reasons:
            print(f"error: {reason}", file=sys.stderr)
        return 2
    try:
        selected = select_cases(args.suite or ["all"], args.case)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out.mkdir()
    tempfile.tempdir = None
    run_request = {
        "schema": 1,
        "root": str(root), "out": str(out), "modelsim": str(modelsim_dir),
        "modelsim_ini": str(ini), "containment_root": str(containment),
        "suites": args.suite or ["all"], "requested_cases": args.case,
        "selected": [entry["name"] for entry in selected],
        "tool_version_contract": TOOL_VERSION,
        "create_no_window": bool(CREATE_NO_WINDOW),
        "python": sys.version,
        "python_executable": sys.executable,
        "environment": _selected_env(env),
        "tempfile_gettempdir": tempfile.gettempdir(),
        "vivado": "not_run_no_synthesis_or_implementation_in_this_scope",
    }
    _write_json(out / "run_request.json", run_request)
    versions, version_reasons = _version_check(modelsim_dir, out, env)
    if version_reasons:
        summary = {
            "ok": False, "reasons": version_reasons,
            "selected": [entry["name"] for entry in selected],
            "tool_versions": versions, "results": {},
        }
        _write_json(out / "summary.json", summary)
        print("RAW_SCAN_QUEUE_RUN_FAIL")
        for reason in version_reasons:
            print(f"FAIL toolchain: {reason}")
        return 2

    results: dict[str, dict[str, Any]] = {}
    for entry in selected:
        result = run_case(root, out, modelsim_dir, ini, env, entry)
        results[entry["name"]] = result
        state = "PASS" if result.get("ok") else "FAIL"
        print(
            f"CASE {entry['name']} {state} "
            f"classification={result.get('classification')}"
        )
        for reason in result.get("reasons", []):
            print(f"  {reason}")
    aggregate = aggregate_results([entry["name"] for entry in selected], results)
    summary = {
        "ok": aggregate["ok"], "reasons": aggregate["reasons"],
        "selected": aggregate["selected"], "failed": aggregate["failed"],
        "missing": aggregate["missing"], "unexpected": aggregate["unexpected"],
        "tool_versions": versions,
        "results": {
            name: {
                "ok": result.get("ok"),
                "classification": result.get("classification"),
                "reasons": result.get("reasons"),
                "stats": result.get("stats"),
                "mismatches": result.get("mismatches"),
                "trace_rows": result.get("trace_rows"),
            }
            for name, result in results.items()
        },
    }
    _write_json(out / "summary.json", summary)
    if aggregate["ok"]:
        print("RAW_SCAN_QUEUE_RUN_PASS")
        return 0
    print("RAW_SCAN_QUEUE_RUN_FAIL")
    for reason in aggregate["reasons"]:
        print(f"FAIL {reason}")
    return 1


def _synthetic_queue_fixture(*, mutant=False) -> str:
    """Main-authored coherent synthetic history, not ModelSim/RTL evidence.

    Constructed separately from the trace validator. No validator call or
    imported expectation model supplies its records. Depth1, tiny payloads.
    """
    schedule = [(1, 0, 0, 0), (0, 0, 1, 0)]
    schedule += [(0, 0, 0, 0)] * 4096
    schedule += [(0, 0, 0, 1), (1, 0, 0, 0), (0, 0, 1, 0)]
    schedule += [(0, 0, 1, 1)] * 2008
    schedule += [(0, 0, 0, 1), (0, 1, 0, 0)]
    occupied = accepted = retired = aborted = 0
    lines = []
    for cycle, (rst, cancel, offered, ready) in enumerate(schedule):
        for side in ("pre", "post"):
            if side == "post":
                if rst:
                    occupied = accepted = retired = aborted = 0
                elif cancel:
                    aborted += occupied
                    occupied = 0
                elif occupied:
                    if ready:
                        occupied = 0
                        retired += 1
                elif offered:
                    occupied = 1
                    accepted += 1
            level = 1 if mutant and cycle == len(schedule) - 1 and side == "post" else occupied
            words = [f"side={side}", "case=queue_directed", f"cycle={cycle + (side == 'post')}",
                     f"rst={rst}", f"cancel={cancel}", f"in_valid={offered}",
                     f"in_ready={int(not (rst or cancel) and not occupied)}"]
            for prefix in ("in", "out"):
                if prefix == "out":
                    words += [f"out_valid={int(not (rst or cancel) and occupied)}", f"out_ready={ready}"]
                words += [prefix + "_" + key + "=1" for key in ("data", "ticks", "quality", "first_seq", "last_seq", "tag")]
            words += [f"level={level}", f"stat_accepted={min(accepted, 3)}", f"stat_retired={min(retired, 3)}", f"stat_aborted={min(aborted, 3)}", f"ref_level={occupied}", f"ref_accepted={accepted}", f"ref_retired={retired}", f"ref_aborted={aborted}"]
            lines.append("# RAW_SCAN_TRACE " + " ".join(words))
    if mutant:
        lines.append("# RAW_SCAN_MISMATCH field=level expected=0 actual=1")
    lines.append(f"# RAW_SCAN_STATS case=queue_directed depth=1 seq_w=2 tick_w=1 tag_w=1 stat_w=2 checks=1 errors={int(mutant)} level={int(mutant)} accepted={min(accepted,3)} retired={min(retired,3)} aborted={min(aborted,3)} true_accepted={accepted} true_retired={retired} true_aborted={aborted} cycles={len(schedule)} resets=2 cancels=1 stalls=4096 wrap_writes=1004 wrap_reads=1004")
    if not mutant:
        lines.append("# RAW_SCAN_PASS")
    lines.append("# Errors: 0, Warnings: 0")
    return "\n".join(lines) + "\n"


def _valid_queue_transcript() -> str:
    return _synthetic_queue_fixture()


def _verify_transcript(spec_path: Path) -> int:
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        base = spec_path.parent
        stdout = (base / spec["stdout"]).read_text(encoding="utf-8")
        stderr = (base / spec["stderr"]).read_text(encoding="utf-8")
        mode = spec["mode"]
        args = spec["args"]
        if mode == "queue":
            result = classify_queue_output(
                args["sim_exit"], stdout, stderr,
                args["expected_case"], args["params"],
            )
        elif mode == "healthy":
            result = classify_queue_output(
                args["sim_exit"], stdout, stderr,
                args["expected_case"], args["params"], healthy=True,
            )
        elif mode == "composition":
            result = classify_composition_output(
                args["sim_exit"], stdout, stderr,
                args["expected_case"], args["params"],
            )
        elif mode == "guard":
            result = classify_guard_output(
                args["compile_exit"], "# Errors: 0, Warnings: 0\n", "",
                args["sim_exit"], stdout, stderr,
                args["family"], FATAL_MESSAGES.get(args["family"], ""),
            )
        elif mode == "mutant":
            result = classify_mutant_output(
                args["compile_exit"], "# Errors: 0, Warnings: 0\n", "",
                args["sim_exit"], stdout, stderr,
                args["expected_case"], args["params"],
                [tuple(item) for item in args["required"]],
            )
        else:
            raise ValueError(f"unknown verify mode {mode}")
    except Exception as exc:
        print(f"VERIFY_TRANSCRIPT_ERROR {type(exc).__name__}: {exc}")
        return 2
    _write_json(base / (spec_path.stem + ".result.json"), result)
    if result["ok"]:
        print("VERIFY_TRANSCRIPT_PASS")
        return 0
    print("VERIFY_TRANSCRIPT_FAIL")
    for reason in result["reasons"]:
        print(f"  {reason}")
    return 1


def _write_fixture(directory: Path, name: str, stdout: str,
                   stderr: str = "") -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stdout_path = directory / f"{name}.stdout"
    stderr_path = directory / f"{name}.stderr"
    stdout_path.write_text(stdout, encoding="utf-8", newline="\n")
    stderr_path.write_text(stderr, encoding="utf-8", newline="\n")
    return stdout_path, stderr_path


def _run_self_test(out: Path) -> int:
    if out.exists():
        print(f"error: --self-test-out must be fresh: {out}", file=sys.stderr)
        return 2
    out.mkdir()
    fixtures = out / "fixtures"
    processes = out / "processes"
    fixtures.mkdir()
    processes.mkdir()
    valid = _valid_queue_transcript()
    error_text = valid + "# ** Error: injected parser error\n"
    warning_text = valid + "# ** Warning: injected parser warning\n"
    missing = valid.replace("# RAW_SCAN_PASS\n", "", 1)
    duplicate = valid + "# RAW_SCAN_PASS\n"
    substring = valid.replace("# RAW_SCAN_PASS", "# prefix RAW_SCAN_PASS", 1)
    malformed_stats = valid.replace("checks=1", "checks=x", 1)
    duplicate_stats = valid + next(
        line + "\n" for line in valid.splitlines()
        if "RAW_SCAN_STATS" in line
    )
    foreign_guard = (
        "# ** Fatal: deepeye_sample_scan_capture: SEQ_W out of range\n"
        "# Errors: 1, Warnings: 0\n"
    )
    own_guard = (
        "# ** Fatal: deepeye_raw_scan_queue: DEPTH out of range\n"
        "# Errors: 1, Warnings: 0\n"
    )
    numeric_mutant = _synthetic_queue_fixture(mutant=True)
    x_mutant = numeric_mutant.replace("expected=0 actual=1", "expected=0 actual=x", 1)
    hello = "hello\n"

    queue_args = {
        "sim_exit": 0, "expected_case": "queue_directed",
        "params": _params(DEPTH=1, SEQ_W=2, TICK_W=1, TAG_W=1, STAT_W=2),
    }
    specifications: list[dict[str, Any]] = [
        ("valid_queue", valid, "", "queue", queue_args, 0),
        ("nonzero_exit_success_text", valid, "", "queue",
         dict(queue_args, sim_exit=7), 1),
        ("explicit_error", error_text, "", "queue", queue_args, 1),
        ("explicit_warning", warning_text, "", "queue", queue_args, 1),
        ("missing_pass", missing, "", "queue", queue_args, 1),
        ("duplicate_pass", duplicate, "", "queue", queue_args, 1),
        ("substring_pass", substring, "", "queue", queue_args, 1),
        ("malformed_numeric", malformed_stats, "", "queue", queue_args, 1),
        ("duplicate_stats", duplicate_stats, "", "queue", queue_args, 1),
        ("foreign_guard", foreign_guard, "", "guard",
         {"sim_exit": 0, "compile_exit": 0, "family": "DEPTH"}, 1),
        ("own_guard", own_guard, "", "guard",
         {"sim_exit": 0, "compile_exit": 0, "family": "DEPTH"}, 0),
        ("numeric_mutant", numeric_mutant, "", "mutant",
         {"sim_exit": 0, "compile_exit": 0,
          "expected_case": "queue_directed",
          "params": _params(DEPTH=1, SEQ_W=2, TICK_W=1, TAG_W=1, STAT_W=2),
          "required": [["level", 0, 1]]}, 0),
        ("x_only_mutant", x_mutant, "", "mutant",
         {"sim_exit": 0, "compile_exit": 0,
          "expected_case": "queue_directed",
          "params": _params(DEPTH=1, SEQ_W=2, TICK_W=1, TAG_W=1, STAT_W=2),
          "required": [["level", 0, 1]]}, 1),
    ]
    entry_results: list[dict[str, Any]] = []
    for name, stdout_text, stderr_text, mode, args, expected_exit in specifications:
        stdout_path, stderr_path = _write_fixture(
            fixtures, name, stdout_text, stderr_text
        )
        spec = {
            "mode": mode, "stdout": stdout_path.name,
            "stderr": stderr_path.name, "args": args,
        }
        spec_path = fixtures / f"{name}.json"
        _write_json(spec_path, spec)
        invocation = _invoke(
            processes, name,
            [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()),
             "--verify-transcript", str(spec_path)],
            processes, 30, os.environ.copy(),
        )
        observed_exit = invocation["exit"]
        passed = observed_exit == expected_exit and not invocation["timed_out"]
        entry_results.append({
            "name": name, "mode": mode, "expected_exit": expected_exit,
            "observed_exit": observed_exit,
            "timed_out": invocation["timed_out"], "ok": passed,
            "stdout_sha256": invocation["streams"]["stdout"]["sha256"],
            "stderr_sha256": invocation["streams"]["stderr"]["sha256"],
        })

    timeout_env = os.environ.copy()
    timeout_run = _run_hidden(
        [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()),
         "--self-test-timeout-child"],
        processes, 0.5, timeout_env,
    )
    timeout_run = _persist_invocation(
        processes, "timeout_partial", timeout_run, timeout_env
    )
    timeout_ok = timeout_run["timed_out"] and timeout_run["exit"] is None
    timeout_result = _result(
        timeout_ok,
        [] if timeout_ok else ["timeout child was not reported as timed out"],
        classification="timeout" if timeout_ok else "unexpected",
    )
    _write_json(processes / "timeout_partial.result.json", timeout_result)

    nonzero_run = _run_hidden(
        [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()),
         "--self-test-nonzero-child"],
        processes, 30, os.environ.copy(),
    )
    nonzero_run = _persist_invocation(
        processes, "nonzero_process", nonzero_run, os.environ.copy()
    )
    nonzero_class = classify_queue_output(
        nonzero_run["exit"], nonzero_run["stdout_text"],
        nonzero_run["stderr_text"], "queue_directed",
        _params(DEPTH=1, SEQ_W=2, TICK_W=1, TAG_W=1, STAT_W=2),
    )
    _write_json(processes / "nonzero_process.result.json", nonzero_class)

    direct_checks = {
        "foreign_guard_rejected": not classify_guard_output(
            0, "", "", 0, foreign_guard, "", "DEPTH", FATAL_MESSAGES["DEPTH"]
        )["ok"],
        "x_mutant_rejected": not classify_mutant_output(
            0, "", "", 0, x_mutant, "", "queue_directed",
            _params(DEPTH=1, SEQ_W=2, TICK_W=1, TAG_W=1, STAT_W=2),
            [("level", 0, 1)],
        )["ok"],
        "nonzero_exit_rejected": not classify_queue_output(
            7, valid, "", "queue_directed",
            _params(DEPTH=1, SEQ_W=2, TICK_W=1, TAG_W=1, STAT_W=2),
        )["ok"],
        "valid_queue_accepted": classify_queue_output(
            0, valid, "", "queue_directed",
            _params(DEPTH=1, SEQ_W=2, TICK_W=1, TAG_W=1, STAT_W=2),
        )["ok"],
    }
    all_entries_ok = all(item["ok"] for item in entry_results)
    ok = (
        all_entries_ok and timeout_ok and nonzero_class["ok"] is False
        and all(direct_checks.values())
    )
    summary = {
        "schema": 1,
        "synthetic": True,
        "note": (
            "Synthetic parser/process fixtures only; these are not ModelSim, "
            "RTL, board or acceptance evidence."
        ),
        "ok": ok,
        "entry_negatives": entry_results,
        "actual_python_entry_negatives": [item for item in entry_results
                                          if item["expected_exit"] != 0],
        "timeout_process": {
            "ok": timeout_ok, "timed_out": timeout_run["timed_out"],
            "exit": timeout_run["exit"], "stdout_bytes":
            timeout_run["streams"]["stdout"]["bytes"],
        },
        "nonzero_process": {
            "exit": nonzero_run["exit"],
            "classification_ok": nonzero_class["ok"],
            "reasons": nonzero_class["reasons"],
        },
        "direct_checks": direct_checks,
    }
    _write_json(out / "self_test_summary.json", summary)
    if ok:
        print("RAW_SCAN_QUEUE_SELFTEST_PASS")
        return 0
    print("RAW_SCAN_QUEUE_SELFTEST_FAIL")
    for item in entry_results:
        if not item["ok"]:
            print(f"FAIL entry {item['name']}")
    for name, passed in direct_checks.items():
        if not passed:
            print(f"FAIL direct {name}")
    if not timeout_ok:
        print("FAIL timeout process")
    if nonzero_class["ok"] is not False:
        print("FAIL nonzero process classification")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
