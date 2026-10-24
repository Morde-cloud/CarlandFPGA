"""Bounded, hidden ModelSim author regression for private diagnostic slice 53.

All generated files stay in this slice's author evidence directory. No Vivado,
hardware, network, Git, controller, service, credentials or child dispatch calls.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid


CONTRACT_HASH = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
PINS = {
    "fpga/acquisition/deepeye_buffered_scan_capture.sv": "c8a540db8122b8f5520582a0f1fa9be0c43cb54a62f03c7c4edc893906f28411",
    "fpga/acquisition/deepeye_sample_scan_capture.sv": "fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d",
    "fpga/acquisition/deepeye_raw_scan_queue.sv": "630e14803d82b3379517d91626de4ad7e7d3c509ad14363b3164031a5f633ee4",
    "fpga/acquisition/deepeye_scan_lane_stream.sv": "b3c9d2024d9325191538cf08fec9a652ff8ff0ae316ec9af96078f85cf5be3cc",
}
RTL = "fpga/diagnostic/deepeye_private_axi_diag.sv"
TB = "tests/rtl/diagnostic/tb_private_axi_diag.sv"
DOC = "fpga/diagnostic/private_axi_diag.md"
RUNNER = "tools/diagnostic/run_private_axi_diag.py"
EVIDENCE = "evidence/diagnostic/private-axi-20261025-53/author"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def has_errors(raw: bytes) -> bool:
    text = raw.decode("utf-8", errors="replace")
    return bool(
        re.search(r"(?im)^\s*(?:#\s*)?\*\*\s*(?:error|fatal)\b", text)
        or re.search(r"(?m)^\s*(?:#\s*)?DIAG53_FAIL\b", text)
        or any(int(n) > 0 for n in re.findall(r"\bErrors\s*:\s*(\d+)", text, re.I))
    )


def adjudicate(raw: bytes, code: int | None, run_id: str, seed: int,
               sources_unchanged: bool) -> dict:
    lines = [re.sub(r"^\s*#\s?", "", line).strip() for line in raw.decode("utf-8", errors="replace").splitlines()]
    begin = f"DIAG53_BEGIN run={run_id} seed={seed}"
    passed = f"DIAG53_PASS run={run_id} seed={seed}"
    stats_pattern = re.compile(
        rf"DIAG53_STATS run={re.escape(run_id)} checks=(\d+) writes=(\d+) reads=(\d+) records=(\d+) cases=(\d+)"
    )
    stats_matches = [stats_pattern.fullmatch(line) for line in lines if line.startswith("DIAG53_STATS")]
    stats = None
    if len(stats_matches) == 1 and stats_matches[0]:
        stats = dict(zip(("checks", "writes", "reads", "records", "cases"), map(int, stats_matches[0].groups())))
    case_pattern = re.compile(rf"DIAG53_CASE run={re.escape(run_id)} index=(\d+) name=\S+")
    case_matches = [case_pattern.fullmatch(line) for line in lines if line.startswith("DIAG53_CASE")]
    case_indices = [int(m[1]) for m in case_matches if m]
    record_lines = [line for line in lines if line.startswith("DIAG53_RECORD")]
    channels = []
    for line in record_lines:
        m = re.fullmatch(
            rf"DIAG53_RECORD run={re.escape(run_id)} tag=[0-9a-fA-F]{{8}} generation=\d+ trigger=\d+ channel=([0-3]) data=[0-9a-fA-F]{{4}} tick=[0-9a-fA-F]{{16}} quality=[0-9a-fA-F]{{2}} first=\d+ last=\d+", line)
        if m:
            channels.append(int(m[1]))
    criteria = {
        "exit_zero": code == 0,
        "no_simulator_errors_or_fatals": not has_errors(raw),
        "unique_exact_begin": [x for x in lines if x.startswith("DIAG53_BEGIN")] == [begin],
        "unique_exact_pass": [x for x in lines if x.startswith("DIAG53_PASS")] == [passed],
        "unique_exact_stats": stats is not None,
        "all_14_unique_cases": len(case_matches) == 14 and case_indices == list(range(1, 15)),
        "all_16_ordered_records": len(record_lines) == 16 and channels == [0, 1, 2, 3] * 4,
        "stats_consistent": bool(stats and stats["checks"] >= 100 and stats["writes"] >= 100
                                 and stats["reads"] >= 250 and stats["records"] == len(record_lines)
                                 and stats["cases"] == len(case_matches)),
        "sources_unchanged": sources_unchanged,
        "marker_order": bool(begin in lines and passed in lines and lines.index(begin) < lines.index(passed)
                             and stats is not None and lines.index(next(x for x in lines if x.startswith("DIAG53_STATS"))) < lines.index(passed)),
    }
    return {"passed": all(criteria.values()), "criteria": criteria, "stats": stats}


def negative_control_verdict(raw: bytes, code: int | None, run_id: str, seed: int,
                             sources_unchanged: bool) -> dict:
    outcome = adjudicate(raw, code, run_id, seed, sources_unchanged)
    lines = [re.sub(r"^\s*#\s?", "", line).strip() for line in raw.decode("utf-8", errors="replace").splitlines()]
    marker = f"DIAG53_EXPECTED_FAILURE run={run_id} purpose=runner_must_reject_real_simulator_fatal"
    # ModelSim 10.7 with onfinish exit actually returns 0 even for $fatal.
    # That is precisely why the error/fatal/summary checks must be mandatory.
    return {"expected_failure": True, "actual_exit_code": code, "adjudication": outcome,
        "passed_negative_control": bool(not outcome["passed"] and code is not None
            and has_errors(raw) and lines.count(marker) == 1 and sources_unchanged
            and outcome["criteria"]["unique_exact_begin"]
            and not any(line.startswith("DIAG53_PASS") for line in lines))}


def parser_controls(directory: Path) -> dict:
    directory.mkdir()
    rid, seed = "synthetic-parser-control", 53025
    text = f"DIAG53_BEGIN run={rid} seed={seed}\n"
    text += "".join(f"DIAG53_CASE run={rid} index={i} name=control{i}\n" for i in range(1, 15))
    text += "".join(f"DIAG53_RECORD run={rid} tag=00000001 generation=1 trigger=1 channel={i%4} data=1234 tick=0123456789abcdef quality=ff first=0 last=3\n" for i in range(16))
    text += f"DIAG53_STATS run={rid} checks=1000 writes=150 reads=300 records=16 cases=14\nDIAG53_PASS run={rid} seed={seed}\n"
    baseline = text.encode()
    assert adjudicate(baseline, 0, rid, seed, True)["passed"], "parser baseline refused"
    variants = {
        "nonzero_exit": (baseline, 7, True),
        "errors_summary_after_pass": (baseline + b"# Errors: 1, Warnings: 0\n", 0, True),
        "runtime_error_after_pass": (baseline + b"# ** Error: deliberate false-positive control\n", 0, True),
        "runtime_fatal_after_pass": (baseline + b"# ** Fatal: deliberate false-positive control\n", 0, True),
        "duplicate_pass": (baseline + f"DIAG53_PASS run={rid} seed={seed}\n".encode(), 0, True),
        "wrong_seed": (baseline.replace(f"seed={seed}".encode(), b"seed=1"), 0, True),
        "missing_stats": (re.sub(rb"DIAG53_STATS[^\n]*\n", b"", baseline), 0, True),
        "missing_case": (re.sub(rb"DIAG53_CASE[^\n]*index=14[^\n]*\n", b"", baseline), 0, True),
        "changed_source": (baseline, 0, False),
    }
    results = {}
    for name, (raw, code, unchanged) in variants.items():
        (directory / f"{name}.txt").write_bytes(raw)
        outcome = adjudicate(raw, code, rid, seed, unchanged)
        results[name] = {"expected_rejection": True, "actual": outcome}
        assert not outcome["passed"], name
    save_json(directory / "results.json", results)
    return {"status": "passed", "negative_controls_rejected": len(results)}


def execute(directory: Path, label: str, argv: list[str], timeout: int = 90) -> dict:
    started = utc()
    entry = {"label": label, "argv": argv, "cwd": str(directory), "started_utc": started,
             "pid": None, "exit_code": None, "timed_out": False}
    save_json(directory / f"{label}.command.json", entry)
    tick = time.monotonic()
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(argv, cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=flags, shell=False)
    entry["pid"] = process.pid
    save_json(directory / f"{label}.command.json", entry)
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        entry["timed_out"] = True
        # Only the process tree started by this runner is eligible for cleanup.
        if os.name == "nt":
            killed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                    capture_output=True, creationflags=flags, timeout=15)
            (directory / f"{label}.timeout-cleanup.stdout.txt").write_bytes(killed.stdout)
            (directory / f"{label}.timeout-cleanup.stderr.txt").write_bytes(killed.stderr)
        else:
            process.kill()
        out, err = process.communicate(timeout=15)
    (directory / f"{label}.stdout.txt").write_bytes(out)
    (directory / f"{label}.stderr.txt").write_bytes(err)
    entry.update(exit_code=process.returncode, finished_utc=utc(), seconds=time.monotonic()-tick,
                 stdout_sha256=sha(out), stderr_sha256=sha(err))
    save_json(directory / f"{label}.command.json", entry)
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelsim-home", type=Path, default=Path("D:/modelsim1/win64"))
    parser.add_argument("--seed", type=int, default=53025)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    author = root / EVIDENCE
    author.mkdir(parents=True, exist_ok=True)
    if not 0 < args.seed < 2**31:
        parser.error("seed must be a nonzero signed-32-bit positive integer")
    directory = None
    for index in range(1, 4):
        candidate = author / f"attempt{index:02d}"
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        directory = candidate
        break
    if directory is None:
        raise SystemExit("Initial attempt plus two bounded author corrections exhausted; retain evidence and report to main")
    run_id = f"53a{index:02d}-{uuid.uuid4().hex[:10]}"
    summary = {
        "task_id": "DEEPEYE-IMPLEMENTATION-20261014", "task_version": 1,
        "work_id": "B-MINIMAL-PL-AXI-20261025-53-v1", "run_id": run_id,
        "attempt": index, "seed": args.seed, "runner_pid": os.getpid(), "started_utc": utc(),
        "status": "running", "requirements_sha256": CONTRACT_HASH,
        "contract_id": "DEEPEYE-HUMAN-LOCK-20261014/revision1", "requirement_ids": [f"H{i:02d}" for i in range(1, 16)],
        "commands": [], "source_snapshot": [], "stages": {"simulation": "running", "synthesis": "not_run",
            "implementation": "not_run", "bitstream": "not_run", "board": "not_run",
            "all_29_formal": "not_run", "R03": "not_run", "full_product": "not_run"},
        "acceptance": "quality main only; author regression is scoped evidence",
    }
    save_json(directory / "summary.json", summary)
    try:
        contract_dir = root.parents[1] / "docs/competition/deepeye-2026"
        contract = json.loads((contract_dir / "immutable_scope.json").read_text(encoding="utf-8-sig"))
        actual = sha(json.dumps(contract["requirements"], ensure_ascii=False, sort_keys=True,
                                separators=(",", ":")).encode("utf-8"))
        if actual != CONTRACT_HASH or [r["id"] for r in contract["requirements"]] != summary["requirement_ids"]:
            raise RuntimeError("fixed human contract mismatch")
        for rel, expected in PINS.items():
            if sha((root / rel).read_bytes()) != expected:
                raise RuntimeError(f"main-pinned read-only dependency changed: {rel}")
        snapshot_items = [(root / rel, rel) for rel in [*PINS, RTL, TB, DOC, RUNNER]]
        snapshot_items += [(contract_dir / name, "contract/" + name) for name in ("immutable_scope.md", "immutable_scope.json")]
        for source, relative in snapshot_items:
            data = source.read_bytes()
            target = directory / "sources" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            summary["source_snapshot"].append({"path": relative, "source_path": str(source),
                "sha256": sha(data), "bytes": len(data), "snapshot": str(target.relative_to(directory))})
        summary["source_set_sha256"] = sha(json.dumps(
            [(x["path"], x["sha256"]) for x in summary["source_snapshot"]], separators=(",", ":")).encode())
        save_json(directory / "summary.json", summary)
        summary["parser_controls"] = parser_controls(directory / "adjudicator-controls")
        home = args.modelsim_home.resolve()
        executables = {name: home / (name + ".exe") for name in ("vsim", "vlog", "vlib", "vmap")}
        for tool in executables.values():
            if not tool.is_file():
                raise RuntimeError(f"ModelSim executable missing: {tool}")

        def command(label: str, argv: list[str], timeout: int = 90) -> dict:
            entry = execute(directory, label, argv, timeout)
            summary["commands"].append(entry)
            save_json(directory / "summary.json", summary)
            return entry

        version = command("version", [str(executables["vsim"]), "-version"], 30)
        version_bytes = (directory / "version.stdout.txt").read_bytes() + (directory / "version.stderr.txt").read_bytes()
        if version["exit_code"] != 0 or not re.search(rb"\b10\.7\b", version_bytes):
            raise RuntimeError("requested actual ModelSim 10.7 not confirmed by version command")
        for label, argv in (
            ("vmap-copy", [str(executables["vmap"]), "-c"]),
            ("vlib", [str(executables["vlib"]), "work"]),
            ("vmap-work", [str(executables["vmap"]), "work", "work"]),
        ):
            entry = command(label, argv, 30)
            if entry["exit_code"] != 0 or has_errors((directory / f"{label}.stdout.txt").read_bytes() + (directory / f"{label}.stderr.txt").read_bytes()):
                raise RuntimeError(f"{label} failed; no replay")
        # Compile preserved raw-byte snapshots, not moving live sources.
        sources = [str(directory / "sources" / rel) for rel in [*PINS, RTL, TB]]
        compiled = command("vlog", [str(executables["vlog"]), "-sv", "-work", "work", *sources])
        compile_bytes = (directory / "vlog.stdout.txt").read_bytes() + (directory / "vlog.stderr.txt").read_bytes()
        if compiled["exit_code"] != 0 or has_errors(compile_bytes) or not re.search(rb"Errors:\s*0\b", compile_bytes):
            raise RuntimeError("compile failed or missing zero-error compiler summary; retain attempt")
        script = directory / "simulate.do"
        script.write_text("onerror {quit -code 17}\nonbreak {quit -code 18}\nonfinish exit\nrun -all\nquit -code 0\n", encoding="ascii")
        positive = command("positive", [str(executables["vsim"]), "-c", "-l", "positive.transcript.txt",
            "-do", str(script), "work.tb_private_axi_diag", f"+RUN_ID={run_id}", f"+SEED={args.seed}"])
        raw = (directory / "positive.stdout.txt").read_bytes() + (directory / "positive.stderr.txt").read_bytes()
        unchanged = all(sha(Path(x["source_path"]).read_bytes()) == x["sha256"] for x in summary["source_snapshot"])
        summary["positive"] = adjudicate(raw, positive["exit_code"], run_id, args.seed, unchanged)
        negative_id = run_id + "-negative"
        neg = command("negative", [str(executables["vsim"]), "-c", "-l", "negative.transcript.txt",
            "-do", str(script), "work.tb_private_axi_diag", f"+RUN_ID={negative_id}", f"+SEED={args.seed}", "+NEGATIVE=1"])
        neg_raw = (directory / "negative.stdout.txt").read_bytes() + (directory / "negative.stderr.txt").read_bytes()
        summary["negative"] = negative_control_verdict(neg_raw, neg["exit_code"], negative_id, args.seed, unchanged)
        unchanged = all(sha(Path(x["source_path"]).read_bytes()) == x["sha256"] for x in summary["source_snapshot"])
        summary["sources_unchanged_after_all_commands"] = unchanged
        passed = summary["positive"]["passed"] and summary["negative"]["passed_negative_control"] and unchanged
        summary["status"] = "passed" if passed else "failed"
        summary["stages"]["simulation"] = summary["status"]
    except Exception as exc:
        summary["status"] = "failed"
        summary["stages"]["simulation"] = "failed"
        summary["error"] = f"{type(exc).__name__}: {exc}"
    summary["finished_utc"] = utc()
    save_json(directory / "summary.json", summary)
    print(json.dumps({"status": summary["status"], "attempt": index,
                      "summary": str(directory / "summary.json"), "error": summary.get("error")}, ensure_ascii=False))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
