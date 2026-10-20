"""Freeze supplemental expectations before changing the delivered runner."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
O=Path(__file__).resolve().parent
W=Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
E=W/"competition/deepeye/evidence/control3d/first-capture-runner-qualification-20261021-19"
old=json.loads((E/"inputs/PARSER_CASES_FROZEN.json").read_bytes())["cases"]
base={k:next(c["text"] for c in old if c["name"]==k+"-minimal-positive") for k in ("normal","guard","mutant")}
cases=[]
def add(name,kind,text,expected,width=None,code=0,timed=False):
    cases.append({"name":name,"kind":kind,"text":text,"expected_accept":expected,"width":(0 if kind=="guard" else 1) if width is None else width,"exit_code":code,"timed_out":timed})
for kind in ("normal","guard","mutant"):
    lines=base[kind].splitlines()
    positions={"before_run":0,"after_run":1,"before_result":len(lines)-(2 if kind=="normal" else 1),"after_result":len(lines)}
    for label,pos in positions.items():
        for count in (0,1,2,7):
            expected=(count==0) if kind=="normal" else ((count==0 and pos<len(lines)) or (count==1 and pos==len(lines)))
            for tally in (f"Errors: {count}, Warnings: 0",f"ERRORS: {count}, WARNINGS: 3",f"eRrOrS: {count}, wArNiNgS: 7"):
                for prefix in ("","# "):
                    for ending in ("\n","\r\n"):
                        text=ending.join(prefix+l for l in [*lines[:pos],tally,*lines[pos:]])+ending
                        add(f"{kind}-{label}-{count}-{len(cases)}",kind,text,expected)
    for label,pos in positions.items():
        for diagnostic in ("Error: unrelated","Fatal: unrelated","ERROR: unrelated","fAtAl: unrelated",
                           "** Error: unrelated","** FATAL: unrelated"," error: unrelated","Error missing colon"):
            add(f"{kind}-{label}-foreign-{len(cases)}",kind,"\n".join([*lines[:pos],diagnostic,*lines[pos:]])+"\n",False)
    for malformed in ("Errors: -1, Warnings: 0","Errors: 01, Warnings: 0","Errors: 1.0, Warnings: 0",
                      "Errors: nan, Warnings: 0","Errors: x, Warnings: 0","Errors: 1e0, Warnings: 0",
                      "Errors: ٠, Warnings: 0","Errors:  0, Warnings: 0","Errors: 0",
                      "Errors: 0, Warnings: nope","Errors: 0, Warnings: -1","Errors: 0, Warnings: 00",
                      "Errors: 0, Warnings: 0 trailing","prefix Errors: 0, Warnings: 0",
                      "Errors : 0, Warnings: 0","Errors: 0; Warnings: 0","Errors: 0, Warnings: 0 Errors: 0"):
        add(f"{kind}-malformed-{len(cases)}",kind,base[kind]+malformed+"\n",False)
    for warning in ("Warning: arbitrary warning","** Warning: bounded warning"):
        add(f"{kind}-warning-{len(cases)}",kind,base[kind]+warning+"\n",True)
    zeros=["Errors: 0, Warnings: 0"]*3
    add(f"{kind}-multiple-stage-zeros-before",kind,"\n".join([*zeros,*lines])+"\n",True)
    if kind=="normal":
        add("normal-multiple-stage-zeros-after",kind,"\n".join([*lines,*zeros])+"\n",True)
    else:
        add(kind+"-zeros-before-own-one-after",kind,"\n".join([*zeros,*lines,"Errors: 1, Warnings: 2"])+"\n",True)
        add(kind+"-duplicate-own-one",kind,base[kind]+"Errors: 1, Warnings: 0\nErrors: 1, Warnings: 0\n",False)
        add(kind+"-own-one-then-zero",kind,base[kind]+"Errors: 1, Warnings: 0\nErrors: 0, Warnings: 0\n",False)
    for code in (None,False,True,0.0,"0",17):
        add(kind+"-bad-exit-"+str(len(cases)),kind,base[kind],False,code=code)
# Same phase/accounting rules apply to the second exact unsupported-width guard.
for c in list(cases):
    if c["kind"]=="guard" and (c["name"].startswith("guard-malformed") or "stage" in c["name"] or "after_result" in c["name"]):
        text=c["text"].replace("width=0 kind=guard","width=33 kind=guard").replace("BUDGET_W=0 SAFE_BUDGET_W=1","BUDGET_W=33 SAFE_BUDGET_W=32")
        add(c["name"]+"-w33","guard",text,c["expected_accept"],33,c["exit_code"],c["timed_out"])
aggregate=[
 {"name":"all-targets","injection":None,"width":2,"expected":True},
 {"name":"one-survivor","injection":"survivor","width":2,"expected":True},
 {"name":"all-survivors","injection":"all_survivors","width":2,"expected":False},
]
for width in (1,2,3):
    for failure in ("foreign_error","plain_error","abnormal_exit","timeout","missing_finish","missing_summary","empty","missing_file",
                    "extra_tally","compile_error","wrong_guard"):
        aggregate.append({"name":f"w{width}-{failure}","injection":failure,"width":width,"expected":False})
policy="""# Frozen op19 runner qualification policy

This is a Python-only qualification repair. All fixtures are synthetic unless explicitly labeled saved historical ModelSim output. Main inspected the delivered code and coordinator findings before freezing these expectations; there is no blind-oracle claim.

Recognize the saved ModelSim error tally grammar `Errors: <canonical ASCII unsigned decimal>, Warnings: <canonical ASCII unsigned decimal>` with case-insensitive labels. Keep its ordinary spaces and comma framing, raw or one exact `# ` transcript prefix, with LF/CRLF. Malformed tally-like records reject. Warning counts may be nonnegative; ordinary warnings do not imply an error.

Normal executions allow no positive error count. Multiple stage-local zero tallies are valid, including before and after the protocol. Guard and target-mutant executions allow exactly their own validated fatal: zero tallies before that fatal are valid stage-local summaries; at most one positive tally may follow it and that count must be exactly one. A zero after the own fatal, a positive tally before it, duplicate positive tallies, extra counts or malformed accounting reject. An absent tally remains admissible for the existing complete minimal protocol controls. Error accounting never substitutes for complete RUN/SCENARIO/SUMMARY/FINISH/own-fatal validation. Plain/case-varied unrelated Error/Fatal records reject everywhere.

For each selected mutant width, compilation must succeed and simulation must complete with the expected integer exit, no timeout, and a complete qualified transcript. Classify it as `target_hit` (complete numeric behavioral mismatch), `survived` (complete healthy normal transcript), or `execution_error`. A healthy survivor is valid but contributes no target hit. Every selected invocation must be valid and every mutation class must have at least one target hit. Any execution error propagates to the aggregate and CLI exit1; all-survivor classes also fail. No error is excused by another width's hit.

Use the exact coordinator43 parser fixtures and4 orchestration fixtures, frozen supplemental phase/tally/diagnostic matrices and synthetic aggregation/CLI seams. Preserve the original18 REVISE, original negative records and all old sources/RTL/testbench/oracle/vectors/evidence/manifests. Read-only reclassify21 historical author cases; execute Python tests and portable copies only. No ModelSim/Vivado/board runs.
"""
for name,data in (("SUPPLEMENTAL_CASES_FROZEN.json",cases),("AGGREGATION_SUPPLEMENTAL_FROZEN.json",aggregate)):
    with (E/name).open("x",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False,indent=2)
with (E/"POLICY.md").open("x",encoding="utf-8",newline="\n") as f:f.write(policy)
freeze={"at_utc":datetime.now(timezone.utc).isoformat(),"source_before_sha256":hashlib.sha256((W/"competition/deepeye/tools/control3d/run_first_capture_deadline.py").read_bytes()).hexdigest(),
 "main_source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"coordinator_parser":43,"coordinator_aggregation":4,
 "supplemental_parser":len(cases),"supplemental_aggregation":len(aggregate),
 "files":{n:hashlib.sha256((E/n).read_bytes()).hexdigest() for n in ("SUPPLEMENTAL_CASES_FROZEN.json","AGGREGATION_SUPPLEMENTAL_FROZEN.json","POLICY.md")}}
with (E/"FREEZE.json").open("x",encoding="utf-8") as f:json.dump(freeze,f,indent=2)
print(json.dumps(freeze))
