import hashlib
import json
import pathlib
from datetime import datetime, timezone

root = pathlib.Path(r"D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014")
author = root / "competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20/author"
final = author / "run-final-01"
run = json.loads((final / "RUN_RESULT.json").read_text(encoding="utf-8"))

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def rec(path):
    return {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}

delivered = {
    "rtl": rec(root / "competition/deepeye/fpga/stream/deepeye_encoded_frame_queue.sv"),
    "candidate_doc": rec(root / "competition/deepeye/fpga/stream/encoded_frame_queue_candidate.md"),
    "testbench": rec(root / "competition/deepeye/tests/rtl/stream/tb_encoded_frame_queue.sv"),
    "runner": rec(root / "competition/deepeye/tools/stream/run_encoded_frame_queue.py"),
}
inputs_dir = pathlib.Path(r"D:\pynq\CarlandFPGA\.local\deployment\node-b\evidence\encoded-frame-queue-20261022-20\inputs")
inputs = {}
for name in ["IMPLEMENTATION_SCOPE.md", "SCOPE_FROZEN.json", "ASSIGNMENT.json", "COMPLETION_MATRIX.md", "CONTINUE_DECISION.json", "INPUTS_CONSUMED.json", "immutable_scope.json"]:
    inputs[name] = sha(inputs_dir / name)

suites = {}
for name in ["standalone", "small", "compose", "guard-0", "guard-1", "guard-33"]:
    s = run["suites"][name]
    item = {
        "status": s["status"],
        "vlib_exit": s["vlib"]["returncode"],
        "vlog_exit": s["vlog"]["returncode"],
        "vsim_exit": s["vsim"]["returncode"],
        "vlog_timeout": s["vlog"]["timed_out"],
        "vsim_timeout": s["vsim"]["timed_out"],
        "compile_pass": s.get("compile_pass"),
        "runner_checks": len(s["checks"]),
        "runner_checks_failed": sum(1 for c in s["checks"] if not c["pass"]),
    }
    if s["kind"] == "ordinary":
        item["summary"] = s["run"]["summary"]
        item["stats"] = s["run"]["stats"]
        item["case_checks"] = s["run"]["case_checks"]
    else:
        item["fatal"] = s["run"]["fatal"]
        item["tally"] = s["run"]["tally"]
    suites[name] = item

preserved = [
    {"attempt": "smoke/main-001", "status": "fail-compile", "note": "testbench compile corrections; 5 compile errors"},
    {"attempt": "smoke/main-002", "status": "fail", "note": "6 cases, 4 pass, 2 fail, 3 TB check failures"},
    {"attempt": "smoke/main-003", "status": "pass-intermediate", "note": "6 cases, 6 pass, 0 fail, 6885 checks"},
    {"attempt": "smoke/main-004", "status": "fail", "note": "13 cases, 9 pass, 4 fail, 32 TB check failures"},
    {"attempt": "smoke/main-005", "status": "pass-intermediate", "note": "13 cases, 13 pass, 0 fail, 9962 checks"},
    {"attempt": "smoke/main-006", "status": "pass-intermediate", "note": "23 cases, 23 pass, 0 fail, 10949 checks"},
    {"attempt": "smoke/small-001", "status": "fail", "note": "STAT_W=2 sampling failure; 2 TB check failures"},
    {"attempt": "smoke/small-002", "status": "pass-intermediate", "note": "STAT_W=2, 195 checks"},
    {"attempt": "smoke/small-003", "status": "pass-intermediate", "note": "STAT_W=2 after composition module was added, 195 checks"},
    {"attempt": "smoke/compose-001", "status": "fail", "note": "fixture defects; 3 cases fail, 22 TB check failures"},
    {"attempt": "smoke/compose-002", "status": "pass-intermediate", "note": "3 cases, 3 pass, 1102 checks"},
    {"attempt": "smoke/guard-0", "status": "pass-intermediate", "note": "exact STAT_W=0 fatal in smoke"},
    {"attempt": "smoke/guard-1", "status": "pass-intermediate", "note": "exact STAT_W=1 fatal in smoke"},
    {"attempt": "smoke/guard-33", "status": "pass-intermediate", "note": "exact STAT_W=33 fatal in smoke"},
    {"attempt": "smoke/guard-composecheck-001", "status": "pass-compile-only", "note": "guard compile remained clean with composition module present"},
    {"attempt": "runner-smoke-01", "status": "pass-subset", "note": "runner ordinary and guard-0 branches, 91 artifacts"},
]

result = {
    "schema": 1,
    "status": "COMPLETE_AUTHOR_EVIDENCE_TERMINAL",
    "terminal": True,
    "at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "operation_id": "B-DEEPEYE-ENCODED-FRAME-QUEUE-20261022-20",
    "task_id": "DEEPEYE-IMPLEMENTATION-20261014",
    "task_version": 1,
    "work_id": "B-ENCODED-FRAME-QUEUE-RTL-20261022-20-v1",
    "role": "sole ordinary DeepSeek Flash/max author; not product main",
    "instance_id": "deepseek-b-46",
    "job_id": "child-a65d74a1ffed41f0a5a81cbb8555e189",
    "thread_id": "01a15f69-4aad-7b03-94a4-605daf72edba",
    "turn_id": None,
    "turn_note": "not exposed to this child; null rather than inferred",
    "model": "deepseek-flash",
    "model_description": "DeepSeek V4.1 Flash",
    "reasoning_effort": "max",
    "product_root": str(root),
    "baseline_head": "aef19351f1836b23f9a714bc5626db4eb4df98c5",
    "actual_head": run.get("actual_head"),
    "contract": {
        "id": "DEEPEYE-HUMAN-LOCK-20261014",
        "revision": 1,
        "pin": "f5989cd5defce561f9ba98e6b18fc2682945f0a2",
        "requirements_sha256": "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
        "requirements_count": 15,
        "requirements_ids": ["H01","H02","H03","H04","H05","H06","H07","H08","H09","H10","H11","H12","H13","H14","H15"],
        "design_commit": "1011259415a0916054eb580687612580bc1e5f09",
        "verified_from_pinned_commit": True,
    },
    "inputs": inputs,
    "pinned_readonly": {
        "competition/deepeye/fpga/codec/deepeye_block_encoder.sv": "870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5",
        "competition/deepeye/fpga/stream/deepeye_block_stream.sv": "c8f8c0d99769efc64a91402ee23e7157368ff90ec765db5c413f02546715fff4",
        "handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json": "6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8",
    },
    "ownership": [
        "competition/deepeye/fpga/stream/deepeye_encoded_frame_queue.sv",
        "competition/deepeye/fpga/stream/encoded_frame_queue_candidate.md",
        "competition/deepeye/tests/rtl/stream/tb_encoded_frame_queue.sv",
        "competition/deepeye/tools/stream/run_encoded_frame_queue.py",
        "competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20/author/",
    ],
    "delivered_sources": delivered,
    "started_evidence": {"path": str(author / "STARTED.json"), "sha256": sha(author / "STARTED.json")},
    "final_run": {
        "path": str(final),
        "runner_exit": 0,
        "status": run["status"],
        "checks_run": run["checks_run"],
        "checks_failed": run["checks_failed"],
        "artifact_count": run["artifact_count"],
        "run_result_sha256": sha(final / "RUN_RESULT.json"),
        "artifacts_manifest_sha256": sha(final / "ARTIFACTS.json"),
        "source_manifest_sha256": sha(final / "source_manifest.json"),
        "toolchain_sha256": sha(final / "toolchain.json"),
        "started_at": run["started_at"],
        "finished_at": run["finished_at"],
        "elapsed_s": run["elapsed_s"],
        "invocation": [
            "python", "-B", "competition/deepeye/tools/stream/run_encoded_frame_queue.py",
            "--out", str(final)
        ],
        "cwd": str(root),
        "suites": suites,
    },
    "toolchain": {
        "vsim": "D:\\modelsim1\\win64\\vsim.exe",
        "vlog": "D:\\modelsim1\\win64\\vlog.exe",
        "vlib": "D:\\modelsim1\\win64\\vlib.exe",
        "vsim_version": "Model Technology ModelSim SE-64 vsim 10.7 Simulator 2017.12 Dec  7 2017",
        "vlog_version": "Model Technology ModelSim SE-64 vlog 10.7 Compiler 2017.12 Dec  7 2017",
    },
    "verification_summary": {
        "ordinary_cases": 27,
        "ordinary_tb_checks": 12246,
        "guard_cases": 3,
        "runner_checks": 218,
        "runner_checks_failed": 0,
        "all_ordinary_suites_pass": True,
        "guard_fatal_identity_exact": True,
        "tb_compile_errors": 0,
        "tb_simulation_errors": 0,
        "tb_warnings": 0,
        "status": "pass",
    },
    "preserved_attempts": preserved,
    "coverage": {
        "author_covered": [
            "reset, idle, single success and two-deep stall",
            "pre-edge no same-edge bypass and metadata-to-payload blocking",
            "old level<2 admission and no credit at old level two",
            "representative framing boundaries bytes 1/2/255/256 and lower/upper valid_bits",
            "representative early-last and missing-last fault2 cases",
            "invalid descriptor fault1 cases",
            "upstream errors 1, 2 and opaque 3; consecutive and around success",
            "fault with older sealed output draining",
            "duplicate/ABA tags",
            "cancel empty, after metadata, partial payload, sealed output, partial output, held cancel",
            "reset priority over cancel and reset after fault",
            "simultaneous allocate/retire and seal/retire",
            "bounded pointer wrap and duplicate tags",
            "STAT_W=2 public-port saturation of all five counters",
            "composition two-frame retention, stream metadata backpressure, raw/Rice, errors, cancel, full 256-byte raw payload",
            "guard 0/1/33 exact fatal identity",
        ],
        "not_author_exhaustive": [
            "all 2048 framing combinations and all 256 byte values",
            "at least 1000 ring wraps",
            "every early-last position for lengths 2..16 and the full boundary matrix",
            "cancel exactly on the final input byte or output-last edge",
            "independent isolated RTL mutants",
            "independent main accepted-edge model and oracle",
        ],
        "main_owned": [
            "exhaustive 2048 framing",
            "small-counter saturation and >=1000 wraps",
            "new exact op08/op09 composition expectations",
            "isolated RTL mutants with public-port counterexamples",
            "final product acceptance and publication",
        ],
    },
    "not_run": {
        "synthesis": "not_run",
        "implementation": "not_run",
        "timing": "not_run",
        "resource": "not_run",
        "physical_board": "not_run; A only",
        "system": "not_run",
        "all29_G05_B06_R03": "not_run",
    },
    "uncertainty": [
        "ModelSim 10.7 returns process exit 0 for the guard fatal in this environment; the runner requires that observed behavior and exact fatal identity. A tool change requires revalidation.",
        "Author-directed tests are not independent product acceptance; main review remains pending.",
        "No synthesis or board evidence exists for this new module.",
    ],
    "actions_not_taken": [
        "no commit or push",
        "no PR or publication",
        "no peer, group or Feishu message",
        "no credential, service, configuration, SQL or queue change",
        "no physical-board operation",
        "no read/import of main oracle or vectors",
        "no synthesis, implementation or timing run",
    ],
    "evidence_manifest": {
        "path": str(author / "EVIDENCE_MANIFEST.json"),
        "sidecar": str(author / "EVIDENCE_MANIFEST.sha256"),
        "note": "Generated after this RESULT and README; lists sha256 for every file under the author evidence directory except the manifest and sidecar, plus delivered and pinned sources.",
    },
    "product_acceptance": "not_claimed",
    "main_acceptance": "pending_independent_main_review",
}

out = author / "patches/RESULT_source.json"
out.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
print(out)
print(out.stat().st_size)