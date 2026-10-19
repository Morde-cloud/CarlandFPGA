#!/usr/bin/env python3
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKTREE = Path(r"D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014")
AUTHOR = WORKTREE / "competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author"
RUN = AUTHOR / "run-author-20261020-15-c"
CLOSEOUT = AUTHOR / "final-closeout-20261020-15-a"
ATTEMPTS = RUN / "manifest-attempts-20261020-15-a"
BASELINE = "7dd2c4108ee49cc6e0feb7c715d786f8b11a99c2"
EXPECTED_REQ_SHA = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
ATOMIC_SHA = "9dc8ecf96e59a2ae8467bda64572f62eb602d52db535733f236f64ff97c43428"
CAPTURE_SHA = "4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456"
PROTECTED_SHA = "6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8"
SCOPE_MD_SHA = "a099b1756d2207c7c7cb11f5babb0b5e2e5433765d0c19a6dcc1538618578135"
SCOPE_JSON_SHA = "66b7d77986be0492e68e326971fb7b5210562cf38cc0fe51f4ab593023fbdebe"
CONTRACT_PIN = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
EXPECTED_TOTALS = {"assertions":100587,"cases":1431,"failure_events":953,"groups":19,
    "handshakes":459,"mismatches":0,"passed_scenarios":19,"raw_faults":6,"records":476,
    "samples":208667,"scenarios":19,"window_starts":507}
EXPECTED_SCENARIOS = {"invalid_parameter_scenarios":9,"mutant_runs":5,"positive_scenarios":19,"total":33}
EXPECTED_GROUPS = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,20,21,22]
INVALID_EXPECTED = {
    "invalid-count-zero": (0,64,32,2,64,32),
    "invalid-count-negative": (-1,64,32,2,64,32),
    "invalid-count-high": (33,64,32,32,64,32),
    "invalid-witness-zero": (32,0,32,32,2,32),
    "invalid-witness-negative": (32,-2,32,32,2,32),
    "invalid-witness-high": (32,65,32,32,64,32),
    "invalid-tag-zero": (32,64,0,32,64,1),
    "invalid-tag-negative": (32,64,-1,32,64,1),
    "invalid-tag-high": (32,64,65,32,64,64),
}
checks = []
failures = []


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check(name, condition, detail):
    passed = bool(condition)
    checks.append({"name": name, "passed": passed, "detail": detail})
    if not passed:
        failures.append({"check": name, "detail": detail})
    return passed


def parse_tb_stats(text):
    pattern = re.compile(
        r"TB_STATS\s+groups=(\d+)\s+cases=(\d+)\s+samples=(\d+)\s+assertions=(\d+)\s+"
        r"records=(\d+)\s+raw_faults=(\d+)\s+failure_events=(\d+)\s+"
        r"window_starts=(\d+)\s+handshakes=(\d+)\s+mismatches=(\d+)")
    rows = pattern.findall(text)
    if len(rows) != 1:
        return None
    keys = ["groups","cases","samples","assertions","records","raw_faults",
            "failure_events","window_starts","handshakes","mismatches"]
    return {key: int(value) for key, value in zip(keys, rows[0])}


def tree_records(root, excluded):
    records = []
    total_bytes = 0
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        size = path.stat().st_size
        total_bytes += size
        records.append({"path": relative, "bytes": size, "sha256": sha_file(path)})
    return records, total_bytes


def tree_sha256(records):
    digest = hashlib.sha256()
    for record in records:
        digest.update(record["path"].encode("utf-8"))
        digest.update(b"\x00")
        digest.update(record["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def rel_worktree(path):
    return Path(path).resolve().relative_to(WORKTREE).as_posix()


def main():
    if not CLOSEOUT.is_dir():
        raise SystemExit(f"missing closeout directory: {CLOSEOUT}")
    if (CLOSEOUT / "FINAL_CLOSURE.json").exists():
        raise SystemExit("FINAL_CLOSURE.json already exists; refusing a second closeout")
    if ATTEMPTS.exists():
        raise SystemExit(f"manifest attempt directory already exists: {ATTEMPTS}")
    ATTEMPTS.mkdir()
    manifest_sources = [
        ("EVIDENCE_TREE_MANIFEST.json", "EVIDENCE_TREE_MANIFEST.initial.json"),
        ("TERMINAL_MANIFEST.json", "TERMINAL_MANIFEST.initial.json"),
        ("TERMINAL_MANIFEST.sha256.txt", "TERMINAL_MANIFEST.sha256.initial.txt")]
    initial_manifests = {}
    for source_name, dest_name in manifest_sources:
        source = RUN / source_name
        dest = ATTEMPTS / dest_name
        if not source.is_file() or dest.exists():
            raise SystemExit(f"bad initial manifest preservation input: {source} -> {dest}")
        shutil.copy2(source, dest)
        initial_manifests[source_name] = {"initial_path":rel_worktree(dest),
            "bytes":dest.stat().st_size,"sha256":sha_file(dest)}
    write_json(CLOSEOUT / "initial-manifest-preservation.json", {
        "purpose":"Preserve runner manifests before final closeout recomputation.",
        "initial_manifests":initial_manifests,
        "reason":"External stdout was still flushing when the runner computed its tree manifest; the command stdout is 922 bytes now but was 0 at the runner tree scan.",
        "recorded_utc":utc_now()})
    for required in (RUN, RUN/"RUN_SUMMARY.json", RUN/"logs", RUN/"source_snapshot", RUN/"mutants"):
        check(f"required_path:{required.name}", required.exists(), str(required))
    if failures:
        write_json(CLOSEOUT/"evidence-verification.json", {"result":"FAIL","checks":checks,"failures":failures})
        return 2
    summary = json.loads((RUN / "RUN_SUMMARY.json").read_text(encoding="utf-8"))
    terminal_initial = json.loads((ATTEMPTS / "TERMINAL_MANIFEST.initial.json").read_text(encoding="utf-8"))
    console = (RUN / "RUNNER_CONSOLE.txt").read_text(encoding="utf-8")
    check("runner_result_pass", summary.get("result") == "PASS", summary.get("result"))
    check("terminal_initial_result_pass", terminal_initial.get("result") == "PASS", terminal_initial.get("result"))
    check("positive_totals_exact", summary.get("positive_totals") == EXPECTED_TOTALS,
          {"actual": summary.get("positive_totals"), "expected": EXPECTED_TOTALS})
    check("scenario_counts_exact", summary.get("scenario_counts") == EXPECTED_SCENARIOS,
          {"actual": summary.get("scenario_counts"), "expected": EXPECTED_SCENARIOS})
    check("summary_no_failures", summary.get("failures") == [], summary.get("failures"))
    check("summary_no_warnings", summary.get("warnings") == [], summary.get("warnings"))
    check("runner_command_count", summary.get("command_count") == len(summary.get("commands", [])),
          {"command_count": summary.get("command_count"), "commands_len": len(summary.get("commands", []))})
    expected_console = ("result=PASS\n"
        "positive_scenarios=19 passed=19\n"
        "samples=208667 assertions=100587 records=476\n"
        "mutant_runs=5 invalid_parameter_runs=9\n"
        "failures=0 warnings=0\n")
    check("runner_console_exact", console == expected_console, console)

    source_paths = {
        "rtl": WORKTREE/"competition/deepeye/fpga/control3d/deepeye_pwm_applied_capture.sv",
        "candidate": WORKTREE/"competition/deepeye/fpga/control3d/pwm_applied_capture_candidate.md",
        "tb": WORKTREE/"competition/deepeye/tests/rtl/control3d/tb_pwm_applied_capture.sv",
        "runner": WORKTREE/"competition/deepeye/tools/control3d/run_pwm_applied_capture.py",
        "atomic": WORKTREE/"competition/deepeye/fpga/control3d/deepeye_atomic_pwm.sv",
        "capture": WORKTREE/"competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv"}
    source_hashes = {key: sha_file(path) for key, path in source_paths.items()}
    snapshot_dir = RUN/"source_snapshot"
    snapshot_names = {"rtl":"rtl.sv","candidate":"candidate.md","tb":"tb.sv",
        "runner":"run_pwm_applied_capture.py","atomic":"atomic.sv","capture":"capture.sv"}
    snapshot_matches = {}
    for key, name in snapshot_names.items():
        source = source_paths[key]
        snapshot = snapshot_dir/name
        same = source.is_file() and snapshot.is_file() and source.read_bytes() == snapshot.read_bytes()
        snapshot_matches[key] = same
        check(f"source_snapshot_byte_match:{key}", same,
              {"source":rel_worktree(source),"snapshot":rel_worktree(snapshot)})
    check("atomic_hash_fixed", source_hashes["atomic"] == ATOMIC_SHA,
          {"actual":source_hashes["atomic"],"expected":ATOMIC_SHA})
    check("capture_hash_fixed", source_hashes["capture"] == CAPTURE_SHA,
          {"actual":source_hashes["capture"],"expected":CAPTURE_SHA})
    for label in ("input_hashes_before","input_hashes_after"):
        record = summary.get(label, {})
        for key, expected in (("atomic",ATOMIC_SHA),("capture",CAPTURE_SHA)):
            entry = record.get(key, {})
            path = Path(entry.get("path",""))
            actual_file = sha_file(path) if path.is_file() else None
            check(f"{label}:{key}", entry.get("expected") == expected and entry.get("actual") == expected and actual_file == expected,
                  {"entry":entry,"current_file_sha256":actual_file})
    for label in ("protected_dirty_before","protected_dirty_after"):
        entry = summary.get(label, {})
        path = Path(entry.get("path",""))
        actual_file = sha_file(path) if path.is_file() else None
        check(f"{label}:protected", entry.get("expected") == PROTECTED_SHA and entry.get("actual") == PROTECTED_SHA and actual_file == PROTECTED_SHA,
              {"entry":entry,"current_file_sha256":actual_file})
    check("summary_input_hashes_equal", summary.get("input_hashes_before") == summary.get("input_hashes_after"),
          {"before":summary.get("input_hashes_before"),"after":summary.get("input_hashes_after")})
    check("summary_protected_hashes_equal", summary.get("protected_dirty_before") == summary.get("protected_dirty_after"),
          {"before":summary.get("protected_dirty_before"),"after":summary.get("protected_dirty_after")})

    contract_path = WORKTREE/"docs/competition/deepeye-2026/immutable_scope.json"
    contract_doc = json.loads(contract_path.read_text(encoding="utf-8"))
    requirements = contract_doc["requirements"]
    canonical = json.dumps(requirements, ensure_ascii=False, sort_keys=True, separators=(",",":")).encode("utf-8")
    worktree_req_sha = hashlib.sha256(canonical).hexdigest()
    pinned = subprocess.run(["git","-C",str(WORKTREE),"show",
        f"{CONTRACT_PIN}:docs/competition/deepeye-2026/immutable_scope.json"],
        capture_output=True, check=True).stdout
    pinned_doc = json.loads(pinned.decode("utf-8"))
    pinned_req_sha = hashlib.sha256(json.dumps(pinned_doc["requirements"], ensure_ascii=False,
        sort_keys=True, separators=(",",":")).encode("utf-8")).hexdigest()
    requirement_ids = [item.get("id") for item in requirements if isinstance(item, dict)]
    check("contract_requirements_worktree_hash", worktree_req_sha == EXPECTED_REQ_SHA,
          {"actual":worktree_req_sha,"expected":EXPECTED_REQ_SHA})
    check("contract_requirements_pinned_hash", pinned_req_sha == EXPECTED_REQ_SHA,
          {"actual":pinned_req_sha,"expected":EXPECTED_REQ_SHA})
    check("contract_requirement_ids", requirement_ids == [f"H{i:02d}" for i in range(1,16)], requirement_ids)
    check("pinned_blob_equals_worktree", pinned == contract_path.read_bytes(),
          {"pinned_bytes":len(pinned),"worktree_bytes":contract_path.stat().st_size})
    scope_md = Path(r"D:\pynq\CarlandFPGA\.local\deployment\node-b\evidence\independent-applied-capture-20261020-15\SCOPE.md")
    scope_json = Path(r"D:\pynq\CarlandFPGA\.local\deployment\node-b\evidence\independent-applied-capture-20261020-15\SCOPE_FROZEN.json")
    scope_hashes = {"SCOPE.md":sha_file(scope_md),"SCOPE_FROZEN.json":sha_file(scope_json)}
    check("scope_md_hash", scope_hashes["SCOPE.md"] == SCOPE_MD_SHA, scope_hashes)
    check("scope_frozen_json_hash", scope_hashes["SCOPE_FROZEN.json"] == SCOPE_JSON_SHA, scope_hashes)
    contract_verify = {"contract_id":"DEEPEYE-HUMAN-LOCK-20261014","contract_revision":1,
        "pin":CONTRACT_PIN,"expected_requirements_sha256":EXPECTED_REQ_SHA,
        "worktree_requirements_sha256":worktree_req_sha,"pinned_requirements_sha256":pinned_req_sha,
        "match":worktree_req_sha == pinned_req_sha == EXPECTED_REQ_SHA,
        "requirement_ids":requirement_ids,"pinned_blob_equals_worktree":pinned == contract_path.read_bytes(),
        "scope_hashes":scope_hashes,
        "method":"json.dumps(requirements, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode('utf-8')",
        "checked_utc":utc_now()}
    write_json(CLOSEOUT/"contract-hash-verify.json", contract_verify)

    head = subprocess.run(["git","-C",str(WORKTREE),"rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip()
    branch = subprocess.run(["git","-C",str(WORKTREE),"branch","--show-current"],capture_output=True,text=True,check=True).stdout.strip()
    status_result = subprocess.run(["git","-C",str(WORKTREE),"status","--porcelain=v1"],
        capture_output=True,text=True,encoding="utf-8",errors="replace")
    status_lines = status_result.stdout.splitlines()
    check("baseline_head", head == BASELINE, {"actual":head,"expected":BASELINE})
    check("task_branch", branch == "codex/b/deepeye-implementation-20261014", branch)
    check("git_status_readable", status_result.returncode == 0,
          {"exit":status_result.returncode,"stderr":status_result.stderr})
    check("root_lib_absent", not (WORKTREE/"lib").exists(), str(WORKTREE/"lib"))
    check("root_transcript_absent", not (WORKTREE/"transcript").exists(), str(WORKTREE/"transcript"))
    unexpected_status = [line for line in status_lines
        if (line[3:] if len(line) > 3 else line).startswith("lib/") or
           (line[3:] if len(line) > 3 else line).startswith("transcript")]
    check("no_unexpected_root_status", unexpected_status == [], unexpected_status)
    command_by_name = {item.get("name"): item for item in summary.get("commands", [])}
    positive_logs = sorted((RUN/"logs").glob("g*.stdout.txt"))
    check("positive_log_count", len(positive_logs) == 19, len(positive_logs))
    positive_aggregate = {"groups":0,"cases":0,"samples":0,"assertions":0,"records":0,
        "raw_faults":0,"failure_events":0,"window_starts":0,"handshakes":0,"mismatches":0,
        "scenarios":0,"passed_scenarios":0}
    positive_groups = []
    loopback_groups = []
    positive_log_results = []
    for log in positive_logs:
        text = log.read_text(encoding="utf-8")
        stats = parse_tb_stats(text)
        passes = re.findall(r"^# TB_PASS group=(\d+) loopback=(\d+)$", text, re.MULTILINE)
        fail_count = len(re.findall(r"^# TB_FAIL", text, re.MULTILINE))
        mismatch_count = len(re.findall(r"^# MISMATCH sample=", text, re.MULTILINE))
        code7_count = len(re.findall(r"CODE7_OBSERVED", text))
        group = int(passes[0][0]) if passes else None
        loopback = int(passes[0][1]) if passes else None
        positive_groups.append(group)
        if loopback == 1:
            loopback_groups.append(group)
        if stats:
            for key in ("groups","cases","samples","assertions","records","raw_faults",
                        "failure_events","window_starts","handshakes","mismatches"):
                positive_aggregate[key] += stats[key]
        check(f"positive_log_pass:{log.stem}", len(passes) == 1, passes)
        check(f"positive_log_no_fail:{log.stem}", fail_count == 0, fail_count)
        check(f"positive_log_no_mismatch:{log.stem}", mismatch_count == 0, mismatch_count)
        check(f"positive_log_no_code7:{log.stem}", code7_count == 0, code7_count)
        check(f"positive_log_stats:{log.stem}", stats is not None, stats)
        positive_log_results.append({"log":log.name,"group":group,"loopback":loopback,
            "stats":stats,"tb_pass":len(passes) == 1,"tb_fail_count":fail_count,
            "mismatch_count":mismatch_count,"code7_observed":code7_count > 0})
    check("positive_group_set", sorted(positive_groups) == EXPECTED_GROUPS,
          {"actual":sorted(positive_groups),"expected":EXPECTED_GROUPS})
    check("loopback_groups_explicit", loopback_groups == [8,9], loopback_groups)
    positive_aggregate["groups"] = len(positive_logs)
    positive_aggregate["scenarios"] = len(positive_logs)
    positive_aggregate["passed_scenarios"] = len(positive_logs)
    check("positive_aggregate_matches_expected", positive_aggregate == EXPECTED_TOTALS,
          {"actual":positive_aggregate,"expected":EXPECTED_TOTALS})
    check("positive_summary_length", len(summary.get("positive", [])) == 19, len(summary.get("positive", [])))
    for item in summary.get("positive", []):
        check(f"positive_summary_pass:{item.get('id')}", item.get("passed") is True and item.get("exit") == 0,
              {"id":item.get("id"),"passed":item.get("passed"),"exit":item.get("exit")})
        check(f"positive_summary_mismatch:{item.get('id')}", item.get("stats", {}).get("mismatches") == 0,
              item.get("stats"))
        check(f"positive_summary_code7:{item.get('id')}", item.get("code7_observed") is False,
              item.get("code7_observed"))
    expected_exhaustive = {"eligible_sampled_records":450,
        "groups":["exhaustive_count_w2_all_legal_tuples","exhaustive_count_w3_all_legal_tuples"],
        "legal_command_triples":1394}
    check("exhaustive_small_domain", summary.get("exhaustive_small_domain") == expected_exhaustive,
          summary.get("exhaustive_small_domain"))

    invalid_results = []
    invalid_seen = set()
    for entry in summary.get("invalid_parameters", []):
        run_id = entry.get("id")
        invalid_seen.add(run_id)
        expected = INVALID_EXPECTED.get(run_id)
        diagnostic = entry.get("diagnostic") or {}
        actual_tuple = (diagnostic.get("count_w"),diagnostic.get("witness_w"),diagnostic.get("tag_w"),
                        diagnostic.get("safe_count_w"),diagnostic.get("safe_witness_w"),
                        diagnostic.get("safe_tag_w"))
        log = RUN/"logs"/f"{run_id}.stdout.txt"
        text = log.read_text(encoding="utf-8") if log.is_file() else ""
        matches = re.findall(
            r"^# DEEPEYE_APPLIED_CAPTURE_INVALID_PARAM COUNT_W=(-?\d+) WITNESS_W=(-?\d+) TAG_W=(-?\d+) "
            r"SAFE_COUNT_W=(\d+) SAFE_WITNESS_W=(\d+) SAFE_TAG_W=(\d+)$", text, re.MULTILINE)
        fatal = text.count("# ** Fatal: DEEPEYE_APPLIED_CAPTURE_INVALID_PARAM unsupported widths")
        command = command_by_name.get(run_id, {})
        check(f"invalid_expectation_known:{run_id}", expected is not None, expected)
        check(f"invalid_summary_pass:{run_id}", entry.get("passed") is True and entry.get("diagnostic_exact") is True,
              {"passed":entry.get("passed"),"diagnostic_exact":entry.get("diagnostic_exact")})
        check(f"invalid_diagnostic_values:{run_id}", expected is not None and actual_tuple == expected,
              {"actual":actual_tuple,"expected":expected})
        check(f"invalid_diagnostic_line_count:{run_id}", len(matches) == 1,
              {"line_count":len(matches),"lines":matches})
        check(f"invalid_fatal_count:{run_id}", fatal == 1, fatal)
        check(f"invalid_command_exit:{run_id}", command.get("exit") == 0,
              {"exit":command.get("exit"),"name":command.get("name")})
        invalid_results.append({"id":run_id,"expected":expected,"diagnostic":actual_tuple,
            "line_count":len(matches),"fatal_count":fatal,"modelsim_exit":command.get("exit")})
    check("invalid_id_set", invalid_seen == set(INVALID_EXPECTED), sorted(invalid_seen))
    check("invalid_count", len(invalid_results) == 9, len(invalid_results))

    mutant_results = []
    mutant_ids = {item.get("id") for item in summary.get("mutants", [])}
    expected_mutants = {"m1-t-invalidation-delayed","m2-same-tag-state-retained",
                        "m3-mismatch-admitted","m4-no-capture-rearm"}
    check("mutant_id_set", mutant_ids == expected_mutants, sorted(mutant_ids))
    for mutant in summary.get("mutants", []):
        mid = mutant.get("id")
        compile_info = mutant.get("compile", {})
        check(f"mutant_compile:{mid}", compile_info.get("compiled") is True, compile_info)
        for run in mutant.get("runs", []):
            log = Path(run.get("stdout",""))
            text = log.read_text(encoding="utf-8") if log.is_file() else ""
            tb_fail = len(re.findall(r"^# TB_FAIL", text, re.MULTILINE))
            tb_pass = len(re.findall(r"^# TB_PASS", text, re.MULTILINE))
            code7 = len(re.findall(r"CODE7_OBSERVED", text))
            mutant_results.append({"id":mid,"group":run.get("group"),"passed":run.get("passed"),
                "rejected":run.get("rejected"),"mismatches":run.get("stats", {}).get("mismatches"),
                "code7_observed":run.get("code7_observed"),"tb_fail_lines":tb_fail,
                "tb_pass_lines":tb_pass,"code7_marker":code7 > 0,"log":log.name})
    for mid in ("m1-t-invalidation-delayed","m2-same-tag-state-retained","m3-mismatch-admitted"):
        runs = next(item.get("runs", []) for item in summary.get("mutants", []) if item.get("id") == mid)
        check(f"mutant_rejected_public_ports:{mid}",
              any(run.get("rejected") is True and run.get("passed") is False and
                  run.get("stats", {}).get("mismatches", 0) > 0 for run in runs),
              [{"group":r.get("group"),"rejected":r.get("rejected"),
                "mismatches":r.get("stats", {}).get("mismatches")} for r in runs])
    m4_runs = next(item.get("runs", []) for item in summary.get("mutants", []) if item.get("id") == "m4-no-capture-rearm")
    check("mutant_m4_code7_only_on_faulty_copy",
          any(r.get("group") == 30 and r.get("code7_observed") is True and r.get("passed") is True for r in m4_runs) and
          any(r.get("group") == 13 and r.get("rejected") is True and
              r.get("stats", {}).get("mismatches", 0) > 0 for r in m4_runs),
          [{"group":r.get("group"),"passed":r.get("passed"),"rejected":r.get("rejected"),
            "mismatches":r.get("stats", {}).get("mismatches"),"code7":r.get("code7_observed")} for r in m4_runs])
    tool_versions = summary.get("tool_versions", {})
    check("modelsim_tool_versions",
          "ModelSim SE-64 vlog 10.7" in tool_versions.get("vlog","") and
          "ModelSim SE-64 vsim 10.7" in tool_versions.get("vsim",""), tool_versions)
    command_manifest = []
    for command in summary.get("commands", []):
        stdout = Path(command.get("stdout",""))
        stderr = Path(command.get("stderr",""))
        command_manifest.append({"name":command.get("name"),"argv":command.get("argv"),
            "cwd":command.get("cwd"),"started_utc":command.get("started_utc"),
            "ended_utc":command.get("ended_utc"),"exit":command.get("exit"),
            "stdout":rel_worktree(stdout) if stdout.is_file() else str(stdout),
            "stdout_bytes":stdout.stat().st_size if stdout.is_file() else None,
            "stdout_sha256":sha_file(stdout) if stdout.is_file() else None,
            "stderr":rel_worktree(stderr) if stderr.is_file() else str(stderr),
            "stderr_bytes":stderr.stat().st_size if stderr.is_file() else None,
            "stderr_sha256":sha_file(stderr) if stderr.is_file() else None})
    write_json(CLOSEOUT/"command-log-manifest.json", {"command_count":len(command_manifest),
        "commands":command_manifest,
        "runner_console":{"path":rel_worktree(RUN/"RUNNER_CONSOLE.txt"),
                          "sha256":sha_file(RUN/"RUNNER_CONSOLE.txt")},
        "recorded_utc":utc_now()})
    invocation_stdout = AUTHOR/"run-author-20261020-15-c.command.stdout.txt"
    invocation_stderr = AUTHOR/"run-author-20261020-15-c.command.stderr.txt"
    write_json(CLOSEOUT/"runner-invocation.json", {
        "argv":[r"D:\pynq\CarlandFPGA\.local\venv\Scripts\python.exe","-B","-X","utf8",
                "competition/deepeye/tools/control3d/run_pwm_applied_capture.py",
                "--modelsim-root","D:/modelsim1/win64","--out",
                "competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author/run-author-20261020-15-c"],
        "cwd":str(WORKTREE),"actual_exit":0,
        "stdout":rel_worktree(invocation_stdout),"stdout_bytes":invocation_stdout.stat().st_size,
        "stdout_sha256":sha_file(invocation_stdout),
        "stderr":rel_worktree(invocation_stderr),"stderr_bytes":invocation_stderr.stat().st_size,
        "stderr_sha256":sha_file(invocation_stderr),
        "note":"The runner historical stdout records its original terminal-manifest hash; final closeout recomputes the tree after stdout flushing. Historical bytes are preserved unchanged."})

    check("all_checks_before_closeout", failures == [], failures)
    verification = {"task_id":"DEEPEYE-IMPLEMENTATION-20261014","task_version":1,
        "work_id":"B-PWM-APPLIED-CAPTURE-RTL-20261020-15-v1",
        "operation_id":"B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15",
        "result":"PASS" if not failures else "FAIL","checks_total":len(checks),
        "checks_passed":sum(1 for item in checks if item["passed"]),
        "checks_failed":sum(1 for item in checks if not item["passed"]),
        "checks":checks,"failures":failures,"positive_totals":positive_aggregate,
        "positive_log_results":positive_log_results,"invalid_results":invalid_results,
        "mutant_results":mutant_results,"source_hashes":source_hashes,
        "source_snapshot_matches":snapshot_matches,"contract":contract_verify,
        "head":head,"branch":branch,"git_status":status_lines,
        "unexpected_root_status":unexpected_status,"tool_versions":tool_versions,
        "python":summary.get("python"),"generated_utc":utc_now()}
    write_json(CLOSEOUT/"evidence-verification.json", verification)
    if failures:
        (CLOSEOUT/"closeout.stdout.txt").write_text(
            f"CLOSEOUT_FAILED failures={len(failures)}\n{json.dumps(failures, indent=2)}\n", encoding="utf-8")
        return 2

    failure_notes = """Preserved command/preparation failures and corrections
=======================================================
1. A preflight used a relative virtual-environment path and failed before any run or
   product output. It is preserved in preflight-author-20261020-15-c/FAILED_PREFLIGHT_NOTE.txt;
   the corrected absolute-path preflight reports Python 3.12.9.
2. A read-only verification search expected *.log files, but the suite stores *.txt logs.
   It failed without changing evidence; closeout rechecks all *.stdout.txt logs.
3. Two early apply-patch wrapper attempts failed (stdin instead of required UTF-8 argument;
   one combined command rejected by command policy). No source bytes changed. The successful
   patch and actual result are preserved under apply-patch-20261020-15-v/.
4. Isolated g15-b validation lacked a pre-run source snapshot. Exact unchanged sources and
   timestamp/log proof are preserved under source-snapshot-debug-g15-b-posthoc-20261020-15-a/.
5. A later compile left a 142-byte ModelSim lib/_info cache and failed-compile transcript at
   the worktree root. They were moved with hashes to stray-root-artifacts-20261020-15-a/;
   root copies are absent.
6. The runner generated its initial tree manifest while externally redirected stdout was
   still flushing. The initial manifests are preserved under
   run-author-20261020-15-c/manifest-attempts-20261020-15-a/ and the final tree is closed once.
"""
    (CLOSEOUT/"TOOL_FAILURES_AND_CORRECTIONS.txt").write_text(failure_notes, encoding="utf-8")
    report = f"""# B op15 applied-capture author terminal report

- Task: DEEPEYE-IMPLEMENTATION-20261014/v1
- Work: B-PWM-APPLIED-CAPTURE-RTL-20261020-15-v1
- Operation: B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15
- Result: PASS (author-side local ModelSim simulation only)
- Parent product main: 01a13b55-095b-7461-8dd5-5476a130bd82
- Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1, H01-H15; requirements SHA256 {EXPECTED_REQ_SHA}
- Frozen design: 1011259415a0916054eb580687612580bc1e5f09
- Worktree: {WORKTREE}
- Branch: codex/b/deepeye-implementation-20261014
- HEAD: {head}
- Positive scenarios: 19 passed, 208667 samples, 100587 assertions, 476 records, zero mismatches
- Exhaustive small domain: 1394 legal triples, 450 eligible sampled records
- Negative behavior: 5 mutant runs, 9 exact invalid-parameter diagnostics
- ModelSim: {tool_versions.get('vlog')} / {tool_versions.get('vsim')}
- Runner actual exit: 0

## Owned files

- competition/deepeye/fpga/control3d/deepeye_pwm_applied_capture.sv: {source_hashes['rtl']}
- competition/deepeye/fpga/control3d/pwm_applied_capture_candidate.md: {source_hashes['candidate']}
- competition/deepeye/tests/rtl/control3d/tb_pwm_applied_capture.sv: {source_hashes['tb']}
- competition/deepeye/tools/control3d/run_pwm_applied_capture.py: {source_hashes['runner']}
- competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author/: final tree hash in TERMINAL_MANIFEST.json

## Limitations

No Vivado synthesis, implementation, place-and-route, static timing, CDC/RDC, board or system
run was performed. All29 formal cards and G05 applied-command/full-cycle/system binding remain
not_run/unaccepted. Actual digital loopback is supplemental and explicitly named. Code7 is
demonstrated only on a deliberately faulty wrapper copy; it is not claimed reachable in the
correct normal composition. This report does not self-accept or claim publication.
"""
    (CLOSEOUT/"FINAL_REPORT.md").write_text(report, encoding="utf-8")
    write_json(CLOSEOUT/"FINAL_REPORT.json", {"result":"PASS",
        "task_id":"DEEPEYE-IMPLEMENTATION-20261014","task_version":1,
        "work_id":"B-PWM-APPLIED-CAPTURE-RTL-20261020-15-v1",
        "operation_id":"B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15",
        "requirement_ids":[f"H{i:02d}" for i in range(1,16)],
        "requirements_sha256":EXPECTED_REQ_SHA,
        "design_pin":"1011259415a0916054eb580687612580bc1e5f09","head":head,
        "positive_totals":positive_aggregate,"source_hashes":source_hashes,
        "self_acceptance":False,"publication_claimed":False,"generated_utc":utc_now()})
    excluded = {
        "run-author-20261020-15-c/EVIDENCE_TREE_MANIFEST.json",
        "run-author-20261020-15-c/TERMINAL_MANIFEST.json",
        "run-author-20261020-15-c/TERMINAL_MANIFEST.sha256.txt",
        "final-closeout-20261020-15-a/FINAL_CLOSURE.json",
        "final-closeout-20261020-15-a/closeout.stdout.txt",
        "final-closeout-20261020-15-a/closeout.stderr.txt"}
    records, total_bytes = tree_records(AUTHOR, excluded)
    final_tree_sha = tree_sha256(records)
    tree_manifest_path = RUN/"EVIDENCE_TREE_MANIFEST.json"
    write_json(tree_manifest_path, {"root":str(AUTHOR),"revision":"final-closeout-20261020-15-a",
        "purpose":"Final evidence tree after all runner and closeout logs were complete.",
        "excluded_from_tree":sorted(excluded),"file_count":len(records),"bytes":total_bytes,
        "tree_sha256":final_tree_sha,"files":records,"generated_utc":utc_now()})
    tree_manifest_sha = sha_file(tree_manifest_path)
    records_after, total_bytes_after = tree_records(AUTHOR, excluded)
    check("final_tree_manifest_readback_count", len(records_after) == len(records),
          {"before":len(records),"after":len(records_after)})
    check("final_tree_hash_recomputes", tree_sha256(records_after) == final_tree_sha,
          {"recorded":final_tree_sha,"recomputed":tree_sha256(records_after)})
    check("final_tree_bytes_recompute", total_bytes_after == total_bytes,
          {"before":total_bytes,"after":total_bytes_after})

    terminal = dict(terminal_initial)
    terminal["generated_utc"] = utc_now()
    terminal["five_paths"] = {
        "rtl":{"absolute_path":str(source_paths["rtl"]),"bytes":source_paths["rtl"].stat().st_size,
               "path":rel_worktree(source_paths["rtl"]),"sha256":source_hashes["rtl"]},
        "candidate":{"absolute_path":str(source_paths["candidate"]),
               "bytes":source_paths["candidate"].stat().st_size,
               "path":rel_worktree(source_paths["candidate"]),"sha256":source_hashes["candidate"]},
        "tb":{"absolute_path":str(source_paths["tb"]),"bytes":source_paths["tb"].stat().st_size,
              "path":rel_worktree(source_paths["tb"]),"sha256":source_hashes["tb"]},
        "runner":{"absolute_path":str(source_paths["runner"]),
              "bytes":source_paths["runner"].stat().st_size,
              "path":rel_worktree(source_paths["runner"]),"sha256":source_hashes["runner"]},
        "evidence_author_dir":{"absolute_path":str(AUTHOR),"path":rel_worktree(AUTHOR),
              "file_count":len(records),"bytes":total_bytes,"tree_sha256":final_tree_sha,
              "tree_manifest":rel_worktree(tree_manifest_path),
              "tree_manifest_sha256":tree_manifest_sha,
              "excluded_from_tree":sorted(excluded)}}
    terminal["run_summary"] = {"absolute_path":str(RUN/"RUN_SUMMARY.json"),
        "path":rel_worktree(RUN/"RUN_SUMMARY.json"),"sha256":sha_file(RUN/"RUN_SUMMARY.json")}
    terminal["warnings"] = ["The runner initial evidence-tree manifest was captured before externally redirected runner stdout finished flushing. Initial manifests are preserved and the final tree was recomputed after all logs were complete."]
    terminal["corrections"] = [
        "Preserved and reconciled the g15-b missing pre-run source snapshot with a post-hoc timestamp-proven source copy.",
        "Moved accidental worktree-root ModelSim lib/_info and transcript artifacts under author evidence.",
        "Preserved the initial raced manifest trio and recomputed the final evidence tree once."]
    terminal["manifest_closeout"] = {"revision":"final-closeout-20261020-15-a",
        "initial_manifests":initial_manifests,
        "reason":"Closed after external stdout and all closeout logs became final.",
        "final_tree_manifest_sha256":tree_manifest_sha}
    terminal["verification"] = {
        "path":rel_worktree(CLOSEOUT/"evidence-verification.json"),
        "sha256":sha_file(CLOSEOUT/"evidence-verification.json"),
        "checks_total":len(checks),"checks_failed":sum(1 for item in checks if not item["passed"]),
        "command_log_manifest":rel_worktree(CLOSEOUT/"command-log-manifest.json"),
        "command_log_manifest_sha256":sha_file(CLOSEOUT/"command-log-manifest.json"),
        "final_report":rel_worktree(CLOSEOUT/"FINAL_REPORT.md"),
        "final_report_sha256":sha_file(CLOSEOUT/"FINAL_REPORT.md"),
        "runner_invocation":rel_worktree(CLOSEOUT/"runner-invocation.json"),
        "runner_invocation_sha256":sha_file(CLOSEOUT/"runner-invocation.json")}
    terminal["result"] = "PASS" if failures == [] else terminal.get("result")
    terminal_path = RUN/"TERMINAL_MANIFEST.json"
    write_json(terminal_path, terminal)
    terminal_sha = sha_file(terminal_path)
    (RUN/"TERMINAL_MANIFEST.sha256.txt").write_text(f"{terminal_sha}  TERMINAL_MANIFEST.json\n",
        encoding="utf-8")
    records_final, total_bytes_final = tree_records(AUTHOR, excluded)
    check("final_tree_unchanged_after_excluded_metadata", tree_sha256(records_final) == final_tree_sha,
          {"recorded":final_tree_sha,"recomputed":tree_sha256(records_final)})
    check("terminal_sha_file",
          (RUN/"TERMINAL_MANIFEST.sha256.txt").read_text(encoding="utf-8") == f"{terminal_sha}  TERMINAL_MANIFEST.json\n",
          terminal_sha)
    if failures:
        (CLOSEOUT/"closeout.stdout.txt").write_text(
            "CLOSEOUT_FAILED after finalization\n" + json.dumps(failures, indent=2) + "\n",
            encoding="utf-8")
        return 2
    stdout_text = ("result=PASS\n"
        "positive_scenarios=19 passed=19\n"
        "samples=208667 assertions=100587 records=476\n"
        "mutant_runs=5 invalid_parameter_runs=9\n"
        f"verification_checks={len(checks)} failed=0\n"
        f"evidence_tree_files={len(records)}\n"
        f"evidence_tree_sha256={final_tree_sha}\n"
        f"tree_manifest_sha256={tree_manifest_sha}\n"
        f"terminal_manifest_sha256={terminal_sha}\n"
        "self_acceptance=false publication_claimed=false\n")
    (CLOSEOUT/"closeout.stdout.txt").write_text(stdout_text, encoding="utf-8")
    (CLOSEOUT/"closeout.stderr.txt").write_text("", encoding="utf-8")
    closure = {"result":"PASS","task_id":"DEEPEYE-IMPLEMENTATION-20261014","task_version":1,
        "work_id":"B-PWM-APPLIED-CAPTURE-RTL-20261020-15-v1",
        "operation_id":"B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15",
        "parent_main":"01a13b55-095b-7461-8dd5-5476a130bd82",
        "requirements_sha256":EXPECTED_REQ_SHA,
        "design_pin":"1011259415a0916054eb580687612580bc1e5f09",
        "head":head,"branch":branch,"five_paths":terminal["five_paths"],
        "positive_totals":positive_aggregate,"actual_exits":{"runner":0},
        "verification_sha256":sha_file(CLOSEOUT/"evidence-verification.json"),
        "command_log_manifest_sha256":sha_file(CLOSEOUT/"command-log-manifest.json"),
        "final_report_sha256":sha_file(CLOSEOUT/"FINAL_REPORT.md"),
        "evidence_tree_sha256":final_tree_sha,"tree_manifest_sha256":tree_manifest_sha,
        "terminal_manifest_sha256":terminal_sha,
        "closeout_stdout_sha256":sha_file(CLOSEOUT/"closeout.stdout.txt"),
        "not_run":terminal.get("not_run"),"limitations":terminal.get("limitations"),
        "warnings":terminal.get("warnings"),"corrections":terminal.get("corrections"),
        "self_acceptance":False,"publication_claimed":False,"generated_utc":utc_now()}
    write_json(CLOSEOUT/"FINAL_CLOSURE.json", closure)
    print(stdout_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())