"""Op14 main reference: absolute observed edge indices, never generator/author state.
H01-H15 requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
Raw common-edge witnesses are local to a rearm window, not source/motion authority.
"""
import argparse,datetime,hashlib,itertools,json,os,random,re,shutil,subprocess
from pathlib import Path
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class Reference:
    def __init__(self,c,w,t):
        self.cm=(1<<c)-1;self.tm=(1<<w)-1;self.tagmask=(1<<t)-1;self.now=-1
        self.armed=False;self.previous=0;self.origin=None;self.start=None;self.falls=[None]*3
        self.tag=0;self.queue=None;self.seen=[0]*4;self.faults=0;self.rows=[];self.cover={}
        self.events=dict(candidates=0,admitted=0,retired=0,starts=0,incoherent=0,period_overflow=0,witness_overflow=0,overrun=0)
    def sample(self,levels=0,ready=1,reset=0,stop=0,rearm=0,tag=0,label=None):
        self.now+=1;now=self.now;abort=bool(reset or stop or rearm)
        pre=int(self.queue is not None and not abort);pulses=[0]*4;fault=None
        if abort:
            self.armed=bool(rearm and not(reset or stop));self.previous=levels if self.armed else 0
            self.origin=now if self.armed else None;self.tag=(tag&self.tagmask) if self.armed else 0
            self.start=self.queue=None;self.falls=[None]*3;self.seen=[0]*4;self.faults=0
        else:
            # Queue consumption is independent of acquisition, including halted windows.
            if self.queue is not None and ready:self.queue=None;self.events['retired']+=1
            if self.armed:
                tick=now-self.origin
                if tick>self.tm:
                    fault=2;self.armed=False;self.start=None;self.falls=[None]*3
                else:
                    rise=(~self.previous)&levels&7;fall=self.previous&(~levels)&7;self.previous=levels
                    if self.start is not None and now-self.start>self.cm:
                        fault=1;self.start=now if rise==7 else None;self.falls=[None]*3
                        if rise==7:self.events['starts']+=1
                    elif self.start is None:
                        if rise==7:self.start=now;self.falls=[None]*3;self.events['starts']+=1
                        elif rise:fault=0
                    elif rise==7:
                        if all(f is not None and self.start<f<now for f in self.falls):
                            period=now-self.start;highs=[f-self.start for f in self.falls]
                            assert 1<=min(highs)<=max(highs)<period<=self.cm
                            candidate=(period,*highs,self.start-self.origin,tick,self.tag)
                            self.events['candidates']+=1
                            if self.queue is None:self.queue=candidate;self.events['admitted']+=1
                            else:fault=3
                        else:fault=0
                        self.start=now;self.falls=[None]*3;self.events['starts']+=1
                    elif rise:
                        fault=0;self.start=None;self.falls=[None]*3
                    else:
                        for lane in range(3):
                            if fall&(1<<lane) and self.falls[lane] is None:self.falls[lane]=now
            if fault is not None:
                pulses[fault]=1;self.seen[fault]=1;self.faults=min(self.cm,self.faults+1)
                self.events[['incoherent','period_overflow','witness_overflow','overrun'][fault]]+=1
        payload=self.queue or (0,)*7
        expected=[pre,int(self.armed),int(self.queue is not None and not abort),*payload,*pulses,*self.seen,self.faults]
        assert len(expected)==19 and sum(pulses)<=1
        row=[reset,stop,rearm,levels,tag&self.tagmask,ready,*expected]
        if self.rows and self.rows[-1][1:]==row:self.rows[-1][0]+=1
        else:self.rows.append([1,*row])
        if label:self.cover[label]=self.cover.get(label,0)+1
        return expected

def stimuli(c,w,t):
    o=Reference(c,w,t);cm=o.cm;tm=o.tm;tagmax=o.tagmask
    def init(levels=0,tag=tagmax):o.sample(reset=1,levels=levels);o.sample(rearm=1,levels=levels,tag=tag)
    def hold(levels,n,**kw):
        for _ in range(n):o.sample(levels=levels,**kw)
    def cycles(period,highs,n=2,ready=1,label=None):
        for i in range(n*period+1):o.sample(levels=sum(int(i%period<h)<<lane for lane,h in enumerate(highs)),ready=ready,tag=tagmax,label=label if i==0 else None)
    if c<=3 and tm>=2*cm+1:
        for p in range(2,cm+1):
            for hs in itertools.product(range(1,p),repeat=3):
                init(tag=(p*19+sum(hs))&tagmax);cycles(p,hs,label='all_small_high_triple');o.sample(stop=1)
    elif c==16:
        for p,hs in [(2,(1,1,1)),(32768,(1,16384,32767)),(32769,(32768,2,1)),(65535,(1,32768,65534))]:
            init();cycles(p,hs,label='full16_period_and_highs');o.sample(stop=1)
    elif c==32:
        for p,hs in [(2,(1,1,1)),(3,(1,2,1)),(17,(16,8,1)),(127,(1,63,126)),(4096,(2048,1,4095))]:
            init();cycles(p,hs,label='bounded32_period_and_highs');o.sample(stop=1)
    # Independently phase-shifted equal periods have no common R0/R1.
    p=min(cm,5)
    for offsets in [(0,1,2),(0,0,1),(2,1,0)]:
        init()
        for i in range(10*p):o.sample(levels=sum(int((i+off)%p<1)<<lane for lane,off in enumerate(offsets)),label='equal_period_phase_shift' if i==0 else None)
        o.sample(stop=1)
    # Shared start, all falls, then unequal end edges: a relaxed-R1 mutant lies here.
    for shape in [[7,6,4,0,1,3,7],[7,0,1,0,7],[7,6,7,0,7],[7,3,1,0,4,6,7]]:
        init()
        for level in shape:o.sample(levels=level,ready=0,label='unequal_or_extra_edges')
        o.sample(levels=0);cycles(2,(1,1,1),n=2);o.sample(stop=1)
    # Count overflow and a fresh common rise on the overflow edge.
    if c<=16 and tm>=cm+6:
        for mode in ['all_high','missing_lane','all_low','rise_on_overflow']:
            init();o.sample(levels=7)
            for elapsed in range(1,cm+2):
                level=7 if mode=='all_high' or(mode=='rise_on_overflow' and elapsed==cm+1) else (4 if mode=='missing_lane' else 0)
                o.sample(levels=level,ready=0,label='period_overflow_'+mode if elapsed==cm+1 else None)
            o.sample(levels=0);cycles(2,(1,1,1),n=2);o.sample(stop=1)
    # No-start constants do not create an acquisition watchdog.
    for level in [0,7,4]:
        init(levels=level);n=cm+3 if c<=16 and tm>cm+8 else min(tm+2,1000)
        hold(level,n,label='constant_baseline')
        o.sample(rearm=1,levels=7,tag=0)
        for level in [6,4,0,7,0,7]:o.sample(levels=level,label='fresh_start_after_high_rearm')
        o.sample(stop=1)
    # Namespace boundary: completed old queue transport continues when disarmed.
    if w<=6:
        for ready_at_exhaustion in [0,1]:
            init();o.sample(levels=7,ready=0);o.sample(levels=0,ready=0);o.sample(levels=7,ready=0)
            hold(7,max(0,tm-3),ready=0)
            o.sample(levels=7,ready=ready_at_exhaustion,label='witness_overflow_old_queue')
            hold(0,4,ready=0);o.sample(levels=7,ready=1,label='retire_while_unarmed')
            o.sample(rearm=1,levels=7,tag=tagmax);o.sample(levels=0);cycles(2,(1,1,1),n=1)
        init()
        hold(0,tm+5,label='idle_namespace_exhaustion')
    if c==2 and w==3:
        init();hold(0,3);o.sample(levels=7);hold(0,3)
        o.sample(levels=7,ready=0,label='witness_over_count_priority')
        hold(0,3);o.sample(stop=1)
    # Every bounded phase with all three explicit abort controls and both readiness values.
    p=min(cm,5);hs=(1,max(1,p//2),p-1)
    for action in ['reset','stop','rearm']:
        for ready in [0,1]:
            for cut in range(2*p+3):
                init()
                for i in range(cut):o.sample(levels=sum(int(i%p<h)<<lane for lane,h in enumerate(hs)),ready=ready,tag=i&tagmax)
                level=sum(int(cut%p<h)<<lane for lane,h in enumerate(hs))
                o.sample(levels=level,ready=ready,tag=0,label='abort_'+action,**{action:1})
                for i in range(2*p+3):o.sample(levels=sum(int((cut+i+1)%p<h)<<lane for lane,h in enumerate(hs)),ready=ready,tag=tagmax)
                o.sample(rearm=1,levels=7,tag=tagmax);o.sample(levels=0);cycles(2,(1,1,1),n=1);o.sample(stop=1)
    for mask in range(1,8):
        init();cycles(2,(1,1,1),n=1,ready=0)
        for i in range(5):o.sample(reset=mask&1,stop=(mask>>1)&1,rearm=(mask>>2)&1,levels=7 if i%2 else 0,ready=1,tag=tagmax if i%2 else 0,label='held_priority_controls')
        cycles(2,(1,1,1),n=2);o.sample(stop=1)
    if c<=3 and tm>=4*cm+12:
        init();cycles(2,(1,1,1),n=cm+5,ready=0,label='overrun_saturation')
        o.sample(levels=0,ready=0);o.sample(levels=7,ready=1,label='retire_refill_after_saturation')
        o.sample(rearm=1,tag=0)
        for _ in range(cm+5):o.sample(levels=1,ready=0,label='incoherent_saturation');o.sample(levels=0,ready=0)
    init();cycles(2,(1,1,1),n=1,ready=0)
    o.sample(levels=0,ready=0);o.sample(levels=7,ready=1,label='same_edge_consume_refill');o.sample(levels=7,ready=1,label='consume_zero_payload')
    rng=random.Random(0x142026+c*10000+w*100+t);level=0
    for i in range(8000):
        if i%100<40:level=sum(int(i%5<h)<<lane for lane,h in enumerate((1,2,4)))
        else:level=rng.randrange(8)
        o.sample(levels=level,ready=int(rng.random()<.43),reset=int(i%401==0),stop=int(i%137==0),rearm=int(i%43==0),tag=rng.getrandbits(t),label='random_sample')
    o.sample(reset=1);o.sample();return o

def vector_bytes(o):return (str(len(o.rows))+'\n'+'\n'.join(' '.join(format(x,'x') for x in row) for row in o.rows)+'\n').encode('ascii')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rtl',type=Path);ap.add_argument('--tb',type=Path,required=True);ap.add_argument('--tool',type=Path,default=Path('D:/modelsim1/win64'));ap.add_argument('--out',type=Path,required=True);ap.add_argument('--owned-root',type=Path,required=True);ap.add_argument('--cases',default='2:6:1,3:6:64,2:2:64,2:3:32,16:17:64,32:64:64');ap.add_argument('--freeze-only',action='store_true');ap.add_argument('--frozen',type=Path);ap.add_argument('--negative',action='store_true');a=ap.parse_args()
    out=a.out.resolve();owned=a.owned_root.resolve();assert out.is_relative_to(owned) and out!=owned and not out.exists();out.mkdir(parents=True)
    r={'operation_id':'B-DEEPEYE-PWM-COHERENT-CAPTURE-20261020-14','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'oracle':'absolute per-lane sample-event indices and local origin; one independent consumer queue','runner_sha256':sha(Path(__file__)),'tb_sha256':sha(a.tb),'commands':[],'runs':[],'status':'started','full32_count_and64_witness_traversal':False}
    def save():(out/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
    def run(name,cmd):
        cmd=[str(x) for x in cmd]
        try:p=subprocess.run(cmd,cwd=out,capture_output=True,timeout=180,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        except subprocess.TimeoutExpired as e:
            (out/(name+'.stdout.txt')).write_bytes(e.stdout or b'');(out/(name+'.stderr.txt')).write_bytes(e.stderr or b'');r['commands'].append({'name':name,'command':cmd,'timeout':180,'exit_code':None});save();raise
        (out/(name+'.stdout.txt')).write_bytes(p.stdout);(out/(name+'.stderr.txt')).write_bytes(p.stderr);r['commands'].append({'name':name,'command':cmd,'cwd':str(out),'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()});save();return p
    try:
        shutil.copyfile(Path(__file__),out/'runner.py');shutil.copyfile(a.tb,out/'tb.sv')
        if not a.freeze_only:
            assert a.rtl and a.frozen
            f=json.loads((a.frozen/'result.json').read_bytes());assert f['status']=='oracle_frozen' and f['runner_sha256']==r['runner_sha256'] and f['tb_sha256']==r['tb_sha256']
            r['frozen_receipt_sha256']=sha(a.frozen/'result.json');r['rtl_sha256']=sha(a.rtl);shutil.copyfile(a.rtl,out/'dut.sv')
            for exe in ['vlog','vsim']:assert run(exe+'-version',[a.tool/(exe+'.exe'),'-version']).returncode==0
            assert run('vlib',[a.tool/'vlib.exe','work']).returncode==0
            p=run('vlog',[a.tool/'vlog.exe','-sv','-work','work','dut.sv','tb.sv']);assert p.returncode==0 and not re.search(rb'\*\* (?:Error|Fatal)',p.stdout+p.stderr)
        for case in a.cases.split(','):
            c,w,t=map(int,case.split(':'));o=stimuli(c,w,t);label='c%d_w%d_t%d'%(c,w,t);v=out/(label+'.vectors.txt');v.write_bytes(vector_bytes(o));ports=out/(label+'.ports.txt')
            rec={'count_w':c,'witness_w':w,'tag_w':t,'sampled_edges':o.now+1,'rle_rows':len(o.rows),'coverage':o.cover,'expected_events':o.events,'vectors_sha256':sha(v)};r['runs'].append(rec);save()
            if a.freeze_only:continue
            assert sha(v)==sha(a.frozen/v.name),'changed frozen input'
            do=out/(label+'.do');do.write_bytes(b'onerror {quit -code 1}\nrun -all\nquit -code 0\n')
            p=run(label,[a.tool/'vsim.exe','-c','-onfinish','stop','work.main_tb_pwm_coherent_capture','-gCOUNT_W='+str(c),'-gWITNESS_W='+str(w),'-gTAG_W='+str(t),'+VECTORS='+v.name,'+TRACE='+ports.name,'-do',do.name]);raw=p.stdout+p.stderr
            passed=p.returncode==0 and b'MAIN_COHERENT_CAPTURE_PASS' in raw and not re.search(rb'\*\* (?:Error|Fatal)',raw);rec.update(passed=passed,ports_sha256=sha(ports) if ports.exists() else None);save()
            if a.negative:
                assert not passed and b'PUBLIC_PORT_MISMATCH' in raw;r['status']='expected_public_port_rejection';save();print(json.dumps(r));return
            assert passed,label
            lines=ports.read_text().splitlines();assert len(lines)==len(o.rows);edges=0
            for i,(line,row) in enumerate(zip(lines,o.rows)):
                edges+=row[0];got=line.split();assert [int(x) for x in got[:3]]==[i,edges,row[0]] and [int(x,16) for x in got[3:]]==row[7:]
        if a.freeze_only:r['status']='oracle_frozen';r['provenance_requires_main_receipt']=True
        else:
            r['invalid_parameters']=[]
            for c,w,t in [(1,8,32),(33,8,32),(0,8,32),(-1,8,32),(3,1,32),(3,65,32),(3,0,32),(3,-1,32),(3,8,0),(3,8,-1),(3,8,65)]:
                label='invalid_c%d_w%d_t%d'%(c,w,t);p=run(label,[a.tool/'vsim.exe','-c','-onfinish','stop','work.main_tb_pwm_coherent_capture','-gCOUNT_W='+str(c),'-gWITNESS_W='+str(w),'-gTAG_W='+str(t),'+VECTORS='+v.name,'+TRACE='+label+'.ports.txt','-do',do.name]);raw=p.stdout+p.stderr
                fatal=re.search(rb'\*\* Fatal:[^\r\n]*',raw);assert fatal and b'MAIN_COHERENT_CAPTURE_PASS' not in raw
                line=fatal.group();assert b'UNSUPPORTED' in line.upper() or b'PARAMETER' in line.upper()
                assert all(s.encode() in line for s in ['COUNT_W=%d'%c,'WITNESS_W=%d'%w,'TAG_W=%d'%t]),'explicit DUT diagnostic must identify the unsupported parameter values'
                r['invalid_parameters'].append({'count_w':c,'witness_w':w,'tag_w':t,'explicit_guard':True,'exit_code':p.returncode})
            r['status']='passed'
        save();print(json.dumps(r))
    except Exception as e:r.update(status='failed',error=repr(e));save();raise
if __name__=='__main__':main()
