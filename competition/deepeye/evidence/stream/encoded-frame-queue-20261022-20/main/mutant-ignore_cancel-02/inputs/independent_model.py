"""Op20 independent accepted-edge/list oracle, written before author dispatch.

No author module, state encoding, reference implementation or test is imported.
Metadata/data are compared only when valid, represented as zero otherwise.
All inputs and observations refer to the same pre-edge state.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import gzip, hashlib, json

INPUTS = [("rst",1),("cancel",1),("mv",1),("tag",16),("error",2),
          ("count",8),("e",4),("raw",1),("k",4),("bits",12),("bytes",9),
          ("iv",1),("data",8),("last",1),("mr",1),("ready",1)]
META = ["tag","error","count","e","raw","k","bits","bytes"]
OUTPUTS = [("imr",1),("ir",1),("omv",1)] + [(n,w) for n,w in INPUTS if n in META] + [
    ("ov",1),("data",8),("last",1),("level",2),("receiving",1),("faulted",1),
    ("event",1),("code",2),("stat_meta",32),("stat_in_bytes",32),
    ("stat_retired",32),("stat_aborted",32),("stat_fault",32)]
def pack(values, fields):
    out=0
    for name,width in fields:
        value=int(values.get(name,0))
        assert 0<=value<(1<<width),(name,value,width)
        out=(out<<width)|value
    return out
def unpack(value, fields):
    out={}
    for name,width in reversed(fields):
        out[name]=value&((1<<width)-1);value>>=width
    assert value==0
    return out

class Queue:
    def __init__(self,width=32):
        self.maximum=(1<<width)-1
        self.clear()
    def clear(self):
        self.frames=[];self.faulted=0;self.event=0;self.code=0
        self.stats={k:0 for k,_ in OUTPUTS if k.startswith("stat_")}
    def add(self,name,amount=1):
        self.stats[name]=min(self.maximum,self.stats[name]+amount)
    def filling(self):
        return next((f for f in self.frames if not f["sealed"] and not f["poison"]),None)
    def observe(self,x):
        o={k:0 for k,_ in OUTPUTS};o.update(self.stats)
        fill=self.filling()
        o.update(level=len(self.frames),receiving=int(fill is not None and not self.faulted),
                 faulted=self.faulted,event=self.event,code=self.code)
        if x.get("rst") or x.get("cancel"):return o
        o["imr"]=int(not self.faulted and fill is None and len(self.frames)<2)
        o["ir"]=int(not self.faulted and fill is not None)
        if self.frames and self.frames[0]["sealed"]:
            f=self.frames[0]
            if not f["metadata_sent"]:
                o["omv"]=1;o.update(f["meta"])
            else:
                o["ov"]=1;o["data"]=f["data"][f["position"]]
                o["last"]=int(f["position"]==f["meta"]["bytes"]-1)
        return o
    def edge(self,x):
        o=self.observe(x)
        if x.get("rst"):
            self.clear();return o
        if x.get("cancel"):
            self.add("stat_aborted",len(self.frames))
            self.frames=[];self.faulted=0;self.event=0;self.code=0
            return o
        fill=self.filling();self.event=0
        retire=False
        if o["omv"] and x.get("mr"):
            f=self.frames[0]
            if f["meta"]["error"]:retire=True
            else:f["metadata_sent"]=True
        if o["ov"] and x.get("ready"):
            if o["last"]:retire=True
            else:self.frames[0]["position"]+=1
        if retire:
            self.frames.pop(0);self.add("stat_retired")
        if o["ir"] and x.get("iv"):
            self.add("stat_in_bytes")
            fill["data"].append(x["data"])
            final=len(fill["data"])==fill["meta"]["bytes"]
            if bool(x.get("last"))!=final:
                fill["poison"]=True;self.faulted=1;self.code=2;self.event=1;self.add("stat_fault")
            elif final:fill["sealed"]=True
        if o["imr"] and x.get("mv"):
            meta={n:x.get(n,0) for n in META}
            valid=(meta["bytes"]==meta["bits"]==0 if meta["error"] else
                   1<=meta["bytes"]<=256 and 8*(meta["bytes"]-1)<meta["bits"]<=8*meta["bytes"])
            self.frames.append(dict(meta=meta,data=[],sealed=bool(valid and meta["error"]),
                                    poison=not valid,metadata_sent=False,position=0))
            self.add("stat_meta")
            if not valid:self.faulted=1;self.code=1;self.event=1;self.add("stat_fault")
        assert len(self.frames)<=2
        if all(v<self.maximum for n,v in self.stats.items() if n!="stat_in_bytes"):
            assert self.stats["stat_meta"]==self.stats["stat_retired"]+self.stats["stat_aborted"]+len(self.frames)
        return o

def codec(samples,e,tag=0,error=0):
    """Integer specification independently expressed as a bit-string encoder."""
    if error:
        return dict(tag=tag,error=error,count=0,e=0,raw=1,k=0,bits=0,bytes=0),[]
    assert samples and len(samples)<=128 and e in (0,1,2,4,8)
    predictor=samples[0];residuals=[];d=2*e+1
    for sample in samples[1:]:
        q=(sample-predictor+e)//d
        predictor=max(0,min(65535,predictor+q*d))
        residuals.append(2*q if q>=0 else -2*q-1)
    choices=[(sum((z>>k)+1+k for z in residuals),k) for k in range(16)
             if all((z>>k)<=31 for z in residuals)]
    best=min(choices) if choices else (10**9,0)
    raw=int(best[0]>=16*(len(samples)-1));k=0 if raw else best[1]
    bits=format(samples[0],"016b")
    if raw:bits="".join(format(v,"016b") for v in samples)
    else:
        for z in residuals:
            bits+="0"*(z>>k)+"1"+(format(z&((1<<k)-1),f"0{k}b") if k else "")
    nbits=len(bits);bits+="0"*((-len(bits))%8)
    data=[int(bits[i:i+8],2) for i in range(0,len(bits),8)]
    return dict(tag=tag,error=0,count=len(samples),e=e,raw=raw,k=k,bits=nbits,bytes=len(data)),data

class Vectors:
    def __init__(self,directory,width):
        self.directory=directory;self.q=Queue(width);self.edges=0
        self.cover=Counter();self.values=set();self.phase="initial"
        self.inputs=gzip.GzipFile(filename="",mode="wb",fileobj=(directory/"inputs.hex.gz").open("xb"),mtime=0)
        self.expected=gzip.GzipFile(filename="",mode="wb",fileobj=(directory/"expected.hex.gz").open("xb"),mtime=0)
        self.ih=hashlib.sha256();self.eh=hashlib.sha256()
        self.iw=(sum(w for _,w in INPUTS)+3)//4;self.ow=(sum(w for _,w in OUTPUTS)+3)//4
        self.step(rst=1);self.step()
    def step(self,**kw):
        x={n:0 for n,_ in INPUTS};x.update(kw);o=self.q.edge(x)
        ib=(f"{pack(x,INPUTS):0{self.iw}x}\n").encode()
        ob=(f"{pack(o,OUTPUTS):0{self.ow}x}\n").encode()
        self.inputs.write(ib);self.expected.write(ob);self.ih.update(ib);self.eh.update(ob)
        self.cover[self.phase]+=1;self.edges+=1
        if o["ir"] and x["iv"]:self.values.add(x["data"])
        alloc=o["imr"] and x["mv"];retire=(o["omv"] and x["mr"] and o["error"]) or (o["ov"] and x["ready"] and o["last"])
        self.cover["admissions"]+=bool(alloc);self.cover["retirements"]+=bool(retire)
        self.cover["simultaneous_allocate_retire"]+=bool(alloc and retire)
        self.cover["simultaneous_input_retire"]+=bool(o["ir"] and x["iv"] and retire)
        self.cover["full_admission_attempts"]+=bool(o["level"]==2 and x["mv"])
        self.cover["fault_edges"]+=bool(self.q.event)
        return o
    def idle(self,n,**kw):
        for _ in range(n):self.step(**kw)
    def admit(self,n,rem=8,tag=7,error=0,**kw):
        meta=dict(tag=tag,error=error,count=(n*3)&255,e=(n+rem)&15,
                  raw=(n+rem)&1,k=(n*7+rem)&15,bits=8*(n-1)+rem if not error else 0,bytes=n if not error else 0)
        meta.update(kw)
        assert self.q.observe({})["imr"]
        self.step(mv=1,iv=1,data=231,last=1,**meta)
    def feed(self,n,seed=0,bubbles=False,bad=None,**kw):
        for i in range(n):
            if bubbles and i%37==0:self.step(data=255,last=1,**kw)
            last=int(i==n-1)
            if bad is not None and i==bad:last=1-last
            self.step(iv=1,data=(i*73+seed)&255,last=last,**kw)
            if bad is not None and i==bad:break
    def drain(self,limit=600,stall=False):
        for i in range(limit):
            if not self.q.frames:break
            if self.q.frames[0]["poison"]:break
            self.step(mr=int(not stall or i%7!=1),ready=int(not stall or i%11 not in (2,3)))
        assert not self.q.frames or self.q.frames[0]["poison"]
    def cancel(self,reset=False):
        self.step(rst=int(reset),cancel=1,mv=1,iv=1,mr=1,ready=1)
        self.idle(2,cancel=1,mv=1,iv=1,mr=1,ready=1);self.step()
    def close(self):
        self.idle(4);self.inputs.close();self.expected.close()
        result=dict(edges=self.edges,input_raw_sha256=self.ih.hexdigest(),expected_raw_sha256=self.eh.hexdigest(),
                    input_width=sum(w for _,w in INPUTS),output_width=sum(w for _,w in OUTPUTS),
                    coverage=dict(self.cover),byte_values=sorted(self.values),final_stats=self.q.stats)
        (self.directory/"vectors.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        return result

def standalone(root):
    d=root/"standalone";d.mkdir();v=Vectors(d,32)
    v.phase="all_2048_framing_combinations"
    for n in range(1,257):
        for rem in range(1,9):
            v.admit(n,rem,tag=(0,65535,0,5)[rem%4])
            v.feed(n,seed=n+rem,bubbles=True)
            if n%31==0:v.idle(17,iv=1,data=231,last=1)
            v.drain(stall=n%23==0)
    assert v.cover["admissions"]==2048 and v.cover["retirements"]==2048
    assert v.values==set(range(256))
    v.phase="full_credit_and_simultaneous"
    for i in range(64):
        v.admit(0,error=(i%3)+1);v.admit(0,error=((i+1)%3)+1)
        v.idle(11,mv=1,iv=1,mr=0,ready=1)
        v.step(mv=1,mr=1,ready=1)  # full -> no admission even though first error retires
        v.step(mv=1,tag=i,error=3,mr=1,ready=1)  # oldlevel1 allocate+retire
        v.drain()
        v.admit(1,tag=5);v.feed(1,seed=i);v.step(mr=1)
        v.admit(2,tag=5);v.step(iv=1,data=41)
        v.step(iv=1,data=42,last=1,ready=1)  # seal+older-success-retire
        v.drain(stall=True)
    v.phase="invalid_descriptors_and_poison"
    invalid=[dict(bytes=n,bits=b,error=e) for n,b,e in
             [(0,0,0),(0,1,0),(257,2048,0),(511,4095,0),(1,0,0),(1,9,0),
              (2,8,0),(2,17,0),(255,0,0),(255,2041,0),(256,2040,0),(256,2049,0),
              (256,4095,0),(1,1,1),(0,1,2),(256,0,3),(0,4095,1)]]
    for item in invalid:
        v.admit(1);v.feed(1,seed=99);v.step(mr=1)
        v.step(mv=1,tag=123,ready=1,**item)
        assert v.q.faulted and v.q.code==1
        v.idle(13,mv=1,iv=1,data=17,last=1,mr=1,ready=1)
        assert len(v.q.frames)==1 and v.q.frames[0]["poison"]
        v.cancel();v.admit(1);v.feed(1,seed=91);v.drain()
    v.phase="early_missing_last"
    faults=[(n,i) for n in range(2,17) for i in range(n-1)]
    faults += [(n,i) for n in (1,2,255,256) for i in sorted({0,n//2,n-1})]
    for n,bad in faults:
        v.admit(1);v.feed(1,seed=66);v.step(mr=1)
        v.admit(n);v.feed(n,bad=bad,ready=1)
        assert v.q.faulted and v.q.code==2
        v.idle(9,mv=1,iv=1,data=255,last=1,mr=1,ready=1)
        assert len(v.q.frames)==1 and v.q.frames[0]["poison"]
        v.cancel()
    v.phase="abort_phases"
    for reset in (False,True):
        v.cancel(reset)
        for n in (1,2,9,255,256):
            for cut in sorted({0,1,n//2,n-1,n}):
                v.admit(n)
                for i in range(cut):v.step(iv=1,data=i&255,last=int(i==n-1))
                v.step(rst=int(reset),cancel=1,iv=1,data=251,last=1,mv=1,mr=1,ready=1)
                v.cancel(reset);v.admit(2,tag=0xBEEF);v.feed(2,seed=29);v.drain()
            for cut in sorted({-1,0,1,n//2,n-1}):
                v.admit(n);v.feed(n,seed=51)
                if cut>=0:v.step(mr=1,ready=1)
                for _ in range(max(0,cut)):v.step(ready=1)
                v.cancel(reset);v.admit(0,error=2,tag=0xF00D);v.drain()
    v.phase="long_stalls"
    v.admit(256);v.feed(256,seed=17)
    v.admit(3);v.feed(3,seed=18)
    v.idle(1500,mv=1,iv=1,data=89,last=1,ready=1)
    v.step(mr=1,ready=1);v.idle(1700,mv=1,iv=1,mr=1)
    v.drain(limit=1000,stall=True)
    return v.close()

def saturation(root,width):
    d=root/f"sat{width}";d.mkdir();v=Vectors(d,width);v.phase="saturation_real_transactions"
    for i in range(22):
        v.admit(3,tag=i);v.feed(3,seed=i);v.drain()
    for i in range(22):
        v.admit(0,error=1);v.step(mv=1,bytes=511,bits=4095)
        v.idle(2,mr=1,ready=1,iv=1)
        v.cancel()
    assert all(n==v.q.maximum for n in v.q.stats.values())
    return v.close()

def composition(root):
    cases=[
      dict(name="rice_constant",samples=[30713]*37,e=4,tag=22),
      dict(name="raw_full256",samples=[0x1357 if i%2==0 else 0xEC8A for i in range(128)],e=0,tag=22),
      dict(name="invalid_cfg",samples=[],e=3,tag=65535,error=1,count=9),
      dict(name="bad_last",samples=[5,7,8],e=1,tag=22,error=2,count=5),
      dict(name="rice_floor",samples=[20000+((i*11)%17)-8 for i in range(61)],e=2,tag=65535),
      dict(name="raw_single",samples=[0xB6E1],e=8,tag=0),
      dict(name="raw_ramp",samples=[(i*19273+731)&65535 for i in range(53)],e=1,tag=22),
      dict(name="rice_steps",samples=[17003+(i//5)*3 for i in range(128)],e=8,tag=0),
    ]
    for c in cases:
        m,b=codec(c["samples"],c["e"],c["tag"],c.get("error",0));c.update(expected_meta=m,expected_bytes=b)
    assert cases[1]["expected_meta"]["bytes"]==256 and cases[1]["expected_meta"]["raw"]==1
    assert cases[0]["expected_meta"]["raw"]==0 and cases[4]["expected_meta"]["raw"]==0
    plan=dict(cases=cases,output_hold_cycles=100000,
              phases=["four-frame producer with independently timed output stall to hold two complete queue frames",
                      "remaining fresh RAW/Rice/errors/duplicate tags under independent metadata/payload stalls",
                      "shared cancel while queue receiving payload; discard all raw/encoded pending records",
                      "shared cancel while downstream metadata stalled and while output bytes partial",
                      "fresh recovery using same case definitions and tags after each abort"],
              oracle="Queue model consumes observed internal handshakes; codec expectations derive only from accepted source cfg/samples and independent integer rules.",
              no_duplicate_encoder="One op09 wrapper already owns one op08 encoder.")
    (root/"composition_frozen.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")

def freeze():
    root=Path(__file__).resolve().parent
    if (root/"FROZEN.json").exists():raise RuntimeError("Existing freeze; do not replay")
    results={"standalone":standalone(root)}
    for width in (2,3):results[f"sat{width}"]=saturation(root,width)
    composition(root)
    files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
           for p in root.rglob("*") if p.is_file()}
    f=dict(at_utc=datetime.now(timezone.utc).isoformat(),task_id="DEEPEYE-IMPLEMENTATION-20261014",task_version=1,
           operation="B-DEEPEYE-ENCODED-FRAME-QUEUE-20261022-20",status="FROZEN_BEFORE_AUTHOR_DISPATCH_AND_RTL_READ",
           model="Independent accepted descriptor records, byte lists, old-state observations and edge transitions",
           files=files,results=results,inputs=INPUTS,outputs=OUTPUTS,
           guard_marker="DEEPEYE_ENCODED_FRAME_QUEUE_INVALID_PARAM STAT_W=<decimal>",
           requirements_sha256="c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
           design="1011259415a0916054eb580687612580bc1e5f09")
    with (root/"FROZEN.json").open("x",encoding="utf-8") as out:json.dump(f,out,indent=2)
    print(json.dumps({"status":f["status"],"files":len(files),"edges":{k:v["edges"] for k,v in results.items()},
                      "sha256":hashlib.sha256((root/"FROZEN.json").read_bytes()).hexdigest()}))
if __name__=="__main__":freeze()
