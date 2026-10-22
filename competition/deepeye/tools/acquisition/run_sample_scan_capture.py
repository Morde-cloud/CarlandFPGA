#!/usr/bin/env python3
"""Scoped ModelSim runner for deepeye_sample_scan_capture.

The module exposes pure classification helpers so acceptance can test exit,
marker, statistics, guard, mutation and aggregation handling without invoking
ModelSim.  Runtime evidence is written only below the caller's fresh --out
directory.  Existing output directories are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TOOL_VERSION = "ModelSim SE-64 10.7"
RTL_RELATIVE = Path("competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv")
TB_RELATIVE = Path("competition/deepeye/tests/rtl/acquisition/tb_sample_scan_capture.sv")

PASS_RE = re.compile(r"^(?:# )?SAMPLE_SCAN_PASS[ \t]*$", re.MULTILINE)
ALIVE_RE = re.compile(r"^(?:# )?GUARD_CONTROL_ALIVE[ \t]*$", re.MULTILINE)
STATS_RE = re.compile(r"^(?:# )?SAMPLE_SCAN_STATS[ \t]+([^\r\n]*)$", re.MULTILINE)
MISMATCH_RE = re.compile(r"^(?:# )?SAMPLE_SCAN_MISMATCH[ \t]+([^\r\n]*)$", re.MULTILINE)
FATAL_BODY_RE = re.compile(
    r"deepeye_sample_scan_capture: (SEQ_W|TICK_W|TAG_W|STAT_W) out of range"
)
DUT_FATAL_LINE_RE = re.compile(
    r"^(?:# )?\*\* Fatal: "
    r"(deepeye_sample_scan_capture: (?:SEQ_W|TICK_W|TAG_W|STAT_W) out of range)"
    r"[ \t]*$",
    re.MULTILINE,
)
WARNING_RE = re.compile(r"\*\* Warning", re.IGNORECASE)
ERROR_RE = re.compile(r"\*\* Error", re.IGNORECASE)
SUMMARY_RE = re.compile(r"^(?:# )?Errors: ([0-9]+), Warnings: ([0-9]+)\s*$", re.MULTILINE)
TOKEN_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=([^ \t\r\n]+)")

STATS_KEYS = {
    "case",
    "checks",
    "errors",
    "windows",
    "events",
    "scans",
    "retired",
    "discarded",
    "order_errors",
    "overruns",
    "partial_len",
    "occupied",
    "armed",
    "exhausted",
}
COUNTER_KEYS = {
    "events",
    "scans",
    "retired",
    "discarded",
    "order_errors",
    "overruns",
    "partial_len",
    "occupied",
    "armed",
    "exhausted",
}
FATAL_MESSAGES = {
    "SEQ_W": "deepeye_sample_scan_capture: SEQ_W out of range",
    "TICK_W": "deepeye_sample_scan_capture: TICK_W out of range",
    "TAG_W": "deepeye_sample_scan_capture: TAG_W out of range",
    "STAT_W": "deepeye_sample_scan_capture: STAT_W out of range",
}

EXPECTED_FINAL_STATS: dict[str, dict[str, int]] = {
    "directed": {"events": 14, "scans": 3, "retired": 2, "discarded": 6,
                 "order_errors": 1, "overruns": 1, "partial_len": 0,
                 "occupied": 0, "armed": 1, "exhausted": 0},
    "exhaustive6": {"events": 4, "scans": 1, "retired": 1, "discarded": 0,
                    "order_errors": 0, "overruns": 0, "partial_len": 0,
                    "occupied": 0, "armed": 1, "exhausted": 0},
    "quality_lanes": {"events": 4096, "scans": 1024, "retired": 1024, "discarded": 0,
                      "order_errors": 0, "overruns": 0, "partial_len": 0,
                      "occupied": 0, "armed": 1, "exhausted": 0},
    "tag64_flush": {"events": 4, "scans": 1, "retired": 1, "discarded": 0,
                    "order_errors": 0, "overruns": 0, "partial_len": 0,
                    "occupied": 0, "armed": 1, "exhausted": 0},
    "abort_matrix": {"events": 4, "scans": 1, "retired": 1, "discarded": 0,
                     "order_errors": 0, "overruns": 0, "partial_len": 0,
                     "occupied": 0, "armed": 1, "exhausted": 0},
    "seq2_conditions": {"events": 4, "scans": 1, "retired": 1, "discarded": 0,
                        "order_errors": 0, "overruns": 0, "partial_len": 0,
                        "occupied": 0, "armed": 0, "exhausted": 1},
    "seq3_conditions": {"events": 4, "scans": 1, "retired": 1, "discarded": 0,
                        "order_errors": 0, "overruns": 0, "partial_len": 0,
                        "occupied": 0, "armed": 1, "exhausted": 0},
    "seq4_conditions": {"events": 4, "scans": 1, "retired": 1, "discarded": 0,
                        "order_errors": 0, "overruns": 0, "partial_len": 0,
                        "occupied": 0, "armed": 1, "exhausted": 0},
    "stat2_saturation": {"events": 3, "scans": 3, "retired": 1, "discarded": 3,
                         "order_errors": 0, "overruns": 3, "partial_len": 0,
                         "occupied": 0, "armed": 0, "exhausted": 1},
    "stat3_saturation": {"events": 7, "scans": 7, "retired": 1, "discarded": 7,
                         "order_errors": 0, "overruns": 7, "partial_len": 0,
                         "occupied": 0, "armed": 0, "exhausted": 1},
    "tick16_pack": {"events": 4, "scans": 1, "retired": 1, "discarded": 0,
                    "order_errors": 0, "overruns": 0, "partial_len": 0,
                    "occupied": 0, "armed": 1, "exhausted": 0},
    "tick1_pack": {"events": 4, "scans": 1, "retired": 1, "discarded": 0,
                   "order_errors": 0, "overruns": 0, "partial_len": 0,
                   "occupied": 0, "armed": 1, "exhausted": 0},
    "mutant_mix": {"events": 4, "scans": 0, "retired": 0, "discarded": 4,
                   "order_errors": 3, "overruns": 0, "partial_len": 0,
                   "occupied": 0, "armed": 1, "exhausted": 0},
    "mutant_loss": {"events": 2, "scans": 0, "retired": 0, "discarded": 2,
                    "order_errors": 1, "overruns": 0, "partial_len": 0,
                    "occupied": 0, "armed": 1, "exhausted": 0},
    "seq16_window": {"events": 65536, "scans": 16384, "retired": 16384,
                     "discarded": 0, "order_errors": 0, "overruns": 0,
                     "partial_len": 0, "occupied": 0, "armed": 0, "exhausted": 1},
    "random20k": {"events": 4, "scans": 1, "retired": 1, "discarded": 0,
                  "order_errors": 0, "overruns": 0, "partial_len": 0,
                  "occupied": 0, "armed": 1, "exhausted": 0},
}


def _lines(text):
    result=[]
    for raw in text.splitlines():
        s=raw.strip()
        result.append(s[2:] if s.startswith('# ') else s)
    return result


def _strict_diagnostics(stdout,stderr,own=None):
    reasons=[];summaries=[];fatals=[]
    for origin,text in [('stdout',stdout),('stderr',stderr)]:
        for s in _lines(text):
            summary=re.fullmatch(r'Errors: (0|[1-9][0-9]*), Warnings: (0|[1-9][0-9]*)',s,flags=re.ASCII)
            if summary:
                if origin!='stdout':reasons.append('diagnostic summary on stderr')
                summaries.append(tuple(map(int,summary.groups())));continue
            if own and s=='** Fatal: '+own:
                if origin!='stdout':reasons.append('own fatal on stderr')
                fatals.append(s);continue
            # Structured rows are validated separately; errors=0 is a stats key.
            if s.startswith('SAMPLE_SCAN_STATS '):continue
            if re.search(r'\b(?:error|errors|warning|warnings|fatal)\b',s,flags=re.I|re.ASCII):reasons.append('unexpected diagnostic: '+s)
    if summaries!=[(int(own is not None),0)]:reasons.append('nonunique/inconsistent error-warning summary')
    if own and len(fatals)!=1:reasons.append('own fatal not exact and unique')
    return reasons


def _structured_rows(stdout,stderr):
    rows={'SAMPLE_SCAN_PASS':[],'SAMPLE_SCAN_STATS':[],'SAMPLE_SCAN_MISMATCH':[],'GUARD_CONTROL_ALIVE':[]};bad=[]
    for origin,text in [('stdout',stdout),('stderr',stderr)]:
        for line in _lines(text):
            for key in rows:
                if key not in line:continue
                if origin!='stdout':bad.append('structured marker on stderr')
                exact=line==key if key in ['SAMPLE_SCAN_PASS','GUARD_CONTROL_ALIVE'] else line.startswith(key+' ')
                if not exact:bad.append('malformed structured marker: '+line)
                else:rows[key].append(line)
    return rows,bad



def _case(
    name: str,
    case_arg: str,
    params: dict[str, int] | None = None,
    *,
    suite: str = "core",
    identities: bool = True,
    timeout: int = 240,
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": "simulation",
        "case_arg": case_arg,
        "params": dict(params or {}),
        "suite": suite,
        "identities": identities,
        "timeout": timeout,
        "expected_stats": dict(EXPECTED_FINAL_STATS[name]),
    }


def _guard(name: str, select: int, expected_family: str) -> dict[str, Any]:
    return {
        "name": name,
        "kind": "guard",
        "case_arg": None,
        "params": {},
        "suite": "guards",
        "timeout": 120,
        "select": select,
        "expected_family": expected_family,
        "expected_message": FATAL_MESSAGES.get(expected_family),
    }


def _mutant(
    name: str,
    case_arg: str,
    old: str,
    new: str,
    required_mismatches: list[tuple[str, int, int]],
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": "mutant",
        "case_arg": case_arg,
        "params": {},
        "suite": "mutants",
        "timeout": 120,
        "mutation_old": old,
        "mutation_new": new,
        "required_mismatches": required_mismatches,
        "expected_case": case_arg,
    }


CASES: list[dict[str, Any]] = [
    _case("directed", "directed"),
    _case("exhaustive6", "exhaustive6", timeout=300),
    _case("quality_lanes", "quality_lanes", timeout=300),
    _case("tag64_flush", "tag64_flush", {"TAG_W": 64}),
    _case("abort_matrix", "abort_matrix", timeout=300),
    _case("seq2_conditions", "seq2_conditions", {"SEQ_W": 2}),
    _case("seq3_conditions", "seq3_conditions", {"SEQ_W": 3}),
    _case("seq4_conditions", "seq4_conditions", {"SEQ_W": 4}),
    _case("stat2_saturation", "stat2_saturation", {"SEQ_W": 4, "STAT_W": 2},
          identities=False),
    _case("stat3_saturation", "stat3_saturation", {"SEQ_W": 5, "STAT_W": 3},
          identities=False),
    _case("tick16_pack", "tick16_pack", {"TICK_W": 16}),
    _case("tick1_pack", "tick1_pack", {"TICK_W": 1}),
    _case("mutant_mix", "mutant_mix"),
    _case("mutant_loss", "mutant_loss"),
    _case("seq16_window", "seq16_window", {"SEQ_W": 16}, timeout=600),
    _case("random20k", "random20k", {"SEQ_W": 8}, timeout=300),
    _guard("guard_seq_w_1", 0, "SEQ_W"),
    _guard("guard_seq_w_33", 1, "SEQ_W"),
    _guard("guard_tick_w_0", 2, "TICK_W"),
    _guard("guard_tick_w_65", 3, "TICK_W"),
    _guard("guard_tag_w_0", 4, "TAG_W"),
    _guard("guard_tag_w_65", 5, "TAG_W"),
    _guard("guard_stat_w_1", 6, "STAT_W"),
    _guard("guard_stat_w_33", 7, "STAT_W"),
    _guard("guard_healthy", 8, "HEALTHY"),
    _mutant(
        "mutant_wrong_channel_mix_rejected",
        "mutant_mix",
        "else if (sample_channel == partial_len_q[1:0]) begin",
        "else if (1'b1) begin",
        [("mutant_mix_scans", 0, 1), ("mutant_mix_valid", 0, 1)],
    ),
    _mutant(
        "mutant_loss_undercount_rejected",
        "mutant_loss",
        "discard_order_c       = {1'b0, partial_len_q} + 4'd1;",
        "discard_order_c       = {1'b0, partial_len_q};",
        [("mutant_loss_discarded", 2, 1)],
    ),
]
CASE_BY_NAME = {entry["name"]: entry for entry in CASES}
SUITES = ("all", "core", "guards", "mutants")
def _result(ok: bool, reasons: list[str], **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": ok, "reasons": reasons}
    payload.update(extra)
    return payload


def _count_lines(pattern: re.Pattern[str], text: str) -> int:
    return sum(1 for _ in pattern.finditer(text))


def _summary_counts(stdout: str) -> tuple[int, int] | None:
    summaries = SUMMARY_RE.findall(stdout)
    if len(summaries) != 1:
        return None
    return int(summaries[0][0]), int(summaries[0][1])


def _zero_summary(stdout: str) -> list[str]:
    summaries = SUMMARY_RE.findall(stdout)
    if len(summaries) != 1:
        return [f"expected exactly one Errors/Warnings summary, found {len(summaries)}"]
    errors, warnings = (int(value) for value in summaries[0])
    reasons: list[str] = []
    if errors != 0:
        reasons.append(f"tool summary reports {errors} errors")
    if warnings != 0:
        reasons.append(f"tool summary reports {warnings} warnings")
    return reasons


def classify_compile(vlog_exit,stdout,stderr):
    reasons=_strict_diagnostics(stdout,stderr)
    if type(vlog_exit) is not int or vlog_exit!=0:reasons.append('compile exit must be0')
    return _result(not reasons,reasons)



def parse_stats(stdout: str) -> dict[str, Any]:
    """Parse exactly one anchored SAMPLE_SCAN_STATS key=value line."""
    stdout = stdout.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(STATS_RE.finditer(stdout))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one SAMPLE_SCAN_STATS line, found {len(matches)}")
    body = matches[0].group(1).strip()
    pairs = TOKEN_RE.findall(body)
    if not pairs:
        raise ValueError("SAMPLE_SCAN_STATS has no key=value fields")
    reconstructed = " ".join(f"{key}={value}" for key, value in pairs)
    if " ".join(body.split()) != reconstructed:
        raise ValueError("SAMPLE_SCAN_STATS contains malformed key=value text")
    values: dict[str, str] = {}
    for key, value in pairs:
        if key in values:
            raise ValueError(f"duplicate SAMPLE_SCAN_STATS key {key}")
        values[key] = value
    if set(values) != STATS_KEYS:
        missing = sorted(STATS_KEYS - set(values))
        extra = sorted(set(values) - STATS_KEYS)
        raise ValueError(f"SAMPLE_SCAN_STATS key mismatch missing={missing} extra={extra}")
    parsed: dict[str, Any] = {"case": values["case"]}
    for key in STATS_KEYS - {"case"}:
        if not re.fullmatch(r"[0-9]+", values[key]):
            raise ValueError(f"non-negative decimal required for {key}")
        parsed[key] = int(values[key])
    if not 0 <= parsed["partial_len"] <= 3:
        raise ValueError("partial_len outside 0..3")
    if parsed["occupied"] not in (0, 1):
        raise ValueError("occupied outside 0..1")
    if parsed["armed"] not in (0, 1):
        raise ValueError("armed outside 0..1")
    if parsed["exhausted"] not in (0, 1):
        raise ValueError("exhausted outside 0..1")
    return parsed


def _mismatch_tokens(stdout: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for match in MISMATCH_RE.finditer(stdout):
        row: dict[str, str] = {}
        for key, value in TOKEN_RE.findall(match.group(1)):
            if key not in row:
                row[key] = value
        rows.append(row)
    return rows


def _identity_reasons(stats: dict[str, int]) -> list[str]:
    reasons: list[str] = []
    occupied = stats["occupied"]
    events_rhs = 4 * (stats["retired"] + occupied) + stats["partial_len"] + stats["discarded"]
    scans_rhs = stats["retired"] + occupied + stats["overruns"]
    if stats["events"] != events_rhs:
        reasons.append(
            f"event conservation mismatch: events={stats['events']} rhs={events_rhs}"
        )
    if stats["scans"] != scans_rhs:
        reasons.append(
            f"scan conservation mismatch: scans={stats['scans']} rhs={scans_rhs}"
        )
    return reasons


def classify_simulation_output(vsim_exit,stdout,stderr,expected_case,expected_stats,*,check_identities=True):
    rows,reasons=_structured_rows(stdout,stderr);reasons+=_strict_diagnostics(stdout,stderr)
    if type(vsim_exit) is not int or vsim_exit!=0:reasons.append('simulation exit must be0')
    if len(rows['SAMPLE_SCAN_PASS'])!=1:reasons.append('pass marker not unique')
    if len(rows['SAMPLE_SCAN_STATS'])!=1:reasons.append('stats not unique')
    if rows['SAMPLE_SCAN_MISMATCH'] or rows['GUARD_CONTROL_ALIVE']:reasons.append('unexpected failure/guard marker')
    stats=None
    try:
        stats=parse_stats(stdout)
        if stats['case']!=expected_case:reasons.append('wrong case')
        if stats['errors']!=0 or stats['checks']<=0 or stats['windows']<=0:reasons.append('failed/empty testbench')
        for key,value in expected_stats.items():
            if stats.get(key)!=value:reasons.append('inconsistent stats '+key)
        if check_identities:reasons+=_identity_reasons(stats)
    except (ValueError,KeyError,TypeError) as exc:reasons.append('invalid stats: '+str(exc))
    return _result(not reasons,reasons,stats=stats)



def classify_guard_output(vlog_exit,vlog_stdout,vlog_stderr,vsim_exit,stdout,stderr,expected_family,expected_message):
    reasons=classify_compile(vlog_exit,vlog_stdout,vlog_stderr)['reasons'];rows,bad=_structured_rows(stdout,stderr);reasons+=bad
    if type(vsim_exit) is not int or vsim_exit!=0:reasons.append('guard process must exit0 on verified run-all/quit-f route')
    healthy=expected_family=='HEALTHY'
    if healthy:
        reasons+=_strict_diagnostics(stdout,stderr)
        if len(rows['GUARD_CONTROL_ALIVE'])!=1:reasons.append('healthy control marker not unique')
    else:
        if expected_message!=FATAL_MESSAGES.get(expected_family) or not expected_message:reasons.append('unknown fatal contract')
        reasons+=_strict_diagnostics(stdout,stderr,expected_message)
        if rows['GUARD_CONTROL_ALIVE']:reasons.append('guard body unexpectedly ran')
    if rows['SAMPLE_SCAN_PASS'] or rows['SAMPLE_SCAN_STATS'] or rows['SAMPLE_SCAN_MISMATCH']:reasons.append('unexpected normal/mismatch marker in guard')
    return _result(not reasons,reasons,classification='guard_healthy' if healthy else 'dut_guard_rejected')



def classify_mutant_output(vlog_exit,vlog_stdout,vlog_stderr,vsim_exit,stdout,stderr,expected_case,required_mismatches):
    reasons=classify_compile(vlog_exit,vlog_stdout,vlog_stderr)['reasons'];rows,bad=_structured_rows(stdout,stderr);reasons+=bad
    reasons+=_strict_diagnostics(stdout,stderr,'tb_sample_scan_capture: case failed')
    if type(vsim_exit) is not int or vsim_exit!=0:reasons.append('mutant process must complete verified route exit0')
    if rows['SAMPLE_SCAN_PASS'] or rows['GUARD_CONTROL_ALIVE']:reasons.append('unexpected positive marker')
    if len(rows['SAMPLE_SCAN_STATS'])!=1:reasons.append('mutant stats not unique')
    stats=None;observed=[]
    try:
        stats=parse_stats(stdout)
        if stats['case']!=expected_case or stats['errors']<=0 or stats['checks']<=0 or stats['windows']<=0:reasons.append('invalid mutant stats')
        if stats['errors']!=len(rows['SAMPLE_SCAN_MISMATCH']):reasons.append('mismatch count differs from errors')
    except (ValueError,KeyError,TypeError) as exc:reasons.append('invalid mutant stats: '+str(exc))
    for s in rows['SAMPLE_SCAN_MISMATCH']:
        m=re.fullmatch(r'SAMPLE_SCAN_MISMATCH field=([A-Za-z_][A-Za-z0-9_]*) expected=([0-9]+) actual=([0-9]+)',s,flags=re.ASCII)
        if not m:reasons.append('nonnumeric/malformed mutant mismatch');continue
        field,e,a=m.groups();e=int(e);a=int(a)
        if e==a:reasons.append('equal values do not prove mismatch')
        observed.append((field,e,a))
    if not required_mismatches or any(tuple(x) not in observed for x in required_mismatches):reasons.append('required concrete mismatch absent')
    return _result(not reasons,reasons,stats=stats,mismatches=observed,classification='mutant_rejected')



def aggregate_results(selected_names,results):
    reasons=[]
    if not selected_names or len(set(selected_names))!=len(selected_names):reasons.append('empty or duplicate selection')
    missing=[n for n in selected_names if n not in results];unexpected=[n for n in results if n not in selected_names]
    failed=[n for n in selected_names if n in results and results[n].get('ok') is not True]
    if missing or unexpected or failed:reasons.append('missing/extra/nonpassing selected results')
    return _result(not reasons,reasons,selected=selected_names,missing=missing,unexpected=unexpected,failed=failed)

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


def _run_hidden(argv: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
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
    except subprocess.TimeoutExpired as exc:
        stdout_bytes = exc.stdout or b""
        stderr_bytes = exc.stderr or b""
        exit_code = None
        timed_out = True
    elapsed = time.monotonic() - started
    return {
        "argv": argv,
        "cwd": str(cwd),
        "exit": exit_code,
        "timed_out": timed_out,
        "elapsed_seconds": round(elapsed, 6),
        "stdout_bytes": stdout_bytes,
        "stderr_bytes": stderr_bytes,
    }


def _persist_invocation(case_dir: Path, tag: str, invocation: dict[str, Any]) -> dict[str, Any]:
    stdout_bytes = invocation.pop("stdout_bytes")
    stderr_bytes = invocation.pop("stderr_bytes")
    stdout_path = case_dir / f"{tag}.stdout.bin"
    stderr_path = case_dir / f"{tag}.stderr.bin"
    stdout_path.write_bytes(stdout_bytes)
    stderr_path.write_bytes(stderr_bytes)
    invocation["stdout_path"] = stdout_path.name
    invocation["stderr_path"] = stderr_path.name
    invocation["stdout_sha256"] = hashlib.sha256(stdout_bytes).hexdigest()
    invocation["stderr_sha256"] = hashlib.sha256(stderr_bytes).hexdigest()
    _write_json(case_dir / f"{tag}.invocation.json", invocation)
    invocation["stdout_text"] = stdout_bytes.decode("utf-8", errors="replace")
    invocation["stderr_text"] = stderr_bytes.decode("utf-8", errors="replace")
    return invocation


def select_cases(suites: list[str], requested_names: list[str]) -> list[dict[str, Any]]:
    unknown = sorted(set(requested_names) - set(CASE_BY_NAME))
    if unknown:
        raise ValueError(f"unknown cases: {unknown}")
    unknown_suites = sorted(set(suites) - set(SUITES))
    if unknown_suites:
        raise ValueError(f"unknown suites: {unknown_suites}")
    if len(requested_names) != len(set(requested_names)):
        raise ValueError("duplicate --case selections are not allowed")

    selected_suites: set[str]
    if "all" in suites:
        selected_suites = {"core", "guards", "mutants"}
    else:
        selected_suites = set(suites)

    selected: list[dict[str, Any]] = []
    for entry in CASES:
        if requested_names:
            if entry["name"] not in requested_names:
                continue
            if entry["suite"] not in selected_suites:
                raise ValueError(
                    f"case {entry['name']} belongs to suite {entry['suite']}, not selected"
                )
            selected.append(entry)
        elif entry["suite"] in selected_suites:
            selected.append(entry)
    missing_in_suite = sorted(set(requested_names) - {entry["name"] for entry in selected})
    if missing_in_suite:
        raise ValueError(f"cases not selected: {missing_in_suite}")
    if not selected:
        raise ValueError("selection is empty")
    return selected


def _snapshot_inputs(root: Path, case_dir: Path, entry: dict[str, Any]) -> tuple[Path, Path, dict[str, Any]]:
    inputs = case_dir / "inputs"
    inputs.mkdir()
    rtl_target = inputs / RTL_RELATIVE.name
    tb_target = inputs / TB_RELATIVE.name
    source_report: dict[str, Any] = {}

    source_rtl = (root / RTL_RELATIVE).resolve()
    source_tb = (root / TB_RELATIVE).resolve()
    if not source_rtl.is_file() or not source_tb.is_file():
        raise FileNotFoundError("source RTL or testbench is missing under --root")

    source_report["source_rtl"] = {
        "path": str(source_rtl),
        "sha256": sha256_file(source_rtl),
    }
    source_report["source_tb"] = {
        "path": str(source_tb),
        "sha256": sha256_file(source_tb),
    }

    if entry["kind"] == "mutant":
        original = source_rtl.read_text(encoding="utf-8")
        old = entry["mutation_old"]
        new = entry["mutation_new"]
        count = original.count(old)
        if count != 1:
            raise ValueError(f"mutant anchor count expected=1 actual={count}")
        mutated = original.replace(old, new)
        rtl_target.write_text(mutated, encoding="utf-8", newline="\n")
        source_report["mutation"] = {
            "anchor_old": old,
            "anchor_new": new,
            "anchor_count": count,
        }
    else:
        shutil.copyfile(source_rtl, rtl_target)
    shutil.copyfile(source_tb, tb_target)

    source_report["rtl_input"] = {"path": str(rtl_target), "sha256": sha256_file(rtl_target)}
    source_report["tb_input"] = {"path": str(tb_target), "sha256": sha256_file(tb_target)}
    return rtl_target, tb_target, source_report


def _tool_version(modelsim_dir: Path, out: Path) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    versions: dict[str, Any] = {}
    version_dir = out / "tool-check"
    version_dir.mkdir()
    for tool in ("vlog", "vsim"):
        executable = modelsim_dir / f"{tool}.exe"
        argv = [str(executable), "-version"]
        started = time.monotonic()
        try:
            invocation = _run_hidden(argv, version_dir, 30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            invocation = {
                "argv": argv,
                "cwd": str(version_dir),
                "exit": None,
                "timed_out": isinstance(exc, subprocess.TimeoutExpired),
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "stdout_bytes": _version_output_bytes(getattr(exc, "stdout", b"")),
                "stderr_bytes": _version_output_bytes(getattr(exc, "stderr", b"")),
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
            }
        invocation = _persist_invocation(version_dir, tool, invocation)
        text = invocation["stdout_text"] + "\n" + invocation["stderr_text"]
        tool_reasons = _version_failure_reasons(tool, invocation)
        entry: dict[str, Any] = {
            "path": str(executable),
            "exit": invocation["exit"],
            "timed_out": invocation["timed_out"],
            "stdout_path": invocation["stdout_path"],
            "stderr_path": invocation["stderr_path"],
            "stdout_sha256": invocation["stdout_sha256"],
            "stderr_sha256": invocation["stderr_sha256"],
            "text": text.strip(),
            "ok": not tool_reasons,
            "reasons": tool_reasons,
        }
        if "exception_type" in invocation:
            entry["exception_type"] = invocation["exception_type"]
            entry["exception_message"] = invocation["exception_message"]
        versions[tool] = entry
        reasons.extend(tool_reasons)
    _write_json(out / "tool_versions.json", versions)
    return versions, reasons


def _version_output_bytes(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace")
    return bytes(value)


def _version_failure_reasons(tool: str, invocation: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    exception_type = invocation.get("exception_type")
    if exception_type:
        message = str(invocation.get("exception_message") or "")
        reasons.append(f"{tool} -version raised {exception_type}: {message}".rstrip())
    if invocation.get("timed_out"):
        reasons.append(f"{tool} -version timed out")
    exit_code = invocation.get("exit")
    if type(exit_code) is not int or exit_code != 0:
        reasons.append(f"{tool} -version exit was {exit_code!r}, expected 0")

    banners = {
        "vlog": re.compile(
            r"Model[ \t]+Technology[ \t]+ModelSim[ \t]+SE-64[ \t]+vlog[ \t]+10\.7[ \t]+"
            r"Compiler[ \t]+2017\.12[ \t]+Dec[ \t]+7[ \t]+2017"
        ),
        "vsim": re.compile(
            r"Model[ \t]+Technology[ \t]+ModelSim[ \t]+SE-64[ \t]+vsim[ \t]+10\.7[ \t]+"
            r"Simulator[ \t]+2017\.12[ \t]+Dec[ \t]+7[ \t]+2017"
        ),
    }
    banner_re = banners[tool]
    banner_count = 0
    summary_count = 0
    for stream_name in ("stdout", "stderr"):
        text = invocation[f"{stream_name}_text"]
        for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            candidate = line
            if candidate.startswith("# "):
                candidate = candidate[2:].strip()
            if banner_re.fullmatch(candidate):
                banner_count += 1
                continue
            if line == "Errors: 0, Warnings: 0":
                summary_count += 1
                continue
            if re.search(r"(?i)\b(?:error|fatal|warning)s?\b", line):
                reasons.append(
                    f"{tool} -version {stream_name} contains an explicit "
                    "Error/Fatal/Warning diagnostic"
                )
            else:
                reasons.append(f"{tool} -version {stream_name} contains unrecognized text")
    if banner_count != 1:
        reasons.append(
            f"{tool} -version printed {banner_count} verified "
            f"ModelSim 10.7 {tool} banners; exactly one is required"
        )
    if summary_count > 1:
        reasons.append(
            f"{tool} -version printed {summary_count} zero Errors/Warnings "
            "summaries; at most one is allowed"
        )
    return reasons


def run_case(
    root: Path,
    out: Path,
    modelsim_dir: Path,
    entry: dict[str, Any],
) -> dict[str, Any]:
    name = entry["name"]
    case_dir = out / "cases" / name
    case_dir.mkdir(parents=True)
    try:
        rtl_input, tb_input, source_report = _snapshot_inputs(root, case_dir, entry)
        vlog = modelsim_dir / "vlog.exe"
        vsim = modelsim_dir / "vsim.exe"
        vlog_argv = [
            str(vlog),
            "-sv",
            "-floatparameters",
            "-work",
            "work",
            str(rtl_input),
            str(tb_input),
        ]
        vlog_run = _persist_invocation(
            case_dir,
            "vlog",
            _run_hidden(vlog_argv, case_dir, 120),
        )

        result: dict[str, Any]
        sim_run: dict[str, Any] | None = None
        compile_class = classify_compile(
            -1 if vlog_run["exit"] is None else vlog_run["exit"],
            vlog_run["stdout_text"],
            vlog_run["stderr_text"],
        )
        if not compile_class["ok"]:
            result = _result(False, [f"compile: {reason}" for reason in compile_class["reasons"]],
                             classification="compile_failed")
        else:
            if entry["kind"] == "guard":
                vsim_argv = [
                    str(vsim),
                    "-c",
                    "-lib",
                    "work",
                    "-do",
                    "run -all; quit -f",
                    f"-gGUARD_SELECT={entry['select']}",
                    "tb_sample_scan_capture_guard",
                ]
            else:
                vsim_argv = [
                    str(vsim),
                    "-c",
                    "-lib",
                    "work",
                    "-do",
                    "run -all; quit -f",
                ]
                for param_name, param_value in entry["params"].items():
                    vsim_argv.append(f"-g{param_name}={param_value}")
                vsim_argv.extend([
                    "tb_sample_scan_capture",
                    f"+CASE={entry['case_arg']}",
                ])
            sim_run = _persist_invocation(
                case_dir,
                "vsim",
                _run_hidden(vsim_argv, case_dir, entry["timeout"]),
            )
            sim_exit = -1 if sim_run["exit"] is None else sim_run["exit"]
            if sim_run["timed_out"]:
                result = _result(False, ["simulation timed out"], classification="timeout")
            elif entry["kind"] == "simulation":
                result = classify_simulation_output(
                    sim_exit,
                    sim_run["stdout_text"],
                    sim_run["stderr_text"],
                    entry["case_arg"],
                    entry["expected_stats"],
                    check_identities=entry["identities"],
                )
                if result["ok"]:
                    result["classification"] = "pass"
            elif entry["kind"] == "guard":
                result = classify_guard_output(
                    vlog_run["exit"],
                    vlog_run["stdout_text"],
                    vlog_run["stderr_text"],
                    sim_exit,
                    sim_run["stdout_text"],
                    sim_run["stderr_text"],
                    entry["expected_family"],
                    entry["expected_message"],
                )
            else:
                result = classify_mutant_output(
                    vlog_run["exit"],
                    vlog_run["stdout_text"],
                    vlog_run["stderr_text"],
                    sim_exit,
                    sim_run["stdout_text"],
                    sim_run["stderr_text"],
                    entry["expected_case"],
                    entry["required_mismatches"],
                )

        case_report = {
            "schema": 1,
            "name": name,
            "kind": entry["kind"],
            "case_arg": entry["case_arg"],
            "params": entry["params"],
            "expected_stats": entry.get("expected_stats"),
            "source": source_report,
            "vlog": {key: vlog_run[key] for key in
                     ("argv", "cwd", "exit", "timed_out", "elapsed_seconds",
                      "stdout_path", "stderr_path", "stdout_sha256", "stderr_sha256")},
            "vsim": None,
            "result": result,
        }
        if sim_run is not None:
            case_report["vsim"] = {key: sim_run[key] for key in
                                   ("argv", "cwd", "exit", "timed_out", "elapsed_seconds",
                                    "stdout_path", "stderr_path", "stdout_sha256", "stderr_sha256")}
        _write_json(case_dir / "case.json", case_report)
        _write_json(case_dir / "result.json", result)
        return result
    except Exception as exc:  # preserve every failed case and its directory
        result = _result(False, [f"runner exception: {type(exc).__name__}: {exc}"],
                         classification="runner_exception")
        _write_json(case_dir / "result.json", result)
        return result


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--modelsim", type=Path)
    parser.add_argument("--suite", action="append", choices=SUITES)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--list-cases", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.list_cases:
        for entry in CASES:
            params = ",".join(f"{key}={value}" for key, value in entry["params"].items())
            print(f"{entry['name']} suite={entry['suite']} kind={entry['kind']} params={params}")
        return 0

    missing_args = [name for name, value in
                    (("--root", args.root), ("--out", args.out), ("--modelsim", args.modelsim))
                    if value is None]
    if missing_args:
        print(f"error: missing required arguments: {missing_args}", file=sys.stderr)
        return 2

    root = args.root.resolve()
    out = args.out.resolve()
    modelsim_dir = args.modelsim.resolve()
    if not (root / RTL_RELATIVE).is_file() or not (root / TB_RELATIVE).is_file():
        print("error: --root does not contain the scoped RTL and testbench", file=sys.stderr)
        return 2
    if not (modelsim_dir / "vlog.exe").is_file() or not (modelsim_dir / "vsim.exe").is_file():
        print("error: --modelsim does not contain vlog.exe and vsim.exe", file=sys.stderr)
        return 2
    if out.exists():
        print(f"error: --out must be a fresh absent directory: {out}", file=sys.stderr)
        return 2
    if not out.parent.is_dir():
        print(f"error: --out parent does not exist: {out.parent}", file=sys.stderr)
        return 2
    try:
        selected = select_cases(args.suite or ["all"], args.case)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out.mkdir()
    _write_json(
        out / "run_request.json",
        {
            "root": str(root),
            "out": str(out),
            "modelsim": str(modelsim_dir),
            "suites": args.suite or ["all"],
            "requested_cases": args.case,
            "selected": [entry["name"] for entry in selected],
            "create_no_window": bool(CREATE_NO_WINDOW),
            "tool_version": TOOL_VERSION,
        },
    )

    versions, version_reasons = _tool_version(modelsim_dir, out)
    if version_reasons:
        summary = {
            "ok": False,
            "reasons": version_reasons,
            "tool_versions": versions,
            "selected": [entry["name"] for entry in selected],
            "results": {},
        }
        _write_json(out / "summary.json", summary)
        print("SAMPLE_SCAN_RUN_FAIL")
        for reason in version_reasons:
            print(f"FAIL toolchain: {reason}")
        return 2

    results: dict[str, dict[str, Any]] = {}
    for entry in selected:
        result = run_case(root, out, modelsim_dir, entry)
        results[entry["name"]] = result
        state = "PASS" if result.get("ok") else "FAIL"
        print(f"CASE {entry['name']} {state} classification={result.get('classification')}")
        for reason in result.get("reasons", []):
            print(f"  {reason}")

    aggregate = aggregate_results([entry["name"] for entry in selected], results)
    summary = {
        "ok": aggregate["ok"],
        "reasons": aggregate["reasons"],
        "selected": aggregate["selected"],
        "failed": aggregate["failed"],
        "missing": aggregate["missing"],
        "unexpected": aggregate["unexpected"],
        "results": {
            name: {
                "ok": result.get("ok"),
                "classification": result.get("classification"),
                "reasons": result.get("reasons"),
                "stats": result.get("stats"),
                "mismatches": result.get("mismatches"),
            }
            for name, result in results.items()
        },
    }
    _write_json(out / "summary.json", summary)
    if aggregate["ok"]:
        print("SAMPLE_SCAN_RUN_PASS")
        return 0
    print("SAMPLE_SCAN_RUN_FAIL")
    for reason in aggregate["reasons"]:
        print(f"FAIL {reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
