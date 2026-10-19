"""Op15 independent deadline/application and absolute sampled-edge oracle.

Only the frozen12/14 port contracts and op15 scope are inputs. No author15
implementation/model is imported. Internal loopback is supplemental to explicit
independent level schedules. All H01-H15 remain fixed at requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
"""
import argparse,datetime,hashlib,itertools,json,os,random,re,shutil,subprocess
from pathlib import Path

FIELDS=['pre_valid','pre_ready','cfg_ready','accepted','rejected','applied','frame_start','running','pending','pwm','active_period','active_high_yaw','active_high_pitch','active_high_speed','active_tag','window_active','window_started','capture_armed','out_valid','out_period','out_high0','out_high1','out_high2','out_start','out_end','out_tag','expected_period','expected_high0','expected_high1','expected_high2','expected_tag','raw_fault_events','failure_event','failure_code']
INPUTS=['rst','stop','cfg_valid','cfg_period','cfg_high_yaw','cfg_high_pitch','cfg_high_speed','cfg_tag','drive_levels','loopback','out_ready']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class Generator:
    """Absolute frame deadlines and half-open high intervals, no RTL phase copy."""
    def __init__(self):
        self.active=None;self.queued=None;self.origin=None;self.next_boundary=None
        self.accepted=self.rejected=self.applied=self.frame_start=self.pwm=0
    def ready(self,rst,stop):return int(not(rst or stop) and self.queued is None)
    def advance(self,now,rst,stop,valid,payload):
        transfer=valid and self.ready(rst,stop)
        self.accepted=self.rejected=self.applied=self.frame_start=0
        if rst or stop:self.active=self.queued=self.origin=self.next_boundary=None
        else:
            boundary=self.active is None or now==self.next_boundary
            if self.queued is not None and boundary:
                self.active=self.queued;self.queued=None;self.applied=1
            if boundary and self.active is not None:
                self.origin=now;self.next_boundary=now+self.active[0];self.frame_start=1
            if transfer:
                if payload[0]>0 and max(payload[1:4])<=payload[0]:self.queued=payload;self.accepted=1
                else:self.rejected=1
        self.pwm=0
        if self.active:
            for lane,width in enumerate(self.active[1:4]):
                if self.origin<=now<self.origin+width:self.pwm|=1<<lane

class Capture:
    """Independent raw contract, absolute first-fall indices and one queue."""
    def __init__(self,c,w):
        self.cm=(1<<c)-1;self.tm=(1<<w)-1;self.armed=False;self.previous=0
        self.origin=self.start=self.queue=None;self.falls=[None]*3;self.tag=0;self.fault=0
        self.events={k:0 for k in ['start','candidate','admitted','retired','incoherent','period','witness','overrun']}
    def advance(self,now,levels,ready,rst,stop,arm,tag):
        self.fault=0
        if rst or stop or arm:
            self.armed=bool(arm and not(rst or stop));self.previous=levels if self.armed else 0
            self.origin=now if self.armed else None;self.start=self.queue=None;self.falls=[None]*3;self.tag=tag if self.armed else 0
            return
        if self.queue is not None and ready:self.queue=None;self.events['retired']+=1
        if not self.armed:return
        tick=now-self.origin
        if tick>self.tm:
            self.fault=4;self.armed=False;self.start=None;self.falls=[None]*3;self.events['witness']+=1;return
        rise=(~self.previous)&levels&7;fall=self.previous&(~levels)&7;self.previous=levels
        if self.start is not None and now-self.start>self.cm:
            self.fault=2;self.start=now if rise==7 else None;self.falls=[None]*3
            if rise==7:self.events['start']+=1
        elif self.start is None:
            if rise==7:self.start=now;self.falls=[None]*3;self.events['start']+=1
            elif rise:self.fault=1
        elif rise==7:
            if all(f is not None and self.start<f<now for f in self.falls):
                record=(now-self.start,*(f-self.start for f in self.falls),self.start-self.origin,tick,self.tag)
                self.events['candidate']+=1
                if self.queue is None:self.queue=record;self.events['admitted']+=1
                else:self.fault=8
            else:self.fault=1
            self.start=now;self.falls=[None]*3;self.events['start']+=1
        elif rise:self.fault=1;self.start=None;self.falls=[None]*3
        else:
            for lane in range(3):
                if fall&(1<<lane) and self.falls[lane] is None:self.falls[lane]=now
        if self.fault:self.events[{1:'incoherent',2:'period',8:'overrun'}[self.fault]]+=1

class Oracle:
    def __init__(self,c,w,t):
        self.cw=c;self.ww=w;self.tw=t;self.cm=(1<<c)-1;self.tagmask=(1<<t)-1
        self.g=Generator();self.c=Capture(c,w);self.now=-1;self.bound=False;self.context=(0,)*5
        self.started=self.failure=self.code=0;self.rows=[];self.cover={};self.scenarios=[]
        self.events={k:0 for k in ['transfers','accepted','rejected','actual_applications','windows','handshakes','mismatch','incoherent','period','witness','overrun','ineligible','unexpected_disarm']}
    def controls(self,rst,stop,valid,ready):
        g=self.g;c=self.c;transfer=bool(valid and g.ready(rst,stop));a=g.active or (0,)*5
        eligible=a[0]>=2 and all(0<h<a[0] for h in a[1:4])
        halt=bool(rst or stop or transfer or g.queued is not None or g.active is None)
        arm=bool(not halt and g.applied and eligible)
        capstop=bool(halt or(g.applied and not eligible)or(not self.bound and not arm))
        rawvalid=c.queue is not None and not(rst or capstop or arm)
        raw=c.queue or(0,)*7;equal=tuple(raw[:4])+(raw[6],)==self.context
        gate=bool(self.bound and not halt and not g.applied)
        validout=bool(gate and c.armed and not c.fault and rawvalid and equal)
        capready=bool(gate and c.armed and not c.fault and equal and ready)
        return dict(transfer=transfer,eligible=eligible,halt=halt,arm=arm,capstop=capstop,rawvalid=rawvalid,equal=equal,valid=validout,ready=capready)
    def step(self,rst=0,stop=0,valid=0,p=0,hs=(0,0,0),tag=0,levels=0,loopback=0,ready=1,label=None):
        payload=(p&self.cm,*(h&self.cm for h in hs),tag&self.tagmask)
        pre=self.controls(rst,stop,valid,ready);preready=self.g.ready(rst,stop);self.now+=1
        sampled=self.g.pwm if loopback else levels
        oldtag=(self.g.active or(0,)*5)[4]
        self.started=self.failure=0
        if pre['valid'] and ready:
            self.events['handshakes']+=1
            assert self.c.queue and 1<=self.c.queue[4]<self.c.queue[5]
            assert self.c.origin is not None and self.c.origin+self.c.queue[4]>self.c.origin
        if rst or stop:self.bound=False;self.context=(0,)*5;self.code=0
        elif pre['transfer'] or self.g.queued is not None or self.g.active is None:
            self.bound=False;self.context=(0,)*5;self.code=0
        elif self.g.applied:
            self.code=0
            if pre['eligible']:
                self.bound=True;self.context=self.g.active;self.started=1;self.events['windows']+=1
            else:self.bound=False;self.context=(0,)*5;self.failure=1;self.code=6
        elif self.bound:
            cause=0
            if self.c.fault:
                cause=4 if self.c.fault&4 else 3 if self.c.fault&2 else 2 if self.c.fault&1 else 5
            elif not self.c.armed:cause=7
            elif pre['rawvalid'] and not pre['equal']:cause=1
            if cause:self.bound=False;self.context=(0,)*5;self.failure=1;self.code=cause
        else:self.bound=False;self.context=(0,)*5
        self.c.advance(self.now,sampled,pre['ready'],rst,pre['capstop'],pre['arm'],oldtag)
        self.g.advance(self.now,rst,stop,valid,payload)
        post=self.controls(rst,stop,valid,ready)
        g=self.g;c=self.c
        expected=[int(pre['valid']),preready,g.ready(rst,stop),g.accepted,g.rejected,g.applied,g.frame_start,int(g.active is not None),int(g.queued is not None),g.pwm,*(g.active or(0,)*5),int(self.bound),self.started,int(c.armed),int(post['valid']),*(c.queue or(0,)*7),*self.context,c.fault,self.failure,self.code]
        assert len(expected)==len(FIELDS)
        row=[rst,stop,valid,*payload,levels,loopback,ready,*expected]
        assert len(row)==len(INPUTS)+len(FIELDS)
        if self.rows and self.rows[-1][1:]==row:self.rows[-1][0]+=1
        else:self.rows.append([1,*row])
        self.events['transfers']+=int(pre['transfer']);self.events['accepted']+=g.accepted;self.events['rejected']+=g.rejected;self.events['actual_applications']+=g.applied
        if self.failure:self.events[['none','mismatch','incoherent','period','witness','overrun','ineligible','unexpected_disarm'][self.code]]+=1
        if label:self.cover[label]=self.cover.get(label,0)+1
        return dict(zip(FIELDS,expected))

def stimuli(c,w,t):
    o=Oracle(c,w,t);cm=o.cm;tm=o.c.tm;tagmax=o.tagmask
    def hold(n,**kw):
        for _ in range(n):o.step(**kw)
    def begin(p,hs,tag=0,levels=0,loopback=0):
        o.step(rst=1,levels=levels,loopback=loopback)
        o.step(valid=1,p=p,hs=hs,tag=tag,levels=levels,loopback=loopback)
        o.step(levels=levels,loopback=loopback)
        r=o.step(levels=levels,loopback=loopback)
        assert r['window_started']==int(p>=2 and all(0<h<p for h in hs))
        return r
    def waves(p,hs,n=None,ready=1,label=None):
        for i in range(n if n is not None else 2*p+2):
            o.step(levels=sum(int(i%p<h)<<lane for lane,h in enumerate(hs)),ready=ready,label=label if i==0 else None)
    # Explicit literal independent schedule, not inferred from the PWM output.
    if cm>=3 and tm>=5:
        begin(3,(1,2,1),tagmax,levels=7)
        got=[o.step(levels=v) for v in (0,7,2,0,7)]
        assert [got[-1][x] for x in ['out_valid','out_period','out_high0','out_high1','out_high2','out_start','out_end']]==[1,3,1,2,1,2,5]
        o.step(levels=7,label='literal_first_handshake')
    if c<=3 and w==6:
        for p in range(1,cm+1):
            for hs in itertools.product(range(p+1),repeat=3):
                measurable=p>=2 and all(0<h<p for h in hs);before=o.events['handshakes']
                begin(p,hs,(p*65537+sum(hs))&tagmax)
                if measurable:waves(p,hs,label='eligible_tuple')
                else:hold(2*p+2,levels=7,label='ineligible_tuple_sample')
                delta=o.events['handshakes']-before
                assert (delta>=1) if measurable else(delta==0)
                o.scenarios.append({'kind':'small_legal_tuple','p':p,'highs':hs,'measurable':measurable,'handshakes':delta})
        assert len(o.scenarios)==sum((p+1)**3 for p in range(1,cm+1))
    # Separate actual registered-PWM digital loopback, full post-application cycle.
    for p,hs in [(2,(1,1,1)),(3,(1,2,1)),(min(cm,7),(1,max(1,min(cm,7)//2),min(cm,7)-1))]:
        if p>cm:continue
        begin(p,hs,tagmax,loopback=1);before=o.events['handshakes']
        hold(3*p+4,loopback=1,label='actual_internal_digital_loopback')
        if tm>=3*p+4:assert o.events['handshakes']>before
        if w==2 and p==2:assert o.events['handshakes']==before
    # Transfer at every bounded old-frame phase; active can lag matching samples.
    p=min(cm,7);hs=(1,max(1,p//2),p-1)
    for phase in range(p):
        for same in (False,True):
            begin(p,hs,tagmax,loopback=1);hold(phase,loopback=1)
            q,h=(p,hs) if same else(2,(1,1,1))
            o.step(valid=1,p=q,hs=h,tag=tagmax,loopback=1,ready=1,label='transfer_each_frame_phase')
            # Independent new waveform begins now, while the old command may remain active.
            waves(q,h,n=3*p+3*q+5,label='new_wave_before_actual_application')
    # A new T on the old application's observation edge prevents old binding.
    for illegal in (False,True):
        o.step(rst=1);o.step(valid=1,p=3,hs=(1,2,1),tag=tagmax);o.step()
        r=o.step(valid=1,p=0 if illegal else 2,hs=(0,0,0) if illegal else(1,1,1),tag=tagmax,levels=7,label='transfer_at_observed_applied')
        assert not r['window_started'] and not r['out_valid']
        waves(2,(1,1,1),n=30)
    # A queued matched old record must never handshake with a new T, including ABA.
    if tm>=6:
        for p,hs in [(2,(1,1,1)),(3,(1,2,1))]:
            for tag in (0,tagmax):
                for mode in ('same','changed','illegal'):
                    begin(p,hs,tag)
                    waves(p,hs,n=p+1,ready=0)
                    assert o.c.queue is not None and o.controls(0,0,0,0)['valid']
                    n,h=(p,hs) if mode=='same' else((3,(2,1,2)) if mode=='changed' else(0,(0,0,0)))
                    r=o.step(valid=1,p=n,hs=h,tag=tag,levels=0,ready=1,label='old_ready_slot_'+mode)
                    assert r['pre_valid']==0 and r['out_valid']==0
                    waves(p,hs,n=4*p+10)
    # Partial windows discarded at each bounded prefix; same-tag same-tuple reapply.
    for cut in range(2*p+4):
        begin(p,hs,tagmax);waves(p,hs,n=cut,ready=0)
        o.step(valid=1,p=p,hs=hs,tag=tagmax,levels=7,ready=1,label='partial_or_slot_ABA')
        waves(p,hs,n=3*p+4)
    # Rapid transfers and held-valid: accepted/pending/actual-applied stay distinct.
    begin(2,(1,1,1),tagmax)
    for i in range(60):o.step(valid=1,p=2+(i%2),hs=(1,1,1),tag=tagmax,levels=7 if i%2 else 0,label='held_valid_rapid_replacement')
    waves(2,(1,1,1),n=30)
    # Every bounded phase, STOP/reset and simultaneous controls outrank transfer.
    p=min(cm,5);hs=(1,max(1,p//2),p-1)
    for action in ('rst','stop'):
        for ready in (0,1):
            for cut in range(2*p+4):
                begin(p,hs,tagmax);waves(p,hs,n=cut,ready=0)
                r=o.step(valid=1,p=p,hs=hs,tag=tagmax,levels=7,ready=ready,**{action:1},label='abort_'+action)
                assert not r['pre_valid'] and not r['window_active']
                waves(p,hs,n=2*p+3)
    for mask in range(1,4):
        begin(2,(1,1,1),tagmax)
        hold(7,rst=mask&1,stop=(mask>>1)&1,valid=1,p=2,hs=(1,1,1),levels=7,label='held_abort_priority')
        waves(2,(1,1,1),n=10)
    # Raw incorrect counts are visible but never externally valid.
    if cm>=3 and tm>=7:
        for badp,badhs in [(2,(1,1,1)),(3,(2,2,1)),(3,(1,1,1)),(3,(1,2,2))]:
            begin(3,(1,2,1),tagmax);before=o.events['mismatch'];waves(badp,badhs)
            assert o.events['mismatch']>before
            waves(3,(1,2,1),n=15);assert not o.bound
            o.step(valid=1,p=3,hs=(1,2,1),tag=tagmax,levels=0,label='new_application_recovery');waves(3,(1,2,1),n=18)
    for offsets in [(0,1,2),(0,0,1),(2,1,0)]:
        p=min(cm,3);begin(p,(1,1,1),tagmax)
        for i in range(20):o.step(levels=sum(int((i+off)%p<1)<<lane for lane,off in enumerate(offsets)),label='phase_shifted_sample')
    for shape in [(7,6,7,0,7),(7,0,1,0,7),(7,3,1,0,4,6,7),(7,7,7,7,7),(0,0,0,0,0)]:
        begin(min(cm,3),(1,1,1),tagmax)
        for v in shape:o.step(levels=v,ready=0,label='extra_missing_constant_sample')
        hold(12,levels=0,ready=1)
    # Full slot stall, matched refill, overrun closure and no spontaneous recovery.
    for ready_after in (0,1):
        begin(2,(1,1,1),tagmax);waves(2,(1,1,1),n=5,ready=0,label='slot_overrun')
        hold(4,levels=0,ready=ready_after)
        waves(2,(1,1,1),n=12)
        assert not o.bound
    if tm>=6:
        begin(2,(1,1,1),tagmax);waves(2,(1,1,1),n=3,ready=0)
        o.step(levels=0,ready=0);o.step(levels=7,ready=1,label='old_retire_new_refill');o.step(levels=0)
        begin(2,(1,1,1),tagmax);waves(2,(1,1,1),n=3,ready=0)
        o.step(levels=0,ready=0);o.step(levels=1,ready=1,label='old_retire_before_new_fault');hold(4,levels=0)
    # True namespace exhaustion with an old complete slot; invalid after new fault.
    if w<=6:
        for ready in (0,1):
            begin(2,(1,1,1),tagmax);hold(max(0,tm-3),levels=0,ready=0)
            waves(2,(1,1,1),n=3,ready=0)
            r=o.step(levels=7,ready=ready,label='witness_exhaustion_old_record')
            assert r['raw_fault_events']==4 and r['out_valid']==0
            hold(4,levels=0,ready=1)
            o.step(valid=1,p=2,hs=(1,1,1),tag=tagmax,levels=0,label='witness_new_application_recovery');hold(3,levels=0);waves(2,(1,1,1),n=9)
        begin(2,(1,1,1));hold(tm+5,levels=0,label='no_edge_witness_exhaustion')
    # Period overflow and an existing complete record retiring on the fault edge.
    if c<=16 and tm>=2*cm+6:
        for full in (False,True):
            begin(cm,(1,1,1),tagmax)
            if full:waves(cm,(1,1,1),n=cm+1,ready=0)
            else:o.step(levels=7,ready=0)
            hold(cm,levels=0,ready=0)
            r=o.step(levels=7,ready=int(full),label='full_count_overflow')
            assert r['raw_fault_events']==2 and r['out_valid']==0
            hold(4,levels=0)
    if c==16:
        for p,hs in [(32768,(1,16384,32767)),(65535,(1,32768,65534))]:
            begin(p,hs,tagmax);before=o.events['handshakes'];waves(p,hs,n=2*p+2,label='fully_observed16_period')
            assert o.events['handshakes']>before
    if c==32:
        for p,hs in [(127,(1,63,126)),(4096,(2048,1,4095))]:
            begin(p,hs,tagmax);waves(p,hs,label='bounded32_full_small_frame')
        for p in (0x7fffffff,0x80000000,0xfffffffe,0xffffffff):
            begin(p,(1,p//2,p-1),tagmax);hold(260,loopback=1,label='bounded32_partial_only');o.step(stop=1)
    rng=random.Random(0x152026+c*10000+w*100+t)
    for i in range(8000):
        q=rng.randrange(0,min(cm,9)+1);h=tuple(rng.randrange(0,min(cm,10)+1) for _ in range(3))
        if i%3==0:h=tuple(min(q,x) for x in h)
        o.step(rst=int(i%409==0),stop=int(i%151==0),valid=int(rng.random()<.2),p=q,hs=h,tag=rng.getrandbits(t),levels=rng.randrange(8),loopback=int(i%200<90),ready=int(rng.random()<.55),label='random_sample')
    o.step(rst=1);o.step();assert o.events['unexpected_disarm']==0
    return o

def vector_bytes(o):return (str(len(o.rows))+'\n'+'\n'.join(' '.join(format(x,'x') for x in row) for row in o.rows)+'\n').encode('ascii')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rtl',type=Path);ap.add_argument('--generator',type=Path);ap.add_argument('--capture',type=Path);ap.add_argument('--tb',type=Path,required=True);ap.add_argument('--tool',type=Path,default=Path('D:/modelsim1/win64'));ap.add_argument('--out',type=Path,required=True);ap.add_argument('--owned-root',type=Path,required=True);ap.add_argument('--cases',default='2:6:1,3:6:64,2:2:64,3:3:32,16:18:64,32:64:64');ap.add_argument('--freeze-only',action='store_true');ap.add_argument('--frozen',type=Path);ap.add_argument('--negative',action='store_true');a=ap.parse_args()
    out=a.out.resolve();owned=a.owned_root.resolve();assert out.is_relative_to(owned) and out!=owned and not out.exists();out.mkdir(parents=True)
    r={'operation_id':'B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'oracle':'absolute generator frame deadlines plus independently sampled first-fall event indices; explicit application boundary context','runner_sha256':sha(Path(__file__)),'tb_sha256':sha(a.tb),'fields':FIELDS,'inputs':INPUTS,'commands':[],'runs':[],'status':'started','full32_count_and64_witness_traversal':False}
    def save():(out/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
    def run(name,cmd):
        cmd=[str(x) for x in cmd]
        try:p=subprocess.run(cmd,cwd=out,capture_output=True,timeout=240,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        except subprocess.TimeoutExpired as e:
            (out/(name+'.stdout.txt')).write_bytes(e.stdout or b'');(out/(name+'.stderr.txt')).write_bytes(e.stderr or b'');r['commands'].append({'name':name,'command':cmd,'cwd':str(out),'timeout':240,'exit_code':None});save();raise
        (out/(name+'.stdout.txt')).write_bytes(p.stdout);(out/(name+'.stderr.txt')).write_bytes(p.stderr)
        r['commands'].append({'name':name,'command':cmd,'cwd':str(out),'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()});save();return p
    try:
        shutil.copyfile(Path(__file__),out/'runner.py');shutil.copyfile(a.tb,out/'tb.sv')
        if not a.freeze_only:
            assert a.rtl and a.generator and a.capture and a.frozen
            f=json.loads((a.frozen/'result.json').read_bytes());assert f['status']=='oracle_frozen' and f['runner_sha256']==r['runner_sha256'] and f['tb_sha256']==r['tb_sha256']
            r['frozen_receipt_sha256']=sha(a.frozen/'result.json');r['source_hashes']={}
            for path,name in [(a.rtl,'dut.sv'),(a.generator,'generator.sv'),(a.capture,'capture.sv')]:r['source_hashes'][name]=sha(path);shutil.copyfile(path,out/name)
            assert r['source_hashes']['generator.sv']=='9dc8ecf96e59a2ae8467bda64572f62eb602d52db535733f236f64ff97c43428'
            assert r['source_hashes']['capture.sv']=='4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456'
            for exe in ('vlog','vsim'):assert run(exe+'-version',[a.tool/(exe+'.exe'),'-version']).returncode==0
            assert run('vlib',[a.tool/'vlib.exe','work']).returncode==0
            p=run('vlog',[a.tool/'vlog.exe','-sv','-work','work','generator.sv','capture.sv','dut.sv','tb.sv']);assert p.returncode==0 and not re.search(rb'\*\* (?:Error|Fatal)',p.stdout+p.stderr)
        for case in a.cases.split(','):
            c,w,t=map(int,case.split(':'));o=stimuli(c,w,t);label='c%d_w%d_t%d'%(c,w,t);v=out/(label+'.vectors.txt');v.write_bytes(vector_bytes(o));ports=out/(label+'.ports.txt')
            rec={'count_w':c,'witness_w':w,'tag_w':t,'sampled_edges':o.now+1,'rle_rows':len(o.rows),'coverage_label_samples':o.cover,'legal_tuple_scenarios':o.scenarios,'expected_events':o.events,'raw_events':o.c.events,'vectors_sha256':sha(v)};r['runs'].append(rec);save()
            if a.freeze_only:continue
            assert sha(v)==sha(a.frozen/v.name),'changed frozen input'
            do=out/(label+'.do');do.write_bytes(b'onerror {quit -code 1}\nrun -all\nquit -code 0\n')
            p=run(label,[a.tool/'vsim.exe','-c','-onfinish','stop','work.main_tb_pwm_applied_capture','-gCOUNT_W='+str(c),'-gWITNESS_W='+str(w),'-gTAG_W='+str(t),'+VECTORS='+v.name,'+TRACE='+ports.name,'-do',do.name]);raw=p.stdout+p.stderr
            passed=p.returncode==0 and b'MAIN_APPLIED_CAPTURE_PASS' in raw and not re.search(rb'\*\* (?:Error|Fatal)',raw);rec.update(passed=passed,ports_sha256=sha(ports) if ports.exists() else None);save()
            if a.negative:
                assert not passed and b'PUBLIC_PORT_MISMATCH' in raw;r['status']='expected_public_port_rejection';save();print(json.dumps({'status':r['status'],'out':str(out)}));return
            assert passed,label
            lines=ports.read_text().splitlines();assert len(lines)==len(o.rows);edges=0
            for i,(line,row) in enumerate(zip(lines,o.rows)):
                edges+=row[0];got=line.split();assert [int(x) for x in got[:3]]==[i,edges,row[0]] and [int(x,16) for x in got[3:]]==row[1+len(INPUTS):]
        if a.freeze_only:r['status']='oracle_frozen';r['provenance_requires_main_receipt']=True
        else:
            r['invalid_parameters']=[]
            for c,w,t in [(1,8,32),(33,8,32),(0,8,32),(-1,8,32),(3,1,32),(3,65,32),(3,0,32),(3,-1,32),(3,8,0),(3,8,-1),(3,8,65)]:
                label='invalid_c%d_w%d_t%d'%(c,w,t);p=run(label,[a.tool/'vsim.exe','-c','-onfinish','stop','work.main_tb_pwm_applied_capture','-gCOUNT_W='+str(c),'-gWITNESS_W='+str(w),'-gTAG_W='+str(t),'+VECTORS='+v.name,'+TRACE='+label+'.ports.txt','-do',do.name]);raw=p.stdout+p.stderr
                fatal=re.search(rb'\*\* Fatal:[^\r\n]*',raw);assert fatal and b'MAIN_APPLIED_CAPTURE_PASS' not in raw
                # Guard name is an implementation detail; require this wrapper's name
                # and all three exact values before/in its own fatal diagnostic.
                before=raw[:fatal.end()];assert b'APPLIED' in fatal.group().upper() and b'PARAM' in fatal.group().upper()
                for key,value in [('COUNT_W',c),('WITNESS_W',w),('TAG_W',t)]:assert (key+'='+str(value)).encode() in before
                r['invalid_parameters'].append({'count_w':c,'witness_w':w,'tag_w':t,'explicit_guard':True,'exit_code':p.returncode})
            r['status']='passed'
        save();print(json.dumps({'status':r['status'],'out':str(out),'samples':sum(x['sampled_edges'] for x in r['runs']),'rows':sum(x['rle_rows'] for x in r['runs']),'runner_sha256':r['runner_sha256'],'tb_sha256':r['tb_sha256']}))
    except Exception as e:r.update(status='failed',error=repr(e));save();raise
if __name__=='__main__':main()
