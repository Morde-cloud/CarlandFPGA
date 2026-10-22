from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(r"D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
RESULT = ROOT / "competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/author/final-all-01/results"
RTL = ROOT / "competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv"
TB = ROOT / "competition/deepeye/tests/rtl/acquisition/tb_sample_scan_capture.sv"
SUMMARY_RE = re.compile(r"^(?:# )?Errors: ([0-9]+), Warnings: ([0-9]+)\s*$", re.MULTILINE)
PASS_RE = re.compile(r"^(?:# )?SAMPLE_SCAN_PASS[ \t]*$", re.MULTILINE)
ALIVE_RE = re.compile(r"^(?:# )?GUARD_CONTROL_ALIVE[ \t]*$", re.MULTILINE)
MISMATCH_RE = re.compile(r"^(?:# )?SAMPLE_SCAN_MISMATCH[ \t]+", re.MULTILINE)
STATS_RE = re.compile(r"^(?:# )?SAMPLE_SCAN_STATS[ \t]+", re.MULTILINE)
FATAL_RE = re.compile(
    r"^(?:# )?\*\* Fatal: deepeye_sample_scan_capture: "
    r"(?:SEQ_W|TICK_W|TAG_W|STAT_W) out of range[ \t]*$",
    re.MULTILINE,
)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_text(path):
    return path.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")

current_rtl = sha(RTL)
current_tb = sha(TB)
summary = json.loads((RESULT / "summary.json").read_text(encoding="utf-8"))
assert summary["ok"] is True, summary
assert len(summary["selected"]) == 27, summary
assert summary["failed"] == [] and summary["missing"] == [] and summary["unexpected"] == []
expected_class = {"simulation": "pass", "guard": None, "mutant": "mutant_rejected"}
counts = {"simulation": 0, "guard": 0, "mutant": 0}
for name in summary["selected"]:
    case_dir = RESULT / "cases" / name
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    result = json.loads((case_dir / "result.json").read_text(encoding="utf-8"))
    kind = case["kind"]
    counts[kind] += 1
    assert result["ok"] is True, (name, result)
    assert case["source"]["source_rtl"]["sha256"] == current_rtl, name
    assert case["source"]["source_tb"]["sha256"] == current_tb, name
    assert case["vlog"]["exit"] == 0 and case["vlog"]["timed_out"] is False, name
    vlog_text = read_text(case_dir / case["vlog"]["stdout_path"]) + "\n" + read_text(case_dir / case["vlog"]["stderr_path"])
    vlog_sum = SUMMARY_RE.findall(vlog_text)
    assert vlog_sum == [("0", "0")], (name, vlog_sum)
    assert "** Warning" not in vlog_text and "** Error" not in vlog_text, name
    if kind == "simulation":
        assert result["classification"] == "pass", name
        assert case["vsim"]["exit"] == 0 and case["vsim"]["timed_out"] is False, name
        text = read_text(case_dir / case["vsim"]["stdout_path"]) + "\n" + read_text(case_dir / case["vsim"]["stderr_path"])
        assert SUMMARY_RE.findall(text) == [("0", "0")], (name, SUMMARY_RE.findall(text))
        assert len(PASS_RE.findall(text)) == 1 and len(STATS_RE.findall(text)) == 1, name
        assert not MISMATCH_RE.search(text) and "** Warning" not in text and "** Error" not in text, name
        assert result["stats"]["errors"] == 0 and result["stats"]["case"] == case["case_arg"], name
    elif kind == "guard":
        assert case["vsim"]["timed_out"] is False, name
        text = read_text(case_dir / case["vsim"]["stdout_path"]) + "\n" + read_text(case_dir / case["vsim"]["stderr_path"])
        if case.get("expected_stats") is None and name == "guard_healthy":
            assert result["classification"] == "guard_healthy", name
            assert SUMMARY_RE.findall(text) == [("0", "0")], (name, SUMMARY_RE.findall(text))
            assert len(ALIVE_RE.findall(text)) == 1 and not PASS_RE.search(text), name
        else:
            assert result["classification"] == "dut_guard_rejected", name
            sums = SUMMARY_RE.findall(text)
            assert len(sums) == 1 and int(sums[0][0]) >= 1 and sums[0][1] == "0", (name, sums)
            assert len(FATAL_RE.findall(text)) == 1 and not ALIVE_RE.search(text), name
            assert "** Warning" not in text, name
    else:
        assert result["classification"] == "mutant_rejected", name
        assert case["vsim"]["timed_out"] is False, name
        text = read_text(case_dir / case["vsim"]["stdout_path"]) + "\n" + read_text(case_dir / case["vsim"]["stderr_path"])
        sums = SUMMARY_RE.findall(text)
        assert len(sums) == 1 and int(sums[0][0]) >= 1 and sums[0][1] == "0", (name, sums)
        assert "** Fatal: tb_sample_scan_capture: case failed" in text and not PASS_RE.search(text), name
        assert result["mismatches"] and "** Warning" not in text, name

versions = json.loads((RESULT / "tool_versions.json").read_text(encoding="utf-8"))
assert "10.7" in versions["vlog"]["text"] and "10.7" in versions["vsim"]["text"]
request = json.loads((RESULT / "run_request.json").read_text(encoding="utf-8"))
assert request["create_no_window"] is True
assert request["selected"] == summary["selected"]
print(
    "FINAL_AUTHOR_AUDIT_PASS cases=27 "
    f"core={counts['simulation']} guards={counts['guard']} mutants={counts['mutant']} "
    f"rtl_sha256={current_rtl} tb_sha256={current_tb}"
)