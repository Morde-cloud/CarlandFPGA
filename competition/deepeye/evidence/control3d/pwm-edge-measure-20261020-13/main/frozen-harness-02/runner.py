"""Main independent absolute-event-index oracle, op13. No author/generator import.
H01-H15 DEEPEYE-HUMAN-LOCK-20261014/r1 requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
Synchronous binary samples only; queued data is not liveness or motion authority.
"""
import argparse,datetime,hashlib,json,os,random,re,shutil,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class Reference:
    def __init__(self,w,t):
        self.limit=(1<<w)-1;self.tm=(1<<t)-1;self.index=-1
        self.armed=False;self.previous=0;self.start=self.fall=None;self.tag=0
        self.queue=None;self.os=self.rs=self.loss=0;self.rows=[];self.cover={};self.events={'records':0,'retired':0,'overflow':0,'overrun':0}
    def sample(self,level=0,ready=1,reset=0,stop=0,rearm=0,tag=0,label=None):
        self.index+=1;now=self.index
        pre=int(self.queue is not None and not (reset or stop or rearm));ov=rr=0
        if reset or stop or rearm:
            self.armed=bool(rearm and not(reset or stop));self.previous=level if self.armed else 0
            self.tag=(tag&self.tm) if self.armed else 0
            self.start=self.fall=self.queue=None;self.os=self.rs=self.loss=0
        elif self.armed:
            rise=bool(level and not self.previous);fall=bool(self.previous and not level)
            self.previous=level
            if self.queue is not None and ready:self.queue=None;self.events['retired']+=1
            if self.start is not None and now-self.start>self.limit:
                ov=1;self.os=1;self.start=now if rise else None;self.fall=None
            elif rise:
                if self.start is not None:
                    assert self.fall is not None
                    p=now-self.start;h=self.fall-self.start
                    assert 1<=h<p<=self.limit
                    if self.queue is None:self.queue=(p,h,self.tag);self.events['records']+=1
                    else:rr=1;self.rs=1
                self.start=now;self.fall=None
            elif fall and self.start is not None:self.fall=now
            if ov or rr:self.loss=min(self.limit,self.loss+1)
        self.events['overflow']+=ov;self.events['overrun']+=rr
        payload=self.queue or (0,0,0)
        exp=[pre,int(self.armed),int(self.queue is not None and not(reset or stop or rearm)),*payload,ov,rr,self.os,self.rs,self.loss]
        row=[reset,stop,rearm,level,tag&self.tm,ready,*exp]
        if self.rows and self.rows[-1][1:]==row:self.rows[-1][0]+=1
        else:self.rows.append([1,*row])
        if label:self.cover[label]=self.cover.get(label,0)+1
        return exp

def stimuli(w,t):
    o=Reference(w,t);m=o.limit;tm=o.tm
    def init(level=0,tag=tm):o.sample(reset=1,level=level);o.sample(rearm=1,level=level,tag=tag)
    def hold(level,n,**kw):
        for _ in range(n):o.sample(level=level,**kw)
    def cycles(p,h,n=3,ready=1,label=None):
        for i in range(n*p+1):o.sample(level=int(i%p<h),ready=ready,tag=tm,label=label if i==0 else None)
    pairs=[(p,h) for p in range(2,m+1) for h in range(1,p)] if w<=4 else ([(2,1),(32768,1),(32769,32768),(65535,1),(65535,32768),(65535,65534)] if w==16 else [(2,1),(3,2),(17,1),(127,126),(4096,2048)])
    for p,h in pairs:
        init(tag=(p*17+h)&tm);cycles(p,h,n=2,label='complete_period_high_pair');o.sample(stop=1)
    # Constant levels without an R0: no absence watchdog.
    for lev in [0,1]:
        init(lev);hold(lev,2*m+3 if w<=16 else 20000,label='no_start_constant')
        o.sample(level=0);o.sample(level=1);o.sample(level=0);o.sample(level=1,label='fresh_after_constant');o.sample(stop=1)
    # Directed MAX+1 overflow, fresh-rising on overflowing edge, and recovery.
    if w<=16:
        for kind in ['high','low','rise_on_overflow']:
            init();o.sample(level=1)
            for d in range(1,m+2):
                lev=1 if kind=='high' or (kind=='rise_on_overflow' and d==m+1) else 0
                o.sample(level=lev,label='overflow_'+kind if d==m+1 else None)
            hold(0,3);cycles(2,1,n=2);o.sample(stop=1)
        # A valid old record remains queued while a distinct partial overflows.
        # Readiness is varied on precisely that overflow edge.
        for pop in [0,1]:
            init();cycles(2,1,n=1,ready=0)
            hold(1,m,ready=0)
            o.sample(level=1,ready=pop,label='old_record_vs_overflow_ready'+str(pop))
            o.sample(level=1,ready=0);o.sample(rearm=1,level=1,tag=0);hold(1,5)
            o.sample(level=0);cycles(2,1,n=2);o.sample(stop=1)
    # Abort/baseline at every point across idle/high/low/completion/retirement.
    p=min(m,7);h=max(1,p//2)
    for action in ['reset','stop','rearm']:
        for ready in [0,1]:
            for cut in range(3*p+3):
                init();
                for i in range(cut):o.sample(level=int(i%p<h),ready=ready,tag=i&tm)
                o.sample(level=int(cut%p<h),ready=ready,tag=0,label='abort_'+action,**{action:1})
                for i in range(2*p+3):o.sample(level=int((cut+i+1)%p<h),ready=ready,tag=tm)
                o.sample(rearm=1,level=1,tag=tm);hold(1,2)
                o.sample(level=0);cycles(2,1,n=2);o.sample(stop=1)
    # Priority combinations, held controls, and changing tags without rearm.
    for mask in range(1,8):
        init();cycles(2,1,n=1,ready=0)
        for i in range(5):o.sample(reset=mask&1,stop=(mask>>1)&1,rearm=(mask>>2)&1,level=i%2,tag=tm if i%2 else 0,ready=1,label='control_priority')
        cycles(2,1,n=3);o.sample(stop=1)
    # Repeated overflow and overrun saturate small-width loss; pulses continue.
    if w<=4:
        init();cycles(2,1,n=m+5,ready=0,label='overrun_saturation')
        for k in range(m+3):
            hold(1,m+2,ready=0);o.sample(level=0,ready=0);o.sample(level=1,ready=0,label='mixed_loss_saturation')
        o.sample(ready=1);o.sample(rearm=1,tag=0);cycles(2,1,n=2)
    # Same-edge retirement/refill and no bypass from an old empty slot.
    init();cycles(2,1,n=8,ready=0,label='stall');o.sample(level=0,ready=0)
    o.sample(level=1,ready=1,label='simultaneous_retire_refill');o.sample(level=1,ready=1)
    for i in range(20):o.sample(level=i%2,ready=(i//2)%2,tag=i&tm,label='ready_alternation')
    # Deterministic externally driven schedules, not generated RTL feedback.
    rng=random.Random(0x13002026+w*64+t);level=0
    for i in range(12000):
        if rng.randrange(7)==0:level^=1
        o.sample(level=level,ready=int(rng.random()<.42),reset=int(i%1013==0),stop=int(i%379==0),rearm=int(i%197==0),tag=rng.getrandbits(t),label='random_sample')
    o.sample(reset=1);o.sample()
    return o

def vector_bytes(o):return (str(len(o.rows))+'\n'+'\n'.join(' '.join(format(x,'x') for x in row) for row in o.rows)+'\n').encode('ascii')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rtl',type=Path);ap.add_argument('--tb',type=Path,required=True);ap.add_argument('--tool',type=Path,default=Path('D:/modelsim1/win64'))
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--owned-root',type=Path,required=True);ap.add_argument('--cases',default='2:1,3:64,4:32,16:64,32:64');ap.add_argument('--freeze-only',action='store_true');ap.add_argument('--frozen',type=Path);ap.add_argument('--negative',action='store_true');a=ap.parse_args()
    out=a.out.resolve();owned=a.owned_root.resolve();assert out.is_relative_to(owned) and out!=owned and not out.exists();out.mkdir(parents=True)
    r={'operation_id':'B-DEEPEYE-PWM-EDGE-MEASURE-20261020-13','created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'oracle':'absolute sample indices, first fall, one result queue','runner_sha256':sha(Path(__file__)),'tb_sha256':sha(a.tb),'commands':[],'runs':[],'status':'started','32bit_limit_claim':'bounded functional samples only; no full max32 period or overflow executed'}
    def save():(out/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
    def run(name,cmd):
        cmd=[str(x) for x in cmd]
        try:p=subprocess.run(cmd,cwd=out,capture_output=True,timeout=180,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        except subprocess.TimeoutExpired as e:
            (out/(name+'.stdout.txt')).write_bytes(e.stdout or b'');(out/(name+'.stderr.txt')).write_bytes(e.stderr or b'');r['commands'].append({'command':cmd,'name':name,'exit_code':None,'timeout':180});save();raise
        (out/(name+'.stdout.txt')).write_bytes(p.stdout);(out/(name+'.stderr.txt')).write_bytes(p.stderr)
        r['commands'].append({'command':cmd,'name':name,'cwd':str(out),'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()});save();return p
    try:
        shutil.copyfile(Path(__file__),out/'runner.py');shutil.copyfile(a.tb,out/'tb.sv')
        if not a.freeze_only:
            assert a.rtl and a.frozen
            f=json.loads((a.frozen/'result.json').read_bytes());assert f['status']=='oracle_frozen' and f['runner_sha256']==r['runner_sha256'] and f['tb_sha256']==r['tb_sha256']
            r['frozen_receipt_sha256']=sha(a.frozen/'result.json');r['rtl_sha256']=sha(a.rtl);shutil.copyfile(a.rtl,out/'dut.sv')
            for exe in ['vlog','vsim']:assert run(exe+'-version',[a.tool/(exe+'.exe'),'-version']).returncode==0
            assert run('vlib',[a.tool/'vlib.exe','work']).returncode==0
            cp=run('vlog',[a.tool/'vlog.exe','-sv','-work','work','dut.sv','tb.sv']);assert cp.returncode==0 and not re.search(rb'\*\* (?:Error|Fatal)',cp.stdout+cp.stderr)
        for case in a.cases.split(','):
            w,t=map(int,case.split(':'));o=stimuli(w,t);label='w%d_t%d'%(w,t);v=out/(label+'.vectors.txt');v.write_bytes(vector_bytes(o));port=out/(label+'.ports.txt')
            rec={'count_w':w,'tag_w':t,'sampled_edges':o.index+1,'rle_rows':len(o.rows),'coverage':o.cover,'expected_events':o.events,'vectors_sha256':sha(v)};r['runs'].append(rec);save()
            if a.freeze_only:continue
            assert sha(v)==sha(a.frozen/v.name),'stimulus changed since independent freeze'
            do=out/(label+'.do');do.write_bytes(b'onerror {quit -code 1}\nrun -all\nquit -code 0\n')
            cp=run(label,[a.tool/'vsim.exe','-c','-onfinish','stop','work.main_tb_pwm_edge_measure','-gCOUNT_W='+str(w),'-gTAG_W='+str(t),'+VECTORS='+v.name,'+TRACE='+port.name,'-do',do.name]);raw=cp.stdout+cp.stderr
            passed=cp.returncode==0 and b'MAIN_EDGE_MEASURE_PASS' in raw and not re.search(rb'\*\* (?:Error|Fatal)',raw)
            rec.update(passed=passed,ports_sha256=sha(port) if port.exists() else None);save()
            if a.negative:
                assert not passed and b'PUBLIC_PORT_MISMATCH' in raw
                r['status']='expected_public_port_rejection';save();print(json.dumps(r));return
            assert passed,label
            lines=port.read_text().splitlines();assert len(lines)==len(o.rows)
            edges=0
            for i,(line,row) in enumerate(zip(lines,o.rows)):
                edges+=row[0];got=line.split();assert [int(x) for x in got[:3]]==[i,edges,row[0]] and [int(x,16) for x in got[3:]]==row[7:]
        if a.freeze_only:r['status']='oracle_frozen';r['author_implementation_read']=False
        else:
            r['invalid_parameters']=[]
            for w,t in [(1,32),(33,32),(3,0),(3,65)]:
                label='invalid_w%d_t%d'%(w,t);cp=run(label,[a.tool/'vsim.exe','-c','-onfinish','stop','work.main_tb_pwm_edge_measure','-gCOUNT_W='+str(w),'-gTAG_W='+str(t),'+VECTORS='+v.name,'+TRACE='+label+'.ports.txt','-do',do.name]);raw=cp.stdout+cp.stderr
                expected=('PWM_EDGE_UNSUPPORTED_PARAMETERS COUNT_W=%d TAG_W=%d'%(w,t)).encode('ascii')
                assert b'MAIN_EDGE_MEASURE_PASS' not in raw and b'** Fatal:' in raw and expected in raw,'explicit time-zero DUT guard required; elaboration errors alone are insufficient'
                r['invalid_parameters'].append({'count_w':w,'tag_w':t,'rejected':True,'exit_code':cp.returncode})
            r['status']='passed'
        save();print(json.dumps(r))
    except Exception as e:r.update(status='failed',error=repr(e));save();raise
if __name__=='__main__':main()
