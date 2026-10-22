"""Independent event ledger, literal controls and stimuli, written before author RTL.

Unsaturated loss is the cardinality of disjoint ordinal sets. The ledger keeps
original events, retired scan tuples, and a single transport slot; counters are
projections of that history, not a translation of RTL registers.
"""
import gzip, hashlib, itertools, json, random
from pathlib import Path
from datetime import datetime, timezone

FIELDS='out_valid out_data out_ticks out_quality out_first_seq out_last_seq out_tag armed partial_len next_seq seq_exhausted order_error_event overrun_event seq_exhaust_event stat_events stat_scans stat_retired stat_discarded_samples stat_order_errors stat_overruns'.split()
INPUTS='rst stop rearm rearm_tag sample_strobe sample_channel sample_data sample_tick sample_quality out_ready'.split()
sha=lambda b:hashlib.sha256(b).hexdigest()

class Ledger:
    def __init__(self,seq=32,tick=64,tag=64,stat=32):
        self.seq,self.tick,self.tagw,self.stat=seq,tick,tag,stat
        self.clear(False,0)
    def clear(self,armed,tag):
        self.enabled=armed;self.tag=tag;self.events=[];self.pending=[];self.slot=None
        self.retired=[];self.scans=[];self.lost=set();self.faults=[];self.overruns=[]
        self.exhaust=False;self.pulses=(0,0,0)
    def view(self,abort=False):
        p=self.slot
        payload=[0]*6 if p is None else [sum(e[1]<<(16*i) for i,e in enumerate(p)),sum(e[2]<<(self.tick*i) for i,e in enumerate(p)),sum(e[3]<<(8*i) for i,e in enumerate(p)),p[0][4],p[-1][4],self.tag]
        sat=lambda n:min(n,(1<<self.stat)-1)
        return [int(p is not None and not abort),*payload,int(self.enabled),len(self.pending),min(len(self.events),(1<<self.seq)-1),int(self.exhaust),*self.pulses,*map(sat,[len(self.events),len(self.scans),len(self.retired),len(self.lost),len(self.faults),len(self.overruns)])]
    def step(self,x):
        rst,stop,rearm,tag,strobe,ch,data,tick,q,ready=x
        abort=bool(rst or stop or rearm); pre=self.view(abort)
        if abort:
            self.clear(not(rst or stop) and bool(rearm),tag if rearm and not(rst or stop) else 0)
        else:
            oe=ov=ex=0
            if self.slot is not None and ready:self.retired.append(self.slot);self.slot=None
            if self.enabled and strobe:
                ordinal=len(self.events); e=(ch,data,tick,q,ordinal);self.events.append(e)
                if ch==len(self.pending):
                    self.pending.append(e)
                    if len(self.pending)==4:
                        complete=tuple(self.pending);self.scans.append(complete);self.pending=[]
                        if self.slot is None:self.slot=complete
                        else:
                            self.overruns.append(complete);self.lost.update(t[4] for t in complete);ov=1
                else:
                    self.faults.append(e);oe=1
                    self.lost.update(t[4] for t in self.pending);self.pending=[]
                    if ch==0:self.pending=[e]
                    else:self.lost.add(ordinal)
                if ordinal==(1<<self.seq)-1:
                    self.enabled=False;self.exhaust=True;ex=1
                    self.lost.update(t[4] for t in self.pending);self.pending=[]
            self.pulses=(oe,ov,ex)
        # History identities use exact integers, including after port saturation.
        assert len(self.events)==4*(len(self.retired)+(self.slot is not None))+len(self.pending)+len(self.lost)
        assert len(self.scans)==len(self.retired)+(self.slot is not None)+len(self.overruns)
        assert len(self.pending)<=3
        return pre,self.view(abort)

def literal_controls():
    cases=[([],0,0,0),([1],0,0,1),([0],0,1,0),([0,1],0,2,0),([0,1,2],0,3,0),([0,1,2,3],1,0,0),([0,0,1,2,3],1,0,1),([0,1,1,2,3],0,0,5),([0,2,0,1,2,3],1,0,2),([0,1,2,3,0,1],1,2,0)]
    for channels,scans,partial,lost in cases:
        m=Ledger();m.step([0,0,1,7,0,0,0,0,0,0])
        for c in channels:m.step([0,0,0,0,1,c,c,0,0,0])
        assert (len(m.scans),len(m.pending),len(m.lost))==(scans,partial,lost)
    m=Ledger(seq=2);m.step([0,0,1,1,0,0,0,0,0,0])
    for c in [0,1,2,0]: m.step([0,0,0,0,1,c,0,0,0,0])
    assert m.view()[7:]==[0,0,3,1,1,0,1,4,0,0,4,1,0]
    m=Ledger(seq=3);m.step([0,0,1,1,0,0,0,0,0,0])
    for c in [0,1,2,3]*2:m.step([0,0,0,0,1,c,0,0,0,0])
    assert len(m.scans)==2 and len(m.lost)==4 and m.pulses==(0,1,1)
    return len(cases)+2

class Stimuli:
    def __init__(self,seq=32,tick=64,tag=64,stat=32):
        self.params=dict(seq=seq,tick=tick,tag=tag,stat=stat);self.rows=[];self.labels=[];self.count=0
    def add(self,strobe=0,ch=0,ready=0,rst=0,stop=0,rearm=0,tag=None,data=None,tick=None,q=None):
        i=self.count;self.count+=1
        values=[0,1,0x7fff,0x8000,0xffff,(i*4051+7)&65535]
        ticks=[0,0,(1<<63),(1<<63)-1,(1<<32),(1<<32)-1,(1<<64)-1,(~i)&((1<<64)-1)]
        row=[rst,stop,rearm,((1<<self.params['tag'])-1 if tag is None else tag)&((1<<self.params['tag'])-1),strobe,ch,values[i%6] if data is None else data,ticks[i%8] if tick is None else tick,(i*17)&255 if q is None else q,ready]
        row[7]&=(1<<self.params['tick'])-1
        self.rows.append(row)
    def rearm(self,tag=None):self.add(rearm=1,tag=tag)
    def group(self,channels,ready=0):
        for c in channels:self.add(strobe=1,ch=c,ready=ready)
    def label(self,s):self.labels.append([len(self.rows),s])

def make_cases():
    s=Stimuli();s.add(rst=1);s.label('empty/short prefixes')
    for n in range(6):
        for channels in itertools.product(range(4),repeat=n):s.rearm();s.group(channels);s.add(ready=1)
    s.label('4096 exhaustive channel strings length6')
    for channels in itertools.product(range(4),repeat=6):s.rearm();s.group(channels);s.add(ready=1)
    s.label('ready patterns; at least two correct scans under each period')
    for n in range(1,5):
        for pattern in itertools.product(range(2),repeat=n):
            s.rearm()
            for i in range(40):s.add(strobe=1,ch=i%4,ready=pattern[i%n])
            s.add(ready=1)
    s.label('long stall and gap no timeout')
    s.rearm();s.group([0,1,2,3]*100);s.add(ready=1);s.group([0,1])
    for _ in range(1500):s.add(ready=1)
    s.group([2,3]);s.add(ready=1)
    s.label('every quality value in every lane, 64 tag bits, opaque ticks')
    for q in range(256):
        s.rearm(tag=(1<<64)-1)
        for c in range(4):s.add(strobe=1,ch=c,q=q,data=[0,1,0x7fff,0x8000,0xffff][q%5],tick=[0,(1<<64)-1,1<<63,(1<<63)-1,1<<31,(1<<31)-1,7,6][q%8])
        s.add(ready=1)
    for b in range(64):
        s.rearm(tag=1<<b);s.group([0,1,2,3]);s.rearm(tag=1<<b);s.add(ready=1);s.group([0,1,2,3]);s.add(ready=1)
    s.label('all abort combinations, held abort, each partial and old full slot')
    for flags in itertools.product(range(2),repeat=3):
        if not any(flags):continue
        for occupied in [False,True]:
            for n in range(4):
                s.rearm(tag=123)
                if occupied:s.group([0,1,2,3])
                s.group(range(n))
                for _ in range(3):s.add(strobe=1,ch=n,ready=1,rst=flags[0],stop=flags[1],rearm=flags[2],tag=123)
                s.group([0,1,2,3],ready=1);s.add(ready=1)
    s.label('25000 independent randomized edges seed2026102221')
    rng=random.Random(2026102221)
    for i in range(25000):
        s.add(strobe=int(rng.random()<.82),ch=rng.randrange(4),ready=int(rng.random()<.31),rearm=int(rng.random()<.007),rst=int(rng.random()<.001),stop=int(rng.random()<.001),tag=rng.getrandbits(64),data=rng.getrandbits(16),tick=rng.getrandbits(64),q=rng.randrange(256))
    cases={'main64':s}
    for w in [2,3,4]:
        s=Stimuli(seq=w,stat=32);s.add(rst=1)
        s.label('every four-event terminal tail, with orphan prefix; drain and unarmed strobe')
        for tail in itertools.product(range(4),repeat=4):
            for ready in [0,1]:
                s.rearm();s.group([3]*((1<<w)-4),ready=ready);s.group(tail,ready=ready)
                s.group([0,1,2,3],ready=0);s.add(ready=1);s.add(ready=1)
        s.label('complete last scan / terminal overrun')
        for ready in [0,1]:
            s.rearm();s.group([0,1,2,3]*(1<<(w-2)),ready=ready);s.add(ready=1);s.add(ready=1)
        s.label('abort at terminal ordinal all combinations')
        for flags in itertools.product(range(2),repeat=3):
            if not any(flags):continue
            s.rearm();s.group(([0,1,2,3]*(1<<(w-2)))[:-1])
            s.add(strobe=1,ch=3,ready=1,rst=flags[0],stop=flags[1],rearm=flags[2]);s.group([0,1,2,3],ready=1)
        cases['seq'+str(w)]=s
    s=Stimuli(seq=16);s.add(rst=1);s.rearm();s.label('all65536 actual events; no seeded ordinal')
    s.group([i%4 for i in range(65536)],ready=1);s.group([0,1,2,3]*4,ready=1);s.rearm();s.group([0,1,2,3]);s.add(ready=1)
    cases['seq16']=s
    for w in [2,3]:
        s=Stimuli(stat=w);s.add(rst=1);s.rearm();s.label('all six counters saturate by transactions; data flow continues')
        s.group([0,1,2,3]*40,ready=1);s.group([0,1,2,3]*40);s.group([0,2,1,3]*40);s.add(ready=1);s.group([0,1,2,3]*4,ready=1)
        cases['stat'+str(w)]=s
    s=Stimuli(seq=32,tick=1,tag=1);s.add(rst=1);s.rearm();s.group([0,1,2,3]*20,ready=1);s.add(ready=1);cases['width1']=s
    return cases

def freeze(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    count=literal_controls();index={}
    for name,s in make_cases().items():
        d=directory/name;d.mkdir();m=Ledger(**s.params);maxima=[0]*6;dual=set()
        vb=(''.join(' '.join(format(x,'x') for x in row)+'\n' for row in s.rows)).encode('ascii');(d/'vectors.hex').write_bytes(vb)
        expect=[]
        for row in s.rows:
            pre,post=m.step(row);expect.append([pre,post])
            maxima=[max(a,b) for a,b in zip(maxima,post[14:])]
            if sum(post[11:14])>1:dual.add(tuple(post[11:14]))
        if name.startswith('stat'):assert maxima==[(1<<s.params['stat'])-1]*6
        eb=gzip.compress(json.dumps(expect,separators=(',',':')).encode(),mtime=0);(d/'expected.json.gz').write_bytes(eb)
        meta={'params':s.params,'edges':len(s.rows),'labels':s.labels,'counter_maxima':maxima,'coincident_flags':sorted(dual),'vectors_sha256':sha(vb),'expected_sha256':sha(eb)}
        (d/'meta.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8');index[name]=meta
    result={'at_utc':datetime.now(timezone.utc).isoformat(),'independence':'Written and frozen before author dispatch/RTL existence; imports no author code or historical oracle. Event/loss ledger and literal controls.','model_sha256':sha(Path(__file__).read_bytes()),'literal_controls':count,'fields':FIELDS,'inputs':INPUTS,'cases':index,'fatal_contract':{p:'deepeye_sample_scan_capture: '+p+' out of range' for p in ['SEQ_W','TICK_W','TAG_W','STAT_W']}}
    (directory/'FREEZE.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({'freeze':str(directory/'FREEZE.json'),'sha256':sha((directory/'FREEZE.json').read_bytes()),'cases':{k:v['edges'] for k,v in index.items()}}))

if __name__=='__main__':freeze(Path(__file__).parent/'frozen-inputs')
