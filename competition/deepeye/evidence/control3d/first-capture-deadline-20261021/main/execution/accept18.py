"""Main acceptance binds exact unchanged RTL, independent execution and repair."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
O=Path(__file__).resolve().parent
W=Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
EP="competition/deepeye/evidence/control3d/first-capture-deadline-20261021";E=W/EP
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,data):
    with p.open("x",encoding="utf-8",newline="\n") as f:json.dump(data,f,ensure_ascii=False,indent=2)
term=json.loads((O/"CHILD_TERMINAL.json").read_bytes())["result"][0]
assert term["status"]=="completed" and term["terminal"] and not term["stale"]
assert term["result"]["model"]=="deepseek-flash" and term["result"]["reasoning_effort"]=="max"
roothead=subprocess.check_output(["git","-C",str(W),"rev-parse","HEAD"]).decode().strip()
assert roothead=="ccf3698cce065e20dbfa24bb6d07a97be7e38de6"
assert not subprocess.check_output(["git","-C",str(W),"diff","--cached","--name-only"]).strip()
before=json.loads((O/"TRACKED_BEFORE.json").read_bytes())
changed=[path for path,h in before.items() if sha(W/path)!=h]
assert not changed,changed
assert sha(W/"handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json")=="6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8"
author=E/"author";index=json.loads((author/"EVIDENCE_INDEX.json").read_bytes())
selected=[]
for r in index["entries"]:
    path=author/r["path"];assert path.resolve().is_relative_to(author.resolve()) and path.is_file()
    assert sha(path)==r["sha256"] and path.stat().st_size==r["size"],r
    selected.append(path)
assert len(selected)==387 and len(set(selected))==387
selected.extend(author/n for n in ("EVIDENCE_INDEX.json","RESULT.json","REPORT.md"))
assert sha(author/"EVIDENCE_INDEX.json")=="6be0efecc1c201cdda4ab5b9113eb9585a2736f6a251698436a3b38d66157e3f"
assert sha(author/"RESULT.json")=="559720c34f7164393958d1abfa9169d80d8531d4a5462e19929a9bcb0e86a9a6"
assert sha(author/"REPORT.md")=="857c6a7fbb5dff0e42a02deb72b719ea364193c5abb41feeb8b0d3ce4e6b14f5"
checks={name:json.loads((E/"main"/name/"RESULT.json").read_bytes()) for name in
        ("check-01","mutant-sources","runner-green-01","mutant-parser-green-01","final-checks")}
assert all(v["status"]=="PASS" for v in checks.values())
for name in ("check-01","mutant-off-by-one","mutant-cancel-ignored","mutant-late-revival","mutant-renewal"):
    folder=E/"main"/name
    for r in json.loads((folder/"COMMANDS.json").read_bytes()):
        assert r["exit_code"]==0 and not r["timeout"]
        for stream in ("stdout","stderr"):assert sha(folder/(r["name"]+"."+stream+".txt"))==r[stream+"_sha256"]
frozen=json.loads((E/"main/frozen/FREEZE.json").read_bytes())
for n,h in frozen["files"].items():assert sha(E/"main/frozen"/n)==h
mainverifier=W/"competition/deepeye/tools/control3d/main_verify_first_capture_deadline.py"
assert sha(mainverifier)==frozen["oracle_source_sha256"]
rtl=W/"competition/deepeye/fpga/control3d/deepeye_first_capture_deadline.sv"
assert sha(rtl)==checks["check-01"]["source_sha256"]=="860010695ef248467e518605dbecf0482e9a2e6b9a1f0b9d30c6e3e730047fae"
write(E/"main/UNCHANGED_INPUTS.json",{"baseline":roothead,"tracked_count":len(before),"changed":[],"hashes":before})
write(E/"main/CHILD_RESULT_CONSUMED.json",{
 "job_id":term["job_id"],"work_id":term["work_id"],"status":term["status"],"terminal":True,"stale":False,
 "actual_thread":term["result"]["thread_id"],"actual_turn":term["result"]["turn"]["id"],
 "model":term["result"]["model"],"effort":term["result"]["reasoning_effort"],
 "author_turn_note":"Author did not know its turn ID; actual completed controller result supplies it here.",
 "main_result":"RTL accepted within bounded scope; author runner rejected then main repaired after terminal release.",
 "independent_execution_timing":"Main froze oracle before dispatch and tested copied RTL while author closeout continued. Final terminal RTL hash and snapshot match; no author write takeover until terminal."})
execution=E/"main/execution";execution.mkdir()
for n in ("run_main18.py","mutants18.py","freeze_runner_probes18.py","probe_runner18.py","probe_mutant18.py",
          "strict_mutant_function.py.txt","repair18.py","final_checks18.py","accept18.py"):
    (execution/n).write_bytes((O/n).read_bytes())
tests={"main_standalone_edges":sum(x["rows"] for x in frozen["standalone"].values()),
 "main_standalone_scenarios":sum(x["scenarios"] for x in frozen["standalone"].values()),
 "main_composition_edges":112,"main_composition_scenarios":7,"main_compiled_mutants":4,
 "main_mutant_numeric_mismatches":{r["name"]:r["numeric_mismatches"] for r in checks["mutant-sources"]["mutants"]},
 "parser_independent_cases":61,"original_parser_misaccepts":20,"final_unit_methods":33,"portable_methods":33,
 "original_unit_methods_unchanged":23,"original_incomplete_mutant_control_rejected":1,
 "saved_author_cases_reclassified":21,"new_runner_cases":3,
 "author_scenarios":3715,"author_assertion_checks":916438,"author_compiled_mutant_runs":12}
receipt={"decision":"ACCEPT_BOUNDED_FIRST_CAPTURE_DEADLINE_SOFTWARE_AND_RTL_SIMULATION",
 "at_utc":datetime.now(timezone.utc).isoformat(),"task_id":"DEEPEYE-IMPLEMENTATION-20261014","task_version":1,
 "work_id":"B-LOCAL-FIRST-CAPTURE-DEADLINE-CONTINUE-20261021-v1",
 "operation_id":"B-DEEPEYE-FIRST-CAPTURE-DEADLINE-20261021-18",
 "owner_thread":"01a13b55-095b-7461-8dd5-5476a130bd82","owner_turn":"01a15a57-d30e-75f2-9fa1-fc0d16a995a6",
 "contract_id":"DEEPEYE-HUMAN-LOCK-20261014","revision":1,"requirement_ids":[f"H{i:02}" for i in range(1,16)],
 "requirements_sha256":"c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
 "contract_pin":"f5989cd5defce561f9ba98e6b18fc2682945f0a2","design_pin":"1011259415a0916054eb580687612580bc1e5f09",
 "baseline":roothead,"rtl_sha256":sha(rtl),"runner_sha256":checks["final-checks"]["runner_sha256"],
 "test_sha256":checks["final-checks"]["test_sha256"],"main_oracle_sha256":sha(mainverifier),
 "tests":tests,"old_tracked_files_unchanged":len(before),"author_index_entries_rehashed":387,
 "author_findings":["20 parser misaccept fixtures retained in runner-preliminary/mutant-parser-red",
                    "original 24th mutant accepting test was incomplete and unmatched; replaced with rejection, 9 additional regression methods",
                    "CLI empty/unknown selection could report PASS; now rejected before output creation",
                    "runner now compiles immutable hashed execution-input copies; old author runs retain their original working-source provenance"],
 "roles":"One Flash/max author, main independently froze/executed RTL oracle. Main authored runner repair and its supplemental checks; no separate independent implementer claimed for that repair.",
 "tools":"ModelSim SE-64 10.7; Python3.12.9; hidden subprocesses",
 "not_run":["synthesis","implementation","timing","CDC/RDC","all29","G05","B06","R03","board","system"],
 "limits":["width32 bounded prefix only","same-clk candidate fixture only","no physicalTTL/sourcefreshness/BOOT/clock/ABI/ENABLE/motion authority","no product STOP/PWM wiring","A alone physical board","old A three-RTL OOC does not cover this new module"],
 "remaining":"Exact-source coordinator/A/C independent review; full product and hardware gates remain open."}
write(E/"main/ACCEPTANCE.json",receipt)
readme=f"""# First-capture deadline candidate — operation18

This same-clock monitor observes the first record during E0+1 through E0+N inclusive. Reset/cancel clears all state; WAIT plus start rejects without renewal; zero-budget requests reject even from a terminal state. Same-edge start/observed does not complete. A last-edge pre-edge observation wins over expiry. Late observations cannot revive a terminal result.

The literal B15 public-port fixture verifies N3 completion at row7 and N2 expiry at row6, quiet input expiry, retained records under backpressure, and the pre-handshake/post-fault distinction. It adds no product STOP/PWM wiring or public ABI.

Main froze its absolute-edge oracle, 6618 scenarios/132010 standalone edges, 7 scenarios/112 composition edges and expected values before author dispatch. Exact source `860010695ef248467e518605dbecf0482e9a2e6b9a1f0b9d30c6e3e730047fae` passes all of them. Four independently compiled RTL mutations produce numeric public-port mismatches: 103 off-by-one, 230 ignored-cancel, 33 late-revival, 43 renewal. All compiler/simulator processes exit0; the oracle fails as expected. This is distinct from the author's 3715 scenarios/916438 assertions and twelve compiled mutant runs.

Main rejected 20 parser misaccept fixtures (9 normal/guard, 11 mutant), saved the original source, waited for actual terminal release, and repaired the runner. All61 independent parser expectations now match.33 unit methods and33 minimal portable methods pass;23 original methods are unchanged. The original incomplete/unmatched mutant accepting fixture is now a rejection;9 additional regression methods were added. Genuine normal/guard logs and all21 original final author simulation cases remain accepted. Three fresh selected cases exercise fixed source snapshot compilation. The `author/` report and candidate document describe the original author results; this README and `main/ACCEPTANCE.json` describe the final reviewed runner.

The final parser requires exact framing, ordered unique RUN/SCENARIO/SUMMARY/FINISH, positive required groups and consistent counts. Mutant qualification requires complete numeric public-port mismatches, matching scenario failures/summary/own-fatal and no X or load-error substitution. CLI empty/unknown/duplicate selections fail before creating a run. ModelSim10.7's actual `$fatal` exit0 is retained and qualified by exact guard diagnostics. Commands combine stdout/stderr in author runner logs; main independent runs preserve separate streams.

Reproduce from repository root:

```powershell
python -B competition/deepeye/tests/control/test_first_capture_deadline_runner.py -v
python -B competition/deepeye/tools/control3d/main_verify_first_capture_deadline.py --root . --out <new-directory>
python -B competition/deepeye/tools/control3d/run_first_capture_deadline.py --source-root . --run-root <another-new-directory>
```

ModelSim defaults to `D:/modelsim1/win64`; pass the author runner's `--modelsim-dir` for another installation. Main verifier currently uses that same explicit local path. Frozen vectors and TBs are in `main/frozen`; each real main run has COMMANDS/RESULT/INPUTS and raw stdout/stderr/transcript. Author387 indexed artifacts plus original reports, preflight failures and source snapshots are retained. Main real tests first ran against copied RTL while author closeout continued; final terminal source hashes match. Main took over runner/test only after actual completed/nonstale release. Main authored the runner repair, so its new runner tests are not claimed as a separate implementer's review.

All {len(before)} existing tracked files, old08–17 evidence and protected codec bytes remain unchanged. New synthesis/implementation are blocked/not_run without Vivado. Width32 tests are bounded prefixes. No physicalTTL, source/freshness, clock/BOOT, TRACE/register/HWH, ENABLE, CDC/RDC or motion authority is granted. All29/G05/B06/R03/board/system remainnot_run; only A operates hardware. The reviewed old A OOC applies to the original three RTL files, not this module.

DEEPEYE-IMPLEMENTATION-20261014/v1; DEEPEYE-HUMAN-LOCK-20261014/revision1 H01–H15 requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, pin `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, design `1011259415a0916054eb580687612580bc1e5f09` remain fixed. Full3D/UI/solid collision/free camera/layout/equal gates/full passage/hidden truth/causal sensing/substantive online3D PC AI and both H12 chains remain mandatory.
"""
with (E/"README.md").open("x",encoding="utf-8",newline="\n") as f:f.write(readme)
excluded=[]
for path in sorted((E/"main").rglob("*")):
    if not path.is_file():continue
    if any(p in {"lib","work","__pycache__"} for p in path.relative_to(E/"main").parts) or path.suffix==".wlf":
        excluded.append({"path":str(path.relative_to(W)),"bytes":path.stat().st_size,"sha256":sha(path)})
    else:selected.append(path)
write(O/"UNPUBLISHED_REGENERABLE_CACHE_INDEX.json",excluded)
selected.extend([E/"README.md",mainverifier,*[W/r["path"] for r in json.loads((author/"RESULT.json").read_bytes())["author_files"]]])
assert len(selected)==len(set(selected))
files=[{"path":p.relative_to(W).as_posix(),"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(selected)]
write(O/"SELECTED.json",{"root":str(W),"baseline":roothead,"files":files})
print(json.dumps({"status":"accepted_bounded","files":len(files),"bytes":sum(x["bytes"] for x in files),"old_tracked_unchanged":len(before),
                  "acceptance_sha256":sha(E/"main/ACCEPTANCE.json"),"regenerable_caches_unpublished":len(excluded)}))
