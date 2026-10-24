#!/usr/bin/env python3
"""Bounded candidate49 ModelSim validation and strict saved-file qualification."""
from __future__ import annotations
import argparse
import binascii
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

P=Path(__file__).resolve().parents[2]
AUTHOR=P/"evidence/codec/trace-uart-candidate-20261024-49/author"
TOOLS=Path("D:/modelsim1/win64")
PINS={
 "fpga/codec/deepeye_trace_frame_candidate.sv":"ceff0930c2403eabe73bdd8a8cfe7bbb868ca33029d026a6a240c8d50a06a5cc",
 "fpga/codec/deepeye_trace_payload_timing_candidate.sv":"0d5ba11fe199708f8376c718bbf3484431adc8dd6e847666451b1b5e873cec7b",
 "fpga/codec/deepeye_block_encoder.sv":"4cb79428ef89096742e293516c4696caf985048d8185f531fe92eaa485c8d532",
 "fpga/transport/deepeye_wire_serializer.sv":"efc6082f6f5dff215b100f718b12d87d4c6467db7b968a24f846802dc6a19885",
 "fpga/transport/deepeye_crc16_byte.sv":"8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f",
 "fpga/transport/deepeye_uart_tx.sv":"5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47",
}
NEW=["fpga/codec/deepeye_trace_uart_candidate.sv","tests/rtl/codec/tb_trace_uart_candidate.sv",
     "tools/codec/run_trace_uart_candidate.py","fpga/codec/trace_uart_candidate.md"]
GOLD=P/"evidence/codec/trace-frame-candidate-20261024-45/author/attempt-01/baseline/cases.json"
GOLD_SHA="7039fe705269648975e4f9fdb5603d59c7acf2b13f0a66adfe6646baac9a9852"
PROTECTED=P.parents[1]/"handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json"
PROTECTED_SHA="6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8"
N=r"(?:0|[1-9][0-9]*)"
TFIELDS="id vector action kind started ended cfg samples starts bytes results aborted error nframe".split()
SFIELDS="cycles checks cases cfg samples starts bytes results aborts".split()
def labels(prefix,fields):return re.compile("# "+prefix+" "+" ".join(k+"=("+N+")" for k in fields))
TR=labels("TU49_TRACE",TFIELDS)
ST=labels("TU49_STATS",SFIELDS)
ROW=re.compile("("+N+r") ([0-9a-fxXzZ]{7}) ([0-9a-f]{7})")

def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for data in iter(lambda:f.read(1048576),b""):h.update(data)
    return h.hexdigest()
def save(p,obj):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
def load(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def need(ok,why):
    if not ok:raise ValueError(why)
def cat(values):
    value=0
    for v,width in values:
        need(0<=v<1<<width,"fixture width")
        value=(value<<width)|v
    return value

def vectors():
    need(sha(GOLD)==GOLD_SHA,"immutable reused payload fixture differs")
    original=load(GOLD)
    selected=[0,1,2,3,4,5,6,7,8,10,11,12,13,14,144,153,154,155,156]
    result=[]
    for index in selected:
        source=original[index];c=source["cfg"];payload=bytes.fromhex(source["payload_hex"])
        fields=[(c[k],w) for k,w in (("count",8),("e",4),("session",32),("channel",2),
                ("first_index",32),("first_tick",64),("index_stride",16),("tick_stride",16),
                ("valid_sample",1),("saturated",1),("held",1),("source_fault",1),("source_tick",64),("epoch",8),("seq",16))]
        frame=b""
        if source["error"]==0:
            header=bytes([0xa5,0x5a,3,7,len(payload),c["epoch"]])+c["seq"].to_bytes(2,"little")+(c["first_tick"]&0xffffffff).to_bytes(4,"little")
            covered=header[2:]+payload
            crc=binascii.crc_hqx(covered,0xffff)
            frame=header+payload+crc.to_bytes(2,"little")
            need(frame.hex()==source["frame_hex"],"independently framed CRC differs from immutable reference")
        result.append(dict(name=source["name"],source_index=index,cfg=c,cfg_hex=f"{cat(fields):067x}",
                           samples=source["samples"],last_mode=source["last_mode"],error=source["error"],
                           reused_payload_hex=payload.hex(),frame_hex=frame.hex()))
    return result

def plans(full,default=False):
    if default:return [[0,0,0,0,0,0]]
    rows=[[v,0,0,0,0,0] for v in range(19)]+[[2,1,0,0,0,10]]
    for kind in (1,2):
        for which in ((0,1) if full else (0,)):
            for phase in range(10):
                rows.extend([[8,2,kind,which,phase,0],[0,0,0,0,0,0]])
        for action in (3,4,5,6):
            rows.extend([[8,action,kind,0,0,0],[0,0,0,0,0,0]])
    return rows

def fixture(folder,clock,baud,full=False,default=False):
    folder.mkdir()
    data=dict(clock=clock,baud=baud,vectors=vectors(),plan=plans(full,default),
              reuse=dict(path=str(GOLD),sha256=GOLD_SHA,selected=19,total_original=157,
                         coverage="Payload goldens reused only. Complete frame header/CRC and UART bit deadlines computed independently; not new codec proof."))
    save(folder/"fixture.json",data)
    rows=[f"{len(data['vectors'])} {len(data['plan'])}"]
    for v in data["vectors"]:
        rows.append(f"{v['cfg_hex']} {len(v['samples'])} {v['error']} {len(v['frame_hex'])//2} {v['last_mode']}")
        rows.extend(f"{x:04x}" for x in v["samples"])
        rows.extend(f"{x:02x}" for x in bytes.fromhex(v["frame_hex"]))
    rows.extend(" ".join(map(str,p)) for p in data["plan"])
    (folder/"fixture.txt").write_text("\n".join(rows)+"\n",encoding="ascii",newline="\n")
    return data

def bits(word):
    return dict(tx=word&1,ub=(word>>1)&1,busy=(word>>2)&1,cr=(word>>3)&1,sr=(word>>4)&1,
                rv=(word>>5)&1,rr=(word>>6)&1,rst=(word>>7)&1,cancel=(word>>8)&1,
                cv=(word>>9)&1,sv=(word>>10)&1,sl=(word>>11)&1,fault=(word>>12)&15,
                error=(word>>16)&7,nbytes=(word>>19)&63)

def check_trace(lines,fixture_data):
    clock,baud=fixture_data["clock"],fixture_data["baud"]
    operations={0:Counter()};decoded={};active=None;last_post=None;last_case=0
    totals=Counter(cases=len(fixture_data["plan"]));coverage=Counter()
    for cycle,line in enumerate(lines,1):
        need(line.endswith("\n"),"unterminated raw trace")
        match=ROW.fullmatch(line[:-1].removesuffix("\r"))
        need(match is not None,f"trace grammar row{cycle}")
        cid=int(match[1]);need(0<=cid<=len(fixture_data["plan"]),"trace operation bound")
        if cid!=last_case:
            need(cid==last_case+1 and active is None,"missing/reordered operation or stale UART")
            operations[cid]=Counter();decoded[cid]=[]
            last_case=cid
        count=operations[cid]
        count.setdefault("started",cycle);count["ended"]=cycle
        if cid:
            plan=fixture_data["plan"][cid-1];v=fixture_data["vectors"][plan[0]]
        else:
            plan=[0,0,0,0,0,0];v=dict(error=0,frame_hex="",samples=[])
        frame=bytes.fromhex(v["frame_hex"])
        unknown=bool(re.search("[xXzZ]",match[2]))
        need(not unknown or (cycle==1 and cid==0),"unknown raw trace after initial PRE")
        pre=bits(int(match[2],16)) if not unknown else bits(192)
        post=bits(int(match[3],16))
        need(int(match[3],16)<1<<25,"trace output width")
        if not unknown:
            need(int(match[2],16)<1<<25,"trace input width")
            if last_post is not None:
                need((pre["tx"],pre["ub"])==(last_post["tx"],last_post["ub"]),"TX/uart_busy changed without edge")
        for key in ("rr","rst","cancel","cv","sv","sl"):
            need(pre[key]==post[key],"input changed within edge")
        abort=bool(pre["rst"] or pre["cancel"])
        def endpoint(p,phase):
            need(p["fault"]==0,"unexpected reachable wire fault")
            if p["rst"] or p["cancel"]:need(not(p["cr"] or p["sr"] or p["rv"]),"immediate masks")
            if p["ub"]:need(p["busy"] and not(p["cr"] or p["rv"]),"UART busy gating")
            if p["rv"]:
                need(not(p["ub"] or p["cr"]),"report/config UART boundary")
                need(p["error"]==v["error"] and p["nbytes"]==(len(frame) if not v["error"] else 0),"result tuple")
                need(count["bytes"]==len(frame) and active is None,"early report before physical stop")
                if v["error"]:need(count["starts"]==0,"error emitted bytes")
            if cid and count["cfg"]>count["results"] and not count["aborted"] and not abort:
                need(not p["cr"] and p["busy"],"pending transaction/config gate")
        if not unknown:endpoint(pre,"PRE")
        for key,value in (("cfg",pre["cv"] and pre["cr"]),("samples",pre["sv"] and pre["sr"]),("results",pre["rv"] and pre["rr"])):
            count[key]+=int(value);totals[key]+=int(value)
        if abort:
            need(post["tx"]==1 and post["ub"]==0,"synchronous abort TX/idle")
            if cid:
                need((pre["rst"],pre["cancel"])==((1,0) if plan[2]==1 else (0,1)),"abort kind/fixture")
                count["aborted"]+=1;totals["aborts"]+=1
                need(count["aborted"]==1 and plan[1]>=2,"unplanned/multiple abort")
                if plan[1]==2:
                    need(active is not None,"phase abort without active UART")
                    admit,bidx,value=active
                    phase=((cycle-1-admit)*baud)//clock
                    target=0 if plan[3]==0 else len(frame)-1
                    need(bidx==target and phase==plan[4],"abort phase/byte fixture")
                    coverage[f"abort_kind{plan[2]}_which{plan[3]}_phase{phase}"]+=1
                elif plan[1]==3:need(count["cfg"]==count["starts"]==0,"configuration abort admitted work")
                elif plan[1]==4:need(count["samples"]>=1 and count["starts"]==0,"sample abort point")
                elif plan[1]==5:need(count["samples"]==len(v["samples"]) and count["starts"]==0,"prefeed abort point")
                elif plan[1]==6:
                    need(last_post and last_post["rv"] and count["bytes"]==len(frame),"report abort without complete emitted frame")
                    coverage["complete_frame_emitted_before_local_abort"]+=1
            active=None
        elif not pre["ub"] and post["ub"]:
            need(cid and v["error"]==0 and count["starts"]<len(frame),"unexpected UART start")
            need(active is None and post["tx"]==0,"start bit/admission")
            active=(cycle,count["starts"],0);count["starts"]+=1;totals["starts"]+=1
        elif pre["ub"]:
            need(active is not None,"busy without observed public admission")
            admit,bidx,value=active;age=cycle-admit;end=(10*clock+baud-1)//baud
            if age==end:
                need(not post["ub"] and post["tx"]==1 and value==frame[bidx],"stop interval/decoded byte")
                count["bytes"]+=1;totals["bytes"]+=1;decoded.setdefault(cid,[]).append(value);active=None
            else:
                need(0<age<end and post["ub"],"UART duration")
                phase=(age*baud)//clock
                wanted=0 if phase==0 else 1 if phase==9 else (frame[bidx]>>(phase-1))&1
                need(post["tx"]==wanted,"analytical UART bit deadline/value")
                if 1<=phase<=8 and age==(phase*clock+baud-1)//baud:
                    value=(value&~(1<<(phase-1)))|(post["tx"]<<(phase-1))
                active=(admit,bidx,value)
        else:need(post["tx"]==1,"idle TX")
        endpoint(post,"POST")
        if pre["rv"] and not pre["rr"] and not abort:
            need(post["rv"] and (post["error"],post["nbytes"])==(pre["error"],pre["nbytes"]),"stalled result stability")
        if last_post and (last_post["rst"] or last_post["cancel"]) and not abort:
            need(pre["cr"]==0,"42 CLEAR recovery barrier")
        last_post=post;totals["cycles"]=cycle;totals["checks"]+=2
    need(active is None and last_case==len(fixture_data["plan"]),"trace not complete/drained")
    need(operations[0]["started"]==1 and operations[0]["ended"]==5,"bootstrap trace coverage")
    rows=[]
    for cid,plan in enumerate(fixture_data["plan"],1):
        c=operations[cid];v=fixture_data["vectors"][plan[0]];n=len(v["frame_hex"])//2
        need(c["cfg"]==(0 if plan[1]==3 else 1),"configuration count")
        need(c["results"]==(0 if plan[1]>=2 else 1),"cancelled/normal result count")
        need(c["aborted"]==int(plan[1]>=2),"abort coverage")
        if plan[1]<2:need(c["bytes"]==n and c["starts"]==n,"normal complete UART bytes")
        row=dict(id=cid,vector=plan[0],action=plan[1],kind=plan[2],started=c["started"],ended=c["ended"],
                 cfg=c["cfg"],samples=c["samples"],starts=c["starts"],bytes=c["bytes"],results=c["results"],
                 aborted=c["aborted"],error=v["error"],nframe=n)
        rows.append(row)
    return dict(stats={k:totals[k] for k in SFIELDS},operations=rows,coverage=dict(coverage),
                decoded={str(k):bytes(v).hex() for k,v in decoded.items()})

def clean_lines(text):
    need(not re.search(r"[\x00-\x09\x0b\x0c\x0e-\x1f\x7f]",text),"control byte")
    need(not re.search(r"\r(?!\n)",text),"bare CR")
    lines=text.replace("\r\n","\n").split("\n")
    if lines[-1]=="":lines.pop()
    return lines

def parse_log(text,data,observed,tb_path,finish_line):
    lines=clean_lines(text)
    tokens=[(i,l) for i,l in enumerate(lines) if "TU49_" in l]
    need(len(tokens)==len(data["plan"])+3,"complete unique marker count")
    begin=f"# TU49_BEGIN clock={data['clock']} baud={data['baud']} vectors={len(data['vectors'])} plans={len(data['plan'])}"
    need(tokens[0][1]==begin and tokens[-1][1]=="# TU49_DONE PASS","exact BEGIN/DONE")
    for (at,line),expected in zip(tokens[1:-2],observed["operations"]):
        m=TR.fullmatch(line);need(m is not None,"exact anchored TRACE labels/order")
        need(dict(zip(TFIELDS,map(int,m.groups())))==expected,"TRACE numeric equality with public trace/fixture")
    at,line=tokens[-2]
    m=ST.fullmatch(line);need(m is not None,"exact anchored statistics grammar")
    need(dict(zip(SFIELDS,map(int,m.groups())))==observed["stats"],"statistics numeric equality with trace")
    need(tokens[-1][0]==at+1 and len(lines)==at+6,"exact terminal ordering/footer")
    start_rows=[i for i,l in enumerate(lines) if "Start time:" in l]
    need(len(start_rows)==1 and start_rows[0]<tokens[0][0],"unique anchored prefix Start time")
    reserved={"Start time:":start_rows[0],"$finish":at+2,"Time:":at+3,"Iteration:":at+3,"Instance:":at+3,
              "End time:":at+4,"Elapsed time:":at+4,"Errors:":at+5,"Warnings:":at+5}
    for token,wanted in reserved.items():
        found=[i for i,l in enumerate(lines) for _ in range(l.count(token))]
        need(found==[wanted],"unique provenance token "+token)
    need(all(not re.search(r"\*\* (Error|Fatal|Warning)",l) for l in lines),"vendor error/warning")
    note=re.fullmatch(r"# \*\* Note: \$finish\s+: (.+)\(([1-9][0-9]*)\)",lines[at+2])
    norm=lambda p:str(p).replace("\\","/").casefold()
    need(note and norm(note[1])==norm(tb_path) and int(note[2])==finish_line,"actual finish file/line")
    need(lines[at+3]==f"#    Time: {observed['stats']['cycles']*10} ns  Iteration: 1  Instance: /tb_trace_uart_candidate","actual finish time/instance")
    stamp=r"([0-9]{2}:[0-9]{2}:[0-9]{2} on [A-Z][a-z]{2} [ 0-9][0-9],[0-9]{4})"
    start=re.fullmatch("# Start time: "+stamp,lines[start_rows[0]])
    end=re.fullmatch("# End time: "+stamp+r", Elapsed time: ([0-9]+):([0-5][0-9]):([0-5][0-9])",lines[at+4])
    need(start and end,"start/end grammar")
    delta=datetime.strptime(end[1],"%H:%M:%S on %b %d,%Y")-datetime.strptime(start[1],"%H:%M:%S on %b %d,%Y")
    need(delta.total_seconds()==int(end[2])*3600+int(end[3])*60+int(end[4]),"elapsed consistency")
    need(lines[-1]=="# Errors: 0, Warnings: 0","clean vendor footer")
    return True

def qualify(folder,base,data,observed,tb,finish):
    folder.mkdir();lines=clean_lines(base);at=next(i for i,l in enumerate(lines) if l.startswith("# TU49_STATS"))
    begin=next(i for i,l in enumerate(lines) if l.startswith("# TU49_BEGIN"));trace=begin+1
    trace=next(i for i,l in enumerate(lines) if l.startswith("# TU49_TRACE"))
    start=next(i for i,l in enumerate(lines) if l.startswith("# Start time:"))
    recipes=[]
    def add(name,op,index=None,value=None):
        recipes.append(dict(name=name,op=op,index=index,value=value,expected_accept=False))
    for name,index in (("BEGIN",begin),("TRACE",trace),("STATS",at),("DONE",at+1)):
        add(name+"_duplicate","insert",index,lines[index])
        add(name+"_unprefixed","replace",index,lines[index].removeprefix("# "))
        add(name+"_prefixed_substring","insert",begin,"noise"+lines[index]+"noise")
        add(name+"_unprefixed_substring","insert",begin,"noise"+lines[index].removeprefix("# ")+"noise")
        add(name+"_missing","delete",index)
    for token,index in (("$finish",at+2),("Time:",at+3),("Iteration:",at+3),("Instance:",at+3),
                         ("End time:",at+4),("Elapsed time:",at+4),("Errors:",at+5),("Warnings:",at+5),("Start time:",start)):
        for where,pos in (("prepend",0),("interleave",at),("append",len(lines))):
            add(token+where,"insert",pos,lines[index])
        add(token+"substring","insert",0,"fragment<"+token+">")
        add(token+"conflict","insert",0,lines[index].replace(token,token+"BAD",1))
        add(token+"leading","replace",index,"prefix "+lines[index])
        add(token+"trailing","replace",index,lines[index]+" suffix")
        add(token+"inline_duplicate","replace",index,lines[index]+" "+token)
    for field in SFIELDS:
        changed=re.sub(r"\b"+field+r"=(\d+)",lambda m:field+"="+str(int(m[1])+1),lines[at])
        add("counter_"+field,"replace",at,changed)
    add("conflicting_trace_number","replace",trace,re.sub(r"\bbytes=(\d+)",lambda m:"bytes="+str(int(m[1])+1),lines[trace]))
    add("NUL","replace",at,lines[at]+"\x00")
    add("bare_CR","replace",at,lines[at]+"\rfragment")
    add("truncated","truncate",at+3)
    add("unknown_footer","insert",len(lines),"# stray footer")
    frozen=[]
    for r in recipes:
        altered=lines.copy();op=r["op"];ix=r["index"]
        if op=="insert":altered.insert(ix,r["value"])
        elif op=="replace":altered[ix]=r["value"]
        elif op=="delete":del altered[ix]
        else:altered=altered[:ix]
        raw=("\n".join(altered)+"\n").encode("utf-8")
        frozen.append(dict(**r,mutated_sha256=hashlib.sha256(raw).hexdigest()))
    save(folder/"FROZEN_NEGATIVES.json",dict(base_sha256=hashlib.sha256(base.encode("utf-8")).hexdigest(),recipes=frozen,
                                           observation_sha256=hashlib.sha256(json.dumps(observed,sort_keys=True).encode()).hexdigest()))
    outcomes=[]
    for r in frozen:
        altered=lines.copy();ix=r["index"]
        if r["op"]=="insert":altered.insert(ix,r["value"])
        elif r["op"]=="replace":altered[ix]=r["value"]
        elif r["op"]=="delete":del altered[ix]
        else:altered=altered[:ix]
        changed="\n".join(altered)+"\n"
        need(hashlib.sha256(changed.encode()).hexdigest()==r["mutated_sha256"],"frozen mutation changed")
        try:parse_log(changed,data,observed,tb,finish)
        except ValueError as error:outcomes.append(dict(name=r["name"],rejected=True,error=str(error)))
        else:raise ValueError("false accept "+r["name"])
    lf="\n".join(lines)+"\n";crlf=lf.replace("\n","\r\n")
    parse_log(lf,data,observed,tb,finish);parse_log(crlf,data,observed,tb,finish)
    unicode_path=str(Path(tb).parent/"语法正例"/Path(tb).name).replace("\\","/")
    uni=lf.replace(str(tb).replace("\\","/"),unicode_path)
    need(uni!=lf,"UTF8 metadata probe did not replace finish path")
    parse_log(uni,data,observed,unicode_path,finish)
    save(folder/"RESULT.json",dict(negatives=len(outcomes),false_accepts=0,positives=3,outcomes=outcomes,
                                  portability="LF/CRLF and UTF8 saved-log path+metadata grammar only, not vendor Unicode execution."))
    return dict(negatives=len(outcomes),false_accepts=0,positives=3)

def parse_guard_log(text,expected,uart_path,guard_line):
    lines=clean_lines(text)
    fatal=f"# ** Fatal: deepeye_uart_tx: {expected} out of range"
    found=[i for i,line in enumerate(lines) if "** Fatal:" in line]
    need(len(found)==1,"unique actual DUT fatal")
    at=found[0];need(lines[at]==fatal and len(lines)==at+6,"exact DUT fatal/terminal grammar")
    block="clock_hz" if expected=="CLOCK_HZ" else "baud"
    scope="tb_trace_uart_candidate.dut.uart_stage.g_guard_"+block
    path=str(uart_path).replace("\\","/")
    need(lines[at+1]==f"#    Time: 0 ps  Scope: {scope} File: {path} Line: {guard_line}","actual guard source/scope/time")
    need(lines[at+2]==f"# ** Note: $finish    : {path}({guard_line})","actual DUT fatal finish")
    need(lines[at+3]==f"#    Time: 0 ps  Iteration: 0  Region: /"+scope.replace(".","/"),"actual guard region/time")
    start_rows=[i for i,l in enumerate(lines) if "Start time:" in l]
    need(len(start_rows)==1 and start_rows[0]<at,"guard prefix start")
    reserved={"Start time:":[start_rows[0]],"$finish":[at+2],"Time:":[at+1,at+3],
              "Scope:":[at+1],"File:":[at+1],"Line:":[at+1],"Iteration:":[at+3],"Region:":[at+3],
              "End time:":[at+4],"Elapsed time:":[at+4],"Errors:":[at+5],"Warnings:":[at+5]}
    for token,wanted in reserved.items():
        actual=[i for i,l in enumerate(lines) for _ in range(l.count(token))]
        need(actual==wanted,"unique exact guard provenance "+token)
    need(not any("TU49_" in l or re.search(r"\*\* (?:Error|Warning)",l) for l in lines),"guard harness/vendor conflict")
    stamp=r"([0-9]{2}:[0-9]{2}:[0-9]{2} on [A-Z][a-z]{2} [ 0-9][0-9],[0-9]{4})"
    start=re.fullmatch("# Start time: "+stamp,lines[start_rows[0]])
    end=re.fullmatch("# End time: "+stamp+r", Elapsed time: ([0-9]+):([0-5][0-9]):([0-5][0-9])",lines[at+4])
    need(start and end,"guard start/end grammar")
    delta=datetime.strptime(end[1],"%H:%M:%S on %b %d,%Y")-datetime.strptime(start[1],"%H:%M:%S on %b %d,%Y")
    need(delta.total_seconds()==int(end[2])*3600+int(end[3])*60+int(end[4]),"guard elapsed consistency")
    need(lines[-1]=="# Errors: 1, Warnings: 0","actual rejected-DUT guard footer")
    return True

def run_process(attempt,name,argv,cwd,timeout=300,allow_nonzero=False):
    directory=attempt/"processes";directory.mkdir(exist_ok=True)
    record=dict(argv=list(map(str,argv)),cwd=str(cwd),started_utc=datetime.now(timezone.utc).isoformat())
    before=time.monotonic()
    with (directory/(name+".stdout.bin")).open("wb") as out,(directory/(name+".stderr.bin")).open("wb") as err:
        proc=subprocess.Popen(record["argv"],cwd=cwd,stdout=out,stderr=err,shell=False)
        record["pid"]=proc.pid;save(directory/(name+".started.json"),record)
        try:record["exit_code"]=proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill();record["exit_code"]=proc.wait();record["timed_out"]=True
    record.update(ended_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-before)
    record["stdout"]=dict(path=str(directory/(name+".stdout.bin")),sha256=sha(directory/(name+".stdout.bin")))
    record["stderr"]=dict(path=str(directory/(name+".stderr.bin")),sha256=sha(directory/(name+".stderr.bin")))
    save(directory/(name+".json"),record)
    need(not record.get("timed_out") and (allow_nonzero or record["exit_code"]==0),"actual process failure "+name)
    return record

def execute(out):
    need(out.resolve().is_relative_to(AUTHOR.resolve()),"output outside exclusive author ownership")
    out.mkdir(parents=True,exist_ok=False)
    result=dict(task="DEEPEYE-IMPLEMENTATION-20261014/v1",work="B-TRACE-UART-CANDIDATE-20261024-49-v1",
                operation="B-DEEPEYE-TRACE-UART-CANDIDATE-20261024-49",job_id="child-879bf96dccd349c98c83260993618022",
                agent_id="01a16a34-b419-7942-9a7b-2b033142446b",status="running",repairs_used=0,
                contract_requirements_sha256="c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
                contract_ids=[f"H{i:02d}" for i in range(1,16)],all29="not_run",board="not_run; A only",
                Vivado="not_run",acceptance="pending independent main; no public ABI/receiver acceptance/remote rollback claim")
    save(out/"RESULT.json",result)
    try:
        for rel,h in PINS.items():need(sha(P/rel)==h,"input pin "+rel)
        need(sha(PROTECTED)==PROTECTED_SHA and sha(GOLD)==GOLD_SHA,"protected input/golden differs")
        before={}
        for rel in NEW+list(PINS):
            source=P/rel;target=out/"source"/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
            before[rel]=dict(path=str(source),sha256=sha(source),snapshot=str(target))
        result["sources"]=before;result["fixture_reuse"]=dict(path=str(GOLD),sha256=GOLD_SHA)
        result["tools"]={name:dict(path=str(TOOLS/(name+".exe")),sha256=sha(TOOLS/(name+".exe"))) for name in ("vlib","vmap","vlog","vsim")}
        result["python"]=dict(executable=sys.executable,version=sys.version,sha256=sha(sys.executable))
        tb=P/NEW[1];finish=[i for i,line in enumerate(tb.read_text().splitlines(),1) if "$finish;" in line]
        need(len(finish)==1,"unique actual TB finish");result["finish"]=dict(path=str(tb).replace("\\","/"),line=finish[0])
        sim=out/"sim";sim.mkdir()
        for name in ("vlog","vsim"):run_process(out,name+"-version",[TOOLS/(name+".exe"),"-version"],sim)
        for name,args in (("vmap-local",["vmap","-c"]),("vlib",["vlib","work"]),("vmap-work",["vmap","work","work"])):
            run_process(out,name,[TOOLS/(args[0]+".exe"),*args[1:]],sim)
        run_process(out,"vlog",[TOOLS/"vlog.exe","-sv","-work","work",*[P/r for r in [NEW[0],*PINS,NEW[1]]]],sim)
        result["profiles"]=[]
        for clock,baud,full,default in ((5,2,True,False),(7,2,False,False),(16,3,False,False),(2,1,False,False),(100000000,9600,False,True)):
            name=f"ratio-{clock}-{baud}";folder=out/name;data=fixture(folder,clock,baud,full,default)
            print("TU49 actual profile "+name,flush=True)
            argv=[TOOLS/"vsim.exe","-c","-onfinish","exit","-wlf",folder/"wave.wlf","-l",folder/"modelsim.log",
                  f"-gCLOCK_HZ={clock}",f"-gBAUD={baud}","work.tb_trace_uart_candidate",
                  "+INPUT="+str(folder/"fixture.txt"),"+TRACE="+str(folder/"public.trace"),"-do","run -all; quit -f"]
            process=run_process(out,"vsim-"+name,argv,sim)
            print("TU49 checking saved public trace "+name,flush=True)
            with (folder/"public.trace").open(encoding="ascii",newline="") as f:observed=check_trace(f,data)
            save(folder/"OBSERVED.json",observed)
            text=(folder/"modelsim.log").read_bytes().decode("utf-8")
            parse_log(text,data,observed,tb,finish[0])
            q=qualify(folder/"qualifier",text,data,observed,tb,finish[0])
            result["profiles"].append(dict(clock=clock,baud=baud,process=process,observed=observed,qualification=q,
                                           files={p.name:dict(path=str(p),sha256=sha(p)) for p in
                                                  (folder/"fixture.json",folder/"fixture.txt",folder/"public.trace",folder/"modelsim.log")}))
            save(out/"RESULT.json",result)
        result["guards"]=[]
        for name,clock,baud,expected in (("clock",1,1,"CLOCK_HZ"),("baud",5,3,"BAUD")):
            folder=out/("guard-"+name);folder.mkdir()
            process=run_process(out,"guard-"+name,[TOOLS/"vsim.exe","-c","-onfinish","exit","-wlf",folder/"wave.wlf",
                "-l",folder/"modelsim.log",f"-gCLOCK_HZ={clock}",f"-gBAUD={baud}","work.tb_trace_uart_candidate",
                "-do","run -all; quit -f"],sim,allow_nonzero=True)
            text=(folder/"modelsim.log").read_bytes().decode("utf-8")
            uart=P/"fpga/transport/deepeye_uart_tx.sv"
            guard_line=next(i for i,line in enumerate(uart.read_text().splitlines(),1) if '$fatal(1, "deepeye_uart_tx: '+expected+' out of range")' in line)
            parse_guard_log(text,expected,uart,guard_line)
            result["guards"].append(dict(name=name,process=process,actual_message=expected+" out of range",
                                         log_sha256=sha(folder/"modelsim.log"),actual_guard_line=guard_line,
                                         exit_note="ModelSim10.7 -onfinish exit can exit0 for a genuine time-zero DUT fatal; exact fatal/footer qualifies rejection."))
        for rel,ref in before.items():need(sha(P/rel)==ref["sha256"],"source changed during execution "+rel)
        need(sha(PROTECTED)==PROTECTED_SHA and sha(GOLD)==GOLD_SHA,"protected/golden changed")
        result.update(status="pass_bounded_author_simulation",protected_input_sha256=PROTECTED_SHA)
    except Exception as error:
        result.update(status="failed_preserved",error=type(error).__name__+": "+str(error))
        save(out/"RESULT.json",result);raise
    save(out/"RESULT.json",result)
    print(json.dumps(dict(status=result["status"],result=str(out/"RESULT.json"),profiles=[p["observed"]["stats"] for p in result["profiles"]],
                          guards=len(result["guards"])),ensure_ascii=True),flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--out",type=Path,required=True)
    execute(parser.parse_args().out)
