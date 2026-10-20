"""Independent frozen Python qualification probes. No vendor/network execution."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,socket,subprocess,sys

E=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(p,x):
    with p.open("x",encoding="utf-8") as f:json.dump(x,f,ensure_ascii=False,indent=2)

def parser_probe(m,c):
    width=c.get("width",0 if c["kind"]=="guard" else 1)
    if c["kind"]=="normal":
        return m.qualify_normal_log(c["text"],width,"standalone",m.SMALL_GROUPS,c["exit_code"],c["timed_out"])
    return getattr(m,"qualify_"+c["kind"]+"_log")(c["text"],width,c["exit_code"],c["timed_out"])

def install_synthetic_tools(m,case,bases):
    def selected(path):return path.parent.name=="cancel-ignored" and int(path.name[1:])==case["width"]
    def compiler(case_dir,*args):
        return {"ok":not(selected(case_dir) and case["injection"]=="compile_error"),
                "synthetic_compile_stub":True,"reason":"synthetic selected compilation failure"}
    def simulator(case_dir,modelsim_dir,top,generic,value,timeout):
        injection=case["injection"] if selected(case_dir) or case["injection"]=="all_survivors" else None
        kind="normal" if injection in ("survivor","all_survivors") else "mutant"
        text=bases[kind].replace("width=1",f"width={value}")
        code=0;timed=False
        if injection=="foreign_error":text+="** Error: unrelated simulator failure\n"
        if injection=="plain_error":text+="Error: unrelated runtime failure\n"
        if injection=="abnormal_exit":code=17
        if injection=="timeout":timed=True
        if injection=="missing_finish":text="\n".join(l for l in text.splitlines() if "FC_FINISH" not in l)+"\n"
        if injection=="missing_summary":text="\n".join(l for l in text.splitlines() if "FC_SUMMARY" not in l)+"\n"
        if injection=="empty":text=""
        if injection=="extra_tally":text+="Errors: 7, Warnings: 0\n"
        if injection=="wrong_guard":text=bases["guard"]
        if injection!="missing_file":(case_dir/"sim.log").write_text(text,encoding="utf-8",newline="\n")
        return {"exit_code":code,"timed_out":timed,"synthetic_simulation_stub":True}
    m.compile_case=compiler;m.run_vsim_case=simulator
    m.capture_versions=lambda *args:{"synthetic_stub":True,"vendor_invocations":0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=E.parents[4])
    p.add_argument("--source",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--expect",choices=("baseline","repaired"),default="repaired")
    p.add_argument("--cli",default=None)
    a=p.parse_args();W=a.root.resolve();D=a.out.resolve();D.mkdir(parents=True,exist_ok=False)
    frozen=json.loads((E/"FREEZE.json").read_bytes())
    for n,h in frozen["files"].items():assert sha((E/n).read_bytes())==h
    source=a.source or W/"competition/deepeye/tools/control3d/run_first_capture_deadline.py"
    raw=source.read_bytes();(D/"runner_under_test.py").write_bytes(raw)
    spec=importlib.util.spec_from_file_location("actual_qualified_runner",D/"runner_under_test.py")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    coord=json.loads((E/"inputs/PARSER_CASES_FROZEN.json").read_bytes())["cases"]
    extra=json.loads((E/"SUPPLEMENTAL_CASES_FROZEN.json").read_bytes())
    ag=json.loads((E/"inputs/AGGREGATION_CASES_FROZEN.json").read_bytes())["cases"]
    ag=[{"name":n,"injection":inj,"width":2,"expected":e,"coordinator":True} for n,inj,e in ag]
    ag+=json.loads((E/"AGGREGATION_SUPPLEMENTAL_FROZEN.json").read_bytes())
    bases={k:next(c["text"] for c in coord if c["name"]==k+"-minimal-positive") for k in ("normal","guard","mutant")}
    attempts=[]
    def forbidden(*args,**kw):
        attempts.append(repr(args))
        raise RuntimeError("Vendor processes and network are forbidden in this Python-only probe.")
    subprocess.Popen=forbidden;socket.socket=forbidden
    if a.cli:
        case=next(c for c in ag if c["name"]==a.cli)
        install_synthetic_tools(m,case,bases)
        result=m.main(["--mode","mutants","--source-root",str(W),"--run-root",str(D/"synthetic-cli"),
                       "--modelsim-dir","D:/modelsim1/win64"])
        save(D/"CLI_RESULT.json",{"synthetic_only":True,"injection":case,"actual_entrypoint_return":result,
             "expected_return":0 if case["expected"] else 1,"source_sha256":sha(raw),"vendor_invocations":0,
             "blocked_process_network_attempts":attempts})
        assert not attempts
        return result
    parser_rows=[];aggregation_rows=[]
    for i,c in enumerate(coord+extra):
        try:
            value=parser_probe(m,c);actual=value[0];error=None;reasons=value[2]
        except Exception as e:actual=False;error=repr(e);reasons=[]
        parser_rows.append({"name":c["name"],"coordinator":i<len(coord),"expected":c["expected_accept"],
                            "actual":actual,"match":actual==c["expected_accept"],"exception":error,"reasons":reasons,
                            "input_sha256":sha(c["text"].encode())})
    for i,c in enumerate(ag):
        folder=D/"aggregation"/f"{i:02d}-{c['name']}";folder.mkdir(parents=True,exist_ok=False)
        install_synthetic_tools(m,c,bases)
        try:
            records=m.mutant_cases(W,Path("NO_VENDOR_EXECUTION"),folder,1)
            actual=all(r["ok"] for r in records);error=None
        except Exception as e:
            records=[];actual=False;error=repr(e)
        row={"case":c,"coordinator":i<4,"expected":c["expected"],"actual":actual,"match":actual==c["expected"],
             "exception":error,"records":records,"synthetic_only":True}
        save(folder/"PROBE_RESULT.json",row)
        aggregation_rows.append({"case":c,"actual":actual,"match":actual==c["expected"],"exception":error,"coordinator":i<4})
    report={"source_sha256":sha(raw),"expect":a.expect,"parser_cases":len(parser_rows),"aggregation_cases":len(aggregation_rows),
        "coordinator_parser_misaccepts":sum(r["coordinator"] and not r["match"] and r["actual"] for r in parser_rows),
        "coordinator_aggregate_misaccepts":sum(r["coordinator"] and not r["match"] and r["actual"] for r in aggregation_rows),
        "parser_mismatches":sum(not r["match"] for r in parser_rows),
        "aggregation_mismatches":sum(not r["match"] for r in aggregation_rows),
        "parser_exceptions":sum(bool(r["exception"]) for r in parser_rows),
        "aggregation_exceptions":sum(bool(r["exception"]) for r in aggregation_rows),
        "blocked_process_network_attempts":attempts,"vendor_invocations":0,
        "parser_results":parser_rows,"aggregation_results":aggregation_rows}
    save(D/"RESULT.json",report)
    compact={k:v for k,v in report.items() if k not in ("parser_results","aggregation_results")}
    print(json.dumps(compact))
    assert not attempts
    if a.expect=="baseline":
        assert report["coordinator_parser_misaccepts"]==15 and report["coordinator_aggregate_misaccepts"]==3
    else:
        assert all(report[k]==0 for k in ("parser_mismatches","aggregation_mismatches","parser_exceptions","aggregation_exceptions"))
    return 0

if __name__=="__main__":raise SystemExit(main())
