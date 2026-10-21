"""Independent op20 real ModelSim execution and public-port trace evaluation."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,gzip,hashlib,importlib.util,json,re,subprocess,sys,time

ROOT=Path(__file__).resolve().parents[4]
EP="competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20/main"
QP="competition/deepeye/fpga/stream/deepeye_encoded_frame_queue.sv"
TP="competition/deepeye/tests/rtl/stream/main_tb_encoded_frame_queue.sv"
CORE="competition/deepeye/fpga/codec/deepeye_block_encoder.sv"
STREAM="competition/deepeye/fpga/stream/deepeye_block_stream.sv"
PINS={CORE:"870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5",
      STREAM:"c8f8c0d99769efc64a91402ee23e7157368ff90ec765db5c413f02546715fff4"}
SHA=lambda b:hashlib.sha256(b).hexdigest()
def save(p,v):
    with p.open("x",encoding="utf-8") as f:json.dump(v,f,ensure_ascii=False,indent=2)
def model(root):
    e=root/EP;f=json.loads((e/"FROZEN.json").read_bytes())
    for name,digest in f["files"].items():assert SHA((e/name).read_bytes())==digest,name
    spec=importlib.util.spec_from_file_location("op20_independent_model",e/"independent_model.py")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m
def errors(text,own=None):
    reasons=[];own_count=0;positive=0
    for raw in text.splitlines():
        s=raw.strip()
        if s.startswith("# "):s=s[2:]
        if own and re.fullmatch(r"\*\* Fatal: "+re.escape(own),s):
            own_count+=1;continue
        tally=re.fullmatch(r"Errors: (0|[1-9][0-9]*), Warnings: (0|[1-9][0-9]*)",s,re.I|re.ASCII)
        if tally:
            n=int(tally[1])
            if not own and n:reasons.append("nonzero error tally")
            elif own and ((own_count==0 and n!=0) or (own_count>0 and (n!=1 or positive))):
                reasons.append("contradictory own-fatal tally")
            if n:positive+=1
        elif re.search(r"\b(?:error|errors|fatal)\b",s,re.I|re.ASCII):
            reasons.append("foreign or malformed diagnostic: "+s)
    if own and own_count!=1:reasons.append("own fatal count !=1")
    return reasons
def command(out,name,argv,timeout=180,guard=None):
    argv=list(map(str,argv));start=datetime.now(timezone.utc).isoformat()
    save(out/(name+".intent.json"),{"argv":argv,"cwd":str(out),"started":start})
    t=time.monotonic();p=subprocess.Popen(argv,cwd=out,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
    timed=False
    try:stdout,stderr=p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed=True;p.kill();stdout,stderr=p.communicate()
    (out/(name+".stdout.bin")).write_bytes(stdout);(out/(name+".stderr.bin")).write_bytes(stderr)
    text=(stdout+b"\n"+stderr).decode("utf-8",errors="replace")
    bad=errors(text,guard)
    record=dict(argv=argv,cwd=str(out),pid=p.pid,exit_code=p.returncode,timed_out=timed,
                elapsed_seconds=time.monotonic()-t,started=start,ended=datetime.now(timezone.utc).isoformat(),
                stdout_sha256=SHA(stdout),stderr_sha256=SHA(stderr),diagnostic_failures=bad)
    save(out/(name+".command.json"),record)
    assert p.returncode==0 and not timed and not bad,(name,record)
    return text
def standalone(m,run,vectors):
    summary=json.loads((vectors/"vectors.json").read_bytes())
    mismatches=0;examples=[];edges=0
    with (run/"trace.txt").open() as actual,gzip.open(vectors/"inputs.hex.gz","rt") as inputs,gzip.open(vectors/"expected.hex.gz","rt") as expected:
        for i,(inp,exp) in enumerate(zip(inputs,expected)):
            line=actual.readline().strip()
            parts=line.split();assert len(parts)==4 and parts[:2]==["Q",str(i)],(i,line)
            assert int(parts[2],16)==int(inp,16),(i,"stimulus changed")
            if i:
                try:got=int(parts[3],16)
                except ValueError:got=None
                want=int(exp,16)
                if got!=want:
                    mismatches+=1
                    if len(examples)<32:
                        g=m.unpack(got,m.OUTPUTS) if got is not None else {"unknown":parts[3]}
                        w=m.unpack(want,m.OUTPUTS)
                        examples.append(dict(edge=i,actual=g,expected=w,
                            differing={k:[w[k],g.get(k)] for k in w if w[k]!=g.get(k)}))
            edges+=1
        assert not actual.read().strip() and not inputs.read().strip() and not expected.read().strip()
    assert edges==summary["edges"]
    return dict(kind="standalone",edges=edges,checked_edges=edges-1,mismatches=mismatches,examples=examples,
                vector_coverage=summary["coverage"])

SOURCE=[("cfg_valid",1),("cfg_ready",1),("count",8),("e",4),("tag",16),
        ("s_valid",1),("s_ready",1),("sample",16),("sample_last",1),
        ("stream_level",2),("stream_ok",32),("stream_error",32),("stream_aborted",32)]
def composition(m,run):
    q=m.Queue();pending=[];fill=None;wire_frame=None;wire_pos=0
    count=0;bad=0;examples=[];full_complete=0;backpressured=0;retired=0
    admissions=0;raw_frames=0;rice_frames=0;error_frames=0;full256=0;aborts=0
    def fail(edge,kind,expected,actual):
        nonlocal bad
        bad+=1
        if len(examples)<32:examples.append(dict(edge=edge,kind=kind,expected=expected,actual=actual))
    with (run/"trace.txt").open() as f:
        for i,line in enumerate(f):
            parts=line.split();assert len(parts)==5 and parts[:2]==["C",str(i)],(i,line)
            # Source payload/metadata may be undefined only while their valid is0.
            # Packed driver below zeroes those irrelevant fields.
            x=m.unpack(int(parts[2],16),m.INPUTS)
            s=({n:0 for n,_ in SOURCE} if i==0 and x["rst"] else
               m.unpack(int(parts[4],16),SOURCE))
            want=q.observe(x)
            if i:
                try:got=m.unpack(int(parts[3],16),m.OUTPUTS)
                except ValueError:got={"unknown":parts[3]}
                if got!=want:fail(i,"queue public outputs",want,got)
            if x["rst"] or x["cancel"]:
                if x["cancel"] and not x["rst"]:aborts+=int(bool(q.frames or pending or fill or wire_frame))
                pending=[];fill=None;wire_frame=None;wire_pos=0
            else:
                if want["level"]==2 and not want["receiving"] and not x["mr"] and s["stream_ok"]>=2:
                    full_complete+=1
                if want["level"]==2 and x["mv"] and not want["imr"]:backpressured+=1
                # Upstream outputs must match independent integer codec of source.
                if x["mv"] and want["imr"]:
                    if not pending:fail(i,"unexpected stream metadata",None,{n:x[n] for n in m.META})
                    else:
                        wire_frame=pending.pop(0);wire_pos=0
                        meta,data=wire_frame
                        actual={n:x[n] for n in m.META}
                        if actual!=meta:fail(i,"stream metadata",meta,actual)
                        if meta["error"]:error_frames+=1;wire_frame=None
                        elif meta["raw"]:raw_frames+=1
                        else:rice_frames+=1
                        if len(data)==256:full256+=1
                if x["iv"] and want["ir"]:
                    if wire_frame is None:fail(i,"unexpected stream payload",None,x)
                    else:
                        meta,data=wire_frame
                        if wire_pos>=len(data):fail(i,"excess stream payload",len(data),wire_pos)
                        else:
                            expected=[data[wire_pos],int(wire_pos==len(data)-1)]
                            if [x["data"],x["last"]]!=expected:fail(i,"stream byte/last",expected,[x["data"],x["last"]])
                        wire_pos+=1
                        if wire_pos==len(data):wire_frame=None
                # Input config cannot overlap prior filling sample by old-state contract.
                old_fill=fill
                if s["s_valid"] and s["s_ready"]:
                    if old_fill is None:fail(i,"sample without config",None,s)
                    else:
                        old_fill["samples"].append(s["sample"])
                        final=len(old_fill["samples"])==old_fill["count"]
                        if bool(s["sample_last"])!=final:
                            pending.append(m.codec([],0,old_fill["tag"],2));fill=None
                        elif final:
                            pending.append(m.codec(old_fill["samples"],old_fill["e"],old_fill["tag"]));fill=None
                if s["cfg_valid"] and s["cfg_ready"]:
                    admissions+=1
                    if not 1<=s["count"]<=128 or s["e"] not in (0,1,2,4,8):
                        pending.append(m.codec([],0,s["tag"],1))
                    else:fill=dict(count=s["count"],e=s["e"],tag=s["tag"],samples=[])
                retired+=int(bool((want["omv"] and x["mr"] and want["error"]) or (want["ov"] and x["ready"] and want["last"])))
            q.edge(x);count+=1
    assert not q.frames and not pending and fill is None and wire_frame is None,"unfinished composition"
    assert full_complete>100 and backpressured>100 and full256>=1 and raw_frames>=2 and rice_frames>=2 and error_frames>=2 and aborts>=3
    assert retired==11
    return dict(kind="composition",edges=count,mismatches=bad,examples=examples,admissions=admissions,
                retired=retired,two_complete_while_stalled_edges=full_complete,full_backpressure_edges=backpressured,
                RAW=raw_frames,Rice=rice_frames,source_errors=error_frames,full256=full256,aborted_phases=aborts)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=ROOT);p.add_argument("--out",type=Path,required=True)
    p.add_argument("--mode",choices=("standalone","sat2","sat3","composition","mutants","guard0","guard1","guard33"),required=True)
    p.add_argument("--dut",type=Path);p.add_argument("--expect-mismatch",action="store_true")
    a=p.parse_args();root=a.root.resolve();out=a.out.resolve()
    out.relative_to(root/EP);out.mkdir(parents=True,exist_ok=False)
    e=root/EP;m=model(root);tools=Path("D:/modelsim1/win64")
    sources={QP:a.dut or root/QP,TP:root/TP,CORE:root/CORE,STREAM:root/STREAM}
    snapshot=out/"inputs";snapshot.mkdir()
    pins={}
    for n,path in sources.items():
        b=path.read_bytes()
        if n in PINS:assert SHA(b)==PINS[n]
        target=snapshot/Path(n).name;target.write_bytes(b)
        pins[n]={"source_path":str(path),"sha256":SHA(b),"snapshot":str(target)}
    save(out/"INPUTS.json",pins)
    checker_inputs={}
    for name,path in (("main_verifier.py",Path(__file__)),
                      ("independent_model.py",e/"independent_model.py"),
                      ("FROZEN.json",e/"FROZEN.json"),
                      ("composition_frozen.json",e/"composition_frozen.json")):
        raw=path.read_bytes();(snapshot/name).write_bytes(raw)
        checker_inputs[name]={"source_path":str(path),"sha256":SHA(raw)}
    save(out/"CHECKER_INPUTS.json",checker_inputs)
    result={"status":"RUNNING","mode":a.mode,"source_sha256":pins[QP]["sha256"]}
    try:
        command(out,"version",[tools/"vsim.exe","-version"],30)
        command(out,"vlib",[tools/"vlib.exe","lib"],30)
        command(out,"vlog",[tools/"vlog.exe","-sv","-work","lib",*[snapshot/Path(n).name for n in sources]],60)
        guard=a.mode.startswith("guard")
        width=int(a.mode[5:]) if guard else int(a.mode[3:]) if a.mode.startswith("sat") else 32
        top="main_queue_guard" if guard else "main_queue_composition" if a.mode=="composition" else "main_queue_tb"
        argv=[tools/"vsim.exe","-c","-work","lib","-l",out/"sim.transcript","-wlf",out/"sim.wlf",
              "-do","run -all; quit -f",f"-gSTAT_W={width}",top,"+TRACE="+str(out/"trace.txt")]
        if not guard and a.mode!="composition":
            vectors=e/a.mode
            raw=gzip.decompress((vectors/"inputs.hex.gz").read_bytes())
            (snapshot/"vectors.hex").write_bytes(raw);argv.append("+INPUT="+str(snapshot/"vectors.hex"))
        own=f"DEEPEYE_ENCODED_FRAME_QUEUE_INVALID_PARAM STAT_W={width}" if guard else None
        text=command(out,"vsim",argv,240,own)
        transcript=(out/"sim.transcript").read_bytes()
        assert not errors(transcript.decode("utf-8",errors="replace"),own)
        if guard:
            assert "MAIN_GUARD_MISSING" not in text
            result.update(status="PASS",guard_width=width,own_fatal=own)
        else:
            pattern=r"(?:# )?MAIN_COMPOSITION_DONE cycles=([0-9]+) retired=11" if a.mode=="composition" else rf"(?:# )?MAIN_QUEUE_DONE edges=([0-9]+) STAT_W={width}"
            markers=[re.fullmatch(pattern,line.strip()) for line in text.splitlines()]
            matches=[z for z in markers if z];assert len(matches)==1,"missing/duplicate/inconsistent completion"
            checked=composition(m,out) if a.mode=="composition" else standalone(m,out,vectors)
            assert checked["edges"]==int(matches[0][1])
            result.update(checked)
            numeric=[r for r in checked["examples"] if "unknown" not in r.get("actual",{})]
            passed=checked["mismatches"]==0
            if a.expect_mismatch:
                assert not passed and numeric,"not a concrete postreset behavioral counterexample"
                result.update(status="EXPECTED_BEHAVIORAL_REJECTION",numeric_examples=numeric)
            else:
                assert passed,checked
                result["status"]="PASS"
            trace=(out/"trace.txt").read_bytes()
            (out/"trace.txt.gz").write_bytes(gzip.compress(trace,mtime=0))
            result.update(trace_raw_sha256=SHA(trace),trace_bytes=len(trace),trace_gzip_sha256=SHA((out/"trace.txt.gz").read_bytes()))
    except Exception as exc:
        result.update(status="FAILED",error=repr(exc));raise
    finally:
        result["final_source_sha256"]=SHA((snapshot/Path(QP).name).read_bytes())
        save(out/"RESULT.json",result)
        print(json.dumps({k:v for k,v in result.items() if k not in ("examples","numeric_examples","vector_coverage")}),flush=True)
if __name__=="__main__":main()
