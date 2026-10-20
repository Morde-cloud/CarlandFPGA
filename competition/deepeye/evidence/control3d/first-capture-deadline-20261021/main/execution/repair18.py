"""Narrow main repair only after actual child terminal release."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
O=Path(__file__).resolve().parent
W=Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
E=W/"competition/deepeye/evidence/control3d/first-capture-deadline-20261021"
terminal=json.loads((O/"CHILD_TERMINAL.json").read_bytes())["result"][0]
assert terminal["terminal"] and not terminal["stale"]
assert terminal["status"]=="completed"
runner=W/"competition/deepeye/tools/control3d/run_first_capture_deadline.py"
data=runner.read_bytes()
assert hashlib.sha256(data).hexdigest()=="b7dea7fb82236a6e8fa8a3b959fb26835d6d35e0557d7fda9eaaca44cf9fd7fc"
D=E/"main/takeover";D.mkdir(exist_ok=False)
result=json.loads((E/"author/RESULT.json").read_bytes())
for r in result["author_files"]:
    raw=(W/r["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==r["sha256"]
    (D/Path(r["path"]).name).write_bytes(raw)
assert hashlib.sha256((W/result["author_files"][0]["path"]).read_bytes()).hexdigest()==json.loads((E/"main/check-01/RESULT.json").read_bytes())["source_sha256"]
receipt={"at_utc":datetime.now(timezone.utc).isoformat(),"decision":"MAIN_TAKEOVER_RUNNER_AND_TEST_AFTER_TERMINAL",
 "job_id":terminal["job_id"],"terminal_status":terminal["status"],"terminal_receipt_sha256":hashlib.sha256((O/"CHILD_TERMINAL.json").read_bytes()).hexdigest(),
 "basis":"9 normal/guard and11 mutant qualification negative fixtures accepted incorrectly; original snapshots and failures preserved",
 "scope":["competition/deepeye/tools/control3d/run_first_capture_deadline.py","competition/deepeye/tests/control/test_first_capture_deadline_runner.py"],
 "rtl_unchanged":True,"old_08_17_unchanged":True,"second_assignment":False}
(D/"TAKEOVER.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
s=data.decode()
def change(a,b):
    global s
    assert s.count(a)==1,a[:100]
    s=s.replace(a,b)
change('    elif line.startswith("#"):\n        line = line[1:].lstrip()\n    return line.rstrip()','    return line')
change('    for raw in text.splitlines():','    for raw in text.split("\\n"):')
change('    reasons = []\n    runs = []\n    summaries = []\n    finishes = []\n    scenarios = []',
'''    reasons = []
    phase = 0
    for _, line in iter_normalized(text):
        if RUN_RE.fullmatch(line):
            if phase != 0: reasons.append("RUN order")
            phase = 1
        elif SCENARIO_RE.fullmatch(line):
            if phase != 1: reasons.append("SCENARIO order")
        elif SUMMARY_RE.fullmatch(line):
            if phase != 1: reasons.append("SUMMARY order")
            phase = 2
        elif FINISH_RE.fullmatch(line):
            if phase != 2: reasons.append("FINISH order")
            phase = 3
    if type(width) is not int or not 1 <= width <= 32:
        reasons.append("unsupported normal width")
    runs = []
    summaries = []
    finishes = []
    scenarios = []''')
change('        if sum(summary_groups.values()) != summary["scenarios"]:',
'''        if not scenarios or any(actual_group_counts.get(g, 0) <= 0 for g in expected_groups):
            reasons.append("required group must contain a scenario")
        if summary["checks"] <= 0:
            reasons.append("SUMMARY checks must be positive")
        if sum(summary_groups.values()) != summary["scenarios"]:''')
change('    safe_width = safe_budget_width(width)\n    runs = []',
'''    order = []
    for _, line in iter_normalized(text):
        if RUN_RE.fullmatch(line): order.append("run")
        elif GUARD_PARAM_RE.fullmatch(line): order.append("param")
        elif GUARD_FATAL_RE.fullmatch(line): order.append("fatal")
        elif "DEEPEYE_" in line: reasons.append("malformed guard protocol")
    if order != ["run", "param", "fatal"]:
        reasons.append("guard RUN/diagnostic/fatal order")
    safe_width = safe_budget_width(width)
    runs = []''')
# Existing subprocess exits are integers; never accept bool/float lookalikes.
assert s.count("    if exit_code != 0:")==3
s=s.replace("    if exit_code != 0:","    if type(exit_code) is not int or exit_code != 0:")
begin=s.index("def parse_mutant_log(");end=s.index("\ndef source_manifest(",begin)
s=s[:begin]+(O/"strict_mutant_function.py.txt").read_text()+ "\n\n"+s[end:]
change('    args = parser.parse_args(argv)\n\n    source_root',
'''    args = parser.parse_args(argv)
    allowed = {f"standalone-w{w:02d}" for w in range(1, 6)}
    allowed |= {"standalone-w32-prefix", "composition", "guard-w00", "guard-w33"}
    if args.only is not None and (
        not args.only or len(set(args.only)) != len(args.only)
        or not set(args.only) <= allowed or args.mode == "mutants"
    ):
        parser.error("--only requires unique known normal case IDs")
    import math
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be finite and positive")

    source_root''')
# Execute the already hashed source snapshot, not mutable working files.
change('    snapshots = snapshot_sources(source_root, run_root / "sources", manifest)\n    versions',
'''    snapshots = snapshot_sources(source_root, run_root / "sources", manifest)
    execution_root = run_root / "execution-inputs"
    for entry in snapshots:
        if not entry["snapshot"]:
            parser.error(f"missing input {entry['relative']}")
        content = Path(entry["snapshot"]).read_bytes()
        if sha256_bytes(content) != entry["sha256"]:
            parser.error(f"input changed during snapshot {entry['relative']}")
        target = execution_root / entry["relative"]
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as f:
            f.write(content)
    versions''')
change('            source_root, modelsim_dir, run_root, args.timeout,','            execution_root, modelsim_dir, run_root, args.timeout,')
change('mutant_records = mutant_cases(source_root, modelsim_dir, run_root / "mutants", args.timeout)','mutant_records = mutant_cases(execution_root, modelsim_dir, run_root / "mutants", args.timeout)')
with runner.open("w",encoding="utf-8",newline="\n") as f:f.write(s)
(D/"REPAIR_RESULT.json").write_text(json.dumps({"runner_sha256":hashlib.sha256(runner.read_bytes()).hexdigest()},indent=2),encoding="utf-8")
print(json.dumps(receipt))
