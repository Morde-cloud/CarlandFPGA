"""Independent interval-deadline oracle and public-port RTL replay (operation12).

DEEPEYE-HUMAN-LOCK-20261014/r1 H01-H15 requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
No author model import, no hierarchical force/seed, no physical-clock claim.
"""
import argparse,hashlib,itertools,json,os,random,re,shutil,subprocess,sys
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class Oracle:
    # Absolute edge deadlines instead of a wrapping RTL phase counter.
    def __init__(self):
        self.edge=-1;self.active=None;self.queued=None;self.origin=None;self.boundary=None
        self.rows=[];self.cover={}
    def step(self,reset=0,stop=0,valid=0,p=0,a=0,b=0,c=0,tag=0,label=None):
        self.edge+=1;t=self.edge
        pre=int(not reset and not stop and self.queued is None)
        accepted=rejected=applied=start=0
        if reset or stop:
            self.active=self.queued=self.origin=self.boundary=None
        else:
            old=self.queued
            boundary=self.active is None or t==self.boundary
            if boundary and old is not None:
                self.active=old;self.queued=None;applied=1
            if boundary and self.active is not None:
                self.origin=t;self.boundary=t+self.active[0];start=1
            if pre and valid:
                if p and max(a,b,c)<=p:self.queued=(p,a,b,c,tag);accepted=1
                else:rejected=1
        post=int(not reset and not stop and self.queued is None)
        active=self.active or (0,0,0,0,0)
        levels=0
        if self.active:
            # Membership of each channel's half-open high interval.
            for bit,width in enumerate(active[1:4]):
                if self.origin<=t<self.origin+width:levels|=1<<bit
        expected=[pre,post,accepted,rejected,applied,start,int(self.active is not None),int(self.queued is not None),levels,*active]
        self.rows.append([reset,stop,valid,p,a,b,c,tag,*expected])
        if label:self.cover[label]=self.cover.get(label,0)+1
        return expected

def vectors(w,tagw):
    o=Oracle();limit=(1<<w)-1;tm=(1<<tagw)-1
    if w<=3:
        for p in range(1,limit+1):
            for hs in itertools.product(range(p+1),repeat=3):
                o.step(reset=1);o.step(valid=1,p=p,a=hs[0],b=hs[1],c=hs[2],tag=(len(o.rows)*7919)&tm,label='exhaustive_legal_tuple')
                for _ in range(2*p+1):o.step()
        # Every phase, two kinds of abort and boundary acceptance versus application.
        for p in range(1,limit+1):
            for at in range(p):
                for abort in ['reset','stop','none']:
                    o.step(reset=1);o.step(valid=1,p=p,a=p,b=p//2,c=0,tag=tm);o.step()
                    for _ in range(at):o.step()
                    o.step(valid=1,p=limit,a=0,b=limit,c=1,tag=1,label='boundary_position')
                    for j in range(p+limit+2):
                        opts={abort:1} if abort!='none' and j==0 else {}
                        o.step(valid=1,p=1,a=1,b=1,c=1,tag=tm,**opts,label='abort_or_busy_overlap')
                    o.step(stop=1)
    else:
        # Public-port bounded observations, explicitly NOT full max32 periods.
        for p in [1,2,3,17,127,0x7fffffff,0x80000000,0xfffffffe,0xffffffff,2000000]:
            for hs in [(0,0,0),(p,p,p),(1,0,p),(p//2,p,0)]:
                o.step(reset=1);o.step(valid=1,p=p,a=hs[0],b=hs[1],c=hs[2],tag=tm,label='32bit_legal_tuple')
                for _ in range(min(2*p+1,260)):o.step()
                o.step(stop=1,label='32bit_partial_abort' if p>127 else '32bit_full_frames')
        for p,hs in [(0,(0,0,0)),(1,(0x80000000,0,0)),(0x7fffffff,(0,0x80000000,0)),(0xfffffffe,(0,0,0xffffffff))]:
            o.step(valid=1,p=p,a=hs[0],b=hs[1],c=hs[2],tag=tm,label='unsigned_invalid')
    # Stable seed and actual accepted-state oracle exercise held/busy/invalid/stop.
    rng=random.Random(0x20261020+w+tagw)
    for i in range(6000):
        p=rng.randint(0,min(limit,31));hs=[rng.randint(0,min(limit,33)) for _ in range(3)]
        if i%7==0:hs=[min(p,x) for x in hs]
        o.step(reset=int(i%337==0),stop=int(i%139==0),valid=int(rng.random()<.8),p=p,a=hs[0],b=hs[1],c=hs[2],tag=rng.getrandbits(tagw),label='random_cycle')
    o.step(reset=1);o.step();return o

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rtl',type=Path,required=True);ap.add_argument('--tb',type=Path,required=True)
    ap.add_argument('--tool',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--owned-root',type=Path,required=True)
    ap.add_argument('--cases',default='2:1,3:64,32:32');ap.add_argument('--negative',action='store_true');ap.add_argument('--long',action='store_true');args=ap.parse_args()
    out=args.out.resolve();owned=args.owned_root.resolve();assert out.is_relative_to(owned) and out!=owned and not out.exists()
    rtl=args.rtl.resolve();tb=args.tb.resolve();assert rtl.is_file() and tb.is_file() and not rtl.is_relative_to(out) and not tb.is_relative_to(out)
    out.mkdir(parents=True);commands=[];runs=[]
    receipt={'operation_id':'B-DEEPEYE-PWM-ATOMIC-20261020-12','kind':'main_independent_public_ports','rtl':str(rtl),'rtl_sha256':sha(rtl),'tb_sha256':sha(tb),'runner_sha256':sha(Path(__file__)),'negative_control':args.negative,'commands':commands,'runs':runs,'status':'started'}
    def save(): (out/'result.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    def run(name,cmd,cwd):
        try:
            p=subprocess.run([str(x) for x in cmd],cwd=cwd,capture_output=True,timeout=180,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        except subprocess.TimeoutExpired as e:
            (out/(name+'.stdout.txt')).write_bytes(e.stdout or b'');(out/(name+'.stderr.txt')).write_bytes(e.stderr or b'')
            commands.append({'name':name,'command':[str(x) for x in cmd],'cwd':str(cwd),'exit_code':None,'timeout_seconds':180});save();raise
        except OSError as e:
            commands.append({'name':name,'command':[str(x) for x in cmd],'cwd':str(cwd),'exit_code':None,'error':repr(e)});save();raise
        (out/(name+'.stdout.txt')).write_bytes(p.stdout);(out/(name+'.stderr.txt')).write_bytes(p.stderr)
        row={'name':name,'command':[str(x) for x in cmd],'cwd':str(cwd),'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()};commands.append(row);save()
        return p
    try:
        for name in ['vlog','vsim']:
            p=run(name+'-version',[args.tool/(name+'.exe'),'-version'],out);assert p.returncode==0
        shutil.copyfile(rtl,out/'dut.sv');shutil.copyfile(tb,out/'tb.sv');shutil.copyfile(Path(__file__),out/'runner.py')
        p=run('vlib',[args.tool/'vlib.exe','work'],out);assert p.returncode==0
        p=run('vlog',[args.tool/'vlog.exe','-sv','-work','work','dut.sv','tb.sv'],out)
        assert p.returncode==0 and not re.search(rb'\*\* (?:Error|Fatal)',p.stdout+p.stderr)
        for case in args.cases.split(','):
            w,t=map(int,case.split(':'));o=vectors(w,t);label='w%d_t%d'%(w,t)
            vfile=out/(label+'.vectors.txt');trace=out/(label+'.ports.txt')
            vfile.write_text(str(len(o.rows))+'\n'+'\n'.join(' '.join('%x'%x for x in r) for r in o.rows)+'\n',encoding='ascii')
            dofile=out/(label+'.do');dofile.write_text('onerror {quit -code 1}\nrun -all\nquit -code 0\n',encoding='ascii')
            cmd=[args.tool/'vsim.exe','-c','-onfinish','stop','work.main_tb_atomic_pwm','-gCOUNT_W='+str(w),'-gTAG_W='+str(t),'+VECTORS='+vfile.name,'+TRACE='+trace.name,'-do',dofile.name]
            p=run(label,cmd,out);passed=p.returncode==0 and b'MAIN_PWM_PASS' in p.stdout and not re.search(rb'\*\* (?:Error|Fatal)',p.stdout+p.stderr)
            record={'count_w':w,'tag_w':t,'rows':len(o.rows),'coverage':o.cover,'vectors_sha256':sha(vfile),'ports_sha256':sha(trace) if trace.exists() else None,'passed':passed};runs.append(record);save()
            if args.negative:
                assert not passed and b'Fatal' in p.stdout and b'row=' in p.stdout,'mutation must produce public-port mismatch'
                receipt['status']='expected_public_port_rejection';save();print(json.dumps(receipt));return
            assert passed,label+' failed'
            lines=trace.read_text().splitlines();assert len(lines)==len(o.rows)
            for i,(line,row) in enumerate(zip(lines,o.rows)):
                got=line.split();assert int(got[0])==i and [int(x,16) for x in got[1:]]==row[8:]
        if args.long:
            dofile=out/'long.do';dofile.write_text('onerror {quit -code 1}\nrun -all\nquit -code 0\n',encoding='ascii')
            p=run('long',[args.tool/'vsim.exe','-c','-onfinish','stop','work.main_tb_atomic_pwm_long','-do',dofile.name],out)
            assert p.returncode==0 and b'MAIN_PWM_LONG_PASS' in p.stdout and not re.search(rb'\*\* (?:Error|Fatal)',p.stdout+p.stderr)
            receipt['long_case']={'full_frame_intervals':2000000,'high_counts':[10000,490000,70000],'new_period':37,'new_complete_frames':2,'passed':True}
        receipt['invalid_parameters']=[]
        for w,t in [(1,32),(33,32),(3,0),(3,65)]:
            label='invalid_w%d_t%d'%(w,t)
            cmd=[args.tool/'vsim.exe','-c','-onfinish','stop','work.main_tb_atomic_pwm','-gCOUNT_W='+str(w),'-gTAG_W='+str(t),'+VECTORS='+vfile.name,'+TRACE='+label+'.ports.txt','-do',dofile.name]
            p=run(label,cmd,out);raw=p.stdout+p.stderr
            assert b'MAIN_PWM_PASS' not in raw and re.search(rb'\*\* (?:Error|Fatal)',raw) and re.search(rb'(?i)COUNT_W|TAG_W|parameter',raw),'invalid parameter must explicitly reject'
            receipt['invalid_parameters'].append({'count_w':w,'tag_w':t,'rejected':True,'exit_code':p.returncode});save()
        receipt['status']='passed';save();print(json.dumps(receipt))
    except Exception as e:
        receipt.update(status='failed',error=repr(e));save();raise
if __name__=='__main__':main()
