"""Independent operation18 absolute-edge oracle, frozen stimuli and public-port QA.

No author model, testbench or expected-value computation is imported.
"""
from __future__ import annotations
import argparse, hashlib, itertools, json, os, re, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

EP="competition/deepeye/evidence/control3d/first-capture-deadline-20261021/main"
RTL="competition/deepeye/fpga/control3d/deepeye_first_capture_deadline.sv"
OLD=["competition/deepeye/fpga/control3d/"+n for n in (
    "deepeye_atomic_pwm.sv","deepeye_pwm_coherent_capture.sv","deepeye_pwm_applied_capture.sv")]
SHA=lambda b:hashlib.sha256(b).hexdigest()
def save(p:Path,x):
    with p.open("x",encoding="utf-8",newline="\n") as f:json.dump(x,f,indent=2)
def raw(p:Path,b:bytes):
    with p.open("xb") as f:f.write(b)

def absolute_oracle(rows):
    """Deadline is an absolute input-row index, not a DUT-style countdown."""
    state=0;deadline=None;out=[]
    for edge,(_,mask,budget) in enumerate(rows):
        rst,cancel,start,observed=[bool(mask&(1<<i)) for i in range(4)]
        event=0
        if rst or cancel:state=0;deadline=None
        elif start:
            if state==1 or budget==0:state=8;deadline=None;event=128
            else:state=1;deadline=edge+budget;event=16
        elif state==1:
            if observed:state=2;deadline=None;event=32
            elif edge==deadline:state=4;deadline=None;event=64
            else:assert deadline is not None and edge<deadline
        out.append(state|event)
    return out

STANDALONE_TB=r"""
module tb_main_deadline;
parameter integer BUDGET_W=5;
logic clk=0,rst=1,cancel=0,start=0,observed=0;
logic [BUDGET_W-1:0] budget_cycles=0;
wire waiting,completed,expired,invalid_request;
wire started_event,completed_event,expired_event,invalid_request_event;
wire [7:0] flags={invalid_request_event,expired_event,completed_event,started_event,
                 invalid_request,expired,completed,waiting};
deepeye_first_capture_deadline #(.BUDGET_W(BUDGET_W)) dut(.*);
always #5 clk=~clk;
integer fd,scan,idx,mask,budget,count=0;reg[4095:0] filename;
initial begin
 if(!$value$plusargs("VECTORS=%s",filename)) $fatal(1,"MAIN_NO_INPUT");
 fd=$fopen(filename,"r");if(!fd)$fatal(1,"MAIN_OPEN_FAILED");
 while(!$feof(fd))begin
  scan=$fscanf(fd,"%d %h %h\n",idx,mask,budget);
  if(scan!=3)$fatal(1,"MAIN_BAD_INPUT");
  @(negedge clk);{observed,start,cancel,rst}=mask[3:0];budget_cycles=budget;
  @(posedge clk);#1;
  $display("MAIN_ROW %0d %0h %0h %02h",idx,mask,budget,flags);count=count+1;
 end
 $fclose(fd);$display("MAIN_DONE rows=%0d",count);$finish;
end
endmodule
"""

INTEGRATION_TB=r"""
module tb_main_composition;
logic clk=0,rst=1,stop=0,cfg_valid=0,out_ready=0;
logic [3:0] cfg_period=2,cfg_high_yaw=1,cfg_high_pitch=1,cfg_high_speed=1,cfg_tag=3;
logic [2:0] sample_levels=0;
wire cfg_ready,accepted,rejected,applied,frame_start,running,pending;
wire [2:0] pwm;
wire [3:0] active_period,active_high_yaw,active_high_pitch,active_high_speed,active_tag;
wire window_active,window_started,capture_armed,out_valid;
wire [3:0] out_period,out_high0,out_high1,out_high2,out_tag;
wire [7:0] out_start,out_end;
wire [3:0] expected_period,expected_high0,expected_high1,expected_high2,expected_tag;
wire [3:0] raw_fault_events;
wire failure_event;wire[2:0] failure_code;
deepeye_pwm_applied_capture #(.COUNT_W(4),.WITNESS_W(8),.TAG_W(4)) source_dut(.*);
wire start=window_started;
wire observed=out_valid;
wire cancel=stop || (cfg_valid && cfg_ready) || pending || !running ||
            !window_active || failure_event || (|raw_fault_events);
logic [5:0] budget_cycles=0;
wire waiting,completed,expired,invalid_request;
wire started_event,completed_event,expired_event,invalid_request_event;
wire[7:0] flags={invalid_request_event,expired_event,completed_event,started_event,
                invalid_request,expired,completed,waiting};
deepeye_first_capture_deadline #(.BUDGET_W(6)) monitor(.*);
always #5 clk=~clk;
integer fd,scan,idx,mask,budget,levels,ready,count=0;
integer pre_start,pre_obs,pre_cancel,pre_fault,pre_valid,pre_wa,pre_pending,pre_running;
reg[4095:0] filename;
initial begin
 if(!$value$plusargs("VECTORS=%s",filename))$fatal(1,"MAIN_NO_INPUT");
 fd=$fopen(filename,"r");if(!fd)$fatal(1,"MAIN_OPEN_FAILED");
 while(!$feof(fd))begin
  scan=$fscanf(fd,"%d %h %h %h %h\n",idx,mask,budget,levels,ready);
  if(scan!=5)$fatal(1,"MAIN_BAD_INPUT");
  @(negedge clk);rst=mask[0];stop=mask[1];cfg_valid=mask[2];
  budget_cycles=budget;sample_levels=levels;out_ready=ready;
  #1;pre_start=start;pre_obs=observed;pre_cancel=cancel;
  pre_fault=raw_fault_events;pre_valid=out_valid;pre_wa=window_active;
  pre_pending=pending;pre_running=running;
  @(posedge clk);#1;
  $display("COMP_ROW %0d %0h %0h %0h %0h %0d %0d %0d %0h %0d %0d %0d %0d %02h %0d %0d %0h %0d %0d %0h %0h %0h %0h",
   idx,mask,budget,levels,ready,pre_start,pre_obs,pre_cancel,pre_fault,pre_valid,
   pre_wa,pre_pending,pre_running,flags,out_valid,window_active,raw_fault_events,
   failure_event,window_started,out_period,out_high0,out_high1,out_high2);
  count=count+1;
 end
 $fclose(fd);$display("COMP_DONE rows=%0d",count);$finish;
end
endmodule
"""

def freeze(root:Path):
    dest=root/EP/"frozen";dest.mkdir(exist_ok=False)
    allmeta={}
    for width in (1,2,3,4,5,32):
        rows=[];scenarios=[]
        def add(name,seq):
            begin=len(rows)
            rows.append((len(rows),1,0))
            for mask,b in seq:rows.append((len(rows),mask,b))
            rows.extend([(len(rows),0,0),(len(rows)+1,1,0)])
            scenarios.append({"name":name,"begin":begin,"end":len(rows)})
        budgets=range(1,1<<width) if width<32 else [1,2,31,0x7fffffff,0xffffffff]
        for budget in budgets:
            horizon=budget+2 if width<32 else min(budget+2,35)
            positions=range(1,budget+2) if width<32 else sorted({1,min(budget,20),min(budget+1,25)})
            for pos in [None,*positions]:
                add(f"observe-N{budget}-at{pos}",[(4,budget)]+[(8 if e==pos else 0,((e*3)^budget)&((1<<width)-1)) for e in range(1,horizon+1)])
            for event,flag in (("cancel",2),("reset",1),("restart",4)):
                for pos in positions:
                    for concurrent in (0,8):
                        add(f"{event}-N{budget}-at{pos}-obs{bool(concurrent)}",
                            [(4,budget)]+[(flag|concurrent if e==pos else 0,0 if e==pos else budget) for e in range(1,horizon+1)])
            add(f"held-start-N{budget}",[(4,budget)]*6+[(4,0)]*3+[(0,0)]*2)
        # Every priority combination in IDLE, WAIT-deadline, COMPLETE, EXPIRED, INVALID.
        prefixes={"idle":[],"wait":[(4,1)],"complete":[(4,1),(8,0)],
                  "expired":[(4,1),(0,0)],"invalid":[(4,0)]}
        for name,prefix in prefixes.items():
            for mask in range(16):
                for budget in (0,1,(1<<width)-1):
                    add(f"priority-{name}-{mask}-{budget}",prefix+[(mask,budget),(8,0),(0,0)])
        values=absolute_oracle(rows)
        raw(dest/f"standalone-w{width}.txt","".join(f"{i} {m:x} {b:x}\n" for i,m,b in rows).encode())
        raw(dest/f"expected-w{width}.txt","".join(f"{i} {v:02x}\n" for i,v in enumerate(values)).encode())
        save(dest/f"scenarios-w{width}.json",scenarios)
        allmeta[str(width)]={"rows":len(rows),"scenarios":len(scenarios),"budgets":list(budgets)}
    # Literal composed schedules are specified without importing B15 model/source helpers.
    comp=[];cases=[]
    for name,budget in (("N3-good",3),("N2-late",2),("quiet",7),("backpressure",3),
                        ("raw-fault",3),("stop",7),("new-request",7)):
        begin=len(comp)
        for edge in range(16):
            mask=1 if edge==0 else 4 if edge==1 else 0
            level=0 if edge<4 or name=="quiet" else (7 if edge%2==0 else 0)
            ready=0 if name=="backpressure" else 1
            if name=="raw-fault":
                if edge==7:level=6;ready=0
                if edge==8:level=7;ready=1
            if name=="stop" and edge==6:mask|=2
            if name=="new-request" and edge==6:mask|=4
            comp.append((len(comp),mask,budget,level,ready))
        cases.append({"name":name,"begin":begin,"rows":16,"budget":budget})
    raw(dest/"composition.txt","".join(f"{i} {m:x} {b:x} {l:x} {r:x}\n" for i,m,b,l,r in comp).encode())
    literal={"N3-good":{"start_at":4,"slot_after":6,"first_observed_at":7,"monitor_complete_at":7},
             "N2-late":{"start_at":4,"slot_after":6,"monitor_expired_at":6,"not_revived_at":7},
             "quiet":{"start_at":4,"monitor_expired_at":11,"old_out_valid_always":0},
             "raw-fault":{"pre_handshake_at":8,"post_fault_at":8,"cancel_terminal_at":9},
             "backpressure":{"complete_at":7,"post_fault_at":8,"cancel_terminal_at":9},
             "stop":{"cancel_at":6},"new-request":{"cancel_at":6}}
    save(dest/"composition-cases.json",cases);save(dest/"composition-literal-expectations.json",literal)
    raw(dest/"tb_main_deadline.sv",STANDALONE_TB.encode())
    raw(dest/"tb_main_composition.sv",INTEGRATION_TB.encode())
    save(dest/"FREEZE.json",{"at_utc":datetime.now(timezone.utc).isoformat(),"oracle":"absolute edge index",
         "oracle_source_sha256":SHA(Path(__file__).read_bytes()),"standalone":allmeta,
         "composition_cases":len(cases),"composition_rows":len(comp),
         "files":{p.name:SHA(p.read_bytes()) for p in sorted(dest.iterdir()) if p.is_file()},
         "pre_author":True,"author_implementation_read":False,"large32bit":"bounded prefix only"})
    print(json.dumps({"frozen":str(dest),"standalone":allmeta,"composition_rows":len(comp)}))

def command(argv,cwd,out,name,records,timeout=90):
    started=datetime.now(timezone.utc).isoformat();timed=False
    try:
        p=subprocess.run([str(x) for x in argv],cwd=cwd,capture_output=True,timeout=timeout,
                         creationflags=0x08000000 if os.name=="nt" else 0)
        stdout,stderr,code=p.stdout,p.stderr,p.returncode
    except subprocess.TimeoutExpired as e:
        stdout,stderr,code=e.stdout or b"",e.stderr or b"",None;timed=True
    raw(out/(name+".stdout.txt"),stdout);raw(out/(name+".stderr.txt"),stderr)
    r={"name":name,"argv":[str(x) for x in argv],"cwd":str(cwd),"started_utc":started,
       "ended_utc":datetime.now(timezone.utc).isoformat(),"exit_code":code,"timeout":timed,
       "stdout_sha256":SHA(stdout),"stderr_sha256":SHA(stderr)}
    records.append(r);save(out/(name+".command.json"),r)
    assert code==0 and not timed,r
    return stdout.decode("utf-8",errors="replace")

def verify_standalone(log,vectors,expected):
    actual=[]
    for line in log.splitlines():
        line=line[2:] if line.startswith("# ") else line
        if line.startswith("MAIN_ROW "):
            m=re.fullmatch(r"MAIN_ROW (\d+) ([0-9a-f]+) ([0-9a-f]+) ([0-9a-f]{2})",line)
            assert m,("malformed_or_X",line)
            actual.append(tuple(int(v,10 if i==0 else 16) for i,v in enumerate(m.groups())))
    inputs=[tuple(int(v,10 if i==0 else 16) for i,v in enumerate(line.split())) for line in vectors.read_text().splitlines()]
    desired=[int(line.split()[1],16) for line in expected.read_text().splitlines()]
    assert len(actual)==len(inputs)==len(desired)
    mismatch=[{"row":i,"actual":x,"expected":(*inputs[i],desired[i])} for i,x in enumerate(actual) if x!=(*inputs[i],desired[i])]
    ends=[l.removeprefix("# ") for l in log.splitlines() if l.removeprefix("# ").startswith("MAIN_DONE")]
    assert ends==[f"MAIN_DONE rows={len(inputs)}"]
    assert not re.search(r"\*\*\s+(?:Fatal|Error):|MAIN_BAD_|MAIN_NO_|MAIN_OPEN_",log)
    return {"rows":len(inputs),"mismatches":len(mismatch),"first_mismatches":mismatch[:12]}

def verify_composition(log,frozen):
    actual=[]
    for line in log.splitlines():
        line=line.removeprefix("# ")
        if line.startswith("COMP_ROW "):
            fields=line.split()[1:];assert len(fields)==23,(len(fields),line)
            hexpos={1,2,3,4,8,13,16,19,20,21,22}
            actual.append(tuple(int(v,16 if i in hexpos else 10) for i,v in enumerate(fields)))
    inputs=[tuple(int(v,10 if i==0 else 16) for i,v in enumerate(l.split())) for l in (frozen/"composition.txt").read_text().splitlines()]
    assert len(actual)==len(inputs)
    assert [a[:5] for a in actual]==inputs
    rows=[(a[0],(a[1]&1)|(a[7]<<1)|(a[5]<<2)|(a[6]<<3),a[2]) for a in actual]
    expected=absolute_oracle(rows)
    mismatch=[{"row":i,"flags":a[13],"expected":expected[i]} for i,a in enumerate(actual) if a[13]!=expected[i]]
    cases=json.loads((frozen/"composition-cases.json").read_bytes())
    byname={c["name"]:actual[c["begin"]:c["begin"]+c["rows"]] for c in cases}
    g=byname["N3-good"];n=byname["N2-late"];q=byname["quiet"]
    assert g[4][5:8]==(1,0,0) and g[6][6]==0 and g[6][14]==1
    assert g[7][6]==1 and g[7][13]==0x22
    assert n[6][13]==0x44 and n[7][13]==4
    assert q[11][13]==0x44 and all(x[14]==0 for x in q)
    for name in ("raw-fault","backpressure"):
        x=byname[name];assert x[8][16]!=0 and x[9][7]==1 and x[9][13]==0
    assert byname["raw-fault"][8][9]==1 and byname["raw-fault"][8][4]==1
    assert byname["stop"][6][7]==1 and byname["new-request"][6][7]==1
    ends=[l.removeprefix("# ") for l in log.splitlines() if l.removeprefix("# ").startswith("COMP_DONE")]
    assert ends==[f"COMP_DONE rows={len(inputs)}"]
    assert not re.search(r"\*\*\s+(?:Fatal|Error):|MAIN_BAD_|MAIN_NO_|MAIN_OPEN_",log)
    return {"rows":len(actual),"mismatches":len(mismatch),"first_mismatches":mismatch[:12],
            "literal_P2H1_N3_complete_N2_expire":True,"pre_handshake_post_fault":True}

def run(root:Path,out:Path,source:Path|None):
    out.mkdir(parents=True,exist_ok=False);frozen=root/EP/"frozen"
    f=json.loads((frozen/"FREEZE.json").read_bytes())
    for name,h in f["files"].items():assert SHA((frozen/name).read_bytes())==h
    selected=source or root/RTL
    sources=[selected,*[root/p for p in OLD],frozen/"tb_main_deadline.sv",frozen/"tb_main_composition.sv"]
    snapshot=out/"sources";snapshot.mkdir()
    for path in sources:raw(snapshot/path.name,path.read_bytes())
    save(out/"INPUTS.json",{str(p):{"sha256":SHA(p.read_bytes()),"bytes":p.stat().st_size} for p in sources})
    records=[];tools=Path("D:/modelsim1/win64")
    results={}
    try:
        command([tools/"vlib.exe","lib"],out,out,"vlib",records)
        c=command([tools/"vlog.exe","-sv","-work","lib",*[snapshot/p.name for p in sources]],out,out,"vlog",records)
        assert re.search(r"Errors:\s*0",c)
        for width in (1,2,3,4,5,32):
            name=f"standalone-w{width}"
            log=command([tools/"vsim.exe","-c","-work","lib","-l",out/(name+".transcript"),"-wlf",out/(name+".wlf"),
              "-do","run -all; quit -f",f"-gBUDGET_W={width}","tb_main_deadline",
              "+VECTORS="+str(frozen/(name+".txt"))],out,out,name,records)
            results[name]=verify_standalone(log,frozen/(name+".txt"),frozen/f"expected-w{width}.txt")
            assert results[name]["mismatches"]==0,results[name]
        log=command([tools/"vsim.exe","-c","-work","lib","-l",out/"composition.transcript","-wlf",out/"composition.wlf",
             "-do","run -all; quit -f","tb_main_composition","+VECTORS="+str(frozen/"composition.txt")],out,out,"composition",records)
        results["composition"]=verify_composition(log,frozen)
        assert results["composition"]["mismatches"]==0
        status="PASS"
    except Exception as e:
        status="FAIL";results["error"]=repr(e);raise
    finally:
        save(out/"RESULT.json",{"status":status,"source_sha256":SHA(selected.read_bytes()),"results":results,
                               "new_board_commands":0,"synthesis":"not_run","large32bit":"bounded prefix"})
        save(out/"COMMANDS.json",records)
    print(json.dumps({"status":status,"results":results}))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True)
    p.add_argument("--freeze",action="store_true");p.add_argument("--out",type=Path);p.add_argument("--source",type=Path)
    args=p.parse_args()
    if args.freeze:freeze(args.root.resolve())
    else:
        assert args.out
        run(args.root.resolve(),args.out.resolve(),args.source.resolve() if args.source else None)
